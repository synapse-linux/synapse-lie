// SPDX-License-Identifier: MIT
// Private scalar HC fusion derived from the retained Gufo F16 up projection
// and HC mixer. Original weight bytes, dot products and injection layout.
template<bool kWitness>
__global__ void HcScalarUpMixKernel(const __half* w, const float* lo,
                                    const float* xn, const float* inject_w,
                                    float* mixed, float* inject, float* gates) {
  constexpr unsigned kHidden = 2560, kRank = 320, kStreams = 4;
  constexpr unsigned kWaves = 8, kParts = kHidden / 256;
  const unsigned lane = threadIdx.x & 31;
  const unsigned wave = threadIdx.x >> 5;
  const unsigned h = blockIdx.x * kWaves + wave;
  float acc[kStreams]{};
#pragma unroll
  for (unsigned step = 0; step < 3; ++step) {
    if (step == 2 && lane >= 16)
      continue;
    const unsigned i = step * 128 + lane * 4;
    const float4 x = *reinterpret_cast<const float4*>(lo + i);
#pragma unroll
    for (unsigned s = 0; s < kStreams; ++s) {
      const __half* row = w + std::size_t(s * kHidden + h) * kRank;
      const uint2 packed = *reinterpret_cast<const uint2*>(row + i);
      const __half2 a = __builtin_bit_cast(__half2, packed.x);
      const __half2 b = __builtin_bit_cast(__half2, packed.y);
      acc[s] = __fmaf_rn(__half2float(__low2half(a)), x.x, acc[s]);
      acc[s] = __fmaf_rn(__half2float(__high2half(a)), x.y, acc[s]);
      acc[s] = __fmaf_rn(__half2float(__low2half(b)), x.z, acc[s]);
      acc[s] = __fmaf_rn(__half2float(__high2half(b)), x.w, acc[s]);
    }
  }
#pragma unroll
  for (unsigned s = 0; s < kStreams; ++s)
    acc[s] = WaveSum(acc[s]);
  if (lane == 0) {
    float value = 0.0f;
#pragma unroll
    for (unsigned s = 0; s < kStreams; ++s) {
      if constexpr (kWitness)
        gates[s * kHidden + h] = acc[s];
      value = __fmaf_rn(xn[s * kHidden + h], SigmoidF(acc[s]), value);
    }
    mixed[h] = value / static_cast<float>(kStreams);
  }
  // Ten designated blocks own exactly the original 256-hidden-element
  // injection slices. All threads in those blocks execute the old wave and
  // increasing-wave reductions. No gate or mixed result feeds this branch.
  if (inject_w == nullptr || blockIdx.x >= kParts)
    return;
  const unsigned i = blockIdx.x * 256 + threadIdx.x;
  float v[kStreams];
#pragma unroll
  for (unsigned s = 0; s < kStreams; ++s)
    v[s] = xn[s * kHidden + i];
  __shared__ float partial[kStreams][kWaves];
#pragma unroll
  for (unsigned o = 0; o < kStreams; ++o) {
    float dot = 0.0f;
#pragma unroll
    for (unsigned s = 0; s < kStreams; ++s)
      dot = __fmaf_rn(inject_w[(o * kStreams + s) * kHidden + i], v[s], dot);
    dot = WaveSum(dot);
    if (lane == 0)
      partial[o][wave] = dot;
  }
  __syncthreads();
  if (threadIdx.x < kStreams) {
    float total = 0.0f;
#pragma unroll
    for (unsigned wv = 0; wv < kWaves; ++wv)
      total = __fadd_rn(total, partial[threadIdx.x][wv]);
    inject[threadIdx.x * kParts + blockIdx.x] = total;
  }
}

void HcScalarUpMix(const __half* w, const float* lo, const float* xn,
                   const float* inject_w, float* mixed, float* inject,
                   hipStream_t stream, float* gate_witness = nullptr) {
  if (gate_witness != nullptr) {
    hipLaunchKernelGGL((HcScalarUpMixKernel<true>), dim3(320), dim3(256), 0,
                       stream, w, lo, xn, inject_w, mixed, inject,
                       gate_witness);
  } else {
    hipLaunchKernelGGL((HcScalarUpMixKernel<false>), dim3(320), dim3(256), 0,
                       stream, w, lo, xn, inject_w, mixed, inject, nullptr);
  }
}
