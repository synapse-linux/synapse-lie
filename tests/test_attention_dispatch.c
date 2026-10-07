/* SPDX-License-Identifier: MIT */
/* Exact host accounting/lifetime control. No inference, kernel or GPU. */
#include "lie/dispatch.h"
#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>

static lie_attention_dispatch_info snapshot(lie_attention_dispatch_counter *c) {
  lie_attention_dispatch_info out;
  lie_attention_dispatch_info_init(&out);
  assert(lie_attention_dispatch_snapshot(c, &out) == LIE_DISPATCH_OK);
  return out;
}
static void sparse_mask_extents(void) {
  /* A 1M allocation has an 8192-word row pitch. It can safely use the existing
   * 2048-word workspace until the actual visible frontier crosses 262144.
   * Fixed boundaries verify the last live block/word and short-stride refusal. */
  static const struct {
    uint32_t start, rows, ratio, pitch, workspace;
    bool fits;
  } cases[] = {
      {0, 128, 4, 8192, 2048, true},
      {0, 129, 4, 1, 2048, false},
      {262143, 1, 4, 8192, 2048, true},
      {262144, 1, 4, 8192, 2048, false},
      {260096, 2048, 4, 8192, 2048, true},
      {260096, 2049, 4, 8192, 2048, false},
      {1046528, 2048, 4, 8192, 2048, false},
      /* Long-specialization storage: the 1M endpoint is exact, including
       * partial words and a pitch smaller than the visible word span. */
      {262144, 1, 4, 8192, 8192, true},
      {524287, 1, 4, 8192, 8192, true},
      {786431, 1, 4, 8192, 8192, true},
      {1046528, 2048, 4, 8192, 8192, true},
      {1048575, 1, 4, 8192, 8192, true},
      {1048576, 1, 4, 8193, 8192, false},
      {1048575, 1, 4, 8191, 8192, false},
      {1048575, 1, 4, 8192, 8191, false},
      {0, 131072, 2, 4096, 2048, true},
      {0, 131073, 2, 4096, 2048, false},
      {0, 1048576, 16, 8192, 2048, true},
      {UINT32_MAX - 1, 1, UINT32_MAX, 1, 1, true},
      {UINT32_MAX, 1, 4, 8192, 2048, false},
      {UINT32_MAX - 1, 2, 4, 8192, 2048, false},
      {0, 0, 4, 8192, 2048, false},
      {0, 1, 0, 8192, 2048, false},
      {0, 1, 4, 0, 2048, false},
      {0, 1, 4, 8192, 0, false},
  };
  for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
    assert(lie_attention_mask_span_fits(cases[i].start, cases[i].rows,
                                       cases[i].ratio, cases[i].pitch,
                                       cases[i].workspace) == cases[i].fits);
  }
}
int main(void) {
  sparse_mask_extents();
  lie_attention_dispatch_counter c;
  lie_attention_dispatch_init(&c, false, 0);
  lie_attention_dispatch_info empty = snapshot(&c), out = empty;
  assert(!empty.supported && !empty.domain);
  assert(lie_attention_dispatch_begin(&c) == LIE_DISPATCH_UNAVAILABLE);
  assert(lie_attention_dispatch_delta(&empty, &empty, &out) ==
         LIE_DISPATCH_UNAVAILABLE);
  assert(!memcmp(&out, &empty, sizeof(out)));
  lie_attention_dispatch_init(&c, true, 19);
  lie_attention_dispatch_info before = snapshot(&c);
  assert(lie_attention_dispatch_begin(&c) == LIE_DISPATCH_OK);
  assert(lie_attention_dispatch_begin(&c) == LIE_DISPATCH_INVALID);
  assert(lie_attention_dispatch_record(&c, LIE_ATTENTION_MATRIX_DENSE, 2, 0,
                                       LIE_ATTENTION_REFUSAL_NONE) ==
         LIE_DISPATCH_OK);
  assert(lie_attention_dispatch_record(&c, LIE_ATTENTION_MATRIX_SPARSE, 2048,
                                       2048, LIE_ATTENTION_REFUSAL_NONE) ==
         LIE_DISPATCH_OK);
  assert(lie_attention_dispatch_record(&c, LIE_ATTENTION_SCALAR_DENSE, 3, 0,
                                       LIE_ATTENTION_REFUSAL_GEOMETRY) ==
         LIE_DISPATCH_OK);
  assert(lie_attention_dispatch_record(
             &c, LIE_ATTENTION_SCALAR_SPARSE, 2048, 8192,
             LIE_ATTENTION_REFUSAL_MASK_PITCH) == LIE_DISPATCH_OK);
  lie_attention_dispatch_counter held = c;
  assert(lie_attention_dispatch_record(&c, LIE_ATTENTION_MATRIX_DENSE, 1, 0,
                                       LIE_ATTENTION_REFUSAL_GEOMETRY) ==
         LIE_DISPATCH_INVALID);
  assert(lie_attention_dispatch_record(&c, LIE_ATTENTION_SCALAR_DENSE, 1, 1,
                                       LIE_ATTENTION_REFUSAL_NONE) ==
         LIE_DISPATCH_INVALID);
  assert(lie_attention_dispatch_record(&c, LIE_ATTENTION_SCALAR_SPARSE, 1, 0,
                                       LIE_ATTENTION_REFUSAL_NONE) ==
         LIE_DISPATCH_INVALID);
  assert(lie_attention_dispatch_record(&c, LIE_ATTENTION_SCALAR_DENSE, 0, 0,
                                       LIE_ATTENTION_REFUSAL_NONE) ==
         LIE_DISPATCH_INVALID);
  assert(lie_attention_dispatch_record(&c, (lie_attention_path)-1, 1, 0,
                                       LIE_ATTENTION_REFUSAL_NONE) ==
         LIE_DISPATCH_INVALID);
  assert(lie_attention_dispatch_record(&c, LIE_ATTENTION_SCALAR_DENSE, 1, 0,
                                       (lie_attention_refusal)-1) ==
         LIE_DISPATCH_INVALID);
  assert(!memcmp(&held, &c, sizeof(c)));
  lie_attention_dispatch_info pending = snapshot(&c);
  assert(pending.pending && !pending.confirmed_batches &&
         !pending.confirmed.matrix_dense);
  out = empty;
  assert(lie_attention_dispatch_delta(&before, &pending, &out) ==
         LIE_DISPATCH_INVALID);
  assert(!memcmp(&out, &empty, sizeof(out)));
  assert(lie_attention_dispatch_finish(&c, true) == LIE_DISPATCH_OK);
  lie_attention_dispatch_info after = snapshot(&c);
  assert(after.confirmed_batches == 1 && !after.unconfirmed_batches);
  assert(after.confirmed.matrix_dense == 1 &&
         after.confirmed.matrix_sparse == 1);
  assert(after.confirmed.scalar_dense == 1 &&
         after.confirmed.scalar_sparse == 1);
  assert(after.confirmed.geometry_refusals == 1 &&
         after.confirmed.mask_pitch_refusals == 1);
  assert(after.confirmed.attention_rows == 4101);
  assert(after.max_observed_rows == 2048 &&
         after.max_observed_mask_words == 8192);
  assert(lie_attention_dispatch_finish(&c, true) == LIE_DISPATCH_INVALID);
  assert(lie_attention_dispatch_begin(&c) == LIE_DISPATCH_OK);
  assert(lie_attention_dispatch_record(
             &c, LIE_ATTENTION_SCALAR_SPARSE, UINT32_MAX, UINT32_MAX,
             LIE_ATTENTION_REFUSAL_GEOMETRY) == LIE_DISPATCH_OK);
  assert(lie_attention_dispatch_finish(&c, false) == LIE_DISPATCH_OK);
  lie_attention_dispatch_info failed = snapshot(&c);
  out = empty;
  assert(lie_attention_dispatch_delta(&after, &failed, &out) ==
         LIE_DISPATCH_OK);
  assert(!out.confirmed_batches && out.unconfirmed_batches == 1);
  assert(out.unconfirmed.scalar_sparse == 1 &&
         out.unconfirmed.geometry_refusals == 1);
  assert(out.unconfirmed.attention_rows == UINT32_MAX &&
         !out.confirmed.attention_rows);
  assert(out.max_observed_rows == UINT32_MAX &&
         out.max_observed_mask_words == UINT32_MAX);
  /* Alias support uses copied result; compare two nonzero snapshots. */
  lie_attention_dispatch_info alias = failed;
  assert(lie_attention_dispatch_delta(&after, &alias, &alias) ==
         LIE_DISPATCH_OK);
  assert(!memcmp(&alias, &out, sizeof(out)));
  alias = after;
  assert(lie_attention_dispatch_delta(&alias, &failed, &alias) ==
         LIE_DISPATCH_OK);
  assert(!memcmp(&alias, &out, sizeof(out)));
  lie_attention_dispatch_info wrong = failed;
  wrong.domain++;
  out = empty;
  assert(lie_attention_dispatch_delta(&after, &wrong, &out) ==
         LIE_DISPATCH_INVALID);
  wrong = failed;
  wrong.confirmed.attention_rows = 0;
  assert(lie_attention_dispatch_delta(&after, &wrong, &out) ==
         LIE_DISPATCH_INVALID);
  wrong = failed;
  wrong.abi_version++;
  assert(lie_attention_dispatch_delta(&after, &wrong, &out) ==
         LIE_DISPATCH_INVALID);
  assert(!memcmp(&out, &empty, sizeof(out)));
  /* Fault injection near saturation; public callers otherwise keep fields
   * readonly. */
  c.info.confirmed.matrix_dense = UINT64_MAX;
  c.info.confirmed.attention_rows = UINT64_MAX - 1;
  c.info.confirmed_batches = UINT64_MAX;
  assert(lie_attention_dispatch_begin(&c) == LIE_DISPATCH_OK);
  assert(lie_attention_dispatch_record(&c, LIE_ATTENTION_MATRIX_DENSE, 2, 0,
                                       LIE_ATTENTION_REFUSAL_NONE) ==
         LIE_DISPATCH_OK);
  assert(lie_attention_dispatch_finish(&c, true) == LIE_DISPATCH_OK);
  lie_attention_dispatch_info saturated = snapshot(&c);
  assert(saturated.overflowed && saturated.confirmed_batches == UINT64_MAX);
  assert(saturated.confirmed.matrix_dense == UINT64_MAX &&
         saturated.confirmed.attention_rows == UINT64_MAX);
  assert(lie_attention_dispatch_delta(&failed, &saturated, &out) ==
         LIE_DISPATCH_INVALID);
  assert(!memcmp(&out, &empty, sizeof(out)));
  lie_attention_dispatch_init(&c, true, 20);
  wrong = snapshot(&c);
  assert(!wrong.overflowed && !wrong.pending && !wrong.confirmed_batches);
  assert(lie_attention_dispatch_delta(&before, &wrong, &out) ==
         LIE_DISPATCH_INVALID);
  lie_attention_dispatch_init(&c, true, 0);
  assert(lie_attention_dispatch_begin(&c) == LIE_DISPATCH_INVALID);
  assert(lie_attention_dispatch_snapshot(NULL, &out) == LIE_DISPATCH_INVALID);
  puts("C17 attention dispatch contract: PASS (host-only, NOT-INFERENCE)");
  return 0;
}
