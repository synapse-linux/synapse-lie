#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare bounded HC down scheduling hypotheses from the measured reference."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-moe-fused'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')
VARIANTS = {
    'hc-down64-wave4': (64, 2, 4, 2),
    'hc-down64-k4': (64, 4, 2, 4),
    'hc-down128-wave4': (128, 2, 4, 2),
}


def single_row_epilogue(source):
    kernel = source.index('__global__ void DenseF16GEMMKernel(')
    start = source.index('  static_assert(kWaveRowTiles % 2 == 0, "the epilogue pairs row tiles");', kernel)
    end = source.index('\n}\n\nbool AttentionF16Gemm(', start)
    paired = source[start:end]
    single = '''  if constexpr (kWaveRowTiles == 1) {
    static_assert(kHalfWeights && !kHcMix && !kSsmConv && !kAttention);
    // One 16-row output tile per wave. Preserve the matrix accumulators;
    // only the LDS-to-global transpose differs from the paired-row route.
    float* tile = reinterpret_cast<float*>(s_lds) +
                  wave_id * kOutputTokens * kOutputStride;
#pragma unroll
    for (int j = 0; j < kWaveTokTiles; ++j) {
#pragma unroll
      for (int l = 0; l < 8; ++l)
        tile[sub_lane * kOutputStride + 2 * l + half_id] = acc[0][j][l];
      __builtin_amdgcn_wave_barrier();
      const std::size_t tok = t_block + (wave_tok * kWaveTokTiles + j) * 16 +
                              (lane_id >> 1);
      const int row_l = (lane_id & 1) * 8;
      const std::size_t row = r_block + wave_row * 16 + row_l;
      if (tok < batch && row + 8 <= m && m % 4 == 0) {
        auto* dst = reinterpret_cast<float4*>(y + tok * m + row);
        const auto* src = reinterpret_cast<const float4*>(
            tile + (lane_id >> 1) * kOutputStride + row_l);
        dst[0] = src[0];
        dst[1] = src[1];
      } else if (tok < batch) {
#pragma unroll
        for (int q = 0; q < 8; ++q)
          if (row + q < m)
            y[tok * m + row + q] =
                tile[(lane_id >> 1) * kOutputStride + row_l + q];
      }
      __builtin_amdgcn_wave_barrier();
    }
  } else {
'''
    return source[:start] + single + paired + '\n  }' + source[end:]


def main():
    old = '''        (DenseF16GEMMKernel<64, 128, 2, 2, 4, 5, false, false, false, true>),
        dim3((batch + 127) / 128, 5), dim3(kThreads), 0, stream, w, x, out,
        batch, m, k);'''
    source = (BASE / REL).read_text()
    if source.count(old) != 1:
        raise ValueError('HC down differs from measured MoE/HC checkpoint')
    reports = {}
    for name, (bn, bk, wm, wn) in VARIANTS.items():
        out = ROOT / ('.deps/gufo-q2-bench-' + name)
        shutil.copytree(BASE, out)
        new = f'''        (DenseF16GEMMKernel<64, {bn}, {bk}, {wm}, {wn}, 5, false, false, false, true>),
        dim3((batch + {bn - 1}) / {bn}, 5), dim3(kThreads), 0, stream, w, x, out,
        batch, m, k);'''
        text = source.replace(old, new).replace(
            '    // Group all five row tiles around one 128-token input stripe. The\n'
            '    // original F16 full-batch input alone exceeds the 32 MiB cache.',
            f'    // Group five row tiles around a {bn}-token stripe; retain both\n'
            '    // ordered K16 accumulation chains with the selected wave plan.')
        if wm == 4:
            text = single_row_epilogue(text)
        path = out / REL
        path.write_text(text)
        subprocess.run(['clang-format', '-i', str(path)], check=True)
        delta = ''.join(difflib.unified_diff(source.splitlines(True),
                        path.read_text().splitlines(True),
                        fromfile='a/' + str(REL), tofile='b/' + str(REL)))
        patch = ROOT / ('experiments/q2-' + name + '.patch')
        patch.write_text(delta)
        changed = [str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file()
                   and p.read_bytes() != (out / p.relative_to(BASE)).read_bytes()]
        if changed != [str(REL)]:
            raise ValueError('Unexpected source changes')
        sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        reports[name] = dict(tile=[64, bn], k_blocks=bk, waves=[wm, wn],
                             file_count=sum(p.is_file() for p in BASE.rglob('*')),
                             changed_file=str(REL),
                             base_sha256=sha(BASE / REL),
                             candidate_sha256=sha(path), patch_sha256=sha(patch))
    result = dict(scope='Static hypotheses only; not GPU or model evidence',
                  official_gufo_pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
                  base='measured F32 MoE/HC fusion; excludes rejected norm copy',
                  variants=reports)
    (ROOT / 'config/q2-hc-down-tiles-source.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Prepared HC down scheduling candidates:', list(reports))


if __name__ == '__main__':
    main()
