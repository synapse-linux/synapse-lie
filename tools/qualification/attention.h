/* SPDX-License-Identifier: MIT */
#ifndef LIE_QUALIFICATION_ATTENTION_H
#define LIE_QUALIFICATION_ATTENTION_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_ATTENTION_FIXTURE_COUNT 13u
#define LIE_ATTENTION_FIXTURE_WIDTH 6144u
/* Generated component fixtures only. No model, HTTP or performance contract.
 * Prefix selections are disjoint across rows, then translated monotonically
 * into a short context. Both worlds have identical ordered K/V and causal tails.
 * Plans own their three arrays; fields are readonly until dispose. */
typedef struct {
  uint32_t end, rows, selections;
  bool zero_mask, zero_query;
} lie_attention_fixture_spec;
typedef struct {
  lie_attention_fixture_spec spec;
  uint32_t deep_start, short_start, deep_capacity, short_capacity;
  uint32_t deep_pitch, short_pitch, short_base, prefix_blocks, block_count;
  uint32_t *blocks, *deep_mask, *short_mask;
} lie_attention_fixture_plan;
extern const lie_attention_fixture_spec
    lie_attention_fixture_specs[LIE_ATTENTION_FIXTURE_COUNT];
/* Initialized zero/disposed output required; refusal preserves it. */
int lie_attention_fixture_prepare(const lie_attention_fixture_spec *,
                                  lie_attention_fixture_plan *);
void lie_attention_fixture_dispose(lie_attention_fixture_plan *);
typedef struct {
  bool gpu_execution, accepted, short_accepted, expected_refusal, output_unchanged;
  uint32_t refusal, primary_error, cleanup_error;
  uint64_t requested_device_bytes;
  char device_arch[128];
} lie_attention_fixture_result;
/* Only the HIP adapter implements this function in a real-device executable.
 * Output spans are caller-owned, disjoint, exactly rows*6144 floats each.
 * All borrowed inputs/outputs are retired before return, including failures.
 * A GPU fault cannot be interpreted as an expected host admission refusal. */
int lie_attention_fixture_gpu(const lie_attention_fixture_plan *, float *,
                              float *, lie_attention_fixture_result *);
#ifdef __cplusplus
}
#endif
#endif
