/* SPDX-License-Identifier: MIT */
#include "iq2_token256_tiles.h"

int lie_iq2_token256_tiles(const uint32_t *counts, uint32_t experts,
                            uint32_t tokens, uint32_t used, int32_t *map,
                            size_t capacity,
                            struct lie_iq2_token256_spans *spans) {
    if (!counts || !map || !spans || !experts || experts > 512 ||
        !tokens || tokens > 4096 || !used || used > experts)
        return 0;
    uint32_t total = 0, wide256 = 0, wide128 = 0, tail64 = 0;
    for (uint32_t e = 0; e < experts; ++e) {
        if (counts[e] > tokens)
            return 0;
        const uint32_t groups = (counts[e] + 63u) / 64u;
        wide256 += groups / 4u;
        wide128 += (groups % 4u) / 2u;
        tail64 += groups & 1u;
        total += counts[e];
    }
    if (total != tokens * used ||
        (size_t)wide256 + wide128 + tail64 > capacity)
        return 0;

    uint32_t i256 = 0, i128 = wide256, i64 = wide256 + wide128;
    for (uint32_t e = 0; e < experts; ++e) {
        const uint32_t groups = (counts[e] + 63u) / 64u;
        const uint32_t n256 = groups / 4u;
        for (uint32_t j = 0; j < n256; ++j)
            map[i256++] = (int32_t)(e | (j << 16));
        if ((groups % 4u) >= 2u)
            map[i128++] = (int32_t)(e | ((n256 * 2u) << 16));
        if (groups & 1u)
            map[i64++] = (int32_t)(e | ((groups - 1u) << 16));
    }
    spans->wide256 = wide256;
    spans->wide128 = wide128;
    spans->tail64 = tail64;
    return 1;
}
