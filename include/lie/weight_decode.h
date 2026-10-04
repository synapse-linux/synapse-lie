/* SPDX-License-Identifier: MIT */
#ifndef LIE_WEIGHT_DECODE_H
#define LIE_WEIGHT_DECODE_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_WEIGHT_DECODE_ABI 1u
typedef enum { LIE_WEIGHT_F16, LIE_WEIGHT_Q8_0 } lie_weight_encoding;
typedef enum {
    LIE_WEIGHT_OK, LIE_WEIGHT_INVALID, LIE_WEIGHT_BUFFER_SMALL,
    LIE_WEIGHT_NONFINITE
} lie_weight_status;
/* Decode little-endian GGML F16 or Q8_0 weight bytes to native uint16 BF16
 * codes, rounding to nearest with even ties. Q8_0 uses 32 signed values and
 * one F16 scale per 34-byte block. No allocation, GPU, model forward or file
 * mutation. The caller owns both spans; overlapping spans are refused.
 * Source length must be exact, count nonzero, output capacity >= count.
 * All validation completes before any output write, including finite scales.
 * This does not recover the unquantized model's original weights. */
lie_weight_status lie_weight_decode_bf16(lie_weight_encoding encoding,
    const void *source, size_t source_bytes, size_t count,
    uint16_t *output, size_t output_capacity);
#ifdef __cplusplus
}
#endif
#endif
