// SPDX-License-Identifier: MIT
// Synthetic WMMA cycle over original-size IQ2 experts; no model forward.
#define Q2_IQ2_PAIR_NO_MAIN 1
#include "q2_iq2_pair.cpp"
#include "src/core/crypto/sha256.hpp"
#include <span>

namespace {
namespace q = gufo::models::qwen38_flash_next::rocm;
constexpr unsigned kExperts = 512, kUsed = 10, kM = 640, kK = 2560;

std::vector<unsigned char> Encoded(unsigned seed) {
  std::vector<unsigned char> out(std::size_t(kExperts) * kM * 10 * 66);
  for (unsigned row = 0; row < kExperts * kM; ++row) {
    const __half d = __float2half(0.00319f * (1 + (row + seed) % 3));
    for (unsigned block = 0; block < 10; ++block) {
      auto *p = out.data() + (std::size_t(row) * 10 + block) * 66;
      std::memcpy(p, &d, 2);
      for (unsigned group = 0; group < 8; ++group) {
        std::uint32_t bits = ((group + block + row + seed) % 16) << 28;
        for (unsigned part = 0; part < 4; ++part) {
          p[2 + group * 8 + part] =
              (row * 13 + block * 17 + group * 19 + part * 23 + seed) % 256;
          bits |= ((row + block * 13 + part * 17 + seed) % 128) << (7 * part);
        }
        std::memcpy(p + 2 + group * 8 + 4, &bits, 4);
      }
    }
  }
  return out;
}

double Weight(const std::vector<unsigned char> &w, unsigned expert,
              unsigned row, unsigned col) {
  const auto *p =
      w.data() + ((std::size_t(expert) * kM + row) * 10 + col / 256) * 66;
  __half d;
  std::memcpy(&d, p, 2);
  const unsigned group = col % 256 / 32, part = col % 32 / 8, lane = col % 8;
  std::uint32_t bits;
  std::memcpy(&bits, p + 2 + group * 8 + 4, 4);
  const unsigned sign = (bits >> (7 * part)) & 127;
  const bool negative =
      lane == 7 ? (std::popcount(sign) & 1) : (sign >> lane) & 1;
  const auto code = p[2 + group * 8 + part];
  return double(__half2float(d)) * (2 * (bits >> 28) + 1) * 0.125 *
         double((grid[code] >> (8 * lane)) & 255) * (negative ? -1 : 1);
}

template <typename T> std::string Digest(const std::vector<T> &values) {
  return gufo::crypto::Sha256Hex(
      std::span(reinterpret_cast<const std::uint8_t *>(values.data()),
                values.size() * sizeof(T)));
}

void Cycle(unsigned tokens, unsigned active, unsigned tile,
           const std::vector<unsigned char> &gate,
           const std::vector<unsigned char> &up, const Device &gd,
           const Device &ud) {
  constexpr std::size_t guard = 16;
  const auto slots = tokens * kUsed;
  const auto size = std::size_t(slots) * kM;
  std::vector<float> x(std::size_t(tokens) * kK);
  for (std::size_t i = 0; i < x.size(); ++i)
    x[i] = (float(int((i * 17 + 31) % 251) - 125) + 0.137f) / 256;
  std::vector<std::int32_t> ids(slots), tiles;
  std::vector<std::uint32_t> counts(kExperts);
  for (unsigned i = 0; i < slots; ++i) {
    ids[i] = (i * 73 + 17) % active;
    ++counts[ids[i]];
  }
  for (unsigned e = 0; e < kExperts; ++e)
    for (unsigned t = 0; t < (counts[e] + 15) / 16 * 16; t += tile)
      tiles.push_back(static_cast<int>(e | ((t / tile) << 16)));
  const auto compact = q::RoutedCompactRows(slots, kExperts);
  Device xd(x.size() * 4), half(x.size() * 2), id(ids.size() * 4);
  Device cd(counts.size() * 4), td(tiles.size() * 4);
  Device bounds((kExperts + 1) * 4), cursors(kExperts * 4);
  Device row_token(compact * 4), row_slot(compact * 4);
  Device yd((size + 2 * guard) * 4);
  Hip(hipMemcpy(xd.data, x.data(), x.size() * 4, hipMemcpyHostToDevice));
  Hip(hipMemcpy(id.data, ids.data(), ids.size() * 4, hipMemcpyHostToDevice));
  Hip(hipMemcpy(cd.data, counts.data(), counts.size() * 4,
                hipMemcpyHostToDevice));
  Hip(hipMemcpy(td.data, tiles.data(), tiles.size() * 4,
                hipMemcpyHostToDevice));
  const auto launch = [&]() {
    q::NarrowActivations(static_cast<const float *>(xd.data), half.data, false,
                         x.size(), nullptr);
    q::RoutedCompact(static_cast<const std::int32_t *>(id.data),
                     static_cast<const std::uint32_t *>(cd.data),
                     static_cast<std::int32_t *>(bounds.data),
                     static_cast<std::int32_t *>(cursors.data),
                     static_cast<std::int32_t *>(row_token.data),
                     static_cast<std::int32_t *>(row_slot.data), tokens, kUsed,
                     kExperts, nullptr);
    Check(q::RoutedGatedIQ2Gemm(
              gd.data, ud.data, static_cast<const __half *>(half.data),
              static_cast<const std::int32_t *>(td.data), tiles.size(), tile,
              static_cast<const std::int32_t *>(bounds.data),
              static_cast<const std::int32_t *>(row_token.data),
              static_cast<const std::int32_t *>(row_slot.data),
              static_cast<float *>(yd.data) + guard, kM, kK, nullptr),
          "WMMA IQ2 gate/up dispatch failed");
  };
  hipEvent_t begin, end;
  Hip(hipEventCreate(&begin));
  Hip(hipEventCreate(&end));
  for (unsigned sample = 0; sample < 7; ++sample) {
    Hip(hipEventRecord(begin));
    for (unsigned repeat = 0; repeat < 8; ++repeat)
      launch();
    Hip(hipEventRecord(end));
    Hip(hipEventSynchronize(end));
    float ms;
    Hip(hipEventElapsedTime(&ms, begin, end));
    std::cout << "{\"event\":\"iq2_wmma_cycle\",\"sample\":" << sample
              << ",\"warmup\":" << (sample < 2 ? "true" : "false")
              << ",\"tokens\":" << tokens << ",\"active_experts\":" << active
              << ",\"tile\":" << tile
              << ",\"calls\":8,\"microseconds_per_call\":" << ms * 1000 / 8
              << "}\n";
  }
  Hip(hipEventDestroy(begin));
  Hip(hipEventDestroy(end));

  // Poison after timing so every output must be written by one complete cycle.
  Hip(hipMemset(yd.data, 0xa5, (size + 2 * guard) * 4));
  launch();
  Hip(hipDeviceSynchronize());
  std::vector<float> got(size + 2 * guard);
  Hip(hipMemcpy(got.data(), yd.data, got.size() * 4, hipMemcpyDeviceToHost));
  for (std::size_t i = 0; i < guard; ++i)
    Check(std::bit_cast<std::uint32_t>(got[i]) == 0xa5a5a5a5U &&
              std::bit_cast<std::uint32_t>(got[guard + size + i]) ==
                  0xa5a5a5a5U,
          "WMMA cycle guard changed");
  for (std::size_t i = guard; i < guard + size; ++i)
    Check(std::isfinite(got[i]) &&
              std::bit_cast<std::uint32_t>(got[i]) != 0xa5a5a5a5U,
          "WMMA cycle nonfinite or unwritten output");
  const auto label =
      "iq2-wmma-n" + std::to_string(tokens) + "-e" + std::to_string(active);
  std::ofstream saved("results/" + label + ".f32", std::ios::binary);
  saved.write(reinterpret_cast<const char *>(got.data() + guard), size * 4);
  Check(bool(saved), "Cannot save complete WMMA output");
  std::vector<float> sampled;
  std::vector<double> expected;
  for (unsigned i = 0; i < 256; ++i) {
    const unsigned slot = i * 79 % slots, row = i * 53 % kM;
    double g = 0, u = 0;
    for (unsigned col = 0; col < kK; ++col) {
      const double activation =
          __half2float(__float2half(x[std::size_t(slot / kUsed) * kK + col]));
      g += activation * Weight(gate, ids[slot], row, col);
      u += activation * Weight(up, ids[slot], row, col);
    }
    sampled.push_back(got[guard + std::size_t(slot) * kM + row]);
    expected.push_back(g * u / (1 + std::exp(-g)));
  }
  std::cout << "{\"event\":\"iq2_wmma_geometry\",\"tokens\":" << tokens
            << ",\"active_experts\":" << active << ",\"tile\":" << tile
            << ",\"tiles\":" << tiles.size() << ",\"output_values\":" << size
            << ",\"active_weight_bytes\":"
            << std::size_t(active) * kM * 10 * 66 * 2 << ",\"input_sha256\":\""
            << Digest(x) << "\",\"ids_sha256\":\"" << Digest(ids) << "\"}\n";
  Compare(sampled, expected, label);
}
} // namespace

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
    const auto gate = Encoded(3), up = Encoded(11);
    Device gd(gate.size()), ud(up.size());
    Hip(hipMemcpy(gd.data, gate.data(), gate.size(), hipMemcpyHostToDevice));
    Hip(hipMemcpy(ud.data, up.data(), up.size(), hipMemcpyHostToDevice));
    std::cout << "{\"event\":\"iq2_wmma_weights\",\"bytes\":"
              << gate.size() + up.size() << ",\"gate_sha256\":\""
              << Digest(gate) << "\",\"up_sha256\":\"" << Digest(up) << "\"}\n";
    Cycle(2040, 512, 64, gate, up, gd, ud);
    Cycle(2048, 128, 128, gate, up, gd, ud);
    std::cout << "PASS synthetic IQ2 WMMA cycles; no model throughput\n";
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
