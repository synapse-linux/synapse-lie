#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Retain packed IQ2 signs while fixing the observed reference scale rounding."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/mmq/vecdotq.hpp'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parent = json.loads((ROOT/'config/q2-iq2-signs-source.json').read_text())
    base = ROOT/parent['candidate']
    actual = {str(p.relative_to(base)):sha(p) for p in base.rglob('*') if p.is_file()}
    if actual != parent['files']:
        raise ValueError('Packed sign parent changed')
    original = (base/REL).read_text()
    start = original.index('static __device__ __forceinline__ float vec_dot_iq2_xxs_q8_1(')
    end = original.index('\n#define VDR_IQ2_XS_',start)
    body = original[start:end]
    old = '''    const float d = __half2float(bq2->d) * __low2float(bq8_1[iqs/2].ds);
    // IQ2's eighths are fractional. Integer division discards live values.
    return d * (static_cast<float>(sumi * ls) * 0.125f);'''
    new = '''    // The measured reference scales Q8_1 by 1/8, then rounds its
    // product with the weight scale before accumulating the integer dot.
    // Keep that boundary despite fast-math reassociation after sign expansion.
    const float scaled8 = __low2float(bq8_1[iqs/2].ds) * 0.125f;
    float d;
    asm("v_mul_f32 %0, %1, %2" : "=v"(d)
        : "v"(scaled8), "v"(__half2float(bq2->d)));
    return d * static_cast<float>(sumi * ls);'''
    if body.count(old) != 1:
        raise ValueError('Unexpected IQ2 scale expression')
    changed = original[:start]+body.replace(old,new)+original[end:]
    out = ROOT/'.deps/gufo-q2-curve-iq2-signs-ordered-asm'
    if out.exists():
        raise ValueError('Refusing to overwrite ordered candidate')
    shutil.copytree(base,out)
    (out/REL).write_text(changed)
    files = {str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()}
    assert files.keys() == actual.keys() and [k for k in actual if actual[k] != files[k]] == [REL]
    patch = ROOT/'experiments/q2-iq2-signs-ordered-asm.patch'
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),
        fromfile='a/'+REL,tofile='b/'+REL)))
    report = dict(schema='synapse-lie.q2-iq2-signs-ordered-source.v1',base=parent['candidate'],
        candidate=str(out.relative_to(ROOT)),files=files,changed_files=[REL],unchanged_files=len(files)-1,
        parent_manifest_sha256=sha(ROOT/'config/q2-iq2-signs-source.json'),patch_sha256=sha(patch),
        hypothesis='Match reference gfx1151 n1 FP scale rounding before FMA, retaining packed signs. Exact replay and speed remain unproven.',
        promoted=False,goal_met=False)
    (ROOT/'config/q2-iq2-signs-ordered-asm-source.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(candidate=report['candidate'],changed_files=[REL])))


if __name__ == '__main__':
    main()
