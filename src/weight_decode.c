/* SPDX-License-Identifier: MIT */
#include "lie/weight_decode.h"
#include <float.h>
#include <string.h>

_Static_assert(sizeof(float) == 4 && FLT_RADIX == 2 && FLT_MANT_DIG == 24 &&
               FLT_MAX_EXP == 128, "IEEE binary32 is required");

static uint16_t read_half(const unsigned char *p) {
    return (uint16_t)((uint16_t)p[0] | (uint16_t)p[1] << 8);
}

static float half_float(uint16_t h) {
    uint32_t sign = (uint32_t)(h & 0x8000u) << 16;
    uint32_t exponent = (h >> 10) & 31u, fraction = h & 1023u, bits;
    if (exponent) {
        bits = sign | (exponent + 112u) << 23 | fraction << 13;
    } else if (!fraction) {
        bits = sign;
    } else {
        int shift = 0;
        while (!(fraction & 1024u)) { fraction <<= 1; ++shift; }
        bits = sign | (uint32_t)(113 - shift) << 23 |
               (fraction & 1023u) << 13;
    }
    float value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

static uint16_t bf16(float value) {
    uint32_t bits;
    memcpy(&bits, &value, sizeof(bits));
    return (uint16_t)((bits + 0x7fffu + ((bits >> 16) & 1u)) >> 16);
}

lie_weight_status lie_weight_decode_bf16(lie_weight_encoding encoding,
    const void *source, size_t source_bytes, size_t count,
    uint16_t *output, size_t output_capacity) {
    if (!source || !output || !count || count > SIZE_MAX / sizeof(*output))
        return LIE_WEIGHT_INVALID;
    size_t bytes;
    if (encoding == LIE_WEIGHT_F16) {
        bytes = count * 2;
    } else if (encoding == LIE_WEIGHT_Q8_0) {
        if (count % 32 || count / 32 > SIZE_MAX / 34)
            return LIE_WEIGHT_INVALID;
        bytes = count / 32 * 34;
    } else {
        return LIE_WEIGHT_INVALID;
    }
    if (source_bytes != bytes) return LIE_WEIGHT_INVALID;
    if (output_capacity < count) return LIE_WEIGHT_BUFFER_SMALL;
    uintptr_t begin = (uintptr_t)source, end = (uintptr_t)output;
    size_t output_bytes = count * sizeof(*output);
    if (bytes > UINTPTR_MAX - begin || output_bytes > UINTPTR_MAX - end ||
        (begin < end + output_bytes && end < begin + bytes))
        return LIE_WEIGHT_INVALID;
    const unsigned char *input = source;
    size_t stride = encoding == LIE_WEIGHT_F16 ? 2 : 34;
    for (size_t offset = 0; offset < bytes; offset += stride)
        if ((read_half(input + offset) & 0x7c00u) == 0x7c00u)
            return LIE_WEIGHT_NONFINITE;
    if (encoding == LIE_WEIGHT_F16) {
        for (size_t i = 0; i < count; ++i)
            output[i] = bf16(half_float(read_half(input + i * 2)));
    } else {
        for (size_t block = 0; block < count / 32; ++block) {
            const unsigned char *p = input + block * 34;
            float scale = half_float(read_half(p));
            for (size_t j = 0; j < 32; ++j) {
                int value = p[2 + j];
                if (value >= 128) value -= 256;
                output[block * 32 + j] = bf16(scale * (float)value);
            }
        }
    }
    return LIE_WEIGHT_OK;
}
