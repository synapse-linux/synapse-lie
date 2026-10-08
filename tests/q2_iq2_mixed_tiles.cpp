// SPDX-License-Identifier: MIT
// Existing production kernels, measured routing counts, synthetic operands.
#define Q2_IQ2_WMMA_NO_MAIN 1
#include "q2_iq2_wmma_signs.cpp"
#include "q2_iq2_routes.hpp"
#include "iq2_mixed_tiles.h"
#include <chrono>

namespace {
struct PinnedMap {
  std::int32_t *data = nullptr;
  explicit PinnedMap(std::size_t count) {
    Hip(hipHostMalloc(reinterpret_cast<void **>(&data), count * sizeof(*data)));
  }
  ~PinnedMap() { if (data) (void)hipHostFree(data); }
  PinnedMap(const PinnedMap &) = delete;
  PinnedMap &operator=(const PinnedMap &) = delete;
};

void MixedCycle(const iq2_routes::Case &test, bool mixed,
                const std::vector<unsigned char> &gate,
                const std::vector<unsigned char> &up,
                const Device &gd, const Device &ud) {
  constexpr std::size_t guard = 16;
  const auto slots = test.tokens * kUsed;
  const auto size = std::size_t(slots) * kM;
  // Both maps fit the original 64-row capacity. No timed allocation.
  const auto capacity = slots / 64 + kExperts;
  PinnedMap map(capacity);
  lie_iq2_tile_spans spans{};
  const auto prepare = [&]() {
    if (mixed) {
      Check(lie_iq2_mixed_tiles(test.counts.data(), kExperts, test.tokens,
                                kUsed, map.data, capacity, &spans),
            "Mixed map construction failed");
    } else {
      unsigned count = 0;
      for (unsigned e = 0; e < kExperts; ++e)
        for (unsigned j = 0; j < (test.counts[e] + test.tile - 1) / test.tile; ++j)
          map.data[count++] = static_cast<std::int32_t>(e | (j << 16));
      Check(count <= capacity, "Reference map exceeds capacity");
      spans = {test.tile == 128 ? count : 0, test.tile == 64 ? count : 0};
    }
  };
  prepare();
  const std::vector<std::int32_t> expected_map(map.data, map.data + spans.wide + spans.tail);
  std::vector<float> x(std::size_t(test.tokens) * kK);
  for (std::size_t i = 0; i < x.size(); ++i)
    x[i] = (float(int((i * 17 + 31) % 251) - 125) + 0.137f) / 256;
  const auto compact = q::RoutedCompactRows(slots, kExperts);
  Device xd(x.size() * 4), half(x.size() * 2), id(test.ids.size() * 4);
  Device cd(test.counts.size() * 4), td(capacity * 4);
  Device bounds((kExperts + 1) * 4), cursors(kExperts * 4);
  Device row_token(compact * 4), row_slot(compact * 4);
  Device yd((size + 2 * guard) * 4);
  Hip(hipMemcpy(xd.data, x.data(), x.size() * 4, hipMemcpyHostToDevice));
  Hip(hipMemcpy(id.data, test.ids.data(), test.ids.size() * 4, hipMemcpyHostToDevice));
  Hip(hipMemcpy(cd.data, test.counts.data(), test.counts.size() * 4, hipMemcpyHostToDevice));
  const auto upload = [&]() {
    Hip(hipMemcpyAsync(td.data, map.data, (spans.wide + spans.tail) * 4,
                        hipMemcpyHostToDevice, nullptr));
  };
  const auto launch = [&]() {
    q::NarrowActivations(static_cast<const float *>(xd.data), half.data, false,
                         x.size(), nullptr);
    q::RoutedCompact(static_cast<const std::int32_t *>(id.data),
                     static_cast<const std::uint32_t *>(cd.data),
                     static_cast<std::int32_t *>(bounds.data),
                     static_cast<std::int32_t *>(cursors.data),
                     static_cast<std::int32_t *>(row_token.data),
                     static_cast<std::int32_t *>(row_slot.data), test.tokens,
                     kUsed, kExperts, nullptr);
    const auto dispatch = [&](unsigned offset, unsigned count, unsigned width) {
      if (count)
        Check(q::RoutedGatedIQ2Gemm(gd.data, ud.data,
                  static_cast<const __half *>(half.data),
                  static_cast<const std::int32_t *>(td.data) + offset, count, width,
                  static_cast<const std::int32_t *>(bounds.data),
                  static_cast<const std::int32_t *>(row_token.data),
                  static_cast<const std::int32_t *>(row_slot.data),
                  static_cast<float *>(yd.data) + guard, kM, kK, nullptr),
              "Mixed IQ2 dispatch failed");
    };
    dispatch(0, spans.wide, 128);
    dispatch(spans.wide, spans.tail, 64);
  };
  upload();
  Hip(hipDeviceSynchronize());
  hipEvent_t begin, end;
  Hip(hipEventCreate(&begin));
  Hip(hipEventCreate(&end));
  for (bool include_map : {false, true}) {
    for (unsigned sample = 0; sample < 7; ++sample) {
      const auto wall_begin = std::chrono::steady_clock::now();
      Hip(hipEventRecord(begin));
      for (unsigned repeat = 0; repeat < 8; ++repeat) {
        if (include_map) {
          // The prior copy must complete before the pinned source is reused.
          // Identical guard in both arms; this scope measures the serialized
          // component, not production overlap with the shared expert.
          Hip(hipStreamSynchronize(nullptr));
          prepare();
          upload();
        }
        launch();
      }
      Hip(hipEventRecord(end));
      Hip(hipEventSynchronize(end));
      const auto wall_end = std::chrono::steady_clock::now();
      float ms;
      Hip(hipEventElapsedTime(&ms, begin, end));
      const double wall = std::chrono::duration<double, std::micro>(wall_end - wall_begin).count() / 8;
      std::cout << "{\"event\":\"iq2_mixed_cycle\",\"sample\":" << sample
                << ",\"case\":\"" << test.name << "\",\"warmup\":" << (sample < 2 ? "true" : "false")
                << ",\"scope\":\"" << (include_map ? "map-upload-cycle" : "resident-map-cycle")
                << "\",\"policy\":\"" << (mixed ? "mixed" : "reference")
                << "\",\"calls\":8,\"microseconds_per_call\":" << ms * 1000 / 8
                << ",\"wall_microseconds_per_call\":" << wall << "}\n";
    }
  }
  Hip(hipEventDestroy(begin));
  Hip(hipEventDestroy(end));
  Check(std::equal(expected_map.begin(), expected_map.end(), map.data), "Map changed across cycles");
  Hip(hipMemset(yd.data, 0xa5, (size + 2 * guard) * 4));
  launch();
  Hip(hipDeviceSynchronize());
  std::vector<float> got(size + 2 * guard);
  Hip(hipMemcpy(got.data(), yd.data, got.size() * 4, hipMemcpyDeviceToHost));
  for (std::size_t i = 0; i < guard; ++i)
    Check(std::bit_cast<std::uint32_t>(got[i]) == 0xa5a5a5a5U &&
              std::bit_cast<std::uint32_t>(got[guard + size + i]) == 0xa5a5a5a5U,
          "Mixed cycle guard changed");
  for (std::size_t i = guard; i < guard + size; ++i)
    Check(std::isfinite(got[i]) && std::bit_cast<std::uint32_t>(got[i]) != 0xa5a5a5a5U,
          "Mixed cycle nonfinite or unwritten output");
  const auto label = "iq2-mixed-" + test.name;
  std::ofstream saved("results/" + label + ".f32", std::ios::binary);
  saved.write(reinterpret_cast<const char *>(got.data() + guard), size * 4);
  Check(bool(saved), "Cannot save mixed cycle output");
  std::vector<float> sampled;
  std::vector<double> expected;
  for (unsigned i = 0; i < 256; ++i) {
    const unsigned slot = i * 79 % slots, row = i * 53 % kM;
    double g = 0, u = 0;
    for (unsigned col = 0; col < kK; ++col) {
      const double activation = __half2float(__float2half(x[std::size_t(slot / kUsed) * kK + col]));
      g += activation * Weight(gate, test.ids[slot], row, col);
      u += activation * Weight(up, test.ids[slot], row, col);
    }
    sampled.push_back(got[guard + std::size_t(slot) * kM + row]);
    expected.push_back(g * u / (1 + std::exp(-g)));
  }
  std::cout << "{\"event\":\"iq2_mixed_geometry\",\"case\":\"" << test.name
            << "\",\"tokens\":" << test.tokens << ",\"active_experts\":" << test.active
            << ",\"original_tile\":" << test.tile << ",\"wide_tiles\":" << spans.wide
            << ",\"tail_tiles\":" << spans.tail << ",\"output_values\":" << size
            << ",\"active_weight_bytes\":" << std::size_t(test.active) * kM * 10 * 66 * 2
            << ",\"input_sha256\":\"" << Digest(x) << "\",\"ids_sha256\":\"" << Digest(test.ids)
            << "\",\"counts_sha256\":\"" << Digest(test.counts) << "\",\"map_sha256\":\"" << Digest(expected_map)
            << "\",\"live_fragments\":" << test.live
            << ",\"reserved_fragments\":" << spans.wide * 8 + spans.tail * 4 << "}\n";
  Compare(sampled, expected, label);
}
} // namespace

