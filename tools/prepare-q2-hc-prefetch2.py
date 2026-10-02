#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare two-group scalar HC down prefetch from the measured packed checkpoint."""
import difflib
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-packed'
OUT = ROOT / '.deps/gufo-q2-bench-hc-prefetch2'


def main():
    shutil.copytree(BASE, OUT)
    relative = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')
    path = OUT / relative
    source = path.read_text()
    before = '''// Original F16 HC down weights, four waves cooperating on each long row.
// FP32 products/accumulation and a small shared reduction; no weight
// conversion.
__global__ void HcDownF16VecKernel(const __half* w, const float* x,
                                   float* out) {
  constexpr unsigned k = 10240;
  constexpr unsigned waves = 4;
  const unsigned row = blockIdx.x;
  const unsigned lane = threadIdx.x % 32;
  const unsigned wave = threadIdx.x / 32;
  const __half* wrow = w + std::size_t(row) * k;
  float acc = 0.0f;
  for (unsigned i = threadIdx.x * 4; i < k; i += waves * 32 * 4) {
    float dot = 0.0f;
#pragma unroll
    for (unsigned j = 0; j < 4; ++j) {
      dot += __half2float(wrow[i + j]) * x[i + j];
    }
    acc += dot;
  }
'''
    after = '''// Original F16 HC down weights, four waves per row. Keep two four-value
// groups in registers while fetching the next two. The fixed 128-thread
// geometry covers exactly ten pairs; no lane-varying loop mask is needed.
__launch_bounds__(128) __global__ void HcDownF16VecKernel(
    const __half* w, const float* x, float* out) {
  constexpr unsigned k = 10240;
  constexpr unsigned waves = 4;
  constexpr unsigned stride = waves * 32 * 4;
  constexpr unsigned steps = k / stride;
  const unsigned row = blockIdx.x;
  const unsigned lane = threadIdx.x % 32;
  const unsigned wave = threadIdx.x / 32;
  const __half* wrow = w + std::size_t(row) * k;
  const unsigned start = threadIdx.x * 4;
  auto weights0 = *reinterpret_cast<const uint2*>(wrow + start);
  auto values0 = *reinterpret_cast<const float4*>(x + start);
  auto weights1 = *reinterpret_cast<const uint2*>(wrow + start + stride);
  auto values1 = *reinterpret_cast<const float4*>(x + start + stride);
  // Match the measured baseline's gfx1151 FMA sequence, not the reassociated
  // source expression: components 3, 1, 2, 0 feed the same accumulator.
  // Explicit RN intrinsics prevent fast-math from choosing another tree.
  const auto accumulate = [](uint2 packed, float4 input, float acc) {
    const __half2 a = __builtin_bit_cast(__half2, packed.x);
    const __half2 b = __builtin_bit_cast(__half2, packed.y);
    acc = __fmaf_rn(input.w, __half2float(__high2half(b)), acc);
    acc = __fmaf_rn(input.y, __half2float(__high2half(a)), acc);
    acc = __fmaf_rn(input.z, __half2float(__low2half(b)), acc);
    return __fmaf_rn(input.x, __half2float(__low2half(a)), acc);
  };
  float acc = 0.0f;
#pragma unroll 1
  for (unsigned step = 2; step < steps; step += 2) {
    const unsigned next0 = start + step * stride;
    const unsigned next1 = next0 + stride;
    const auto next_weights0 = *reinterpret_cast<const uint2*>(wrow + next0);
    const auto next_values0 = *reinterpret_cast<const float4*>(x + next0);
    const auto next_weights1 = *reinterpret_cast<const uint2*>(wrow + next1);
    const auto next_values1 = *reinterpret_cast<const float4*>(x + next1);
    // Hold both next-group loads above the ordered arithmetic. A single
    // lookahead left too little work to hide their latency on gfx1151.
    __builtin_amdgcn_sched_barrier(0);
    acc = accumulate(weights0, values0, acc);
    acc = accumulate(weights1, values1, acc);
    weights0 = next_weights0;
    values0 = next_values0;
    weights1 = next_weights1;
    values1 = next_values1;
  }
  acc = accumulate(weights0, values0, acc);
  acc = accumulate(weights1, values1, acc);
'''
    if source.count(before) != 1:
        raise ValueError('HC down source differs from the measured checkpoint')
    path.write_text(source.replace(before, after))
    subprocess.run(['clang-format', '-i', str(path)], check=True)
    patch = ''.join(difflib.unified_diff((BASE / relative).read_text().splitlines(True),
                      path.read_text().splitlines(True), fromfile='a/' + str(relative),
                      tofile='b/' + str(relative)))
    (ROOT / 'experiments/q2-hc-prefetch2.patch').write_text(patch)
    print('Prepared two-group HC down prefetch:', relative)


if __name__ == '__main__':
    main()
