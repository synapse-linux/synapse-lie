/* SPDX-License-Identifier: MIT */
#include "lie/weight_decode.h"
#include <assert.h>
#include <fenv.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static void half_bytes(unsigned char *p, uint16_t h) {
    p[0] = (unsigned char)h; p[1] = (unsigned char)(h >> 8);
}
/* Independent arithmetic reference; no bit-level half expansion or BF16
 * integer-rounding implementation is shared with the converter. */
static double half_value(uint16_t h) {
    unsigned exponent = (h >> 10) & 31, mantissa = h & 1023;
    double v = exponent ? ldexp(1.0 + mantissa / 1024.0, (int)exponent - 15)
                        : ldexp((double)mantissa, -24);
    return h & 0x8000 ? -v : v;
}
static uint16_t expected_bf16(double value) {
    if (value == 0) return signbit(value) ? 0x8000 : 0;
    int exponent;
    double fraction = frexp(fabs(value), &exponent);
    float rounded = (float)ldexp(nearbyint(fraction * 256), exponent - 8);
    if (signbit(value)) rounded = -rounded;
    uint32_t bits; memcpy(&bits, &rounded, sizeof(bits));
    assert(!(bits & 0xffffu));
    return (uint16_t)(bits >> 16);
}
int main(void) {
    assert(fesetround(FE_TONEAREST) == 0);
    unsigned char data[272]; uint16_t out[258];
    size_t checked = 0;
    for (unsigned h = 0; h <= UINT16_MAX; ++h) {
        half_bytes(data, (uint16_t)h); out[0] = 0xdead;
        lie_weight_status status = lie_weight_decode_bf16(
            LIE_WEIGHT_F16, data, 2, 1, out, 1);
        if ((h & 0x7c00) == 0x7c00) {
            assert(status == LIE_WEIGHT_NONFINITE && out[0] == 0xdead);
        } else {
            assert(status == LIE_WEIGHT_OK);
            assert(out[0] == expected_bf16(half_value((uint16_t)h)));
            ++checked;
        }
    }
    size_t quantized = 0;
    for (unsigned h = 0; h <= UINT16_MAX; h += 31) {
        if ((h & 0x7c00) == 0x7c00) continue;
        for (unsigned b = 0; b < 8; ++b) {
            half_bytes(data + b * 34, (uint16_t)h);
            for (unsigned j = 0; j < 32; ++j)
                data[b * 34 + 2 + j] = (unsigned char)(b * 32 + j);
        }
        out[0] = out[257] = 0xbeef;
        assert(lie_weight_decode_bf16(LIE_WEIGHT_Q8_0, data, sizeof(data),
            256, out + 1, 256) == LIE_WEIGHT_OK);
        assert(out[0] == 0xbeef && out[257] == 0xbeef);
        for (unsigned q = 0; q < 256; ++q) {
            int signed_q = q >= 128 ? (int)q - 256 : (int)q;
            assert(out[q + 1] == expected_bf16(half_value((uint16_t)h) * signed_q));
            ++quantized;
        }
    }
    memset(out, 0x55, sizeof(out));
    half_bytes(data + 7 * 34, 0x7c01);
    assert(lie_weight_decode_bf16(LIE_WEIGHT_Q8_0, data, sizeof(data),
        256, out + 1, 256) == LIE_WEIGHT_NONFINITE);
    for (unsigned i = 0; i < 258; ++i) assert(out[i] == 0x5555);
    assert(lie_weight_decode_bf16(LIE_WEIGHT_Q8_0, data, 271, 256, out, 258) == LIE_WEIGHT_INVALID);
    assert(lie_weight_decode_bf16(LIE_WEIGHT_Q8_0, data, 272, 255, out, 258) == LIE_WEIGHT_INVALID);
    assert(lie_weight_decode_bf16(LIE_WEIGHT_Q8_0, data, 272, 256, out, 255) == LIE_WEIGHT_BUFFER_SMALL);
    assert(lie_weight_decode_bf16(LIE_WEIGHT_F16, data, 2, 1, (uint16_t *)data, 1) == LIE_WEIGHT_INVALID);
    assert(lie_weight_decode_bf16(LIE_WEIGHT_F16, data, 2, SIZE_MAX, out, 258) == LIE_WEIGHT_INVALID);
    assert(lie_weight_decode_bf16((lie_weight_encoding)99, data, 2, 1, out, 1) == LIE_WEIGHT_INVALID);
    assert(lie_weight_decode_bf16(LIE_WEIGHT_F16, NULL, 2, 1, out, 1) == LIE_WEIGHT_INVALID);
    assert(lie_weight_decode_bf16(LIE_WEIGHT_F16, data, 2, 1, NULL, 1) == LIE_WEIGHT_INVALID);
    assert(lie_weight_decode_bf16(LIE_WEIGHT_F16, data, 0, 0, out, 258) == LIE_WEIGHT_INVALID);
    printf("Weight decode: %zu finite F16 values, %zu Q8 values, atomic refusals PASS (NOT-INFERENCE)\n", checked, quantized);
    return 0;
}
