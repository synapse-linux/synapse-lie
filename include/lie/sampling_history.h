/* SPDX-License-Identifier: MIT */
/* Model-neutral request history; caller-owned storage, no device or threads. */
#ifndef LIE_SAMPLING_HISTORY_H
#define LIE_SAMPLING_HISTORY_H
#include "lie/sampling.h"
#include <stdbool.h>
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_SAMPLING_HISTORY_ABI 1u
typedef enum {
  LIE_HISTORY_OK,
  LIE_HISTORY_INVALID,
  LIE_HISTORY_RESOURCE,
  LIE_HISTORY_OVERFLOW
} lie_sampling_history_status;
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t repeat_last_n, max_penalties, max_batch_tokens;
  bool generated, repetition;
} lie_sampling_history_options;
typedef int (*lie_history_grow_tokens)(void *, size_t, uint32_t **, size_t *);
typedef int (*lie_history_grow_penalties)(void *, size_t,
                                          lie_sampling_penalty **, size_t *);
typedef struct {
  uint32_t *tokens;
  size_t token_count, token_capacity;
  lie_sampling_penalty *penalties;
  size_t penalty_count, penalty_capacity;
  lie_history_grow_tokens grow_tokens;
  lie_history_grow_penalties grow_penalties;
  void *context;
} lie_sampling_history;
void lie_sampling_history_options_init(lie_sampling_history_options *);
/* One owner mutates a workspace. Options stay fixed until reset. Input/copy
 * sources must not alias workspace allocations. Growth preserves existing
 * entries and must not invalidate other borrowed input. Clients enforce their
 * allocation budget; the C module never allocates, frees or retains pointers.
 * Reset uses only the prompt tail: prompt tokens never count as generated.
 * Accept counts all committed generated tokens, including those outside the
 * repetition window. Repeated flags are boolean; penalties stay sorted/unique.
 * Refusal preserves logical entries/counts, but capacity and unpublished
 * scratch may change. Bulk acceptance stages up to the number of input tokens;
 * ordinary single-token acceptance requires no staging buffer. No RNG/draw is
 * changed. */
lie_sampling_history_status
lie_sampling_history_reset(const lie_sampling_history_options *,
                           lie_sampling_history *, const uint32_t *, size_t);
lie_sampling_history_status
lie_sampling_history_accept(const lie_sampling_history_options *,
                            lie_sampling_history *, const uint32_t *, size_t);
/* Copies independent history/counts only, leaving RNG/grammar to their owners.
 * Self-copy is a no-op; other overlapping allocations are refused. */
lie_sampling_history_status
lie_sampling_history_copy(const lie_sampling_history_options *,
                          lie_sampling_history *, const lie_sampling_history *);
#ifdef __cplusplus
}
#endif
#endif