int main(int argc, char **argv) {
  try {
    Check(argc == 2 && (std::string(argv[1]) == "reference" || std::string(argv[1]) == "mixed"),
          "Expected reference or mixed tile policy");
    const bool mixed = std::string(argv[1]) == "mixed";
    const auto cases = iq2_routes::Load("config/q2-iq2-live-epilogue-plan.json");
    Hip(hipSetDevice(0));
    std::cout << std::unitbuf;
    std::cout.precision(12);
    const auto gate = Encoded(3), up = Encoded(11);
    Device gd(gate.size()), ud(up.size());
    Hip(hipMemcpy(gd.data, gate.data(), gate.size(), hipMemcpyHostToDevice));
    Hip(hipMemcpy(ud.data, up.data(), up.size(), hipMemcpyHostToDevice));
    std::cout << "{\"event\":\"iq2_mixed_weights\",\"bytes\":" << gate.size() + up.size()
              << ",\"gate_sha256\":\"" << Digest(gate) << "\",\"up_sha256\":\"" << Digest(up) << "\"}\n";
    for (const auto &test : cases) MixedCycle(test, mixed, gate, up, gd, ud);
    std::cout << "{\"event\":\"iq2_mixed_complete\",\"numerical_pass\":"
              << (numerical_failures ? "false" : "true") << ",\"independent_checks\":" << independent_checks
              << ",\"failures\":" << numerical_failures << ",\"model_inference\":false}\n";
    std::cout << (numerical_failures ? "FAIL" : "PASS") << " synthetic IQ2 mixed cycles; no model throughput\n";
    return numerical_failures ? 1 : 0;
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
