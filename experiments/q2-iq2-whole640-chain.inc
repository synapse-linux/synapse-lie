// SPDX-License-Identifier: MIT
// Original whole-row dyadic packing with routed ownership. Fused tail slots
// are absent from this map and must never be read from the F32 intermediate.
__global__ void PackQ2ScaledOrdinaryRowsKernel(const float* x, __half* out,
                                               float* inverse,
                                               const std::int32_t* tiles,
                                               std::uint32_t wide_tiles,
                                               const std::int32_t* bounds,
                                               const std::int32_t* slots) {
  const unsigned lane = threadIdx.x & 31;
  const unsigned wave = threadIdx.x >> 5;
  const unsigned block = blockIdx.x;
  const unsigned wide_blocks = wide_tiles * 16;
  const bool wide = block < wide_blocks;
  const unsigned tile_index =
      wide ? block / 16 : wide_tiles + (block - wide_blocks) / 8;
  const unsigned chunk = wide ? block % 16 : (block - wide_blocks) % 8;
  const unsigned descriptor = static_cast<unsigned>(tiles[tile_index]);
  const unsigned expert = descriptor & 65535U;
  const unsigned token =
      (descriptor >> 16) * (wide ? 128 : 64) + chunk * 8 + wave;
  const unsigned begin = static_cast<unsigned>(bounds[expert]);
  if (token >= static_cast<unsigned>(bounds[expert + 1]) - begin)
    return;
  const int destination = slots[begin + token];
  if (destination < 0)
    return;
  const float* src = x + static_cast<std::size_t>(destination) * 640;
  __half* dst = out + static_cast<std::size_t>(destination) * 640;
  float4 values[5];
  float local = 0.F;
#pragma unroll
  for (unsigned i = 0; i < 5; ++i) {
    const unsigned column = (i * 32 + lane) * 4;
    const float4 value = reinterpret_cast<std::uintptr_t>(src) % 16 == 0
                             ? *reinterpret_cast<const float4*>(src + column)
                             : make_float4(src[column], src[column + 1],
                                           src[column + 2], src[column + 3]);
    values[i] = value;
    local = fmaxf(local, fabsf(value.x));
    local = fmaxf(local, fabsf(value.y));
    local = fmaxf(local, fabsf(value.z));
    local = fmaxf(local, fabsf(value.w));
  }
  for (unsigned offset = 16; offset; offset >>= 1)
    local = fmaxf(local, __shfl_down(local, offset, 32));
  float multiplier = 1.F;
  if (lane == 0) {
    const unsigned bits = __builtin_bit_cast(unsigned, local);
    const int exponent = int((bits >> 23) & 255U) - 127;
    int shift = local == 0.F ? 0 : 13 - exponent;
    shift = shift < -120 ? -120 : shift > 120 ? 120 : shift;
    multiplier = __builtin_bit_cast(float, unsigned(127 + shift) << 23);
    inverse[destination] =
        __builtin_bit_cast(float, unsigned(127 - shift) << 23);
  }
  multiplier = __shfl(multiplier, 0, 32);
#pragma unroll
  for (unsigned i = 0; i < 5; ++i) {
    const unsigned column = (i * 32 + lane) * 4;
    const float4 value = values[i];
    const __half2 lo =
        __floats2half2_rn(value.x * multiplier, value.y * multiplier);
    const __half2 hi =
        __floats2half2_rn(value.z * multiplier, value.w * multiplier);
    if (reinterpret_cast<std::uintptr_t>(dst) % 8 == 0) {
      *reinterpret_cast<uint2*>(dst + column) = make_uint2(
          __builtin_bit_cast(unsigned, lo), __builtin_bit_cast(unsigned, hi));
    } else {
      dst[column] = __low2half(lo);
      dst[column + 1] = __high2half(lo);
      dst[column + 2] = __low2half(hi);
      dst[column + 3] = __high2half(hi);
    }
  }
}

bool PackQ2ScaledOrdinaryRows(const float* x, __half* out, float* inverse,
                              const std::int32_t* tiles,
                              std::uint32_t wide_tiles,
                              std::uint32_t tail_tiles,
                              const std::int32_t* bounds,
                              const std::int32_t* slots, hipStream_t stream) {
  if (!wide_tiles && !tail_tiles)
    return true;
  if (!x || !out || !inverse || !tiles || !bounds || !slots ||
      wide_tiles > 16384 || tail_tiles > 512)
    return false;
  hipLaunchKernelGGL(PackQ2ScaledOrdinaryRowsKernel,
                     dim3(wide_tiles * 16 + tail_tiles * 8), dim3(256), 0,
                     stream, x, out, inverse, tiles, wide_tiles, bounds, slots);
  return hipGetLastError() == hipSuccess;
}

bool RoutedGatedIQ2Whole640(const void* gate, const void* up, const __half* x,
                            const std::int32_t* tiles, std::uint32_t n_tiles,
                            const std::int32_t* bounds,
                            const std::int32_t* tokens,
                            const std::int32_t* slots, __half* out,
                            float* inverse, hipStream_t stream) {
  if (!n_tiles)
    return true;
  if (!gate || !up || !x || !tiles || !bounds || !tokens || !slots || !out ||
      !inverse || n_tiles > 512 || reinterpret_cast<std::uintptr_t>(x) % 16)
    return false;
  hipLaunchKernelGGL(RoutedIq2Whole640Wave16LdsDraftKernel, dim3(n_tiles),
                     dim3(512), 0, stream, gate, up, x, tiles, bounds, tokens,
                     slots, out, inverse);
  return hipGetLastError() == hipSuccess;
}
