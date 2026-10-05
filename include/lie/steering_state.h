/* SPDX-License-Identifier: MIT */
#ifndef LIE_STEERING_STATE_H
#define LIE_STEERING_STATE_H
#include "lie/steering.h"
#include "lie/state.h"
#ifdef __cplusplus
extern "C" {
#endif
/* C17 model-neutral binding. Model descriptors and tensor bytes remain a prefix;
 * policy/scope live in the existing typed auxiliary envelope, without a second
 * tensor copy. No provider type, device call or transport enters this ABI. */
#define LIE_STEERING_STATE_BINDING_ABI 1u
#define LIE_STEERING_STATE_NO_OFFSET UINT64_MAX
typedef struct {
  uint32_t abi_version, struct_bytes;
  lie_state_layout model;
  uint64_t model_bytes, payload_bytes;
  uint64_t policy_offset, scope_offset, inserted_auxiliary_offset;
} lie_steering_state_view;
/* Extend a validated model layout; omit extension only through plan below.
 * Existing semantic scope is reused, never duplicated or moved. */
lie_status lie_steering_state_extend(const lie_state_layout *, lie_state_layout *, lie_error *);
/* The trusted model binding supplies its independently expected model format,
 * then re-describes and checks the returned model layout against actual geometry.
 * This function validates canonical framing, not numerical model content. */
lie_status lie_steering_state_inspect(const lie_state_layout *, uint32_t model_format,
  lie_steering_state_view *, lie_error *);
/* Owner-only capture plan: policy frontier must equal model token_count.
 * No active scales/history preserves the exact legacy layout. */
lie_status lie_steering_state_plan(lie_steering_policy *, const lie_state_layout *,
  lie_state_layout *, lie_error *);
/* After completed model capture, writes only policy/scope/new auxiliary bytes.
 * All admission precedes writes. The raw buffer contains the outer payload. */
lie_status lie_steering_state_capture(lie_steering_policy *, const lie_state_layout *,
  uint32_t model_format, const unsigned char semantic_scope[32],
  void *payload, size_t bytes, lie_error *);
/* Prefix-only restore: validate metadata, bank, actual retained count, semantic
 * scope and current initial scales before model mutation. The staged scope must
 * match the destination's requested initial history, preventing token-only reuse.
 * The model still validates all tensor content before upload. Success returns
 * an owned plan and combined scope; refusals preserve both output objects.
 * Commit exactly the independently observed restored frontier after transfer,
 * including successful transfers whose client delivery is cancelled. */
lie_status lie_steering_state_prepare_restore(lie_steering_policy *, const lie_state_layout *,
  uint32_t model_format, const unsigned char semantic_scope[32],
  const void *payload, size_t bytes, lie_steering_update **,
  unsigned char combined_scope[32], lie_error *);
#ifdef __cplusplus
}
#endif
#endif
