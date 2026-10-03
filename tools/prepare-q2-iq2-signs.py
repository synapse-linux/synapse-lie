#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare the pinned DeepSeek packed-sign technique for Qwen IQ2 MMVQ."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-curve-q2'
OUT = ROOT / '.deps/gufo-q2-curve-iq2-signs'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/mmq/vecdotq.hpp')
DONOR = Path('src/models/deepseek_v4_flash/kernels/rocm/detail/ds4_rocm_iq2_gate.hip.hpp')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((ROOT/'config/q2-curve-source.json').read_text())
    # Pin the actual measured provider, including its cumulative experimental
    # arithmetic. This preparation does not qualify those earlier changes.
    expected = manifest['variants']['q2']['files']
    actual = {str(p.relative_to(BASE)):sha(p) for p in BASE.rglob('*') if p.is_file()}
    if actual != expected:
        raise ValueError('Canonical Q2 provider changed')
    original = (BASE/REL).read_text()
    begin = original.index('static __device__ __forceinline__ float vec_dot_iq2_xxs_q8_1(')
    end = original.index('\n#define VDR_IQ2_XS_', begin)
    body = original[begin:end]
    old = '''        const uint32_t signs = unpack_ksigns(aux32 >> (7 * k0 / 2));

        const int signs0 = __vcmpne4(signs & 0x08040201, 0);
        const int grid0 = __vsub4(grid_pos.x ^ signs0, signs0);'''
    new = '''        // Adapted from official Gufo DeepSeek dev_iq2_i8x8_lut at
        // f783fedb9bea2ec7de941f6da4e02f4a4596b29e (see provenance).
        // Complete parity, then spread four signs into byte-wise increments.
        // IQ2 magnitudes are nonzero; negation cannot carry to another byte.
        const uint32_t sign7 = (aux32 >> (7 * k0 / 2)) & 127u;
        const uint32_t signs = sign7 | ((__popc(sign7) & 1u) << 7u);
        const uint32_t add0 = ((signs & 15u) * 0x00204081u) & 0x01010101u;
        const uint32_t add1 = ((signs >> 4u) * 0x00204081u) & 0x01010101u;
        const int grid0 = static_cast<int>((grid_pos.x ^ (add0 * 255u)) + add0);'''
    old1 = '''        const int signs1 = __vcmpne4(signs & 0x80402010, 0);
        const int grid1 = __vsub4(grid_pos.y ^ signs1, signs1);'''
    new1 = '''        const int grid1 = static_cast<int>((grid_pos.y ^ (add1 * 255u)) + add1);'''
    if body.count(old) != 1 or body.count(old1) != 1:
        raise ValueError('Unexpected IQ2 vector dot body')
    body = body.replace(old,new).replace(old1,new1)
    changed = original[:begin]+body+original[end:]
    if OUT.exists():
        raise ValueError('Refusing to overwrite candidate')
    shutil.copytree(BASE,OUT)
    (OUT/REL).write_text(changed)
    files = {str(p.relative_to(OUT)):sha(p) for p in OUT.rglob('*') if p.is_file()}
    differences = [k for k in actual if actual[k] != files[k]]
    if actual.keys() != files.keys() or differences != [str(REL)]:
        raise ValueError('Unexpected candidate delta')
    patch = ROOT/'experiments/q2-iq2-signs.patch'
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),
        fromfile='a/'+str(REL),tofile='b/'+str(REL))))
    report = dict(schema='synapse-lie.q2-iq2-signs-source.v1',
        pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
        base=str(BASE.relative_to(ROOT)),candidate=str(OUT.relative_to(ROOT)),
        donor=str(DONOR),donor_sha256=sha(ROOT/'.deps/gufo-base'/DONOR),
        base_sha256=actual[str(REL)],candidate_sha256=files[str(REL)],
        patch_sha256=sha(patch),changed_files=differences,unchanged_files=len(files)-1,
        scope='Static preparation only. No runtime, numerical acceptance or performance evidence.',
        unchanged='IQ2 bytes, codebook, Q8_1 quantization, dp4a order, FP32 scale and reduction, prefill WMMA path, C17 core',
        pending=['Exhaustive 256 codebook entries x 128 signs on .157',
                 'IQ2 operators with unchanged independent limits and full-output replay',
                 'Device ISA/resource comparison and complete decode cycle',
                 'Uninstrumented Q2/UD canonical PP+TG curve, only if component benefit survives'],
        files=files,promoted=False,goal_met=False)
    (ROOT/'config/q2-iq2-signs-source.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(changed=differences,unchanged=len(files)-1)))


if __name__ == '__main__':
    main()
