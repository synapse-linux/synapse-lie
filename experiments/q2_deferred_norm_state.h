/* SPDX-License-Identifier: MIT */
#ifndef LIE_Q2_DEFERRED_NORM_STATE_H
#define LIE_Q2_DEFERRED_NORM_STATE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Host identity only. Device buffers remain owned by the transitional executor
 * and all producer/consumer launches use its existing ordered stream. */
typedef struct {
    const float *residual;
    const float *gamma;
    float *scales;
    uint32_t rows;
} lie_q2_deferred_norm_state;

static inline void lie_q2_deferred_norm_clear(lie_q2_deferred_norm_state *state) {
    state->residual = NULL;
    state->gamma = NULL;
    state->scales = NULL;
    state->rows = 0;
}

static inline bool lie_q2_deferred_norm_publish(lie_q2_deferred_norm_state *state,
        const float *residual, const float *gamma, float *scales, uint32_t rows) {
    lie_q2_deferred_norm_clear(state);
    if (residual == NULL || gamma == NULL || scales == NULL || rows != 2048)
        return false;
    state->residual = residual;
    state->gamma = gamma;
    state->scales = scales;
    state->rows = rows;
    return true;
}

static inline bool lie_q2_deferred_norm_matches(const lie_q2_deferred_norm_state *state,
        const float *residual, const float *gamma, uint32_t rows) {
    return state->rows == 2048 && state->scales != NULL &&
        state->residual == residual && state->gamma == gamma && state->rows == rows;
}
#endif
