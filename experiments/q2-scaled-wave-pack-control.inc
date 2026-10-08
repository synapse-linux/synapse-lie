// SPDX-License-Identifier: MIT
// Literal retained1573 row packing, compiled only into the new fixture.
__global__ void PackQ2ScaledWaveControlKernel(const float* x, __half* out,
                                       float* inverse, std::size_t cols) {
  const unsigned tid = threadIdx.x;
  const unsigned lane = tid & 31, wave = tid >> 5;
  const std::size_t row = blockIdx.x;
  __shared__ float maxima[8];
  __shared__ float multiplier;
  // The launcher admits only 640 columns. Retain the at most three
  // original values per thread across the unchanged maximum reduction.
  // This avoids reading the complete F32 row again after the barrier.
  float values[3] = {};
  float local = 0.0F;
#pragma unroll
  for (unsigned i = 0; i < 3; ++i) {
    const std::size_t c = tid + i * 256;
    if (c < cols) {
      values[i] = x[row * cols + c];
      local = fmaxf(local, fabsf(values[i]));
    }
  }
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
#pragma unroll
  for (unsigned i = 0; i < 3; ++i) {
    const std::size_t c = tid + i * 256;
    if (c < cols)
      out[row * cols + c] = __float2half_rn(values[i] * multiplier);
  }
}
