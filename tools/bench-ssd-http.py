#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""SSD HTTP restart/concurrency client. Server ownership and GPU admission are external."""
import argparse
import concurrent.futures
import csv
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import socket
import statistics
import threading
import time
from urllib.parse import urlsplit

SCHEMA = 'synapse-lie.http-ssd-bench.v1'
LIMIT = 32 * 1024 * 1024


class Inconclusive(RuntimeError):
    """The required scheduling window was not observed; never a passing witness."""


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def count(value, name, maximum=2**64-1):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError('invalid count: ' + name)
    return value


def distribution(values):
    if not values:
        return None
    if any(type(x) not in (int, float) or not math.isfinite(x) or x < 0 for x in values):
        raise ValueError('invalid latency sample')
    ordered = sorted(values)
    # Nearest-rank percentiles remain honest for small n; they are not CIs.
    return dict(n=len(values), mean=statistics.fmean(values), min=ordered[0], max=ordered[-1],
                **{'p'+str(p): ordered[max(0, math.ceil(len(values)*p/100)-1)] for p in (50, 95, 99)})


def validate_cases(cases):
    if not isinstance(cases, list) or not 2 <= len(cases) <= 8:
        raise ValueError('two to eight distinct prompt cases required')
    ids = set()
    for case in cases:
        if (not isinstance(case, dict) or set(case) != {'id', 'prompt', 'max_tokens'} or
                not isinstance(case['id'], str) or not case['id'] or len(case['id']) > 80 or
                case['id'] in ids or not isinstance(case['prompt'], str) or not case['prompt'] or
                len(case['prompt'].encode()) > 7*1024*1024 or
                type(case['max_tokens']) is not int or not 1 <= case['max_tokens'] <= 4096):
            raise ValueError('invalid prompt case')
        ids.add(case['id'])
    return cases


def validate_chat(usage, timings, budget):
    prompt = count(usage['prompt_tokens'], 'prompt')
    output = count(usage['completion_tokens'], 'output', budget)
    cached = count(usage.get('prompt_tokens_details', {}).get('cached_tokens', 0), 'cached', prompt)
    if not prompt or count(usage['total_tokens'], 'total') != prompt+output:
        raise ValueError('invalid usage sum')
    if (timings['schema'] != 'synapse-lie.request-timings.v1' or timings['valid'] is not True or
            timings['scope'] != 'synchronous_executor_calls'):
        raise ValueError('invalid timing schema')
    for key in ('prefill_tokens', 'decode_tokens', 'prefill_calls', 'decode_calls', 'cached_tokens', 'ssd_cached_tokens'):
        count(timings[key], key)
    if (timings['cached_tokens'] != cached or timings['prefill_tokens']+cached != prompt or
            timings['decode_tokens'] != output or not 0 <= timings['ssd_cached_tokens'] <= cached or
            timings['decode_calls'] not in (output, output+1)):
        raise ValueError('cache/executor accounting mismatch')
    for phase in ('prefill', 'decode'):
        tokens, calls = timings[phase+'_tokens'], timings[phase+'_calls']
        ms, rate = timings[phase+'_ms'], timings[phase+'_tokens_per_second']
        if type(ms) not in (int, float) or not math.isfinite(ms) or ms < 0:
            raise ValueError('invalid executor duration')
        if not calls:
            if tokens or ms != 0 or rate is not None:
                raise ValueError('unexecuted phase must have null throughput')
        elif ms <= 0 or type(rate) not in (int, float) or not math.isfinite(rate) or not math.isclose(rate, tokens*1000/ms, rel_tol=1e-12):
            raise ValueError('invalid executor rate')
    for key in ('ssd_read_ms', 'cache_restore_ms', 'cache_capture_ms'):
        value = timings[key]
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError('invalid cache duration')
    return prompt, output, cached


