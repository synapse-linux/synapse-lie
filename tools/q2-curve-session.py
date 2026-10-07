#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Own one transient C17 server and canonical curve client under q2-runner."""
import hashlib
import json
import os
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from q2_native_curve import client_argv, check_backend

ROOT = Path(__file__).resolve().parents[1]


def identity(process):
    stat = Path('/proc', str(process.pid), 'stat').read_text().rsplit(') ', 1)[1].split()
    return dict(pid=process.pid, start_ticks=int(stat[19]), process_group=os.getpgid(process.pid))


def main():
    binary, model, variant, *flags = sys.argv[1:]
    native_bench = None
    if flags[:1] == ['--native-bench']:
        if len(flags) < 2:
            raise ValueError('Missing native benchmark binary')
        native_bench, flags = Path(flags[1]), flags[2:]
        if not native_bench.is_absolute() or not native_bench.is_file():
            raise ValueError('Native benchmark must be an existing absolute binary')
    point_only = flags[:1] == ['--point-only']
    if point_only:
        flags = flags[1:]
        if native_bench is None:
            raise ValueError('Focused point requires the native benchmark')
    prefill_depth = None
    if flags[:1] == ['--prefill-only-depth']:
        prefill_depth, flags = int(flags[1]), flags[2:]
    if flags not in ([], ['--profile-ple'], ['--iq2-signs'], ['--ple-cache-first'], ['--profile-routes'], ['--iq2-mixed'], ['--iq2-scale'], ['--scaled-row'], ['--norm-ragged'], ['--retained-128'], ['--retained-prefill'], ['--live-grid-prefill'], ['--profile-prefix32k']):
        raise ValueError('Unknown diagnostic flags')
    live_grid = flags == ['--live-grid-prefill']
    profile_prefix32k = flags == ['--profile-prefix32k']
    full_prefill = profile_prefix32k or live_grid or flags == ['--retained-prefill']
    if prefill_depth is not None and (not full_prefill or prefill_depth not in (65536,131072)):
        raise ValueError('Only saved unfinished full-prefill depths may be selected')
    retained128 = full_prefill or flags == ['--retained-128']
    if retained128 and (variant != 'q2' or native_bench is None or point_only):
        raise ValueError('Retained128 requires the complete native Q2 curve')
    profile = flags == ['--profile-ple']
    iq2_signs = flags == ['--iq2-signs']
    cache_first = flags == ['--ple-cache-first']
    routes = flags == ['--profile-routes']
    mixed = flags == ['--iq2-mixed']
    norm_ragged = flags == ['--norm-ragged']
    if norm_ragged and not point_only:
        raise ValueError('Paired norm requires focused point')
    row_reuse = flags == ['--scaled-row']
    scale = flags == ['--iq2-scale']
    if variant not in ('q2', 'ud'):
        raise ValueError('Unknown curve variant')
    if (iq2_signs or cache_first or routes or mixed or scale or row_reuse or norm_ragged) and variant != 'q2':
        raise ValueError('IQ2 signs requires the Q2 model')
    if (scale or row_reuse) and native_bench is None:
        raise ValueError('Scale model comparison requires the native C canonical benchmark')
    if native_bench is not None and not ((variant == 'ud' and not flags) or iq2_signs or scale or row_reuse or norm_ragged or retained128):
        raise ValueError('Native curve requires an uninstrumented ordered Q2, scale Q2 or UD provider')
    result = ROOT/'results'
    receipt = dict(state='STARTING', variant=variant, commands=[], started_ns=time.monotonic_ns(),
                   instrumentation='routing-counts' if routes else 'ple-forward' if profile else None,
                   point_only=point_only,
                   provider_experiment='select-live-grid-prefill-through32K' if live_grid else 'iq2-fixed-bounds-full-prefill128' if full_prefill else 'iq2-fixed-bounds-retained128' if retained128 else 'norm-ragged' if norm_ragged else 'scaled-row-reuse' if row_reuse else 'iq2-scale-reuse' if scale else 'iq2-mixed-ordered' if mixed else
                                       'ple-cache-first-ordered' if cache_first else
                                       'iq2-signs-ordered' if iq2_signs else None)
    if native_bench is not None:
        receipt['client_driver'] = 'synapse-lie-bench-native-C'
        receipt['client_binary_sha256'] = hashlib.sha256(native_bench.read_bytes()).hexdigest()
        native_variant = 'live-grid' if live_grid else 'retained128' if retained128 else 'norm' if norm_ragged else 'row' if row_reuse else 'scale' if scale else 'ordered' if iq2_signs else 'ud'
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
    if profile_prefix32k:
        from q2_long_profile import profiler_argv
        profiler = shutil.which('rocprofv3') or '/opt/rocm/bin/rocprofv3'
        if not Path(profiler).is_file():
            raise RuntimeError('Installed rocprofv3 unavailable')
        server_argv = profiler_argv(profiler, result/'profile', server_argv)
        receipt.update(profiler_argv=server_argv, profiler_sha256=hashlib.sha256(Path(profiler).read_bytes()).hexdigest(),
                       instrumentation='rocprofv3-kernel-hip-memory-copy', headline_eligible=False,
                       provider_experiment='retained-prefix32k-diagnostic')
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
                    if retained128 and info.get('backend', {}).get('state') == 'FAILED':
                        raise RuntimeError('Model initialization failed')
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
                '--variant', variant, *flags]
            if native_bench is not None:
                check_backend(receipt['backend_ready'], native_variant)
                argv = client_argv(native_bench, result/'native-curve.jsonl',
                                   result/'native-curve-graphs', native_variant, point_only=point_only)
            if full_prefill:
                from q2_full_prefill128 import client_argv as full_argv
                if live_grid:
                    from q2_select_live_grid_model import client_argv as full_argv
                if profile_prefix32k:
                    from q2_long_profile import client_argv as full_argv
                argv = full_argv(ROOT, native_bench, result/'full-prefill.jsonl', depth=prefill_depth)
                receipt['workload'] = 'Exact saved full-prefix requests; no continuation measurements'
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
            if full_prefill:
                from q2_full_prefill128 import validate_result
                if live_grid:
                    from q2_select_live_grid_model import validate_result
                if profile_prefix32k:
                    from q2_long_profile import validate_result
                receipt['full_prefill_validation'] = validate_result(ROOT, result/'full-prefill.jsonl', depth=prefill_depth)
            if native_bench is not None:
                with urllib.request.urlopen(f'http://127.0.0.1:{management}/actuator/llm', timeout=5) as response:
                    payload = response.read(1048577)
                if len(payload) > 1048576:
                    raise RuntimeError('Oversized backend metadata')
                receipt['backend_after'] = json.loads(payload)
                check_backend(receipt['backend_after'], native_variant)
                receipt['client_binary_sha256_after'] = hashlib.sha256(native_bench.read_bytes()).hexdigest()
                if receipt['client_binary_sha256_after'] != receipt['client_binary_sha256']:
                    raise RuntimeError('Native benchmark binary changed')
            receipt['state'] = ('PREFIX32K_PROFILE_COMPLETE_NOT_BENCHMARK' if profile_prefix32k else
                                'CANONICAL_ROUTE_PROFILE_COMPLETE_NOT_BENCHMARK' if routes else
                                'CANONICAL_PLE_PROFILE_COMPLETE_NOT_BENCHMARK' if profile else
                                'CANONICAL_WORKLOAD_MEASURED_NOT_PARITY_VERDICT')
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
