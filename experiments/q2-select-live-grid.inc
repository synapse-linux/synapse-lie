// SPDX-License-Identifier: MIT
// Derived from the pinned Gufo selector launch; unchanged GPU kernels.
void SelectBlocksLiveGrid(
    const float* q, const __half* blocks, std::uint32_t* mask, float* scores,
    std::uint32_t n_tokens, const std::uint32_t* start_pos,
    std::uint32_t first_token, std::uint32_t heads, std::uint32_t dim,
    std::uint32_t ratio, std::uint32_t budget, std::uint32_t mask_words,
    std::uint32_t max_blocks, std::uint32_t live_blocks, hipStream_t stream) {
  if (heads != kSelectHeads || dim != kSelectDim) {
    return;
  }
  // Eager prefill knows the last live block. Keep the allocated score pitch
  // and mask stride; only blocks that always return without effects are
  // omitted. Captured decode must keep its original capacity grid.
  const dim3 grid(
      n_tokens, (std::min(live_blocks, max_blocks) + kThreads - 1) / kThreads);
  hipLaunchKernelGGL(SelectScoreKernel, grid, dim3(kThreads), 0, stream, q,
                     blocks, scores, n_tokens, start_pos, first_token, ratio,
                     budget, max_blocks);
  hipLaunchKernelGGL(SelectMarkKernel, dim3(n_tokens), dim3(kThreads), 0,
                     stream, mask, scores, start_pos, first_token, ratio,
                     budget, mask_words, max_blocks);
}
