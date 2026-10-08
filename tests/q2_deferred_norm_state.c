/* SPDX-License-Identifier: MIT */
#include "q2_deferred_norm_state.h"
#include <stdio.h>

#define CHECK(expr) do { if (!(expr)) { \
    fprintf(stderr, "Deferred norm identity check failed at line %d\n", __LINE__); \
    return 1; } } while (0)

int main(void) {
    float residual[2] = {0}, gamma[2] = {0}, scales[2] = {0};
    lie_q2_deferred_norm_state state = {0};
    CHECK(!lie_q2_deferred_norm_matches(&state, residual, gamma, 2048));
    CHECK(lie_q2_deferred_norm_publish(&state, residual, gamma, scales, 2048));
    CHECK(lie_q2_deferred_norm_matches(&state, residual, gamma, 2048));
    CHECK(!lie_q2_deferred_norm_matches(&state, residual + 1, gamma, 2048));
    CHECK(!lie_q2_deferred_norm_matches(&state, residual, gamma + 1, 2048));
    CHECK(!lie_q2_deferred_norm_matches(&state, residual, gamma, 1));
    CHECK(!lie_q2_deferred_norm_matches(&state, residual, gamma, 2047));
    CHECK(lie_q2_deferred_norm_publish(&state, residual + 1, gamma + 1, scales + 1, 2048));
    CHECK(!lie_q2_deferred_norm_matches(&state, residual, gamma, 2048));
    CHECK(lie_q2_deferred_norm_matches(&state, residual + 1, gamma + 1, 2048));
    CHECK(state.scales == scales + 1);
    CHECK(!lie_q2_deferred_norm_publish(&state, NULL, gamma, scales, 2048));
    CHECK(state.rows == 0 && state.scales == NULL);
    CHECK(!lie_q2_deferred_norm_publish(&state, residual, NULL, scales, 2048));
    CHECK(!lie_q2_deferred_norm_publish(&state, residual, gamma, NULL, 2048));
    CHECK(!lie_q2_deferred_norm_publish(&state, residual, gamma, scales, 2049));
    CHECK(lie_q2_deferred_norm_publish(&state, residual, gamma, scales, 2048));
    lie_q2_deferred_norm_clear(&state);
    CHECK(!lie_q2_deferred_norm_matches(&state, residual, gamma, 2048));
    CHECK(state.residual == NULL && state.gamma == NULL && state.scales == NULL && state.rows == 0);
    puts("PASS deferred HC norm host identities; no GPU or model inference");
    return 0;
}
