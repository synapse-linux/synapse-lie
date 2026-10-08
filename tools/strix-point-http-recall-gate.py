#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Optional .161 development coordinator; the recall client itself is native C.

Run one frozen cold, two-turn corpus in an independently admitted GPU window.
This helper owns only its server and client; the campaign owns the outer lease,
thermal observations, container and router stop/restore. No retry or tuning.
"""

import argparse
import datetime
import hashlib
import http.client
import json
import math
from pathlib import Path
import signal
import socket
import subprocess
import time

ROOT = Path('/work')
MODEL_ID = 'qwen3.8-flash-next'
PROFILE_LIMITS = {'native': 262144, 'yarn2': 524288, 'yarn4': 1048576}
SETTINGS = {'context', 'rope_scaling', 'size', 'chunk', 'seed',
            'request_timeout_seconds', 'load_timeout_seconds'}
TURNS = 2
OUTPUT_TOKENS = 128


def settings(value):
    if type(value) is not dict or set(value) != SETTINGS:
        raise ValueError('Expected complete HTTP recall settings')
    rope = value['rope_scaling']
    if type(rope) is not str or rope not in PROFILE_LIMITS:
        raise ValueError('Unknown recall RoPE profile')
    bounds = {'context': (4096, PROFILE_LIMITS[rope]),
              'size': (128, 1048576), 'chunk': (1, 32768),
              'seed': (0, 2**64-1), 'request_timeout_seconds': (30, 14400),
              'load_timeout_seconds': (30, 1800)}
    for name, (low, high) in bounds.items():
        if type(value[name]) is not int or not low <= value[name] <= high:
            raise ValueError('Invalid recall setting: '+name)
    if value['size'] + TURNS * OUTPUT_TOKENS + 256 > value['context']:
        raise ValueError('Recall target leaves insufficient continuation capacity')
    if value['chunk'] > value['context']:
        raise ValueError('Recall chunk exceeds context capacity')
    return dict(value)


def client_timeout(config):
    # Three calibration requests and two measured turns, plus client overhead.
    return 5 * config['request_timeout_seconds'] + 30


def container_timeout(config):
    return config['load_timeout_seconds'] + client_timeout(config) + 60


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def unique_object(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('Duplicate JSON property: '+key)
        result[key] = value
    return result


def strict_json(text):
    def nonfinite(value):
        raise ValueError('Nonfinite JSON number: '+value)
    return json.loads(text, object_pairs_hook=unique_object, parse_constant=nonfinite)


def json_lines(path, limit):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise RuntimeError('Missing or oversized recall artifact: '+str(path))
    return [strict_json(line) for line in path.read_text().splitlines()]


def private_ports():
    # Hold both reservations while selecting; collision after release is a
    # recorded server-start failure, never grounds for an automatic retry.
    with socket.socket() as api, socket.socket() as management:
        api.bind(('127.0.0.1', 0))
        management.bind(('127.0.0.1', 0))
        return api.getsockname()[1], management.getsockname()[1]


def listed_model(port):
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
    try:
        connection.request('GET', '/v1/models')
        response = connection.getresponse()
        body = response.read(1024 * 1024 + 1)
        return (response.status == 200 and len(body) <= 1024 * 1024 and
                MODEL_ID in {row['id'] for row in strict_json(body)['data']})
    finally:
        connection.close()


def server_command(args, config, api, management):
    command = [args.server, '--model', args.model, '--model-id', MODEL_ID,
               '--host', '127.0.0.1', '--port', str(api),
               '--management-host', '127.0.0.1', '--management-port', str(management),
               '--context', str(config['context']), '--rope-scaling', config['rope_scaling'],
               '--prefill-chunk', str(config['chunk']),
               '--prefill-capacity', str(config['chunk']), '--max-active', '1',
               '--kv-cache-ram-mb', '0', '--request-timeout-ms',
               str(config['request_timeout_seconds'] * 1000)]
    if args.mode == 'mtp':
        command += ['--model-mtp', args.predictor, '--mtp-draft-tokens', '7']
    return command


def client_command(args, config, api):
    return [args.client, '--suite', 'http', '--url', f'http://127.0.0.1:{api}/v1',
            '--model', MODEL_ID, '--preset', 'long-context-recall',
            '--sizes', str(config['size']), '--context-capacity', str(config['context']),
            '--rope-scaling', config['rope_scaling'], '--tg', str(OUTPUT_TOKENS),
            '--turns', str(TURNS), '--corpus-seed', str(config['seed']),
            '--warmups', '0', '--repetitions', '1', '--server-kv-cache', 'off',
            '--timeout', str(config['request_timeout_seconds']), '--server-label', 'LIE',
            '--output', str(ROOT/'measurements.jsonl'),
            '--export-requests', str(ROOT/'requests.jsonl')]


def integer(value, low=0, high=2**63-1):
    return type(value) is int and low <= value <= high


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def validate(rows, cases, config, mode):
    """Check actual requests, continuation, physical counts and answers afresh.

    Do not turn a native quality miss into transport failure or accept a green
    summary without the exported corpus and both complete measured responses.
    """
    if len(rows) != 7 or len(cases) != 1 or any(type(row) is not dict for row in rows):
        raise RuntimeError('Incomplete recall calibration or measured turns')
    identity, terminal = rows[0], rows[-1]
    wanted = {'event': 'identity', 'schema': 'synapse-lie.http-bench.v1',
              'model': MODEL_ID, 'server_label': 'LIE', 'cache_policy': 'off',
              'warmups': 0, 'repetitions': 1, 'preset': 'long-context-recall',
              'context_capacity_declared': config['context'],
              'rope_scaling_declared': config['rope_scaling'],
              'timeout_seconds': config['request_timeout_seconds'],
              'target_prompt_tokens': [config['size']], 'corpus_seed': config['seed'],
              'request_options': {}}
    if any(identity.get(key) != value for key, value in wanted.items()):
        raise RuntimeError('Recall client identity differs from the admitted workload')
    for key in ('warmups', 'repetitions', 'context_capacity_declared', 'corpus_seed'):
        if type(identity.get(key)) is not int:
            raise RuntimeError('Untyped recall identity count')
    calibration = rows[1:4]
    if [r.get('event') for r in calibration] != ['calibration'] * 3 or \
            [r.get('lines') for r in calibration] != [8, 16, 32]:
        raise RuntimeError('Missing native prompt calibration')
    counts = [r.get('usage', {}).get('prompt_tokens') for r in calibration]
    if any(not integer(n, 1) for n in counts):
        raise RuntimeError('Invalid physical calibration usage')
    if any(r.get('cached_tokens') != 0 or r.get('stream_complete') is not True
           for r in calibration):
        raise RuntimeError('Calibration did not complete on a cold server')
    step = counts[1] - counts[0]
    unit, remainder = divmod(step, 8)
    intercept = counts[0] - 8 * unit
    if unit <= 0 or remainder or counts[2] != intercept + 32 * unit:
        raise RuntimeError('Nonlinear physical calibration')
    case = cases[0]
    if type(case) is not dict:
        raise RuntimeError('Invalid exported recall case')
    corpus, body, oracles = case.get('corpus'), case.get('body'), case.get('expected')
    if (type(corpus) is not dict or type(body) is not dict or type(oracles) is not list or
            len(oracles) != TURNS or corpus.get('generator') != 'lie-associative-recall-v1' or
            not integer(corpus.get('seed'), 0, 2**64-1) or corpus['seed'] != config['seed'] or
            not integer(corpus.get('records'), 4, 1048576) or
            corpus.get('position_units') != 'zero-based record index and UTF-8 byte offset; not token offsets' or
            case.get('target_prompt_tokens') != config['size'] or
            case.get('id') != 'long-context-recall-'+str(config['size']) or
            case.get('expected_prompt_tokens') != intercept + corpus['records'] * unit or
            not config['size'] - unit < case['expected_prompt_tokens'] <= config['size']):
        raise RuntimeError('Exported corpus, seed or physical target mismatch')
    messages = body.get('messages')
    if (type(messages) is not list or len(messages) != 1 or
            set(messages[0]) != {'role', 'content'} or messages[0]['role'] != 'user' or
            type(messages[0]['content']) is not str or body.get('max_tokens') != OUTPUT_TOKENS or
            set(body) != {'messages', 'max_tokens'}):
        raise RuntimeError('Unexpected exported recall request body')
    prompt = messages[0]['content'].encode('utf-8')
    if corpus.get('prompt_bytes') != len(prompt):
        raise RuntimeError('Recall prompt byte count changed')
    needles = corpus.get('needles')
    if type(needles) is not list or len(needles) != 3:
        raise RuntimeError('Missing independent recall bindings')
    values = []
    for index, (position, record) in enumerate(zip(
            ('start', 'middle', 'end'), (0, corpus['records']//2, corpus['records']-1))):
        key = 'key_' + hashlib.sha256(
            f'lie-associative-recall-v1:key:{config["seed"]}:{index}'.encode()).hexdigest()[:16]
        value = 'v_' + hashlib.sha256(
            f'lie-associative-recall-v1:value:{config["seed"]}:{index}'.encode()).hexdigest()[:16]
        needle = needles[index]
        if (type(needle) is not dict or needle.get('region') != position or
                type(needle.get('record_index')) is not int or needle['record_index'] != record or needle.get('key') != key or
                not integer(needle.get('prompt_byte_offset'), 0, len(prompt))):
            raise RuntimeError('Seeded binding or original-ledger position changed')
        offset = needle['prompt_byte_offset']
        binding = f'binding {key} = {value}\n'.encode()
        if prompt[offset:offset+len(binding)] != binding or \
                prompt[:offset].count(b'\n') != record + 1:
            raise RuntimeError('Binding does not occupy its declared record position')
        values.append((key, value))
    expected = [{values[1][0]: values[1][1]}, dict((values[0], values[2]))]
    if oracles != [{'kind': 'json-object-exact', 'value': value} for value in expected]:
        raise RuntimeError('Independent per-turn recall oracles changed')
    followups = case.get('followups')
    if (type(followups) is not list or len(followups) != 1 or
            type(followups[0]) is not str or not all(k in followups[0] for k in expected[1]) or
            any(v in followups[0] for v in expected[1].values())):
        raise RuntimeError('Continuation question leaks or omits an unanswered binding')
    request = {'model': MODEL_ID, 'temperature': 0, **body, 'stream': True,
               'stream_options': {'include_usage': True}}
    passes, drafted, accepted = 0, 0, 0
    for turn, row in enumerate(rows[4:6]):
        if (row.get('event') != 'sample' or row.get('case') != case['id'] or
                type(row.get('turn')) is not int or row['turn'] != turn or
                type(row.get('rep')) is not int or row['rep'] != 0 or
                row.get('warmup') is not False or row.get('corpus') != corpus or
                row.get('request') != request or row.get('stream_complete') is not True):
            raise RuntimeError('Actual measured request or continuation differs from the corpus')
        pp, tg, cached = (row.get(k) for k in ('prompt_tokens', 'output_tokens', 'cached_tokens'))
        usage, phase = row.get('usage', {}), row.get('server_timings', {})
        if (not integer(pp, 1, config['context']-OUTPUT_TOKENS) or
                not integer(tg, 1, OUTPUT_TOKENS) or type(cached) is not int or cached != 0 or
                usage.get('prompt_tokens') != pp or usage.get('completion_tokens') != tg or
                phase.get('schema') != 'synapse-lie.request-timings.v1' or
                phase.get('valid') is not True or phase.get('decode_mode') != mode or
                phase.get('prefill_tokens') != pp or phase.get('decode_tokens') != tg or
                phase.get('cached_tokens') != 0 or phase.get('ssd_cached_tokens') != 0 or
                not positive(phase.get('prefill_ms')) or not positive(phase.get('decode_ms')) or
                row.get('finish_reason') not in ('stop', 'length')):
            raise RuntimeError('Physical prompt, cold cache or executor timing unverified')
        if not turn and (pp != case['expected_prompt_tokens'] or
                         row.get('target_prompt_tokens') != config['size']):
            raise RuntimeError('First measured prompt differs from calibrated physical input')
        if turn and (row.get('target_prompt_tokens') is not None or
                     pp <= rows[4]['prompt_tokens']):
            raise RuntimeError('Continuation did not retain the original ledger')
        if mode == 'mtp':
            draft, accept = phase.get('mtp_drafted_tokens'), phase.get('mtp_accepted_tokens')
            if not integer(draft) or not integer(accept, 0, draft):
                raise RuntimeError('Invalid measured speculative accounting')
            drafted += draft
            accepted += accept
        assistant = row.get('assistant')
        if (type(assistant) is not dict or assistant.get('role') != 'assistant' or
                type(assistant.get('content')) is not str):
            raise RuntimeError('Missing complete assistant observation')
        answer = None
        try:
            answer = strict_json(assistant['content'])
        except (ValueError, TypeError):
            pass
        matched = ('tool_calls' not in assistant and type(answer) is dict and
                   all(type(v) is str for v in answer.values()) and answer == expected[turn])
        quality = row.get('quality', {})
        if (quality.get('kind') != 'json-object-exact' or quality.get('pass') is not matched or
                quality.get('status') != ('PASS' if matched else 'FAIL') or
                quality.get('expected') != expected[turn] or
                quality.get('output_budget_reached') is not (row['finish_reason'] == 'length')):
            raise RuntimeError('Native score differs from independent exact-answer evaluation')
        passes += matched
        if not turn:
            request = {**request, 'messages': messages + [assistant, {'role': 'user', 'content': followups[0]}]}
    summary = {'checks': TURNS, 'passes': passes, 'warmup_checks': 0,
               'warmup_passes': 0, 'exact_match_rate': passes / TURNS}
    success = passes == TURNS
    actual_summary = terminal.get('quality_summary')
    if (terminal.get('event') != ('complete' if success else 'quality_failed') or
            type(terminal.get('exit_code')) is not int or terminal['exit_code'] != (0 if success else 1) or
            type(actual_summary) is not dict or actual_summary != summary or
            any(type(actual_summary.get(key)) is not int
                for key in ('checks', 'passes', 'warmup_checks', 'warmup_passes'))):
        raise RuntimeError('Terminal quality summary differs from both complete observations')
    if mode == 'mtp' and drafted == 0:
        raise RuntimeError('MTP-enabled server supplied no measured draft proposals')
    return {'samples': TURNS, 'quality_summary': summary,
            'state': 'PASSED' if success else 'QUALITY_FAILED',
            'mtp_drafted_tokens': drafted, 'mtp_accepted_tokens': accepted}


def process_identity(child):
    stat = Path(f'/proc/{child.pid}/stat').read_text()
    fields = stat[stat.rfind(')')+2:].split()
    return {'pid': child.pid, 'start_ticks': int(fields[19]),
            'cgroup': Path(f'/proc/{child.pid}/cgroup').read_text()}


def retire(child):
    if child.poll() is None:
        child.terminate()
    try:
        return child.wait(timeout=15)
    except subprocess.TimeoutExpired:
        child.kill()
        return child.wait(timeout=15)


def run(args, config):
    result_path = ROOT/'http-recall-result.json'
    if result_path.exists():
        raise RuntimeError('Refusing recall campaign replay')
    api, management = private_ports()
    result = {'schema': 'synapse-lie.point-http-recall-original.v1',
              'state': 'RUNNING', 'started_at': now(), 'mode': args.mode,
              'settings': config, 'api_port': api, 'management_port': management,
              'server_argv': server_command(args, config, api, management),
              'client_argv': client_command(args, config, api),
              'client_timeout_seconds': client_timeout(config)}
    children = {}

    def interrupted(number, _frame):
        raise RuntimeError(f'Interrupted by signal {number}')

    signals = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)
    handlers = {number: signal.signal(number, interrupted) for number in signals}
    try:
        with (ROOT/'server.log').open('xb') as log:
            children['server'] = subprocess.Popen(result['server_argv'], stdout=log,
                                                 stderr=subprocess.STDOUT)
            result['server_identity'] = process_identity(children['server'])
            (ROOT/'http-started.marker').write_text(str(children['server'].pid)+'\n')
            deadline = time.monotonic() + config['load_timeout_seconds']
            while True:
                if children['server'].poll() is not None:
                    raise RuntimeError('Owned server exited during model load')
                try:
                    if listed_model(api):
                        break
                except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException):
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError('Original-weight model readiness deadline')
                time.sleep(.25)
            result['ready_at'] = now()
            with (ROOT/'client.stdout.log').open('xb') as stdout, \
                 (ROOT/'client.stderr.log').open('xb') as stderr:
                children['client'] = subprocess.Popen(result['client_argv'], stdout=stdout, stderr=stderr)
                result['client_identity'] = process_identity(children['client'])
                try:
                    result['client_exit_code'] = children['client'].wait(timeout=client_timeout(config))
                except subprocess.TimeoutExpired:
                    result['client_timed_out'] = True
                    raise RuntimeError('Native recall client deadline')
            rows = json_lines(ROOT/'measurements.jsonl', 32*1024*1024)
            cases = json_lines(ROOT/'requests.jsonl', 8*1024*1024)
            proof = validate(rows, cases, config, args.mode)
            if result['client_exit_code'] != (0 if proof['state'] == 'PASSED' else 1):
                raise RuntimeError('Native client exit differs from measured quality outcome')
            result.update(proof)
    except BaseException as error:
        result['state'] = 'FAILED'
        result['error'] = repr(error)
    finally:
        for number in signals:
            signal.signal(number, signal.SIG_IGN)
        result['cleanup_errors'] = []
        for name in ('client', 'server'):
            if name in children:
                try:
                    result[name+'_exit_code'] = retire(children[name])
                except BaseException as error:
                    result['cleanup_errors'].append(name+': '+repr(error))
                    result['state'] = 'FAILED'
        for name in ('measurements.jsonl', 'requests.jsonl'):
            path = ROOT/name
            if path.is_file() and not path.is_symlink():
                result[name.split('.')[0]+'_sha256'] = sha(path)
                result[name.split('.')[0]+'_bytes'] = path.stat().st_size
        if result.get('server_exit_code') not in (0, -signal.SIGTERM):
            result['state'] = 'FAILED'
        result['ended_at'] = now()
        with result_path.open('x') as output:
            output.write(json.dumps(result, indent=2)+'\n')
        for number, handler in handlers.items():
            signal.signal(number, handler)
    return 0 if result['state'] == 'PASSED' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('ar', 'mtp'), required=True)
    parser.add_argument('--settings', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--predictor')
    parser.add_argument('--server', required=True)
    parser.add_argument('--client', required=True)
    args = parser.parse_args()
    if (args.mode == 'mtp') != bool(args.predictor):
        parser.error('MTP requires exactly one predictor; AR must omit it')
    try:
        config = settings(strict_json(Path(args.settings).read_text()))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return run(args, config)


if __name__ == '__main__':
    raise SystemExit(main())
