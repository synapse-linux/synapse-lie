/* SPDX-License-Identifier: MIT */
/* Model-neutral reactive MTP contract. Synthetic providers, NOT-INFERENCE. */
#include "fake_executor.h"
#include "lie/core.h"
#include "lie/inference.h"
#include <assert.h>
#include <poll.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
static void pause_short(void) {
  struct timespec t = {0, 1000000};
  nanosleep(&t, NULL);
}
static lie_core_info ready(lie_core *c, lie_core_state target) {
  lie_core_info i = {0};
  for (unsigned n = 0; n < 5000; ++n) {
    lie_core_snapshot(c, &i);
    if (i.state == target)
      return i;
    pause_short();
  }
  assert(!"core deadline");
  return i;
}
static lie_flow_event next(lie_job *j) {
  lie_flow_event e = {0};
  for (unsigned n = 0; n < 5000; ++n) {
    lie_flow_status s = lie_flow_next(lie_job_flow(j), &e);
    if (s == LIE_FLOW_OK)
      return e;
    assert(s == LIE_FLOW_WOULD_BLOCK);
    struct pollfd fd = {lie_flow_fd(lie_job_flow(j), LIE_FLOW_OUTPUT_READY),
                        POLLIN, 0};
    assert(poll(&fd, 1, 1) >= 0);
    lie_flow_drain(lie_job_flow(j), LIE_FLOW_OUTPUT_READY);
  }
  assert(!"flow deadline");
  return e;
}
static void family(const char *predictor, unsigned burst) {
  lie_core_options o;
  lie_core_options_init(&o);
  o.model_path = ":fixture:";
  o.mtp_model_path = predictor;
  o.context = 128;
  o.chunk = 4;
  o.max_active = 2;
  assert(
      !lie_core_create(&o)); /* Cannot disguise incomplete AR state as MTP. */
  o.prefix_cache_bytes = 0;
  lie_core *c = lie_core_create(&o);
  assert(c);
  lie_core_info ci = ready(c, LIE_READY);
  assert(ci.model.speculative_supported && ci.mtp.max_output_tokens == burst);
  int32_t tokens[] = {1, 10, 10, 10};
  lie_core_request r;
  lie_core_request_init(&r);
  r.kind = LIE_INPUT_TOKENS;
  r.tokens = tokens;
  r.token_count = 4;
  r.max_tokens = 19;
  lie_job *a = NULL, *b = NULL;
  fake_barrier_arm_phase(FAKE_PREFILL);
  assert(!lie_core_submit(c, &r, &a));
  fake_barrier_wait();
  assert(!lie_core_submit(c, &r, &b));
  assert(lie_flow_request(lie_job_flow(a), 64) == LIE_FLOW_OK);
  assert(lie_flow_request(lie_job_flow(b), 64) == LIE_FLOW_OK);
  fake_barrier_release();
  lie_job *jobs[] = {a, b};
  for (unsigned i = 0; i < 2; ++i) {
    unsigned total = 0, maximum = 0;
    for (;;) {
      lie_flow_event e = next(jobs[i]);
      if (e.end != LIE_FLOW_ACTIVE) {
        assert(e.end == LIE_FLOW_COMPLETE);
        break;
      }
      assert(e.token_offset == total && e.tokens && e.tokens <= burst &&
             e.bytes == e.tokens * 256);
      if (e.tokens > maximum)
        maximum = (unsigned)e.tokens;
      total += (unsigned)e.tokens;
      assert(lie_flow_release(lie_job_flow(jobs[i]), e.ticket) == LIE_FLOW_OK);
    }
    assert(total == 19 && maximum == burst);
    lie_job_info info;
    lie_job_snapshot(jobs[i], &info);
    assert(info.output_tokens == 19 &&
           info.decode_calls == (19 + burst - 1) / burst &&
           info.mtp_accepted > 0 && info.mtp_accepted == info.mtp_drafted);
    int32_t output[19];
    size_t n = 0;
    assert(lie_job_output_tokens(jobs[i], output, 19, &n) == LIE_OK && n == 19);
    for (unsigned k = 0; k < 19; ++k)
      assert(output[k] == 1000);
    lie_job_release(jobs[i]);
  }
  lie_core_stop(c);
  ready(c, LIE_STOPPED);
  lie_core_destroy(c);
}
typedef struct {
  lie_sequence *s;
  lie_flow *f;
} cancel_arg;
static void *cancel_during(void *v) {
  cancel_arg *a = v;
  fake_barrier_wait();
  lie_sequence_cancel(a->s);
  lie_flow_cancel(a->f);
  fake_barrier_release();
  return NULL;
}
static void dispatch(void) {
  lie_error e = {0};
  lie_model *m = NULL;
  lie_model_options o = {LIE_EXECUTOR_ABI, sizeof(o), 128, 4};
  assert(lie_backend_open_mtp(":fixture:", &o, 2, ":wide-fixture:", 12, &m,
                              &e) == LIE_OK);
  lie_sequence *s[2] = {0};
  lie_flow *f[2] = {0};
  lie_flow_options fo = {1, 4096, 32768};
  int32_t tokens[] = {1, 10, 10, 10};
  lie_inference_row rows[2] = {0};
  lie_inference_batch batch;
  for (unsigned i = 0; i < 2; ++i) {
    assert(lie_sequence_create(m, &s[i], &e) == LIE_OK);
    assert(lie_sequence_prefill(s[i], tokens, 4, &e) == LIE_OK);
    assert(lie_flow_create(&fo, &f[i]) == LIE_FLOW_OK);
    rows[i] = (lie_inference_row){.sequence = s[i],
                                  .flow = f[i],
                                  .position = 4,
                                  .context = 128,
                                  .vocab = 2048,
                                  .step_tokens = 13};
  }
  fake_calls_reset();
  assert(lie_inference_prepare(rows, 2, 2, &batch, &e) == LIE_OK &&
         !batch.selected);
  assert(lie_inference_run(&batch, &e) == LIE_OK &&
         !fake_calls_snapshot().decode);
  assert(lie_flow_request(f[0], 1) == LIE_FLOW_OK);
  assert(lie_flow_request(f[1], 13) == LIE_FLOW_OK);
  assert(lie_inference_prepare(rows, 2, 2, &batch, &e) == LIE_OK &&
         rows[0].reservation.tokens == 1 && rows[1].reservation.tokens == 13);
  fake_barrier_arm();
  cancel_arg a = {s[0], f[0]};
  pthread_t t;
  assert(!pthread_create(&t, NULL, cancel_during, &a));
  assert(lie_inference_run(&batch, &e) == LIE_OK);
  assert(!pthread_join(t, NULL));
  assert(rows[0].burst.status == LIE_CANCELLED && !rows[0].burst.emitted);
  assert(rows[1].burst.status == LIE_OK && rows[1].burst.emitted == 13 &&
         rows[1].burst.position == 17);
  for (unsigned i = 0; i < 2; ++i) {
    assert(lie_flow_abort(f[i], rows[i].reservation.ticket, 1) == LIE_FLOW_OK);
    assert(lie_sequence_close(&s[i], &e) == LIE_OK);
    assert(lie_flow_destroy(&f[i]) == LIE_FLOW_OK);
  }
  assert(lie_model_close(&m, &e) == LIE_OK);
}
static void invalid_burst(void) {
  lie_model *m = NULL;
  lie_model_options options = {LIE_EXECUTOR_ABI, sizeof(options), 128, 4};
  assert(lie_backend_open_mtp(":fixture:", &options, 2, ":wide-fixture:", 0, &m, NULL) == LIE_OK);
  lie_inference_row rows[2] = {0};
  lie_sequence *seq[2] = {0};
  lie_flow *flow[2] = {0};
  const char *texts[] = {"LONG", "BAD-POSITION"};
  for (unsigned i = 0; i < 2; ++i) {
    lie_chat_message message = {LIE_CHAT_USER, texts[i], strlen(texts[i])};
    int32_t tokens[4];size_t n = 0;
    assert(lie_model_chat_tokens(m, &message, 1, tokens, 4, &n, NULL) == LIE_OK);
    assert(lie_sequence_create(m, &seq[i], NULL) == LIE_OK);
    assert(lie_sequence_prefill(seq[i], tokens, n, NULL) == LIE_OK);
    lie_flow_options fo = {1, 4096, 32768};
    assert(lie_flow_create(&fo, &flow[i]) == LIE_FLOW_OK);
    assert(lie_flow_request(flow[i], 13) == LIE_FLOW_OK);
    rows[i] = (lie_inference_row){.sequence=seq[i],.flow=flow[i],.position=4,.context=128,.vocab=2048,.step_tokens=13};
  }
  lie_inference_batch batch;
  assert(lie_inference_prepare(rows, 2, 2, &batch, NULL) == LIE_OK);
  assert(lie_inference_run(&batch, NULL) == LIE_BACKEND_FAILED);
  for (unsigned i = 0; i < 2; ++i) {
    assert(rows[i].burst.status == LIE_BACKEND_FAILED && !rows[i].burst.emitted);
    assert(lie_flow_abort(flow[i], rows[i].reservation.ticket, 1) == LIE_FLOW_OK);
    assert(lie_flow_destroy(&flow[i]) == LIE_FLOW_OK);
    assert(lie_sequence_close(&seq[i], NULL) == LIE_OK);
  }
  assert(lie_model_close(&m, NULL) == LIE_OK);
}
int main(void) {
  family(":fixture:", 8);
  family(":wide-fixture:", 13);
  dispatch();
  invalid_burst();
  puts("Model-neutral MTP bursts, credits, cancellation and output bounds: "
       "PASS (NOT-INFERENCE)");
}
