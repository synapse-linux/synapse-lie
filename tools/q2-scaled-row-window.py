#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Coordinate one bounded .157 scaled row reuse component window; no cleanup."""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path('/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run')
REGISTRY = Path('/tmp/synapse-lie-ds4-coordination/runs.jsonl')
PREVIOUS = ROOT/'q2-native-scale-window-release.json'
PREVIOUS_SHA = 'e54cadce7133189886dc0d07808f644a16ee1a2c70b84058e16b4cf6a0f62c35'
LABELS = ('q2-scaled-row-before-r1', 'q2-scaled-row-candidate-r1',
          'q2-scaled-row-after-r1')


def read(path):
    return json.loads(path.read_text())


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ('admit', 'release'):
        raise SystemExit('Expected admit/release and source checkpoint')
    mode, checkpoint = sys.argv[1:]
    previous = read(PREVIOUS)
    if hashlib.sha256(PREVIOUS.read_bytes()).hexdigest() != PREVIOUS_SHA:
        raise RuntimeError('Previous canonical release changed')
    admission_path = ROOT/'q2-scaled-row-window-admission.json'
    report_path = admission_path if mode == 'admit' else ROOT/'q2-scaled-row-window-release.json'
    if report_path.exists():
        raise RuntimeError('Refusing to overwrite a window receipt')
    sys.path.insert(0, str(ROOT/'q2-scaled-row-host-r1/tools'))
    from q2_thermal import sample, enforce
    held = []
    try:
        for row in previous['leases']:
            fd = os.open(row['path'], os.O_RDWR | os.O_NOFOLLOW)
            held.append(fd)
            st = os.fstat(fd)
            if (st.st_dev, st.st_ino) != (row['device'], row['inode']):
                raise RuntimeError('Original lease identity changed')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        rows = [json.loads(line) for line in REGISTRY.read_text().splitlines() if line.strip()]
        if mode == 'admit':
            if rows[-1].get('event') != 'window_release' or rows[-1].get('receipt_sha256') != PREVIOUS_SHA:
                raise RuntimeError('Intervening ownership event; cannot admit')
        else:
            own_admission = read(admission_path)
            subsequent = [r for r in rows if r.get('at', '') >= own_admission['at']]
            if any(r.get('owner') != 'synapse-lie-q2' for r in subsequent):
                raise RuntimeError('Foreign event inside bounded window')
        kfd = [p.name for p in Path('/sys/class/kfd/kfd/proc').glob('*')]
        if kfd:
            raise RuntimeError('KFD clients remain')
        identities = {r['pid']: r for r in previous['retired_identities']}
        groups = set(previous['retired_groups'])
        cohorts = []
        labels = ['q2-scaled-row-host-r1']
        if mode == 'release':
            labels.extend(n for n in LABELS
                          if (ROOT/n/'results/result.json').exists())
        for label in labels:
            r = read(ROOT/label/'results/result.json')
            if 'finished_at' not in r:
                raise RuntimeError('Cohort still live')
            if label.startswith('q2-scaled-row-host-') and (r['state'] != 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' or
                    len(r['commands']) != 6 or any(c['exit_code'] for c in r['commands'])):
                raise RuntimeError('Host gate did not pass')
            identities[r['pid']] = dict(pid=r['pid'], start_ticks=None)
            for c in r['commands']:
                identities[c['pid']] = dict(pid=c['pid'], start_ticks=int(c['start_ticks']))
                groups.add(c['pid'])
            session_path = ROOT/label/'results/curve-session.json'
            if session_path.exists():
                session = read(session_path)
                for child in [session.get('server_identity', {}), *session.get('commands', [])]:
                    if 'pid' in child:
                        identities[child['pid']] = dict(pid=child['pid'], start_ticks=int(child['start_ticks']))
                        groups.add(child['process_group'])
            cohorts.append(dict(label=label, finished_at=r['finished_at'],
                                command_exits=[c['exit_code'] for c in r['commands']]))
        members = []
        for p in Path('/proc').glob('[0-9]*'):
            try:
                stat = (p/'stat').read_text().rsplit(')', 1)[1].split()
            except FileNotFoundError:
                continue
            pid, start, group = int(p.name), int(stat[19]), int(stat[2])
            if pid in identities and identities[pid]['start_ticks'] in (None, start):
                raise RuntimeError('Recorded process remains live')
            if group in groups: members.append(pid)
        if members:
            raise RuntimeError('Owned group members remain')
        for row in previous['models']:
            st = Path(row['path']).stat()
            actual = (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
            expected = tuple(row[k] for k in ('device','inode','bytes','mtime_ns','ctime_ns'))
            if actual != expected:
                raise RuntimeError('Original model stat identity changed')
        thermal = sample()
        enforce(thermal)
        if mode == 'admit' and any(r['device'] == 'k10temp' and r['temperature_mc'] > 60000 for r in thermal):
            raise RuntimeError('CPU above admission temperature')
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        report = dict(schema='synapse-lie.q2-scaled-row-window.v1', at=now,
            state='Q2_SCALED_ROW_WINDOW_ADMITTED' if mode == 'admit' else 'Q2_SCALED_ROW_WINDOW_RELEASED',
            owner='synapse-lie-q2', source_checkpoint=checkpoint,
            previous_release=str(PREVIOUS), previous_release_sha256=PREVIOUS_SHA,
            previous_registry_event=rows[-1], cohorts=cohorts,
            retired_identities=list(identities.values()), retired_groups=sorted(groups),
            owned_group_members=[], kfd=kfd, leases=previous['leases'],
            models=previous['models'], model_stats_unchanged=True, thermal=thermal,
            scope='Three scaled row reuse component arms: ordered reference, bounded input reuse, repeated ordered reference. Five recorded/control routing cases, pack and complete pack/down timing, rotating synthetic activations, independent conversion/FP64 checks and complete output digests; no original model or interleaving.',
            gpu_reserved=mode == 'admit', restart_scheduled=False,
            observer_or_waiter=False, remote_cleanup=False, model_inference=False, planned_labels=LABELS)
        if mode == 'release': report['next_window_owner'] = 'core'
        payload = (json.dumps(report, indent=2)+'\n').encode()
        with report_path.open('xb') as stream: stream.write(payload)
        event = dict(event='window_admit' if mode == 'admit' else 'window_release',
            owner='synapse-lie-q2', label='q2-scaled-row', at=now, state=report['state'],
            receipt=str(report_path), receipt_sha256=hashlib.sha256(payload).hexdigest())
        if mode == 'release': event['next_window_owner'] = 'core'
        with REGISTRY.open('a') as stream: stream.write(json.dumps(event)+'\n')
        print(payload.decode(), end='')
    finally:
        for fd in reversed(held): os.close(fd)


if __name__ == '__main__':
    main()
