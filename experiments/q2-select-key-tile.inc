// SPDX-License-Identifier: MIT
// Original F16 bits in8-key x8-feature tiles; score arithmetic is unchanged.
__global__ void PackSelectKeyTilesKernel(const __half* input, __half* output,
                                        unsigned complete) {
  const unsigned v = blockIdx.x * blockDim.x + threadIdx.x;
  const unsigned b = v / 16, f = v % 16;
  if (b >= complete) return;
  const uint4 value = reinterpret_cast<const uint4*>(input)[v];
  const unsigned slot = (b / 8) * 128 + f * 8 + b % 8;
  reinterpret_cast<uint4*>(output)[slot] = value;
}

__global__ void SelectScoreKeyTileKernel(const float* q, const __half* blocks,
                                  float* scores, std::uint32_t n_tokens,
                                  const std::uint32_t* start_pos,
                                  std::uint32_t first_token,
                                  std::uint32_t ratio, std::uint32_t budget,
                                  std::uint32_t max_blocks) {
#pragma clang fp reassociate(off)
  const auto t0 = blockIdx.x;
  const auto complete = (*start_pos + first_token + t0 + 1) / ratio;
  const auto b = blockIdx.y * blockDim.x + threadIdx.x;
  if (t0 >= n_tokens || complete <= budget || b >= complete)
    return;
  float key[kSelectDim];
#pragma unroll
  for (unsigned i = 0; i < kSelectDim; ++i)
    key[i] = __half2float(blocks[std::size_t{b / 8} * (8 * kSelectDim) + (i / 8) * 64 + (b % 8) * 8 + i % 8]);
  float total = 0.0F;
#pragma unroll
  for (unsigned h = 0; h < kSelectHeads; ++h) {
    const auto* query = q + (std::size_t{t0} * kSelectHeads + h) * kSelectDim;
    float partial[32];
#pragma unroll
    for (unsigned lane = 0; lane < 32; ++lane) {
      float dot = 0.0F;
#pragma unroll
      for (unsigned i = 0; i < 4; ++i)
        dot = fmaf(query[lane + i * 32], key[lane + i * 32], dot);
      partial[lane] = dot;
      // Bound query-load hoisting: keeping all 128 scalar values live spills
      // registers on gfx1151. Scheduling groups retain every FMA and sum.
      if ((lane + 1) % 16 == 0)
        __builtin_amdgcn_sched_barrier(0);
    }
#pragma unroll
    for (unsigned delta = 16; delta; delta >>= 1) {
#pragma unroll
      for (unsigned lane = 0; lane < delta; ++lane)
        partial[lane] += partial[lane + delta];
    }
    total += fmaxf(partial[0], 0.0F);
  }
  scores[std::size_t{t0} * max_blocks + b] = total;
}
