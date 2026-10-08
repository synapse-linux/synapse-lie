/* SPDX-License-Identifier: MIT */
#ifndef LIE_Q2_SCALED_TILES_MAP_H
#define LIE_Q2_SCALED_TILES_MAP_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

struct lie_q2_scaled_tile_spans {
  uint32_t narrow;
  uint32_t wide;
  uint32_t selected_experts;
  uint32_t selected_rows;
  uint32_t original_tiles;
  uint32_t original_reserved_rows;
  uint32_t reserved_rows;
  uint32_t max_rows;
  uint32_t histogram[6]; /* 0, 1..48, 49..128, 129..255, 256..511, >=512 */
};

/* Own host scheduling policy for the existing Q2 scaled WMMA kernels.
 * Narrow (48-row) descriptors precede wide (64-row) descriptors. Each word
 * encodes expert in bits 0..15 and width-relative tile index in bits 16..30.
 * Select 64 only for >=256 padded rows with no larger reserved-row count.
 * Each expert remains in exactly one span. No allocation/device/model access.
 * Counts/map/spans must not alias. Failure leaves map and spans unchanged.
 * Bounds are 1..512 experts, 1..4096 tokens, and exactly tokens*used routes. */
int lie_q2_scaled_tiles_map(const uint32_t* counts, uint32_t experts,
                            uint32_t tokens, uint32_t used, int32_t* map,
                            size_t capacity,
                            struct lie_q2_scaled_tile_spans* spans);

#ifdef __cplusplus
}
#endif
#endif
