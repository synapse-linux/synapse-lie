#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run the native prepared HTTP client inside one admitted Point GPU window."""

import argparse
import datetime
import hashlib
import http.client
import json
from pathlib import Path
import signal
import socket
import subprocess
import time

ROOT = Path('/work')
MODEL_ID = 'qwen3.8-flash-next'
API_PORT = 8000


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def listed_model():
    connection = http.client.HTTPConnection('127.0.0.1', API_PORT, timeout=3)
    try:
        connection.request('GET', '/v1/models')
        response = connection.getresponse()
        body = response.read(1024 * 1024 + 1)
        if response.status != 200 or len(body) > 1024 * 1024:
            return False
        return MODEL_ID in {row['id'] for row in json.loads(body)['data']}
    finally:
        connection.close()


def management_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def server_command(args, management):
    if args.impl == 'lie':
        command = [args.server, '--model', args.model, '--model-id', MODEL_ID,
                   '--host', '127.0.0.1', '--port', str(API_PORT),
                   '--management-host', '127.0.0.1', '--management-port', str(management),
                   '--context', '4096', '--prefill-chunk', '2048',
                   '--max-active', '8', '--kv-cache-ram-mb', '8192',
                   '--request-timeout-ms', '630000']
        if args.mode == 'mtp':
            command += ['--model-mtp', args.predictor, '--mtp-draft-tokens', '7']
        return command
    command = [args.server, 'serve', '--host', '127.0.0.1', '--port',
               str(API_PORT), '--sessions', '8', 'llm', '--model', args.model,
               '--served-model-name', MODEL_ID, '--context', '4096',
               '--prefill-chunk', '2048', '--max-pending', '16',
               '--max-pending-per-client', '16', '--request-timeout-ms',
               '630000', '--think', 'off', '--speculative',
               'mtp' if args.mode == 'mtp' else 'off']
    if args.mode == 'mtp':
        command += ['--mtp-model', args.predictor, '--draft-tokens', '7']
    return command


def client_command(args):
    return [args.client, '--suite', 'http-multi', '--url',
            f'http://127.0.0.1:{API_PORT}/v1', '--model', MODEL_ID,
            '--requests', '/work/corpus.jsonl', '--users', args.users,
            '--tg', '128', '--context-capacity', '4096', '--warmups',
            str(args.warmups), '--repetitions', str(args.repetitions),
            '--timeout', '630', '--server-label', args.impl.upper(),
            '--output', '/work/measurements.jsonl']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--impl', choices=('lie', 'gufo'), required=True)
    parser.add_argument('--mode', choices=('ar', 'mtp'), required=True)
    parser.add_argument('--users', choices=('1', '1,2,4,6,8'), required=True)
    parser.add_argument('--warmups', type=int, choices=(1,), required=True)
    parser.add_argument('--repetitions', type=int, choices=(3,), required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--predictor')
    parser.add_argument('--server', required=True)
    parser.add_argument('--client', required=True)
    args = parser.parse_args()
    if (args.mode == 'mtp') != bool(args.predictor):
        parser.error('MTP requires exactly one predictor')
    result = {'schema': 'synapse-lie.point-http-multi-original.v1',
              'state': 'RUNNING', 'started_at': now(), 'implementation': args.impl,
              'mode': args.mode, 'users': args.users, 'warmups': args.warmups,
              'repetitions': args.repetitions,
              'server_argv': server_command(args, management_port()),
              'client_argv': client_command(args), 'corpus_sha256': sha(ROOT/'corpus.jsonl')}
    server = None

    def interrupted(number, _frame):
        raise RuntimeError(f'Interrupted by signal {number}')

    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, interrupted)
    try:
        with (ROOT/'server.log').open('xb') as log:
            server = subprocess.Popen(result['server_argv'], stdout=log,
                                      stderr=subprocess.STDOUT)
            (ROOT/'http-started.marker').write_text(str(server.pid) + '\n')
            deadline = time.monotonic() + 900
            while True:
                if server.poll() is not None:
                    raise RuntimeError(f'Server exited during model load: {server.returncode}')
                try:
                    if listed_model():
                        break
                except (OSError, ValueError, KeyError, http.client.HTTPException):
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError('Original-weight model readiness deadline')
                time.sleep(.25)
            result['ready_at'] = now()
            with (ROOT/'client.stdout.log').open('xb') as stdout, \
                 (ROOT/'client.stderr.log').open('xb') as stderr:
                client = subprocess.run(result['client_argv'], stdout=stdout,
                                        stderr=stderr, timeout=5400)
            result['client_exit_code'] = client.returncode
            if (ROOT/'measurements.jsonl').exists():
                result['measurements_sha256'] = sha(ROOT/'measurements.jsonl')
                result['measurement_bytes'] = (ROOT/'measurements.jsonl').stat().st_size
            if client.returncode:
                raise RuntimeError(f'Native HTTP client exited {client.returncode}')
            rows = [json.loads(line) for line in (ROOT/'measurements.jsonl').read_text().splitlines()]
            if (not rows or rows[-1] != {'event': 'complete', 'exit_code': 0} or
                    len([row for row in rows if row.get('event') == 'cohort']) !=
                    (1 if args.users == '1' else 5) * (args.warmups + args.repetitions)):
                raise RuntimeError('Incomplete native HTTP cohorts')
            result['cohorts'] = len(rows) - 2
            result['state'] = 'PASSED'
    except BaseException as error:
        result['state'] = 'FAILED'
        result['error'] = repr(error)
    finally:
        if server is not None:
            if server.poll() is None:
                server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
            result['server_exit_code'] = server.returncode
        result['ended_at'] = now()
        (ROOT/'http-multi-result.json').write_text(json.dumps(result, indent=2) + '\n')
    return 0 if result['state'] == 'PASSED' and result.get('server_exit_code') in (0, -15) else 1


if __name__ == '__main__':
    raise SystemExit(main())
