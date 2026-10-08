// SPDX-License-Identifier: MIT
#pragma once
#include "q2_packed_fixture.hpp"

void CheckScaledDown(const void *weights, const float *input,
                     const std::vector<float> &host_input,
                     const std::vector<double> &expected,
                     const std::int32_t *tiles, std::uint32_t n_tiles,
                     int tile_rows, const std::int32_t *bounds,
                     const std::int32_t *slots, int rows,
                     const std::vector<float> &reference,
                     const std::string &label) {
  namespace q = gufo::models::qwen38_flash_next::rocm;
  constexpr std::size_t cols = 640, guard = 16;
  const auto count = host_input.size() / cols;
  Device half(host_input.size() * 2), scales(count * 4);
  Device output((reference.size() + 2 * guard) * 4);
  Hip(hipMemset(output.data, 0xA5, (reference.size() + 2 * guard) * 4));
  Check(q::PackQ2ScaledRows(input, static_cast<__half *>(half.data),
                            static_cast<float *>(scales.data), count, cols,
                            nullptr),
        "Scaled input packing failed");
  Check(q::RoutedQ2ScaledGemm(weights, static_cast<const __half *>(half.data),
                              static_cast<const float *>(scales.data), tiles,
                              n_tiles, tile_rows, bounds, slots,
                              static_cast<float *>(output.data) + guard, rows,
                              cols, nullptr),
        "Scaled down failed");
  Hip(hipDeviceSynchronize());
  std::vector<__half> packed(host_input.size());
  std::vector<float> inverse(count), got(reference.size() + 2 * guard);
  Hip(hipMemcpy(packed.data(), half.data, packed.size() * 2,
                hipMemcpyDeviceToHost));
  Hip(hipMemcpy(inverse.data(), scales.data, inverse.size() * 4,
                hipMemcpyDeviceToHost));
  Hip(hipMemcpy(got.data(), output.data, got.size() * 4,
                hipMemcpyDeviceToHost));
  for (std::size_t row = 0; row < count; ++row) {
    float peak = 0;
    for (std::size_t c = 0; c < cols; ++c)
      peak = std::max(peak, std::abs(host_input[row * cols + c]));
    int exponent = 0;
    (void)std::frexp(peak, &exponent);
    const int shift = peak == 0 ? 0 : std::clamp(14 - exponent, -120, 120);
    Check(inverse[row] == std::ldexp(1.f, -shift), "Wrong row scale");
    for (std::size_t c = 0; c < cols; ++c) {
      const auto offset = row * cols + c;
      const auto scalar =
          __float2half_rn(std::ldexp(host_input[offset], shift));
      Check(std::bit_cast<std::uint16_t>(scalar) ==
                std::bit_cast<std::uint16_t>(packed[offset]),
            "Scaled input differs from scalar IEEE conversion");
    }
  }
  for (std::size_t i = 0; i < guard; ++i)
    Check(std::bit_cast<std::uint32_t>(got[i]) == 0xA5A5A5A5U &&
              std::bit_cast<std::uint32_t>(got[guard + reference.size() + i]) ==
                  0xA5A5A5A5U,
          "Scaled output guard changed");
  got = std::vector<float>(got.begin() + guard, got.end() - guard);
  std::size_t changed = 0;
  for (std::size_t i = 0; i < got.size(); ++i)
    changed += std::bit_cast<std::uint32_t>(got[i]) !=
               std::bit_cast<std::uint32_t>(reference[i]);
  std::ofstream saved("results/scaled-" + label + ".f32", std::ios::binary);
  saved.write(reinterpret_cast<const char *>(got.data()), got.size() * 4);
  Check(bool(saved), "Could not save scaled output");
  std::cout << "{\"event\":\"scaled_replay\",\"label\":\"" << label
            << "\",\"values\":" << got.size() << ",\"changed\":" << changed
            << ",\"packed_values_checked\":" << packed.size() << "}\n";
  // Original F32 operands and unchanged independent limits, not rounded
  // goldens.
  Compare(got, expected, "scaled " + label);
}
