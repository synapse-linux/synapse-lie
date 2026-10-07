/* SPDX-License-Identifier: MIT */
#ifndef LIE_IQ2_TOKEN256_TILES_H
#define LIE_IQ2_TOKEN256_TILES_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

struct lie_iq2_token256_spans {
    uint32_t wide256;
    uint32_t wide128;
    uint32_t tail64;
};

/* Private C17 route map for a measured IQ2 tile experiment. Width-relative
 * indices occupy descriptor bits 16..30; expert IDs occupy bits 0..15.
 * Each live 64-row unit is covered once. Failure leaves outputs unchanged.
 * Inputs and outputs must not alias. */
int lie_iq2_token256_tiles(const uint32_t *counts, uint32_t experts,
                            uint32_t tokens, uint32_t used, int32_t *map,
                            size_t capacity,
                            struct lie_iq2_token256_spans *spans);

#ifdef __cplusplus
}
#endif
#endif
