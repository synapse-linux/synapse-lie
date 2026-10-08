/* SPDX-License-Identifier: MIT */
#ifndef LIE_ACTIVATION_OBSERVER_H
#define LIE_ACTIVATION_OBSERVER_H
#include "lie/executor.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_ACTIVATION_OBSERVER_ABI 1u
typedef enum {
  LIE_ACTIVATION_ATTENTION = 1u,
  LIE_ACTIVATION_FFN = 2u
} lie_activation_component;
typedef struct {
  uint32_t abi_version, struct_bytes, layers, width, ffn_branches, components;
} lie_activation_geometry;
typedef struct {
  uint32_t abi_version, struct_bytes;
  lie_activation_component component;
  uint32_t layer, layers, width, branches;
  uint64_t token_position; /* Zero-based physical prompt token. */
  const float *values; /* Branch-major completed F32 host rows. */
  size_t value_count;
} lie_activation_observation;
typedef struct {
  uint32_t abi_version, struct_bytes, components;
  uint64_t max_row_bytes; /* Host row allocation bound, excluding allocator overhead. */
  void (*observe)(void *, const lie_activation_observation *);
  void *context;
} lie_activation_observer;
/* Owner-only geometry, without device work. Unsupported providers refuse. */
lie_status lie_model_activation_geometry(lie_model *, lie_activation_geometry *, lie_error *);
/* Diagnostic of the existing completed prefill path, including one-token tails.
 * Captures only the last token in the supplied cumulative prefix, at ordinary
 * trunk attention output and completed FFN residual branches, after any steering.
 * The observer is copied for this call only; its context must outlive the call.
 * Each values span is borrowed only during its callback. Copy there; never
 * retain pointers, throw, destroy handles or reenter executor APIs. Callbacks
 * cannot veto, edit or retry inference. No callback remains after any return.
 * Rows precede full-call completion: failures/cancellation can leave partial
 * captures. A learner must confirm successful prefill AND complete layer rows.
 * MTP predictor/decode/verification do not contribute rows. Capture requires
 * new prompt tokens; an unchanged frontier refuses. No throughput measurement
 * includes diagnostic copies, device waits, callbacks or file I/O. */
lie_status lie_sequence_prefill_observed(lie_sequence *, const int32_t *, size_t,
  const lie_activation_observer *, lie_error *);
#ifdef __cplusplus
}
#endif
#endif
