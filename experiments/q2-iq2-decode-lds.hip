// SPDX-License-Identifier: MIT
// Private scalar IQ2 component entry; no model dispatch is modified.
#include "qfn_mmq_prelude.h"
namespace qfn_mmq {
#include "mmvq.hpp"
#include "unary.hpp"
#include "vecdotq.hpp"
// The derived body requires the preceding vendor definitions.
#include "experiments/q2-iq2-decode-lds.inc"

void Iq2DecodeLdsProbe(bool staged, const void* gate, const void* up,
                       const block_q8_1* input, const int32_t* ids,
                       float* output, int k, int rows, int experts_used,
                       int input_stride, hipStream_t stream) {
  const int row_stride = k / 256;
  const dim3 grid((rows + 1) / 2, experts_used);
  const dim3 block(32, 2);
  if (staged) {
    Iq2DecodeGridKernel<GGML_TYPE_IQ2_XXS, 2, true, true>
        <<<grid, block, 0, stream>>>(
            gate, input, ids, output, k, rows, row_stride, input_stride,
            rows * experts_used, rows * row_stride, rows, 1, experts_used, up);
  } else {
    Iq2DecodeGridKernel<GGML_TYPE_IQ2_XXS, 2, true, false>
        <<<grid, block, 0, stream>>>(
            gate, input, ids, output, k, rows, row_stride, input_stride,
            rows * experts_used, rows * row_stride, rows, 1, experts_used, up);
  }
}
}  // namespace qfn_mmq
