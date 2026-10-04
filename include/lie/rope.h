/* SPDX-License-Identifier: MIT */
#ifndef LIE_ROPE_H
#define LIE_ROPE_H
#include <stdbool.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef enum { LIE_ROPE_NATIVE, LIE_ROPE_YARN2, LIE_ROPE_YARN4 } lie_rope_profile;
#define LIE_ROPE_PLAN_ABI 1u
#define LIE_ROPE_MAX_DIM 256u
#define LIE_CONTEXT_LIMIT 1048576u
/* Immutable model profile. Positions remain physical; image axes use the same
 * frequencies. This is an operator contract, not long-context quality evidence. */
typedef struct {
    uint32_t abi_version, native_context, context_limit, rotary_dim;
    lie_rope_profile profile;
    float attention_factor;
    float inv_frequency[LIE_ROPE_MAX_DIM / 2];
} lie_rope_plan;
const char *lie_rope_profile_name(lie_rope_profile);
bool lie_rope_profile_parse(const char *, lie_rope_profile *);
/* Static YaRN, beta_fast=32, beta_slow=1; no dependence on current position.
 * Failure leaves the destination untouched. Native execution need not use the
 * table, allowing an existing arithmetic path to remain unchanged. */
bool lie_rope_plan_build(lie_rope_profile, uint32_t native_context,
                         uint32_t rotary_dim, double theta, lie_rope_plan *);
uint64_t lie_rope_plan_domain(const lie_rope_plan *);
#ifdef __cplusplus
}
#endif
#endif