class Client:
    def __init__(self, url, management_url, model, provider, record, check=lambda: None, timeout=180):
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 7200:
            raise ValueError('invalid HTTP timeout')
        self.api, self.management = self.address(url), self.address(management_url)
        self.model, self.provider, self.record, self.check, self.timeout = model, provider, record, check, timeout
        self.lock = threading.Lock()

    @staticmethod
    def address(url):
        value = urlsplit(url)
        if (value.scheme not in ('http', 'https') or not value.hostname or value.username or
                value.password or value.query or value.fragment):
            raise ValueError('HTTP(S) URL without credentials, query or fragment required')
        _ = value.port
        return value

    def connection(self, management=False):
        u = self.management if management else self.api
        return (http.client.HTTPSConnection if u.scheme == 'https' else http.client.HTTPConnection)(u.hostname, u.port, timeout=self.timeout)

    def event(self, kind, **fields):
        with self.lock:
            self.record(dict(event=kind, monotonic_ns=time.monotonic_ns(), **fields))

    def state(self):
        self.check()
        c = self.connection(True)
        try:
            c.request('GET', self.management.path.rstrip('/')+'/actuator/llm')
            response = c.getresponse(); raw = response.read(1024*1024+1)
            if response.status != 200 or len(raw) > 1024*1024:
                raise RuntimeError('management response failed')
            obj = json.loads(raw)
        finally:
            c.close()
        if obj.get('ready') is not True or obj['backend']['engine'] != self.provider or obj['backend']['model'] != self.model:
            raise ValueError('backend readiness/identity mismatch')
        cache, scheduler = obj['cache'], obj['scheduler']
        disk = cache['ssd']
        if cache['enabled'] or not cache['ssd_enabled'] or not disk['enabled']:
            raise ValueError('this SSD experiment requires RAM off and SSD on')
        for key in ('active', 'queued', 'output_blocked', 'completed', 'cancelled', 'failed', 'generated_tokens'):
            count(scheduler[key], key)
        if (scheduler['mode'] != 'single-owner-reactive-ready-batch' or
                not 2 <= scheduler['max_active'] <= 8 or
                not 0 <= scheduler['output_blocked'] <= scheduler['active'] <= scheduler['max_active'] or
                scheduler['active']+scheduler['queued'] > 8):
            raise ValueError('invalid scheduler occupancy')
        for key in ('pending', 'staging_bytes', 'staging_budget_bytes', 'writes', 'hits', 'errors'):
            count(disk[key], key)
        if disk['pending'] > 1 or disk['staging_bytes'] > disk['staging_budget_bytes'] or disk['errors']:
            raise ValueError('SSD resource/error contract')
        return obj

    def poll(self, predicate, description, seconds=None):
        deadline = time.monotonic()+(self.timeout if seconds is None else seconds)
        while True:
            obj = self.state()
            if predicate(obj):
                return obj
            if time.monotonic() >= deadline:
                raise Inconclusive(description+': required state not observed')
            time.sleep(.01)

    def idle(self):
        return self.poll(lambda s: not any(s['scheduler'][k] for k in ('active', 'queued', 'output_blocked')) and not s['cache']['ssd']['pending'], 'idle retirement')

    def payload(self, case, api, stream):
        if api == 'chat':
            body = dict(model=self.model, messages=[{'role': 'user', 'content': case['prompt']}],
                        max_tokens=case['max_tokens'], temperature=0, stream=stream,
                        chat_template_kwargs={'enable_thinking': False})
            if stream: body['stream_options'] = {'include_usage': True}
        elif api == 'responses':
            body = dict(model=self.model, input=case['prompt'], max_output_tokens=case['max_tokens'],
                        temperature=0, stream=stream, store=False)
        else:
            raise ValueError('unsupported HTTP API')
        return body

    def send(self, case, api='chat', stream=True, on_output=None, label='sample', barrier=None, rep=0):
        self.check(); body = self.payload(case, api, stream); wire = encoded(body)
        if len(wire) > 8*1024*1024: raise ValueError('HTTP request bound')
        c = self.connection(); times = []; text = []; frames = []; terminal = None; usage = None; timings = None; finish = None
        begun = time.monotonic_ns()
        try:
            if barrier: barrier.wait(timeout=self.timeout)
            begun = time.monotonic_ns()
            path = self.api.path.rstrip('/')+('/chat/completions' if api == 'chat' else '/responses')
            c.request('POST', path, wire, {'Content-Type': 'application/json'})
            response = c.getresponse()
            if response.status != 200: raise RuntimeError('HTTP '+str(response.status)+': '+response.read(65536).decode(errors='replace'))
            if not stream:
                raw = response.read(LIMIT+1)
                if len(raw) > LIMIT: raise ValueError('HTTP response bound')
                terminal = json.loads(raw)
            else:
                if 'text/event-stream' not in response.getheader('Content-Type', ''): raise ValueError('expected SSE')
                total = 0; event_name = None; done = False; finish_count = 0; stream_id = None
                while True:
                    self.check(); line = response.readline(1024*1024+1); total += len(line)
                    if len(line) > 1024*1024 or total > LIMIT: raise ValueError('SSE response bound')
                    if not line: break
                    if line.startswith(b'event: '): event_name = line[7:].strip().decode(); continue
                    if not line.startswith(b'data: '): continue
                    value = line[6:].strip()
                    if value == b'[DONE]':
                        if api != 'chat' or done or finish_count != 1: raise ValueError('invalid DONE terminal')
                        done = True; break
                    obj = json.loads(value); frames.append(obj)
                    if obj.get('error'): raise ValueError('SSE error')
                    piece = ''
                    if api == 'chat':
                        if (obj.get('system_fingerprint') != self.provider or obj.get('model') != self.model or
                                obj.get('object') != 'chat.completion.chunk' or not isinstance(obj.get('id'), str) or not obj['id']):
                            raise ValueError('stream identity mismatch')
                        if stream_id is not None and stream_id != obj['id']: raise ValueError('stream ID changed')
                        stream_id = obj['id']
                        choices = obj.get('choices')
                        if not isinstance(choices, list) or len(choices) > 1: raise ValueError('invalid choice count')
                        if obj.get('usage'):
                            if usage is not None or choices or finish_count != 1: raise ValueError('invalid stream usage ordering')
                            usage = obj['usage']
                        if 'lie_timings' in obj: timings = obj['lie_timings']
                        for choice in choices:
                            if finish_count: raise ValueError('choice after finish')
                            if choice.get('index') != 0: raise ValueError('multiple choices')
                            piece += choice.get('delta', {}).get('content') or ''
                            if choice.get('finish_reason') is not None:
                                finish = choice['finish_reason']; finish_count += 1
                    else:
                        if obj['type'] != event_name or obj['sequence_number'] != len(frames)-1: raise ValueError('Responses event sequence')
                        if obj['type'] == 'response.output_text.delta': piece = obj['delta']
                        if obj['type'] in ('response.completed', 'response.incomplete'):
                            terminal = obj['response']; done = True; break
                        if obj['type'] in ('response.failed', 'error'): raise ValueError('Responses stream failed')
                    if piece:
                        text.append(piece); times.append(time.monotonic_ns())
                        if on_output: on_output(times[-1])
                if not done: raise ValueError('incomplete SSE stream')
            end = time.monotonic_ns()
            if api == 'chat':
                if not stream:
                    if terminal.get('object') != 'chat.completion' or terminal.get('model') != self.model or terminal.get('system_fingerprint') != self.provider or len(terminal['choices']) != 1:
                        raise ValueError('completion identity')
                    choice = terminal['choices'][0]; text = [choice['message']['content']]
                    usage, timings, finish = terminal['usage'], terminal['lie_timings'], choice['finish_reason']
                prompt, output, cached = validate_chat(usage, timings, case['max_tokens'])
            else:
                if terminal.get('object') != 'response' or terminal.get('model') != self.model or terminal['status'] not in ('completed', 'incomplete') or terminal.get('error'):
                    raise ValueError('Responses terminal failed')
                projected = ''.join(part['text'] for item in terminal['output'] if item['type'] == 'message' for part in item['content'] if part['type'] == 'output_text')
                if stream and ''.join(text) != projected: raise ValueError('Responses delta/terminal disagreement')
                text = [projected]; usage = terminal['usage']
                prompt, output = count(usage['input_tokens'], 'input'), count(usage['output_tokens'], 'output', case['max_tokens'])
                cached = count(usage['input_tokens_details']['cached_tokens'], 'cached', prompt)
                if not prompt or count(usage['total_tokens'], 'total') != prompt+output: raise ValueError('Responses usage sum')
                finish = 'length' if terminal['status'] == 'incomplete' else 'stop'
            if finish not in ('length', 'stop') or (finish == 'length' and output != case['max_tokens']): raise ValueError('invalid output budget/finish')
            row = dict(label=label, rep=rep, case=case['id'], api=api, stream=stream, request=body, request_sha256=digest(body),
                       prompt_tokens=prompt, output_tokens=output, cached_tokens=cached, finish=finish, content=''.join(text),
                       timings=timings, full_output_budget=output == case['max_tokens'], started_ns=begun, finished_ns=end,
                       wall_ms=(end-begun)/1e6, first_output_ms=(times[0]-begun)/1e6 if times else None,
                       output_event_ns=times, inter_output_ms=[(b-a)/1e6 for a,b in zip(times,times[1:])])
            self.event('sample', **row); return row
        except BaseException as ex:
            self.event('request_failed', case=case['id'], api=api, stream=stream, label=label, request_sha256=digest(body), error=repr(ex))
            raise
        finally:
            c.close()


