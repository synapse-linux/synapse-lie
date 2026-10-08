/* SPDX-License-Identifier: MIT */
#include "iq2_token160_tiles.h"

static int choose_160(uint32_t rows) {
    const uint32_t padded = ((rows + 15u) / 16u) * 16u;
    const uint32_t remainder = padded % 160u;
    return padded >= 160u && (remainder == 0u || remainder >= 64u);
}

int lie_iq2_token160_tiles(const uint32_t *counts, uint32_t experts,
                           uint32_t tokens, uint32_t used, int32_t *map,
                           size_t capacity,
                           struct lie_iq2_token160_spans *spans) {
    if (!counts || !map || !spans || !experts || experts > 512u ||
        !tokens || tokens > 4096u || !used || used > experts)
        return 0;

    uint32_t total = 0, wide160 = 0, wide128 = 0, tail64 = 0;
    for (uint32_t e = 0; e < experts; ++e) {
        if (counts[e] > tokens)
            return 0;
        total += counts[e];
        if (choose_160(counts[e])) {
            const uint32_t padded = ((counts[e] + 15u) / 16u) * 16u;
            wide160 += (padded + 159u) / 160u;
        } else {
            const uint32_t groups = (counts[e] + 63u) / 64u;
            wide128 += groups / 2u;
            tail64 += groups & 1u;
        }
    }
    if (total != tokens * used ||
        (size_t)wide160 + wide128 + tail64 > capacity)
        return 0;

    uint32_t i160 = 0, i128 = wide160, i64 = wide160 + wide128;
    for (uint32_t e = 0; e < experts; ++e) {
        if (choose_160(counts[e])) {
            const uint32_t padded = ((counts[e] + 15u) / 16u) * 16u;
            const uint32_t tiles = (padded + 159u) / 160u;
            for (uint32_t j = 0; j < tiles; ++j)
                map[i160++] = (int32_t)(e | ((j * 10u) << 16));
        } else {
            const uint32_t groups = (counts[e] + 63u) / 64u;
            for (uint32_t j = 0; j < groups / 2u; ++j)
                map[i128++] = (int32_t)(e | (j << 16));
            if (groups & 1u)
                map[i64++] = (int32_t)(e | ((groups - 1u) << 16));
        }
    }
    spans->wide160 = wide160;
    spans->wide128 = wide128;
    spans->tail64 = tail64;
    return 1;
}
