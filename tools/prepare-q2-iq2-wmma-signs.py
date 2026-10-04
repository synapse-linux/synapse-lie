#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Replace the active IQ2 WMMA sign-table reads, retaining ordered decode."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parent_path = ROOT/'config/q2-iq2-signs-ordered-asm-source.json'
    parent = json.loads(parent_path.read_text())
    base = ROOT/parent['candidate']
    actual = {str(f.relative_to(base)): sha(f) for f in base.rglob('*') if f.is_file()}
    if actual != parent['files']:
        raise ValueError('Measured ordered IQ2 provider changed')
    original = (base/REL).read_text()
    old = '''          const uint2 mask = reinterpret_cast<const uint2*>(ksigns64)[sign];
          signed_codes[part] =
              make_uint2((magnitude.x ^ mask.x) + (mask.x & 0x01010101U),
                         (magnitude.y ^ mask.y) + (mask.y & 0x01010101U));'''
    new = '''          // Official Gufo DeepSeek integer sign expansion, now in the
          // active Qwen WMMA loader. Preserve all scale and WMMA arithmetic.
          const unsigned signs = sign | ((__popc(sign) & 1U) << 7U);
          const unsigned add0 = ((signs & 15U) * 0x00204081U) & 0x01010101U;
          const unsigned add1 = ((signs >> 4U) * 0x00204081U) & 0x01010101U;
          signed_codes[part] = make_uint2((magnitude.x ^ (add0 * 255U)) + add0,
                                          (magnitude.y ^ (add1 * 255U)) + add1);'''
    if original.count(old) != 1:
        raise ValueError('Unexpected active IQ2 WMMA sign loader')
    changed = original.replace(old, new)
    out = ROOT/'.deps/gufo-q2-curve-iq2-wmma-signs'
    if out.exists():
        raise ValueError('Refusing to overwrite WMMA candidate')
    shutil.copytree(base, out)
    (out/REL).write_text(changed)
    files = {str(f.relative_to(out)): sha(f) for f in out.rglob('*') if f.is_file()}
    if files.keys() != actual.keys() or [k for k in actual if actual[k] != files[k]] != [REL]:
        raise ValueError('Unexpected provider delta')
    patch = ROOT/'experiments/q2-iq2-wmma-signs.patch'
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True),
                    fromfile='a/'+REL, tofile='b/'+REL)))
    donor = 'src/models/deepseek_v4_flash/kernels/rocm/detail/ds4_rocm_iq2_gate.hip.hpp'
    report = dict(schema='synapse-lie.q2-iq2-wmma-signs-source.v1',
        base=parent['candidate'], candidate=str(out.relative_to(ROOT)), files=files,
        parent_manifest_sha256=sha(parent_path), changed_files=[REL], unchanged_files=len(files)-1,
        patch_sha256=sha(patch), pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
        donor=donor, donor_sha256=sha(ROOT/'.deps/gufo-base'/donor),
        mechanism='Replace each eight-byte ksigns64 lookup by parity completion and packed integer signs in RoutedF16GEMMKernel IQ2 fetch_stage.',
        unchanged='Ordered MMVQ decode, codebook, scale rounding, WMMA order, SwiGLU, routing, tile geometry, Q2 down, PLE and C17 core.',
        risk='Extra integer instructions/registers can cost more than cached table loads. No speedup inferred from source.',
        runtime_validated=False, promoted=False, goal_met=False)
    (ROOT/'config/q2-iq2-wmma-signs-source.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('candidate', 'changed_files', 'unchanged_files')}))


if __name__ == '__main__':
    main()
