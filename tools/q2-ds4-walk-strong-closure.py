#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent readback after the owned Q2 DS4-walk window has been released."""
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
BOOT = 'be3e89fd-955b-47a4-a385-11c3ad98bb78'
REGISTRY = Path('/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run/gpu-coordination/epochs') / BOOT / 'runs.jsonl'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    release_path = HERE / 'release.json'
    release = json.loads(release_path.read_text())
    digest = sha(release_path)
    require(release['state'] == 'Q2_DS4_WALK_PROMESSI_RELEASED' and
            release['boot_id'] == BOOT and not release['gpu_reserved'], 'Release state differs')
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT, 'Boot changed')
    last = json.loads(REGISTRY.read_text().splitlines()[-1])
    require(last['event'] == 'window_release' and last['receipt_sha256'] == digest and
            last['label'] == 'q2-ds4-walk-promessi-r1', 'Registry release differs')
    require(not list(Path('/sys/class/kfd/kfd/proc').glob('*')), 'KFD client remains')
    require(not list(Path('/sys/kernel/iommu_groups').glob('*')), 'IOMMU groups changed')
    require('amd_iommu=off' in Path('/proc/cmdline').read_text().split(), 'IOMMU boot mode changed')

    held = []
    try:
        for row in [release['core_cpu_lease'], *release['leases']]:
            fd = os.open(row['path'], os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
            held.append(fd)
            stat = os.fstat(fd)
            require((stat.st_dev, stat.st_ino) == (row['device'], row['inode']),
                    'Original lease identity changed')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

        identities = {row['pid']: row['start_ticks'] for row in release['retired_identities']}
        groups = set(release['retired_groups'])
        for process in Path('/proc').glob('[0-9]*'):
            try:
                fields = (process / 'stat').read_text().rsplit(')', 1)[1].split()
            except FileNotFoundError:
                continue
            pid, group, start = int(process.name), int(fields[2]), int(fields[19])
            require(pid not in identities or identities[pid] not in (None, start),
                    'Recorded process remains live')
            require(group not in groups, 'Owned process group remains live')

        for row in release['models']:
            stat = Path(row['path']).stat()
            require((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns,
                     stat.st_ctime_ns) == tuple(row[key] for key in
                     ('device', 'inode', 'bytes', 'mtime_ns', 'ctime_ns')),
                    'Reference model changed')
        if release.get('glm_model_path'):
            stat = Path(release['glm_model_path']).stat()
            require(all(getattr(stat, key) == value for key, value in
                        release['glm_model_stats'].items()), 'GLM model changed')
        receipt = dict(schema='synapse-lie.q2-ds4-walk-strong-closure.v1',
                       at=dt.datetime.now(dt.timezone.utc).isoformat(),
                       release_sha256=digest, boot_id=BOOT,
                       retired_identities=len(identities), retired_groups=len(groups),
                       kfd_empty=True, original_five_leases_free=True,
                       reference_model_stats_unchanged=True,
                       glm_model_stats_unchanged=True, iommu_groups=0,
                       gpu_reserved=False)
        with (HERE / 'strong-closure.json').open('x') as stream:
            json.dump(receipt, stream, indent=2)
            stream.write('\n')
        print(json.dumps(receipt))
    finally:
        for fd in reversed(held):
            os.close(fd)


if __name__ == '__main__':
    main()
