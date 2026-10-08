/* SPDX-License-Identifier: MIT */
#ifndef LIE_STEERING_CAPTURE_H
#define LIE_STEERING_CAPTURE_H
#include "lie/activation_observer.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_STEERING_CAPTURE_ABI 1u
typedef struct lie_steering_capture lie_steering_capture;
typedef struct {
  uint32_t abi_version, struct_bytes;
  lie_activation_geometry geometry;
  uint32_t components;
  uint64_t token_position, max_bytes;
} lie_steering_capture_options;
typedef struct {
  uint32_t abi_version, struct_bytes, ready;
  uint64_t rows, expected_rows, requested_bytes;
} lie_steering_capture_info;
/* C17 collector; no device, model, HTTP or independent threads. Exact geometry,
 * token identity and unique component/layer rows are required. FFN branches
 * are averaged; attention has one branch. Borrowed inputs are never retained.
 * Requested bytes include owner, row-presence map and selected F32 matrices. */
lie_status lie_steering_capture_create(const lie_steering_capture_options *,
  lie_steering_capture **, lie_error *);
lie_status lie_steering_capture_add(lie_steering_capture *,
  const lie_activation_observation *, lie_error *);
/* Publication requires both actual successful prefill and every selected row.
 * Failed completion seals this capture against later publication. Partial rows
 * remain inspectable through snapshot for failure evidence, never as a bank. */
lie_status lie_steering_capture_finish(lie_steering_capture *, lie_status prefill_status,
  uint64_t completed_prefix_tokens, lie_error *);
lie_status lie_steering_capture_snapshot(const lie_steering_capture *,
  lie_steering_capture_info *, lie_error *);
/* Borrowed component activation matrix until destroy; NULL unless ready.
 * This matrix contains activations, not yet a normalized direction bank. */
const float *lie_steering_capture_values(const lie_steering_capture *, lie_activation_component);
void lie_steering_capture_destroy(lie_steering_capture **);
#ifdef __cplusplus
}
#endif
#endif
