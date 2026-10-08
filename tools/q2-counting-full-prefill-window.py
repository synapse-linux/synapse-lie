#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Focused exact-counting full-prefill diagnostic on .157.

The script never builds, installs, changes a model, or terminates a foreign
process. `run` owns only the native benchmark children it creates. Collect
the result directory before `release`.
"""

import argparse
import contextlib
import datetime as dt
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from types import SimpleNamespace
import urllib.error
import urllib.request

ROOT = Path('/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run')
BOOT_ID = Path('/proc/sys/kernel/random/boot_id')
EXPECTED_BOOT = '8b9cbb46-c7d4-47c3-b5cc-32e1fdad0653'
EPOCH = ROOT / 'gpu-coordination/epochs' / EXPECTED_BOOT
REGISTRY = EPOCH / 'runs.jsonl'
HERE = Path(__file__).resolve().parent
PLAN = HERE / 'plan.json'
ADMISSION = HERE / 'admission.json'
RELEASE = HERE / 'release.json'
LABEL = 'q2-counting-full-prefill-r1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def validate_power(receipt):
    require(receipt['exit_code'] == 0, 'APU readback command failed')
    settings = json.loads(receipt['stdout'])
    require(settings['apu_power_mode'] == 'performance' and
            settings['tdp_watts'] == 120, 'Original performance/120 W mode differs')
    for fan in ('fan1', 'fan2', 'fan3'):
        require(settings[fan]['mode'] == 'curve' and
                settings[fan]['rampup_curve'] == '40,50,60,70,82' and
                settings[fan]['rampdown_curve'] == '35,45,55,65,78',
                'Qualified fan curve differs: ' + fan)
    return settings


def power_check(path=None):
    argv = ['/usr/bin/axb35-ctl', 'get', 'all']
    process = subprocess.run(argv, capture_output=True, text=True, timeout=20)
    receipt = dict(at=now(), argv=argv, exit_code=process.returncode,
                   stdout=process.stdout, stderr=process.stderr,
                   read_only=True, boot_id=BOOT_ID.read_text().strip())
    if path is not None:
        write_new(path, receipt)
    validate_power(receipt)
    return receipt


def source(plan):
    require(BOOT_ID.read_text().strip() == plan['boot_id'] == EXPECTED_BOOT, 'Boot changed')
    require(plan['schema'] == 'synapse-lie.q2-counting-full-prefill-plan.v1', 'Plan schema differs')
    require(sha(__file__) == plan['runner_sha256'], 'Runner changed')
    require(plan['label'] == LABEL and HERE == ROOT / LABEL, 'Label differs')
    require(plan['order'] == ['short-9216', 'short-133760', '8k-c2048', '8k-c4096', '8k-c8192'] and
            plan['output_tokens'] == 128 and plan['warmups'] == 1 and
            plan['repetitions'] == 3, 'Workload differs')
    require(plan['previous_release'] == 'glm53-qwen-native2048-r2/artifacts/release.json', 'Predecessor differs')
    path = ROOT / plan['previous_release']
    require(sha(path) == plan['previous_release_sha256'], 'Previous release changed')
    previous = read(path)
    require(previous['boot_id'] == EXPECTED_BOOT and
            previous['state'] == 'GLM53_EXISTING_BENCH157_RELEASED' and
            not previous['gpu_reserved'], 'Previous window is not released')
    for name, digest in plan['staged_sha256'].items():
        require(Path(name).name == name and sha(HERE / name) == digest, 'Staged input changed: ' + name)
    cpu = read(HERE / 'cpu-tests.json')
    require(cpu['exit_code'] == 0 and cpu['synthetic'] and not cpu['gpu_access'] and
            not cpu['model_access'], 'Focused CPU tests have not passed')
    require(plan['model_stats'] == previous['models'], 'Model identities differ')
    require('amd_iommu=off' not in Path('/proc/cmdline').read_text().split() and
            bool(list(Path('/sys/kernel/iommu_groups').glob('*'))), 'IOMMU must stay enabled')
    return previous


def registry_rows():
    return [json.loads(line) for line in REGISTRY.read_text().splitlines() if line.strip()]


def assert_retired(previous, own=None):
    require(all(row['boot_id'] == EXPECTED_BOOT for row in
                [*previous['retired_identities'], *(own or [])]),
            'Process identities belong to another boot')
    identities = {row['pid']: row['start_ticks'] for row in previous['retired_identities']}
    groups = set(previous['retired_groups'])
    if own:
        for row in own:
            identities[row['pid']] = row['start_ticks']
            groups.add(row['process_group'])
    for process in Path('/proc').glob('[0-9]*'):
        try:
            fields = (process / 'stat').read_text().rsplit(')', 1)[1].split()
        except FileNotFoundError:
            continue
        pid, group, start = int(process.name), int(fields[2]), int(fields[19])
        require(pid not in identities or identities[pid] not in (None, start),
                'Recorded process remains live')
        require(group not in groups, 'Owned process group remains live')


@contextlib.contextmanager
def leases(previous):
    held = []
    try:
        for row in [previous['core_cpu_lease'], *previous['leases']]:
            fd = os.open(row['path'], os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
            held.append(fd)
            stat = os.fstat(fd)
            require((stat.st_dev, stat.st_ino) == (row['device'], row['inode']),
                    'Original lease identity differs')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        for fd in reversed(held):
            os.close(fd)


def clear(previous, own=None):
    require(not list(Path('/sys/class/kfd/kfd/proc').glob('*')), 'KFD client remains')
    assert_retired(previous, own)
    for row in previous['models']:
        stat = Path(row['path']).stat()
        require((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns,
                 stat.st_ctime_ns) == tuple(row[key] for key in
                    ('device', 'inode', 'bytes', 'mtime_ns', 'ctime_ns')),
                'Original model stat differs')
    if previous.get('glm_model_path'):
        stat = Path(previous['glm_model_path']).stat()
        require(all(getattr(stat, key) == value for key, value in
                    previous['glm_model_stats'].items()), 'GLM model stat differs')


def emit_event(kind, receipt):
    row = dict(event=kind, owner='synapse-lie-q2', label='q2-counting-full-prefill-r1',
               at=receipt['at'], boot_id=EXPECTED_BOOT, receipt=str(receipt['path']),
               receipt_sha256=sha(receipt['path']), state=receipt['state'])
    with REGISTRY.open('a') as stream:
        stream.write(json.dumps(row) + '\n')
    return row


def admit(plan, previous):
    require(not ADMISSION.exists() and not RELEASE.exists(), 'Window receipt exists')
    with leases(previous):
        rows = registry_rows()
        require(rows and rows[-1].get('event') == 'window_release' and
                rows[-1].get('receipt_sha256') == plan['previous_release_sha256'],
                'Intervening ownership event')
        clear(previous)
        power = power_check(HERE / 'admission-power.json')
        receipt = dict(schema='synapse-lie.q2-counting-full-prefill-window.v3',
                       boot_id=EXPECTED_BOOT,
                       state='Q2_COUNTING_FULL_PREFILL_ADMITTED', at=now(),
                       plan_sha256=sha(PLAN), previous_release_sha256=plan['previous_release_sha256'],
                       original_model_stats_unchanged=True, kfd_empty=True,
                       original_leases_free=True, gpu_reserved=True,
                       planned_label=LABEL, remote_cleanup=False,
                       power_readback=power)
        write_new(ADMISSION, receipt)
        emit_event('window_admit', dict(receipt, path=ADMISSION))
        print(json.dumps(receipt))


def active(plan):
    require(ADMISSION.exists() and not RELEASE.exists(), 'No active admission')
    admission = read(ADMISSION)
    require(admission['state'] == 'Q2_COUNTING_FULL_PREFILL_ADMITTED' and
            admission['plan_sha256'] == sha(PLAN), 'Admission plan differs')
    rows = registry_rows()
    require(rows and rows[-1].get('event') == 'window_admit' and
            rows[-1].get('receipt_sha256') == sha(ADMISSION), 'Window is not active')
    return admission


def identity(process):
    fields = Path('/proc', str(process.pid), 'stat').read_text().rsplit(')', 1)[1].split()
    return dict(boot_id=EXPECTED_BOOT, pid=process.pid, start_ticks=int(fields[19]),
                process_group=os.getpgid(process.pid))


def sensor():
    base = Path('/sys/class/drm/card1/device')
    hwmon = next(base.glob('hwmon/hwmon*'))
    return dict(at=now(), gpu_busy=(base/'gpu_busy_percent').read_text().strip(),
                gpu_clock=(base/'pp_dpm_sclk').read_text().strip(),
                gpu_temp_mc=(hwmon/'temp1_input').read_text().strip(),
                gpu_power_uw=(hwmon/'power1_average').read_text().strip())


def cpu_temp_mc():
    temperatures = []
    for hwmon in Path('/sys/class/hwmon').glob('hwmon*'):
        try:
            if (hwmon/'name').read_text().strip() == 'k10temp':
                temperatures.extend(int(p.read_text()) for p in hwmon.glob('temp*_input'))
        except FileNotFoundError:
            continue
    require(temperatures, 'CPU thermal sensor unavailable')
    return max(temperatures)


def cool():
    deadline = time.monotonic() + 600
    while cpu_temp_mc() > 60000:
        require(time.monotonic() < deadline, 'CPU did not return to 60 C before next arm')
        time.sleep(5)


def one_arm(plan, index, arm, result, own):
    cool()
    expected = {
        'short-9216': (2048,2048,9216),
        'short-133760': (2048,2048,133760),
        '8k-c2048': (8192,2048,133760),
        '8k-c4096': (8192,4096,133760),
        '8k-c8192': (8192,8192,133760),
    }
    target, chunk, capacity = expected[arm]
    tag = f'{index:02d}-{arm}'
    output = result / (tag + '.jsonl')
    argv = [str(HERE/'synapse-lie-bench'), '--suite', 'fresh',
            '--model', plan['model_stats'][0]['path'],
            '--prompt-preset', 'q2-counting', '--output', str(output),
            '--sizes', str(target), '--prefill-chunk', str(chunk),
            '--tg', '128', '--warmups', '1', '--repetitions', '3',
            '--context-capacity', str(capacity), '--execution', 'reactive',
            '--graphs', str(result/(tag+'-report'))]
    env = dict(os.environ, HIP_VISIBLE_DEVICES='0', ROCR_VISIBLE_DEVICES='0')
    child = None
    try:
        with (result/(tag+'.log')).open('x') as log, (result/(tag+'.telemetry.jsonl')).open('x') as telemetry:
            child = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT,
                                     cwd=HERE, env=env, start_new_session=True)
            own.append(identity(child))
            write_new(result/(tag+'.start.json'), dict(own[-1], at=now(), argv=argv))
            deadline = time.monotonic()+600
            while child.poll() is None:
                require(time.monotonic()<deadline, 'Owned benchmark timeout')
                temp = cpu_temp_mc()
                telemetry.write(json.dumps(dict(sensor(), cpu_temp_mc=temp))+'\n')
                telemetry.flush()
                require(temp <= 98000, 'CPU exceeds the recorded 98 C gate')
                time.sleep(2)
            require(child.returncode == 0, 'Native benchmark failed')
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try: child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait(timeout=10)
        write_new(result/(tag+'.child.json'), dict(argv=argv, exit_code=child.returncode if child else None,
                  owned_identities=list(own), finished_at=now()))
    records = [json.loads(line) for line in output.read_text().splitlines()]
    require(records[-1]['event']=='complete' and records[-1]['exit_code']==0, 'Incomplete benchmark')
    ident = records[0]
    require(ident['synthetic'] is False and ident['prefill_chunk']==chunk and
            ident['suite']=='fresh' and ident['measurement_contract']=='full-prefill-v1' and
            ident['prompt_contract']=='exact-counting-chat-v1' and
            ident['warmups']==1 and ident['repetitions']==3, 'Wrong benchmark identity')
    inputs = [r for r in records if r['event']=='input']
    samples = [r for r in records if r['event']=='sample']
    require(len(inputs)==1 and len(samples)==4, 'Point or repetition count differs')
    prompt=inputs[0]
    require(prompt['prompt_tokens']==prompt['target_prompt_tokens']==target and
            len(prompt['physical_ids'])==target and prompt['context_capacity']==capacity,
            'Physical prompt or allocation differs')
    for sample in samples:
        require(sample['depth']==0 and sample['cache_tokens']==0 and
                sample['prefill_tokens_per_user']==target and
                sample['prefill_calls_per_user']==target//chunk and
                sample['prefill_tail_tokens']==0 and sample['full_output_budget']==1 and
                sample['output_tokens_per_user']==128 and sample['decode_single_calls']==128,
                'Full prefill or decode accounting differs')
        require(sample['prefill_ns']==sample['prefill_end_monotonic_ns']-sample['prefill_begin_monotonic_ns'],
                'Timestamp difference does not equal elapsed time')
    return dict(arm=arm, index=index, target=target, chunk=chunk, capacity=capacity,
                input_sha256=prompt['physical_ids_sha256'], samples=samples,
                prefill_tps=[s['prefill_tps'] for s in samples if not s['warmup']],
                output_sha256=sha(output), binary_sha256=sha(HERE/'synapse-lie-bench'))


def run(plan, previous):
    active(plan)
    result = ROOT / LABEL / 'results'
    require(not result.exists(), 'Previous pair result exists')
    with leases(previous):
        clear(previous)
        result.mkdir(parents=True)
        own = [identity(SimpleNamespace(pid=os.getpid()))]
        write_new(result/'supervisor-start.json',
                  dict(identity(SimpleNamespace(pid=os.getpid())), at=now()))
        summary = dict(schema='synapse-lie.q2-counting-full-prefill-results.v1',
                       plan_sha256=sha(PLAN), order=plan['order'], started_at=now(),
                       arms=[], owned_identities=own, state='RUNNING')
        try:
            power_check(result / 'power-before.json')
            write_new(result / 'host-configuration.json', dict(
                cmdline=Path('/proc/cmdline').read_text().strip(),
                iommu_groups=len(list(Path('/sys/kernel/iommu_groups').glob('*'))),
                meminfo=Path('/proc/meminfo').read_text(), read_only=True))
            for index, arm in enumerate(plan['order']):
                summary['arms'].append(one_arm(plan, index, arm, result, own))
                write_new(result/f'{index:02d}-receipt.json', summary['arms'][-1])
                print(json.dumps(dict(index=index, arm=arm,
                    prefill_tps=summary['arms'][-1]['prefill_tps'])), flush=True)
            power_check(result / 'power-after.json')
            summary['state'] = 'COMPLETE'
        except Exception as error:
            summary.update(state='FAILED', error=str(error))
            raise
        finally:
            summary['finished_at'] = now()
            write_new(result/'native-result.json', summary)


def release(plan, previous):
    active(plan)
    result = ROOT / LABEL / 'results' / 'native-result.json'
    require(result.exists(), 'Pair result was not collected')
    summary = read(result)
    with leases(previous):
        clear(previous, summary['owned_identities'])
        receipt = dict(schema='synapse-lie.q2-counting-full-prefill-window.v3',
                       boot_id=EXPECTED_BOOT,
                       state='Q2_COUNTING_FULL_PREFILL_RELEASED', at=now(), plan_sha256=sha(PLAN),
                       admission_sha256=sha(ADMISSION), pair_result_sha256=sha(result),
                       pair_state=summary['state'], kfd_empty=True,
                       original_model_stats_unchanged=True, original_leases_free=True,
                       retired_owned_identities=summary['owned_identities'],
                       retired_identities=[*previous['retired_identities'],
                                           *summary['owned_identities']],
                       retired_groups=sorted(set(previous['retired_groups']) |
                                             {row['process_group'] for row in
                                              summary['owned_identities']}),
                       models=previous['models'], leases=previous['leases'],
                       glm_model_path=previous.get('glm_model_path'),
                       glm_model_stats=previous.get('glm_model_stats', {}),
                       core_cpu_lease=previous['core_cpu_lease'],
                       historical_release=previous.get('historical_release', str(ROOT / plan['previous_release'])),
                       historical_release_sha256=previous.get('historical_release_sha256', plan['previous_release_sha256']),
                       remote_cleanup=False, gpu_reserved=False, next_window_owner='core')
        write_new(RELEASE, receipt)
        emit_event('window_release', dict(receipt, path=RELEASE))
        print(json.dumps(receipt))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('verify', 'admit', 'run', 'release'))
    args = parser.parse_args()
    plan = read(PLAN)
    previous = source(plan)
    if args.mode == 'verify':
        rows = registry_rows()
        require(rows and rows[-1].get('event') == 'window_release' and
                rows[-1].get('receipt_sha256') == plan['previous_release_sha256'],
                'Intervening ownership event')
        with leases(previous):
            clear(previous)
            power_check(HERE / 'verify-power.json')
        print(json.dumps(dict(verified=True, gpu_admitted=False, at=now())))
    elif args.mode == 'admit':
        admit(plan, previous)
    elif args.mode == 'run':
        run(plan, previous)
    else:
        release(plan, previous)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print('Q2 exact benchmark trial failed: ' + str(error), file=sys.stderr)
        sys.exit(2)
