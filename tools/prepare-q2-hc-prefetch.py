#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare isolated scalar HC down prefetch from the measured packed checkpoint."""
import difflib
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-packed'
OUT = ROOT / '.deps/gufo-q2-bench-hc-prefetch'


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
    after = '''// Original F16 HC down weights, four waves per row. Keep one four-value
// group in registers while fetching the next. The fixed 128-thread geometry
// covers exactly twenty groups; no lane-varying loop mask is needed.
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
  auto weights = *reinterpret_cast<const uint2*>(wrow + start);
  auto values = *reinterpret_cast<const float4*>(x + start);
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
  for (unsigned step = 1; step < steps; ++step) {
    const unsigned next = start + step * stride;
    const auto next_weights = *reinterpret_cast<const uint2*>(wrow + next);
    const auto next_values = *reinterpret_cast<const float4*>(x + next);
    // Keep the next loads ahead of the current arithmetic in the machine
    // scheduler. Without this boundary LLVM sinks them after the FMAs and
    // reuses the old registers, eliminating the intended overlap.
    __builtin_amdgcn_sched_barrier(0);
    acc = accumulate(weights, values, acc);
    weights = next_weights;
    values = next_values;
  }
  acc = accumulate(weights, values, acc);
'''
    if source.count(before) != 1:
        raise ValueError('HC down source differs from the measured checkpoint')
    path.write_text(source.replace(before, after))
    subprocess.run(['clang-format', '-i', str(path)], check=True)
    patch = ''.join(difflib.unified_diff((BASE / relative).read_text().splitlines(True),
                      path.read_text().splitlines(True), fromfile='a/' + str(relative),
                      tofile='b/' + str(relative)))
    (ROOT / 'experiments/q2-hc-prefetch.patch').write_text(patch)
    print('Prepared HC down prefetch:', relative)


if __name__ == '__main__':
    main()
