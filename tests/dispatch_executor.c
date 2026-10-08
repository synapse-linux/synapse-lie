/* SPDX-License-Identifier: MIT */
/* Dedicated owner-asserting accounting fixture, NOT-INFERENCE. Never linked
 * into other fixtures or the production provider. One model per test process.
 */
#define lie_model_attention_dispatch_snapshot dispatch_fixture_snapshot
#define lie_sequence_prefill dispatch_fixture_prefill
#include "fake_executor.c"
#undef lie_model_attention_dispatch_snapshot
#undef lie_sequence_prefill

static lie_attention_dispatch_counter dispatch_counter;
lie_status lie_model_attention_dispatch_snapshot(
    lie_model *m, lie_attention_dispatch_info *out, lie_error *e) {
  owner(m); /* Detect any accidental provider access from client threads. */
  if (dispatch_counter.info.domain != m->domain)
    lie_attention_dispatch_init(&dispatch_counter, true, m->domain);
  if (lie_attention_dispatch_snapshot(&dispatch_counter, out) !=
      LIE_DISPATCH_OK)
    return error(e, LIE_INVALID, "invalid dispatch fixture snapshot");
  return LIE_OK;
}
lie_status lie_sequence_prefill(lie_sequence *s, const int32_t *tokens,
                                size_t count, lie_error *e) {
  owner(s->model);
  assert(lie_attention_dispatch_begin(&dispatch_counter) == LIE_DISPATCH_OK);
  bool sparse = s->position != 0;
  assert(lie_attention_dispatch_record(
             &dispatch_counter,
             sparse ? LIE_ATTENTION_SCALAR_SPARSE : LIE_ATTENTION_MATRIX_DENSE,
             (uint32_t)(count - s->position), sparse ? 8192 : 0,
             sparse ? LIE_ATTENTION_REFUSAL_MASK_PITCH
                    : LIE_ATTENTION_REFUSAL_NONE) == LIE_DISPATCH_OK);
  lie_status rc = dispatch_fixture_prefill(s, tokens, count, e);
  assert(lie_attention_dispatch_finish(&dispatch_counter, rc == LIE_OK) ==
         LIE_DISPATCH_OK);
  return rc;
}
