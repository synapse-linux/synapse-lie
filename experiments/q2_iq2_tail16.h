/* SPDX-License-Identifier: MIT */
#ifndef LIE_Q2_IQ2_TAIL16_H
#define LIE_Q2_IQ2_TAIL16_H
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

struct lie_iq2_tail16_spans {
    uint32_t wide128;
    uint32_t tail64;
    uint32_t tail16;
};

/* Bounded, allocation-free IQ2 gate/up map, with ordered128/64/16 spans.
 * Keep every original128 descriptor and every tail with17..64 live rows.
 * Select16 only for1..16-row tails, including tails following wide tiles.
 * Bits0..15 hold the expert; bits16..30 hold the index in that span's width.
 * Descriptor count/capacity stay unchanged. Inputs/outputs must not alias.
 * Failure leaves outputs unchanged. Bounds:1..512 experts,1..4096 tokens,
 * 1..experts used per token. No device or model arithmetic. */
int lie_iq2_tail16(const uint32_t *counts, uint32_t experts, uint32_t tokens,
                   uint32_t used, int32_t *map, size_t capacity,
                   struct lie_iq2_tail16_spans *spans);

#ifdef __cplusplus
}
#endif
#endif
