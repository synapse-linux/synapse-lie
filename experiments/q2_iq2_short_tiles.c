/* SPDX-License-Identifier: MIT */
#include "q2_iq2_short_tiles.h"

int lie_iq2_short_tiles(const uint32_t *counts, uint32_t experts,
                        uint32_t tokens, uint32_t used, int32_t *map,
                        size_t capacity, struct lie_iq2_short_tile_spans *spans) {
    if (!counts || !map || !spans || !experts || experts > 512 ||
        !tokens || tokens > 4096 || !used || used > experts)
        return 0;
    uint32_t total = 0, wide = 0, tail = 0, short48 = 0;
    for (uint32_t e = 0; e < experts; ++e) {
        const uint32_t n = counts[e];
        if (n > tokens)
            return 0;
        total += n;
        if (n && n <= 48) {
            ++short48;
        } else {
            const uint32_t groups = (n + 63u) / 64u;
            wide += groups / 2u;
            tail += groups & 1u;
        }
    }
    if (total != tokens * used || (size_t)wide + tail + short48 > capacity)
        return 0;
    uint32_t wi = 0, ti = wide, si = wide + tail;
    for (uint32_t e = 0; e < experts; ++e) {
        const uint32_t n = counts[e];
        if (n && n <= 48) {
            map[si++] = (int32_t)e;
        } else {
            const uint32_t groups = (n + 63u) / 64u;
            for (uint32_t j = 0; j < groups / 2u; ++j)
                map[wi++] = (int32_t)(e | (j << 16));
            if (groups & 1u)
                map[ti++] = (int32_t)(e | ((groups - 1u) << 16));
        }
    }
    *spans = (struct lie_iq2_short_tile_spans){wide, tail, short48};
    return 1;
}