def same_output(row, reference):
    if any(row[k] != reference[k] for k in ('prompt_tokens', 'output_tokens', 'finish', 'content')):
        raise ValueError('fresh/restored output mismatch')


def require_hit(row, chunk):
    expected = max(1, row['prompt_tokens']//chunk)*chunk if row['prompt_tokens'] >= chunk else row['prompt_tokens']
    if row['cached_tokens'] != expected:
        raise ValueError('required SSD prefix was not reused')
    if row['api'] == 'chat' and row['timings']['ssd_cached_tokens'] != expected:
        raise ValueError('required SSD reuse accounting absent')


def run_phase(client, cases, phase, chunk, reference=None, repetitions=3):
    validate_cases(cases)
    if phase not in ('write', 'read') or type(chunk) is not int or not 1 <= chunk <= 262144 or type(repetitions) is not int or not 1 <= repetitions <= 100:
        raise ValueError('invalid SSD phase/profile')
    identity = client.idle(); before = identity['scheduler']; results = []
    if phase == 'write' and identity['cache']['ssd']['entries'] != 0: raise ValueError('writer requires an empty store')
    if phase == 'read':
        if (not isinstance(reference, dict) or reference.get('state') != 'PASS' or reference.get('phase') != 'write' or
                reference.get('cases_sha256') != digest(cases) or reference.get('provider') != client.provider or
                reference.get('chunk') != chunk or reference.get('backend') != identity['backend']):
            raise ValueError('incompatible or incomplete producer reference')
        refs = {x['case']: x for x in reference['samples']}
        if set(refs) != {x['id'] for x in cases}: raise ValueError('missing producer cases')
    for case in cases:
        variants = [('chat', False)] if phase == 'write' else [('chat', False), ('chat', True), ('responses', False), ('responses', True)]
        for rep in range(1 if phase == 'write' else repetitions):
            for api, stream in variants:
                row = client.send(case, api, stream, label='restart-'+phase, rep=rep)
                if phase == 'write':
                    if row['cached_tokens']: raise ValueError('producer unexpectedly reused a prefix')
                else:
                    same_output(row, refs[case['id']]); require_hit(row, chunk)
                results.append(row); client.idle()
    cohorts = []
    if phase == 'read':
        for rep in range(repetitions):
            barrier = threading.Barrier(2); start = time.monotonic_ns()
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(client.send, case, barrier=barrier, label='concurrent-'+str(rep), rep=rep) for case in cases[:2]]
                pair = [f.result(timeout=client.timeout+5) for f in futures]
            finish = time.monotonic_ns()
            for row in pair:
                same_output(row, refs[row['case']]); require_hit(row, chunk)
            results.extend(pair); client.idle()
            cohort = dict(rep=rep, users=2, wall_ms=(finish-start)/1e6,
                          output_over_wall_tps=sum(x['output_tokens'] for x in pair)*1e9/(finish-start))
            cohorts.append(cohort); client.event('cohort', **cohort)
    final = client.idle()
    if final['scheduler']['failed'] != before['failed'] or final['scheduler']['cancelled'] != before['cancelled'] or final['scheduler']['completed'] != before['completed']+len(results):
        raise ValueError('unexpected server activity/request accounting')
    if phase == 'write' and final['cache']['ssd']['writes'] != len(cases): raise ValueError('missing durable producer write')
    if phase == 'read' and final['cache']['ssd']['writes'] != identity['cache']['ssd']['writes']: raise ValueError('reader persisted an unexpected replacement')
    result = dict(schema=SCHEMA, state='PASS', phase=phase, provider=client.provider, synthetic=identity['backend']['synthetic'],
                  backend=identity['backend'], chunk=chunk, cases_sha256=digest(cases), samples=results, cohorts=cohorts,
                  initial=identity, final=final, quantile_method='nearest rank; small n is not a tail-latency confidence estimate',
                  inter_output_scope='nonempty SSE text events, not one measurement per model token')
    client.event('phase_complete', result=result); return result


