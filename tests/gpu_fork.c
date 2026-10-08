/* SPDX-License-Identifier: MIT */
#include "gpu_fork.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

typedef struct {
  char trace[16], fail;
  unsigned count;
  int drain_fail;
} fixture;
static int step(void *ctx, char name) {
  fixture *x = ctx;
  assert(x->count + 1 < sizeof(x->trace));
  x->trace[x->count++] = name;
  return x->fail == name ? 7 : 0;
}
static int ready(void *x) { return step(x, 'R'); }
static int launch(void *x) { return step(x, 'L'); }
static int join(void *x) { return step(x, 'J'); }
static int drain(void *x) {
  fixture *f = x;
  (void)step(x, 'D');
  return f->drain_fail;
}
static const lie_gpu_fork_ops ops = {ready, launch, join, drain};
int main(void) {
  lie_gpu_fork f = {0};
  fixture x = {0};
  assert(lie_gpu_fork_begin(0, &ops, &x) == LIE_GPU_INVALID);
  assert(lie_gpu_fork_begin(&f, 0, &x) == LIE_GPU_INVALID);
  assert(lie_gpu_fork_join(&f) == LIE_GPU_INVALID);
  assert(lie_gpu_fork_begin(&f, &ops, &x) == LIE_GPU_OK);
  assert(f.state == LIE_GPU_ACTIVE && !strcmp(x.trace, "RL"));
  assert(lie_gpu_fork_begin(&f, &ops, &x) == LIE_GPU_BUSY);
  assert(lie_gpu_fork_join(&f) == LIE_GPU_OK);
  assert(f.state == LIE_GPU_IDLE && !strcmp(x.trace, "RLJ"));
  assert(lie_gpu_fork_abort(&f) == LIE_GPU_OK);
  assert(!strcmp(x.trace, "RLJ"));
  for (unsigned i = 0; i < 3; ++i) {
    x = (fixture){.fail = "RLJ"[i]};
    lie_gpu_status rc = lie_gpu_fork_begin(&f, &ops, &x);
    if (i == 2) {
      assert(rc == LIE_GPU_OK);
      rc = lie_gpu_fork_join(&f);
    }
    assert(rc == LIE_GPU_FAILED && f.state == LIE_GPU_IDLE);
    assert(f.operation_error == 7 && f.drain_error == 0);
    assert(!strcmp(x.trace, i == 0 ? "RD" : i == 1 ? "RLD" : "RLJD"));
  }
  /* Cancellation/failure between fork and join must drain once. */
  x = (fixture){0};
  assert(lie_gpu_fork_begin(&f, &ops, &x) == LIE_GPU_OK);
  assert(lie_gpu_fork_abort(&f) == LIE_GPU_OK);
  assert(!strcmp(x.trace, "RLD"));
  assert(lie_gpu_fork_abort(&f) == LIE_GPU_OK);
  assert(!strcmp(x.trace, "RLD"));
  x = (fixture){.fail = 'L', .drain_fail = 9};
  assert(lie_gpu_fork_begin(&f, &ops, &x) == LIE_GPU_DRAIN_FAILED);
  assert(f.state == LIE_GPU_POISONED && f.operation_error == 7 &&
         f.drain_error == 9);
  assert(lie_gpu_fork_begin(&f, &ops, &x) == LIE_GPU_DRAIN_FAILED);
  assert(lie_gpu_fork_join(&f) == LIE_GPU_DRAIN_FAILED);
  assert(lie_gpu_fork_abort(&f) == LIE_GPU_DRAIN_FAILED);
  assert(!strcmp(x.trace, "RLD"));
  puts("GPU fork lifecycle fixtures passed; no GPU work executed.");
  return 0;
}
