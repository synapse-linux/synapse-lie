#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Restore a compacted source tree or diagnostic file from its verified copy."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_path(name):
    rel = PurePosixPath(name)
    if rel.is_absolute() or '..' in rel.parts or not rel.parts:
        raise ValueError('Expected a repository-relative path')
    path = ROOT.joinpath(*rel.parts)
    for p in (path, *path.parents):
        if p == ROOT:
            break
        if p.is_symlink():
            raise ValueError('Refusing a symlink path')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', help='Original path listed in the cleanup index')
    args = parser.parse_args()
    source_index = json.loads((ROOT/'config/q2-retained-source-index.json').read_text())
    file_index_path = ROOT/'config/q2-compacted-diagnostics-index.json'
    files = json.loads(file_index_path.read_text()) if file_index_path.exists() else {}
    target = safe_path(args.path)
    if target.exists():
        raise ValueError('Target already exists; existing work will not be overwritten')
    if args.path in source_index:
        entry = source_index[args.path]
        archive = safe_path(entry['archive'])
        if sha(archive) != entry['archive_sha256']:
            raise ValueError('Source capsule digest differs')
        target.mkdir(parents=True)
        observed = []
        with tarfile.open(archive, 'r|gz') as stream:
            for member in stream:
                if not member.name.startswith('source/'):
                    continue
                name = member.name[len('source/'):]
                if not name:
                    continue
                path = safe_path(str(PurePosixPath(args.path)/name))
                if not path.is_relative_to(target):
                    raise ValueError('Archive member escapes source tree')
                if member.isdir():
                    path.mkdir(parents=True, exist_ok=True)
                    continue
                if not member.isfile():
                    raise ValueError('Unsupported archive member')
                path.parent.mkdir(parents=True, exist_ok=True)
                with stream.extractfile(member) as inp, path.open('xb') as out:
                    shutil.copyfileobj(inp, out, 1024*1024)
                path.chmod(member.mode & 0o777)
                os.utime(path, (member.mtime, member.mtime))
                observed.append((name, path.stat().st_size, sha(path), member.mode & 0o777))
        fingerprint = hashlib.sha256(json.dumps(sorted(observed),
                    separators=(',', ':')).encode()).hexdigest()
        if fingerprint != entry['fingerprint']:
            raise ValueError('Restored source fingerprint differs; keep for diagnosis')
    elif args.path in files:
        entry = files[args.path]
        packed = safe_path(entry['compressed_path'])
        if sha(packed) != entry['compressed_sha256']:
            raise ValueError('Compressed diagnostic digest differs')
        target.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(packed, 'rb') as inp, target.open('xb') as out:
            shutil.copyfileobj(inp, out, 1024*1024)
        if sha(target) != entry['sha256']:
            raise ValueError('Restored diagnostic digest differs; keep for diagnosis')
        target.chmod(entry['mode'])
        os.utime(target, ns=(entry['mtime_ns'], entry['mtime_ns']))
    else:
        raise ValueError('Path is not listed in the cleanup index')
    print('Restored and verified: ' + args.path)


if __name__ == '__main__':
    main()
