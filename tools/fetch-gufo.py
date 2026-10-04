#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Explicit source-only fetch. No configure/build, package install or model download."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PIN = 'f783fedb9bea2ec7de941f6da4e02f4a4596b29e'
SHA = '4b61a3f23e5ab51f7c95d6a7b6d2d82c8f7976e39f9566196f75323ab5eb2110'
URL = f'https://api.github.com/repos/gufo-org/gufo/tarball/{PIN}'


def main():
    destination = ROOT / '.deps' / ('gufo-' + PIN[:8])
    if destination.exists():
        raise SystemExit('Destination exists; refusing replacement')
    with urllib.request.urlopen(URL, timeout=60) as response:
        data = response.read(16000001)
    if len(data) > 16000000 or hashlib.sha256(data).hexdigest() != SHA:
        failure = {'url': URL, 'expected_sha256': SHA,
                   'actual_sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
        with (ROOT / 'evidence/fetch-refusal.jsonl').open('a') as f:
            f.write(json.dumps(failure) + '\n')
        raise SystemExit('Pinned source archive identity mismatch; refusal recorded')
    receipt = {'repository': 'https://github.com/gufo-org/gufo', 'commit': PIN,
               'url': URL, 'archive_sha256': SHA, 'archive_bytes': len(data),
               'license': 'MIT; components retain their notices', 'files': {}, 'omitted_editor_symlinks': []}
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        members = []
        for member in archive:
            parts = PurePosixPath(member.name).parts
            if not parts or parts[0] not in ('gufo-' + PIN, 'gufo-org-gufo-' + PIN[:7]) or '..' in parts:
                raise ValueError('unsafe source member')
            rel = PurePosixPath(*parts[1:])
            if member.isdir(): continue
            if member.issym() and str(rel) in ('.claude/skills', 'CLAUDE.md'):
                receipt['omitted_editor_symlinks'].append({'path': str(rel), 'target': member.linkname}); continue
            if not member.isfile() or member.size > 16000000 or str(rel) in receipt['files']:
                raise ValueError('unsupported/duplicate member')
            raw = archive.extractfile(member).read()
            receipt['files'][str(rel)] = hashlib.sha256(raw).hexdigest()
            members.append((rel, raw))
        destination.mkdir(parents=True)
        for rel, raw in members:
            path = destination / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as f: f.write(raw)
    (ROOT / 'third_party' / 'gufo-source.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(f'Pinned source extracted: {destination}; {len(members)} regular files')


if __name__ == '__main__': main()
