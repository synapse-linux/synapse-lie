#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run an owned build/test group with thermal telemetry; never tune the host."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time

HWMON = Path('/sys/class/hwmon')
CPUINFO = Path('/proc/cpuinfo')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--timeout', type=float, default=600)
    p.add_argument('--limit-c', type=float, default=85,
                   help='CPU ceiling in Celsius; GPU temperature is observed only')
    p.add_argument('command', nargs=argparse.REMAINDER)
    a = p.parse_args()
    argv = a.command[1:] if a.command[:1] == ['--'] else a.command
    if not argv or not 30 <= a.limit_c <= 98 or not 0 < a.timeout <= 7200:
        p.error('Command, timeout and temperature limit are required and bounded')
    if a.limit_c>85 and 'ryzen ai max+ 395' not in CPUINFO.read_text().lower():
        p.error('Raised thermal ceiling requires the qualified Strix Halo 395 host')
    a.output.mkdir(parents=True, exist_ok=False)
    sensors = []
    for device in sorted(HWMON.glob('hwmon*')):
        name = (device / 'name').read_text().strip()
        if name not in ('k10temp', 'amdgpu', 'nvme', 'coretemp'):
            continue
        for path in sorted(device.glob('temp*_input')):
            limit = None if name=='amdgpu' else min(a.limit_c,85) if name=='nvme' else a.limit_c
            for suffix in ('max', 'crit'):
                if name == 'amdgpu':
                    continue
                bound = path.with_name(path.name[:-6] + '_' + suffix)
                if bound.exists():
                    value = int(bound.read_text()) / 1000
                    if 30 <= value <= 150:
                        limit = min(limit, value)
            sensors.append({'name': name, 'path': str(path), 'limit_c': limit,
                            'policy': 'observe-only' if name=='amdgpu' else 'operating-ceiling'})
    plan = {'argv': argv, 'cwd': os.getcwd(), 'sensors': sensors,
            'timeout_s': a.timeout, 'pid': os.getpid(),
            'scope': 'Owned child process group only; no power/fan/clock changes'}
    (a.output / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    child = None
    reason = None
    signal_received = None
    started = time.monotonic()
    peaks = {}

    def interrupted(signum, _frame):
        nonlocal signal_received
        signal_received = signum

    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)

    def sample(log):
        nonlocal reason
        row = {'wall_time_ns': time.time_ns(), 'elapsed_s': time.monotonic() - started, 'temperatures': []}
        try:
            if not any(s['name'] in ('k10temp', 'coretemp') for s in sensors):
                raise ValueError('No CPU temperature sensor')
            for s in sensors:
                value = int(Path(s['path']).read_text()) / 1000
                if not -40 <= value <= 150:
                    raise ValueError('Invalid sensor reading')
                row['temperatures'].append(dict(s, value_c=value))
                peaks[s['path']] = max(peaks.get(s['path'], value), value)
                if s['limit_c'] is not None and value >= s['limit_c']:
                    reason = 'thermal_limit'
        except (OSError, ValueError) as exc:
            row['error'] = str(exc)
            reason = 'sensor_error'
        log.write(json.dumps(row) + '\n')
        log.flush()

    code = 125
    with (a.output / 'temperatures.jsonl').open('x') as telemetry, (a.output / 'command.log').open('x') as log:
        sample(telemetry)
        if reason is None:
            # Limit numerical Python tooling in functional/plot fixtures only.
            # This helper is not a performance runner or a model launcher.
            env = dict(os.environ, LC_ALL='C', ROCR_VISIBLE_DEVICES='-1', HIP_VISIBLE_DEVICES='-1', CUDA_VISIBLE_DEVICES='-1',
                       OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
            try:
                child = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
                while child.poll() is None:
                    sample(telemetry)
                    if signal_received:
                        reason = 'interrupted'
                    elif time.monotonic() - started >= a.timeout:
                        reason = 'timeout'
                    if reason:
                        # Popen owns the group; no PID lookup or foreign kill.
                        try:
                            os.killpg(child.pid, signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                        try:
                            child.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            os.killpg(child.pid, signal.SIGKILL)
                            child.wait()
                        break
                    time.sleep(1)
                code = child.wait()
            except OSError as exc:
                reason = 'spawn_error'
                log.write(str(exc) + '\n')
        sample(telemetry)
    result = {'argv': argv, 'child_exit_code': code if child else None,
              'exit_code': 125 if reason else code, 'reason': reason,
              'peak_c': peaks, 'elapsed_s': time.monotonic() - started}
    (a.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    return result['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
