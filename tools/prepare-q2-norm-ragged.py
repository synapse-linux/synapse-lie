#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Match the paired HC norm producer to its existing bounded library consumer."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/executor.cpp'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parent_path = ROOT/'config/q2-iq2-signs-ordered-asm-source.json'
    parent = json.loads(parent_path.read_text())
    base = ROOT/parent['candidate']
    files = {str(p.relative_to(base)): sha(p) for p in base.rglob('*') if p.is_file()}
    if files != parent['files']:
        raise ValueError('Measured ordered IQ2 provider changed')
    out = ROOT/'.deps/gufo-q2-norm-ragged'
    manifest = ROOT/'config/q2-norm-ragged-source.json'
    patch = ROOT/'experiments/q2-norm-ragged.patch'
    if any(p.exists() for p in (out, manifest, patch)):
        raise ValueError('Refusing to overwrite retained source')
    old = (base/REL).read_text()
    anchor = '!wide_mixer_ && n_tokens == 2048 && n_tokens <= options_.max_batch &&'
    if old.count(anchor) != 1:
        raise ValueError('Paired norm dispatch changed')
    new = old.replace(anchor,
        '!wide_mixer_ && n_tokens >= 96 && n_tokens <= 2048 &&\n'
        '      n_tokens <= options_.max_batch &&')
    new = subprocess.run(['clang-format', '-style=file',
                          '--assume-filename='+str(base/REL)], input=new,
                         capture_output=True, text=True, check=True).stdout
    consumer = (base/REL).with_name('blaslt.cpp').read_text()
    if consumer.count('m == 320 && n >= 96 && n <= 2048 && k == 10240') != 2:
        raise ValueError('Library consumer no longer covers this interval')
    shutil.copytree(base, out)
    (out/REL).write_text(new)
    actual = {str(p.relative_to(out)): sha(p) for p in out.rglob('*') if p.is_file()}
    changed = sorted(k for k in actual if actual[k] != files[k])
    if actual.keys() != files.keys() or changed != [REL]:
        raise ValueError('Unexpected source delta')
    patch.write_text(''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                     fromfile='a/'+REL, tofile='b/'+REL)))
    report = dict(schema='synapse-lie.q2-norm-ragged-source.v1',
        base=parent['candidate'], candidate=str(out.relative_to(ROOT)), files=actual,
        parent_manifest_sha256=sha(parent_path), patch_sha256=sha(patch),
        changed_files=changed, unchanged_files=len(files)-1,
        mechanism='Emit the existing F16 norm copy together with F32 for 96..2048 rows, matching the existing HC library consumer. Avoid its separate narrowing pass.',
        unchanged='Arithmetic kernels, BLAS algorithm, IQ2 decode, expert dispatch, PLE, allocation and half-buffer invalidation/publication are byte-identical.',
        risk='Extra producer stores can offset the removed narrowing pass; wider dispatch needs full-model buffer-lifetime and output checks.',
        validation='Start with complete paired/unpaired component cycles at the retained canonical d0 size 2040 and aligned control 2048. One native canonical point follows only after a useful component result; no full curve admitted.',
        runtime_validated=False, promoted=False, goal_met=False)
    manifest.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('candidate','changed_files','unchanged_files')}))


if __name__ == '__main__':
    main()
