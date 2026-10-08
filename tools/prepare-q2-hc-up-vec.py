#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare an isolated scalar HC up vector-load candidate from fused Q2."""
import difflib
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-up-fused'
OUT = ROOT / '.deps/gufo-q2-bench-hc-up-vec'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')


def once(source, before, after):
    if source.count(before) != 1:
        raise ValueError('Measured HC up checkpoint differs: ' + before[:80])
    return source.replace(before, after)


def main():
    shutil.copytree(BASE, OUT)
    path = OUT / REL
    source = path.read_text()
    kernel = '''// Original F16 HC up weights: one wave per output row, with aligned
// eight-byte weight and sixteen-byte activation loads. The last 64 values
// occupy only lanes 0..15. Preserve the generic dot and wave reduction.
__global__ void HcUpF16VecKernel(const __half* w, const float* x,
                                 float* out) {
  constexpr unsigned k = 320;
  const unsigned lane = threadIdx.x % warpSize;
  const unsigned row = blockIdx.x * 4 + threadIdx.x / warpSize;
  const __half* wrow = w + std::size_t(row) * k;
  float acc = 0.0f;
#pragma unroll
  for (unsigned step = 0; step < 3; ++step) {
    if (step == 2 && lane >= 16) {
      continue;
    }
    const unsigned i = step * 128 + lane * 4;
    const uint2 packed = *reinterpret_cast<const uint2*>(wrow + i);
    const float4 value = *reinterpret_cast<const float4*>(x + i);
    const __half2 lo = __builtin_bit_cast(__half2, packed.x);
    const __half2 hi = __builtin_bit_cast(__half2, packed.y);
    float dot = 0.0f;
    dot += __half2float(__low2half(lo)) * value.x;
    dot += __half2float(__high2half(lo)) * value.y;
    dot += __half2float(__low2half(hi)) * value.z;
    dot += __half2float(__high2half(hi)) * value.w;
    acc += dot;
  }
  const float total = WaveSum(acc);
  if (lane == 0) {
    out[row] = total;
  }
}

'''
    source = once(source, '// Original F16 HC down weights, four waves',
                  kernel + '// Original F16 HC down weights, four waves')
    dispatch = '''  if (type == WeightType::kF16 && n_tokens == 1 && m == 320 && k == 10240) {'''
    source = once(source, dispatch,
        '''  if (type == WeightType::kF16 && n_tokens == 1 && m == 10240 &&
      k == 320) {
    hipLaunchKernelGGL(HcUpF16VecKernel, dim3(10240 / 4), dim3(128), 0,
                       stream, static_cast<const __half*>(w), x, out);
    return;
  }
''' + dispatch)
    path.write_text(source)
    subprocess.run(['clang-format', '-i', str(path)], check=True)
    patch = ''.join(difflib.unified_diff((BASE / REL).read_text().splitlines(True),
                    path.read_text().splitlines(True), fromfile='a/' + str(REL),
                    tofile='b/' + str(REL)))
    (ROOT / 'experiments/q2-hc-up-vec.patch').write_text(patch)
    print('Prepared scalar HC up vector-load candidate:', REL)


if __name__ == '__main__':
    main()
