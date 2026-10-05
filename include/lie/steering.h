/* SPDX-License-Identifier: MIT */
#ifndef LIE_STEERING_H
#define LIE_STEERING_H
#include "lie/executor.h"
#include <stdbool.h>
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_STEERING_ABI 1u
typedef struct lie_steering_bank lie_steering_bank;
/* Geometry comes from the admitted model, never a hardcoded architecture.
 * max_bytes is the caller's explicit host memory budget for vector data. */
typedef struct {
  uint32_t abi_version, struct_bytes, layers, width;
  uint64_t max_bytes;
} lie_steering_geometry;
typedef struct {
  uint32_t abi_version, struct_bytes, layers, width;
  uint64_t bytes;
  unsigned char file_sha256[32], scope_sha256[32];
} lie_steering_info;
/* DS4-compatible headerless little-endian IEEE754 f32, layer-major.
 * Exactly layers*width finite values are required; values, including zero
 * directions, are preserved without normalization. The source is read-only.
 * Version/size tags and a NULL output handle are required. Failures leave the
 * handle unchanged; no model/GPU operation occurs in this host loader. */
lie_status lie_steering_bank_load(const char *, const lie_steering_geometry *,
                                  lie_steering_bank **, lie_error *);
lie_status lie_steering_bank_info(const lie_steering_bank *, lie_steering_info *,
                                  lie_error *);
/* The immutable span is borrowed for the lifetime of an owned bank reference.
 * File identity describes exact bytes; scope additionally binds tensor geometry.
 * Cache users must also bind model identity and effective steering scale/history. */
const float *lie_steering_bank_values(const lie_steering_bank *);
/* Reference operations are thread-safe while the caller holds an owned pin;
 * racing a final release with an unpinned borrow is invalid. */
lie_status lie_steering_bank_retain(lie_steering_bank *);
void lie_steering_bank_release(lie_steering_bank **);

/* Owned session policy and cache identity. This does not execute GPU steering.
 * Mutations run on the creating device owner; snapshots/references are safe
 * with an owned pin. Prepare before numerical work; commit only its completed
 * target-forward frontier, or discard. Deferred sampled tokens, predictor work
 * and rejected drafts do not advance this frontier. Failed work never commits. */
#define LIE_STEERING_POLICY_ABI 1u
#define LIE_STEERING_MAX_UPDATES 2u
typedef struct lie_steering_policy lie_steering_policy;
typedef struct lie_steering_update lie_steering_update;
typedef struct {
  uint32_t abi_version, struct_bytes;
  float ffn, attention; /* Finite -100..100; zero disables this edit. */
} lie_steering_settings;
void lie_steering_settings_init(lie_steering_settings *, bool bank_present);
typedef struct {
  uint32_t abi_version, struct_bytes;
  uint64_t max_positions;
  lie_steering_bank *bank; /* Retained on success; NULL permits zero scales. */
  lie_steering_settings settings;
} lie_steering_policy_options;
typedef struct {
  uint32_t abi_version, struct_bytes;
  uint64_t max_positions, completed_positions, revision, history_epochs;
  uint64_t policy_bytes, staged_bytes;
  uint32_t outstanding_updates;
  bool bank_present, has_completed_work, has_steered_history;
  lie_steering_settings settings, last_completed_settings;
  lie_steering_info bank;
  unsigned char history_sha256[32], cache_scope_sha256[32];
} lie_steering_policy_info;
lie_status lie_steering_policy_create(const lie_steering_policy_options *,
                                      lie_steering_policy **, lie_error *);
lie_status lie_steering_policy_snapshot(const lie_steering_policy *,
                                        lie_steering_policy_info *, lie_error *);
/* Change future scale policy without modifying past history. The application
 * applies/invalidate device state first, then commits at the same frontier. */
lie_status lie_steering_policy_prepare_change(lie_steering_policy *,
  const lie_steering_settings *, lie_steering_update **, lie_error *);
/* Reserve at most maximum_positions absolute positions. The prepared history
 * is independent of actual burst size. Commit confirms any frontier in
 * [old, maximum]; old means no target advance and leaves policy unchanged. */
lie_status lie_steering_policy_prepare_advance(lie_steering_policy *,
  uint64_t maximum_positions, lie_steering_update **, lie_error *);
/* Model binding: independently observed retained frontier must agree with the
 * owned policy before submission. Equal maximum is a no-op with NULL plan.
 * A divergent actual frontier is BACKEND_FAILED and requires model poisoning.
 * Complete after the model call (even when delivery is cancelled), with actual
 * retained positions only. Refusals never consume the plan or publish history. */
lie_status lie_steering_forward_prepare(lie_steering_policy *,
  uint64_t actual_positions, uint64_t maximum_positions,
  lie_steering_update **, lie_error *);
lie_status lie_steering_forward_complete(lie_steering_policy *,
  lie_steering_update **, uint64_t actual_positions, lie_error *);
