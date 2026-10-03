/* SPDX-License-Identifier: MIT */
#ifndef LIE_EXPERIMENT_GPU_FORK_H
#define LIE_EXPERIMENT_GPU_FORK_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

typedef enum { LIE_GPU_IDLE, LIE_GPU_ACTIVE, LIE_GPU_POISONED } lie_gpu_state;
typedef enum {
  LIE_GPU_OK,
  LIE_GPU_INVALID,
  LIE_GPU_BUSY,
  LIE_GPU_FAILED,
  LIE_GPU_DRAIN_FAILED
} lie_gpu_status;
typedef struct {
  int (*ready)(void *context);
  int (*launch)(void *context);
  int (*join)(void *context);
  int (*drain)(void *context);
} lie_gpu_fork_ops;
typedef struct {
  lie_gpu_state state;
  const lie_gpu_fork_ops *ops;
  void *context;
  int operation_error, drain_error;
  uint64_t started, joined, drained;
} lie_gpu_fork;

/* Zero-initialize once. One host owner, one outstanding branch, no allocation.
 * ready orders the branch after parent input production; launch records its
 * completion; join orders every subsequent parent consumer after that event.
 * Successful join transfers lifetime back to the parent's ordered stream: it
 * is not host-observed GPU completion. Parent completion is still mandatory.
 * drain waits for BOTH streams, including partial launch/error/cancellation.
 * Callbacks/context remain alive through join/abort and must not reenter this
 * object or throw through C. Failed drain permanently poisons admission.
 * No buffer may be released on a failed drain. No automatic retry/reset. */
lie_gpu_status lie_gpu_fork_begin(lie_gpu_fork *fork,
                                  const lie_gpu_fork_ops *ops, void *context);
lie_gpu_status lie_gpu_fork_join(lie_gpu_fork *fork);
lie_gpu_status lie_gpu_fork_abort(lie_gpu_fork *fork);
#ifdef __cplusplus
}
#endif
#endif
