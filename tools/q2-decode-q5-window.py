#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""One bounded .157 Q5 dense decode component window; no model or cleanup."""

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
RELEASE = HERE / 'release.json'
RESULT = HERE / 'result.json'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def rows():
    return [json.loads(line) for line in REGISTRY.read_text().splitlines()
            if line.strip()]


def clients():
    return sorted(p.name for p in Path('/sys/class/kfd/kfd/proc').glob('*'))


def identity(process):
    fields = (Path('/proc') / str(process) / 'stat').read_text().rsplit(')', 1)[1].split()
    return int(fields[2]), int(fields[19])


def retired(previous, result=None):
    identities = {row['pid']: row['start_ticks']
                  for row in previous['retired_identities']}
    groups = set(previous['retired_groups'])
    if result and result.get('pid'):
        require(result['pid'] not in identities and
                result['process_group'] not in groups,
                'Owned process identity collides with prior retirement')
        identities[result['pid']] = result['start_ticks']
        groups.add(result['process_group'])
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


def models(previous):
    for row in previous['models']:
        stat = Path(row['path']).stat()
        require((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns,
                 stat.st_ctime_ns) ==
                tuple(row[key] for key in ('device', 'inode', 'bytes',
                                           'mtime_ns', 'ctime_ns')),
                'Original model stat changed')


def load():
    plan = json.loads(PLAN.read_text())
    require(plan['schema'] == 'synapse-lie.q2-decode-q5-window-plan.v1' and
            plan['label'] == 'q2-decode-q5-component-r1' and
            plan['component_only'] and not plan['model_access'] and
            not plan['remote_build'] and not plan['remote_cleanup'] and
            plan['timeout_seconds'] == 900 and
            plan['original_model_inference'] is False,
            'Unexpected component scope')
    for name, digest in plan['staged_sha256'].items():
        require(Path(name).name == name and
                name not in ('plan.json', 'admission.json', 'release.json') and
                sha(HERE / name) == digest, 'Staged file changed: ' + name)
    require(plan['previous_release'] ==
            'q2-iq2-token160-component-r1/handover.json',
            'Previous release path differs')
    previous_path = RUN / plan['previous_release']
    require(sha(previous_path) == plan['previous_release_sha256'],
            'Previous release differs')
    return plan, json.loads(previous_path.read_text())


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
        for fd in reversed(held):
            os.close(fd)
        raise


def close(held):
    for fd in reversed(held):
        os.close(fd)


def active(plan):
    admission = json.loads(ADMISSION.read_text())
    require(admission['state'] == 'Q2_DECODE_Q5_WINDOW_ADMITTED' and
            admission['plan_sha256'] == sha(PLAN), 'Admission differs')
    events = rows()
    windows = [row for row in events if row.get('event') in
               ('window_admit', 'window_release')]
    require(windows and windows[-1]['event'] == 'window_admit' and
            windows[-1]['receipt_sha256'] == sha(ADMISSION) and
            windows[-1]['at'] == admission['at'], 'Window is not active')
    require(all(row.get('owner') == 'synapse-lie-q2'
                for row in events if row.get('at', '') >= admission['at']),
            'Foreign registry event inside window')
    require(admission['label'] == plan['label'], 'Admitted label differs')
    return admission


def write_event(path, event, report):
    payload = (json.dumps(report, indent=2, allow_nan=False) + '\n').encode()
    with path.open('xb') as output:
        output.write(payload)
    registry = {'event': event, 'owner': 'synapse-lie-q2',
                'label': report['label'], 'at': report['at'],
                'state': report['state'], 'receipt': str(path),
                'receipt_sha256': hashlib.sha256(payload).hexdigest()}
    if event == 'window_release':
        registry['next_window_owner'] = 'core'
    with REGISTRY.open('a') as stream:
        stream.write(json.dumps(registry) + '\n')
    print(payload.decode(), end='')


def preflight_or_admit(mode, plan, previous):
    held = leases(previous)
    try:
        require(not ADMISSION.exists() and not RELEASE.exists() and
                not RESULT.exists(), 'Window already started')
        events = rows()
        require(events and events[-1]['event'] == 'window_release' and
                events[-1]['receipt_sha256'] == plan['previous_release_sha256'],
                'Intervening ownership event')
        require(not clients(), 'KFD client remains')
        retired(previous)
        models(previous)
        thermal = sample()
        enforce(thermal)
        require(all(row['temperature_mc'] <= 60000 for row in thermal
                    if row['device'] == 'k10temp'),
                'CPU above admission temperature')
        report = {'schema': 'synapse-lie.q2-decode-q5-window.v1',
                  'state': ('PREFLIGHT_OK' if mode == 'preflight'
                            else 'Q2_DECODE_Q5_WINDOW_ADMITTED'),
                  'at': now(), 'label': plan['label'],
                  'plan_sha256': sha(PLAN), 'previous_registry_event': events[-1],
                  'kfd': [], 'models_unchanged': len(previous['models']),
                  'leases_free': len(held), 'thermal': thermal,
                  'gpu_reserved': mode == 'admit', 'model_access': False,
                  'remote_cleanup': False}
        if mode == 'admit':
            write_event(ADMISSION, 'window_admit', report)
        else:
            print(json.dumps(report, indent=2))
    finally:
        close(held)


