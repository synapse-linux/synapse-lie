#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Measure model-owned serial prefill/reactive decode Q2 cohorts on .157.

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
EXPECTED_BOOT = 'be3e89fd-955b-47a4-a385-11c3ad98bb78'
EPOCH = ROOT / 'gpu-coordination/epochs' / EXPECTED_BOOT
REGISTRY = EPOCH / 'runs.jsonl'
HERE = Path(__file__).resolve().parent
PLAN = HERE / 'plan.json'
ADMISSION = HERE / 'admission.json'
RELEASE = HERE / 'release.json'
LABEL = 'q2-core-model-flow-2k8k-r1'


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
    require(plan['schema'] == 'synapse-lie.q2-core-model-flow-2k8k-plan.v1', 'Plan schema differs')
    require(sha(__file__) == plan['runner_sha256'], 'Runner changed')
    require(plan['label'] == LABEL and HERE == ROOT / LABEL, 'Label differs')
    expected = [dict(tokens=size, users=users) for size in (2048, 4096, 6144, 8192)
                for users in (1, 2, 4, 6, 8)]
    require(plan['order'] == expected and plan['output_tokens'] == 128 and
            plan['warmups'] == 0 and plan['repetitions'] == 1 and
            plan['context_capacity'] == 133760 and plan['prefill_chunk'] == 2048 and
            plan['arm_timeout_seconds'] == 900, 'Workload differs')
    require('..' not in Path(plan['previous_release']).parts, 'Predecessor path differs')
    path = ROOT / plan['previous_release']
    require(sha(path) == plan['previous_release_sha256'], 'Previous release changed')
    root_release = read(path)
    require(root_release['state'] == 'COMPILE_COMPLETE_NOT_GPU_QUALIFIED' and
            root_release['gpu_reserved'] is False and
            root_release['actual_exit_code'] == 0,
            'Previous root window is not released')
    closure_path = path.parent / 'strong-closure.json'
    require(sha(closure_path) == plan['previous_closure_sha256'],
            'Previous strong closure changed')
    closure = read(closure_path)
    require(closure['release_sha256'] == plan['previous_release_sha256'] and
            closure['state'] == 'COMPILER_WHOLE_WINDOW_CLOSED_NOT_INFERENCE_QUALIFIED' and
            closure['kfd_empty'] and closure['future_grant'] is False,
            'Previous root closure incomplete')
    foundation_path = ROOT / 'q2-ds4-walk-promessi-r1/release.json'
    require(sha(foundation_path) == plan['foundation_release_sha256'],
            'Q2 foundation release changed')
    previous = read(foundation_path)
    require(previous['boot_id'] == EXPECTED_BOOT == plan['boot_id'] and
            previous['state'] == 'Q2_DS4_WALK_PROMESSI_RELEASED' and
            not previous['gpu_reserved'] and
            closure['original_model_stat_checks'] == previous['models'],
            'Foundation models or state differ')
    for row in closure['identities_checked']:
        previous['retired_identities'].append(dict(
            boot_id=EXPECTED_BOOT,pid=row['pid'],start_ticks=row['start_ticks'],
            process_group=row.get('group',row['pid'])))
    previous['retired_groups'] = sorted(set(previous['retired_groups']) |
                                         set(closure['original_groups_checked']))
    for name, digest in plan['staged_sha256'].items():
        require(Path(name).name == name and sha(HERE / name) == digest,
                'Staged input changed: ' + name)
    for row in plan['inputs']:
        require(sha(HERE / row['file']) == row['file_sha256'], 'Physical input changed')
    cpu = read(HERE / 'cpu-tests.json')
    require(cpu['exit_code'] == 0 and cpu['synthetic'] and not cpu['gpu_access'] and
            not cpu['model_access'], 'Focused CPU tests have not passed')
    require(plan['model_stats'] == previous['models'], 'Model identities differ')
    require('amd_iommu=off' in Path('/proc/cmdline').read_text().split() and
            not list(Path('/sys/kernel/iommu_groups').glob('*')), 'IOMMU must stay disabled')
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
    row = dict(event=kind, owner='synapse-lie-q2', label='q2-core-model-flow-2k8k-r1',
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
        receipt = dict(schema='synapse-lie.q2-core-model-flow-2k8k-window.v1',
                       boot_id=EXPECTED_BOOT,
                       state='Q2_CORE_MODEL_FLOW_2K8K_ADMITTED', at=now(),
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
    require(admission['state'] == 'Q2_CORE_MODEL_FLOW_2K8K_ADMITTED' and
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


def ids_hash(ids):
    return hashlib.sha256(b''.join(value.to_bytes(4, 'little', signed=True)
                                   for value in ids)).hexdigest()


def one_arm(plan, index, arm, result, own):
    cool()
    size, users = arm['tokens'], arm['users']
    require(arm == plan['order'][index], 'Unplanned arm')
    row = next(value for value in plan['inputs'] if value['tokens'] == size)
    tag = f'{index:02d}-q2-p{size}-c{users}'
    output = result / (tag + '.jsonl')
    argv = [str(HERE/'synapse-lie-bench'), '--suite', 'core',
            '--model', plan['model_stats'][0]['path'],
            '--tokens-file', str(HERE/row['file']), '--output', str(output),
            '--context', '133760', '--chunk', '2048', '--users', str(users),
            '--tg', '128', '--warmups', '0', '--repetitions', '1',
            '--kv-cache-ram-mb', '0', '--kv-cache-policy', 'legacy',
            '--graphs', str(result/(tag+'-report'))]
    env = dict(os.environ, HIP_VISIBLE_DEVICES='0', ROCR_VISIBLE_DEVICES='0')
    child = None
    try:
        with (result/(tag+'.log')).open('x') as log, (result/(tag+'.telemetry.jsonl')).open('x') as telemetry:
            child = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT,
                                     cwd=HERE, env=env, start_new_session=True)
            own.append(identity(child))
            write_new(result/(tag+'.start.json'), dict(own[-1], at=now(), argv=argv))
            deadline = time.monotonic()+plan['arm_timeout_seconds']
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
    require(records[-1] == {'event':'complete','exit_code':0}, 'Incomplete benchmark')
    ident = records[0]
    require(ident['synthetic'] is False and ident['suite']=='core' and
            ident['execution']=='shared-reactive-core' and
            ident['prefill_dispatch']=='single-model-owner-serial' and
            ident['decode_dispatch']=='reactive-ready-native-batch' and
            ident['input_kind']=='physical-tokens' and
            ident['context_capacity']==133760 and ident['prefill_chunk']==2048 and
            ident['users']==users and ident['output_limit']==128 and
            ident['warmups']==0 and ident['repetitions']==1 and
            ident['cache_policy']=='off', 'Wrong benchmark identity')
    inputs = [r for r in records if r['event']=='input']
    jobs = [r for r in records if r['event']=='job']
    samples = [r for r in records if r['event']=='sample']
    require(len(inputs)==1 and len(jobs)==users and len(samples)==1,
            'Input/job/sample count differs')
    prompt=inputs[0];sample=samples[0]
    require(prompt['prompt_tokens']==size and len(prompt['physical_ids'])==size and
            prompt['physical_ids_sha256']==row['physical_ids_sha256'] and
            ids_hash(prompt['physical_ids'])==row['physical_ids_sha256'],
            'Physical prompt differs')
    require(sorted(j['user'] for j in jobs)==list(range(users)) and
            all(j['prompt_tokens']==j['prefill_tokens']==size and
                j['prefill_calls']==size//2048 and j['cached_tokens']==0 and
                j['ssd_cached_tokens']==0 and j['output_tokens']==128 for j in jobs),
            'Per-user prefill/decode differs')
    require(sample['users']==users and sample['warmup']==0 and sample['rep']==0 and
            sample['prefill_tokens_total']==users*size and
            sample['model_prefill_started']==sample['model_prefill_returned']==users*size//2048 and
            sample['prefill_executor_ns_total']==sum(j['prefill_ns'] for j in jobs) and
            sample['prefill_executor_ns_total']>0 and
            sample['output_tokens']==users*128 and
            sample['model_decode_started']==sample['model_decode_returned']==
                sample['decode_batches']+sample['decode_single_calls'] and
            sample['decode_executor_ns_total']>0 and
            sample['cache_hits']==sample['cache_captures']==0,
            'Model-owner physical accounting differs')
    for rate, tokens, elapsed in (
        ('prefill_executor_tps',users*size,sample['prefill_executor_ns_total']),
        ('decode_executor_tps',users*128,sample['decode_executor_ns_total']),
        ('output_per_total_wall_tps',users*128,sample['wall_ns'])):
        require(abs(sample[rate]-tokens*1e9/elapsed)<=1e-8*max(sample[rate],1),
                'Throughput/timestamp differs: '+rate)
    return dict(index=index, tokens=size, users=users,
                physical_ids_sha256=row['physical_ids_sha256'], sample=sample,
                model_prefill_tps=sample['prefill_executor_tps'],
                model_decode_tps=sample['decode_executor_tps'],
                output_wall_tps=sample['output_per_total_wall_tps'],
                decode_batches=sample['decode_batches'],
                output_sha256=sha(output), binary_sha256=sha(HERE/'synapse-lie-bench'))


def run(plan, previous):
    active(plan)
    result = ROOT / LABEL / 'results'
    require(not result.exists(), 'Previous matrix result exists')
    with leases(previous):
        clear(previous)
        result.mkdir(parents=True)
        own = [identity(SimpleNamespace(pid=os.getpid()))]
        write_new(result/'supervisor-start.json',
                  dict(identity(SimpleNamespace(pid=os.getpid())), at=now()))
        summary = dict(schema='synapse-lie.q2-core-model-flow-2k8k-results.v1',
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
                    prefill_tps=summary['arms'][-1]['model_prefill_tps'],
                    decode_tps=summary['arms'][-1]['model_decode_tps'])), flush=True)
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
    require(result.exists(), 'Matrix result was not collected')
    summary = read(result)
    with leases(previous):
        clear(previous, summary['owned_identities'])
        receipt = dict(schema='synapse-lie.q2-core-model-flow-2k8k-window.v1',
                       boot_id=EXPECTED_BOOT,
                       state='Q2_CORE_MODEL_FLOW_2K8K_RELEASED', at=now(), plan_sha256=sha(PLAN),
                       admission_sha256=sha(ADMISSION), pair_result_sha256=sha(result),
                       pair_state=summary['state'], kfd_empty=True,
                       immediate_previous_release=plan['previous_release'],
                       immediate_previous_release_sha256=plan['previous_release_sha256'],
                       immediate_previous_closure_sha256=plan['previous_closure_sha256'],
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
        print('Q2 model-flow benchmark trial failed: ' + str(error), file=sys.stderr)
        sys.exit(2)
