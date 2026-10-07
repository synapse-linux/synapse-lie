/* SPDX-License-Identifier: MIT */
#ifndef LIE_STEERING_DIRECTION_H
#define LIE_STEERING_DIRECTION_H
#include "lie/executor.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_STEERING_DIRECTION_ABI 1u
/* Independent model geometry; no HTTP, device operation or model forward.
 * Requested-byte accounting includes the owner, aligned compensated sums, normalized
 * output and per-layer norms; allocator overhead and caller inputs are excluded.
 * Owners are serialized and nonreentrant, with no threads or global state. */
typedef struct {
  uint32_t abi_version, struct_bytes, layers, width;
  uint64_t max_pairs, max_bytes;
} lie_steering_direction_options;
typedef struct {
  uint32_t abi_version, struct_bytes, layers, width, ready;
  uint64_t pairs, max_pairs, bank_bytes, requested_bytes, max_bytes;
} lie_steering_direction_info;
typedef struct lie_steering_direction lie_steering_direction;
lie_status lie_steering_direction_create(const lie_steering_direction_options *,
  lie_steering_direction **, lie_error *);
/* Complete layer-major matrices, already averaged over any residual branches.
 * All input values must be finite. Refusal preserves sums/counts/publication.
 * Input spans are borrowed for this call only and may overlap each other. */
lie_status lie_steering_direction_add_pair(lie_steering_direction *,
  const float *target, const float *contrast, size_t values, lie_error *);
/* Normalize the ordered compensated FP64 sum of paired target-minus-contrast rows to unit
 * L2 per layer; final values are binary32. Averaging over the pair count before
 * normalization gives the same mathematical direction. A zero layer refuses
 * without publication; more pairs may then be added. Publication is immutable.
 * This is a learned bank only when its input activations and model provenance
 * have separately been qualified. CPU fixtures establish none of that. */
lie_status lie_steering_direction_finish(lie_steering_direction *, lie_error *);
lie_status lie_steering_direction_snapshot(const lie_steering_direction *,
  lie_steering_direction_info *, lie_error *);
/* Borrowed until destroy. NULL before successful finish. Layer-major host
 * floats; a file writer must encode headerless little-endian binary32. */
const float *lie_steering_direction_values(const lie_steering_direction *);
void lie_steering_direction_destroy(lie_steering_direction **);
/* Average one token's branch-major hidden-width F32 rows. Distinct input/output
 * spans and exact lengths are required. Nonfinite/invalid/overlapping inputs
 * refuse before any output byte changes. No allocation or pointer retention. */
lie_status lie_steering_direction_mean_branches(uint32_t width, uint32_t branches,
  const float *input, size_t input_values, float *output, size_t output_values,
  lie_error *);
#ifdef __cplusplus
}
#endif
#endif
