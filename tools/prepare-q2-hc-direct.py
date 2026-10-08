#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare direct-register HC down WMMA against the measured Q2 palette."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-affine-palette'
OUT = ROOT / '.deps/gufo-q2-bench-hc-direct'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')
EXPECTED = '4de114a41d58e2b6f74038abfbf27bef8dc285dadf4b95ef69ae3b51b6b8a9fe'
KERNEL = r'''
// Original F16 HC down: load WMMA fragments directly into registers. The
// same 64x128 tiles and two ordered K16 accumulation chains are retained;
// LDS is used only for the final per-wave output transpose.
__launch_bounds__(256) __global__ void HcDownF16DirectKernel(
    const __half* __restrict__ w, const __half* __restrict__ x,
    float* __restrict__ y, std::size_t batch) {
  constexpr unsigned k = 10240, m = 320, bn = 128;
  constexpr unsigned stride = 36;
  __shared__ __attribute__((aligned(16))) float scratch[8 * 16 * stride];
  const unsigned tid = threadIdx.x;
  const unsigned wave = tid >> 5, lane = tid & 31;
  const unsigned sub = lane & 15, half = lane >> 4;
  const unsigned wave_row = wave / 4, wave_tok = wave % 4;
  // Group all five row tiles around one input stripe, as in the reference.
  const unsigned within = blockIdx.y * gridDim.x + blockIdx.x;
  const unsigned row_block = (within % 5) * 64;
  const std::size_t token_block = std::size_t(within / 5) * bn;
  const __half* weights[2];
  const __half* inputs[2];
  bool live[2];
#pragma unroll
  for (unsigned i = 0; i < 2; ++i) {
    const unsigned row = row_block + (wave_row * 2 + i) * 16 + sub;
    weights[i] = w + std::size_t(row) * k;
    const std::size_t token = token_block + (wave_tok * 2 + i) * 16 + sub;
    live[i] = token < batch;
    inputs[i] = live[i] ? x + token * k : x;
  }
  v8f low[2][2]{}, high[2][2]{};
  for (unsigned offset = 0; offset < k; offset += 32) {
    v16h a_low[2], a_high[2];
#pragma unroll
    for (unsigned i = 0; i < 2; ++i) {
      a_low[i] = LoadFrag(weights[i] + offset);
      a_high[i] = LoadFrag(weights[i] + offset + 16);
    }
#pragma unroll
    for (unsigned j = 0; j < 2; ++j) {
      const v16h b_low = live[j] ? LoadFrag(inputs[j] + offset) : v16h{};
      const v16h b_high = live[j] ? LoadFrag(inputs[j] + offset + 16) : v16h{};
#pragma unroll
      for (unsigned i = 0; i < 2; ++i) {
        low[i][j] = Wmma(a_low[i], b_low, low[i][j]);
        high[i][j] = Wmma(a_high[i], b_high, high[i][j]);
      }
    }
  }
#pragma unroll
  for (unsigned i = 0; i < 2; ++i) {
#pragma unroll
    for (unsigned j = 0; j < 2; ++j)
      low[i][j] += high[i][j];
  }
  float* tile = scratch + wave * 16 * stride;
#pragma unroll
  for (unsigned j = 0; j < 2; ++j) {
#pragma unroll
    for (unsigned q = 0; q < 8; ++q) {
      tile[sub * stride + 2 * q + half] = low[0][j][q];
      tile[sub * stride + 16 + 2 * q + half] = low[1][j][q];
    }
    __builtin_amdgcn_wave_barrier();
    const std::size_t token = token_block + (wave_tok * 2 + j) * 16 + lane / 2;
    const unsigned row = row_block + wave_row * 32 + (lane & 1) * 16;
    if (token < batch) {
      const auto* src = reinterpret_cast<const float4*>(
          tile + (lane / 2) * stride + (lane & 1) * 16);
      auto* dst = reinterpret_cast<float4*>(y + token * m + row);
#pragma unroll
      for (unsigned q = 0; q < 4; ++q)
        dst[q] = src[q];
    }
    __builtin_amdgcn_wave_barrier();
  }
}

'''


def main():
    original = (BASE / REL).read_text()
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if sha(BASE / REL) != EXPECTED:
        raise ValueError('Measured affine-palette base changed')
    anchor = 'bool UnquantizedF16Gemm(const void* w, const __half* x, float* out,'
    old = '''    hipLaunchKernelGGL(
        (DenseF16GEMMKernel<64, 128, 2, 2, 4, 5, false, false, false, true>),
        dim3((batch + 127) / 128, 5), dim3(kThreads), 0, stream, w, x, out,
        batch, m, k);'''
    new = '''    hipLaunchKernelGGL(HcDownF16DirectKernel,
                       dim3((batch + 127) / 128, 5), dim3(kThreads), 0,
                       stream, static_cast<const __half*>(w), x, out, batch);'''
    if original.count(anchor) != 1 or original.count(old) != 1:
        raise ValueError('Unexpected HC down launch boundary')
    changed = original.replace(anchor, KERNEL + anchor).replace(old, new)
    shutil.copytree(BASE, OUT)
    target = OUT / REL
    target.write_text(changed)
    subprocess.run(['clang-format', '-i', str(target)], check=True)
    changed_files = sorted(str(p.relative_to(BASE)) for p in BASE.rglob('*')
                           if p.is_file() and p.read_bytes() != (OUT / p.relative_to(BASE)).read_bytes())
    if changed_files != [str(REL)]:
        raise ValueError('Unexpected changed source inventory')
    patch = ROOT / 'experiments/q2-hc-direct.patch'
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True),
        target.read_text().splitlines(True), fromfile='a/' + str(REL), tofile='b/' + str(REL))))
    report = dict(scope='Prepared source; runtime performance and numerical replay unproven',
        pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
        base=str(BASE.relative_to(ROOT)), candidate=str(OUT.relative_to(ROOT)),
        base_sha256=sha(BASE / REL), candidate_sha256=sha(target), patch_sha256=sha(patch),
        changed_files=changed_files, mechanism='Direct global-to-register WMMA fragments; LDS only for output transpose',
        dispatch='F16 M320/K10240, n>=96; existing 64x128 tile and five-row grouping',
        numeric_contract='Original half weights, two ordered K16 chains, final F32 addition and output layout',
        limit='Additional repeated global reads may outweigh removed staging/synchronization; no benefit assumed')
    (ROOT / 'config/q2-hc-direct-source.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
