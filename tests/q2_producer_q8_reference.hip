// SPDX-License-Identifier: MIT
// Unchanged original MMQ format reference, independently invoked after the
// parent F32 gate. Not a timed control and not an independent quality oracle.
#include "qfn_mmq_prelude.h"
namespace qfn_mmq {
#include "quantize.hpp"
extern "C" void q2_fixture_quantize_d2s6(const float *input, void *output,
                                         unsigned rows, hipStream_t stream) {
  quantize_mmq_q8_1_hip(input, nullptr, output, GGML_TYPE_Q2_K, 640, 640, 0, 0,
                        768, rows, 1, 1, stream);
}
} // namespace qfn_mmq
