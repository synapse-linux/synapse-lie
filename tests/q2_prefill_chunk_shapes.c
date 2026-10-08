/* SPDX-License-Identifier: MIT */
/* New host bounds only. No model, floating-point oracle or GPU claim. */
#include "lie_q2_deferred_norm_state.h"
#define main retained_map_test_main
#include "iq2_mixed_tiles.c"
#undef main

int main(void) {
    lie_q2_deferred_norm_state state = {0};
    float residual[2] = {0}, gamma[2] = {0}, scales[2] = {0};
    const uint32_t supported[] = {2048, 4096, 8192};
    for (size_t i = 0; i < 3; ++i) {
        const uint32_t n = supported[i];
        CHECK(lie_q2_deferred_norm_publish(&state, residual, gamma, scales, n));
        CHECK(lie_q2_deferred_norm_matches(&state, residual, gamma, n));
        CHECK(!lie_q2_deferred_norm_matches(&state, residual + 1, gamma, n));
        CHECK(!lie_q2_deferred_norm_matches(&state, residual, gamma + 1, n));
        CHECK(!lie_q2_deferred_norm_matches(&state, residual, gamma, n + 1));
        CHECK(!lie_q2_deferred_norm_publish(&state, NULL, gamma, scales, n));
        CHECK(state.rows == 0 && state.scales == NULL);
        CHECK(!lie_q2_deferred_norm_publish(&state, residual, NULL, scales, n));
        CHECK(!lie_q2_deferred_norm_publish(&state, residual, gamma, NULL, n));
    }
    const uint32_t rejected[] = {0, 1, 2047, 2049, 4095, 4097, 8191, 8193, UINT32_MAX};
    for (size_t i = 0; i < sizeof(rejected) / sizeof(*rejected); ++i) {
        CHECK(lie_q2_deferred_norm_publish(&state, residual, gamma, scales, 8192));
        CHECK(!lie_q2_deferred_norm_publish(&state, residual, gamma, scales, rejected[i]));
        CHECK(state.rows == 0 && !state.residual && !state.gamma && !state.scales);
    }
    /* The retained independent row-coverage oracle checks exact bounds and
       ragged 64/128-token tiles for every newly admitted bucket length. */
    for (uint32_t n = 4097; n <= 8192; ++n)
        verify(&n, 1, n, 1);
    for (uint32_t split = 0; split <= 8192; ++split) {
        const uint32_t counts[] = {split, 8192 - split};
        verify(counts, 2, 8192, 1);
    }
    uint32_t counts[512];
    for (size_t i = 0; i < 512; ++i) counts[i] = 8192;
    verify(counts, 512, 8192, 512);
    int32_t map[2] = {-1729, -1729};
    struct lie_iq2_tile_spans spans = {71, 73};
    CHECK(!lie_iq2_mixed_tiles(counts, 512, 8192, 512, map, 2, &spans));
    CHECK(!lie_iq2_mixed_tiles(counts, 512, 8193, 512, map, 2, &spans));
    CHECK(map[0] == -1729 && map[1] == -1729 && spans.wide == 71 && spans.tail == 73);
    puts("PASS extended chunk ownership and IQ2 map coverage (NOT-INFERENCE)");
    return 0;
}
