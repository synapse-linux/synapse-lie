// SPDX-License-Identifier: MIT
#ifndef LIE_EXPERIMENT_Q2_SHARED_FORK_HPP
#define LIE_EXPERIMENT_Q2_SHARED_FORK_HPP
#include "gpu_fork.h"
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hpp"

namespace gufo::models::qwen38_flash_next::rocm {
// HIP adapter for one C-owned fork. All buffers already belong to the executor.
// The routed branch reads x_half and writes gate_e/down_e; it never touches
// the Q8 input or these three shared-expert outputs before the event join.
struct LieSharedFork {
  lie_gpu_fork *flow;
  hipStream_t parent, branch;
  hipEvent_t ready_event, done_event;
  const void *gate_weight, *up_weight, *down_weight, *input_q8;
  float *gate_output, *up_output, *down_output;
  __half *swiglu_half;
  std::uint32_t tokens, hidden, width;

  static int Ready(void *context) noexcept {
    auto &s = *static_cast<LieSharedFork *>(context);
    auto rc = hipEventRecord(s.ready_event, s.parent);
    return rc == hipSuccess ? hipStreamWaitEvent(s.branch, s.ready_event, 0)
                            : rc;
  }
  static int Launch(void *context) noexcept {
    auto &s = *static_cast<LieSharedFork *>(context);
    if (!W8A8Gemm(s.gate_weight, s.input_q8, s.gate_output, s.tokens, s.width,
                  s.hidden, s.branch) ||
        !W8A8Gemm(s.up_weight, s.input_q8, s.up_output, s.tokens, s.width,
                  s.hidden, s.branch))
      return -1;
    SwigluHalf(s.gate_output, s.up_output, s.swiglu_half,
               std::size_t{s.tokens} * s.width, s.branch);
    auto rc = hipGetLastError();
    if (rc != hipSuccess)
      return rc;
    if (!DenseF16Gemm(s.down_weight, s.swiglu_half, s.down_output, s.tokens,
                      s.hidden, s.width, s.branch))
      return -2;
    return hipEventRecord(s.done_event, s.branch);
  }
  static int Join(void *context) noexcept {
    auto &s = *static_cast<LieSharedFork *>(context);
    return hipStreamWaitEvent(s.parent, s.done_event, 0);
  }
  static int Drain(void *context) noexcept {
    auto &s = *static_cast<LieSharedFork *>(context);
    const auto branch_rc = hipStreamSynchronize(s.branch);
    const auto parent_rc = hipStreamSynchronize(s.parent);
    return branch_rc != hipSuccess ? branch_rc : parent_rc;
  }
  static inline const lie_gpu_fork_ops ops{Ready, Launch, Join, Drain};
  lie_gpu_status Begin() noexcept {
    return lie_gpu_fork_begin(flow, &ops, this);
  }
  // Error/exception unwinding drains unfinished work before stack context dies.
  ~LieSharedFork() { (void)lie_gpu_fork_abort(flow); }
};
} // namespace gufo::models::qwen38_flash_next::rocm
#endif
