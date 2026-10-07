// SPDX-License-Identifier: MIT
// Derived from Gufo HcDownF16VecKernel and SiluScaleKernel, official pin
// f783fedb9bea2ec7de941f6da4e02f4a4596b29e. Original F16 weights/F32 math.
#include <hip/hip_fp16.h>
#include <hip/hip_runtime.h>

namespace gufo::models::qwen38_flash_next::rocm {
namespace {
__device__ __forceinline__ float SigmoidF(float x) {
  return 1.0f / (1.0f + __expf(-x));
}
__device__ __forceinline__ float SiluF(float x) {
  return x * SigmoidF(x);
}
__device__ __forceinline__ float WaveSum(float v) {
  for (int offset = warpSize / 2; offset > 0; offset >>= 1) {
    v += __shfl_xor(v, offset);
  }
  return v;
}
}  // namespace

template<bool kWitness>
__global__ void HcDownSiluKernel(const __half* w, const float* x, float* out,
                                 float* raw) {
  constexpr unsigned k = 10240, waves = 16;
  const unsigned row = blockIdx.x;
  const unsigned lane = threadIdx.x % 32;
  const unsigned wave = threadIdx.x / 32;
  const __half* wrow = w + std::size_t(row) * k;
  float acc = 0.0f;
  for (unsigned i = threadIdx.x * 4; i < k; i += waves * 32 * 4) {
    const uint2 packed = *reinterpret_cast<const uint2*>(wrow + i);
    const float4 v = *reinterpret_cast<const float4*>(x + i);
    const __half2 a = __builtin_bit_cast(__half2, packed.x);
    const __half2 b = __builtin_bit_cast(__half2, packed.y);
    // Retain the saved gfx1151 instruction order: components 3,1,2,0.
    // Explicit FMA prevents the fused epilogue from reassociating the dot.
    acc = __fmaf_rn(v.w, __half2float(__high2half(b)), acc);
    acc = __fmaf_rn(v.y, __half2float(__high2half(a)), acc);
    acc = __fmaf_rn(v.z, __half2float(__low2half(b)), acc);
    acc = __fmaf_rn(v.x, __half2float(__low2half(a)), acc);
  }
  __shared__ float partial[waves];
  const float reduced = WaveSum(acc);
  if (lane == 0)
    partial[wave] = reduced;
  __syncthreads();
  if (wave == 0) {
    const float total = WaveSum(lane < waves ? partial[lane] : 0.0f);
    if (lane == 0) {
      if constexpr (kWitness)
        raw[row] = total;
      // SiluScale applies its scale BEFORE SiLU, at the same F32 boundary.
      float scaled = __fmul_rn(total, 0.25f);
      // A register-only boundary also prevents fast-math from folding this
      // scale into __expf's multiplier. It emits no additional instruction.
      asm volatile("" : "+v"(scaled));
      out[row] = SiluF(scaled);
    }
  }
}

void HcDownSilu(const __half* w, const float* x, float* out, hipStream_t stream,
                float* raw) {
  if (raw) {
    hipLaunchKernelGGL((HcDownSiluKernel<true>), dim3(320), dim3(512), 0,
                       stream, w, x, out, raw);
  } else {
    hipLaunchKernelGGL((HcDownSiluKernel<false>), dim3(320), dim3(512), 0,
                       stream, w, x, out, nullptr);
  }
}
}  // namespace gufo::models::qwen38_flash_next::rocm
