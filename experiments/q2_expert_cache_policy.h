/* SPDX-License-Identifier: MIT */
#ifndef LIE_Q2_EXPERT_CACHE_POLICY_H
#define LIE_Q2_EXPERT_CACHE_POLICY_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define LIE_Q2_EXPERT_CACHE_BUDGET ((size_t)32 * 1024 * 1024 * 1024)
#define LIE_Q2_EXPERT_CACHE_RESERVE ((size_t)8 * 1024 * 1024 * 1024)
#define LIE_Q2_EXPERT_CACHE_TAIL ((size_t)4096)

typedef struct lie_q2_expert_cache_plan {
    size_t tensor_payload_bytes;
    size_t tensor_allocation_bytes;
    size_t layer_allocation_bytes;
    size_t next_cache_bytes;
} lie_q2_expert_cache_plan;

/* Fixed experimental coverage: every eighth trunk layer, all its experts.
 * Admit complete gate/up/down groups. Exhaustion keeps encoded weights.
 * Own C17 accounting only: no tensor reads, allocation or model forward. */
static inline int lie_q2_expert_cache_admit(
    uint32_t layer, uint32_t layers, uint32_t experts, uint32_t hidden,
    uint32_t ff, bool supported, size_t used, size_t free_bytes,
    lie_q2_expert_cache_plan *out) {
    if (!out) return -1;
    out->tensor_payload_bytes = 0;
    out->tensor_allocation_bytes = 0;
    out->layer_allocation_bytes = 0;
    out->next_cache_bytes = 0;
    if (!supported || layers != 48 || layer >= layers || layer % 8 ||
        experts != 512 || hidden != 2560 || ff != 640) return 0;
    if ((size_t)experts > SIZE_MAX / hidden ||
        (size_t)experts * hidden > SIZE_MAX / ff) return -1;
    size_t elements = (size_t)experts * hidden * ff;
    if (elements > (SIZE_MAX - LIE_Q2_EXPERT_CACHE_TAIL) / 2) return -1;
    size_t allocation = elements * 2 + LIE_Q2_EXPERT_CACHE_TAIL;
    if (allocation > SIZE_MAX / 3) return -1;
    size_t total = 3 * allocation;
    if (used > LIE_Q2_EXPERT_CACHE_BUDGET ||
        total > LIE_Q2_EXPERT_CACHE_BUDGET - used || total > free_bytes ||
        free_bytes - total < LIE_Q2_EXPERT_CACHE_RESERVE) return 0;
    out->tensor_payload_bytes = elements * 2;
    out->tensor_allocation_bytes = allocation;
    out->layer_allocation_bytes = total;
    out->next_cache_bytes = used + total;
    return 1;
}
#endif
