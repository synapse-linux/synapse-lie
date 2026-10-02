#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""SSD restart through both HTTP APIs; CPU synthetic state, NOT-INFERENCE."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from test_tools_http import exchange, port


def run(binary, root, index, ram):
    api, management = port(), port()
    while api == management:
        management = port()
    log_path = root / f'{index}.log'
    with log_path.open('wb') as log:
        proc = subprocess.Popen([binary, '--model', ':fixture:', '--port', str(api),
                                 '--management-port', str(management), '--context', '128',
                                 '--prefill-chunk', '4', '--prefix-cache-mib', str(ram),
                                 '--prefix-ssd-dir', str(root/'store'), '--prefix-ssd-quota-mib', '1',
                                 '--prefix-ssd-staging-mib', '1'], stdout=log, stderr=log)
        try:
            deadline = time.monotonic()+5
            while True:
                assert proc.poll() is None, log_path.read_text()
                try:
                    if exchange(management, '/actuator/health/readiness')[0] == 200:
                        break
                except OSError:
                    pass
                assert time.monotonic() < deadline, log_path.read_text()
                time.sleep(.01)
            request = {'model': 'cpu-test-fixture', 'messages': [{'role': 'user', 'content': 'hello'}], 'max_tokens': 8}
            status, text = exchange(api, '/v1/chat/completions', request)
            assert status == 200, text
            chat = json.loads(text)
            timings = chat['lie_timings']
            assert timings['ssd_cached_tokens'] == (0 if index == 0 else 4), chat
            assert timings['prefill_tokens'] == (4 if index == 0 else 0)
            if index:
                assert chat['usage']['prompt_tokens_details']['cached_tokens'] == 4
                status, text = exchange(api, '/v1/responses', {'model': 'cpu-test-fixture', 'input': 'hello', 'max_output_tokens': 8})
                assert status == 200, text
                response = json.loads(text)
                assert response['usage']['input_tokens_details']['cached_tokens'] == 4
                assert response['output'][0]['content'][0]['text'] == chat['choices'][0]['message']['content']
            status, text = exchange(management, '/actuator/llm')
            cache = json.loads(text)['cache']
            assert status == 200 and cache['ssd_enabled'] and cache['enabled'] == bool(ram)
            assert cache['ssd']['staging_bytes'] <= cache['ssd']['staging_budget_bytes']
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        assert proc.returncode == 0, log_path.read_text()


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='lie-ssd-http-') as directory:
        root = Path(directory)
        run(sys.argv[1], root, 0, 0)
        assert len(list((root/'store').glob('*.lie'))) == 1
        run(sys.argv[1], root, 1, 0)
        run(sys.argv[1], root, 2, 1)
        for options in [['--prefix-ssd-quota-mib','1'], ['--prefix-ssd-dir',str(root/'never-created')]]:
            p = subprocess.run([sys.argv[1],*options], capture_output=True, timeout=5)
            assert p.returncode == 2
        assert not (root/'never-created').exists()
