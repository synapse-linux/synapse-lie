/* SPDX-License-Identifier: MIT */
#ifndef LIE_Q2_HC_INJECT_SCRATCH_H
#define LIE_Q2_HC_INJECT_SCRATCH_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Allocation identity, never a new allocation or an asynchronous lease.
 * The executor queues combine -> producer -> reducer -> MoE on one stream.
 * Reject offset scratch views and any unconsumed expert output. */
typedef struct {
    float *base;
    size_t bytes;
} lie_q2_hc_inject_scratch;

static inline size_t lie_q2_hc_inject_capacity(size_t rows, size_t used,
                                             size_t hidden) {
    if (!rows || !used || !hidden || rows > SIZE_MAX / used)
        return 0;
    size_t elements = rows * used;
    if (elements > SIZE_MAX / hidden)
        return 0;
    elements *= hidden;
    return elements > SIZE_MAX / sizeof(float) ? 0 : elements * sizeof(float);
}

static inline bool lie_q2_hc_inject_can_borrow(
        const lie_q2_hc_inject_scratch *allocation, const float *current,
        uint32_t rows, uint32_t hidden, uint32_t rank, uint32_t streams,
        bool expert_output_pending) {
    return allocation && allocation->base && current == allocation->base &&
        rows == 2048 && hidden == 2560 && rank == 320 && streams == 4 &&
        !expert_output_pending &&
        allocation->bytes >= (size_t)2048 * 2560 * sizeof(float);
}
#endif
