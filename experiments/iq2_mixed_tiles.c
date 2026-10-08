/* SPDX-License-Identifier: MIT */
#include "iq2_mixed_tiles.h"

int lie_iq2_mixed_tiles(const uint32_t *counts, uint32_t experts,
                        uint32_t tokens, uint32_t used, int32_t *map,
                        size_t capacity, struct lie_iq2_tile_spans *spans) {
    if (!counts || !map || !spans || !experts || experts > 512 ||
        !tokens || tokens > 4096 || !used || used > experts)
        return 0;
    uint32_t total = 0, wide = 0, tail = 0;
    for (uint32_t e = 0; e < experts; ++e) {
        if (counts[e] > tokens)
            return 0;
        const uint32_t groups = (counts[e] + 63u) / 64u;
        wide += groups / 2u;
        tail += groups & 1u;
        total += counts[e];
    }
    if (total != tokens * used || (size_t)wide + tail > capacity)
        return 0;
    uint32_t wi = 0, ti = wide;
    for (uint32_t e = 0; e < experts; ++e) {
        const uint32_t groups = (counts[e] + 63u) / 64u;
        for (uint32_t j = 0; j < groups / 2u; ++j)
            map[wi++] = (int32_t)(e | (j << 16));
        if (groups & 1u)
            map[ti++] = (int32_t)(e | ((groups - 1u) << 16));
    }
    spans->wide = wide;
    spans->tail = tail;
    return 1;
}
