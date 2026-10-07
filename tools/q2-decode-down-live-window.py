#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""One Q2_K decode zero-padding component; no model access or remote build."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    'epoch', HERE / 'q2-decode-down-rows-native128-performance-window.py')
epoch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(epoch)
from q2_thermal import enforce, sample

LABEL = 'q2-decode-down-live-component-r1'
PLAN = HERE / 'plan.json'
ADMISSION = HERE / 'admission.json'
RELEASE = HERE / 'release.json'
RESULT = HERE / 'result.json'
require, sha, read, write_new, now = (
    epoch.require, epoch.sha, epoch.read, epoch.write_new, epoch.now)


def load():
    plan = read(PLAN)
    require(plan['schema'] == 'synapse-lie.q2-decode-down-live-window-plan.v1'
            and plan['label'] == LABEL and HERE == epoch.ROOT / LABEL,
            'Unexpected component scope')
    require(epoch.BOOT_ID.read_text().strip() == plan['boot_id'] == epoch.EXPECTED_BOOT,
            'Boot changed; separate coordination required')
    require(plan['component_only'] and not plan['model_access']
            and not plan['remote_build'] and not plan['remote_cleanup']
            and plan['timeout_seconds'] == 300, 'Unexpected work requested')
    require(plan['previous_release'] == 'q2-select-key-tile-steady-component-r1/release.json',
            'Unexpected predecessor')
    prior = epoch.ROOT / plan['previous_release']
    require(sha(prior) == plan['previous_release_sha256'], 'Previous receipt changed')
    previous = read(prior)
    require(previous['boot_id'] == epoch.EXPECTED_BOOT and
            not previous['gpu_reserved'], 'Previous window is not released')
    for name, digest in plan['staged_sha256'].items():
        require(Path(name).name == name and sha(HERE / name) == digest,
                'Staged input changed: ' + name)
    return plan, previous


def event(kind, path, report):
    write_new(path, report)
    with epoch.REGISTRY.open('a') as stream:
        stream.write(json.dumps(dict(event=kind, owner='synapse-lie-q2',
            label=LABEL, at=report['at'], boot_id=epoch.EXPECTED_BOOT,
            receipt=str(path), receipt_sha256=sha(path), state=report['state']))+'\n')


def active():
    require(ADMISSION.exists() and not RELEASE.exists(), 'No active admission')
    row = epoch.registry_rows()[-1]
    require(row['event'] == 'window_admit' and
            row['receipt_sha256'] == sha(ADMISSION) and
            read(ADMISSION)['plan_sha256'] == sha(PLAN), 'Active window differs')


def admit(mode, plan, previous):
    with epoch.leases(previous):
        require(not ADMISSION.exists() and not RELEASE.exists() and not RESULT.exists(),
                'Window already used')
        row = epoch.registry_rows()[-1]
        require(row['event'] == 'window_release' and
                row['receipt_sha256'] == plan['previous_release_sha256'],
                'Intervening ownership event')
        epoch.clear(previous)
        power = epoch.power_check()
        thermal = sample()
        enforce(thermal)
        require(all(r['temperature_mc'] <= 60000 for r in thermal
                    if r['device'] == 'k10temp'), 'CPU above admission threshold')
        report = dict(state='DECODE_DOWN_LIVE_ADMITTED' if mode == 'admit' else 'VERIFIED',
            label=LABEL, boot_id=epoch.EXPECTED_BOOT, at=now(), plan_sha256=sha(PLAN),
            power=power, thermal=thermal, gpu_reserved=mode == 'admit')
        if mode == 'admit':
            event('window_admit', ADMISSION, report)
        print(json.dumps(report))


def run(plan, previous):
    active()
    require(not RESULT.exists(), 'Component already ran')
    with epoch.leases(previous):
        epoch.clear(previous)
        own = []
        write_new(HERE/'supervisor-start.json',
                  dict(epoch.identity(SimpleNamespace(pid=os.getpid())), at=now()))
        report = dict(state='RUNNING', started_at=now(), owned_identities=own,
                      exit_code=None, model_access=False, remote_cleanup=False)
        child = None
        try:
            epoch.power_check(HERE/'power-before.json')
            (HERE/'results').mkdir()
            with (HERE/'component.stdout').open('xb') as out, \
                    (HERE/'component.stderr').open('xb') as err, \
                    (HERE/'thermal.jsonl').open('x') as thermal_log:
                child = subprocess.Popen([str(HERE/'q2_decode_down_live_check')],
                    cwd=HERE, stdout=out, stderr=err, start_new_session=True,
                    env=dict(os.environ, HIP_VISIBLE_DEVICES='0', ROCR_VISIBLE_DEVICES='0'))
                own.append(epoch.identity(child))
                write_new(HERE/'child-start.json', dict(own[-1], at=now()))
                deadline = time.monotonic() + plan['timeout_seconds']
                while child.poll() is None:
                    thermal = sample()
                    thermal_log.write(json.dumps(dict(at=now(), sensors=thermal))+'\n')
                    thermal_log.flush()
                    enforce(thermal)
                    require(time.monotonic() < deadline, 'Component timeout')
                    time.sleep(.25)
                report['exit_code'] = child.returncode
            epoch.power_check(HERE/'power-after.json')
            report['state'] = 'COMPLETE' if child.returncode in (0, 1) else 'FAILED'
        except Exception as error:
            report.update(state='FAILED', error=str(error))
        finally:
            if child is not None:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGTERM)
                    try:
                        child.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait(timeout=10)
                report['exit_code'] = child.returncode
            report['finished_at'] = now()
            write_new(RESULT, report)
        print(json.dumps(report))
        return report['exit_code'] if report['state'] == 'COMPLETE' else 2


def release(plan, previous):
    active()
    result = read(RESULT)
    require(result['finished_at'] and result['state'] != 'RUNNING', 'Not terminal')
    with epoch.leases(previous):
        epoch.clear(previous, result['owned_identities'])
        receipt = {key: previous[key] for key in (
            'boot_id', 'models', 'leases', 'core_cpu_lease',
            'historical_release', 'historical_release_sha256')}
        receipt.update(schema='synapse-lie.q2-decode-down-live-window.v1',
            state='DECODE_DOWN_LIVE_RELEASED', label=LABEL, at=now(),
            plan_sha256=sha(PLAN), admission_sha256=sha(ADMISSION),
            component_result_sha256=sha(RESULT), component_exit_code=result['exit_code'],
            retired_owned_identities=result['owned_identities'],
            retired_identities=[*previous['retired_identities'], *result['owned_identities']],
            retired_groups=sorted(set(previous['retired_groups']) |
                {r['process_group'] for r in result['owned_identities']}),
            gpu_reserved=False, kfd_empty=True, original_model_stats_unchanged=True,
            original_leases_free=True, remote_cleanup=False, next_window_owner='core')
        event('window_release', RELEASE, receipt)
        print(json.dumps(receipt))


def main():
    require(len(sys.argv) == 2 and sys.argv[1] in ('verify', 'admit', 'run', 'release'),
            'Expected one window mode')
    plan, previous = load()
    mode = sys.argv[1]
    if mode in ('verify', 'admit'):
        admit(mode, plan, previous)
    elif mode == 'run':
        return run(plan, previous)
    else:
        release(plan, previous)
    return 0


if __name__ == '__main__':
    sys.exit(main())
