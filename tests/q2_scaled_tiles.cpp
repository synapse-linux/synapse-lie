// SPDX-License-Identifier: MIT
// Component-only geometry comparison. Existing arithmetic failures remain.
#include "q2_scaled_fixture.hpp"

static unsigned numerical_failures = 0;
static unsigned tile_mismatches = 0;

static std::vector<char> ReadOutput(const std::string &label) {
  std::ifstream input("results/scaled-" + label + ".f32", std::ios::binary);
  Check(bool(input), "Missing scaled tile output");
  return {std::istreambuf_iterator<char>(input),
          std::istreambuf_iterator<char>()};
}

static void CheckScaledTiles(const void *weights, const float *input,
                             const std::vector<float> &host_input,
                             const std::vector<double> &expected,
                             const std::int32_t *tiles, std::uint32_t n_tiles,
                             int tile_rows, const std::int32_t *bounds,
                             const std::int32_t *slots, int rows,
                             const std::vector<float> &reference,
                             const std::string &label) {
  Check(tile_rows == 48, "Unexpected reference tile");
  std::vector<std::int32_t> host_bounds(513);
  Hip(hipMemcpy(host_bounds.data(), bounds, host_bounds.size() * 4,
                hipMemcpyDeviceToHost));
  std::vector<char> control;
  for (int width : {48, 64, 128}) {
    std::vector<std::int32_t> descriptors;
    for (int e = 0; e < 512; ++e)
      for (int offset = 0; offset < host_bounds[e + 1] - host_bounds[e];
           offset += width)
        descriptors.push_back(e | ((offset / width) << 16));
    Device device_tiles(descriptors.size() * 4);
    Hip(hipMemcpy(device_tiles.data, descriptors.data(), descriptors.size() * 4,
                  hipMemcpyHostToDevice));
    const auto suffix =
        width == 48 ? "-ref48" : "-wide" + std::to_string(width);
    try {
      CheckScaledDown(
          weights, input, host_input, expected,
          width == 48 ? tiles
                      : static_cast<const std::int32_t *>(device_tiles.data),
          width == 48 ? n_tiles : descriptors.size(), width, bounds, slots,
          rows, reference, label + suffix);
    } catch (const std::exception &e) {
      if (std::string(e.what()) != "independent operator tolerance exceeded")
        throw;
      ++numerical_failures;
      std::cout << "NUMERICAL_FAILURE: " << e.what() << '\n';
    }
    auto output = ReadOutput(label + suffix);
    Check(output.size() == reference.size() * sizeof(float),
          "Incomplete scaled tile output");
    if (width == 48) {
      control = std::move(output);
      continue;
    }
    const bool exact = control == output;
    tile_mismatches += !exact;
    std::cout << "{\"event\":\"scaled_tile_operator_replay\",\"label\":\""
              << label << "\",\"values\":" << reference.size()
              << ",\"reference_tile\":48,\"candidate_tile\":" << width
              << ",\"exact\":" << (exact ? "true" : "false") << "}\n";
  }
}

// Reuse original encoded-weight/F32-input FP64 oracles and packing checks.
// The wrapper replaces only the scaled observer; the original compensated
// and packed controls still execute with their supported 48-row geometry.
#define Q2_PACKED_CHECKS 1
#define Q2_SCALED_CHECKS 1
#define CheckScaledDown CheckScaledTiles
#include "q2_routed.cpp"
#undef CheckScaledDown
#define Q2_SCALED_BENCH 1
#define Q2_SCALED_TILE_BENCH 1
#define main unused_packed_benchmark_main
#include "q2_packed_bench.cpp"
#undef main

int main() {
  try {
    Hip(hipSetDevice(0));
    std::cout << std::unitbuf;
    std::cout.precision(12);
    for (int tokens : {17, 63, 64, 65, 127, 128, 129, 257})
      for (bool tiny : {false, true})
        RoutedQ2Case(tokens, 129, 48, tiny);
    unsigned benchmark_failures = 0;
    for (unsigned active : {512u, 128u, 64u})
      for (unsigned width : {64u, 128u})
        benchmark_failures += !Bench(active, true, width);
    std::cout << "{\"event\":\"scaled_tile_summary\",\"operator_cases\":16"
              << ",\"candidate_tiles\":[64,128],\"benchmark_cohorts\":6"
              << ",\"independent_failures\":" << numerical_failures
              << ",\"tile_mismatches\":" << tile_mismatches
              << ",\"benchmark_failures\":" << benchmark_failures
              << ",\"packing_timed_in_both_arms\":true}\n";
    return numerical_failures || tile_mismatches || benchmark_failures ? 1 : 0;
  } catch (const std::exception &e) {
    std::cerr << "FAIL: " << e.what() << '\n';
    return 1;
  }
}
