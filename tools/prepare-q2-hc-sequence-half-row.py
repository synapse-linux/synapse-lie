#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Measure the exact half-row geometry after both HC norm producers."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-sequence'
OUT = ROOT / '.deps/gufo-q2-bench-hc-sequence-half-row'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')


def main():
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if sha(BASE / REL) != 'b832e97c62d682874acca9dad06adaa10787b77c823debe634694b9516953194':
        raise ValueError('Sequence source differs from measured component')
    shutil.copytree(BASE, OUT)
    inputs = [ROOT / ('experiments/q2-hc-' + name + '.patch')
              for name in ('full-row', 'half-row')]
    for patch in inputs:
        subprocess.run(['patch', '--batch', '--fuzz=0', '--no-backup-if-mismatch',
                        '-p1', '-i', str(patch)], cwd=OUT, check=True)
    subprocess.run(['clang-format', '-i', str(OUT / REL)], check=True)
    changed = [str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file()
               and p.read_bytes() != (OUT / p.relative_to(BASE)).read_bytes()]
    if changed != [str(REL)]:
        raise ValueError('Unexpected changed inventory')
    patch = ROOT / 'experiments/q2-hc-sequence-half-row.patch'
    patch.write_text(''.join(difflib.unified_diff(
        (BASE / REL).read_text().splitlines(True), (OUT / REL).read_text().splitlines(True),
        fromfile='a/' + str(REL), tofile='b/' + str(REL))))
    report = {'scope': 'Isolated half-row sequence; runtime benefit unproven',
              'base': str(BASE.relative_to(ROOT)), 'output': str(OUT.relative_to(ROOT)),
              'official_gufo_pin': 'f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
              'input_patches': {str(p.relative_to(ROOT)): sha(p) for p in inputs},
              'changed_files': changed, 'base_sha256': sha(BASE / REL),
              'candidate_sha256': sha(OUT / REL), 'patch_sha256': sha(patch)}
    (ROOT / 'config/q2-hc-sequence-half-row-source.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
