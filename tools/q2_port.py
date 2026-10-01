#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Materialize a checked, private Q2 host-compatibility source variant. No build/GPU.
The pristine source and all qualified archives stay unchanged. Not runtime-ready.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PIN = 'f783fedb9bea2ec7de941f6da4e02f4a4596b29e'
RECIPE = ROOT / 'adapters/gufo-q2/host-edits.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def transform(data, edits):
    """All exact replacements refer to the original bytes; no cascading/fuzzy edit."""
    spans = []
    for edit in edits:
        old, new = edit['old'].encode(), edit['new'].encode()
        if not old or data.count(old) != 1:
            raise ValueError('Q2 edit is not unique in pinned input')
        start = data.index(old)
        spans.append((start, start + len(old), new))
    spans.sort()
    if any(b[0] < a[1] for a, b in zip(spans, spans[1:])):
        raise ValueError('overlapping Q2 edits')
    out, cursor = bytearray(), 0
    for start, end, new in spans:
        out.extend(data[cursor:start]); out.extend(new); cursor = end
    out.extend(data[cursor:])
    return bytes(out)


def checked_variant(manifest, recipe, load):
    if recipe['schema'] != 'synapse-lie.q2-host-edits.v1' or recipe['upstream_pin'] != PIN:
        raise ValueError('Q2 recipe identity mismatch')
    if recipe['runtime_link_allowed'] is not False:
        raise ValueError('Q2 host recipe cannot authorize runtime linkage')
    if manifest['commit'] != PIN or manifest['repository'] != 'https://github.com/gufo-org/gufo':
        raise ValueError('pristine manifest identity mismatch')
    files, changes = manifest['files'], recipe['files']
    if not changes or not set(changes).issubset(files):
        raise ValueError('Q2 recipe targets unknown source')
    result = {}
    for name, expected in files.items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts or str(path) != name:
            raise ValueError('invalid source member path')
        data = load(name)
        if sha(data) != expected:
            raise ValueError('pristine source drift: ' + name)
        if name in changes:
            change = changes[name]
            if change['before_sha256'] != expected:
                raise ValueError('Q2 edit base mismatch: ' + name)
            data = transform(data, change['edits'])
            if sha(data) != change['after_sha256']:
                raise ValueError('Q2 edit result mismatch: ' + name)
        result[name] = data
    return result


def prepare(source, destination):
    manifest_bytes = (ROOT / 'third_party/gufo-source.json').read_bytes()
    recipe_bytes = RECIPE.read_bytes()
    recipe = json.loads(recipe_bytes)
    source = Path(source)
    def load(name):
        p = source / name
        # Refuse symlink parents too, rather than following a substituted tree.
        if any(x.is_symlink() for x in [p, *p.parents]) or not p.is_file():
            raise ValueError('nonregular pristine source: ' + name)
        return p.read_bytes()
    data = checked_variant(json.loads(manifest_bytes), recipe, load)
    destination = Path(destination)
    if any(x.is_symlink() for x in [destination, *destination.parents]):
        raise ValueError('symlink output path')
    destination.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for name, content in data.items():
        p = destination / name
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('xb') as f:
            f.write(content)
        hashes[name] = sha(content)
        if sha(p.read_bytes()) != hashes[name]:
            raise ValueError('materialized source drift: ' + name)
    receipt = {'schema': 'synapse-lie.q2-host-source.v1', 'upstream_pin': PIN,
               'state': 'HOST_COMPATIBILITY_SOURCE_ONLY_NOT_GPU_READY',
               'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'pristine_manifest_sha256': sha(manifest_bytes), 'recipe_sha256': sha(recipe_bytes),
               'preparer_sha256': sha(Path(__file__).read_bytes()),
               'runtime_link_allowed': False, 'gpu_execution': False,
               'modified_files': sorted(recipe['files']), 'files': hashes}
    with (destination / 'LIE-Q2-SOURCE.json').open('x') as f:
        f.write(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    label = sys.argv[1] if len(sys.argv) == 2 else ''
    if not re.fullmatch(r'[a-z0-9-]{1,64}', label):
        raise SystemExit('Usage: q2_port.py EXCLUSIVE-LABEL (host source preparation only)')
    if os.environ.get('SSH_CONNECTION'):
        raise SystemExit('Q2 source preparation is editing-host-only')
    build = ROOT / 'build' / label
    if any(x.is_symlink() for x in [build, *build.parents]):
        raise SystemExit('Q2 output path contains symlink')
    build.mkdir(exist_ok=False)  # Reserve the whole label, never reuse a partial run.
    r = prepare(ROOT / '.deps/gufo-f783fedb', build / 'source')
    print(json.dumps({k: v for k, v in r.items() if k != 'files'}, indent=2))


if __name__ == '__main__':
    main()
