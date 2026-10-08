// SPDX-License-Identifier: MIT
// Derived from pinned Gufo selector; only FP32 query storage changes.
__global__ void SelectScoreQueryLdsKernel(const float* q, const __half* blocks,
                                  float* scores, std::uint32_t n_tokens,
                                  const std::uint32_t* start_pos,
                                  std::uint32_t first_token,
                                  std::uint32_t ratio, std::uint32_t budget,
                                  std::uint32_t max_blocks) {
#pragma clang fp reassociate(off)
  const auto t0 = blockIdx.x;
  const auto complete = (*start_pos + first_token + t0 + 1) / ratio;
  const auto b = blockIdx.y * blockDim.x + threadIdx.x;
  // These exits are uniform across the workgroup, before its barrier.
  if (t0 >= n_tokens || complete <= budget || blockIdx.y * blockDim.x >= complete)
    return;
  __shared__ float query_cache[kSelectHeads * kSelectDim];
  for (unsigned i = threadIdx.x; i < kSelectHeads * kSelectDim; i += blockDim.x)
    query_cache[i] = q[std::size_t{t0} * kSelectHeads * kSelectDim + i];
  __syncthreads();
  if (b >= complete)
    return;
  float key[kSelectDim];
#pragma unroll
  for (unsigned i = 0; i < kSelectDim; ++i)
    key[i] = __half2float(blocks[std::size_t{b} * kSelectDim + i]);
  float total = 0.0F;
#pragma unroll
  for (unsigned h = 0; h < kSelectHeads; ++h) {
    const auto* query = query_cache + h * kSelectDim;
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
