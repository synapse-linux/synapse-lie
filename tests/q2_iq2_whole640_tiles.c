/* SPDX-License-Identifier: MIT */
#include "q2_iq2_whole640_tiles.h"
#include "iq2_mixed_tiles.h"
#include "../experiments/q2_iq2_tail16_routes.inc"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(x) do { if (!(x)) { \
    fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #x); exit(1); \
} } while (0)

static void verify(const uint32_t *counts, uint32_t experts, uint32_t tokens,
                   uint32_t used) {
    size_t capacity = 0;
    uint32_t expected_short = 0;
    for (uint32_t e = 0; e < experts; ++e) {
        capacity += (counts[e] + 127u) / 128u;
        expected_short += counts[e] % 128u && counts[e] % 128u <= 16u;
    }
    int32_t *storage = malloc((capacity + 2) * sizeof(*storage));
    int32_t *original = malloc(capacity * sizeof(*original));
    unsigned char *seen = calloc((size_t)experts * tokens, 1);
    CHECK(storage && original && seen);
    storage[0] = storage[capacity + 1] = -1729;
    struct lie_iq2_tail16_spans spans = {0, 0, 0};
    struct lie_iq2_tile_spans parent = {0, 0};
    CHECK(lie_iq2_mixed_tiles(counts, experts, tokens, used, original, capacity, &parent));
    CHECK(lie_iq2_whole640_tiles(counts, experts, tokens, used, storage + 1, capacity, &spans));
    CHECK((size_t)spans.wide128 + spans.tail64 + spans.tail16 == capacity);
    CHECK(spans.wide128 == parent.wide && spans.tail64 + spans.tail16 == parent.tail);
    CHECK(spans.tail16 == expected_short);
    CHECK(memcmp(storage + 1, original, parent.wide * sizeof(*original)) == 0);
    size_t new_tail = spans.wide128;
    for (size_t i = parent.wide; i < capacity; ++i)
        if (counts[(uint32_t)original[i] & 65535u] - ((uint32_t)original[i] >> 16) * 64u > 16u)
            CHECK(storage[1 + new_tail++] == original[i]);
    CHECK(new_tail == (size_t)spans.wide128 + spans.tail64);
    for (size_t i = 0; i < capacity; ++i) {
        const uint32_t word = (uint32_t)storage[i + 1];
        const uint32_t e = word & 65535u;
        const uint32_t width = i < spans.wide128 ? 128u
            : i < (size_t)spans.wide128 + spans.tail64 ? 64u : 16u;
        const uint32_t unit = i < spans.wide128 ? 128u : 64u;
        const uint32_t begin = (word >> 16) * unit;
        CHECK(e < experts && begin < counts[e]);
        if (width == 16)
            CHECK(begin % 128 == 0 && counts[e] - begin <= 16);
        if (width == 128)
            CHECK(counts[e] - begin > 64);
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
    free(original);
    free(storage);
}

int main(void) {
    for (uint32_t n = 1; n <= 4096; ++n)
        verify(&n, 1, n, 1);
    for (uint32_t split = 0; split <= 4096; ++split) {
        const uint32_t counts[] = {split, 4096 - split};
        verify(counts, 2, 4096, 1);
    }
    uint32_t counts[512];
    for (uint32_t e = 0; e < 512; ++e) counts[e] = 4096;
    verify(counts, 512, 4096, 512);
    const uint32_t skew[] = {0, 1, 15, 16, 17, 33, 47, 48, 49, 63, 64, 65, 127, 128, 129, 0};
    uint32_t total = 0;
    for (size_t i = 0; i < sizeof(skew) / sizeof(*skew); ++i) total += skew[i];
    verify(skew, sizeof(skew) / sizeof(*skew), total, 1);
    for (uint32_t e = 0; e < 512; ++e) counts[e] = e < 8 ? 2048 : 8 + (e < 72);
    verify(counts, 512, 2048, 10);
    verify(kLayer0Counts, 512, 2048, 10);
    verify(kLayer3Counts, 512, 2048, 10);
    verify(kLayer22Counts, 512, 2048, 10);
    int32_t map[8], before[8];
    memset(map, 0xa5, sizeof(map));
    memcpy(before, map, sizeof(map));
    struct lie_iq2_tail16_spans spans = {71, 73, 79};
    const uint32_t one = 129;
    CHECK(!lie_iq2_whole640_tiles(&one, 1, 129, 1, map, 1, &spans));
    CHECK(!lie_iq2_whole640_tiles(&one, 1, 128, 1, map, 8, &spans));
    CHECK(!lie_iq2_whole640_tiles(&one, 1, 130, 1, map, 8, &spans));
    CHECK(!lie_iq2_whole640_tiles(&one, 0, 129, 1, map, 8, &spans));
    CHECK(!lie_iq2_whole640_tiles(&one, 513, 129, 1, map, 8, &spans));
    CHECK(!lie_iq2_whole640_tiles(&one, 1, 0, 1, map, 8, &spans));
    CHECK(!lie_iq2_whole640_tiles(&one, 1, 4097, 1, map, 8, &spans));
    CHECK(!lie_iq2_whole640_tiles(&one, 1, 129, 0, map, 8, &spans));
    CHECK(!lie_iq2_whole640_tiles(&one, 1, 129, 2, map, 8, &spans));
    CHECK(!lie_iq2_whole640_tiles(NULL, 1, 129, 1, map, 8, &spans));
    CHECK(!lie_iq2_whole640_tiles(&one, 1, 129, 1, NULL, 8, &spans));
    CHECK(!lie_iq2_whole640_tiles(&one, 1, 129, 1, map, 8, NULL));
    CHECK(memcmp(map, before, sizeof(map)) == 0 && spans.wide128 == 71 &&
          spans.tail64 == 73 && spans.tail16 == 79);
    const uint32_t short_count = 16;
    CHECK(!lie_iq2_whole640_tiles(&short_count, 1, 16, 1, map, 0, &spans));
    CHECK(memcmp(map, before, sizeof(map)) == 0 && spans.tail16 == 79);
    puts("PASS whole640 partition, descriptor units and row ownership; no model inference");
    return 0;
}