def run_overlap(client, disk_case, peer_case, references, chunk, read_gate=lambda: None):
    """Observe peer decode and cancellation while one real SSD operation is pending.

    read_gate is a test-only caller hook; production CLI always uses the no-op.
    A missed disk window is INCONCLUSIVE, never inferred from fast total latency.
    """
    before = client.idle(); first = threading.Event(); pending_connection = None
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        peer = pool.submit(client.send, peer_case, on_output=lambda _: first.set(), label='overlap-peer')
        try:
            if not first.wait(client.timeout): raise Inconclusive('peer produced no output')
            read_gate()
            pending_connection = client.connection()
            body = encoded(client.payload(disk_case, 'chat', True))
            pending_connection.request('POST', client.api.path.rstrip('/')+'/chat/completions', body, {'Content-Type': 'application/json'})
            pending = client.poll(lambda s: s['cache']['ssd']['pending'] == 1 and s['scheduler']['active'] == 2, 'SSD overlap admission')
            def progressed(s):
                if not s['cache']['ssd']['pending']: raise Inconclusive('SSD read finished before peer progress witness')
                return s['scheduler']['generated_tokens'] > pending['scheduler']['generated_tokens']
            progress = client.poll(progressed, 'peer progress during SSD read')
            client.event('ssd_overlap_witness', pending=pending, progress=progress)
            pending_connection.close(); pending_connection = None
            cancelled = client.poll(lambda s: s['scheduler']['cancelled'] == before['scheduler']['cancelled']+1, 'disk-wait cancellation')
            client.event('ssd_cancel_witness', state=cancelled, cancelled_while_io_pending=bool(cancelled['cache']['ssd']['pending']))
            if not cancelled['cache']['ssd']['pending']:
                raise Inconclusive('SSD operation retired before cancellation witness')
            if cancelled['scheduler']['failed'] != before['scheduler']['failed']:
                raise ValueError('overlap request failure')
            row = peer.result(timeout=client.timeout+5); same_output(row, references[peer_case['id']]); require_hit(row, chunk)
            return dict(state='PASS', peer_progress_while_ssd_pending=True,
                        cancelled_while_io_pending=bool(cancelled['cache']['ssd']['pending']), peer=row)
        finally:
            if pending_connection: pending_connection.close()


