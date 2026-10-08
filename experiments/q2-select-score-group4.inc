// SPDX-License-Identifier: MIT
// Independent experiment: score four adjacent queries while a key is resident.
// The production selector and its dispatch remain unchanged.
namespace gufo::models::qwen38_flash_next::rocm {

__global__ void Q2SelectScoreGroup4Kernel(
    const float* q, const __half* blocks, float* scores,
    std::uint32_t n_tokens, const std::uint32_t* start_pos,
    std::uint32_t first_token, std::uint32_t ratio, std::uint32_t budget,
    std::uint32_t max_blocks) {
#pragma clang fp reassociate(off)
  constexpr std::uint32_t kGroup = 4;
  const auto first = blockIdx.x * kGroup;
  if (first >= n_tokens) return;
  const auto last = min(first + kGroup, n_tokens) - 1;
  const auto start = *start_pos;
  const auto last_complete = (start + first_token + last + 1) / ratio;
  const auto b = blockIdx.y * blockDim.x + threadIdx.x;
  if (last_complete <= budget || b >= last_complete) return;

  float key[kSelectDim];
#pragma unroll
  for (unsigned i = 0; i < kSelectDim; ++i)
    key[i] = __half2float(blocks[std::size_t{b} * kSelectDim + i]);

#pragma clang loop unroll(disable)
  for (unsigned row = 0; row < kGroup; ++row) {
    const auto t0 = first + row;
    if (t0 >= n_tokens) break;
    const auto complete = (start + first_token + t0 + 1) / ratio;
    if (complete <= budget || b >= complete) continue;
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
        if ((lane + 1) % 16 == 0) __builtin_amdgcn_sched_barrier(0);
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

}  // namespace gufo::models::qwen38_flash_next::rocm
