#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reuse exact HC chain pairs in a wider raw-F16 down-projection tile."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-up-chains'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')
EXPECTED = 'a5ccc81f7762beae74cf0bbb06e6aeebd44edf1c804c1473b63619af023a6cd5'
EPILOGUE = r'''
  if constexpr (kHcChains && !kHcMix) {
    static_assert(kHalfWeights && !kSsmConv && !kAttention);
    static_assert(BM == 128 && BN == 128 && BK == 2 && WM == 4 && WN == 2);
    // Publish each original low-K16 sum, then add its original high-K16
    // sum in the paired wave. The final 64 padded rows are never stored.
    constexpr unsigned stride = 36;
    float* tile = reinterpret_cast<float*>(s_lds) + wave_id * 16 * stride;
#pragma unroll
    for (unsigned j = 0; j < kWaveTokTiles; ++j) {
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
        const std::size_t token = t_block +
            (wave_tok * kWaveTokTiles + j) * 16 + lane_id / 2;
        const unsigned row = r_block + wave_row * 32 + (lane_id & 1) * 16;
        if (token < batch && row < m) {
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


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Unexpected source boundary: ' + old[:90])
    return text.replace(old, new)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage-blocks', type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    stage = args.stage_blocks
    name = 'hc-down-wide' + ('-k1' if stage == 1 else '')
    out = ROOT / ('.deps/gufo-q2-bench-' + name)
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if sha(BASE / REL) != EXPECTED:
        raise ValueError('Measured paired-up source changed')
    original = (BASE / REL).read_text()
    start = original.index('template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,')
    end = original.index('\nbool AttentionF16Gemm(', start)
    body = original[start:end].replace('kHcUpChains', 'kHcChains')
    body = once(body, '''  static_assert(!kHcChains ||
                (kHalfWeights && kHcMix && BM == 256 && BN == 128));''',
        '''  static_assert(!kHcChains || (kHalfWeights && BN == 128 &&
                ((kHcMix && BM == 256) || (!kHcMix && BM == 128))));''')
    epilogue = EPILOGUE.replace('BK == 2', 'BK == ' + str(stage))
    body = once(body, '  if constexpr (kAttention) {', epilogue + '  if constexpr (kAttention) {')
    changed = original[:start] + body + original[end:]
    changed = once(changed, '''    // Group all five row tiles around one 128-token input stripe. The
    // original F16 full-batch input alone exceeds the 32 MiB cache.
    hipLaunchKernelGGL(
        (DenseF16GEMMKernel<64, 128, 2, 2, 4, 5, false, false, false, true>),
        dim3((batch + 127) / 128, 5), dim3(kThreads), 0, stream, w, x, out,''',
        '''    // Three wider row tiles share each 128-token input stripe. Paired
    // waves retain the original low/high K16 accumulation chains.
    hipLaunchKernelGGL(
        (DenseF16GEMMKernel<128, 128, 2, 4, 2, 3, false, false, false, true, true>),
        dim3((batch + 127) / 128, 3), dim3(512), 0, stream, w, x, out,'''.replace(
            '128, 128, 2, 4, 2, 3', f'128, 128, {stage}, 4, 2, 3'))
    shutil.copytree(BASE, out)
    target = out / REL
    target.write_text(changed)
    subprocess.run(['clang-format', '-i', str(target)], check=True)
    changed_files = sorted(str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file()
                           and p.read_bytes() != (out / p.relative_to(BASE)).read_bytes())
    if changed_files != [str(REL)]:
        raise ValueError('Unexpected changed inventory')
    patch = ROOT / ('experiments/q2-' + name + '.patch')
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True), target.read_text().splitlines(True),
        fromfile='a/' + str(REL), tofile='b/' + str(REL))))
    report = dict(scope='Prepared source; numerical replay and runtime benefit unproven',
        pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e', base=str(BASE.relative_to(ROOT)),
        candidate=str(out.relative_to(ROOT)), base_sha256=sha(BASE / REL), candidate_sha256=sha(target),
        patch_sha256=sha(patch), changed_files=changed_files,
        dispatch=f'Only original-F16 M320/K10240 at n>=96: 128x128/BK{stage}/WM4/WN2, three row groups, 512 threads',
        numeric_contract='Original F16 bytes, unchanged ordered low/high K16 chains and final F32 low+high sum',
        ownership='Existing stage and transpose LDS; unchanged input/output ownership and model storage',
        limit='Three blocks replace five per token stripe, but padding adds 20% matrix work; BK1 doubles stage barriers; no gain assumed')
    (ROOT / ('config/q2-' + name + '-source.json')).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
