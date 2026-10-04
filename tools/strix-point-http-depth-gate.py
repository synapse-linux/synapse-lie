#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Measure one cold-prefill HTTP context in an admitted Point GPU window."""

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
CONTEXT = 262144


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
                   '--context', str(CONTEXT), '--prefill-chunk', '2048',
                   '--max-active', '1', '--kv-cache-ram-mb', '0',
                   '--request-timeout-ms', '1800000']
        if args.mode == 'mtp':
            command += ['--model-mtp', args.predictor, '--mtp-draft-tokens', '7']
        return command
    command = [args.server, 'serve', '--host', '127.0.0.1', '--port', str(API_PORT),
               '--sessions', '1', 'llm', '--model', args.model,
               '--served-model-name', MODEL_ID, '--context', str(CONTEXT),
               '--prefill-chunk', '2048', '--max-pending', '16',
               '--max-pending-per-client', '16', '--request-timeout-ms', '1800000',
               '--think', 'off', '--speculative', 'mtp' if args.mode == 'mtp' else 'off']
    if args.mode == 'mtp':
        command += ['--mtp-model', args.predictor, '--draft-tokens', '7']
    return command


def client_command(args):
    command = [args.client, '--suite', 'http', '--url',
               f'http://127.0.0.1:{API_PORT}/v1', '--model', MODEL_ID,
               '--preset', 'long-context', '--sizes', str(args.size), '--tg', '128',
               '--context-capacity', str(CONTEXT), '--rope-scaling', 'native',
               '--corpus-seed', '20261004', '--warmups', '0',
               '--repetitions', str(args.repetitions), '--server-kv-cache', 'off',
               '--timeout', '1800', '--server-label', args.impl.upper(),
               '--output', '/work/measurements.jsonl',
               '--export-requests', '/work/requests.jsonl']
    if args.impl == 'gufo':
        command += ['--request-options', '/work/gufo-options.json']
    return command


def validate(rows, args):
    identity = rows[0]
    if (identity.get('event') != 'identity' or
            identity.get('schema') != 'synapse-lie.http-bench.v1' or
            identity.get('cache_policy') != 'off' or
            identity.get('context_capacity_declared') != CONTEXT or
            identity.get('rope_scaling_declared') != 'native' or
            rows[-1] != {'event': 'complete', 'exit_code': 0}):
        raise RuntimeError('Unexpected native HTTP identity or completion')
    samples = [r for r in rows if r.get('event') == 'sample']
    if len(samples) != args.repetitions or any(r.get('warmup') for r in samples):
        raise RuntimeError('Missing measured cold-prefill repetitions')
    for row in samples:
        pp = row.get('prompt_tokens')
        phase = (row.get('server_timings') if args.impl == 'lie' else
                 row.get('usage', {}).get('gufo'))
        if (not isinstance(pp, int) or abs(pp - args.size) > 32 or
                row.get('cached_tokens') != 0 or
                row.get('output_tokens') != 128 or
                row.get('full_output_budget') is not True or
                row.get('stream_complete') is not True or
                not isinstance(phase, dict) or
                phase.get('prefill_tokens') != pp or
                not isinstance(phase.get('prefill_ms'), (float, int)) or
                phase['prefill_ms'] <= 0 or
                not isinstance(phase.get('decode_ms'), (float, int)) or
                phase['decode_ms'] <= 0):
            raise RuntimeError('Cold prefill, full output or server phase unverified')
    return len(samples)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--impl', choices=('lie', 'gufo'), required=True)
    parser.add_argument('--mode', choices=('ar', 'mtp'), required=True)
    parser.add_argument('--size', type=int, choices=(1500, 8192, 32768, 131072, 258794), required=True)
    parser.add_argument('--repetitions', type=int, choices=(2,), required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--predictor')
    parser.add_argument('--server', required=True)
    parser.add_argument('--client', required=True)
    args = parser.parse_args()
    if (args.mode == 'mtp') != bool(args.predictor):
        parser.error('MTP requires exactly one predictor')
    if args.impl == 'gufo':
        (ROOT/'gufo-options.json').write_text('{"cache_prompt":false}\n')
    result = {'schema': 'synapse-lie.point-http-depth-original.v1',
              'state': 'RUNNING', 'started_at': now(), 'implementation': args.impl,
              'mode': args.mode, 'size': args.size, 'repetitions': args.repetitions,
              'server_argv': server_command(args, management_port()),
              'client_argv': client_command(args)}
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
                                        stderr=stderr, timeout=7200)
            result['client_exit_code'] = client.returncode
            if (ROOT/'measurements.jsonl').exists():
                result['measurements_sha256'] = sha(ROOT/'measurements.jsonl')
                result['measurement_bytes'] = (ROOT/'measurements.jsonl').stat().st_size
            if client.returncode:
                raise RuntimeError(f'Native HTTP client exited {client.returncode}')
            rows = [json.loads(line) for line in (ROOT/'measurements.jsonl').read_text().splitlines()]
            result['samples'] = validate(rows, args)
            result['requests_sha256'] = sha(ROOT/'requests.jsonl')
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
        (ROOT/'http-depth-result.json').write_text(json.dumps(result, indent=2) + '\n')
    return 0 if result['state'] == 'PASSED' and result.get('server_exit_code') in (0, -15) else 1


if __name__ == '__main__':
    raise SystemExit(main())
