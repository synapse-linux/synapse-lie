#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Decode paired IQ2 weights once into bounded, shared F16 stages."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(folder):
    return {str(p.relative_to(folder)): sha(p)
            for p in sorted(folder.rglob('*')) if p.is_file()}


def function(text, signature):
    if text.count(signature) != 1:
        raise ValueError('Ambiguous retained kernel')
    start = text.index(signature)
    body = re.search(r'\)\s*\{', text[start:])
    if body is None:
        raise ValueError('Retained kernel body missing')
    opening = start + body.end() - 1
    depth, end = 1, opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end] + '\n'


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Source anchor changed: '+old[:80])
    return text.replace(old, new, 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--swizzled', action='store_true',
                        help='Separate variant with conflict-free producer row bits')
    args = parser.parse_args()
    parent_path = ROOT/'config/q2-hc-moe-deferred-source.json'
    parent = json.loads(parent_path.read_text())['variants']['hc-moe-deferred']
    base = ROOT/parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Measured MoE provider changed')
    original = (base/REL).read_text()
    signature = 'template<WeightType kType, int BM, int BN, int BK, bool kPair = false,'
    kernel = function(original, signature)
    changed_kernel = once(kernel,
        '  constexpr bool kSigned = kQ8 || kIQ2;',
        '''  constexpr bool kSigned = kQ8 || kIQ2;
  // IQ2 paired rows otherwise repeat the same F16 weight conversion in both
  // half-waves. Convert once in the producer, retaining CodesToHalves exactly.
  constexpr bool kStageHalves = kIQ2 && kPair;''')
    changed_kernel = once(changed_kernel,
        '  constexpr int kCodeBytes = BM * kChunks * 16;',
        '''  constexpr int kStoredChunks = kStageHalves ? 2 * kChunks : kChunks;
  constexpr int kCodeBytes = BM * kStoredChunks * 16;''')
    changed_kernel = once(changed_kernel,
        '  constexpr int kScaleBytes = (kQ2 ? 4 : 1) * BK * BM * 4;',
        '  constexpr int kScaleBytes = kStageHalves ? 0 : (kQ2 ? 4 : 1) * BK * BM * 4;')
    changed_kernel = once(changed_kernel,
        '  constexpr int kActStride = BN + 1;',
        '''  // XOR the low token bits with its quarter rather than padding the
  // planes. At BN128 the expanded weight/activation stage is exactly32 KiB.
  // BN is a multiple of16, so this bijection cannot leave a token fragment.
  constexpr int kActStride = kStageHalves ? BN : BN + 1;''')
    changed_kernel = once(changed_kernel,
        '    a_slot[i] = chunk < kActChunks ? (sub * kActStride) + t : -1;',
        '''    a_slot[i] = chunk < kActChunks
                    ? (sub * kActStride) + (kStageHalves ? (t ^ sub) : t)
                    : -1;''')
    changed_kernel = once(changed_kernel,
        '''    return (row * kChunks) +
           (c ^ (kChunks == 4 ? ((row >> 1) & 3) : ((row >> 2) & 1)));''',
        '''    return (row * kStoredChunks) +
           (c ^ (kStageHalves ? ((row >> 1) & 7)
                             : (kChunks == 4 ? ((row >> 1) & 3)
                                            : ((row >> 2) & 1))));''')
    changed_kernel = once(changed_kernel,
        '''      if constexpr (kSigned || kQ2) {
        s_codes[swizzle(row, 2 * f_c)] = f_codes[u];''',
        '''      if constexpr (kStageHalves) {
        const std::uint32_t dm = f_live[u] ? f_dm[u] : 0U;
        const __half2 scale2 = __low2half2(__builtin_bit_cast(__half2, dm));
        const __half2 zero2 = __float2half2_rn(0.0F);
        const __half2 signed_magic = __float2half2_rn(-1152.0F);
        const std::uint32_t words[8] = {
            f_codes[u].x, f_codes[u].y, f_codes[u].z, f_codes[u].w,
            f_codes_hi[u].x, f_codes_hi[u].y, f_codes_hi[u].z, f_codes_hi[u].w};
#pragma unroll
        for (int c = 0; c < 4; ++c) {
          __half2 h[4];
          CodesToHalves(words[2 * c] ^ 0x80808080U, signed_magic, scale2,
                        zero2, h[0], h[1]);
          CodesToHalves(words[2 * c + 1] ^ 0x80808080U, signed_magic, scale2,
                        zero2, h[2], h[3]);
          uint4 v;
          __builtin_memcpy(&v, h, 16);
          s_codes[swizzle(row, 4 * f_c + c)] = v;
          __builtin_amdgcn_sched_barrier(0);
        }
      } else if constexpr (kSigned || kQ2) {
        s_codes[swizzle(row, 2 * f_c)] = f_codes[u];''')
    changed_kernel = once(changed_kernel,
        '      if constexpr (!kQ2)\n        s_scale[(f_c * BM) + row] = scale_bias;',
        '      if constexpr (!kQ2 && !kStageHalves)\n        s_scale[(f_c * BM) + row] = scale_bias;')
    start = changed_kernel.index('        const __half2 sb =',
                                 changed_kernel.index('  const auto compute_stage'))
    finish_anchor = '        __builtin_memcpy(&a_hi[u], &h[8], 32);'
    finish = changed_kernel.index(finish_anchor, start)+len(finish_anchor)
    original_decode = changed_kernel[start:finish]
    expanded = '''        if constexpr (kStageHalves) {
          const uint4 h[4] = {
              s_codes[swizzle(row, 4 * kb)],
              s_codes[swizzle(row, 4 * kb + 1)],
              s_codes[swizzle(row, 4 * kb + 2)],
              s_codes[swizzle(row, 4 * kb + 3)]};
          __builtin_memcpy(&a_lo[u], &h[0], 32);
          __builtin_memcpy(&a_hi[u], &h[2], 32);
        } else {
'''+''.join('  '+line+'\n' for line in original_decode.splitlines())+'''        }'''
    changed_kernel = changed_kernel[:start]+expanded+changed_kernel[finish:]
    changed_kernel = once(changed_kernel,
        '          b[q] = frag[q * kActStride];',
        '''          if constexpr (kStageHalves) {
            const int quarter = kb * 4 + q;
            b[q] = s_act[quarter * kActStride +
                         ((j * 16 + sub_lane) ^ quarter)];
          } else {
            b[q] = frag[q * kActStride];
          }''')
    if args.swizzled:
        changed_kernel = once(changed_kernel,
                              'kStageHalves ? ((row >> 1) & 7)',
                              'kStageHalves ? (row & 7)')
    changed = original.replace(kernel, changed_kernel, 1)
    tag = 'q2-iq2-halfstage-swizzled' if args.swizzled else 'q2-iq2-halfstage'
    candidate = ROOT/'.deps'/('gufo-'+tag+'-run')
    control = ROOT/'experiments/q2-iq2-halfstage-control.inc'
    patch = ROOT/'experiments'/(tag+'.patch')
    manifest = ROOT/'config'/(tag+'-source.json')
    if any(p.exists() for p in (candidate, patch, manifest)) or (control.exists() and not args.swizzled):
        raise ValueError('Refusing to overwrite a retained experiment')
    shutil.copytree(base, candidate)
    (candidate/REL).write_text(changed)
    control_text = ('// SPDX-License-Identifier: MIT\n'
                    '// Literal retained MoE paired IQ2 control, test-only.\n'
                    '// Independently pinned Gufo-derived LIE provider; no DS4 import.\n'+
                    kernel.replace('RoutedF16GEMMKernel', 'RoutedIQ2HalfstageControlKernel'))
    if control.exists():
        if control.read_text() != control_text:
            raise ValueError('Literal retained control changed')
    else:
        with control.open('x') as stream:
            stream.write(control_text)
    with patch.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n'+''.join(difflib.unified_diff(
            original.splitlines(True), changed.splitlines(True),
            fromfile='a/'+REL, tofile='b/'+REL)))
    files = inventory(candidate)
    delta = [n for n in files if files[n] != parent['files'].get(n)]
    if delta != [REL] or len(files) != 1025:
        raise ValueError('Unexpected provider delta')
    variant = dict(source=str(candidate.relative_to(ROOT)), files=files,
        changed_files=delta, parent_manifest=str(parent_path.relative_to(ROOT)),
        parent_manifest_sha256=sha(parent_path),
        measured_parent='config/q2-hc-moe-deferred-model-results.json',
        measured_parent_sha256=sha(ROOT/'config/q2-hc-moe-deferred-model-results.json'),
        original_kernel_sha256=hashlib.sha256(kernel.encode()).hexdigest(),
        control_include=str(control.relative_to(ROOT)), control_include_sha256=sha(control),
        patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch),
        mechanism='One producer F16 expansion per IQ2 weight; duplicate half-wave consumers read exact halves. XOR activation LDS layout avoids padding and retains32 KiB maximum stage.',
        risks='Weight LDS traffic doubles; producer conversion moves onto the stage commit. Register occupancy, bank conflicts and scheduling can outweigh fewer conversions.',
        numerical_contract='Same signed bytes, scale rounding, CodesToHalves packed add/FMA, ordered K16 WMMA, SwiGLU, tails, routing and packed output.',
        stage_bytes_by_bn={str(bn):16384+bn*128 for bn in (16,48,64,128)},
        producer_conflict_free_swizzle=args.swizzled,
        additional_allocations=0, additional_streams=0,
        byte_exactness_expected_not_qualified=True,
        full_model_measured=False, numerical_acceptance=False, goal_met=False)
    with manifest.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-iq2-halfstage-source.v1',
                       variants={'iq2-halfstage':variant}, gpu_run=False,
                       goal_met=False), stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(files=len(files), changed=delta,
                         stage_bytes_by_bn=variant['stage_bytes_by_bn'])))


if __name__ == '__main__':
    main()
