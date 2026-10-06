/* SPDX-License-Identifier: MIT */
#ifndef LIE_DISPATCH_H
#define LIE_DISPATCH_H
#include <stdbool.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_ATTENTION_DISPATCH_ABI 1u
typedef enum {
  LIE_ATTENTION_MATRIX_DENSE,
  LIE_ATTENTION_MATRIX_SPARSE,
  LIE_ATTENTION_SCALAR_DENSE,
  LIE_ATTENTION_SCALAR_SPARSE
} lie_attention_path;
typedef enum {
  LIE_ATTENTION_REFUSAL_NONE,
  LIE_ATTENTION_REFUSAL_GEOMETRY,
  LIE_ATTENTION_REFUSAL_MASK_PITCH
} lie_attention_refusal;
typedef enum {
  LIE_DISPATCH_OK,
  LIE_DISPATCH_INVALID,
  LIE_DISPATCH_UNAVAILABLE
} lie_dispatch_status;
typedef struct {
  uint64_t matrix_dense, matrix_sparse, scalar_dense, scalar_sparse;
  uint64_t geometry_refusals, mask_pitch_refusals, attention_rows;
} lie_attention_dispatch_totals;
typedef struct {
  uint32_t abi_version, struct_bytes;
  bool supported, pending, overflowed;
  uint64_t domain; /* Process-local model observer epoch; never compare across
                      processes. */
  uint64_t confirmed_batches, unconfirmed_batches;
  lie_attention_dispatch_totals confirmed, unconfirmed;
  /* Lifetime maxima of host-observed calls, including unconfirmed batches.
   * Rows count attention rows per layer, not physical prompt tokens. */
  uint32_t max_observed_rows, max_observed_mask_words;
} lie_attention_dispatch_info;
/* Inline caller-owned storage; no heap, lock, thread or device work.
 * Fields are readonly to callers after init. Record/snapshot calls are
 * serialized on the numerical owner. Cross-thread clients use a copied
 * shared-core snapshot instead of reading this storage directly.
 * Observer storage outlives the numerical model that borrows its pointer. */
typedef struct {
  lie_attention_dispatch_info info;
  lie_attention_dispatch_totals staged;
} lie_attention_dispatch_counter;
void lie_attention_dispatch_info_init(lie_attention_dispatch_info *);
/* Nonzero, unique model epoch required when supported; reset changes epoch. */
void lie_attention_dispatch_init(lie_attention_dispatch_counter *, bool,
                                 uint64_t);
/* One transaction around a completed model prefill call. No nesting.
 * Record only actual host selections, never graph capture/replay estimates.
 * finish(true) requires numerical completion; finish(false) keeps all
 * observed work unconfirmed, including exceptions/cancellation before return.
 * Refusal preserves state/output. Counter additions saturate and latch
 * overflowed, making exact interpretation unavailable; no wrap or retry.
 * Output snapshot storage is disjoint from the counter. */
lie_dispatch_status
lie_attention_dispatch_begin(lie_attention_dispatch_counter *);
lie_dispatch_status
lie_attention_dispatch_record(lie_attention_dispatch_counter *,
                              lie_attention_path, uint32_t, uint32_t,
                              lie_attention_refusal);
lie_dispatch_status
lie_attention_dispatch_finish(lie_attention_dispatch_counter *, bool);
lie_dispatch_status
lie_attention_dispatch_snapshot(const lie_attention_dispatch_counter *,
                                lie_attention_dispatch_info *);
/* Counter delta for one model's observation window. Input/output aliases are
 * allowed. Maxima remain explicitly lifetime maxima; they are not subtracted.
 * Availability/overflow/pending or decreasing counters refuse exact deltas. */
lie_dispatch_status
lie_attention_dispatch_delta(const lie_attention_dispatch_info *,
                             const lie_attention_dispatch_info *,
                             lie_attention_dispatch_info *);
#ifdef __cplusplus
}
#endif
#endif
