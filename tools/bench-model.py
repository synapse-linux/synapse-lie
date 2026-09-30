#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""One-shot leased C1 baseline supervisor. No builds, downloads, tuning or retries.
Requires a fresh operator-authorized manifest and private, unused run directory.
Shares only read-only utility functions with the retained original-model runner.
"""
import fcntl
import json
import math
import os
from pathlib import Path
import resource
import runpy
import signal
import statistics
import subprocess
import sys
import time

H = runpy.run_path(str(Path(__file__).with_name('smoke-model.py')))
now, sha, ticks = (H[x] for x in ('now', 'sha', 'ticks'))


def summarize(data):
    if data[-1] != {'event': 'complete', 'exit_code': 0}:
        raise ValueError('incomplete benchmark')
    identity = data[0]
    if (identity['context'], identity['chunk'], identity['output_limit']) != (9216, 2048, 128):
        raise ValueError('benchmark settings mismatch')
    rows = [x for x in data if x['event'] == 'sample']
    order = [(r, i) for r in range(4) for i in ([2, 1, 0] if r == 2 else [0, 1, 2])]
    if [(x['rep'], x['profile']) for x in rows] != order:
        raise ValueError('missing/reordered samples; no partial averaging')
    inputs = [x for x in data if x['event'] == 'input']
    if [x['profile'] for x in inputs] != [0, 1, 2]:
        raise ValueError('input identities missing')
    groups = []
    for i in range(3):
        group = [x for x in rows if x['profile'] == i]
        p = inputs[i]
        if not 0 < p['prompt_tokens'] <= (512, 2048, 8192)[i] or len(p['physical_ids']) != p['prompt_tokens']:
            raise ValueError('physical prompt count')
        for x in group:
            if x['prompt_tokens'] != p['prompt_tokens'] or x['warmup'] != (x['rep'] == 0):
                raise ValueError('prompt/warmup drift')
            if not x['finite_logits'] or (x['rep'] and not x['matches_warmup']):
                raise ValueError('unverified frontier')
            n = x['completed_decode_tokens']
            if not 0 <= n <= 128 or len(x['output_ids']) != n or x['final_position'] != p['prompt_tokens'] + n:
                raise ValueError('decode completion count')
            if n < 128 and not x['stop']:
                raise ValueError('unexplained short decode')
            for name in ('prefill_ns', 'decode_ns'):
                if not math.isfinite(x[name]) or x[name] <= 0:
                    raise ValueError('invalid timing')
            for name in ('output_ids', 'stop', 'prefill_logits_sha256', 'decode_logits_sha256'):
                if x[name] != group[0][name]:
                    raise ValueError('repeatability mismatch')
        measured = group[1:]
        pp = [x['prompt_tokens'] * 1e9 / x['prefill_ns'] for x in measured]
        tg = [x['completed_decode_tokens'] * 1e9 / x['decode_ns'] for x in measured]
        groups.append({'profile': i, 'prompt_tokens': p['prompt_tokens'],
                       'completed_decode_tokens': group[0]['completed_decode_tokens'],
                       'eos': bool(group[0]['stop']), 'measured_repetitions': 3,
                       'prefill_tps': {'median': statistics.median(pp), 'min': min(pp), 'max': max(pp), 'all': pp},
                       'decode_tps': {'median': statistics.median(tg), 'min': min(tg), 'max': max(tg), 'all': tg},
                       'prefill_seconds': [x['prefill_ns'] / 1e9 for x in measured],
                       'decode_seconds': [x['decode_ns'] / 1e9 for x in measured]})
    return {'identity': identity, 'profiles': groups, 'warmups_excluded': 3, 'samples_retained': 9,
            'outliers_removed': 0, 'finite_frontiers_and_exact_repeatability': True,
            'pristine_numerical_qualification': False, 'reactive_speedup_measured': False,
            'scope': 'single-owner direct C ABI; embedded Gufo; not HTTP/worker throughput or GPU-only kernel time'}


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: bench-model.py PRIVATE-RUN-DIRECTORY')
    run = Path(sys.argv[1]).resolve()
    m = json.loads((run / 'manifest.json').read_text())
    if m['authorization']['kind'] != 'operator-one-shot-window' or not m['authorization']['gpu_test_authorized']:
        raise SystemExit('Fresh operator authorization required')
    out = run / 'results'
    out.mkdir()
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    r = {'state': 'PREFLIGHT', 'started_at': now(), 'manifest_sha256': sha(run / 'manifest.json'),
         'runner_sha256': sha(__file__), 'supervisor_pid': os.getpid(), 'supervisor_start_ticks': ticks(os.getpid()),
         'authorization': m['authorization'], 'ds4_ack_claimed': False, 'model_attempted': False,
         'commands': [], 'locks': []}
    locks, child, registered = [], None, False
    interrupted = False

    def save():
        tmp = out / 'result.tmp'
        tmp.write_text(json.dumps(r, indent=2) + '\n')
        tmp.replace(out / 'result.json')

    def stop(signum, frame):
        nonlocal interrupted
        interrupted = True
        r['received_signal'] = signum
        if child is not None and child.poll() is None:
            child.terminate()  # The C harness latches stop and retires completed work.

    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, stop)

    def register(event):
        row = {'owner': 'synapse-lie', 'event': event, 'at': now(), 'run': str(run),
               'pid': os.getpid(), 'start_ticks': r['supervisor_start_ticks'], 'state': r['state'],
               'authorization_kind': m['authorization']['kind'], 'source_commit': m['source_commit'],
               'model': m['models'][0]['path'], 'command': r.get('argv'), 'exit_code': r.get('child_exit_code')}
        fd = os.open('/tmp/synapse-lie-ds4-coordination/runs.jsonl', os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            payload = (json.dumps(row) + '\n').encode()
            if os.write(fd, payload) != len(payload):
                raise RuntimeError('incomplete register write')
            os.fsync(fd)
        finally:
            os.close(fd)

    def command(argv, env):
        p = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=30)
        r['commands'].append({'argv': argv, 'exit_code': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr})
        save()
        if p.returncode:
            raise RuntimeError('preflight command failed')
        return p.stdout

    try:
        for name in m['lock_order']:
            p = Path(name)
            fd = os.open(p, os.O_RDONLY | os.O_CLOEXEC)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BaseException:
                os.close(fd)
                raise
            locks.append(fd)
            s, live = os.fstat(fd), p.stat()
            if (s.st_dev, s.st_ino) != (live.st_dev, live.st_ino):
                raise RuntimeError('lock identity race')
            r['locks'].append({'path': name, 'device': s.st_dev, 'inode': s.st_ino})
        r['models_before'] = [H['model_stat'](x) for x in m['models']]
        r['preflight_memory'] = H['memory']()
        r['preflight_kfd'] = sorted(H['kfd']())
        baseline_dri, denied = H['dri_clients']()
        r['preflight_dri'] = {'pids': sorted(baseline_dri), 'permission_denied': denied}
        if r['preflight_kfd']:
            raise RuntimeError('foreign KFD client before launch')
        trunk = sum(x['bytes'] for x in m['models'] if '/mtp-' not in x['path'])
        if r['preflight_memory']['MemAvailable'] <= trunk:
            raise RuntimeError('available RAM below trunk-size estimate, not OOM/fit evidence')
        binary = run / 'lie-executor-bench'
        for name, expected in m['files'].items():
            if sha(run / name) != expected:
                raise RuntimeError('staged file identity mismatch: ' + name)
        env = {k: v for k, v in os.environ.items() if not k.startswith(('GUFO_', 'DS4_', 'HIP_', 'ROCR_', 'HSA_', 'CUDA_')) and k not in ('LD_PRELOAD', 'LD_LIBRARY_PATH')}
        for key, name in [('HOME', 'home'), ('XDG_CACHE_HOME', 'cache'), ('TMPDIR', 'tmp')]:
            p = run / name
            p.mkdir()
            env[key] = str(p)
        env.update(LC_ALL='C', LD_BIND_NOW='1', ROCR_VISIBLE_DEVICES='0', HIP_VISIBLE_DEVICES='0')
        masked = dict(env, ROCR_VISIBLE_DEVICES='-1', HIP_VISIBLE_DEVICES='-1')
        info = json.loads(command([str(binary), '--build-info'], masked))
        if info != m['build_info'] or info['synthetic'] or info['ownership'] != 'delegated':
            raise RuntimeError('provider/build identity mismatch')
        command(['uname', '-srmo'], masked)
        command(['readelf', '-d', str(binary)], masked)
        linked = command(['ldd', str(binary)], masked)
        if 'not found' in linked:
            raise RuntimeError('unresolved DSO')
        r['dsos'] = {}
        for word in linked.split():
            if word.startswith('/') and Path(word).is_file():
                p = Path(word).resolve()
                if not str(p).startswith(('/usr/', '/opt/rocm/')):
                    raise RuntimeError('unapproved DSO path')
                r['dsos'][str(p)] = sha(p)
        r['power_settings'] = {}
        paths = list(Path('/sys/devices/system/cpu/cpufreq').glob('policy*/*'))
        paths += [Path('/sys/class/drm/card1/device') / x for x in ('power_dpm_force_performance_level', 'pp_power_profile_mode')]
        for p in paths:
            if p.name in ('scaling_governor', 'energy_performance_preference', 'power_dpm_force_performance_level', 'pp_power_profile_mode'):
                r['power_settings'][str(p)] = p.read_text().strip()
        if interrupted or H['kfd']():
            raise RuntimeError('admission interrupted or foreign client appeared')
        r['argv'] = [str(binary), '--model', m['models'][0]['path'], '--output', str(out / 'measurements.jsonl')]
        register('start')
        registered = True
        r['state'] = 'BENCHMARK_RUNNING'
        r['model_attempted'] = True
        with (out / 'stdout.log').open('xb') as log, (out / 'stderr.log').open('xb') as err:
            child = subprocess.Popen(r['argv'], cwd=run, env=env, stdout=log, stderr=err, start_new_session=True)
        r['child_pid'], r['child_start_ticks'] = child.pid, ticks(child.pid)
        save()
        deadline = time.monotonic() + 900
        with (out / 'telemetry.jsonl').open('x') as log:
            while child.poll() is None:
                kfd = H['kfd']()
                drm, denied = H['dri_clients']()
                foreign = (kfd - {child.pid}) | (drm - baseline_dri - {child.pid})
                log.write(json.dumps({'at': now(), 'memory': H['memory'](), 'gpu': H['gpu'](),
                                      'kfd': sorted(kfd), 'dri': sorted(drm), 'dri_permission_denied': denied}) + '\n')
                log.flush()
                if foreign:
                    r['foreign_gpu_clients'] = sorted(foreign)
                    raise RuntimeError('foreign GPU client detected')
                if interrupted or time.monotonic() > deadline:
                    raise RuntimeError('benchmark interrupted/deadline')
                time.sleep(1)
        r['child_exit_code'] = child.returncode
        if child.returncode:
            raise RuntimeError('benchmark failed; see retained measurements/stderr')
        data = [json.loads(x) for x in (out / 'measurements.jsonl').read_text().splitlines()]
        r['summary'] = summarize(data)
        r['measurements_sha256'] = sha(out / 'measurements.jsonl')
        r['state'] = 'C1_COMPLETED_PP_TG_BASELINE_MEASURED_NOT_PRISTINE_QUALIFICATION'
    except BaseException as ex:
        r['state'], r['error'] = 'FAILED', repr(ex)
    finally:
        if child is not None:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=120)
                except subprocess.TimeoutExpired:
                    r['forced_owned_child_kill'] = True
                    child.kill()
                    child.wait()
            r['child_exit_code'] = child.returncode
        try:
            r['models_after'] = [H['model_stat'](x) for x in m['models']]
            r['files_unchanged'] = all(sha(run / name) == expected for name, expected in m['files'].items())
            r['postflight_kfd'], r['postflight_memory'], r['postflight_gpu'] = sorted(H['kfd']()), H['memory'](), H['gpu']()
            if not r['files_unchanged'] or (child and child.pid in r['postflight_kfd']) or interrupted:
                raise RuntimeError('retirement/preservation/interruption failure')
        except Exception as ex:
            r['state'], r['closure_error'] = 'FAILED', repr(ex)
        r['finished_at'] = now()
        save()
        try:
            if registered:
                register('end')
        finally:
            for fd in reversed(locks):
                os.close(fd)
    print(json.dumps(r, indent=2), flush=True)
    return 0 if r['state'] == 'C1_COMPLETED_PP_TG_BASELINE_MEASURED_NOT_PRISTINE_QUALIFICATION' else 1


if __name__ == '__main__':
    raise SystemExit(main())
