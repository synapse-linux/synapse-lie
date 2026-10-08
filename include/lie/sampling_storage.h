/* SPDX-License-Identifier: MIT */
#ifndef LIE_SAMPLING_STORAGE_H
#define LIE_SAMPLING_STORAGE_H
#include "lie/sampling_history.h"
#include "lie/grammar.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_SAMPLING_STORAGE_ABI 1u
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t max_owned_bytes;
  lie_grammar_allocator allocator;
} lie_sampling_storage_description;
typedef struct {
  /* Requested live/overlap-peak bytes; successful allocations saturate at
   * SIZE_MAX. Release resets lifetime diagnostics. Clone publishes the new
   * domain's diagnostics; move transfers them with its allocations. */
  size_t live_owned_bytes, peak_owned_bytes, allocations;
} lie_sampling_storage_info;
/* Initialized move-only ownership records. Do not shallow-copy them. Their
 * embedded callback context is bound to their address; use clone/move below.
 * Direct field mutation is forbidden except writing reserved probability
 * entries through the exported workspace. Caller supplies fixed body storage.
 * No initial heap allocation. Default 64 MiB requested buffer heap per owner;
 * growth charges simultaneous old/new buffers, excludes body/hooks/overhead.
 * Paired nonthrowing hooks return fresh, disjoint max_align_t storage and
 * outlive owners. Init requires a fresh or already-released body, preserves
 * it on invalid description, and never retires an existing live owner.
 * No model, device, HTTP, RNG, thread or global mutable cache. Operations are
 * caller-serialized/nonreentrant; retire borrowers before mutation/release. */
typedef struct {
  lie_sampling_storage_description description;
  lie_sampling_storage_info info;
  lie_sampling_history_options options;
  lie_sampling_history state;
} lie_sampling_history_storage;
typedef struct {
  lie_sampling_storage_description description;
  lie_sampling_storage_info info;
  lie_sampling_probability *entries;
  size_t count, capacity;
} lie_sampling_probability_storage;
void lie_sampling_storage_description_init(lie_sampling_storage_description *);
lie_sampling_history_status lie_sampling_history_storage_init(
  lie_sampling_history_storage *, const lie_sampling_storage_description *);
void lie_sampling_history_storage_release(lie_sampling_history_storage *);
lie_sampling_history_status lie_sampling_history_storage_reset(
  lie_sampling_history_storage *, const lie_sampling_history_options *, const uint32_t *, size_t);
lie_sampling_history_status lie_sampling_history_storage_accept(
  lie_sampling_history_storage *, const uint32_t *, size_t);
/* Transactional logical clone into an initialized owner. New clone allocations
 * are a separate temporary owner/domain; both domains count their own buffers.
 * On refusal destination contents and source remain unchanged. Move releases
 * destination, transfers exact buffers/allocator/options and rebinds callbacks;
 * source remains initialized, empty and reusable. Self clone/move is a no-op.
 * Clone refuses overlapping records. Move requires disjoint records (or self).
 * Reset/accept input aliasing owned allocations refuses. */
lie_sampling_history_status lie_sampling_history_storage_clone(
  lie_sampling_history_storage *, const lie_sampling_history_storage *);
void lie_sampling_history_storage_move(lie_sampling_history_storage *, lie_sampling_history_storage *);
lie_sampling_status lie_sampling_probability_storage_init(
  lie_sampling_probability_storage *, const lie_sampling_storage_description *);
void lie_sampling_probability_storage_release(lie_sampling_probability_storage *);
lie_sampling_status lie_sampling_probability_storage_reserve(lie_sampling_probability_storage *, size_t);
/* Assigned input is disjoint from destination allocations. Assign/clone publish
 * count only after reserve/copy success. Allocation refusal preserves contents;
 * capacity/cost diagnostics may advance. Move transfers exact buffers and hooks.
 * A workspace borrows the owner; native C growth preserves ALL old capacity,
 * including algorithm staging above logical count. Caller writes live entries
 * then publishes count; publish never initializes or changes probability bits.
 * On algorithm refusal retire/discard unpublished staging per its contract. */
lie_sampling_status lie_sampling_probability_storage_assign(
  lie_sampling_probability_storage *, const lie_sampling_probability *, size_t);
lie_sampling_status lie_sampling_probability_storage_clone(
  lie_sampling_probability_storage *, const lie_sampling_probability_storage *);
void lie_sampling_probability_storage_move(lie_sampling_probability_storage *, lie_sampling_probability_storage *);
lie_sampling_workspace lie_sampling_probability_storage_workspace(lie_sampling_probability_storage *);
lie_sampling_status lie_sampling_probability_storage_publish(lie_sampling_probability_storage *, size_t);
#ifdef __cplusplus
}
#endif
#endif
