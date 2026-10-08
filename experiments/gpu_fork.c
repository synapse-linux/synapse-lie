/* SPDX-License-Identifier: MIT */
#include "gpu_fork.h"

lie_gpu_status lie_gpu_fork_abort(lie_gpu_fork *f) {
  if (!f)
    return LIE_GPU_INVALID;
  if (f->state == LIE_GPU_IDLE)
    return LIE_GPU_OK;
  if (f->state == LIE_GPU_POISONED)
    return LIE_GPU_DRAIN_FAILED;
  if (f->state != LIE_GPU_ACTIVE || !f->ops || !f->ops->drain)
    return LIE_GPU_INVALID;
  f->drain_error = f->ops->drain(f->context);
  ++f->drained;
  if (f->drain_error) {
    f->state = LIE_GPU_POISONED;
    return LIE_GPU_DRAIN_FAILED;
  }
  f->state = LIE_GPU_IDLE;
  f->ops = 0;
  f->context = 0;
  return LIE_GPU_OK;
}

static lie_gpu_status failed(lie_gpu_fork *f, int error) {
  f->operation_error = error;
  return lie_gpu_fork_abort(f) == LIE_GPU_OK ? LIE_GPU_FAILED
                                             : LIE_GPU_DRAIN_FAILED;
}

lie_gpu_status lie_gpu_fork_begin(lie_gpu_fork *f, const lie_gpu_fork_ops *ops,
                                  void *context) {
  if (!f || !ops || !ops->ready || !ops->launch || !ops->join || !ops->drain)
    return LIE_GPU_INVALID;
  if (f->state == LIE_GPU_POISONED)
    return LIE_GPU_DRAIN_FAILED;
  if (f->state != LIE_GPU_IDLE)
    return LIE_GPU_BUSY;
  f->state = LIE_GPU_ACTIVE;
  f->ops = ops;
  f->context = context;
  f->operation_error = f->drain_error = 0;
  int rc = ops->ready(context);
  if (rc)
    return failed(f, rc);
  rc = ops->launch(context);
  if (!rc)
    ++f->started;
  return rc ? failed(f, rc) : LIE_GPU_OK;
}

lie_gpu_status lie_gpu_fork_join(lie_gpu_fork *f) {
  if (!f)
    return LIE_GPU_INVALID;
  if (f->state == LIE_GPU_POISONED)
    return LIE_GPU_DRAIN_FAILED;
  if (f->state != LIE_GPU_ACTIVE || !f->ops || !f->ops->join)
    return LIE_GPU_INVALID;
  int rc = f->ops->join(f->context);
  if (rc)
    return failed(f, rc);
  ++f->joined;
  f->state = LIE_GPU_IDLE;
  f->ops = 0;
  f->context = 0;
  return LIE_GPU_OK;
}
