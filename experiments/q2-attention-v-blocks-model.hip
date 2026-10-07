// SPDX-License-Identifier: MIT
#include <hip/hip_fp16.h>
#include <hip/hip_runtime.h>

#include <cmath>
#include <cstdint>

namespace gufo::models::qwen38_flash_next::rocm {
namespace {
// Keep the measured helpers and arithmetic verbatim; unused control templates
// are not instantiated in this production translation unit.
// clang-format off
#include "q2_attention_v_control.inc"
#include "q2_attention_v_blocks.inc"
// clang-format on
}  // namespace

int AttentionVBlocksPrefill(const float* query, const float* gate,
                            const __half* keys, const __half* values,
                            const std::uint32_t* mask, std::uint32_t mask_words,
                            float* output, __half* temporary,
                            std::uint32_t rows, std::uint32_t start_pos,
                            hipStream_t stream) {
  const std::uint32_t context = start_pos + rows;
  const std::size_t vectors = std::size_t((context + 3) & ~3u) * 64;
  hipLaunchKernelGGL(PackAttentionVBlocksKernel, dim3((vectors + 255) / 256),
                     dim3(256), 0, stream,
                     reinterpret_cast<const uint4*>(values),
                     reinterpret_cast<uint4*>(temporary), context);
  const auto packed = hipGetLastError();
  if (packed != hipSuccess) {
    return static_cast<int>(packed);
  }
  const dim3 grid((rows + 3) / 4, 2);
  if (start_pos >= 65536) {
    hipLaunchKernelGGL((WmmaCausalAttentionVBlocksKernel<4, 16, true, true>),
                       grid, dim3(256), 0, stream, query, gate, keys, temporary,
                       mask, mask_words, output, start_pos, rows, 0);
  } else {
    hipLaunchKernelGGL((WmmaCausalAttentionVBlocksKernel<4, 16, true, false>),
                       grid, dim3(256), 0, stream, query, gate, keys, temporary,
                       mask, mask_words, output, start_pos, rows, 0);
  }
  return static_cast<int>(hipGetLastError());
}
}  // namespace gufo::models::qwen38_flash_next::rocm
