// SPDX-License-Identifier: MIT
// Mirrors exactly the retained prefill operand conversion, not a new
// quantization. Layout: [expert][K/16][output row][16 half weights].
template<bool IQ2>
__global__ void ConvertExpertCacheKernel(const std::uint8_t* encoded,
                                        __half* output, std::size_t groups,
                                        std::uint32_t m, std::uint32_t k) {
  const std::size_t group = std::size_t(blockIdx.x) * blockDim.x + threadIdx.x;
  if (group >= groups) return;
  const unsigned col = (group % (k / 4)) * 4;
  const std::size_t erow = group / (k / 4);
  const unsigned row = erow % m;
  const std::size_t expert = erow / m;
  const auto* block = encoded + erow * ((k + 255) / 256) * (IQ2 ? 66 : 84)
                      + (col / 256) * (IQ2 ? 66 : 84);
  __half2 lo, hi;
  if constexpr (IQ2) {
    const unsigned sub = (col % 256) / 32;
    uint2 raw;
    __half d;
    __builtin_memcpy(&raw, block + 2 + sub * 8, 8);
    __builtin_memcpy(&d, block, 2);
    const unsigned part = (col % 32) / 8;
    const unsigned code = (raw.x >> (8 * part)) & 255U;
    const unsigned sign = (raw.y >> (7 * part)) & 127U;
    const std::uint64_t high = kIq2HalfHighGrid[code] ^
        (ksigns64[sign] & 0x8080808080808080ULL);
    const float scale = __half2float(d) * float(2 * (raw.y >> 28) + 1) * 0.125F;
    const __half rounded = __float2half_rn(scale);
    Iq2HalfBytesToHalves(std::uint32_t(high >> ((col & 4) * 8)),
        __halves2half2(rounded, rounded), __float2half2_rn(0.0F), lo, hi);
  } else {
    const unsigned q = col % 256;
    const unsigned sm = block[q / 16];
    __half2 dm;
    __builtin_memcpy(&dm, block + 80, 4);
    const float d = __low2float(dm) * float(sm & 15U);
    const float bias = -__high2float(dm) * float(sm >> 4U);
    const unsigned offset = (q / 128) * 32 + q % 32;
    const unsigned shift = 2 * ((q % 128) / 32);
    float values[4];
#pragma unroll
    for (unsigned i = 0; i < 4; ++i)
      values[i] = fmaf(float((block[16 + offset + i] >> shift) & 3U), d, bias);
    lo = __floats2half2_rn(values[0], values[1]);
    hi = __floats2half2_rn(values[2], values[3]);
  }
  auto* dst = output + expert * m * k + ((col / 16) * m + row) * 16 + col % 16;
  *reinterpret_cast<uint2*>(dst) = make_uint2(
      __builtin_bit_cast(unsigned, lo), __builtin_bit_cast(unsigned, hi));
}

bool ConvertExpertCache(const void* encoded, void* output, bool iq2,
                         std::uint32_t experts, std::uint32_t m,
                         std::uint32_t k, hipStream_t stream) {
  if (!encoded || !output || !experts || !m || !k || k % 64 ||
      (iq2 && k % 256)) return false;
  const std::size_t groups = std::size_t(experts) * m * (k / 4);
  const dim3 grid((groups + 255) / 256);
  if (iq2)
    hipLaunchKernelGGL((ConvertExpertCacheKernel<true>), grid, dim3(256), 0,
        stream, static_cast<const std::uint8_t*>(encoded),
        static_cast<__half*>(output), groups, m, k);
  else
    hipLaunchKernelGGL((ConvertExpertCacheKernel<false>), grid, dim3(256), 0,
        stream, static_cast<const std::uint8_t*>(encoded),
        static_cast<__half*>(output), groups, m, k);
  return hipGetLastError() == hipSuccess;
}
