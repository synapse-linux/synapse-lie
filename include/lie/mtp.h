/* SPDX-License-Identifier: MIT */
#ifndef LIE_MTP_H
#define LIE_MTP_H
#include "lie/executor.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_MTP_ABI 1u
/* Core allocation bound, not a model architecture or predictor length. */
#define LIE_MTP_MAX_OUTPUT 32u
#define LIE_MTP_MAX_DRAFT (LIE_MTP_MAX_OUTPUT - 1u)
typedef struct {
  uint32_t abi_version, struct_bytes;
  uint32_t max_draft_tokens, max_output_tokens;
  uint32_t prefix_state_supported;
} lie_mtp_info;
lie_status lie_model_mtp_info(lie_model *, lie_mtp_info *, lie_error *);
/* Completed, target-verified output only. Proposals never consume consumer
 * credits. Callers reserve output capacity before submission; unused credits
 * are refunded on commit. Cancellation suppresses the entire late result. */
typedef struct {
  lie_status status;
  int32_t tokens[LIE_MTP_MAX_OUTPUT];
  uint32_t emitted, stop, position;
  uint64_t drafted, accepted;
} lie_mtp_outcome;
/* Explicit predictor admission, no automatic sidecar discovery or fallback.
 * Same device-owner and failure-poisoning contract as executor ABI 2.
 * max_draft=0 selects the provider default; otherwise admission validates it
 * against that model. Query the admitted burst bound before allocating outputs.
 */
lie_status lie_backend_open_mtp(const char *, const lie_model_options *,
                                uint32_t, const char *, uint32_t, lie_model **,
                                lie_error *);
lie_status lie_sequences_decode_mtp(lie_sequence *const *, const uint32_t *,
                                    size_t, lie_mtp_outcome *, lie_error *);
#ifdef __cplusplus
}
#endif
#endif
