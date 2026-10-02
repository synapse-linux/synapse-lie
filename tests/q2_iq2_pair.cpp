// SPDX-License-Identifier: MIT
// Independent IQ2 format oracle over synthetic tensors, not a CPU model.
#include "q2_operator_fixture.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hpp"
#ifdef Q2_PACKED_CHECKS
#include "q2_packed_fixture.hpp"
#endif

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
#ifdef Q2_PACKED_CHECKS
  Device packed_out((size + 2 * guard) * 4);
  Hip(hipMemset(packed_out.data, 0xA5, (size + 2 * guard) * 4));
  Check(q::RoutedGatedIQ2GemmPacked(
            gd.data, ud.data, static_cast<const __half *>(xd.data),
            static_cast<const std::int32_t *>(td.data), tiles.size(), tile_rows,
            static_cast<const std::int32_t *>(bounds.data),
            static_cast<const std::int32_t *>(row_token.data),
            static_cast<const std::int32_t *>(row_slot.data),
            static_cast<std::uint32_t *>(packed_out.data) + guard, rows, k,
            nullptr),
        "Packed IQ2 dispatch failed");
  Hip(hipDeviceSynchronize());
  std::vector<std::uint32_t> packed(size + 2 * guard);
  Hip(hipMemcpy(packed.data(), packed_out.data, packed.size() * 4,
                hipMemcpyDeviceToHost));
  for (std::size_t i = 0; i < guard; ++i)
    Check(packed[i] == 0xA5A5A5A5U && packed[guard + size + i] == 0xA5A5A5A5U,
          "Packed IQ2 output guard changed");
  for (std::size_t i = 0; i < size; ++i)
    Check(packed[guard + i] == PackCompensated(got[i]),
          "Packed IQ2 differs from independent packing of F32 reference");
  const auto label = "iq2-n" + std::to_string(tokens) + "-m" +
                     std::to_string(rows) + "-tile" +
                     std::to_string(tile_rows) + (tiny ? "-tiny" : "-normal");
  std::ofstream saved("results/packed-" + label + ".u32", std::ios::binary);
  saved.write(reinterpret_cast<const char *>(packed.data() + guard), size * 4);
  Check(bool(saved), "Could not save packed IQ2 output");
  std::cout << "PASS exact packed IQ2 " << label << " values=" << size << '\n';
  if (rows == 640) {
    constexpr int down_rows = 129;
    auto down = Make(10, experts, down_rows, 768, 19);
    Device dw(down.bytes.size()), exact_packed(size * 4);
    const auto down_size = std::size_t(slots) * down_rows;
    Device reference_out((down_size + 2 * guard) * 4);
    Hip(hipMemcpy(dw.data, down.bytes.data(), down.bytes.size(),
                  hipMemcpyHostToDevice));
    Hip(hipMemcpy(exact_packed.data, packed.data() + guard, size * 4,
                  hipMemcpyHostToDevice));
    Hip(hipMemset(reference_out.data, 0xA5, (down_size + 2 * guard) * 4));
    Check(q::RoutedQ2Gemm(dw.data, static_cast<const float *>(out.data) + guard,
                          static_cast<const std::int32_t *>(td.data),
                          tiles.size(), tile_rows,
                          static_cast<const std::int32_t *>(bounds.data),
                          static_cast<const std::int32_t *>(row_slot.data),
                          static_cast<float *>(reference_out.data) + guard,
                          down_rows, rows, nullptr),
          "Reference chain down failed");
    Hip(hipDeviceSynchronize());
    std::vector<float> down_guarded(down_size + 2 * guard);
    Hip(hipMemcpy(down_guarded.data(), reference_out.data,
                  down_guarded.size() * 4, hipMemcpyDeviceToHost));
    for (std::size_t i = 0; i < guard; ++i)
      Check(std::bit_cast<std::uint32_t>(down_guarded[i]) == 0xA5A5A5A5U &&
                std::bit_cast<std::uint32_t>(
                    down_guarded[guard + down_size + i]) == 0xA5A5A5A5U,
            "Reference chain output guard changed");
    std::vector<float> reference(down_guarded.begin() + guard,
                                 down_guarded.begin() + guard + down_size);
    for (float value : reference)
      Check(std::isfinite(value) &&
                std::bit_cast<std::uint32_t>(value) != 0xA5A5A5A5U,
            "Invalid reference chain output");
    CheckPackedDown(dw.data,
                    static_cast<const std::uint32_t *>(exact_packed.data),
                    static_cast<const std::int32_t *>(td.data), tiles.size(),
                    tile_rows, static_cast<const std::int32_t *>(bounds.data),
                    static_cast<const std::int32_t *>(row_slot.data), down_rows,
                    reference, "chain-" + label);
  }
#endif
}

#ifndef Q2_PACKED_CHECKS
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

#endif
