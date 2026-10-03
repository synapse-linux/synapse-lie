// SPDX-License-Identifier: MIT
// Full finite F16/Q8 scale space against the independently pinned upstream.
#include "lie/weight_decode.h"
#include "src/core/quant/ggml_dequant.hpp"
#include <array>
#include <bit>
#include <cassert>
#include <cstdio>

static std::uint16_t bf16(float value) {
    const auto bits = std::bit_cast<std::uint32_t>(value);
    // Same rounding boundary as the original pinned vision encoder.
    return static_cast<std::uint16_t>((bits + 0x7fff + ((bits >> 16) & 1)) >> 16);
}
int main() {
    static_assert(std::endian::native == std::endian::little);
    std::array<gufo::quant::block_q8_0, 8> blocks;
    std::array<float, 256> reference;
    std::array<std::uint16_t, 256> decoded;
    std::size_t scales = 0;
    for (unsigned h = 0; h <= UINT16_MAX; ++h) {
        if ((h & 0x7c00) == 0x7c00) continue;
        auto half = static_cast<std::uint16_t>(h);
        assert(lie_weight_decode_bf16(LIE_WEIGHT_F16, &half, 2, 1,
                                     decoded.data(), decoded.size()) == LIE_WEIGHT_OK);
        assert(decoded[0] == bf16(gufo::quant::Fp16ToFloat(half)));
        for (unsigned b = 0; b < blocks.size(); ++b) {
            blocks[b].d = half;
            for (unsigned j = 0; j < 32; ++j)
                blocks[b].qs[j] = static_cast<std::int8_t>(b * 32 + j);
        }
        gufo::quant::DequantizeQ8_0(blocks.data(), reference.data(), reference.size());
        assert(lie_weight_decode_bf16(LIE_WEIGHT_Q8_0, blocks.data(), sizeof(blocks),
                                     decoded.size(), decoded.data(), decoded.size()) == LIE_WEIGHT_OK);
        for (unsigned j = 0; j < decoded.size(); ++j)
            assert(decoded[j] == bf16(reference[j]));
        ++scales;
    }
    std::printf("Pinned Gufo weight parity: %zu F16 and %zu Q8 values PASS (NOT-INFERENCE)\n",
                scales, scales * 256);
}