const lie_steering_settings *lie_steering_update_settings(const lie_steering_update *);
/* Success consumes the update. Refusal preserves both update and live state.
 * A stale/wrong-owner commit after device mutation requires model poisoning,
 * not retry. Plans pin their policy until committed or discarded. */
lie_status lie_steering_update_commit(lie_steering_update **,
                                     uint64_t completed_positions, lie_error *);
void lie_steering_update_discard(lie_steering_update **);
lie_status lie_steering_policy_retain(lie_steering_policy *);
void lie_steering_policy_release(lie_steering_policy **);
/* Preserve exact legacy/image scope when steering has no numerical history.
 * Nonzero steering and image scopes combine in a separate SHA domain. Model
 * identity and complete payload admission remain the storage owner's duty. */
lie_status lie_steering_policy_cache_scope(const lie_steering_policy *,
  const unsigned char semantic_scope[32], unsigned char out[32], lie_error *);
/* Fixed model-neutral metadata for RAM/SSD state bindings, never a C struct
 * dump or a replacement for the DS4 tensor payload. Owner-only capture rejects
 * outstanding numerical updates. Little-endian fields and SHA-256 checksum;
 * the containing state must separately bind model/input identity and payload.
 * Export writes exactly STATE_BYTES and preserves output on every refusal. */
#define LIE_STEERING_STATE_BYTES 192u
lie_status lie_steering_policy_encode(const lie_steering_policy *,
  unsigned char *out, size_t capacity, lie_error *);
/* Prepare before any device transfer into a pristine destination policy.
 * completed_positions is the independently validated model-state frontier.
 * Encoded metadata must match its bank and reconstruct its cache scope.
 * NULL/zero bytes denotes an unsteered legacy state and requires zero scales.
 * The plan owns its decoded metadata; no input span survives the call. Commit
 * only the exact restored frontier after successful device transfer, or discard.
 * No live policy is mutated during parsing/preparation. Destination capacity
 * and revision remain its own; captured runtime counters are not serialized. */
lie_status lie_steering_policy_prepare_restore(lie_steering_policy *,
  const unsigned char *state, size_t bytes, uint64_t completed_positions,
  lie_steering_update **, lie_error *);
/* On the owner, validate a staged restore's semantic scope before device
 * transfer. Uses the immutable prepared policy without committing live state. */
lie_status lie_steering_update_cache_scope(const lie_steering_update *,
  const unsigned char semantic_scope[32], unsigned char out[32], lie_error *);

/* Independent model admission ABI. File is borrowed through open/load only;
 * geometry is supplied by the admitted model before its first GPU upload. */
#define LIE_STEERING_MODEL_ABI 1u
#define LIE_STEERING_DEFAULT_VECTOR_BUDGET (UINT64_C(16) * 1024u * 1024u)
typedef struct {
  uint32_t abi_version, struct_bytes;
  const char *file;
  uint64_t vector_budget_bytes;
  lie_steering_settings defaults;
} lie_steering_model_options;
void lie_steering_model_options_init(lie_steering_model_options *);
/* Shared en_US CLI parsing: 1 accepted, 0 unknown option, -1 invalid/disabled.
 * The file value remains borrowed until core/model admission copies it.
 * Both clients require a file whenever any scale option is supplied. */
int lie_steering_model_option(lie_steering_model_options *,const char *,const char *);
/* Bounded C17 admission shared by model providers, no device/model forward. */
lie_status lie_steering_model_bank_load(const lie_steering_model_options *,
  uint32_t layers, uint32_t width, lie_steering_bank **, lie_error *);
typedef struct {
  uint32_t abi_version, struct_bytes;
  bool admitted, prefix_state_supported;
  lie_steering_info bank;
  lie_steering_settings defaults;
  uint64_t device_vector_bytes;
} lie_steering_model_info;
/* Explicit composition, never automatic fallback. Optional predictor/projector
 * are admitted by the same selected provider. Existing open functions retain
 * their exact absent-steering path. GPU qualification remains separate. */
lie_status lie_backend_open_steered(const char *, const lie_model_options *,
  uint32_t width, const char *predictor, uint32_t drafts, const char *projector,
  const lie_steering_model_options *, lie_model **, lie_error *);
lie_status lie_model_steering_info(lie_model *, lie_steering_model_info *, lie_error *);
/* Initial owner-only configuration, before prefill, restore or sampling.
 * Live scale changes are not supported yet. Prefix restore validates owned
 * policy metadata together with complete model state before transfer. */
lie_status lie_sequence_configure_steering(lie_sequence *,
  const lie_steering_settings *, lie_error *);
lie_status lie_sequence_steering_info(lie_sequence *, lie_steering_policy_info *, lie_error *);
lie_status lie_sequence_steering_cache_scope(lie_sequence *,
  const unsigned char semantic_scope[32], unsigned char out[32], lie_error *);
#ifdef __cplusplus
}
#endif
#endif
