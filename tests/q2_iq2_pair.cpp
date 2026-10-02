// SPDX-License-Identifier: MIT
// Independent IQ2 format oracle over synthetic tensors, not a CPU model.
#include "q2_operator_fixture.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hpp"

void IQ2Case(int tokens, int rows, int tile_rows, bool tiny) {
  namespace q = gufo::models::qwen38_flash_next::rocm;
  const int experts = rows == 5 ? 512 : 3;
  constexpr int used = 2, k = 2560;
  const int slots = tokens * used;
  auto gate = Make(16, experts, rows, k, 7);
  auto up = Make(16, experts, rows, k, 11);
  std::vector<__half> x(std::size_t(tokens) * k);
  const float scale = tiny ? std::ldexp(1.f, -14) : std::ldexp(1.f, -8);
  for (std::size_t i = 0; i < x.size(); ++i)
    x[i] =
        __float2half((float(int((i * 17 + 31) % 251) - 125) + 0.137f) * scale);
  std::vector<std::int32_t> ids(slots), tiles;
  std::vector<std::uint32_t> counts(experts);
  for (int t = 0; t < tokens; ++t) {
    ids[t * used] = t % 3 == 0 ? 1 : 0;
    ids[t * used + 1] = experts - 1;
    ++counts[ids[t * used]];
    ++counts[experts - 1];
  }
  for (int e = 0; e < experts; ++e) {
    const int padded = int((counts[e] + 15) / 16 * 16);
    for (int t = 0; t < padded; t += tile_rows)
      tiles.push_back(e | ((t / tile_rows) << 16));
  }
  const auto compact_rows = q::RoutedCompactRows(slots, experts);
  Device gd(gate.bytes.size()), ud(up.bytes.size()), xd(x.size() * 2);
  Device id(ids.size() * 4), cd(counts.size() * 4), td(tiles.size() * 4);
  Device bounds((experts + 1) * 4), cursors(experts * 4);
  Device row_token(compact_rows * 4), row_slot(compact_rows * 4);
  constexpr std::size_t guard = 16;
  const auto size = std::size_t(slots) * rows;
  Device out((size + 2 * guard) * 4);
  Hip(hipMemcpy(gd.data, gate.bytes.data(), gate.bytes.size(),
                hipMemcpyHostToDevice));
  Hip(hipMemcpy(ud.data, up.bytes.data(), up.bytes.size(),
                hipMemcpyHostToDevice));
  Hip(hipMemcpy(xd.data, x.data(), x.size() * 2, hipMemcpyHostToDevice));
  Hip(hipMemcpy(id.data, ids.data(), ids.size() * 4, hipMemcpyHostToDevice));
  Hip(hipMemcpy(cd.data, counts.data(), counts.size() * 4,
                hipMemcpyHostToDevice));
  Hip(hipMemcpy(td.data, tiles.data(), tiles.size() * 4,
                hipMemcpyHostToDevice));
  Hip(hipMemset(out.data, 0xA5, (size + 2 * guard) * 4));
  q::RoutedCompact(static_cast<const std::int32_t *>(id.data),
                   static_cast<const std::uint32_t *>(cd.data),
                   static_cast<std::int32_t *>(bounds.data),
                   static_cast<std::int32_t *>(cursors.data),
                   static_cast<std::int32_t *>(row_token.data),
                   static_cast<std::int32_t *>(row_slot.data), tokens, used,
                   experts, nullptr);
  Check(q::RoutedGatedIQ2Gemm(
            gd.data, ud.data, static_cast<const __half *>(xd.data),
            static_cast<const std::int32_t *>(td.data), tiles.size(), tile_rows,
            static_cast<const std::int32_t *>(bounds.data),
            static_cast<const std::int32_t *>(row_token.data),
            static_cast<const std::int32_t *>(row_slot.data),
            static_cast<float *>(out.data) + guard, rows, k, nullptr),
        "IQ2 paired routed dispatch failed");
  Hip(hipDeviceSynchronize());
  std::vector<float> guarded(size + 2 * guard);
  Hip(hipMemcpy(guarded.data(), out.data, guarded.size() * 4,
                hipMemcpyDeviceToHost));
  for (std::size_t i = 0; i < guard; ++i)
    Check(std::bit_cast<std::uint32_t>(guarded[i]) == 0xA5A5A5A5U &&
              std::bit_cast<std::uint32_t>(guarded[guard + size + i]) ==
                  0xA5A5A5A5U,
          "IQ2 paired output guard changed");
  std::vector<float> got(guarded.begin() + guard,
                         guarded.begin() + guard + size);
  for (float value : got)
    Check(std::isfinite(value) &&
              std::bit_cast<std::uint32_t>(value) != 0xA5A5A5A5U,
          "Nonfinite or unwritten IQ2 output");
  std::vector<double> expected(size);
  for (int slot = 0; slot < slots; ++slot)
    for (int row = 0; row < rows; ++row) {
      double g = 0, u = 0;
      for (int col = 0; col < k; ++col) {
        const auto wi = (std::size_t(ids[slot]) * rows + row) * k + col;
        const double activation =
            __half2float(x[std::size_t(slot / used) * k + col]);
        g += activation * gate.values[wi];
        u += activation * up.values[wi];
      }
      expected[std::size_t(slot) * rows + row] = g * u / (1 + std::exp(-g));
    }
  Compare(got, expected,
          "IQ2-pair-n" + std::to_string(tokens) + "-m" + std::to_string(rows) +
              "-tile" + std::to_string(tile_rows) +
              (tiny ? "-tiny" : "-normal"));
}

int main() {
  try {
    Hip(hipSetDevice(0));
    std::cout.precision(12);
    for (int tile : {16, 48, 64, 128})
      for (bool tiny : {false, true}) {
        IQ2Case(17, 5, tile, tiny);
        IQ2Case(65, 129, tile, tiny);
      }
    for (bool tiny : {false, true})
      IQ2Case(17, 640, 64, tiny);
    std::cout << "PASS synthetic paired IQ2 operators; no model inference\n";
  } catch (const std::exception &ex) {
    std::cerr << ex.what() << '\n';
    return 1;
  }
}