def run_slow_client(client, blocked_case, peer_case, references, chunk):
    """A real unread TCP receive window must stop decode credit, not its peer."""
    if client.api.scheme != 'http': raise ValueError('TCP pressure probe requires plain HTTP')
    before = client.idle(); held = socket.socket(); held.settimeout(client.timeout)
    held.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
    try:
        held.connect((client.api.hostname, client.api.port or 80))
        body = encoded(client.payload(blocked_case, 'chat', True))
        path = client.api.path.rstrip('/')+'/chat/completions'
        held.sendall(f'POST {path} HTTP/1.1\r\nHost: {client.api.hostname}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n'.encode()+body)
        stalled = client.poll(lambda s: s['scheduler']['output_blocked'] == 1 and s['scheduler']['executor']['phase'] == 'none', 'slow-client backpressure')
        if not 0 < stalled['scheduler']['generated_tokens']-before['scheduler']['generated_tokens'] < blocked_case['max_tokens']:
            raise Inconclusive('client did not stall before output budget')
        for _ in range(5):
            time.sleep(.05); state = client.state()
            if (state['scheduler']['output_blocked'] != 1 or
                    state['scheduler']['generated_tokens'] != stalled['scheduler']['generated_tokens'] or
                    state['scheduler']['executor']['decode_started'] != stalled['scheduler']['executor']['decode_started']):
                raise Inconclusive('decode did not remain credit-stalled')
        row = client.send(peer_case, label='slow-client-peer')
        same_output(row, references[peer_case['id']]); require_hit(row, chunk)
        progressed = client.poll(lambda s: s['scheduler']['completed'] == before['scheduler']['completed']+1 and s['scheduler']['output_blocked'] == 1, 'peer completion with slow client')
        held.close()
        client.poll(lambda s: s['scheduler']['cancelled'] == before['scheduler']['cancelled']+1, 'slow-client disconnect')
        final = client.idle()
        if final['scheduler']['failed'] != before['scheduler']['failed']: raise ValueError('peer isolation failed')
        result = dict(state='PASS', before=before, stalled=stalled, progressed=progressed, final=final)
        client.event('slow_client_witness', result=result); return result
    finally:
        held.close()


