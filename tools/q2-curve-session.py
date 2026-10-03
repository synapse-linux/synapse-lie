#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Own one transient C17 server and canonical curve client under q2-runner."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def identity(process):
    stat = Path('/proc', str(process.pid), 'stat').read_text().rsplit(') ', 1)[1].split()
    return dict(pid=process.pid, start_ticks=int(stat[19]), process_group=os.getpgid(process.pid))


def main():
    binary, model, variant = sys.argv[1:]
    if variant not in ('q2', 'ud'):
        raise ValueError('Unknown curve variant')
    result = ROOT/'results'
    receipt = dict(state='STARTING', variant=variant, commands=[], started_ns=time.monotonic_ns())
    def save():
        (result/'curve-session.json').write_text(json.dumps(receipt, indent=2)+'\n')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        management = sock.getsockname()[1]
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 8000))
    server_argv = [binary, '--host', '127.0.0.1', '--port', '8000',
        '--management-host', '127.0.0.1', '--management-port', str(management),
        '--model', model, '--model-id', 'bench', '--context', '133760',
        '--prefill-chunk', '2048', '--max-active', '1', '--request-timeout-ms', '1800000',
        '--kv-cache-ram-mb', '16384', '--kv-cache-policy', 'ds4',
        '--kv-cache-min-tokens', '32', '--kv-cache-cold-max-tokens', '0',
        '--kv-cache-continued-interval-tokens', '0', '--kv-cache-boundary-trim-tokens', '0',
        '--kv-cache-boundary-align-tokens', '0', '--kv-cache-text-prefix', 'off',
        '--kv-cache-capture-finish', 'on']
    receipt['server_argv'] = server_argv
    receipt['server_binary_sha256'] = hashlib.sha256(Path(binary).read_bytes()).hexdigest()
    save()
    server = client = None
    try:
        with (result/'curve-server.log').open('xb') as log:
            # Inherit q2-runner's owned group: thermal/timeout cleanup reaches
            # this server as well as its client. Never detach a GPU child.
            server = subprocess.Popen(server_argv, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            receipt['server_identity'] = identity(server)
            save()
            deadline = time.monotonic()+600
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    raise RuntimeError('Server exited before model readiness')
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{management}/actuator/llm', timeout=5) as response:
                        info = json.load(response)
                    if info.get('ready') is True:
                        receipt['backend_ready'] = info
                        break
                except (OSError, urllib.error.URLError):
                    pass
                time.sleep(.2)
            else:
                raise RuntimeError('Model readiness timeout')
            argv = [sys.executable, '-B', str(ROOT/'tools/q2-canonical-http.py'),
                '--base-url', 'http://127.0.0.1:8000', '--management-url', f'http://127.0.0.1:{management}',
                '--gufo-source', str(ROOT/'source'), '--output', str(result/'canonical-curve'),
                '--variant', variant]
            command = dict(argv=argv, started_ns=time.monotonic_ns())
            receipt['commands'].append(command)
            with (result/'curve-client.log').open('xb') as client_log:
                client = subprocess.Popen(argv, cwd=ROOT, stdout=client_log, stderr=subprocess.STDOUT)
                command.update(identity(client))
                save()
                command['exit_code'] = client.wait(timeout=2400)
                command['ended_ns'] = time.monotonic_ns()
                save()
                if command['exit_code']:
                    raise RuntimeError('Canonical curve client failed; raw evidence retained')
            receipt['state'] = 'CANONICAL_WORKLOAD_MEASURED_NOT_PARITY_VERDICT'
    except Exception as error:
        receipt.update(state='FAILED', error=str(error))
        raise
    finally:
        for process, name in ((client, 'client'), (server, 'server')):
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
                receipt[name+'_exit_code'] = process.returncode
        receipt['ended_ns'] = time.monotonic_ns()
        save()


if __name__ == '__main__':
    main()
