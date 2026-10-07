// SPDX-License-Identifier: MIT
// Isolated Q2_K scalar down, original MMQ quantizer/pool and four-row body.
#include "mmq/qfn_mmq_prelude.h"
namespace qfn_mmq {
#include "mmq/mmvq.hpp"
#include "mmq/quantize.hpp"
#include "mmq/unary.hpp"
#include "mmq/vecdotq.hpp"
// This kernel body depends on the preceding vendor definitions.
#include "q2_decode_down_rows.inc"

// The same context and pool used by the retained qfn_mmq_moe_vec entry.
ggml_backend_hip_context* get_ctx_for_device(int device);

static int Q2DownRows4(const void* weights, const float* x, const int32_t* ids,
                       float* out, hipStream_t stream) {
  if (!weights || !x || !ids || !out)
    return -1;
  auto* ctx = get_ctx_for_device(ggml_hip_get_device());
  if (!ctx)
    return -1;
  constexpr int slots = 10, input_k = 640, physical_k = 768, rows = 2560;
  constexpr int padded_k = GGML_PAD(physical_k, MATRIX_ROW_PADDING);
  static_assert(padded_k == 1024);
  constexpr size_t bytes = slots * padded_k * sizeof(block_q8_1) / QK8_1;
  ggml_hip_pool_alloc<char> packed;
  packed.alloc(ctx->pool(), bytes);
  quantize_row_q8_1_hip(x, nullptr, packed.get(), GGML_TYPE_Q2_K, input_k,
                        input_k, input_k, input_k * slots, padded_k, 1, slots,
                        1, stream);
  if (hipGetLastError() != hipSuccess)
    return -2;
  Q2DownRowsKernel<GGML_TYPE_Q2_K, 4>
      <<<dim3(rows / 4, 1, 2), dim3(32, 8), 0, stream>>>(
          weights, packed.get(), ids, out, physical_k, rows, 3,
          padded_k / QK8_1, rows, rows * 3, rows, slots, 1);
  return hipGetLastError() == hipSuccess ? 0 : -3;
}
}  // namespace qfn_mmq

namespace gufo::models::qwen38_flash_next::rocm {
int Q2DecodeDownRows4(const void* weights, const float* x, const int32_t* ids,
                      float* out, hipStream_t stream) {
  return qfn_mmq::Q2DownRows4(weights, x, ids, out, stream);
}
}  // namespace gufo::models::qwen38_flash_next::rocm