def run(plan, previous):
    active(plan)
    require(not RESULT.exists() and not clients(), 'Component already ran or KFD busy')
    held = leases(previous)
    try:
        models(previous)
        thermal_start = sample()
        enforce(thermal_start)
        stdout = HERE / 'component.stdout'
        stderr = HERE / 'component.stderr'
        limit = plan['timeout_seconds']
        started = now()
        reason = None
        with stdout.open('xb') as out, stderr.open('xb') as err:
            process = subprocess.Popen([str(HERE / 'q2_decode_q5_dense_check')],
                                       cwd=HERE, stdout=out, stderr=err,
                                       start_new_session=True)
            process_group, start_ticks = identity(process.pid)
            require(process_group == process.pid, 'Owned process group differs')
            deadline = time.monotonic() + limit
            peak_cpu = max(row['temperature_mc'] for row in thermal_start
                           if row['device'] == 'k10temp')
            peak_gpu = max(row['temperature_mc'] for row in thermal_start
                           if row['device'] == 'amdgpu')
            while process.poll() is None:
                try:
                    thermal = sample()
                    peak_cpu = max(peak_cpu, *(row['temperature_mc'] for row in thermal
                                               if row['device'] == 'k10temp'))
                    peak_gpu = max(peak_gpu, *(row['temperature_mc'] for row in thermal
                                               if row['device'] == 'amdgpu'))
                    if any(row['over_limit'] for row in thermal):
                        reason = 'thermal_limit'
                except Exception:
                    reason = 'thermal_sensor_error'
                if time.monotonic() > deadline:
                    reason = 'timeout'
                if reason:
                    os.killpg(process_group, signal.SIGTERM)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process_group, signal.SIGKILL)
                    break
                time.sleep(0.25)
            exit_code = process.wait()
        report = {'schema': 'synapse-lie.q2-decode-q5-component.v1',
                  'mode': 'decode-q5-dense-check', 'started_at': started,
                  'finished_at': now(), 'pid': process.pid,
                  'process_group': process_group, 'start_ticks': start_ticks,
                  'exit_code': exit_code, 'stop_reason': reason,
                  'stdout_sha256': sha(stdout), 'stderr_sha256': sha(stderr),
                  'binary_sha256': sha(HERE / 'q2_decode_q5_dense_check'),
                  'peak_cpu_mc': peak_cpu, 'peak_gpu_mc': peak_gpu,
                  'model_access': False, 'remote_cleanup': False}
        with RESULT.open('x') as output:
            json.dump(report, output, indent=2)
            output.write('\n')
        print(json.dumps(report, indent=2))
        return 0 if exit_code == 0 else 1
    finally:
        close(held)


def release(plan, previous):
    admission = active(plan)
    held = leases(previous)
    try:
        require(not RELEASE.exists(), 'Window already released')
        result = json.loads(RESULT.read_text()) if RESULT.exists() else None
        require(not result or result['finished_at'], 'Component is not terminal')
        identities, groups = retired(previous, result)
        require(not clients(), 'KFD client remains')
        models(previous)
        thermal = sample()
        enforce(thermal)
        report = {'schema': 'synapse-lie.q2-decode-q5-window.v1',
                  'state': 'Q2_DECODE_Q5_WINDOW_RELEASED',
                  'at': now(), 'label': plan['label'],
                  'plan_sha256': sha(PLAN), 'admission_sha256': sha(ADMISSION),
                  'previous_release_sha256': plan['previous_release_sha256'],
                  'component_result_sha256': sha(RESULT) if result else None,
                  'component_exit_code': result['exit_code'] if result else None,
                  'retired_identities': [
                      {'pid': pid, 'start_ticks': start}
                      for pid, start in sorted(identities.items())],
                  'retired_groups': sorted(groups),
                  'core_cpu_lease': previous['core_cpu_lease'],
                  'leases': previous['leases'],
                  'models': previous['models'],
                  'kfd': [], 'models_unchanged': len(previous['models']),
                  'leases_free': len(held), 'thermal': thermal,
                  'gpu_reserved': False, 'model_access': False,
                  'remote_cleanup': False, 'next_window_owner': 'core',
                  'admitted_at': admission['at']}
        write_event(RELEASE, 'window_release', report)
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
