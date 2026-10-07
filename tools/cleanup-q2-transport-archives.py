#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Remove local transport archives only after verifying every extracted member.

No remote access, extraction, symlink traversal, source-tree deletion or model
access. One fsynced journal entry records content hashes before each unlink.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]


def identity(path):
    s = path.lstat()
    return (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def digest(stream):
    h = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        h.update(chunk)
    return h.hexdigest()


def local_path(base, name):
    rel = PurePosixPath(name)
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('Archive path is not local: ' + name)
    path = base.joinpath(*rel.parts)
    for parent in (path, *path.parents):
        if parent == ROOT:
            break
        if parent.is_symlink():
            raise ValueError('Symlink in extracted path: ' + str(path))
    path.relative_to(ROOT)
    return path


def verify(archive):
    before = identity(archive)
    if not stat.S_ISREG(before[2]):
        raise ValueError('Archive is not a regular file')
    base = archive.parent
    if archive.name == 'output-arrays.tar.gz':
        base /= 'output-arrays'
    checked, total = [], 0
    with tarfile.open(archive, 'r|gz') as stream:
        for member in stream:
            path = local_path(base, member.name)
            if member.isdir():
                if not path.is_dir():
                    raise ValueError('Missing extracted directory: ' + str(path))
                continue
            if not member.isfile():
                raise ValueError('Retain archive with links or special members')
            before_file = identity(path)
            if not stat.S_ISREG(before_file[2]) or before_file[3] != member.size:
                raise ValueError('Extracted type/size differs: ' + str(path))
            with stream.extractfile(member) as data:
                archive_hash = digest(data)
            with path.open('rb') as data:
                local_hash = digest(data)
            if archive_hash != local_hash or identity(path) != before_file:
                raise ValueError('Extracted bytes changed: ' + str(path))
            checked.append(dict(path=str(path.relative_to(ROOT)),
                                bytes=member.size, sha256=archive_hash))
            total += member.size
    if not checked:
        raise ValueError('No regular payload verified')
    with archive.open('rb') as stream:
        archive_hash = digest(stream)
    if identity(archive) != before:
        raise ValueError('Archive changed during verification')
    return dict(path=str(archive.relative_to(ROOT)), bytes=before[3],
                sha256=archive_hash, members=checked, payload_bytes=total), before


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--journal', type=Path, required=True)
    args = parser.parse_args()
    journal = args.journal.resolve()
    journal.relative_to(ROOT / 'evidence/worktree-cleanup-20261007')
    journal.parent.mkdir(parents=True, exist_ok=True)
    names = {'results.tar.gz', 'output-arrays.tar.gz', 'collection.tar.gz'}
    archives = sorted((p for p in (ROOT/'evidence').rglob('*.tar.gz')
                       if p.name in names), key=lambda p: p.stat().st_size, reverse=True)
    removed = saved = skipped = 0
    with journal.open('x') as log:
        def record(row):
            log.write(json.dumps(row, separators=(',', ':'))+'\n')
            log.flush()
            os.fsync(log.fileno())
        for archive in archives:
            start = time.time()
            try:
                report, before = verify(archive)
                record(dict(event='verified', **report))
                if args.apply:
                    if identity(archive) != before:
                        raise ValueError('Archive changed before deletion')
                    archive.unlink()
                    removed += 1
                    saved += report['bytes']
                    record(dict(event='removed_duplicate_archive', path=report['path'],
                                bytes=report['bytes'], sha256=report['sha256']))
                print(json.dumps(dict(path=report['path'], verified=True,
                    removed=args.apply, bytes=report['bytes'], seconds=time.time()-start)), flush=True)
            except (OSError, ValueError, tarfile.TarError) as error:
                skipped += 1
                record(dict(event='retained', path=str(archive.relative_to(ROOT)), reason=str(error)))
                print(json.dumps(dict(path=str(archive.relative_to(ROOT)), retained=True,
                                      reason=str(error))), flush=True)
        record(dict(event='complete', removed=removed, bytes=saved, retained=skipped))
    print(json.dumps(dict(removed=removed, bytes=saved, retained=skipped)), flush=True)


if __name__ == '__main__':
    main()
