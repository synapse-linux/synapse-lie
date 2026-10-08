#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stage each HC input stripe once for all 320 output rows."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-up-chains'
OUT = ROOT / '.deps/gufo-q2-bench-hc-full-row'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')
EXPECTED = 'a5ccc81f7762beae74cf0bbb06e6aeebd44edf1c804c1473b63619af023a6cd5'


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Unexpected retained source: ' + old[:90])
    return text.replace(old, new)


def main():
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if sha(BASE / REL) != EXPECTED:
        raise ValueError('Retained paired-HC-up source changed')
    original = (BASE / REL).read_text()
    start = original.index('template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,')
    end = original.index('\nbool AttentionF16Gemm(', start)
    body = original[start:end]
    epilogue = body.index('  // Transpose the result through LDS, two row tiles at a time,')
    closing = body.rindex('\n}')
    special = '''  if constexpr (kHalfWeights && !kHcMix && !kSsmConv && !kAttention &&
                !kHcUpChains && BM == 320 && BN == 32) {
    // Five row tiles per wave: the final tile has only sixteen rows.
    // Keep the original epilogue untouched in every other specialization.
    static_assert(kWaveRowTiles == 5 && kWaveTokTiles == 1);
    constexpr unsigned stride = 36;
    float* tile = reinterpret_cast<float*>(s_lds) + wave_id * 16 * stride;
#pragma unroll
    for (int i = 0; i < kWaveRowTiles; i += 2) {
#pragma unroll
      for (int l = 0; l < 8; ++l) {
        tile[sub_lane * stride + 2 * l + half_id] = acc[i][0][l];
        if (i + 1 < kWaveRowTiles)
          tile[sub_lane * stride + 16 + 2 * l + half_id] = acc[i + 1][0][l];
      }
      __builtin_amdgcn_wave_barrier();
      const int tok_l = lane_id >> 1;
      const int row_l = (lane_id & 1) * 16;
      const std::size_t tok = t_block + wave_tok * 16 + tok_l;
      const std::size_t row = r_block + (wave_row * kWaveRowTiles + i) * 16 + row_l;
      if (tok < batch && row + 16 <= m &&
          (i + 1 < kWaveRowTiles || row_l == 0)) {
        const auto* src = reinterpret_cast<const float4*>(tile + tok_l * stride + row_l);
        auto* dst = reinterpret_cast<float4*>(y + tok * m + row);
#pragma unroll
        for (int q = 0; q < 4; ++q)
          dst[q] = src[q];
      }
      __builtin_amdgcn_wave_barrier();
    }
  } else {
'''
    body = body[:epilogue] + special + body[epilogue:closing] + '\n  }' + body[closing:]
    changed = original[:start] + body + original[end:]
    changed = once(changed,
        '    // Group all five row tiles around one 128-token input stripe. The\n'
        '    // original F16 full-batch input alone exceeds the 32 MiB cache.\n'
        '    hipLaunchKernelGGL(\n'
        '        (DenseF16GEMMKernel<64, 128, 2, 2, 4, 5, false, false, false, true>),\n'
        '        dim3((batch + 127) / 128, 5), dim3(kThreads), 0, stream, w, x, out,\n'
        '        batch, m, k);',
        '    // One row tile shares every input stripe across all 320 outputs.\n'
        '    // Narrower token tiles retain 64 independent blocks at n2048.\n'
        '    // Both ordered K16 accumulator chains and original weights remain.\n'
        '    hipLaunchKernelGGL(\n'
        '        (DenseF16GEMMKernel<320, 32, 2, 4, 2, 1, false, false, false, true>),\n'
        '        dim3((batch + 31) / 32, 1), dim3(kThreads), 0, stream, w, x, out,\n'
        '        batch, m, k);')
    shutil.copytree(BASE, OUT)
    target = OUT / REL
    target.write_text(changed)
    subprocess.run(['clang-format', '-i', str(target)], check=True)
    inventory = sorted(str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file()
                       and p.read_bytes() != (OUT / p.relative_to(BASE)).read_bytes())
    if inventory != [str(REL)]:
        raise ValueError('Unexpected changed inventory')
    patch = ROOT / 'experiments/q2-hc-full-row.patch'
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True),
        target.read_text().splitlines(True), fromfile='a/' + str(REL), tofile='b/' + str(REL))))
    report = dict(scope='Prepared full-row HC source; exactness and performance unproven',
        pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
        base=str(BASE.relative_to(ROOT)), candidate=str(OUT.relative_to(ROOT)),
        changed_files=inventory, base_sha256=sha(BASE / REL), candidate_sha256=sha(target),
        patch_sha256=sha(patch),
        dispatch='Original F16 HC down M320/K10240, n>=96; BM320/BN32/BK2/WM4/WN2, 256 threads',
        arithmetic='Original half weights and narrowed inputs, both ordered K16 chains, final F32 low+high sum unchanged',
        mechanism='Stage inputs once for all output rows; five result row tiles per wave with bounded unpaired epilogue',
        tradeoff='At n2048 logical input staging falls fivefold, weight staging rises fourfold, block count 80 to 64, LDS 24576 to 45056 bytes; no physical traffic or speed claim',
        unchanged='Paired HC up, scalar decode, routed IQ2/Q2, PLE, original model files and public ABI',
        numerical_limits_changed=False, model_conversion=False, promoted=False)
    (ROOT / 'config/q2-hc-full-row-source.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
