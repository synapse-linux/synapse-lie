// SPDX-License-Identifier: MIT
#pragma once
// Synthetic format/replay checks only; no CPU model inference.
#include "q2_operator_fixture.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hpp"

std::uint32_t PackCompensated(float value) {
  const __half hi = __float2half_rn(value);
  const float residual = (value - __half2float(hi)) * 4096.0f;
  const __half lo = __float2half_rn(residual);
  return std::uint32_t(std::bit_cast<std::uint16_t>(hi)) |
         (std::uint32_t(std::bit_cast<std::uint16_t>(lo)) << 16);
}

void CheckPackedDown(const void *weights, const std::uint32_t *packed,
                     const std::int32_t *tiles, std::uint32_t n_tiles,
                     int tile_rows, const std::int32_t *bounds,
                     const std::int32_t *rows_slot, int rows,
                     const std::vector<float> &reference,
                     const std::string &label) {
  namespace q = gufo::models::qwen38_flash_next::rocm;
  constexpr std::size_t guard = 16;
  const auto size = reference.size();
  Device out((size + guard * 2) * 4);
  Hip(hipMemset(out.data, 0xA5, (size + guard * 2) * 4));
  Check(q::RoutedQ2GemmPacked(
            weights, packed, tiles, n_tiles, tile_rows, bounds, rows_slot,
            static_cast<float *>(out.data) + guard, rows, 640, nullptr),
        "Packed Q2 dispatch failed");
  Hip(hipDeviceSynchronize());
  std::vector<float> result(size + guard * 2);
  Hip(hipMemcpy(result.data(), out.data, result.size() * 4,
                hipMemcpyDeviceToHost));
  for (std::size_t i = 0; i < guard; ++i)
    Check(std::bit_cast<std::uint32_t>(result[i]) == 0xA5A5A5A5U &&
              std::bit_cast<std::uint32_t>(result[guard + size + i]) ==
                  0xA5A5A5A5U,
          "Packed Q2 output guard changed");
  for (std::size_t i = 0; i < size; ++i)
    Check(std::isfinite(result[guard + i]) &&
              std::bit_cast<std::uint32_t>(result[guard + i]) ==
                  std::bit_cast<std::uint32_t>(reference[i]),
          "Packed Q2 output differs from F32 input path");
  std::ofstream saved("results/packed-" + label + ".f32", std::ios::binary);
  saved.write(reinterpret_cast<const char *>(result.data() + guard), size * 4);
  Check(bool(saved), "Could not save packed down output");
  std::cout << "PASS exact packed Q2 " << label << " values=" << size << '\n';
}
