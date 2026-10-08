#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Private HTTP session for the unmodified pinned Terminal-Bench harness.

Launched only by q2-runner while it holds the original four leases. No socket
proxy or replacement inference path: requests reach the frozen C17 LIE server.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT.parent / 'q2-terminal-bench/benchmark'
DEP_ROOT = BENCH.parent
ENDPOINT = 'http://127.0.0.1:8000/v1'
MODEL = 'qwen3.8-flash-next-q2'


def request(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(ENDPOINT + path, data=data,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=1800) as response:
        return json.load(response)


def main():
    binary, model, mode = sys.argv[1:]
    if mode not in ('probe', 'smoke', 'full'):
        raise ValueError('Unknown benchmark scope')
    plan = json.loads((ROOT / 'config/q2-terminal-bench-plan.json').read_text())
    manifest = BENCH / plan['manifest']
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != plan['manifest_sha256']:
        raise RuntimeError('Benchmark manifest changed')
    # Verify every benchmark source/task against its independently fetched pin.
    identity = json.loads((ROOT / 'config/q2-terminal-bench-source.json').read_text())
    for name, expected in identity['files'].items():
        if hashlib.sha256((BENCH / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError('Benchmark source changed: ' + name)
    results = ROOT / 'results'
    receipt = {'state': 'STARTING', 'scope': mode, 'model': MODEL,
               'endpoint': ENDPOINT, 'commands': [], 'started_at': now(),
               'serving_limits': plan['serving_limits'], 'benchmark_revision': plan['revision']}

    def save():
        (results / 'terminal-session.json').write_text(json.dumps(receipt, indent=2) + '\n')

    # Existing listeners are never stopped. The management port is private.
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        management_port = sock.getsockname()[1]
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 8000))
    server_args = [binary, '--host', '0.0.0.0', '--port', '8000',
                   '--management-host', '127.0.0.1', '--management-port', str(management_port),
                   '--model', model, '--model-id', MODEL, '--context', '262144',
                   '--prefill-chunk', '2048', '--max-active', '1',
                   '--kv-cache-ram-mb', '0', '--request-timeout-ms', '1800000']
    env = dict(os.environ, UV_CACHE_DIR=str(DEP_ROOT / 'uv-cache'),
               UV_PYTHON_INSTALL_DIR=str(DEP_ROOT / 'python'), UV_PYTHON='3.12',
               LC_ALL='C', PYTHONUNBUFFERED='1')
    before = set((BENCH / 'jobs').glob('*'))
    receipt['server_argv'] = server_args
    save()
    with (results / 'terminal-server.log').open('xb') as log:
        server = subprocess.Popen(server_args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        receipt['server_pid'] = server.pid
        save()
        try:
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    raise RuntimeError('Server exited before readiness')
                try:
                    models = request('/models')
                    if models.get('data'):
                        break
                except (OSError, urllib.error.URLError):
                    pass
                time.sleep(1)
            else:
                raise RuntimeError('Model readiness timeout')
            if (len(models['data']) != 1 or models['data'][0]['id'] != MODEL or
                    models['data'][0]['context_length'] != 262144 or
                    models['data'][0]['max_output_tokens'] != 4096):
                raise RuntimeError('Unexpected endpoint metadata')
            receipt['models'] = models
            receipt['ready_at'] = now()
            receipt['state'] = 'READY'
            save()
            common = ['--endpoint', ENDPOINT, '--tier', 'full' if mode == 'full' else 'smoke']
            commands = [[sys.executable, str(BENCH / 'terminal_bench.py'), 'doctor', *common]]
            if mode == 'probe':
                # Endpoint admission only, not a Terminal-Bench score.
                answer = request('/chat/completions', {
                    'model': MODEL, 'messages': [{'role': 'user',
                    'content': 'What is 17 plus 28? Reply with only the integer.'}],
                    'temperature': 0, 'max_tokens': 32})
                receipt['admission_response'] = answer
                choice = answer['choices'][0]
                if choice['message']['content'].strip() != '45' or choice['finish_reason'] != 'stop':
                    raise RuntimeError('Real inference admission answer failed')
            else:
                commands.append([sys.executable, str(BENCH / 'terminal_bench.py'), 'run', *common,
                    '--platform', 'strix-halo', '--model-name', 'Qwen3.8-Flash-Next',
                    '--engine', 'synapse-lie-q2-experiment', '--backend', 'rocm',
                    '--engine-version', 'ae9c34ef-gufo-f783fedb', '--quant', 'Q2',
                    '--inference-profile', 'ar-thinking-off-prefix-off-output4096',
                    '--tag', ROOT.name, '--job-name', ROOT.name])
            for i, argv in enumerate(commands):
                row = {'argv': argv, 'started_at': now()}
                receipt['commands'].append(row)
                save()
                with (results / f'terminal-command-{i}.log').open('xb') as output:
                    process = subprocess.Popen(argv, cwd=BENCH, env=env,
                                               stdout=output, stderr=subprocess.STDOUT)
                    row['pid'] = process.pid
                    save()
                    while process.poll() is None:
                        if server.poll() is not None:
                            process.send_signal(signal.SIGINT)
                            process.wait(timeout=20)
                            raise RuntimeError('Server exited while benchmark was running')
                        time.sleep(1)
                    row.update(exit_code=process.returncode, finished_at=now())
                    save()
                if process.returncode:
                    raise RuntimeError('Benchmark command failed; preserve the actual exit')
            receipt['state'] = ('HTTP_ORIGINAL_MODEL_ADMISSION_PASS_NOT_TASK_SCORE'
                                if mode == 'probe' else 'BENCHMARK_COMMAND_COMPLETE_INSPECT_REWARDS')
        except BaseException as error:
            receipt.update(state='FAILED', error=repr(error))
            raise
        finally:
            receipt['jobs'] = [str(p) for p in sorted(set((BENCH / 'jobs').glob('*')) - before)]
            if server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)
            receipt['server_exit_code'] = server.returncode
            receipt['finished_at'] = now()
            save()
    print(json.dumps(receipt), flush=True)


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def cleanup():
    """Only this capsule's exact job and conditional-attempt Compose projects."""
    sys.path.insert(0, str(BENCH))
    import terminal_bench
    configs = []
    for job in (ROOT.name, ROOT.name + '-attempt2'):
        path = BENCH / '.runner/configs' / (job + '.json')
        if path.is_file():
            value = json.loads(path.read_text())
            if value['job_name'] != job:
                raise RuntimeError('Cleanup identity mismatch')
            configs.append(value)
    terminal_bench.cleanup_interrupted_containers(configs, runtime='docker')


if __name__ == '__main__':
    if sys.argv[1:] == ['--cleanup']:
        cleanup()
    else:
        main()
