#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Optional own-child steering qualification; invoke only in an admitted window.

The outer campaign owns the GPU lease, resources, container and router. This
helper owns two serial model servers and their native C HTTP clients, preserves
partial evidence and never retries, installs dependencies or acquires a lease.
"""
import argparse
import datetime
import http.client
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import time

HERE = Path(__file__).resolve().parent
SNAPSHOT_TIMEOUT_SECONDS = 3
# 70 bounded snapshot reads (210 s), two client deadline margins (60 s),
# four owned retirements (120 s), plus container setup and bounded I/O slack.
SUPERVISION_OVERHEAD_SECONDS = 600
# Keep all sixty bank-phase records until their applied-policy snapshots are
# collected. The native store reserves the output budget, semantic journal and
# retained job, even for short answers. 64 MiB refused the 59th original request;
# 256 MiB covers this protocol's maximum 512-token budget without eviction.
RESPONSE_STORE_MIB = 256


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


quality = module('steering_response_review', HERE/'strix-point-steering-quality-gate.py')
owned = module('steering_owned_children', HERE/'strix-point-http-recall-gate.py')


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def container_timeout(config, load_seconds):
    quality.settings(config)
    if not quality.integer(load_seconds, 30, 1800):
        raise ValueError('Model readiness timeout must be 30..1800 seconds')
    deadline = 2*load_seconds + 70*config['request_timeout_seconds'] + SUPERVISION_OVERHEAD_SECONDS
    if deadline > 86400:
        raise ValueError('Steering campaign exceeds the one-day container bound')
    return deadline


def server_command(args, config, phase, api, management):
    command = [args.server, '--model', args.model, '--model-id', config['model_id'],
               '--host', '127.0.0.1', '--port', str(api), '--management-host', '127.0.0.1',
               '--management-port', str(management), '--context', str(config['context']),
               '--rope-scaling', 'native', '--prefill-chunk', str(config['chunk']),
               '--prefill-capacity', str(config['chunk']), '--max-active', '1',
               '--kv-cache-ram-mb', '0', '--request-timeout-ms', str(1000*config['request_timeout_seconds']),
               '--response-store-records', '128', '--response-store-ram-mb', str(RESPONSE_STORE_MIB),
               '--response-store-ttl-seconds', str(container_timeout(config, args.load_timeout))]
    if phase == 'bank':
        command += ['--dir-steering-file', str(args.bank), '--dir-steering-ffn', '0', '--dir-steering-attn', '0']
    elif phase != 'absent':
        raise ValueError('Unknown steering server phase')
    return command


def get(api, path):
    connection = http.client.HTTPConnection('127.0.0.1', api, timeout=SNAPSHOT_TIMEOUT_SECONDS)
    try:
        connection.request('GET', path)
        response = connection.getresponse()
        data = response.read(1024*1024+1)
        if len(data) > 1024*1024:
            raise RuntimeError('Stored HTTP observation exceeds its bound')
        # Preserve status/text before interpreting an error or malformed JSON.
        return {'status': response.status, 'body': data.decode('utf-8')}
    finally:
        connection.close()


def ready(server, api, model_id, load_seconds):
    deadline = time.monotonic()+load_seconds
    while True:
        if server.poll() is not None:
            raise RuntimeError('Owned server exited during model loading')
        try:
            response = get(api, '/v1/models')
            if response['status'] == 200:
                data = quality.strict(response['body'])
                if model_id in {row['id'] for row in data['data']}:
                    return
        except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException):
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError('Original model readiness deadline')
        time.sleep(.25)


def bank_identity(path):
    before = path.stat(follow_symlinks=False)
    _data, content = quality.read(path, 16*2**20)
    after = path.stat(follow_symlinks=False)
    keys = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
    if any(getattr(before, k) != getattr(after, k) for k in keys):
        raise RuntimeError('Bank changed during identity review')
    return {**content, 'device': after.st_dev, 'inode': after.st_ino,
            'mtime_ns': after.st_mtime_ns, 'ctime_ns': after.st_ctime_ns}


def lines(path, maximum):
    data, identity = quality.read(path, maximum)
    if not data.endswith(b'\n'):
        raise RuntimeError('Incomplete native JSONL evidence')
    return [quality.strict(line) for line in data.splitlines()], identity


def run(args, config, data):
    config, data = quality.settings(config), quality.corpus(data)
    deadline = container_timeout(config, args.load_timeout)
    root = args.directory
    if not root.is_absolute() or root.resolve() != root or root.stat().st_uid != os.getuid():
        raise RuntimeError('Campaign directory must be canonical and owned')
    result_path = root/'steering-quality-result.json'
    if result_path.exists() or result_path.is_symlink():
        raise RuntimeError('Refusing steering qualification replay')
    bank_before = bank_identity(args.bank)
    if bank_before['sha256'] != config['bank_sha256']:
        raise RuntimeError('Admitted learned bank SHA256 differs')
    directory = root/'steering-quality'
    quality.prepare(directory, data, config)
    result = {'schema': 'synapse-lie.point-steering-quality-run.v1', 'state': 'RUNNING',
              'started_at': now(), 'settings': config, 'load_timeout_seconds': args.load_timeout,
              'container_timeout_seconds': deadline, 'bank_before': bank_before,
              'phases': {}, 'native_exit_codes': {}, 'cleanup_errors': [],
              'outer_lease_container_resource_and_model_provenance_checks_required': True}
    children, rows, cases, snapshots = {}, {}, {}, {}

    def interrupted(number, _frame):
        raise RuntimeError('Interrupted by signal '+str(number))

    signals = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)
    handlers = {number: signal.signal(number, interrupted) for number in signals}
    try:
        with (directory/'snapshots-raw.jsonl').open('x', encoding='utf-8') as raw:
            for phase in ('absent', 'bank'):
                target = directory/phase
                api, management = owned.private_ports()
                observed = result['phases'][phase] = {'api_port': api, 'management_port': management,
                    'server_argv': server_command(args, config, phase, api, management),
                    'client_argv': quality.client_command(args.client, config, api, target),
                    'client_timeout_seconds': len(quality.requests(data, config, phase))*config['request_timeout_seconds']+30}
                with (target/'server.log').open('xb') as log:
                    key = phase+'.server'
                    server = children[key] = subprocess.Popen(observed['server_argv'], stdout=log, stderr=subprocess.STDOUT)
                    observed['server_identity'] = owned.process_identity(server)
                    if phase == 'absent':
                        with (root/'http-started.marker').open('x') as marker:
                            marker.write(str(server.pid)+'\n')
                    ready(server, api, config['model_id'], args.load_timeout)
                    observed['ready_at'] = now()
                    with (target/'client.stdout.log').open('xb') as stdout, (target/'client.stderr.log').open('xb') as stderr:
                        client_key = phase+'.client'
                        client = children[client_key] = subprocess.Popen(observed['client_argv'], stdout=stdout, stderr=stderr)
                        observed['client_identity'] = owned.process_identity(client)
                        code = client.wait(timeout=observed['client_timeout_seconds'])
                        result['native_exit_codes'][phase] = observed['client_exit_code'] = code
                        if code != 0:
                            raise RuntimeError('Native HTTP client failed; complete or partial observations retained')
                    rows[phase], observed['measurements_identity'] = lines(target/'measurements.jsonl', 64*2**20)
                    cases[phase], observed['requests_identity'] = lines(target/'requests.jsonl', 2**20)
                    wanted = quality.requests(data, config, phase)
                    if cases[phase] != wanted or len(rows[phase]) != len(wanted)+2:
                        raise RuntimeError('Incomplete or changed native request cohort')
                    for case, row in zip(wanted, rows[phase][1:-1]):
                        identifier, _text = quality.wire(row, config)
                        response = get(api, '/v1/chat/completions/'+identifier+'/steering')
                        raw.write(json.dumps({'case': case['id'], 'id': identifier, 'response': response})+'\n')
                        raw.flush()
                        if response['status'] != 200:
                            raise RuntimeError('Actual stored steering observation unavailable')
                        snapshots[case['id']] = quality.strict(response['body'])
                    observed['client_exit_code'] = owned.retire(client)
                    observed['server_exit_code'] = owned.retire(server)
                    if observed['server_exit_code'] not in (0, -signal.SIGTERM):
                        raise RuntimeError('Owned server failed during retirement')
                    observed['retired_at'] = now()
                # Both own children retire before the next model is opened.
        proof = quality.validate(rows, cases, snapshots, config, data, result['native_exit_codes'])
        result['quality_review'] = proof
        result['state'] = proof['state']
    except BaseException as error:
        result['state'] = 'FAILED'
        result['error'] = repr(error)
    finally:
        for number in signals:
            signal.signal(number, signal.SIG_IGN)
        try:
            for key, child in reversed(list(children.items())):
                phase, role = key.split('.')
                try:
                    code = owned.retire(child)
                    result['phases'][phase][role+'_exit_code'] = code
                    if role == 'client':
                        result['native_exit_codes'][phase] = code
                    if role == 'server' and code not in (0, -signal.SIGTERM):
                        raise RuntimeError('Unexpected actual owned server exit '+str(code))
                except BaseException as error:
                    result['cleanup_errors'].append(key+': '+repr(error))
                    result['state'] = 'FAILED'
            try:
                result['bank_after'] = bank_identity(args.bank)
                result['bank_identity_unchanged'] = result['bank_after'] == bank_before
                if not result['bank_identity_unchanged']:
                    raise RuntimeError('Learned bank identity changed')
            except BaseException as error:
                result['cleanup_errors'].append('bank identity: '+repr(error))
                result['state'] = 'FAILED'
            write(directory/'snapshots.json', snapshots)
            write(directory/'execution.json', {'native_exit_codes': result['native_exit_codes'], 'phases': result['phases']})
            result['ended_at'] = now()
            write(result_path, result)
        finally:
            for number, handler in handlers.items():
                signal.signal(number, handler)
    return 0 if result['state'] == 'PASSED' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path('/work'))
    parser.add_argument('--settings', required=True, type=Path)
    parser.add_argument('--corpus', required=True, type=Path)
    parser.add_argument('--bank', required=True, type=Path)
    parser.add_argument('--model', required=True)
    parser.add_argument('--server', required=True)
    parser.add_argument('--client', required=True)
    parser.add_argument('--load-timeout', type=int, default=900)
    args = parser.parse_args()
    config = quality.settings(quality.strict(quality.read(args.settings, 65536)[0]))
    data = quality.corpus(quality.strict(quality.read(args.corpus, 2**20)[0]))
    return run(args, config, data)


if __name__ == '__main__':
    raise SystemExit(main())
