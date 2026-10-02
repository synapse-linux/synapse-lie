#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Real C HTTP/SSD consumer with a deterministic disk barrier. NOT-INFERENCE."""
import copy
import http.client
import importlib.util
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import time
from test_tools_http import port

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ssd_checks', ROOT/'tools/bench-ssd-http.py')
checks = importlib.util.module_from_spec(spec); spec.loader.exec_module(checks)
runner = runpy.run_path(str(ROOT/'tools/run-bench.py'))
PROVIDER = 'cpu-test-fixture-NOT-INFERENCE'
CASES = [{'id': 'disk', 'prompt': 'LONG-A', 'max_tokens': 16},
         {'id': 'peer', 'prompt': 'LONG-B', 'max_tokens': 512}]


def reject(call):
    try: call()
    except (ValueError, KeyError, TypeError): return
    raise AssertionError('invalid evidence accepted')


def parser_failures(client, sample):
    base=dict(id='chatcmpl-fixture',object='chat.completion.chunk',model=client.model,system_fingerprint=PROVIDER)
    content=dict(base,choices=[dict(index=0,delta={'content':sample['content']},finish_reason=None)])
    finish=dict(base,choices=[dict(index=0,delta={},finish_reason=sample['finish'])])
    usage=dict(prompt_tokens=sample['prompt_tokens'],completion_tokens=sample['output_tokens'],
               total_tokens=sample['prompt_tokens']+sample['output_tokens'],
               prompt_tokens_details={'cached_tokens':sample['cached_tokens']})
    terminal=dict(base,choices=[],usage=usage,lie_timings=sample['timings'])
    class Response(io.BytesIO):
        status=200
        def getheader(self,*args):return 'text/event-stream'
    class Connection:
        def request(self,*args):pass
        def close(self):pass
        def getresponse(self):return Response(wire)
    saved=client.connection
    try:
        client.connection=lambda:Connection()
        for frames in ([content,finish,terminal,'[DONE]'], [content,finish,terminal],
                       [content,finish,content,terminal,'[DONE]'], [content,terminal,finish,'[DONE]'],
                       [content,dict(finish,id='other'),terminal,'[DONE]'],
                       [content,dict(finish,choices=finish['choices']*2),terminal,'[DONE]'],
                       [dict(content,model='other'),finish,terminal,'[DONE]']):
            wire=b''.join(b'data: '+(x.encode() if isinstance(x,str) else checks.encoded(x))+b'\n\n' for x in frames)
            if frames == [content,finish,terminal,'[DONE]']:
                checks.same_output(client.send(CASES[0],label='parser-fixture'),sample)
            else:reject(lambda:client.send(CASES[0],label='parser-fixture'))
        wire=b'event: response.completed\ndata: {"type":"response.completed","sequence_number":1}\n\n'
        reject(lambda:client.send(CASES[0],api='responses',label='parser-fixture'))
    finally:client.connection=saved


