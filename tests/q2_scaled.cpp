// SPDX-License-Identifier: MIT
// Reuse original operand oracles; preserve all timings after numerical
// failures.
#define Q2_PACKED_CHECKS 1
#define Q2_SCALED_CHECKS 1
#define Q2_SCALED_BENCH 1
#include "q2_routed.cpp"
#define main retained_packed_benchmark_main
#include "q2_packed_bench.cpp"
#undef main

int main() {
  try {
    Hip(hipSetDevice(0));
    std::cout << std::unitbuf;
    std::cout.precision(12);
    unsigned failures = 0, cases = 0;
    for (int tile : {16, 48, 64})
      for (int shift : {-12, 0, 12})
        for (bool tiny : {false, true}) {
          ++cases;
          try {
            RoutedQ2Case(65, 129, tile, tiny, shift);
          } catch (const std::exception &e) {
            if (std::string(e.what()) !=
                "independent operator tolerance exceeded")
              throw;
            ++failures;
            std::cout << "NUMERICAL_FAILURE: " << e.what() << '\n';
          }
        }
    // Original 2K/10-expert output geometry and more than 32 MiB active
    // weights. Include normalization/packing inside every candidate timed
    // launch.
    for (unsigned active : {512u, 128u, 64u})
      failures += !Bench(active, true, 48);
    std::cout << "{\"event\":\"scaled_summary\",\"operator_cases\":" << cases
              << ",\"failures\":" << failures
              << ",\"representation_changed\":true,\"packing_timed\":true}\n";
    return failures ? 1 : 0;
  } catch (const std::exception &e) {
    std::cerr << "FAIL: " << e.what() << '\n';
    return 1;
  }
}
