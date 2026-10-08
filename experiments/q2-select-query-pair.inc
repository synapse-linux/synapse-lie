// SPDX-License-Identifier: MIT
// Derived from pinned Gufo exact FP32 selector; private component only.
__global__ void SelectScoreQueryPairKernel(
    const float* q, const __half* blocks, float* scores, std::uint32_t n_tokens,
    const std::uint32_t* start_pos, std::uint32_t first_token,
    std::uint32_t ratio, std::uint32_t budget, std::uint32_t max_blocks) {
#pragma clang fp reassociate(off)
  const auto first = 2 * blockIdx.x;
  if (first >= n_tokens)
    return;
  const auto last = min(first + 1, n_tokens - 1);
  const auto last_complete = (*start_pos + first_token + last + 1) / ratio;
  const auto b = blockIdx.y * blockDim.x + threadIdx.x;
  if (last_complete <= budget || b >= last_complete)
    return;
  float key[kSelectDim];
#pragma unroll
  for (unsigned i = 0; i < kSelectDim; ++i)
    key[i] = __half2float(blocks[std::size_t{b} * kSelectDim + i]);
  // Reuse the same original F16 key for two complete query reductions.
  // Query arithmetic, head order and the exact32-lane sum tree remain.
#pragma unroll
  for (unsigned row = 0; row < 2; ++row) {
    const auto t0 = first + row;
    const auto complete = (*start_pos + first_token + t0 + 1) / ratio;
    if (t0 >= n_tokens || complete <= budget || b >= complete)
      continue;
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
}

void SelectBlocksQueryPair(const float* q, const __half* blocks,
                           std::uint32_t* mask, float* scores,
                           std::uint32_t n_tokens,
                           const std::uint32_t* start_pos,
                           std::uint32_t first_token, std::uint32_t ratio,
                           std::uint32_t budget, std::uint32_t mask_words,
                           std::uint32_t max_blocks, hipStream_t stream) {
  const dim3 grid((n_tokens + 1) / 2, (max_blocks + kThreads - 1) / kThreads);
  hipLaunchKernelGGL(SelectScoreQueryPairKernel, grid, dim3(kThreads), 0,
                     stream, q, blocks, scores, n_tokens, start_pos,
                     first_token, ratio, budget, max_blocks);
  hipLaunchKernelGGL(SelectMarkKernel, dim3(n_tokens), dim3(kThreads), 0,
                     stream, mask, scores, start_pos, first_token, ratio,
                     budget, mask_words, max_blocks);
}
