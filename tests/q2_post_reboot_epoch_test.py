#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU checks for boot-time stat rebinding and partial lease acquisition."""

import importlib.util
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'epoch', ROOT / 'tools/q2-post-reboot-epoch.py')
epoch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(epoch)


def rejected(fn):
    try:
        fn()
    except (OSError, ValueError):
        return
    raise AssertionError('Expected rejection')


def acquire(rows):
    with epoch.hold(rows):
        pass


def main():
    model = dict(path='/unopened-model', device=52, inode=123, bytes=456,
                 mtime_ns=789, ctime_ns=987)
    stat = SimpleNamespace(st_dev=54, st_ino=123, st_size=456,
                           st_mtime_ns=789, st_ctime_ns=987)
    rebound = epoch.rebind(model, stat, True)
    assert rebound == dict(model, device=54)
    for key in ('inode', 'bytes', 'mtime_ns', 'ctime_ns'):
        changed = dict(model)
        changed[key] += 1
        rejected(lambda: epoch.rebind(changed, stat, True))
    with tempfile.TemporaryDirectory(prefix='lie-epoch-cpu-') as name:
        base = Path(name)
        rows = []
        for label in ('first', 'second'):
            path = base / label
            path.write_bytes(b'preserve lease content')
            s = path.stat()
            rows.append(dict(path=str(path), device=s.st_dev, inode=s.st_ino))
        acquire(rows)
        # Failure on the second lease must release the first one too.
        with epoch.hold(rows[1:]):
            rejected(lambda: acquire(rows))
            acquire(rows[:1])
        acquire(rows)
        changed = [rows[0], dict(rows[1], inode=rows[1]['inode'] + 1)]
        rejected(lambda: acquire(changed))
        acquire(rows)
        alias = base / 'alias'
        alias.symlink_to(rows[0]['path'])
        rejected(lambda: acquire([dict(rows[0], path=str(alias))]))
        assert all(Path(r['path']).read_bytes() == b'preserve lease content' for r in rows)
    print('Epoch CPU checks pass: mount rebinding, four identity rejections, '
          'partial acquisition cleanup, contention, stale inode, symlink and content preservation.')


if __name__ == '__main__':
    main()
