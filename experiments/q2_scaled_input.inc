// SPDX-License-Identifier: MIT
// Experimental activation representation; original encoded weights stay intact.
__global__ void PackQ2ScaledRowsKernel(const float *x, __half *out,
                                       float *inverse, std::size_t cols) {
  const unsigned tid = threadIdx.x;
  const unsigned lane = tid & 31, wave = tid >> 5;
  const std::size_t row = blockIdx.x;
  __shared__ float maxima[8];
  __shared__ float multiplier;
  float local = 0.0F;
  for (std::size_t c = tid; c < cols; c += 256)
    local = fmaxf(local, fabsf(x[row * cols + c]));
  for (unsigned offset = 16; offset; offset >>= 1)
    local = fmaxf(local, __shfl_down(local, offset, 32));
  if (lane == 0)
    maxima[wave] = local;
  __syncthreads();
  if (tid == 0) {
    float peak = 0.0F;
    for (unsigned i = 0; i < 8; ++i)
      peak = fmaxf(peak, maxima[i]);
    const unsigned bits = __builtin_bit_cast(unsigned, peak);
    const int exponent = int((bits >> 23) & 255U) - 127;
    // Normal finite rows target [8192,16384). Bounded power-of-two factors
    // keep both scale and inverse finite. Zero rows retain signed zero.
    int shift = peak == 0.0F ? 0 : 13 - exponent;
    shift = shift < -120 ? -120 : shift > 120 ? 120 : shift;
    multiplier = __builtin_bit_cast(float, unsigned(127 + shift) << 23);
    inverse[row] = __builtin_bit_cast(float, unsigned(127 - shift) << 23);
  }
  __syncthreads();
  for (std::size_t c = tid; c < cols; c += 256)
    out[row * cols + c] = __float2half_rn(x[row * cols + c] * multiplier);
}

bool PackQ2ScaledRows(const float *x, __half *out, float *inverse,
                      std::uint32_t rows, std::size_t cols,
                      hipStream_t stream) {
  if (!x || !out || !inverse || !rows || cols != 640)
    return false;
  hipLaunchKernelGGL(PackQ2ScaledRowsKernel, dim3(rows), dim3(256), 0, stream,
                     x, out, inverse, cols);
  return hipGetLastError() == hipSuccess;
}

template <int BN>
void LaunchRoutedQ2Scaled(const void *w, const __half *x, const float *inverse,
                          const std::int32_t *tiles, std::uint32_t n_tiles,
                          const std::int32_t *bounds, const std::int32_t *slots,
                          float *out, std::size_t m, std::size_t k,
                          hipStream_t stream) {
  hipLaunchKernelGGL(
      (RoutedF16GEMMKernel<WeightType::kQ2_K, 128, BN, 2, false, false, true>),
      dim3(static_cast<unsigned>((m + 127) / 128), n_tiles), dim3(256), 0,
      stream, w, x, tiles, bounds, slots, slots, nullptr, out, nullptr, m, k,
      inverse);
}

bool RoutedQ2ScaledGemm(const void *w, const __half *x, const float *inverse,
                        const std::int32_t *tiles, std::uint32_t n_tiles,
                        std::uint32_t tile_rows, const std::int32_t *bounds,
                        const std::int32_t *slots, float *out, std::size_t m,
                        std::size_t k, hipStream_t stream) {
  if (!w || !x || !inverse || !tiles || !bounds || !slots || !out || !m ||
      !n_tiles || k != 640)
    return false;
  switch (tile_rows) {
  case 16:
    LaunchRoutedQ2Scaled<16>(w, x, inverse, tiles, n_tiles, bounds, slots, out,
                             m, k, stream);
    break;
  case 48:
    LaunchRoutedQ2Scaled<48>(w, x, inverse, tiles, n_tiles, bounds, slots, out,
                             m, k, stream);
    break;
  case 64:
    LaunchRoutedQ2Scaled<64>(w, x, inverse, tiles, n_tiles, bounds, slots, out,
                             m, k, stream);
    break;
  default:
    return false;
  }
  return hipGetLastError() == hipSuccess;
}
