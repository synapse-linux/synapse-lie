/* SPDX-License-Identifier: MIT */
#ifndef LIE_STEERING_H
#define LIE_STEERING_H
#include "lie/executor.h"
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
#ifdef __cplusplus
}
#endif
#endif
