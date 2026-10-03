// SPDX-License-Identifier: MIT
// Static gfx1151 lowering probe, not a model kernel or throughput benchmark.
#include <cstdint>
#include <hip/hip_fp16.h>
#include <hip/hip_runtime.h>

struct Q2Fields {
  std::uint32_t discarded : 6;
  std::uint32_t code : 2;
  std::uint32_t upper : 24;
};

struct FloatFields {
  std::uint32_t mantissa : 23;
  std::uint32_t exponent : 8;
  std::uint32_t sign : 1;
};

union WordView {
  Q2Fields q2;
  FloatFields fp;
  std::uint32_t word;
  float value;
};

static_assert(sizeof(Q2Fields) == 4);
static_assert(sizeof(FloatFields) == 4);
static_assert(sizeof(WordView) == 4);

extern "C" __global__ void extract_shift(const std::uint32_t *in,
                                         std::uint32_t *out) {
  const unsigned i = blockIdx.x * blockDim.x + threadIdx.x;
  out[i] = (in[i] >> 6U) & 3U;
}

extern "C" __global__ void extract_fields(const std::uint32_t *in,
                                          std::uint32_t *out) {
  const unsigned i = blockIdx.x * blockDim.x + threadIdx.x;
  // Keep the active union member explicit. Representation transfer uses
  // bit_cast, rather than a C++ read of an inactive union member.
  WordView view{.q2 = __builtin_bit_cast(Q2Fields, in[i])};
  out[i] = view.q2.code;
}

extern "C" __global__ void fixed_native(const std::uint32_t *in, float *out) {
  const unsigned i = blockIdx.x * blockDim.x + threadIdx.x;
  out[i] = float(in[i] & 255U) * 0.0625F;
}

extern "C" __global__ void fixed_bits(const std::uint32_t *in, float *out) {
  const unsigned i = blockIdx.x * blockDim.x + threadIdx.x;
  // For q in [0,255], this constructs 2^19 + q/16 exactly in binary32.
  out[i] = __builtin_bit_cast(float, 0x49000000U | (in[i] & 255U)) - 524288.0F;
}

extern "C" __global__ void fixed_fields(const std::uint32_t *in, float *out) {
  const unsigned i = blockIdx.x * blockDim.x + threadIdx.x;
  WordView view{.fp = {in[i] & 255U, 146U, 0U}};
  out[i] = __builtin_bit_cast(float, view.fp) - 524288.0F;
}

extern "C" __global__ void pair_native(const std::uint32_t *in,
                                       std::uint32_t *out) {
  const unsigned i = blockIdx.x * blockDim.x + threadIdx.x;
  const std::uint32_t q = in[i];
  out[i] = __builtin_bit_cast(
      std::uint32_t, __floats2half2_rn(float(q & 3U), float((q >> 8U) & 3U)));
}

extern "C" __global__ void pair_bits(const std::uint32_t *in,
                                     std::uint32_t *out) {
  const unsigned i = blockIdx.x * blockDim.x + threadIdx.x;
  const std::uint32_t q = in[i];
  const std::uint32_t bits = (q & 3U) | ((q & 0x300U) << 8U) | 0x64006400U;
  const __half2 value = __hadd2(__builtin_bit_cast(__half2, bits),
                                __floats2half2_rn(-1024.0F, -1024.0F));
  out[i] = __builtin_bit_cast(std::uint32_t, value);
}
