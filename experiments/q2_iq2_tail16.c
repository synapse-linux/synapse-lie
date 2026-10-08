/* SPDX-License-Identifier: MIT */
#include "q2_iq2_tail16.h"

int lie_iq2_tail16(const uint32_t *counts, uint32_t experts, uint32_t tokens,
                   uint32_t used, int32_t *map, size_t capacity,
                   struct lie_iq2_tail16_spans *spans) {
    if (!counts || !map || !spans || !experts || experts > 512 ||
        !tokens || tokens > 4096 || !used || used > experts)
        return 0;
    uint32_t total = 0, wide = 0, tail64 = 0, tail16 = 0;
    for (uint32_t e = 0; e < experts; ++e) {
        const uint32_t n = counts[e];
        if (n > tokens)
            return 0;
        total += n;
        const uint32_t groups = (n + 63u) / 64u;
        wide += groups / 2u;
        if (groups & 1u) {
            if (n - (groups - 1u) * 64u <= 16u)
                ++tail16;
            else
                ++tail64;
        }
    }
    if (total != tokens * used || (size_t)wide + tail64 + tail16 > capacity)
        return 0;
    uint32_t wi = 0, ti = wide, si = wide + tail64;
    for (uint32_t e = 0; e < experts; ++e) {
        const uint32_t n = counts[e];
        const uint32_t groups = (n + 63u) / 64u;
        for (uint32_t j = 0; j < groups / 2u; ++j)
            map[wi++] = (int32_t)(e | (j << 16));
        if (groups & 1u) {
            const uint32_t old_index = groups - 1u;
            if (n - old_index * 64u <= 16u)
                map[si++] = (int32_t)(e | ((old_index * 4u) << 16));
            else
                map[ti++] = (int32_t)(e | (old_index << 16));
        }
    }
    *spans = (struct lie_iq2_tail16_spans){wide, tail64, tail16};
    return 1;
}
