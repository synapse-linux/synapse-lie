/* SPDX-License-Identifier: MIT */
/* Owner-only numerical diagnostics; no HTTP, scheduler or sampling policy. */
#ifndef LIE_SAMPLING_OBSERVER_H
#define LIE_SAMPLING_OBSERVER_H
#include "lie/mtp.h"
#include "lie/sampling.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_SAMPLING_OBSERVER_ABI 1u
typedef enum {
  LIE_SAMPLING_OBSERVE_TARGET_DRAW = 1,
  LIE_SAMPLING_OBSERVE_PROPOSAL = 2,
  LIE_SAMPLING_OBSERVE_VERIFICATION = 3
} lie_sampling_observation_kind;
typedef struct {
  uint32_t abi_version, struct_bytes;
  lie_sampling_observation_kind kind;
  uint32_t token, accepted, deferred;
  uint64_t rng_before, rng_after;
  const float *logits;
  size_t logit_count;
  /* Proposal rows map compact positions to model IDs; target rows use NULL. */
  const uint32_t *logit_ids;
  const uint8_t *allowed;
  size_t allowed_count;
  const uint32_t *history;
  size_t history_count;
  const lie_sampling_penalty *penalties;
  size_t penalty_count;
  const uint32_t *proposal_ids;
  const float *proposal_probabilities;
  size_t proposal_count;
  uint32_t proposal_token;
  float proposal_probability;
} lie_sampling_observation;
typedef struct {
  uint32_t abi_version, struct_bytes;
  void (*observe)(void *, const lie_sampling_observation *);
  void *context;
} lie_sampling_observer;
/* Synchronous single-sequence diagnostic call on the existing device owner.
 * All row/mask/history/proposal pointers are borrowed for the callback only.
 * Copy required data there; never retain pointers, throw, destroy state or call
 * executor APIs from the callback. It cannot veto, edit or retry numerical work.
 * A writer failure is recorded by the client and checked after the call returns.
 * No callback is installed after return, including failure. Unsupported providers
 * explicitly refuse. Invalid observer/owner/nested admission preserves output.
 * GPU greedy verification need not expose host rows: absent observations are
 * not evidence for those predictions. No throughput claim includes capture I/O.
 */
lie_status lie_sequence_decode_mtp_observed(lie_sequence *, uint32_t,
    const lie_sampling_observer *, lie_mtp_outcome *, lie_error *);
#ifdef __cplusplus
}
#endif
#endif
