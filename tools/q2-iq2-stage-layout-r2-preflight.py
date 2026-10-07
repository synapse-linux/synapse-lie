#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only .157 ownership preflight for the private IQ2 stage-layout component."""

import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path


ROOT = Path('/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run')
PREVIOUS = ROOT / 'q2-iq2-stage-layout-window-release.json'
PREVIOUS_SHA = '2f2bfa77a6754191e3fbb05ca833ade8f4ebd9126b73406743ec1da66430c9bb'
REGISTRY = Path('/tmp/synapse-lie-ds4-coordination/runs.jsonl')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    require(hashlib.sha256(PREVIOUS.read_bytes()).hexdigest() == PREVIOUS_SHA,
            'Previous release receipt differs')
    previous = json.loads(PREVIOUS.read_text())
    rows = [json.loads(line) for line in REGISTRY.read_text().splitlines() if line.strip()]
    require(rows and rows[-1]['event'] == 'window_release' and
            rows[-1]['receipt_sha256'] == PREVIOUS_SHA, 'Intervening ownership event')
    kfd = sorted(path.name for path in Path('/sys/class/kfd/kfd/proc').glob('*'))
    require(not kfd, 'KFD client remains')
    identities = {row['pid']: row['start_ticks'] for row in previous['retired_identities']}
    groups = set(previous['retired_groups'])
    for process in Path('/proc').glob('[0-9]*'):
        try:
            fields = (process / 'stat').read_text().rsplit(')', 1)[1].split()
        except FileNotFoundError:
            continue
        pid, group, start = int(process.name), int(fields[2]), int(fields[19])
        require(pid not in identities or identities[pid] not in (None, start),
                'Recorded process remains live')
        require(group not in groups, 'Owned process group remains live')
    for row in previous['models']:
        stat = Path(row['path']).stat()
        require((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns,
                 stat.st_ctime_ns) ==
                tuple(row[key] for key in ('device', 'inode', 'bytes', 'mtime_ns',
                                           'ctime_ns')), 'Original model stat changed')
    held = []
    try:
        for row in [previous['core_cpu_lease'], *previous['leases']]:
            fd = os.open(row['path'], os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
            held.append(fd)
            stat = os.fstat(fd)
            require((stat.st_dev, stat.st_ino) ==
                    (row['device'], row['inode']), 'Original lease identity changed')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        report = {
            'schema': 'synapse-lie.q2-iq2-stage-layout-r2-preflight.v1',
            'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'previous_release_sha256': PREVIOUS_SHA,
            'latest_registry_event': rows[-1],
            'kfd': kfd,
            'retired_identity_count': len(identities),
            'retired_group_count': len(groups),
            'models_unchanged': len(previous['models']),
            'leases_free': len(held),
            'gpu_admitted': False,
            'remote_build': False,
            'model_access': False,
        }
        print(json.dumps(report, indent=2))
    finally:
        for fd in reversed(held):
            os.close(fd)


if __name__ == '__main__':
    main()