def run(binary, root, phase, reference=None):
    api, management = port(), port()
    while api == management: management = port()
    gate = root/'gate'; gate.mkdir(exist_ok=True)
    events = []; logpath = root/(phase+'.log')
    with logpath.open('xb') as log:
        proc = subprocess.Popen([binary, '--model', ':fixture:', '--cache-policy', 'legacy', '--port', str(api), '--management-port', str(management),
                                 '--context', '4096', '--prefill-chunk', '4', '--max-active', '2', '--prefix-cache-mib', '0',
                                 '--prefix-ssd-dir', str(root/'store'), '--prefix-ssd-quota-mib', '1', '--prefix-ssd-staging-mib', '1'],
                                stdout=log, stderr=log, env=dict(os.environ, LIE_TEST_SSD_READ_GATE=str(gate)))
        def live():
            if proc.poll() is not None: raise RuntimeError(logpath.read_text())
        client = checks.Client('http://127.0.0.1:'+str(api)+'/v1', 'http://127.0.0.1:'+str(management),
                               'cpu-test-fixture', PROVIDER, events.append, live, timeout=10)
        try:
            deadline = time.monotonic()+6
            while True:
                live()
                try:
                    client.state(); break
                except (OSError, http.client.HTTPException):
                    if time.monotonic()>deadline: raise
                    time.sleep(.01)
            cases_path = root/'cases.json'
            if phase == 'write': cases_path.write_text(json.dumps(CASES))
            output = root/(phase+'.jsonl')
            argv = ['--url', client.api.geturl(), '--management-url', client.management.geturl(),
                    '--model', client.model, '--provider', PROVIDER, '--cases', str(cases_path),
                    '--output', str(output), '--phase', phase, '--chunk', '4', '--timeout', '10', '--repetitions', '2']
            if phase == 'write':
                cli = subprocess.run([sys.argv[2], '--suite', 'http-ssd', *argv], capture_output=True, text=True, timeout=20)
                assert cli.returncode == 0, cli.stderr
            else:
                argv += ['--reference', str(root/'write.jsonl.summary.json')]
                runner['http_ssd_check'](dict(client=argv, ports=[api,management], readiness_timeout=10), checks.__dict__, live)
            assert json.loads(output.read_text().splitlines()[-1])['event'] == 'complete'
            result = json.loads(Path(str(output)+'.summary.json').read_text())
            assert result['synthetic'] and result['state'] == 'PASS'
            if phase == 'write':
                assert result['final']['cache']['ssd']['writes'] == 2
                return result
            assert len(result['samples']) == 20 and len(result['cohorts']) == 2
            refs = {x['case']: x for x in reference['samples']}
            def arm(): (gate/'hold').write_text('hold owned fixture reads\n')
            try:
                overlap = checks.run_overlap(client, CASES[0], CASES[1], refs, 4, read_gate=arm)
                assert (gate/'entered').exists()
                assert overlap['peer_progress_while_ssd_pending'] and overlap['cancelled_while_io_pending']
            finally:
                (gate/'hold').unlink(missing_ok=True)
            idle = client.idle()
            assert idle['scheduler']['cancelled'] == 1 and not idle['cache']['ssd']['staging_bytes']
            recovered = client.send(CASES[0], label='recovery'); checks.same_output(recovered, refs['disk']); checks.require_hit(recovered, 4)
            client.idle()
            slow = checks.run_slow_client(client, CASES[1], CASES[0], refs, 4)
            assert slow['state'] == 'PASS' and slow['final']['scheduler']['cancelled'] == 2
            print(json.dumps(dict(synthetic=True, samples=len(result['samples']), cohorts=len(result['cohorts']),
                                  overlap_pending=True, peer_output_tokens=overlap['peer']['output_tokens'],
                                  cancelled_while_io_pending=True, slow_client_peer_complete=True,
                                  final=slow['final']['scheduler'], ssd=slow['final']['cache']['ssd'])))
            stats = checks.summarize(result)
            assert len(stats) == 10 and all(x['samples'] == 2 for x in stats)
            checks.export(result, root/'graphs')
            assert (root/'graphs/benchmark.svg').stat().st_size > 1000
            # Corrupt metadata must not turn a reference mismatch into a cache pass.
            bad = copy.deepcopy(reference); bad['cases_sha256'] = '0'*64
            reject(lambda: checks.run_phase(client, CASES, phase, 4, bad, 1))
            row = result['samples'][0]; usage = {'prompt_tokens': 4, 'completion_tokens': row['output_tokens'], 'total_tokens': 4+row['output_tokens'],
                                             'prompt_tokens_details': {'cached_tokens': 4}}
            parser_failures(client,row)
            for key, value in [('prefill_tokens', 4), ('ssd_cached_tokens', 0), ('cached_tokens', 3), ('prefill_tokens_per_second', 1000), ('prefill_ms', float('nan'))]:
                broken = copy.deepcopy(row); broken['timings'][key] = value
                if key == 'ssd_cached_tokens': reject(lambda: checks.require_hit(broken, 4))
                else: reject(lambda: checks.validate_chat(usage, broken['timings'], CASES[0]['max_tokens']))
            quantiles = checks.distribution([1, 2, 3]); assert quantiles['p50'] == 2 and quantiles['p95'] == quantiles['p99'] == 3
            reject(lambda: checks.distribution([float('nan')]))
            return result
        except BaseException:
            print(json.dumps(events[-5:], indent=2)[:8000]); raise
        finally:
            (gate/'hold').unlink(missing_ok=True)
            if proc.poll() is None: proc.terminate()
            try: proc.wait(timeout=6)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait(); raise
            assert proc.returncode == 0, logpath.read_text()


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='lie-ssd-serving-NOT-INFERENCE-') as directory:
        root = Path(directory); reference = run(sys.argv[1], root, 'write')
        assert len(list((root/'store').glob('*.lie'))) == 2
        run(sys.argv[1], root, 'read', reference)
    print('SSD HTTP JSON/SSE restart, C2, pending-read peer progress and cancellation: PASS (NOT-INFERENCE)')
