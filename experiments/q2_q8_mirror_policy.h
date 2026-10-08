/* SPDX-License-Identifier: MIT */
#ifndef LIE_Q2_Q8_MIRROR_POLICY_H
#define LIE_Q2_Q8_MIRROR_POLICY_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Own C17 resource admission for an isolated numerical-port experiment.
 * No allocation, tensor read, conversion, model forward or GPU access here. */
#define LIE_Q8_MIRROR_BUDGET_BYTES ((size_t)6 * 1024 * 1024 * 1024)
#define LIE_Q8_MIRROR_TAIL_BYTES ((size_t)4096)

typedef struct lie_q8_mirror_plan {
    size_t elements;
    size_t payload_bytes;
    size_t allocation_bytes;
    size_t next_mirror_bytes;
} lie_q8_mirror_plan;

/* 1 admits one checked allocation, 0 leaves the original route alone,
 * -1 fails before allocating. The caller owns allocation/rollback/publication. */
static inline int lie_q8_mirror_admit(uint32_t rows, uint32_t cols,
                                     uint32_t experts, bool q8,
                                     size_t mirror_bytes,
                                     lie_q8_mirror_plan *out) {
    if (out == NULL) return -1;
    out->elements = 0;
    out->payload_bytes = 0;
    out->allocation_bytes = 0;
    out->next_mirror_bytes = 0;
    if (!q8 || experts != 1 ||
        !(((rows == 16384 || rows == 13312) && cols == 2560) ||
          (rows == 2560 && cols == 6144))) return 0;
    if ((size_t)rows > SIZE_MAX / cols) return -1;
    const size_t elements = (size_t)rows * cols;
    if (elements > (SIZE_MAX - LIE_Q8_MIRROR_TAIL_BYTES) / 2) return -1;
    const size_t allocation = elements * 2 + LIE_Q8_MIRROR_TAIL_BYTES;
    if (mirror_bytes > LIE_Q8_MIRROR_BUDGET_BYTES ||
        allocation > LIE_Q8_MIRROR_BUDGET_BYTES - mirror_bytes) return -1;
    out->elements = elements;
    out->payload_bytes = elements * 2;
    out->allocation_bytes = allocation;
    out->next_mirror_bytes = mirror_bytes + allocation;
    return 1;
}

#endif
