#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Admit and release one IQ2 stage-layout component on .157 without cleanup."""

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
PREVIOUS_SHA = 'f960565737549f74bd095402f217083207c3cca2ac2220b1042caac3703c7320'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def cohort(label, digest, identities, groups, host):
    path = ROOT / label / 'results/result.json'
    require(path.is_file() and (not digest or sha(path) == digest),
            'Cohort result missing or changed')
    result = json.loads(path.read_text())
    exits = [row.get('exit_code') for row in result['commands']]
    require(result.get('finished_at') and not result['model_access'] and
            exits and all(type(code) is int for code in exits),
            'Cohort not terminal or accessed a model')
    if host:
        require(result['mode'] == 'cpu' and
                result['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and
                exits == [0] * 6, 'Host cohort did not pass')
    else:
        require(result['mode'] == 'iq2-stage-layout-check',
                'Component mode changed')
    identities[result['pid']] = {'pid': result['pid'], 'start_ticks': None}
    for row in result['commands']:
        identities[row['pid']] = {'pid': row['pid'],
                                  'start_ticks': int(row['start_ticks'])}
        groups.add(row.get('process_group', row['pid']))
    return {'label': label, 'finished_at': result['finished_at'],
            'command_exits': exits, 'state': result['state']}


def retire(identities, groups):
    for process in Path('/proc').glob('[0-9]*'):
        try:
            fields = (process / 'stat').read_text().rsplit(')', 1)[1].split()
        except FileNotFoundError:
            continue
        pid, group, start = int(process.name), int(fields[2]), int(fields[19])
        require(pid not in identities or
                identities[pid]['start_ticks'] not in (None, start),
                'Recorded process remains live')
        require(group not in groups, 'Owned group remains live')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('admit', 'release'))
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--checkpoint', required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    require(plan['schema'] == 'synapse-lie.q2-iq2-stage-layout-plan.v1' and
            plan['previous_release_sha256'] == PREVIOUS_SHA and
            plan['arms'] == [] and len(plan['components']) == 1 and
            (plan['components'][0]['mode'], plan['components'][0]['variant']) ==
            ('iq2-stage-layout-check', 'iq2-stage-layout') and
            not plan['gpu_admitted'] and not plan['model_inference'] and
            not plan['production_dispatch_changed'], 'Unexpected plan scope')
    previous_path = ROOT / Path(plan['previous_release']).name
    require(sha(previous_path) == PREVIOUS_SHA,
            'Previous canonical release differs')
    previous = json.loads(previous_path.read_text())
    admission_path = ROOT / Path(plan['admission_path']).name
    release_path = ROOT / Path(plan['release_path']).name
    require(not release_path.exists(), 'Window already released')
    output_path = admission_path if args.mode == 'admit' else release_path
    require(not output_path.exists(), 'Refusing to overwrite window receipt')
    for name, digest in plan['fixtures'].items():
        require(sha(ROOT / plan['host'] / name) == digest,
                'Tested host source differs: ' + name)
    sys.path.insert(0, str(ROOT / plan['host'] / 'tools'))
    from q2_thermal import sample, enforce
    from q2_window_registry import active_window

    held = []
    try:
        for row in [previous['core_cpu_lease'], *previous['leases']]:
            fd = os.open(row['path'], os.O_RDONLY | os.O_NOFOLLOW)
            held.append(fd)
            stat = os.fstat(fd)
            require((stat.st_dev, stat.st_ino) ==
                    (row['device'], row['inode']),
                    'Original lease identity differs')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        rows = [json.loads(line) for line in REGISTRY.read_text().splitlines()
                if line.strip()]
        admission = None
        if args.mode == 'admit':
            require(rows and rows[-1].get('event') == 'window_release' and
                    rows[-1].get('receipt_sha256') == PREVIOUS_SHA,
                    'Intervening ownership event')
        else:
            admission = json.loads(admission_path.read_text())
            require(admission['state'] == 'Q2_IQ2_STAGE_LAYOUT_WINDOW_ADMITTED' and
                    admission['gpu_reserved'] and
                    admission['plan_sha256'] == sha(args.plan) and
                    admission['planned_labels'] ==
                    [plan['components'][0]['label']],
                    'Active admission scope differs')
            active_window(rows, sha(admission_path), admission['at'])
        kfd = sorted(path.name for path in
                     Path('/sys/class/kfd/kfd/proc').glob('*'))
        require(not kfd, 'KFD client remains')
        identities = {row['pid']: row
                      for row in previous['retired_identities']}
        groups = set(previous['retired_groups'])
        cohorts = [cohort(plan['host'], plan['host_result_sha256'],
                          identities, groups, host=True)]
        if args.mode == 'release':
            label = plan['components'][0]['label']
            if (ROOT / label).exists():
                cohorts.append(cohort(label, None, identities, groups,
                                      host=False))
        retire(identities, groups)
        for row in previous['models']:
            stat = Path(row['path']).stat()
            require((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns,
                     stat.st_ctime_ns) ==
                    tuple(row[key] for key in ('device', 'inode', 'bytes',
                                               'mtime_ns', 'ctime_ns')),
                    'Original model identity differs')
        thermal = sample()
        enforce(thermal)
        require(args.mode != 'admit' or
                all(row['device'] != 'k10temp' or
                    row['temperature_mc'] <= 60000 for row in thermal),
                'CPU above admission temperature')
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        require(not admission or now > admission['at'],
                'Release precedes admission')
        report = {
            'schema': 'synapse-lie.q2-iq2-stage-layout-window.v1',
            'at': now,
            'state': ('Q2_IQ2_STAGE_LAYOUT_WINDOW_ADMITTED'
                      if args.mode == 'admit'
                      else 'Q2_IQ2_STAGE_LAYOUT_WINDOW_RELEASED'),
            'owner': 'synapse-lie-q2',
            'source_checkpoint': args.checkpoint,
            'plan_sha256': sha(args.plan),
            'previous_release': str(previous_path),
            'previous_release_sha256': PREVIOUS_SHA,
            'previous_registry_event': rows[-1],
            'cohorts': cohorts,
            'retired_identities': list(identities.values()),
            'retired_groups': sorted(groups),
            'kfd': kfd,
            'leases': previous['leases'],
            'core_cpu_lease': previous['core_cpu_lease'],
            'models': previous['models'],
            'model_stats_unchanged': True,
            'thermal': thermal,
            'scope': plan['scope'],
            'gpu_reserved': args.mode == 'admit',
            'model_inference': False,
            'planned_labels': [plan['components'][0]['label']],
            'observer_or_waiter': False,
            'restart_scheduled': False,
            'remote_cleanup': False,
        }
        if admission:
            report['admission_sha256'] = sha(admission_path)
            report['next_window_owner'] = 'core'
        payload = (json.dumps(report, indent=2, allow_nan=False) + '\n').encode()
        with output_path.open('xb') as stream:
            stream.write(payload)
        event = {
            'event': 'window_admit' if args.mode == 'admit'
                     else 'window_release',
            'owner': 'synapse-lie-q2',
            'label': 'q2-iq2-stage-layout',
            'at': now,
            'state': report['state'],
            'receipt': str(output_path),
            'receipt_sha256': hashlib.sha256(payload).hexdigest(),
        }
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
