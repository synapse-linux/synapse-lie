// SPDX-License-Identifier: MIT
// Original scalar IQ2 gate/up, with the existing codebook staged in LDS.
#include "mmq/qfn_mmq_prelude.h"
namespace qfn_mmq {
#include "mmq/mmvq.hpp"
#include "mmq/quantize.hpp"
#include "mmq/unary.hpp"
#include "mmq/vecdotq.hpp"
#include "q2_iq2_decode_lds.inc"

ggml_backend_hip_context* get_ctx_for_device(int device);

static int Iq2DecodeLds(const void* gate, const void* up, const float* x,
                      const int32_t* ids, float* out, hipStream_t stream) {
  if (!gate || !up || !x || !ids || !out)
    return -1;
  auto* ctx = get_ctx_for_device(ggml_hip_get_device());
  if (!ctx)
    return -1;
  constexpr int k = 2560, rows = 640, slots = 10;
  constexpr int padded_k = GGML_PAD(k, MATRIX_ROW_PADDING);
  static_assert(padded_k == 2560);
  constexpr size_t bytes = padded_k * sizeof(block_q8_1) / QK8_1;
  ggml_hip_pool_alloc<char> packed;
  packed.alloc(ctx->pool(), bytes);
  quantize_row_q8_1_hip(x, nullptr, packed.get(), GGML_TYPE_IQ2_XXS,
                        k, k, k, k, padded_k, 1, 1, 1, stream);
  if (hipGetLastError() != hipSuccess)
    return -2;
  Iq2DecodeGridKernel<GGML_TYPE_IQ2_XXS, 2, true, true>
      <<<dim3(rows / 2, slots), dim3(32, 2), 0, stream>>>(
          gate, packed.get(), ids, out, k, rows, k / 256,
          padded_k / QK8_1, rows * slots, rows * (k / 256), rows, 1,
          slots, up);
  return hipGetLastError() == hipSuccess ? 0 : -3;
}
}  // namespace qfn_mmq

namespace gufo::models::qwen38_flash_next::rocm {
int IQ2DecodeLds(const void* gate, const void* up, const float* x,
                 const int32_t* ids, float* out, hipStream_t stream) {
  return qfn_mmq::Iq2DecodeLds(gate, up, x, ids, out, stream);
}
}  // namespace gufo::models::qwen38_flash_next::rocm
