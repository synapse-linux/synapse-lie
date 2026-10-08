#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Admit/release the partition selector component on .157; never clean up processes."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path('/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run')
REGISTRY = Path('/tmp/synapse-lie-ds4-coordination/runs.jsonl')
PREVIOUS_SHA = '7c5193f944c7e135e678b48bc62e2517d2c913c80e6215f4817a25f03ee7042b'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def retire(identities, groups):
    for process in Path('/proc').glob('[0-9]*'):
        try:
            stat = (process / 'stat').read_text().rsplit(')', 1)[1].split()
        except FileNotFoundError:
            continue
        pid, start, group = int(process.name), int(stat[19]), int(stat[2])
        require(pid not in identities or identities[pid]['start_ticks'] not in (None, start),
                'Recorded process remains live')
        require(group not in groups, 'Owned group member remains')


def cohort(label, expected_sha, identities, groups, host=False, retired_cpu=False, model=False):
    path = ROOT / label / 'results/result.json'
    if expected_sha:
        require(sha(path) == expected_sha, 'Saved cohort receipt differs')
    result = read(path)
    require(result.get('finished_at') and result['model_access'] is model,
            'Cohort unfinished or model scope differs')
    exits = [c['exit_code'] for c in result['commands']]
    if host:
        require(result['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and
                result['mode'] == 'cpu' and exits == [0] * 6, 'Host gate did not pass')
    elif retired_cpu:
        require(result['mode'] in ('cpu', 'curve256-cpu') and exits and
                result['state'] in ('FAILED', 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE') and
                all(type(code) is int for code in exits), 'Historical CPU closure incomplete')
    else:
        # A terminal device/build failure may release the window. It does not
        # authorize analysis/adoption or a subsequent original-model arm.
        require(result['mode'] == 'select-partition-check' and not model and exits and
                all(type(code) is int for code in exits), 'Component scope/exit lost')
    identities[result['pid']] = dict(pid=result['pid'], start_ticks=None)
    for command in result['commands']:
        identities[command['pid']] = dict(pid=command['pid'], start_ticks=int(command['start_ticks']))
        groups.add(command.get('process_group', command['pid']))
    session_path = ROOT / label / 'results/curve-session.json'
    if session_path.exists():
        session = read(session_path)
        for child in [session.get('server_identity', {}), *session.get('commands', [])]:
            if 'pid' in child:
                identities[child['pid']] = dict(pid=child['pid'], start_ticks=int(child['start_ticks']))
                groups.add(child['process_group'])
    return dict(label=label, finished_at=result['finished_at'], command_exits=exits)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('admit', 'release'))
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--checkpoint', required=True)
    args = parser.parse_args()
    plan = read(args.plan)
    require(plan['schema'] == 'synapse-lie.q2-select-partition-plan.v1' and
            not plan['arms'] and len(plan['components']) == 1 and
            [(a['mode'],a['variant']) for a in plan['components']] ==
            [('select-partition-check','iq2-fixed-bounds')],
            'Expected the new partition selector component only')
    require(sha(Path(__file__)) == plan['window_helper_sha256'], 'Window helper differs')
    previous_path = ROOT / Path(plan['previous_release']).name
    require(plan['previous_release_sha256'] == PREVIOUS_SHA and
            sha(previous_path) == PREVIOUS_SHA, 'Previous canonical release differs')
    previous = read(previous_path)
    admission_path = ROOT / Path(plan['admission_path']).name
    release_path = ROOT / Path(plan['release_path']).name
    require(not release_path.exists(), 'Window already released')
    output_path = admission_path if args.mode == 'admit' else release_path
    require(not output_path.exists(), 'Refusing to overwrite a window receipt')
    # The host's source capsule is the tested runtime for this admission.
    for name, digest in {**plan['fixtures'], **plan['manifests']}.items():
        path = ROOT / plan['host'] / name
        require(sha(path) == digest, 'Tested capsule differs: ' + name)
    sys.path.insert(0, str(ROOT / plan['host'] / 'tools'))
    from q2_thermal import sample, enforce
    from q2_window_registry import active_window
    held = []
    try:
        for row in [plan['core_cpu_lease'], *previous['leases']]:
            fd = os.open(row['path'], os.O_RDWR | os.O_NOFOLLOW)
            held.append(fd)
            stat = os.fstat(fd)
            require((stat.st_dev, stat.st_ino) == (row['device'], row['inode']),
                    'Original lease identity differs')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        rows = [json.loads(line) for line in REGISTRY.read_text().splitlines() if line.strip()]
        admission = None
        if args.mode == 'admit':
            require(rows and rows[-1].get('event') == 'window_release' and
                    rows[-1].get('receipt_sha256') == PREVIOUS_SHA,
                    'Intervening ownership event')
        else:
            admission = read(admission_path)
            require(admission['state'] == 'Q2_SELECT_PARTITION_WINDOW_ADMITTED' and
                    admission['gpu_reserved'] is True and admission['owner'] == 'synapse-lie-q2' and
                    admission['plan_sha256'] == sha(args.plan) and
                    admission['planned_labels'] == [a['label'] for a in plan['components'] + plan['arms']],
                    'Active admission scope differs')
            active_window(rows, sha(admission_path), admission['at'])
        kfd = [p.name for p in Path('/sys/class/kfd/kfd/proc').glob('*')]
        require(not kfd, 'KFD clients remain')
        identities = {r['pid']: r for r in previous['retired_identities']}
        groups = set(previous['retired_groups'])
        for row in plan['core_identities']:
            identities[row['pid']] = row
        groups.update(plan['core_groups'])
        supplemental = plan['supplemental_cpu']
        require(read(Path(supplemental['path'])) == supplemental['receipt'],
                'Supplemental CPU receipt differs')
        command = supplemental['receipt']['command']
        require(supplemental['receipt']['exit_code'] == 0 and
                supplemental['receipt']['owned_group_retired'], 'Supplemental CPU closure incomplete')
        identities[command['pid']] = dict(pid=command['pid'], start_ticks=command['start_ticks'])
        groups.add(command['process_group'])
        for historical in plan.get('retired_cpu_cohorts', []):
            cohort(historical['label'], historical['result_sha256'], identities, groups,
                   retired_cpu=True)
        cohorts = [cohort(plan['host'], plan['host_result_sha256'], identities, groups, host=True)]
        if args.mode == 'release':
            for arm in plan['components'] + plan['arms']:
                if (ROOT / arm['label']).exists():
                    cohorts.append(cohort(arm['label'], None, identities, groups, model=arm in plan['arms']))
        retire(identities, groups)
        for row in previous['models']:
            stat = Path(row['path']).stat()
            require((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns) ==
                    tuple(row[k] for k in ('device', 'inode', 'bytes', 'mtime_ns', 'ctime_ns')),
                    'Original model stat identity differs')
        thermal = sample()
        enforce(thermal)
        require(args.mode != 'admit' or all(row['device'] != 'k10temp' or
                row['temperature_mc'] <= 60000 for row in thermal), 'CPU above admission temperature')
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        require(not admission or now > admission['at'], 'Release precedes admission')
        report = dict(schema='synapse-lie.q2-select-partition-window.v1', at=now,
            state='Q2_SELECT_PARTITION_WINDOW_ADMITTED' if args.mode == 'admit'
                  else 'Q2_SELECT_PARTITION_WINDOW_RELEASED',
            owner='synapse-lie-q2', source_checkpoint=args.checkpoint, plan_sha256=sha(args.plan),
            previous_release=str(previous_path), previous_release_sha256=PREVIOUS_SHA,
            previous_registry_event=rows[-1], cohorts=cohorts, qualified_host_labels=[plan['host']],
            historical_cpu_cohorts=plan.get('retired_cpu_cohorts', []),
            retired_identities=list(identities.values()), retired_groups=sorted(groups),
            owned_group_members=[], kfd=kfd, leases=previous['leases'], core_cpu_lease=plan['core_cpu_lease'],
            core_closure_sha256=plan['core_closure_sha256'], supplemental_cpu=supplemental,
            models=previous['models'], model_stats_unchanged=True, thermal=thermal, scope=plan['scope'],
            gpu_reserved=args.mode == 'admit', model_inference=any(c['label'] in [a['label'] for a in plan['arms']] for c in cohorts),
            planned_labels=[a['label'] for a in plan['components'] + plan['arms']],
            observer_or_waiter=False, restart_scheduled=False, remote_cleanup=False)
        if admission:
            report['admission_sha256'] = sha(admission_path)
            report['next_window_owner'] = 'core'
        payload = (json.dumps(report, indent=2, allow_nan=False) + '\n').encode()
        with output_path.open('xb') as stream:
            stream.write(payload)
        event = dict(event='window_admit' if args.mode == 'admit' else 'window_release',
            owner='synapse-lie-q2', label='q2-select-partition', at=now, state=report['state'],
            receipt=str(output_path), receipt_sha256=hashlib.sha256(payload).hexdigest())
        if admission:
            event['next_window_owner'] = 'core'
        with REGISTRY.open('a') as stream:
            stream.write(json.dumps(event) + '\n')
        print(payload.decode(), end='')
    finally:
        for fd in reversed(held):
            os.close(fd)


if __name__ == '__main__':
    main()
