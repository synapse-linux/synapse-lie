#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Create coordination metadata after the authorized IOMMU reboot; no GPU run."""
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path

ROOT = Path('/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run')
BOOT = Path('/proc/sys/kernel/random/boot_id')
TRANSITION = ROOT / 'q2-counting-iommu-boot-r1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def write_new(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def rebind(row, model=False):
    stat = Path(row['path']).stat()
    keys = ('inode', 'bytes', 'mtime_ns', 'ctime_ns') if model else ('inode',)
    current = dict(path=row['path'], device=stat.st_dev, inode=stat.st_ino)
    if model:
        current.update(bytes=stat.st_size, mtime_ns=stat.st_mtime_ns, ctime_ns=stat.st_ctime_ns)
    require(all(current[key] == row[key] for key in keys), 'Persistent identity changed: ' + row['path'])
    return current


@contextlib.contextmanager
def hold(rows):
    held = []
    try:
        for row in rows:
            fd = os.open(row['path'], os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
            held.append(fd)
            stat = os.fstat(fd)
            require((stat.st_dev, stat.st_ino) == (row['device'], row['inode']), 'Lease changed')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        for fd in reversed(held):
            os.close(fd)


def main():
    boot = BOOT.read_text().strip()
    plan = json.loads((TRANSITION / 'plan.json').read_text())
    restored = json.loads((TRANSITION / 'restore.json').read_text())
    require(sha(Path(__file__)) == plan['epoch_helper_sha256'], 'Epoch helper changed')
    require(boot == restored['boot_id'] and boot != plan['before_boot_id'] and
            restored['exact_original_restored'], 'Authorized boot transition incomplete')
    require('amd_iommu=off' in Path('/proc/cmdline').read_text().split() and
            not list(Path('/sys/kernel/iommu_groups').glob('*')), 'IOMMU is not disabled')
    prior_path = ROOT / plan['before_window'] / 'release.json'
    require(sha(prior_path) == plan['before_release_sha256'], 'Prior release changed')
    prior = json.loads(prior_path.read_text())
    require(prior['boot_id'] == plan['before_boot_id'] and not prior['gpu_reserved'],
            'Prior GPU work was not released')
    old_rows = [prior['core_cpu_lease'], *prior['leases']]
    require(len(old_rows) == 5 and old_rows[-1]['path'].endswith('/'+plan['before_boot_id']+'/gpu.lock'),
            'Unexpected original lease order')
    rows = [rebind(row) for row in old_rows[:-1]]
    models = [rebind(row, True) for row in prior['models']]
    glm_stats = dict(prior.get('glm_model_stats', {}))
    if prior.get('glm_model_path'):
        stat = Path(prior['glm_model_path']).stat()
        require(all(getattr(stat, key) == value for key, value in glm_stats.items()
                    if key != 'st_dev'), 'GLM model changed across reboot')
        glm_stats['st_dev'] = stat.st_dev
    epoch = ROOT / 'gpu-coordination/epochs' / boot
    with hold(rows):
        epoch.mkdir(exist_ok=False)
        lock = epoch / 'gpu.lock'
        with lock.open('x'):
            pass
        stat = lock.stat()
        new_lock = dict(path=str(lock), device=stat.st_dev, inode=stat.st_ino)
        with hold([new_lock]):
            require(BOOT.read_text().strip() == boot, 'Boot changed during metadata setup')
            clients = [p.name for p in Path('/sys/class/kfd/kfd/proc').glob('*')]
            baseline = dict(schema='synapse-lie.gpu-epoch-baseline.v1',
                state='EPOCH_BOOTSTRAP_NOT_ADMITTED', boot_id=boot,
                at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                previous_boot_id=prior['boot_id'],
                boot_transition_plan_sha256=sha(TRANSITION / 'plan.json'),
                boot_restore_sha256=sha(TRANSITION / 'restore.json'),
                historical_release=str(prior_path), historical_release_sha256=sha(prior_path),
                historical_retired_identities=len(prior['retired_identities']),
                retired_identities=[], retired_groups=[],
                retirement_scope='Current boot only; prior process identities retained in historical release.',
                core_cpu_lease=rows[0], leases=[*rows[1:], new_lock], models=models,
                glm_model_path=prior.get('glm_model_path'), glm_model_stats=glm_stats,
                kfd_clients=clients, kfd_empty=not clients, gpu_reserved=False,
                new_gpu_admission=False, remote_cleanup=False)
            path = epoch / 'baseline.json'
            write_new(path, baseline)
            with (epoch / 'runs.jsonl').open('x') as stream:
                stream.write(json.dumps(dict(event='epoch_bootstrap', owner='synapse-lie-q2',
                    boot_id=boot, at=baseline['at'], receipt=str(path),
                    receipt_sha256=sha(path), state=baseline['state']))+'\n')
                stream.flush()
                os.fsync(stream.fileno())
    print(json.dumps(dict(path=str(path), sha256=sha(path), kfd_clients=clients,
                         gpu_admitted=False)), flush=True)


if __name__ == '__main__':
    main()
