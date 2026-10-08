#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Create persistent, boot-qualified coordination metadata; never use the GPU.

The bootstrap can record a busy GPU. It never constitutes benchmark admission.
Existing legacy lease files are opened without creation or content changes.
"""

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path

ROOT = Path('/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run')
BOOT = Path('/proc/sys/kernel/random/boot_id')
EXPECTED_BOOT = '8b9cbb46-c7d4-47c3-b5cc-32e1fdad0653'
INTERRUPTED = ROOT / 'q2-decode-down-rows-native128-r1'
PRIOR = ROOT / 'q2-decode-down-rows-component-r1/release.json'
EPOCH = ROOT / 'gpu-coordination/epochs' / EXPECTED_BOOT


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write_new(path, data):
    with path.open('x') as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def rebind(row, stat, model=False):
    keys = ('inode', 'bytes', 'mtime_ns', 'ctime_ns') if model else ('inode',)
    current = dict(device=stat.st_dev, inode=stat.st_ino)
    if model:
        current.update(bytes=stat.st_size, mtime_ns=stat.st_mtime_ns,
                       ctime_ns=stat.st_ctime_ns)
    if any(current[key] != row[key] for key in keys):
        raise ValueError('Persistent identity changed: ' + row['path'])
    return dict(path=row['path'], **current)


@contextlib.contextmanager
def hold(rows):
    held = []
    try:
        for row in rows:
            fd = os.open(row['path'], os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
            held.append(fd)
            stat = os.fstat(fd)
            if (stat.st_dev, stat.st_ino) != (row['device'], row['inode']):
                raise ValueError('Lease changed since observation')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        for fd in reversed(held):
            os.close(fd)


def create():
    if BOOT.read_text().strip() != EXPECTED_BOOT:
        raise ValueError('Unexpected boot')
    if sha(PRIOR) != '9954b78f2c76846bed0074ba73cf02ca1898429efd9916bb751d6db2bbdc4e25':
        raise ValueError('Historical release changed')
    receipt_path = INTERRUPTED / 'interrupted-receipt.json'
    if sha(receipt_path) != '858d0f6c1e3d26811bcdfc85206dd7ab8070a78d0a5c072c53699d747868f037':
        raise ValueError('Interrupted receipt changed')
    receipt, prior = read(receipt_path), read(PRIOR)
    if receipt['current_boot_id'] != EXPECTED_BOOT or receipt['state'] != 'ABORTED_HOST_REBOOT':
        raise ValueError('Interrupted receipt is not this reboot')
    old_leases = [prior['core_cpu_lease'], *prior['leases']]
    if old_leases[-1]['path'] != '/tmp/synapse-lie-ds4-gpu.lock':
        raise ValueError('Unexpected legacy lease order')
    rows = [rebind(row, Path(row['path']).stat()) for row in old_leases[:-1]]
    models = [rebind(row, Path(row['path']).stat(), True) for row in prior['models']]
    with hold(rows):
        EPOCH.mkdir(parents=True, exist_ok=False)
        lock = EPOCH / 'gpu.lock'
        with lock.open('x'):
            pass
        stat = lock.stat()
        new_lock = dict(path=str(lock), device=stat.st_dev, inode=stat.st_ino)
        with hold([new_lock]):
            if BOOT.read_text().strip() != EXPECTED_BOOT:
                raise ValueError('Boot changed during bootstrap')
            clients = [p.name for p in Path('/sys/class/kfd/kfd/proc').glob('*')]
            baseline = dict(
                schema='synapse-lie.gpu-epoch-baseline.v1',
                state='EPOCH_BOOTSTRAP_NOT_ADMITTED',
                at=dt.datetime.now(dt.timezone.utc).isoformat(),
                boot_id=EXPECTED_BOOT, previous_boot_id=receipt['prior_boot_id'],
                interrupted_receipt=str(receipt_path), interrupted_sha256=sha(receipt_path),
                historical_release=str(PRIOR), historical_release_sha256=sha(PRIOR),
                historical_retired_identities=len(prior['retired_identities']),
                historical_retired_groups=len(prior['retired_groups']),
                retired_identities=[], retired_groups=[],
                retirement_scope='Current boot only; prior boot inventories remain in historical release.',
                core_cpu_lease=rows[0], leases=[*rows[1:], new_lock], models=models,
                mount_rebind='Persistent inode/size/mtime/ctime retained; st_dev observed afresh after reboot.',
                kfd_clients=clients, kfd_empty=not clients, gpu_reserved=False,
                new_gpu_admission=False, remote_cleanup=False)
            path = EPOCH / 'baseline.json'
            write_new(path, baseline)
            event = dict(event='epoch_bootstrap', owner='synapse-lie-q2',
                         at=baseline['at'], boot_id=EXPECTED_BOOT,
                         receipt=str(path), receipt_sha256=sha(path),
                         state=baseline['state'])
            with (EPOCH / 'runs.jsonl').open('x') as stream:
                stream.write(json.dumps(event) + '\n')
                stream.flush()
                os.fsync(stream.fileno())
    print(json.dumps(dict(baseline=str(path), sha256=sha(path),
                         kfd_clients=clients, gpu_admitted=False)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['create'])
    parser.parse_args()
    create()
