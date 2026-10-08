/* SPDX-License-Identifier: MIT */
#include "iq2_mixed_tiles.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(x) do { if (!(x)) { \
    fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #x); exit(1); \
} } while (0)

static void verify(const uint32_t *counts, uint32_t experts, uint32_t tokens,
                   uint32_t used) {
    /* Independently enumerate coverage at every live row, including ragged
     * boundaries. The exact-sized output has guards on both sides. */
    size_t capacity = 0;
    for (uint32_t e = 0; e < experts; ++e)
        capacity += (counts[e] + 127u) / 128u;
    int32_t *storage = malloc((capacity + 2) * sizeof(*storage));
    unsigned char *seen = calloc((size_t)experts * tokens, 1);
    CHECK(storage && seen);
    storage[0] = storage[capacity + 1] = -1729;
    struct lie_iq2_tile_spans spans = {0, 0};
    CHECK(lie_iq2_mixed_tiles(counts, experts, tokens, used, storage + 1,
                              capacity, &spans));
    CHECK((size_t)spans.wide + spans.tail == capacity);
    for (size_t i = 0; i < capacity; ++i) {
        const uint32_t word = (uint32_t)storage[i + 1];
        const uint32_t e = word & 65535u;
        const uint32_t width = i < spans.wide ? 128u : 64u;
        const uint32_t begin = (word >> 16) * width;
        CHECK(e < experts && begin < counts[e]);
        if (width == 64)
            CHECK(counts[e] - begin <= 64);
        for (uint32_t row = begin; row < counts[e] && row < begin + width; ++row)
            CHECK(++seen[(size_t)e * tokens + row] == 1);
    }
    for (uint32_t e = 0; e < experts; ++e)
        for (uint32_t row = 0; row < tokens; ++row)
            CHECK(seen[(size_t)e * tokens + row] == (row < counts[e]));
    CHECK(storage[0] == -1729 && storage[capacity + 1] == -1729);
    free(seen);
    free(storage);
}

int main(void) {
    /* Exhaust every supported single bucket length, then asymmetric experts
     * with both launch spans. None of these inputs is model inference. */
    for (uint32_t n = 1; n <= 4096; ++n)
        verify(&n, 1, n, 1);
    for (uint32_t split = 0; split <= 4096; ++split) {
        const uint32_t counts[] = {split, 4096 - split};
        verify(counts, 2, 4096, 1);
    }
    uint32_t counts[512] = {0};
    for (uint32_t e = 0; e < 512; ++e) counts[e] = 4096;
    verify(counts, 512, 4096, 512);
    const uint32_t skew[] = {0, 1, 15, 16, 17, 63, 64, 65, 127, 128, 129, 0};
    verify(skew, 12, 625, 1);
    int32_t map[8], before[8];
    memset(map, 0xa5, sizeof(map));
    memcpy(before, map, sizeof(map));
    struct lie_iq2_tile_spans spans = {71, 73};
    const uint32_t one = 129;
    CHECK(!lie_iq2_mixed_tiles(&one, 1, 129, 1, map, 1, &spans));
    CHECK(!lie_iq2_mixed_tiles(&one, 1, 128, 1, map, 8, &spans));
    CHECK(!lie_iq2_mixed_tiles(&one, 1, 130, 1, map, 8, &spans));
    CHECK(!lie_iq2_mixed_tiles(&one, 0, 129, 1, map, 8, &spans));
    CHECK(!lie_iq2_mixed_tiles(&one, 513, 129, 1, map, 8, &spans));
    CHECK(!lie_iq2_mixed_tiles(&one, 1, 0, 1, map, 8, &spans));
    CHECK(!lie_iq2_mixed_tiles(&one, 1, 4097, 1, map, 8, &spans));
    CHECK(!lie_iq2_mixed_tiles(&one, 1, 129, 0, map, 8, &spans));
    CHECK(!lie_iq2_mixed_tiles(&one, 1, 129, 2, map, 8, &spans));
    CHECK(!lie_iq2_mixed_tiles(NULL, 1, 129, 1, map, 8, &spans));
    CHECK(!lie_iq2_mixed_tiles(&one, 1, 129, 1, NULL, 8, &spans));
    CHECK(!lie_iq2_mixed_tiles(&one, 1, 129, 1, map, 8, NULL));
    CHECK(memcmp(map, before, sizeof(map)) == 0 && spans.wide == 71 && spans.tail == 73);
    puts("PASS synthetic IQ2 mixed-map coverage; no model inference");
    return 0;
}
