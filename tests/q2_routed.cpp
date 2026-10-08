// SPDX-License-Identifier: MIT
#include "q2_operator_fixture.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hpp"
#ifdef Q2_PACKED_CHECKS
#include "q2_packed_fixture.hpp"
#endif
#ifdef Q2_SCALED_CHECKS
#include "q2_scaled_fixture.hpp"
#endif

void RoutedQ2Case(int tokens, int rows, int tile_rows, bool tiny,
                  int exponent_shift = 0) {
  namespace q = gufo::models::qwen38_flash_next::rocm;
  constexpr int experts = 512, used = 2, logical = 640, stored = 768;
  const int slots = tokens * used;
  auto w = Make(10, experts, rows, stored, 7);
  std::vector<float> x(std::size_t(slots) * logical);
  const float scale = std::ldexp(1.f, (tiny ? -14 : -8) + exponent_shift);
  for (std::size_t i = 0; i < x.size(); ++i)
    x[i] = (float(int((i * 17 + 31) % 251) - 125) + 0.137f) * scale;
  std::vector<std::int32_t> ids(slots), tiles;
  std::vector<std::uint32_t> counts(experts);
  for (int t = 0; t < tokens; ++t) {
    ids[t * used] = (t % 3 == 0 ? 17 : 0);
    ids[t * used + 1] = 511;
    ++counts[ids[t * used]];
    ++counts[511];
  }
  for (int e = 0; e < experts; ++e) {
    const int padded = int((counts[e] + 15) / 16 * 16);
    for (int t = 0; t < padded; t += tile_rows)
      tiles.push_back(e | ((t / tile_rows) << 16));
  }
  const auto compact_rows = q::RoutedCompactRows(slots, experts);
  Device wd(w.bytes.size()), xd(x.size() * 4);
  Device id(ids.size() * 4), cd(counts.size() * 4), td(tiles.size() * 4);
  Device bounds((experts + 1) * 4), cursors(experts * 4);
  Device row_token(compact_rows * 4), row_slot(compact_rows * 4);
  Device out((std::size_t(slots) * rows + 16) * 4);
  Hip(hipMemcpy(wd.data, w.bytes.data(), w.bytes.size(),
                hipMemcpyHostToDevice));
  Hip(hipMemcpy(xd.data, x.data(), x.size() * 4, hipMemcpyHostToDevice));
  Hip(hipMemcpy(id.data, ids.data(), ids.size() * 4, hipMemcpyHostToDevice));
  Hip(hipMemcpy(cd.data, counts.data(), counts.size() * 4,
                hipMemcpyHostToDevice));
  Hip(hipMemcpy(td.data, tiles.data(), tiles.size() * 4,
                hipMemcpyHostToDevice));
  Hip(hipMemset(out.data, 0xA5, (std::size_t(slots) * rows + 16) * 4));
  q::RoutedCompact(static_cast<const std::int32_t *>(id.data),
                   static_cast<const std::uint32_t *>(cd.data),
                   static_cast<std::int32_t *>(bounds.data),
                   static_cast<std::int32_t *>(cursors.data),
                   static_cast<std::int32_t *>(row_token.data),
                   static_cast<std::int32_t *>(row_slot.data), tokens, used,
                   experts, nullptr);
  Check(q::RoutedQ2Gemm(wd.data, static_cast<const float *>(xd.data),
                        static_cast<const std::int32_t *>(td.data),
                        tiles.size(), tile_rows,
                        static_cast<const std::int32_t *>(bounds.data),
                        static_cast<const std::int32_t *>(row_slot.data),
                        static_cast<float *>(out.data), rows, logical, nullptr),
        "Q2 compensated routed dispatch failed");
  Hip(hipDeviceSynchronize());
  std::vector<float> got(std::size_t(slots) * rows + 16);
  Hip(hipMemcpy(got.data(), out.data, got.size() * 4, hipMemcpyDeviceToHost));
  for (std::size_t i = std::size_t(slots) * rows; i < got.size(); ++i)
    Check(std::bit_cast<std::uint32_t>(got[i]) == 0xA5A5A5A5U,
          "Q2 routed F16 output guard changed");
  got.resize(std::size_t(slots) * rows);
  for (float value : got)
    Check(std::bit_cast<std::uint32_t>(value) != 0xA5A5A5A5U,
          "Unwritten routed output");
  std::vector<double> expected(got.size());
  for (int slot = 0; slot < slots; ++slot)
    for (int row = 0; row < rows; ++row)
      for (int col = 0; col < logical; ++col)
        expected[std::size_t(slot) * rows + row] +=
            double(w.values[(std::size_t(ids[slot]) * rows + row) * stored +
                            col]) *
            x[std::size_t(slot) * logical + col];
  Compare(
      got, expected,
      "Q2 routed F16 tokens=" + std::to_string(tokens) + " rows=" +
          std::to_string(rows) + " tile=" + std::to_string(tile_rows) +
          (tiny ? " tiny" : " ordinary") +
          (exponent_shift ? " shift=" + std::to_string(exponent_shift) : ""));
#ifdef Q2_SCALED_CHECKS
  CheckScaledDown(wd.data, static_cast<const float *>(xd.data), x, expected,
                  static_cast<const std::int32_t *>(td.data), tiles.size(),
                  tile_rows, static_cast<const std::int32_t *>(bounds.data),
                  static_cast<const std::int32_t *>(row_slot.data), rows, got,
                  "n" + std::to_string(tokens) + "-m" + std::to_string(rows) +
                      "-tile" + std::to_string(tile_rows) + "-shift" +
                      std::to_string(exponent_shift) +
                      (tiny ? "-tiny" : "-normal"));
#endif
#ifdef Q2_PACKED_CHECKS
  std::vector<std::uint32_t> packed(x.size());
  for (std::size_t i = 0; i < x.size(); ++i)
    packed[i] = PackCompensated(x[i]);
  Device pd(packed.size() * 4);
  Hip(hipMemcpy(pd.data, packed.data(), packed.size() * 4,
                hipMemcpyHostToDevice));
  CheckPackedDown(
      wd.data, static_cast<const std::uint32_t *>(pd.data),
      static_cast<const std::int32_t *>(td.data), tiles.size(), tile_rows,
      static_cast<const std::int32_t *>(bounds.data),
      static_cast<const std::int32_t *>(row_slot.data), rows, got,
      "down-n" + std::to_string(tokens) + "-m" + std::to_string(rows) +
          "-tile" + std::to_string(tile_rows) + (tiny ? "-tiny" : "-normal") +
          (exponent_shift ? "-shift" + std::to_string(exponent_shift) : ""));
#endif
}

#ifndef Q2_PACKED_CHECKS
int main() {
  try {
    Hip(hipSetDevice(0));
    std::cout.precision(12);
    for (int tile : {16, 48, 64})
      for (bool tiny : {false, true}) {
        RoutedQ2Case(17, 5, tile, tiny);
        RoutedQ2Case(65, 129, tile, tiny);
      }
    std::cout << "PASS compensated Q2 routed operators; no model inference\n";
  } catch (const std::exception &ex) {
    std::cerr << ex.what() << '\n';
    return 1;
  }
}

#endif
