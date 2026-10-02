#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""One-shot leased simplified benchmark supervisor. No builds, downloads, tuning or retries.
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
import stat
import statistics
import subprocess
import sys
import time

H = runpy.run_path(str(Path(__file__).with_name('smoke-model.py')))
now, sha, ticks = (H[x] for x in ('now', 'sha', 'ticks'))


def read_power_settings(paths):
    observed = {}
    for p in paths:
        try:
            observed[str(p)] = {'value': p.read_text().strip(), 'error': None}
        except OSError as ex:
            # Optional telemetry, not an admission control. Never invent a value.
            observed[str(p)] = {'value': None, 'error': {'type': type(ex).__name__, 'errno': ex.errno}}
    return observed


REPORT = runpy.run_path(str(Path(__file__).with_name("bench-report.py")))


def validate_args(args):
    allowed={'--suite','--sizes','--depths','--users','--pp','--tg','--warmups','--repetitions','--execution'}
    if not isinstance(args,list) or len(args)%2 or any(type(x) is not str for x in args):
        raise ValueError('invalid declared benchmark arguments')
    keys=args[::2]
    options=dict(zip(keys,args[1::2]))
    if options.get('--suite')=='core':
        allowed={'--suite','--users','--tg','--warmups','--repetitions',
                 '--context','--chunk','--timeout-ms','--prompt-file','--tokens-file','--prefix-cache-mib'}
    if options.get('--suite')=='state':
        allowed={'--suite','--context','--chunk','--pp','--tokens-file'}
    if len(set(keys))!=len(keys) or any(k not in allowed for k in keys):
        raise ValueError('unapproved/duplicate benchmark option')
    if not args or '--suite' not in keys:
        raise ValueError('explicit benchmark suite required')
    return args


def bind_args(args, run, manifest):
    """Bind a core input to one immutable staged file, never an external path."""
    args=validate_args(args)
    options=dict(zip(args[::2],args[1::2]))
    if options['--suite'] not in ('core','state'):
        if manifest.get('benchmark_input') is not None:
            raise ValueError('input manifest only applies to core suite')
        return args
    keys=[k for k in ('--prompt-file','--tokens-file') if k in options]
    declared=manifest.get('benchmark_input')
    if len(keys)!=1 or not isinstance(declared,dict):
        raise ValueError('one bound core input required')
    name=options[keys[0]]
    if not name or name in ('.','..') or Path(name).name!=name or name.startswith('-'):
        raise ValueError('core input must be a staged basename')
    if declared.get('path')!=name or type(declared.get('bytes')) is not int or not 0<declared['bytes']<=8*1024*1024:
        raise ValueError('core input declaration mismatch')
    if manifest.get('files',{}).get(name)!=declared.get('sha256') or not isinstance(declared.get('sha256'),str):
        raise ValueError('core input missing from file identities')
    fd=os.open(Path(run)/name,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        info=os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size!=declared['bytes']:
            raise ValueError('core input size/type mismatch')
        data=f.read(8*1024*1024+1)
    import hashlib
    if len(data)!=declared['bytes'] or hashlib.sha256(data).hexdigest()!=declared['sha256']:
        raise ValueError('core input content mismatch')
    result=list(args);result[result.index(keys[0])+1]=str(Path(run).resolve()/name)
    return result


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: run-bench.py PRIVATE-RUN-DIRECTORY')
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
            if m.get('lock_identities') and m['lock_identities'].get(name) != [s.st_dev,s.st_ino]:
                raise RuntimeError('unexpected established lease identity')
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
        reserve=m.get('ram_cache_reserve_bytes',0)
        if type(reserve) is not int or reserve<0 or r['preflight_memory']['MemAvailable']<=trunk+reserve:
            raise RuntimeError('RAM cache reserve admission failed; no memory-fit claim')
        binary = run / 'synapse-lie-bench'
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
        benchmark_args = bind_args(m['benchmark_args'],run,m)
        selected_suite = dict(zip(benchmark_args[::2],benchmark_args[1::2]))['--suite']
        info = json.loads(command([str(binary), *(['--suite',selected_suite] if selected_suite in ('core','state') else []), '--build-info'], masked))
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
        paths = list(Path('/sys/devices/system/cpu/cpufreq').glob('policy*/*'))
        paths += [Path('/sys/class/drm/card1/device') / x for x in ('power_dpm_force_performance_level', 'pp_power_profile_mode')]
        r['power_settings'] = read_power_settings(p for p in paths if p.name in (
            'scaling_governor', 'energy_performance_preference', 'power_dpm_force_performance_level', 'pp_power_profile_mode'))
        if interrupted or H['kfd']():
            raise RuntimeError('admission interrupted or foreign client appeared')
        r['argv'] = [str(binary), '--model', m['models'][0]['path'], '--output', str(out / 'measurements.jsonl')]
        r['argv'] += benchmark_args
        register('start')
        registered = True
        r['state'] = 'BENCHMARK_RUNNING'
        r['model_attempted'] = True
        with (out / 'stdout.log').open('xb') as log, (out / 'stderr.log').open('xb') as err:
            child = subprocess.Popen(r['argv'], cwd=run, env=env, stdout=log, stderr=err, start_new_session=True)
        r['child_pid'], r['child_start_ticks'] = child.pid, ticks(child.pid)
        save()
        deadline = time.monotonic() + 3600
        with (out / 'telemetry.jsonl').open('x') as log:
            while child.poll() is None:
                kfd = H['kfd']()
                drm, denied = H['dri_clients']()
                foreign = (kfd - {child.pid}) | (drm - baseline_dri - {child.pid})
                log.write(json.dumps({'at': now(), 'memory': H['memory'](), 'gpu': H['gpu'](),
                                      'kfd': sorted(kfd), 'dri': sorted(drm), 'dri_permission_denied': denied,
                                      'process': H['process_status'](child.pid)}) + '\n')
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
        r['summary'] = REPORT['read_result'](out / 'measurements.jsonl')
        r['measurements_sha256'] = sha(out / 'measurements.jsonl')
        r['state'] = 'SIMPLIFIED_BENCHMARK_PASS_NOT_INDEPENDENT_QUALIFICATION'
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
    return 0 if r['state'] == 'SIMPLIFIED_BENCHMARK_PASS_NOT_INDEPENDENT_QUALIFICATION' else 1


if __name__ == '__main__':
    raise SystemExit(main())
