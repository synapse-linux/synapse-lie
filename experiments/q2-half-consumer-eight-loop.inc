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
