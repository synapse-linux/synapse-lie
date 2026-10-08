/* SPDX-License-Identifier: MIT */
#ifndef LIE_IQ2_TOKEN160_TILES_H
#define LIE_IQ2_TOKEN160_TILES_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

struct lie_iq2_token160_spans {
    uint32_t wide160;
    uint32_t wide128;
    uint32_t tail64;
};

/* Private route experiment. The first span encodes offsets in 16-row units;
 * the remaining spans retain production width-relative offsets. Successful
 * maps cover each padded 16-row unit exactly once. Inputs and outputs must
 * not alias; failure leaves map and spans unchanged. */
int lie_iq2_token160_tiles(const uint32_t *counts, uint32_t experts,
                           uint32_t tokens, uint32_t used, int32_t *map,
                           size_t capacity,
                           struct lie_iq2_token160_spans *spans);

#ifdef __cplusplus
}
#endif
#endif
