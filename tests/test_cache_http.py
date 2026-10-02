#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""HTTP projections of shared C RAM state; synthetic tokens, never inference."""
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from test_tools_http import exchange, port
from test_responses_http import events


def run(binary, enabled, policy='legacy'):
    api, management = port(), port()
    while management == api:
        management = port()
    with tempfile.TemporaryDirectory(prefix='lie-cache-http-') as tmp:
        logpath = Path(tmp)/'server.log'
        with logpath.open('wb') as log:
            proc = subprocess.Popen([binary, '--model', ':fixture:', '--cache-policy', policy,
                                     '--cache-min-tokens', '4', '--cache-cold-max-tokens', '4',
                                     '--cache-trim-tokens', '0', '--cache-align-tokens', '4',
                                     '--cache-capture-finish', 'off', '--port', str(api),
                                     '--management-port', str(management), '--context', '128',
                                     '--prefill-chunk', '4', *([] if enabled else ['--prefix-cache-mib', '0'])],
                                    stdout=log, stderr=log)
            try:
                deadline = time.monotonic()+5
                while True:
                    assert proc.poll() is None, logpath.read_text()
                    try:
                        if exchange(management, '/actuator/health/readiness')[0] == 200:
                            break
                    except OSError:
                        pass
                    assert time.monotonic() < deadline
                    time.sleep(.01)
                base = {'model': 'cpu-test-fixture', 'messages': [{'role': 'user', 'content': 'hello'}], 'max_tokens': 8}
                code, body = exchange(api, '/v1/chat/completions', base)
                assert code == 200, body
                cold = json.loads(body)
                assert cold['lie_timings']['cached_tokens'] == 0
                code, body = exchange(api, '/v1/chat/completions', dict(base, stream=True, stream_options={'include_usage': True}))
                assert code == 200, body
                frames = [json.loads(x[6:]) for x in body.split('\n\n') if x.startswith('data: {')]
                terminal = next(x for x in frames if 'lie_timings' in x)
                usage = next(x['usage'] for x in frames if x.get('usage'))
                cached = usage.get('prompt_tokens_details', {}).get('cached_tokens', 0)
                assert cached == (4 if enabled else 0), terminal
                assert terminal['lie_timings']['cached_tokens'] == cached
                assert terminal['lie_timings']['prefill_tokens'] == 4-cached
                text = ''.join(x['choices'][0]['delta'].get('content', '') for x in frames if x.get('choices'))
                assert text == cold['choices'][0]['message']['content']
                # Both wire APIs observe one cache in the same C core.
                code, body = exchange(api, '/v1/responses', {'model': 'cpu-test-fixture', 'input': 'hello', 'max_output_tokens': 8, 'stream': True})
                assert code == 200, body
                response = events(body)[-1]['response']
                assert response['usage']['input_tokens_details']['cached_tokens'] == cached
                assert response['output'][0]['content'][0]['text'] == text
                code, body = exchange(management, '/actuator/llm')
                assert code == 200
                cache = json.loads(body)['cache']
                assert cache['enabled'] is enabled and not cache['ssd_enabled'], cache
                assert cache['budget_bytes'] == (4*1024**3 if enabled else 0), cache
                assert cache['hits'] == (2 if enabled else 0), cache
                assert cache['captures'] == (1 if enabled else 0), cache
                assert cache['retained_bytes'] <= cache['budget_bytes']
                assert cache['index_bytes'] <= cache['index_budget_bytes']
                assert cache['checkpoint_policy']['kind'] == policy
                assert cache['checkpoint_policy']['capture_finish'] is False
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill(); proc.wait()
            assert proc.returncode == 0, logpath.read_text()


if __name__ == '__main__':
    run(sys.argv[1], True)
    run(sys.argv[1], False)
    info=json.loads(subprocess.check_output([sys.argv[1], '--build-info'],text=True,timeout=5))
    if info['ds4_cache_policy']:
        run(sys.argv[1], True, 'ds4')
