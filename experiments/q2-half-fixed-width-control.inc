// SPDX-License-Identifier: MIT
// Literal measured1571 half-input consumer; no saved cohort rerun.
__global__ void HcCombineMoeHalfWidthControlKernel(
    float* res, const __half* expert_out, const float* weights,
    const float* shared_out, const float* gate, std::uint32_t gate_stride,
    std::uint32_t used, const float* inject, std::uint32_t inject_parts,
    const float* gamma, float* norm_scales, std::uint32_t hidden, float eps,
    __half* norm_half) {
  constexpr std::uint32_t kStreams = 4;
  constexpr std::uint32_t kMaxChunks = 10;  // 4 x 2560 / 4 / kThreads
  __shared__ float shared[kStreams][kThreads / 32];
  const std::uint32_t t = blockIdx.x;
  const std::size_t hc_dim = static_cast<std::size_t>(kStreams) * hidden;
  float w[kStreams];
#pragma unroll
  for (std::uint32_t s = 0; s < kStreams; ++s) {
    float logit = 0.0f;
    for (std::uint32_t p = 0; p < inject_parts; ++p) {
      logit +=
          inject[(static_cast<std::size_t>(t) * kStreams + s) * inject_parts +
                 p];
    }
    w[s] = 2.0f * SigmoidF(logit / static_cast<float>(kStreams));
  }
  float* dst = res + static_cast<std::size_t>(t) * hc_dim;
  __shared__ __attribute__((aligned(16))) float moe[2560];
  const float g = SigmoidF(gate[static_cast<std::size_t>(t) * gate_stride]);
  // SPDX-License-Identifier: MIT
  // hidden2560 and eight-value ownership preserve all per-value FMA chains.
  const bool aligned_experts =
      reinterpret_cast<std::uintptr_t>(expert_out) % 16 == 0;
  for (std::uint32_t i = threadIdx.x * 8; i < hidden; i += kThreads * 8) {
    float4 lo{0.0F, 0.0F, 0.0F, 0.0F}, hi{0.0F, 0.0F, 0.0F, 0.0F};
    const __half* rows =
        expert_out + static_cast<std::size_t>(t) * used * hidden + i;
    for (std::uint32_t s = 0; s < used; ++s) {
      const float wk = weights[t * used + s];
      const __half* p = rows + static_cast<std::size_t>(s) * hidden;
      float4 a, b;
      if (aligned_experts) {
        const uint4 packed = *reinterpret_cast<const uint4*>(p);
        const float2 x = __half22float2(__builtin_bit_cast(__half2, packed.x));
        const float2 y = __half22float2(__builtin_bit_cast(__half2, packed.y));
        const float2 z = __half22float2(__builtin_bit_cast(__half2, packed.z));
        const float2 w = __half22float2(__builtin_bit_cast(__half2, packed.w));
        a = float4{x.x, x.y, y.x, y.y};
        b = float4{z.x, z.y, w.x, w.y};
      } else {
        a = Load4(p);
        b = Load4(p + 4);
      }
      lo.x = __fmaf_rn(wk, a.x, lo.x);
      lo.y = __fmaf_rn(wk, a.y, lo.y);
      lo.z = __fmaf_rn(wk, a.z, lo.z);
      lo.w = __fmaf_rn(wk, a.w, lo.w);
      hi.x = __fmaf_rn(wk, b.x, hi.x);
      hi.y = __fmaf_rn(wk, b.y, hi.y);
      hi.z = __fmaf_rn(wk, b.z, hi.z);
      hi.w = __fmaf_rn(wk, b.w, hi.w);
    }
    const float* sh = shared_out + static_cast<std::size_t>(t) * hidden + i;
    const float4 a = *reinterpret_cast<const float4*>(sh);
    const float4 b = *reinterpret_cast<const float4*>(sh + 4);
    lo.x = __fmaf_rn(g, a.x, lo.x);
    lo.y = __fmaf_rn(g, a.y, lo.y);
    lo.z = __fmaf_rn(g, a.z, lo.z);
    lo.w = __fmaf_rn(g, a.w, lo.w);
    hi.x = __fmaf_rn(g, b.x, hi.x);
    hi.y = __fmaf_rn(g, b.y, hi.y);
    hi.z = __fmaf_rn(g, b.z, hi.z);
    hi.w = __fmaf_rn(g, b.w, hi.w);
    *reinterpret_cast<float4*>(moe + i) = lo;
    *reinterpret_cast<float4*>(moe + i + 4) = hi;
  }
  // All lanes finish the shared row before any stream reads it.
  __syncthreads();
  const float* src = moe;
  const std::uint32_t chunks = static_cast<std::uint32_t>(hc_dim / 4);
  float4 v[kMaxChunks];
  float ss[kStreams] = {0.0F, 0.0F, 0.0F, 0.0F};
#pragma unroll
  for (std::uint32_t c = 0; c < kMaxChunks; ++c) {
    const std::uint32_t e = (c * kThreads + threadIdx.x) * 4;
    v[c] = float4{0.0F, 0.0F, 0.0F, 0.0F};
    if (e < hc_dim) {
      const std::uint32_t s = e / hidden;
      const std::uint32_t i = e - (s * hidden);
      const float ws = w[s];
      const float4 r = *reinterpret_cast<const float4*>(dst + e);
      const float4 b = *reinterpret_cast<const float4*>(src + i);
      v[c] = float4{r.x + b.x * ws, r.y + b.y * ws, r.z + b.z * ws,
                    r.w + b.w * ws};
      *reinterpret_cast<float4*>(dst + e) = v[c];
      // Retain the measured F32 sum-of-squares contraction order.
      const float sq = __fmaf_rn(
          v[c].x, v[c].x,
          __fmaf_rn(v[c].z, v[c].z,
                    __fmaf_rn(v[c].y, v[c].y, __fmul_rn(v[c].w, v[c].w))));
#pragma unroll
      for (std::uint32_t k = 0; k < kStreams; ++k) {
        ss[k] += (k == s) ? sq : 0.0F;
      }
    }
  }
  if (gamma == nullptr) {
    return;
  }
  const std::uint32_t lane = threadIdx.x & 31u;
  const std::uint32_t wave = threadIdx.x >> 5u;
#pragma unroll
  for (std::uint32_t k = 0; k < kStreams; ++k) {
    ss[k] = WaveSum(ss[k]);
    if (lane == 0) {
      shared[k][wave] = ss[k];
    }
  }
  __syncthreads();
  float scale[kStreams];
#pragma unroll
  for (std::uint32_t k = 0; k < kStreams; ++k) {
    float total = 0.0F;
    for (std::uint32_t q = 0; q < kThreads / 32; ++q) {
      total += shared[k][q];
    }
    scale[k] = rsqrtf(total / static_cast<float>(hidden) + eps);
  }
  if (threadIdx.x == 0) {
    *reinterpret_cast<float4*>(norm_scales + std::size_t(t) * 4) =
        float4{scale[0], scale[1], scale[2], scale[3]};
  }
#pragma unroll
  for (std::uint32_t c = 0; c < kMaxChunks; ++c) {
    const std::uint32_t e = (c * kThreads + threadIdx.x) * 4;
    // Every lane of the wave takes part in the block reductions below, so
    // lanes past the row carry zeros instead of leaving.
    float4 n{0.0F, 0.0F, 0.0F, 0.0F};
    if (e < hc_dim) {
      const std::uint32_t s = e / hidden;
      const float sc = scale[s];
      const float4 gm = *reinterpret_cast<const float4*>(gamma + e);
      n = DeferredHcNormValue(v[c], sc, gm);
      // Anchor F32 rounding before conversion. Without this barrier
      // fast-math can emit a mixed FMA rounding directly into F16.
      asm("" : "+v"(n.x), "+v"(n.y), "+v"(n.z), "+v"(n.w));
      if (norm_half != nullptr) {
        __half* half = norm_half + (static_cast<std::size_t>(t) * hc_dim) + e;
        *reinterpret_cast<__half2*>(half) = __floats2half2_rn(n.x, n.y);
        *reinterpret_cast<__half2*>(half + 2) = __floats2half2_rn(n.z, n.w);
      }
    }
  }
}
