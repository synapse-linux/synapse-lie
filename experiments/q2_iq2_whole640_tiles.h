/* SPDX-License-Identifier: MIT */
#ifndef LIE_IQ2_WHOLE640_TILES_H
#define LIE_IQ2_WHOLE640_TILES_H
#include "q2_iq2_tail16.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Reuse the qualified 128/64/16-row partition, but encode both tail spans
 * in the original 64-row descriptor units. The last span still covers only
 * 1..16 live rows. Capacity, row order and failure atomicity are unchanged.
 * No allocation, device access or model execution. Inputs must not alias. */
int lie_iq2_whole640_tiles(const uint32_t *counts, uint32_t experts,
                           uint32_t tokens, uint32_t used, int32_t *map,
                           size_t capacity, struct lie_iq2_tail16_spans *spans);

#ifdef __cplusplus
}
#endif
#endif
