// SPDX-License-Identifier: MIT
// Actual routing count distributions, synthetic weights/activations. No model rate.
#define Q2_IQ2_WMMA_NO_MAIN 1
#define Q2_PACKED_CHECKS 1
#include "q2_iq2_wmma_signs.cpp"
#include "q2_iq2_routes.hpp"
#include <set>

namespace {
void RoutedCycle(const iq2_routes::Case &test,
           const std::vector<unsigned char> &gate,
           const std::vector<unsigned char> &up, const Device &gd,
           const Device &ud) {
  const auto tokens = test.tokens, active = test.active, tile = test.tile;
  constexpr std::size_t guard = 16;
  const auto slots = tokens * kUsed;
  const auto size = std::size_t(slots) * kM;
  std::vector<float> x(std::size_t(tokens) * kK);
  for (std::size_t i = 0; i < x.size(); ++i)
    x[i] = (float(int((i * 17 + 31) % 251) - 125) + 0.137f) / 256;
  const auto &ids = test.ids, &tiles = test.tiles;
  const auto &counts = test.counts;
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
    std::cout << "{\"event\":\"iq2_epilogue_cycle\",\"sample\":" << sample
              << ",\"case\":\"" << test.name << "\",\"warmup\":" << (sample < 2 ? "true" : "false")
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
  const auto label = "iq2-epilogue-" + test.name;
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
  std::cout << "{\"event\":\"iq2_epilogue_geometry\",\"tokens\":" << tokens
            << ",\"case\":\"" << test.name << "\",\"active_experts\":" << active << ",\"tile\":" << tile
            << ",\"tiles\":" << tiles.size() << ",\"output_values\":" << size
            << ",\"active_weight_bytes\":"
            << std::size_t(active) * kM * 10 * 66 * 2 << ",\"input_sha256\":\""
            << Digest(x) << "\",\"ids_sha256\":\"" << Digest(ids)
            << "\",\"counts_sha256\":\"" << Digest(counts)
            << "\",\"live_fragments\":" << test.live
            << ",\"reserved_fragments\":" << test.reserved << "}\n";
  Compare(sampled, expected, label);
}
} // namespace

int main() {
  try {
    const auto cases = iq2_routes::Load("config/q2-iq2-live-epilogue-plan.json");
    Hip(hipSetDevice(0));
    std::cout << std::unitbuf;
    std::cout.precision(12);
    for (int tile : {16, 48, 64, 128}) {
      const std::set<int> boundaries{15, 16, 17, tile - 1, tile, tile + 1};
      for (int tokens : boundaries)
        for (bool tiny : {false, true})
          IQ2Case(tokens, 5, tile, tiny);
      IQ2Case(65, 129, tile, false);
    }
    const auto gate = Encoded(3), up = Encoded(11);
    Device gd(gate.size()), ud(up.size());
    Hip(hipMemcpy(gd.data, gate.data(), gate.size(), hipMemcpyHostToDevice));
    Hip(hipMemcpy(ud.data, up.data(), up.size(), hipMemcpyHostToDevice));
    std::cout << "{\"event\":\"iq2_epilogue_weights\",\"bytes\":"
              << gate.size() + up.size() << ",\"gate_sha256\":\""
              << Digest(gate) << "\",\"up_sha256\":\"" << Digest(up) << "\"}\n";
    for (const auto &test : cases)
      RoutedCycle(test, gate, up, gd, ud);
    std::cout << "{\"event\":\"iq2_epilogue_complete\",\"numerical_pass\":"
              << (numerical_failures ? "false" : "true")
              << ",\"independent_checks\":" << independent_checks
              << ",\"failures\":" << numerical_failures
              << ",\"model_inference\":false}\n";
    std::cout << (numerical_failures ? "FAIL" : "PASS")
              << " synthetic IQ2 epilogue cycles; no model throughput\n";
    return numerical_failures ? 1 : 0;
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
