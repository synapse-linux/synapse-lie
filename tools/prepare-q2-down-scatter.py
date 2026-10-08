#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare a padded, cooperative F32 epilogue for packed Q2 expert down."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-up-chains'
OUT = ROOT / '.deps/gufo-q2-bench-down-scatter'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')
EXPECTED = 'a5ccc81f7762beae74cf0bbb06e6aeebd44edf1c804c1473b63619af023a6cd5'


def main():
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if sha(BASE / REL) != EXPECTED:
        raise ValueError('Retained paired-HC-up source changed')
    original = (BASE / REL).read_text()
    anchor = '''  // One wave writes a complete 128-byte line of F16 output. Padding the
  // shared row by two floats also makes the accumulator scatter conflict-free.'''
    if original.count(anchor) != 1:
        raise ValueError('Unexpected routed epilogue anchor')
    epilogue = '''  if constexpr (kQ2 && kPacked && BN >= 48) {
    // Reuse the existing stage allocation for the complete F32 row tile.
    // A two-float pad distributes the WMMA scatter across all LDS banks;
    // each wave then writes 64 consecutive output columns with float2 stores.
    // This only moves already-rounded results: both WMMA sums and their
    // residual correction above retain the original arithmetic order.
    constexpr unsigned stride = BM + 2;
    static_assert(kLdsBytes >= 16 * stride * sizeof(float));
    float* scratch = reinterpret_cast<float*>(lds);
#pragma unroll
    for (int j = 0; j < kTokTiles; ++j) {
#pragma unroll
      for (int u = 0; u < kWaveRowTiles; ++u) {
#pragma unroll
        for (int l = 0; l < 8; ++l)
          scratch[sub_lane * stride + wave_id * 16 + u * 128 + 2 * l +
                  half_id] = acc[u][j][l];
      }
      __syncthreads();
#pragma unroll
      for (int round = 0; round < 16 * BM / (256 * 2); ++round) {
        const unsigned flat = (round * 256 + tid) * 2;
        const unsigned tr = flat / BM, row = flat % BM;
        const unsigned t = t_local + j * 16 + tr, r = r_block + row;
        if (t < unsigned(bucket_rows) && r < m) {
          const int dst = rows_out[bucket_begin + t];
          if (dst >= 0) {
            const float2 v =
                *reinterpret_cast<const float2*>(scratch + tr * stride + row);
            const std::size_t offset = std::size_t(dst) * m + r;
            if (m % 2 == 0 && r + 1 < m)
              *reinterpret_cast<float2*>(out + offset) = v;
            else {
              out[offset] = v.x;
              if (r + 1 < m)
                out[offset + 1] = v.y;
            }
          }
        }
      }
      __syncthreads();
    }
    return;
  }

'''
    changed = original.replace(anchor, epilogue + anchor)
    shutil.copytree(BASE, OUT)
    target = OUT / REL
    target.write_text(changed)
    subprocess.run(['clang-format', '-i', str(target)], check=True)
    inventory = sorted(str(p.relative_to(BASE)) for p in BASE.rglob('*')
                       if p.is_file() and p.read_bytes() !=
                       (OUT / p.relative_to(BASE)).read_bytes())
    if inventory != [str(REL)]:
        raise ValueError('Unexpected changed inventory')
    patch = ROOT / 'experiments/q2-down-scatter.patch'
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True),
        target.read_text().splitlines(True), fromfile='a/' + str(REL),
        tofile='b/' + str(REL))))
    report = dict(scope='Prepared source; GPU exactness and performance unproven',
        pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
        base=str(BASE.relative_to(ROOT)), candidate=str(OUT.relative_to(ROOT)),
        changed_files=inventory, base_sha256=sha(BASE / REL),
        candidate_sha256=sha(target), patch_sha256=sha(patch),
        mechanism='Packed Q2 BN48/64 uses padded block-wide F32 transpose and float2 scatter in existing LDS',
        arithmetic='Original affine palette, high/residual planes, ordered WMMA accumulation and final correction retained',
        unchanged='Weight/model bytes, activation layout, allocation sizes, raw F32-input control, BN16, IQ2 gate/up, HC, scalar decode and public ABI',
        qualification='Complete exact output replay, existing independent FP64 checks and useful complete-model benefit required',
        model_conversion=False, persistent_decoded_weight_cache=False)
    (ROOT / 'config/q2-down-scatter-source.json').write_text(
        json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
