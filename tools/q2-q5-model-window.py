#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bounded original-model Q8/Q5 exact-2048 window on .157; no cleanup."""

import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from q2_thermal import enforce, sample


HERE = Path(__file__).resolve().parent
RUN = HERE.parent
REGISTRY = Path('/tmp/synapse-lie-ds4-coordination/runs.jsonl')
PLAN = HERE / 'plan.json'
ADMISSION = HERE / 'admission.json'
RESULT = HERE / 'result.json'
RELEASE = HERE / 'release.json'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def registry():
    return [json.loads(line) for line in REGISTRY.read_text().splitlines()
            if line.strip()]


def kfd():
    return sorted(p.name for p in Path('/sys/class/kfd/kfd/proc').glob('*'))


def identity(pid):
    fields = (Path('/proc') / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()
    return int(fields[2]), int(fields[19])


def load():
    plan = json.loads(PLAN.read_text())
    require(plan['schema'] == 'synapse-lie.q2-q5-model-window-plan.v1' and
            plan['label'] == 'q2-q5-model-shared-down-r1' and
            plan['previous_release'] == 'q2-q5-overlay-converter-r1/release.json' and
            plan['family'] == 'shared-down' and
            plan['arms'] == ['q8', 'shared-down'] and
            plan['physical_prompt_tokens'] == 2048 and
            plan['context_capacity'] == 9216 and plan['chunk'] == 2048 and
            plan['output_tokens'] == 128 and plan['timed_decode_calls'] == 127 and
            plan['input_sha256'] ==
                '75343e606f5b815fe01f69ddc6ce50a997e2de96d8a20304a82a7f24f1180b35' and
            plan['model_access'] and not plan['remote_build'] and
            not plan['remote_cleanup'] and plan['timeout_seconds_per_arm'] == 900,
            'Unexpected original-model test scope')
    for name, expected in plan['staged_sha256'].items():
        require(Path(name).name == name and name not in
                ('plan.json', 'admission.json', 'result.json', 'release.json') and
                digest(HERE / name) == expected, 'Staged bytes differ: ' + name)
    previous_path = RUN / plan['previous_release']
    require(digest(previous_path) == plan['previous_release_sha256'],
            'Previous release differs')
    previous = json.loads(previous_path.read_text())
    require(plan['model_path'] == previous['models'][0]['path'],
            'Original model path differs')
    return plan, previous


def leases(previous):
    held = []
    try:
        for row in [previous['core_cpu_lease'], *previous['leases']]:
            fd = os.open(row['path'], os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
            held.append(fd)
            stat = os.fstat(fd)
            require((stat.st_dev, stat.st_ino) == (row['device'], row['inode']),
                    'Original lease identity differs')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return held
    except Exception:
        close(held)
        raise


def close(held):
    for fd in reversed(held):
        os.close(fd)


def check_models(previous):
    for row in previous['models']:
        stat = Path(row['path']).stat()
        require((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns,
                 stat.st_ctime_ns) == tuple(row[key] for key in
                 ('device', 'inode', 'bytes', 'mtime_ns', 'ctime_ns')),
                'Original model stat changed')


def retired(previous, result=None):
    identities = {row['pid']: row['start_ticks']
                  for row in previous['retired_identities']}
    groups = set(previous['retired_groups'])
    observed = {row['pid']: row for path in sorted(HERE.glob('*/launch.json'))
                for row in [json.loads(path.read_text())]}
    for path in sorted(HERE.glob('*/arm.json')):
        row = json.loads(path.read_text())
        observed[row['pid']] = row
    if result:
        for row in result.get('arms', []):
            observed[row['pid']] = row
    if observed:
        for arm in observed.values():
            pid, group, start = (arm[key] for key in
                                 ('pid', 'process_group', 'start_ticks'))
            require(pid not in identities and group not in groups,
                    'Owned process identity collision')
            identities[pid] = start
            groups.add(group)
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            group, start = identity(proc.name)
        except FileNotFoundError:
            continue
        pid = int(proc.name)
        require(pid not in identities or identities[pid] not in (None, start),
                'Recorded process remains live')
        require(group not in groups, 'Recorded process group remains live')
    return identities, groups


def active(plan):
    admission = json.loads(ADMISSION.read_text())
    require(admission['state'] == 'Q2_Q5_MODEL_WINDOW_ADMITTED' and
            admission['plan_sha256'] == digest(PLAN), 'Admission differs')
    events = registry()
    windows = [row for row in events if row.get('event') in
               ('window_admit', 'window_release')]
    require(windows and windows[-1]['event'] == 'window_admit' and
            windows[-1]['receipt_sha256'] == digest(ADMISSION) and
            windows[-1]['at'] == admission['at'], 'Window is not active')
    require(all(row.get('owner') == 'synapse-lie-q2'
                for row in events if row.get('at', '') >= admission['at']),
            'Foreign registry event inside window')
    return admission


def event(path, kind, report):
    payload = (json.dumps(report, indent=2, allow_nan=False) + '\n').encode()
    with path.open('xb') as output:
        output.write(payload)
    row = {'event': kind, 'owner': 'synapse-lie-q2',
           'label': report['label'], 'at': report['at'],
           'state': report['state'], 'receipt': str(path),
           'receipt_sha256': hashlib.sha256(payload).hexdigest()}
    if kind == 'window_release':
        row['next_window_owner'] = 'core'
    with REGISTRY.open('a') as output:
        output.write(json.dumps(row) + '\n')
    print(payload.decode(), end='')


def preflight_or_admit(mode, plan, previous):
    held = leases(previous)
    try:
        require(not ADMISSION.exists() and not RESULT.exists() and
                not RELEASE.exists(), 'Window already started')
        events = registry()
        require(events and events[-1]['event'] == 'window_release' and
                events[-1]['receipt_sha256'] == plan['previous_release_sha256'],
                'Intervening ownership event')
        require(not kfd(), 'KFD client remains')
        retired(previous)
        check_models(previous)
        thermal = sample()
        enforce(thermal)
        require(all(row['temperature_mc'] <= 60000 for row in thermal
                    if row['device'] == 'k10temp'),
                'CPU above admission temperature')
        report = {'schema': 'synapse-lie.q2-q5-model-window.v1',
                  'state': ('PREFLIGHT_OK' if mode == 'preflight' else
                            'Q2_Q5_MODEL_WINDOW_ADMITTED'),
                  'at': now(), 'label': plan['label'],
                  'plan_sha256': digest(PLAN),
                  'previous_registry_event': events[-1], 'kfd': [],
                  'models_unchanged': len(previous['models']),
                  'leases_free': len(held), 'thermal': thermal,
                  'gpu_reserved': mode == 'admit', 'model_access': True,
                  'remote_cleanup': False}
        if mode == 'admit':
            event(ADMISSION, 'window_admit', report)
        else:
            print(json.dumps(report, indent=2))
    finally:
        close(held)


def measure_arm(plan, name):
    work = HERE / name
    work.mkdir(mode=0o755)
    (work / 'results').mkdir(mode=0o755)
    out, err = work / 'stdout', work / 'stderr'
    environment = os.environ.copy()
    environment.pop('LIE_EXPERIMENTAL_Q5_DECODE', None)
    if name != 'q8':
        environment['LIE_EXPERIMENTAL_Q5_DECODE'] = name
    started = now()
    reason = None
    peak_cpu = 0
    peak_gpu = 0
    with out.open('xb') as stdout, err.open('xb') as stderr:
        process = subprocess.Popen([str(HERE / 'q2_model'),
                                    plan['model_path'], 'bench2k'],
                                   cwd=work, env=environment, stdout=stdout,
                                   stderr=stderr, start_new_session=True)
        try:
            group, start_ticks = identity(process.pid)
            require(group == process.pid, 'Owned process group differs')
            with (work / 'launch.json').open('x') as launched:
                json.dump({'pid': process.pid, 'process_group': group,
                           'start_ticks': start_ticks, 'at': started}, launched)
                launched.write('\n')
            deadline = time.monotonic() + plan['timeout_seconds_per_arm']
            while process.poll() is None:
                try:
                    thermal = sample()
                    peak_cpu = max(peak_cpu, *(row['temperature_mc'] for row in
                                               thermal if row['device'] == 'k10temp'))
                    peak_gpu = max(peak_gpu, *(row['temperature_mc'] for row in
                                               thermal if row['device'] == 'amdgpu'))
                    if any(row['over_limit'] for row in thermal):
                        reason = 'thermal_limit'
                except Exception:
                    reason = 'thermal_sensor_error'
                if time.monotonic() > deadline:
                    reason = 'timeout'
                if reason:
                    os.killpg(group, signal.SIGTERM)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(group, signal.SIGKILL)
                    break
                time.sleep(0.5)
            exit_code = process.wait()
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
    files = {p.name: {'bytes': p.stat().st_size, 'sha256': digest(p)}
             for p in sorted((work / 'results').glob('*')) if p.is_file()}
    input_ok = (files.get('pp2048-input.i32', {}).get('sha256') ==
                plan['input_sha256'])
    report = {'name': name, 'started_at': started, 'finished_at': now(),
              'pid': process.pid, 'process_group': group,
              'start_ticks': start_ticks, 'exit_code': exit_code,
              'stop_reason': reason, 'stdout_sha256': digest(out),
              'stderr_sha256': digest(err), 'files': files,
              'original_input_match': input_ok, 'peak_cpu_mc': peak_cpu,
              'peak_gpu_mc': peak_gpu}
    with (work / 'arm.json').open('x') as output:
        json.dump(report, output, indent=2)
        output.write('\n')
    return report


def run(plan, previous):
    active(plan)
    require(not RESULT.exists() and not kfd(), 'Run already started or KFD busy')
    held = leases(previous)
    arms = []
    try:
        check_models(previous)
        for name in plan['arms']:
            arm = measure_arm(plan, name)
            arms.append(arm)
            if arm['exit_code'] or arm['stop_reason'] or not arm['original_input_match']:
                break
        report = {'schema': 'synapse-lie.q2-q5-model-result.v1',
                  'label': plan['label'], 'at': now(),
                  'plan_sha256': digest(PLAN), 'binary_sha256': digest(HERE/'q2_model'),
                  'arms': arms, 'complete': len(arms) == len(plan['arms']) and
                  all(a['exit_code'] == 0 and a['original_input_match'] and
                      a['stop_reason'] is None for a in arms),
                  'model_access': True, 'remote_cleanup': False}
        with RESULT.open('x') as output:
            json.dump(report, output, indent=2)
            output.write('\n')
        print(json.dumps({'at': report['at'], 'complete': report['complete'],
                          'arms': [{k: a[k] for k in ('name', 'exit_code',
                                   'stop_reason', 'original_input_match')}
                                   for a in arms]}, indent=2))
        return 0 if report['complete'] else 1
    finally:
        close(held)


def release(plan, previous):
    admission = active(plan)
    held = leases(previous)
    try:
        require(not RELEASE.exists(), 'Window already released')
        result = json.loads(RESULT.read_text()) if RESULT.exists() else None
        identities, groups = retired(previous, result)
        require(not kfd(), 'KFD client remains')
        check_models(previous)
        thermal = sample()
        enforce(thermal)
        report = {'schema': 'synapse-lie.q2-q5-model-window.v1',
                  'state': 'Q2_Q5_MODEL_WINDOW_RELEASED', 'at': now(),
                  'label': plan['label'], 'plan_sha256': digest(PLAN),
                  'admission_sha256': digest(ADMISSION),
                  'previous_release_sha256': plan['previous_release_sha256'],
                  'result_sha256': digest(RESULT) if result else None,
                  'retired_identities': [
                      {'pid': pid, 'start_ticks': start}
                      for pid, start in sorted(identities.items())],
                  'retired_groups': sorted(groups),
                  'core_cpu_lease': previous['core_cpu_lease'],
                  'leases': previous['leases'], 'models': previous['models'],
                  'kfd': [], 'models_unchanged': len(previous['models']),
                  'leases_free': len(held), 'thermal': thermal,
                  'gpu_reserved': False, 'model_access': True,
                  'remote_cleanup': False, 'next_window_owner': 'core',
                  'admitted_at': admission['at']}
        event(RELEASE, 'window_release', report)
    finally:
        close(held)


def main():
    require(len(sys.argv) == 2 and sys.argv[1] in
            ('preflight', 'admit', 'run', 'release'), 'Expected one window mode')
    plan, previous = load()
    mode = sys.argv[1]
    if mode in ('preflight', 'admit'):
        preflight_or_admit(mode, plan, previous)
    elif mode == 'run':
        return run(plan, previous)
    else:
        release(plan, previous)
    return 0


if __name__ == '__main__':
    sys.exit(main())
