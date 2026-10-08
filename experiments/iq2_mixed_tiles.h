/* SPDX-License-Identifier: MIT */
#ifndef LIE_IQ2_MIXED_TILES_H
#define LIE_IQ2_MIXED_TILES_H
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

struct lie_iq2_tile_spans {
    uint32_t wide;
    uint32_t tail;
};

/* Experimental host map for the existing Qwen IQ2 128/64-row kernels.
 * Descriptors encode expert in bits 0..15 and the width-relative tile index
 * in bits 16..30. Wide descriptors precede tails; each live row occurs once.
 * Inputs/outputs must not alias. Failure leaves map and spans unchanged.
 * Supports the current qualification bound: 1..512 experts, <=4096 tokens.
 * No allocation, device access or model execution. */
int lie_iq2_mixed_tiles(const uint32_t *counts, uint32_t experts,
                        uint32_t tokens, uint32_t used, int32_t *map,
                        size_t capacity, struct lie_iq2_tile_spans *spans);

#ifdef __cplusplus
}
#endif
#endif
