#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Pair the original HC up K16 chains to enable a larger spill-free tile."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-affine-palette'
OUT = ROOT / '.deps/gufo-q2-bench-hc-up-chains'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')
EXPECTED = '4de114a41d58e2b6f74038abfbf27bef8dc285dadf4b95ef69ae3b51b6b8a9fe'


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Unexpected source boundary: ' + old[:90])
    return text.replace(old, new)


def main():
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if sha(BASE / REL) != EXPECTED:
        raise ValueError('Measured palette source changed')
    original = (BASE / REL).read_text()
    start = original.index('template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,')
    end = original.index('\nbool AttentionF16Gemm(', start)
    body = original[start:end]
    changes = [
        ('bool kHalfWeights = false>', 'bool kHalfWeights = false, bool kHcUpChains = false>'),
        ('__launch_bounds__(256)', '__launch_bounds__(kHcUpChains ? 512 : 256)'),
        ('  constexpr int kAUnits = BM * BK;',
         '  static_assert(!kHcUpChains || (kHalfWeights && kHcMix && BM == 256 && BN == 128));\n'
         '  constexpr int kBlockThreads = kHcUpChains ? 512 : 256;\n  constexpr int kAUnits = BM * BK;'),
        ('(kAUnits + 255) / 256', '(kAUnits + kBlockThreads - 1) / kBlockThreads'),
        ('(kBUnits + 255) / 256', '(kBUnits + kBlockThreads - 1) / kBlockThreads'),
        ('  const int wave_id = tid >> 5;',
         '  const int wave_id = (tid >> 5) / (kHcUpChains ? 2 : 1);\n'
         '  const int chain = (tid >> 5) & 1;'),
        ('(p * 256)', '(p * kBlockThreads)'),
        ('kHalfWeights ? kWaveRowTiles : 1', '(kHalfWeights && !kHcUpChains) ? kWaveRowTiles : 1'),
        ('kHalfWeights ? kWaveTokTiles : 1', '(kHalfWeights && !kHcUpChains) ? kWaveTokTiles : 1'),
        ('for (int q = 0; q < 4; ++q) {\n          c[q] = s_a[kb][row][swizzle(row, q)];',
         'for (int q = 0; q < (kHcUpChains ? 2 : 4); ++q) {\n'
         '          c[q] = s_a[kb][row][swizzle(row, q + (kHcUpChains ? chain * 2 : 0))];'),
        ('        __builtin_memcpy(&a_hi[i], &c[2], 32);',
         '        if constexpr (!kHcUpChains)\n          __builtin_memcpy(&a_hi[i], &c[2], 32);'),
        ('for (int q = 0; q < 4; ++q) {\n          c[q] = s_b[kb][t][swizzle(t, q)];',
         'for (int q = 0; q < (kHcUpChains ? 2 : 4); ++q) {\n'
         '          c[q] = s_b[kb][t][swizzle(t, q + (kHcUpChains ? chain * 2 : 0))];'),
        ('        __builtin_memcpy(&b_hi, &c[2], 32);',
         '        if constexpr (!kHcUpChains)\n          __builtin_memcpy(&b_hi, &c[2], 32);'),
        ('          if constexpr (kHalfWeights)\n            acc_high[i][j]',
         '          if constexpr (kHalfWeights && !kHcUpChains)\n            acc_high[i][j]'),
        ('          else\n            acc[i][j] = Wmma(a_hi[i], b_hi, acc[i][j]);',
         '          else if constexpr (!kHcUpChains)\n            acc[i][j] = Wmma(a_hi[i], b_hi, acc[i][j]);'),
        ('  if constexpr (kHalfWeights) {\n#pragma unroll\n    for (int i = 0;',
         '  if constexpr (kHalfWeights && !kHcUpChains) {\n#pragma unroll\n    for (int i = 0;'),
    ]
    for old, new in changes:
        if old not in body:
            raise ValueError('Missing kernel anchor: ' + old)
        body = body.replace(old, new)
    mix_start = body.index('  if constexpr (kHcMix) {')
    mix_end = body.index('\n  // Transpose the result', mix_start)
    mix = body[mix_start:mix_end]
    mix = once(mix, '        if (wave_tok == token_group) {',
               '        if (wave_tok == token_group && (!kHcUpChains || chain == 0)) {')
    mix = once(mix, '''        __syncthreads();
        // A half-wave writes all 64 hidden values of one token.''', '''        __syncthreads();
        if constexpr (kHcUpChains) {
          // Each wave pair owns the original low/high K16 sums. Publish low,
          // then add high in F32 in the same order before any sigmoid/mix.
          if (chain == 1 && wave_tok == token_group) {
#pragma unroll
            for (int i = 0; i < kWaveRowTiles; ++i) {
#pragma unroll
              for (int l = 0; l < 8; ++l) {
                const unsigned row =
                    (wave_row * kWaveRowTiles + i) * 16 + 2 * l + half_id;
                const unsigned pos =
                    (row % 4) * kPlane + sub_lane * kStreamStride + row / 4;
                gates[pos] = gates[pos] + acc[i][j][l];
              }
            }
          }
          __syncthreads();
        }
        // A half-wave writes all 64 hidden values of one token.''')
    body = body[:mix_start] + mix + body[mix_end:]
    changed = original[:start] + body + original[end:]
    changed = once(changed, '''  const dim3 grid((n_tokens + 63) / 64, 4 * hidden / 128);
  hipLaunchKernelGGL(
      (DenseF16GEMMKernel<128, 64, 1, 4, 2, 8, true, false, false, true>), grid,
      dim3(kThreads), 0, stream, up, low_rank, mixed, n_tokens, 4 * hidden,''',
        '''  const dim3 grid((n_tokens + 127) / 128, 4 * hidden / 256);
  hipLaunchKernelGGL(
      (DenseF16GEMMKernel<256, 128, 1, 4, 2, 8, true, false, false, true, true>), grid,
      dim3(512), 0, stream, up, low_rank, mixed, n_tokens, 4 * hidden,''')
    shutil.copytree(BASE, OUT)
    target = OUT / REL
    target.write_text(changed)
    subprocess.run(['clang-format', '-i', str(target)], check=True)
    changed_files = sorted(str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file()
                           and p.read_bytes() != (OUT / p.relative_to(BASE)).read_bytes())
    if changed_files != [str(REL)]:
        raise ValueError('Unexpected changed inventory')
    patch = ROOT / 'experiments/q2-hc-up-chains.patch'
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True), target.read_text().splitlines(True),
        fromfile='a/' + str(REL), tofile='b/' + str(REL))))
    report = dict(scope='Prepared source; numerical replay and runtime benefit unproven',
        pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e', base=str(BASE.relative_to(ROOT)),
        candidate=str(OUT.relative_to(ROOT)), base_sha256=sha(BASE / REL), candidate_sha256=sha(target),
        patch_sha256=sha(patch), changed_files=changed_files,
        dispatch='Fused original F16 HC up/mix only; 256x128/BK1/WM4/WN2 with 512 physical threads',
        numeric_contract='Identical F16 weights/inputs, original low and high K16 chains, low+high addition, sigmoid and four-stream FMA order',
        ownership='Existing stage/gate LDS and output buffers; no new allocation, stream or model conversion',
        limit='Extra wave-pair barriers and block size may offset larger tiles; static resources are not performance evidence')
    (ROOT / 'config/q2-hc-up-chains-source.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
