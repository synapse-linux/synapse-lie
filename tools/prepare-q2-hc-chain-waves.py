#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Distribute existing HC K16 chains between wave pairs without regrouping sums."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-affine-palette'
OUT = ROOT / '.deps/gufo-q2-bench-hc-chain-waves'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')
EXPECTED = '4de114a41d58e2b6f74038abfbf27bef8dc285dadf4b95ef69ae3b51b6b8a9fe'
EPILOGUE = r'''
  if constexpr (kHcChainWaves) {
    static_assert(kHalfWeights && !kHcMix && !kSsmConv && !kAttention);
    static_assert(BM == 64 && BN == 128 && BK == 2 && WM == 2 && WN == 4);
    // A wave pair owns the same output tile. The first wave writes the
    // original low-K16 chain; the second adds its original high-K16 chain
    // in F32, then performs the same output transpose and vector stores.
    constexpr unsigned stride = 36;
    float* tile = reinterpret_cast<float*>(s_lds) + wave_id * 16 * stride;
#pragma unroll
    for (unsigned j = 0; j < 2; ++j) {
      if (chain == 0) {
#pragma unroll
        for (unsigned l = 0; l < 8; ++l) {
          tile[sub_lane * stride + 2 * l + half_id] = acc[0][j][l];
          tile[sub_lane * stride + 16 + 2 * l + half_id] = acc[1][j][l];
        }
      }
      __syncthreads();
      if (chain == 1) {
#pragma unroll
        for (unsigned l = 0; l < 8; ++l) {
          const unsigned lo = sub_lane * stride + 2 * l + half_id;
          const unsigned hi = lo + 16;
          tile[lo] = tile[lo] + acc[0][j][l];
          tile[hi] = tile[hi] + acc[1][j][l];
        }
        __builtin_amdgcn_wave_barrier();
        const std::size_t token = t_block + (wave_tok * 2 + j) * 16 + lane_id / 2;
        const unsigned row = r_block + wave_row * 32 + (lane_id & 1) * 16;
        if (token < batch) {
          const auto* src = reinterpret_cast<const float4*>(
              tile + (lane_id / 2) * stride + (lane_id & 1) * 16);
          auto* dst = reinterpret_cast<float4*>(y + token * m + row);
#pragma unroll
          for (unsigned q = 0; q < 4; ++q)
            dst[q] = src[q];
        }
      }
      __syncthreads();
    }
    return;
  }

'''


