/* SPDX-License-Identifier: MIT */
#ifndef LIE_STEERING_ACTIVATION_H
#define LIE_STEERING_ACTIVATION_H
#include "lie/executor.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Model-neutral geometry for y -= scale * d * dot(d,y). Every token/branch
 * is an independent contiguous hidden-width row; d is one layer's direction.
 * This descriptor validates a launch, not numerical execution or model state. */
#define LIE_STEERING_ACTIVATION_ABI 1u
typedef struct {
  uint32_t abi_version, struct_bytes;
  uint32_t width, tokens, branches, rows;
  float scale;
  uint64_t elements, activation_bytes, direction_bytes;
} lie_steering_activation;
/* Set output ABI/size first. Refusal preserves every output byte. Capacities
 * describe the available spans, not allocation requests. No normalization,
 * device access, allocation or thread creation takes place here. Zero scale
 * is canonical positive zero and permits the provider's exact no-launch path. */
lie_status lie_steering_activation_prepare(uint32_t width, uint32_t tokens,
  uint32_t branches, float scale, uint64_t activation_capacity,
  uint64_t direction_capacity, lie_steering_activation *, lie_error *);
#ifdef __cplusplus
}
#endif
#endif
