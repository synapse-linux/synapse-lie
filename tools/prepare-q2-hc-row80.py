#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Share HC input across 80 rows, preserving two ordered K16 wave chains."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-up-chains'
DONOR = ROOT / '.deps/gufo-q2-bench-hc-chain-coalesced'
OUT = ROOT / '.deps/gufo-q2-bench-hc-row80'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Unexpected source anchor: ' + old[:80])
    return text.replace(old, new)


EPILOGUE = '''
  // Each pair retains the two original K16 sums. Share low through the
  // now-dead staging allocation, then high adds low+high in the same order.
  // Five row tiles per logical wave require a bounded final 16-row store.
  constexpr unsigned stride = 36;
  float* tile = reinterpret_cast<float*>(s_lds) + wave_id * 16 * stride;
#pragma unroll
  for (unsigned i = 0; i < kWaveRowTiles; i += 2) {
    if (chain == 0) {
#pragma unroll
      for (unsigned l = 0; l < 8; ++l) {
        tile[sub_lane * stride + 2 * l + half_id] = acc[i][0][l];
        if (i + 1 < kWaveRowTiles)
          tile[sub_lane * stride + 16 + 2 * l + half_id] = acc[i + 1][0][l];
      }
    }
    __syncthreads();
    if (chain == 1) {
#pragma unroll
      for (unsigned l = 0; l < 8; ++l) {
        const unsigned lo = sub_lane * stride + 2 * l + half_id;
        tile[lo] = tile[lo] + acc[i][0][l];
        if (i + 1 < kWaveRowTiles)
          tile[lo + 16] = tile[lo + 16] + acc[i + 1][0][l];
      }
      __builtin_amdgcn_wave_barrier();
      const std::size_t token = t_block + wave_tok * 16 + lane_id / 2;
      const unsigned row_l = (lane_id & 1) * 16;
      const unsigned row = r_block + i * 16 + row_l;
      if (token < batch && row + 16 <= m &&
          (i + 1 < kWaveRowTiles || row_l == 0)) {
        const auto* src = reinterpret_cast<const float4*>(
            tile + (lane_id / 2) * stride + row_l);
        auto* dst = reinterpret_cast<float4*>(y + token * m + row);
#pragma unroll
        for (unsigned q = 0; q < 4; ++q)
          dst[q] = src[q];
      }
    }
    __syncthreads();
  }
}

'''


def main():
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if sha(BASE / REL) != 'a5ccc81f7762beae74cf0bbb06e6aeebd44edf1c804c1473b63619af023a6cd5':
        raise ValueError('Retained paired-up base changed')
    if sha(DONOR / REL) != 'f92ed87029211b44c5c9dd7d0e460c52fb15b686397d387f9012c33faf13fc50':
        raise ValueError('Measured coalesced-wave donor changed')
    original = (BASE / REL).read_text()
    donor = (DONOR / REL).read_text()
    begin = donor.index('template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,')
    begin = donor.index('  static_assert(WM * WN', begin)
    end = donor.index('\n  if constexpr (kHcChainWaves) {', begin)
    body = donor[begin:end]
    body = once(body, 'BM == 64', 'BM == 80')
    body = once(body, 'BK == 2 && WM == 2 && WN == 4', 'BK == 2 && WM == 1 && WN == 8')
    body = once(body, 'kRowGroup == 5', 'kRowGroup == 4')
    signature = '''// Isolated 80-row original-F16 HC down specialization.
__launch_bounds__(512) __global__ void HcDownRow80Kernel(
    const void* __restrict__ w, const __half* __restrict__ x,
    float* __restrict__ y, std::size_t batch, std::size_t m, std::size_t k) {
  constexpr int BM = 80, BN = 128, BK = 2, WM = 1, WN = 8, kRowGroup = 4;
  constexpr bool kHalfWeights = true, kHcChainWaves = true, kHcMix = false,
                 kSsmConv = false, kAttention = false;
'''
    changed = once(original, 'bool UnquantizedF16Gemm(', signature + body + EPILOGUE + 'bool UnquantizedF16Gemm(')
    changed = once(changed,
        '    // Group all five row tiles around one 128-token input stripe. The\n'
        '    // original F16 full-batch input alone exceeds the 32 MiB cache.\n'
        '    hipLaunchKernelGGL(\n'
        '        (DenseF16GEMMKernel<64, 128, 2, 2, 4, 5, false, false, false, true>),\n'
        '        dim3((batch + 127) / 128, 5), dim3(kThreads), 0, stream, w, x, out,\n'
        '        batch, m, k);',
        '    // Four row blocks share each 128-token input stripe. The original\n'
        '    // F16 operands and ordered K16 sums are retained by wave pairs.\n'
        '    hipLaunchKernelGGL(HcDownRow80Kernel, dim3((batch + 127) / 128, 4),\n'
        '                       dim3(512), 0, stream, w, x, out, batch, m, k);')
    shutil.copytree(BASE, OUT)
    target = OUT / REL
    target.write_text(changed)
    subprocess.run(['clang-format', '-i', str(target)], check=True)
    changed_files = sorted(str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file()
                           and p.read_bytes() != (OUT / p.relative_to(BASE)).read_bytes())
    if changed_files != [str(REL)]:
        raise ValueError('Unexpected source changes')
    patch = ROOT / 'experiments/q2-hc-row80.patch'
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True), target.read_text().splitlines(True),
                                               fromfile='a/' + str(REL), tofile='b/' + str(REL))))
    report = dict(scope='Isolated HC row80 experiment; numerical replay and speed unproven',
                  pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
                  base=str(BASE.relative_to(ROOT)), donor=str(DONOR.relative_to(ROOT)),
                  candidate=str(OUT.relative_to(ROOT)), base_sha256=sha(BASE / REL),
                  donor_sha256=sha(DONOR / REL), candidate_sha256=sha(target), patch_sha256=sha(patch),
                  changed_files=changed_files, dispatch='Only M320/K10240/n>=96 original-F16 HC down',
                  geometry='BM80/BN128/BK2/WM1/WN8, four-row grouping, 512 threads',
                  mechanism='Coalesced 16-byte stage fetches, five row tiles per paired wave, bounded odd epilogue',
                  arithmetic='Original F16 operands, two ordered K16 sums and final low+high F32 addition',
                  logical_staging_n2048=dict(input_mib=160, weights_mib=100, blocks=64),
                  reference_staging_n2048=dict(input_mib=200, weights_mib=100, blocks=80),
                  physical_traffic_measured=False, model_conversion=False, numerical_limits_changed=False,
                  promoted=False)
    (ROOT / 'config/q2-hc-row80-source.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