def main():
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if sha(BASE / REL) != EXPECTED:
        raise ValueError('Measured palette base changed')
    original = (BASE / REL).read_text()
    start = original.index('template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,')
    end = original.index('\nbool AttentionF16Gemm(', start)
    body = original[start:end]
    replacements = [
        ('bool kHalfWeights = false>', 'bool kHalfWeights = false, bool kHcChainWaves = false>'),
        ('__launch_bounds__(256)', '__launch_bounds__(kHcChainWaves ? 512 : 256)'),
        ('  constexpr int kAUnits = BM * BK;',
         '  constexpr int kBlockThreads = kHcChainWaves ? 512 : 256;\n  constexpr int kAUnits = BM * BK;'),
        ('(kAUnits + 255) / 256', '(kAUnits + kBlockThreads - 1) / kBlockThreads'),
        ('(kBUnits + 255) / 256', '(kBUnits + kBlockThreads - 1) / kBlockThreads'),
        ('  const int wave_id = tid >> 5;',
         '  const int wave_id = (tid >> 5) / (kHcChainWaves ? 2 : 1);\n  const int chain = (tid >> 5) & 1;'),
        ('(p * 256)', '(p * kBlockThreads)'),
        ('kHalfWeights ? kWaveRowTiles : 1', '(kHalfWeights && !kHcChainWaves) ? kWaveRowTiles : 1'),
        ('kHalfWeights ? kWaveTokTiles : 1', '(kHalfWeights && !kHcChainWaves) ? kWaveTokTiles : 1'),
        ('for (int q = 0; q < 4; ++q) {\n          c[q] = s_a[kb][row][swizzle(row, q)];',
         'for (int q = 0; q < (kHcChainWaves ? 2 : 4); ++q) {\n          c[q] = s_a[kb][row][swizzle(row, q + (kHcChainWaves ? chain * 2 : 0))];'),
        ('        __builtin_memcpy(&a_hi[i], &c[2], 32);',
         '        if constexpr (!kHcChainWaves)\n          __builtin_memcpy(&a_hi[i], &c[2], 32);'),
        ('for (int q = 0; q < 4; ++q) {\n          c[q] = s_b[kb][t][swizzle(t, q)];',
         'for (int q = 0; q < (kHcChainWaves ? 2 : 4); ++q) {\n          c[q] = s_b[kb][t][swizzle(t, q + (kHcChainWaves ? chain * 2 : 0))];'),
        ('        __builtin_memcpy(&b_hi, &c[2], 32);',
         '        if constexpr (!kHcChainWaves)\n          __builtin_memcpy(&b_hi, &c[2], 32);'),
        ('          if constexpr (kHalfWeights)\n            acc_high[i][j]',
         '          if constexpr (kHalfWeights && !kHcChainWaves)\n            acc_high[i][j]'),
        ('          else\n            acc[i][j] = Wmma(a_hi[i], b_hi, acc[i][j]);',
         '          else if constexpr (!kHcChainWaves)\n            acc[i][j] = Wmma(a_hi[i], b_hi, acc[i][j]);'),
        ('  if constexpr (kHalfWeights) {\n#pragma unroll\n    for (int i = 0;',
         '  if constexpr (kHalfWeights && !kHcChainWaves) {\n#pragma unroll\n    for (int i = 0;'),
        ('  if constexpr (kAttention) {', EPILOGUE + '  if constexpr (kAttention) {'),
    ]
    for old, new in replacements:
        if old not in body:
            raise ValueError('Kernel anchor missing: ' + old)
        body = body.replace(old, new)
    changed = original[:start] + body + original[end:]
    old = '''(DenseF16GEMMKernel<64, 128, 2, 2, 4, 5, false, false, false, true>),
        dim3((batch + 127) / 128, 5), dim3(kThreads), 0, stream, w, x, out,'''
    new = '''(DenseF16GEMMKernel<64, 128, 2, 2, 4, 5, false, false, false, true, true>),
        dim3((batch + 127) / 128, 5), dim3(512), 0, stream, w, x, out,'''
    if changed.count(old) != 1:
        raise ValueError('HC launch anchor changed')
    changed = changed.replace(old, new)
    shutil.copytree(BASE, OUT)
    target = OUT / REL
    target.write_text(changed)
    subprocess.run(['clang-format', '-i', str(target)], check=True)
    changed_files = sorted(str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file()
                           and p.read_bytes() != (OUT / p.relative_to(BASE)).read_bytes())
    if changed_files != [str(REL)]:
        raise ValueError('Unexpected changed source inventory')
    patch = ROOT / 'experiments/q2-hc-chain-waves.patch'
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True),
        target.read_text().splitlines(True), fromfile='a/' + str(REL), tofile='b/' + str(REL))))
    report = dict(scope='Prepared source; numerical replay and speed unproven',
        pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
        base=str(BASE.relative_to(ROOT)), candidate=str(OUT.relative_to(ROOT)),
        base_sha256=sha(BASE / REL), candidate_sha256=sha(target), patch_sha256=sha(patch),
        changed_files=changed_files, mechanism='One existing K16 accumulator chain per physical wave; pairs share the same logical output tile',
        dispatch='Only F16 M320/K10240, n>=96, uses 512 threads; all other specializations retain 256',
        numeric_contract='Same F16 bytes, low/high K16 sequences and final low+high F32 addition',
        unchanged='64x128 tiles, BK2, five-row grouping, LDS stage data and allocations, model storage')
    (ROOT / 'config/q2-hc-chain-waves-source.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
