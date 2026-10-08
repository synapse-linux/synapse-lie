/* SPDX-License-Identifier: MIT */
/* Owner/client publication, cancel and poison controls. NOT-INFERENCE. */
#include "fake_executor.h"
#include "lie/core.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
static void pause_short(void) {
  struct timespec t = {0, 1000000};
  nanosleep(&t, NULL);
}
static void ready(lie_core *c, lie_core_state target) {
  for (unsigned k = 0; k < 5000; ++k) {
    lie_core_info i;
    lie_core_snapshot(c, &i);
    if (i.state == target)
      return;
    pause_short();
  }
  assert(!"core state deadline");
}
static lie_attention_dispatch_info snapshot(lie_core *c) {
  lie_attention_dispatch_info out;
  lie_attention_dispatch_info_init(&out);
  assert(lie_core_attention_dispatch_snapshot(c, &out, NULL) == LIE_OK);
  return out;
}
static lie_job *submit(lie_core *c, int32_t mode) {
  int32_t tokens[] = {mode, 1, 1, 1};
  lie_core_request r;
  lie_core_request_init(&r);
  r.kind = LIE_INPUT_TOKENS;
  r.tokens = tokens;
  r.token_count = 4;
  r.max_tokens = 1;
  lie_job *j = NULL;
  assert(!lie_core_submit(c, &r, &j) && j);
  return j;
}
static void retired(lie_job *j) {
  for (unsigned k = 0; k < 5000; ++k) {
    lie_flow_event ev;
    lie_flow_status rc = lie_flow_next(lie_job_flow(j), &ev);
    if (rc == LIE_FLOW_OK && ev.end == LIE_FLOW_ACTIVE)
      assert(lie_flow_release(lie_job_flow(j), ev.ticket) == LIE_FLOW_OK);
    lie_job_info info;
    lie_job_snapshot(j, &info);
    if (info.retired)
      return;
    pause_short();
  }
  assert(!"job retirement deadline");
}
int main(void) {
  lie_core_options o;
  lie_core_options_init(&o);
  o.model_path = ":fixture:";
  o.context = 1024;
  o.chunk = 2;
  o.prefix_cache_bytes = 0;
  lie_core *c = lie_core_create(&o);
  assert(c);
  ready(c, LIE_READY);
  lie_attention_dispatch_info initial = snapshot(c);
  assert(initial.supported && initial.domain && !initial.pending &&
         !initial.confirmed_batches);
  lie_attention_dispatch_info invalid = initial, saved;
  invalid.struct_bytes++;
  saved = invalid;
  assert(lie_core_attention_dispatch_snapshot(c, &invalid, NULL) ==
         LIE_INVALID);
  assert(!memcmp(&saved, &invalid, sizeof(invalid)));
  fake_barrier_arm_phase(FAKE_PREFILL);
  lie_job *j = submit(c, 0);
  fake_barrier_wait();
  /* Staged owner work is invisible to every client until return; no device
   * wait. */
  for (unsigned k = 0; k < 100; ++k) {
    lie_attention_dispatch_info busy = snapshot(c);
    assert(!memcmp(&initial, &busy, sizeof(busy)));
  }
  fake_barrier_release();
  retired(j);
  lie_job_release(j);
  lie_attention_dispatch_info good = snapshot(c);
  assert(good.confirmed_batches == 2 && !good.unconfirmed_batches);
  assert(good.confirmed.matrix_dense == 1 && good.confirmed.scalar_sparse == 1);
  assert(good.confirmed.mask_pitch_refusals == 1 &&
         good.confirmed.attention_rows == 4);
  fake_barrier_arm_phase(FAKE_PREFILL);
  j = submit(c, 0);
  fake_barrier_wait();
  lie_job_cancel(j);
  fake_barrier_release();
  retired(j);
  lie_job_release(j);
  lie_attention_dispatch_info cancel = snapshot(c);
  assert(cancel.confirmed_batches == 2 && cancel.unconfirmed_batches == 1);
  assert(cancel.unconfirmed.matrix_dense == 1 &&
         cancel.unconfirmed.attention_rows == 2);
  j = submit(c, 7);
  retired(j);
  lie_job_release(j);
  ready(c, LIE_FAILED);
  lie_attention_dispatch_info fault = snapshot(c);
  assert(fault.confirmed_batches == 3 && fault.unconfirmed_batches == 2);
  assert(fault.unconfirmed.scalar_sparse == 1 &&
         fault.unconfirmed.mask_pitch_refusals == 1);
  lie_core_stop(c);
  ready(c, LIE_STOPPED);
  lie_attention_dispatch_info stopped = snapshot(c);
  assert(!memcmp(&fault, &stopped, sizeof(fault)));
  lie_core_destroy(c);
  puts("Shared core attention publication: PASS (synthetic, NOT-INFERENCE)");
  return 0;
}
