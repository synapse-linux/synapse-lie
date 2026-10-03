#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Extend only the experimental HC-down library dispatch to bounded ragged rows."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-library-norm-bound'
OUT = ROOT / '.deps/gufo-q2-bench-hc-library-ragged'
REL = 'src/models/qwen38_flash_next/kernels/rocm/blaslt.cpp'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    expected = json.loads((ROOT/'config/q2-decode-baseline-static.json').read_text())['source_file_hashes']
    actual = {str(p.relative_to(BASE)): sha(p) for p in BASE.rglob('*') if p.is_file()}
    if actual != expected:
        raise ValueError('Measured baseline source differs')
    patch = ROOT/'experiments/q2-hc-library-ragged.patch'
    manifest = ROOT/'config/q2-hc-library-ragged-source.json'
    if OUT.exists() or patch.exists() or manifest.exists():
        raise ValueError('Refusing to overwrite a prepared experiment')
    old = (BASE/REL).read_text()
    predicate = 'm == 320 && n == 2048 && k == 10240'
    if old.count(predicate) != 2:
        raise ValueError('Preferred algorithm or library dispatch changed')
    new = old.replace(predicate, 'm == 320 && n >= 96 && n <= 2048 && k == 10240')
    new = subprocess.run(['clang-format', '-style=file', '--assume-filename='+str(BASE/REL)],
                         input=new, capture_output=True, text=True, check=True).stdout
    shutil.copytree(BASE, OUT)
    (OUT/REL).write_text(new)
    patch.write_text(''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                     fromfile='a/'+REL, tofile='b/'+REL)))
    current = {str(p.relative_to(OUT)): sha(p) for p in OUT.rglob('*') if p.is_file()}
    changed = sorted(k for k in current if current[k] != expected[k])
    if changed != [REL]:
        raise ValueError('Unexpected source change')
    result = dict(scope='Prepared component experiment, no runtime or model acceptance',
        source_pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
        base=str(BASE.relative_to(ROOT)), candidate=str(OUT.relative_to(ROOT)),
        source_file_hashes=current, parent_sha256=expected[REL], changed_files=changed,
        unchanged_files=len(current)-1, patch_sha256=sha(patch),
        contract='Only F16 HC-down M320/K10240 library dispatch and preferred algorithm predicate broaden from n2048 to 96<=n<=2048. Algorithm 7526 must be supported with zero workspace; refusal remains explicit. Executor, producers, kernels, allocations and scalar decode unchanged.',
        control='Native HC down with the same original norm and narrowing; n2048 is a library-control shape, not a new model speedup.',
        paired_norm='Still restricted to n2048; not broadened in this experiment',
        inherited_numerical_rejection=True, numerical_limits_changed=False,
        numerical_pass=None, performance_pass=None, promoted=False, goal_met=False)
    manifest.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(changed_files=changed, unchanged_files=len(current)-1)))


if __name__ == '__main__':
    main()
