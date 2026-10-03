#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare a component-only vector-memory F32-to-F16 conversion experiment."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-scaled-input'
OUT = ROOT / '.deps/gufo-q2-bench-narrow-vector'
DIR = Path('src/models/qwen38_flash_next/kernels/rocm')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def insert_once(source, anchor, insertion):
    if source.count(anchor) != 1:
        raise ValueError('Unexpected source anchor: ' + anchor)
    return source.replace(anchor, insertion + anchor)


def main():
    identity = json.loads((ROOT / 'config/q2-scaled-input-source.json').read_text())
    for row in identity['changed_files']:
        if digest(BASE / row['path']) != row['sha256']:
            raise ValueError('Scaled source changed: ' + row['path'])
    edits = {
        DIR / 'kernels.hip.cpp': insert_once(
            (BASE / DIR / 'kernels.hip.cpp').read_text(),
            'std::size_t Q8TiledBytes(std::size_t batch, std::size_t k) {',
            '#include "q2_narrow_vector.inc"\n\n'),
        DIR / 'kernels.hpp': insert_once(
            (BASE / DIR / 'kernels.hpp').read_text(),
            '/// W8A8 route for wide batches over Q8_0 weights:',
            '// Experimental component entry; no model dispatch change.\n'
            'bool NarrowF16Vector(const float*, __half*, std::size_t, hipStream_t);\n\n'),
        DIR / 'q2_narrow_vector.inc': (ROOT / 'experiments/q2_narrow_vector.inc').read_text(),
    }
    shutil.copytree(BASE, OUT)  # Immutable prior experiments are never overwritten.
    for name, content in edits.items():
        (OUT / name).write_text(content)
        subprocess.run(['clang-format', '-i', str(OUT / name)], check=True)
    patch = ROOT / 'experiments/q2-narrow-vector.patch'
    fragments = []
    for name in sorted(edits):
        original = (BASE / name).read_text() if (BASE / name).exists() else ''
        fragments += difflib.unified_diff(
            original.splitlines(True), (OUT / name).read_text().splitlines(True),
            fromfile='a/' + str(name) if original else '/dev/null',
            tofile='b/' + str(name))
    patch.write_text(''.join(fragments))
    base_files = {str(p.relative_to(BASE)): digest(p)
                  for p in sorted(BASE.rglob('*')) if p.is_file()}
    candidate_files = {str(p.relative_to(OUT)): digest(p)
                       for p in sorted(OUT.rglob('*')) if p.is_file()}
    changed = [name for name in candidate_files
               if candidate_files[name] != base_files.get(name)]
    if set(changed) != {str(p) for p in edits}:
        raise ValueError('Unexpected source differences')
    result = {
        'scope': 'Component-only memory-access experiment; no GPU or model result',
        'pin': identity['pin'], 'base': str(BASE.relative_to(ROOT)),
        'candidate': str(OUT.relative_to(ROOT)), 'base_files': base_files,
        'source_files': len(candidate_files),
        'changed_files': [{'path': name, 'base_sha256': base_files.get(name),
                           'sha256': candidate_files[name]} for name in changed],
        'patch_sha256': digest(patch), 'model_dispatch_changed': False,
        'tensor_allocation_bytes_added': 0,
        'contract': 'Same individual __half(float) conversions; float4 reads and uint2 stores; scalar tail and alignment fallback',
        'limits': 'Require full bitwise replay, independent IEEE checks and complete consumer timing; existing scaled-input rejection remains.',
    }
    (ROOT / 'config/q2-narrow-vector-source.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'base_files'}))


if __name__ == '__main__':
    main()
