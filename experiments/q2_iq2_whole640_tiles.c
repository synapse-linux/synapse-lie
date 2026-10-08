/* SPDX-License-Identifier: MIT */
#include "q2_iq2_whole640_tiles.h"

int lie_iq2_whole640_tiles(const uint32_t *counts, uint32_t experts,
                           uint32_t tokens, uint32_t used, int32_t *map,
                           size_t capacity, struct lie_iq2_tail16_spans *spans) {
    if (!lie_iq2_tail16(counts, experts, tokens, used, map, capacity, spans))
        return 0;
    const uint32_t first = spans->wide128 + spans->tail64;
    for (uint32_t i = first; i < first + spans->tail16; ++i) {
        const uint32_t descriptor = (uint32_t)map[i];
        /* The qualified short-tail start is always a multiple of 128 rows. */
        map[i] = (int32_t)((descriptor & 65535u) | ((descriptor >> 18u) << 16u));
    }
    return 1;
}
