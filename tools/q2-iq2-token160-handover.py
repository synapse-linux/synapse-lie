#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Append a verified full-inventory handover for the closed token160 window."""

import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path

from q2_thermal import enforce, sample


HERE = Path(__file__).resolve().parent
RUN = HERE.parent
REGISTRY = Path('/tmp/synapse-lie-ds4-coordination/runs.jsonl')
PREVIOUS = RUN / 'q2-select-live-grid-pair-r2-window-release.json'
PRIOR_SHA = 'd14805883aaba480fcd51be1ae0b9efb38786076f7f4be3da8681447f7fa0d68'
RELEASE = HERE / 'release.json'
RELEASE_SHA = 'b937ad6c4238092a63f534db9851349b6e713b71f716f3d4466ddeb55eb0a7d6'
RESULT = HERE / 'result.json'
RESULT_SHA = '8497920ea85653e235eb3ee7379b7d74fb07270ad764d13240a3f16136a2f961'
PLAN_SHA = 'a7fb3d30ccebd19916ede75a3a267e3d47e060a401c6464e85cec096b2f160b3'
OUT = HERE / 'handover.json'


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def process_identity(path):
    fields = (path / 'stat').read_text().rsplit(')', 1)[1].split()
    return int(fields[2]), int(fields[19])


def main():
    require(not OUT.exists(), 'Handover already exists')
    require(sha(PREVIOUS) == PRIOR_SHA and sha(RELEASE) == RELEASE_SHA and
            sha(RESULT) == RESULT_SHA and sha(HERE / 'plan.json') == PLAN_SHA,
            'Frozen evidence differs')
    previous = json.loads(PREVIOUS.read_text())
    release = json.loads(RELEASE.read_text())
    result = json.loads(RESULT.read_text())
    require(release['state'] == 'Q2_IQ2_TOKEN160_WINDOW_RELEASED' and
            release['component_result_sha256'] == RESULT_SHA and
            release['admission_sha256'] == sha(HERE / 'admission.json') and
            release['kfd'] == [] and release['models_unchanged'] == 7 and
            release['leases_free'] == 5 and not release['remote_cleanup'] and
            result['exit_code'] == 0 and result['finished_at'] and
            not result['model_access'], 'Closed component evidence differs')
    held = []
    try:
        for row in [previous['core_cpu_lease'], *previous['leases']]:
            fd = os.open(row['path'], os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
            held.append(fd)
            stat = os.fstat(fd)
            require((stat.st_dev, stat.st_ino) == (row['device'], row['inode']),
                    'Original lease inode differs')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        events = [json.loads(line) for line in REGISTRY.read_text().splitlines()
                  if line.strip()]
        require(events and events[-1]['event'] == 'window_release' and
                events[-1]['receipt_sha256'] == RELEASE_SHA,
                'Intervening ownership event')
        require(not list(Path('/sys/class/kfd/kfd/proc').glob('*')),
                'KFD client remains')
        identities = {row['pid']: row['start_ticks']
                      for row in previous['retired_identities']}
        require(result['pid'] not in identities,
                'Owned child PID collides with retired inventory')
        identities[result['pid']] = result['start_ticks']
        groups = set(previous['retired_groups'])
        groups.add(result['process_group'])
        for proc in Path('/proc').glob('[0-9]*'):
            try:
                group, start = process_identity(proc)
            except FileNotFoundError:
                continue
            pid = int(proc.name)
            require(pid not in identities or identities[pid] not in (None, start),
                    'Recorded process remains live')
            require(group not in groups, 'Recorded group remains live')
        for row in previous['models']:
            stat = Path(row['path']).stat()
            require((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns,
                     stat.st_ctime_ns) ==
                    tuple(row[key] for key in ('device', 'inode', 'bytes',
                                               'mtime_ns', 'ctime_ns')),
                    'Original model stat changed')
        thermal = sample()
        enforce(thermal)
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        report = {
            'schema': 'synapse-lie.q2-iq2-token160-handover.v1',
            'state': 'Q2_IQ2_TOKEN160_HANDOVER_RELEASED',
            'owner': 'synapse-lie-q2', 'at': now,
            'label': 'q2-iq2-token160-handover-r1',
            'previous_release': str(RELEASE),
            'previous_release_sha256': RELEASE_SHA,
            'prior_full_release': str(PREVIOUS),
            'prior_full_release_sha256': PRIOR_SHA,
            'component_result_sha256': RESULT_SHA,
            'plan_sha256': PLAN_SHA,
            'handover_helper_sha256': sha(Path(__file__)),
            'retired_identities': list(previous['retired_identities']) +
                                  [{'pid': result['pid'],
                                    'start_ticks': result['start_ticks']}],
            'retired_groups': sorted(groups),
            'core_cpu_lease': previous['core_cpu_lease'],
            'leases': previous['leases'], 'models': previous['models'],
            'kfd': [], 'thermal': thermal,
            'models_unchanged': len(previous['models']),
            'leases_free': len(held), 'gpu_reserved': False,
            'model_access': False, 'remote_cleanup': False,
            'next_window_owner': 'core',
            'amendment_reason': 'The original terminal release recorded only counts for retired identities and groups; this immutable receipt adds the full verified inventory.',
        }
        payload = (json.dumps(report, indent=2, allow_nan=False) + '\n').encode()
        with OUT.open('xb') as output:
            output.write(payload)
        event = {'event': 'window_release', 'owner': 'synapse-lie-q2',
                 'label': report['label'], 'at': now, 'state': report['state'],
                 'receipt': str(OUT),
                 'receipt_sha256': hashlib.sha256(payload).hexdigest(),
                 'next_window_owner': 'core'}
        with REGISTRY.open('a') as stream:
            stream.write(json.dumps(event) + '\n')
        print(payload.decode(), end='')
    finally:
        for fd in reversed(held):
            os.close(fd)


if __name__ == '__main__':
    main()
