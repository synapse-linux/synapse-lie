/* SPDX-License-Identifier: MIT */
#ifndef LIE_Q2_IQ2_SHORT_TILES_H
#define LIE_Q2_IQ2_SHORT_TILES_H
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

struct lie_iq2_short_tile_spans {
    uint32_t wide128;
    uint32_t tail64;
    uint32_t short48;
};

/* Bounded experimental IQ2 gate/up map; no allocation or device access.
 * Whole nonempty buckets of1..48 rows use one48-row descriptor at offset0.
 * Other buckets retain the original128-row groups and optional64-row tail.
 * Map spans are ordered128,64,48. Expert occupies bits0..15; the index in
 * bits16..30 is relative to that span's width. Each live row occurs once.
 * Inputs/outputs must not alias. Failure leaves map and spans unchanged.
 * Bounds:1..512 experts,1..4096 tokens,1..experts used per token. */
int lie_iq2_short_tiles(const uint32_t *counts, uint32_t experts,
                        uint32_t tokens, uint32_t used, int32_t *map,
                        size_t capacity, struct lie_iq2_short_tile_spans *spans);

#ifdef __cplusplus
}
#endif
#endif