def summarize(result):
    groups = {}
    for row in result['samples']:
        users = 2 if row['label'].startswith('concurrent-') else 1
        groups.setdefault((row['case'], row['api'], row['stream'], users), []).append(row)
    summary = []
    for (case, api, stream, users), rows in groups.items():
        summary.append(dict(case=case, api=api, stream=stream, users=users, samples=len(rows),
                            full_output_budget=all(x['full_output_budget'] for x in rows),
                            wall_ms=distribution([x['wall_ms'] for x in rows]),
                            first_output_ms=distribution([x['first_output_ms'] for x in rows if x['first_output_ms'] is not None]),
                            inter_output_ms=distribution([t for x in rows for t in x['inter_output_ms']]),
                            executed_pp_tps=distribution([x['timings']['prefill_tokens_per_second'] for x in rows if x['timings'] and x['timings']['prefill_tokens_per_second'] is not None]),
                            executor_tg_tps=distribution([x['timings']['decode_tokens_per_second'] for x in rows if x['timings'] and x['timings']['decode_tokens_per_second'] is not None])))
    return summary


def export(result, directory):
    out = Path(directory); out.mkdir(parents=True, exist_ok=False)
    stats = summarize(result)
    (out/'summary.json').write_text(json.dumps(stats, indent=2)+'\n')
    with (out/'summary.csv').open('w', newline='') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow(['case', 'api', 'stream', 'users', 'samples', 'metric', 'n', 'p50', 'p95', 'p99', 'min', 'max'])
        for group in stats:
            for metric in ('wall_ms', 'first_output_ms', 'inter_output_ms', 'executed_pp_tps', 'executor_tg_tps'):
                d = group[metric]
                writer.writerow([group[k] for k in ('case', 'api', 'stream', 'users', 'samples')]+[metric]+([d[k] for k in ('n', 'p50', 'p95', 'p99', 'min', 'max')] if d else ['']*6))
    os.environ.setdefault('MPLCONFIGDIR', str(out/'matplotlib-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), layout='constrained')
    streamed = [x for x in stats if x['stream']]
    labels = [f"{x['case']}\n{x['api']} C{x['users']}" for x in streamed]
    for ax, metric, title in zip(axes, ['first_output_ms', 'inter_output_ms', 'wall_ms'], ['First text output (ms)', 'Gap between text events (ms)', 'Complete HTTP wall (ms)']):
        for key in ('p50', 'p95', 'p99'):
            ax.plot(range(len(streamed)), [x[metric][key] if x[metric] else math.nan for x in streamed], marker='o', label=key)
        ax.set_xticks(range(len(labels)), labels, rotation=30, ha='right'); ax.set_title(title); ax.legend(); ax.grid(alpha=.2)
    scope = 'NOT-INFERENCE CPU fixture — ' if result['synthetic'] else ''
    fig.suptitle(scope+'SSD HTTP restart — nearest-rank percentiles; see sample counts in CSV\nInter-output events are not individual model tokens; model load/hash excluded')
    fig.savefig(out/'benchmark.png', dpi=150); fig.savefig(out/'benchmark.svg'); plt.close(fig)
    svg = out/'benchmark.svg'; svg.write_text('\n'.join(x.rstrip() for x in svg.read_text().splitlines())+'\n')


def main(argv=None, check=lambda: None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url', required=True, help='Running admitted LIE API base, ending in /v1')
    p.add_argument('--management-url', required=True, help='Management origin without /actuator')
    p.add_argument('--model', required=True); p.add_argument('--provider', required=True)
    p.add_argument('--cases', required=True); p.add_argument('--output', required=True)
    p.add_argument('--phase', required=True, choices=['write', 'read']); p.add_argument('--reference')
    p.add_argument('--chunk', required=True, type=int); p.add_argument('--repetitions', type=int, default=3)
    p.add_argument('--timeout', type=float, default=180); p.add_argument('--overlap', action='store_true')
    p.add_argument('--slow-client', action='store_true'); p.add_argument('--graphs')
    a = p.parse_args(argv)
    if (a.phase == 'read') != bool(a.reference) or ((a.overlap or a.slow_client) and a.phase != 'read'): p.error('read requires a producer reference; overlap/slow-client require read')
    cases = validate_cases(json.loads(Path(a.cases).read_text()))
    reference = json.loads(Path(a.reference).read_text()) if a.reference else None
    with Path(a.output).open('x') as log:
        def record(row): log.write(json.dumps(row, ensure_ascii=False, allow_nan=False)+'\n'); log.flush()
        client = Client(a.url, a.management_url, a.model, a.provider, record, check, timeout=a.timeout)
        client.event('identity', schema=SCHEMA, phase=a.phase, cases_sha256=digest(cases), reference_sha256=hashlib.sha256(Path(a.reference).read_bytes()).hexdigest() if a.reference else None)
        try:
            result = run_phase(client, cases, a.phase, a.chunk, reference, a.repetitions)
            if a.overlap:
                refs = {x['case']: x for x in reference['samples']}
                result['overlap'] = run_overlap(client, cases[0], cases[1], refs, a.chunk)
                client.idle()
                recovery = client.send(cases[0], label='post-cancel-recovery'); same_output(recovery, refs[cases[0]['id']]); require_hit(recovery, a.chunk)
                result['final'] = client.idle()
            if a.slow_client:
                refs = {x['case']: x for x in reference['samples']}
                result['slow_client'] = run_slow_client(client, cases[1], cases[0], refs, a.chunk)
                result['final'] = client.idle()
            result['distributions'] = summarize(result)
            if a.graphs: export(result, a.graphs)
            summary = Path(a.output+'.summary.json')
            with summary.open('x') as f: f.write(json.dumps(result, indent=2)+'\n')
            client.event('complete', state='PASS', summary=str(summary))
        except BaseException as ex:
            client.event('failed', outcome='INCONCLUSIVE' if isinstance(ex, Inconclusive) else 'FAILED', error=repr(ex)); raise
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
