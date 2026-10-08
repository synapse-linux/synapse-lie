// SPDX-License-Identifier: MIT
// Reuse the same independent cases, adding packed replay and full chains.
#define Q2_PACKED_CHECKS 1
#include "q2_iq2_pair.cpp"
#include "q2_routed.cpp"

int main() {
  try {
    Hip(hipSetDevice(0));
    std::cout.precision(12);
    for (int tile : {16, 48, 64})
      for (bool tiny : {false, true}) {
        RoutedQ2Case(17, 5, tile, tiny);
        RoutedQ2Case(65, 129, tile, tiny);
      }
    for (int tile : {16, 48, 64, 128})
      for (bool tiny : {false, true}) {
        IQ2Case(17, 5, tile, tiny);
        IQ2Case(65, 129, tile, tiny);
      }
    for (bool tiny : {false, true})
      IQ2Case(17, 640, 64, tiny);
    std::cout
        << "PASS synthetic packed operators and chains; no model inference\n";
  } catch (const std::exception &ex) {
    std::cerr << ex.what() << '\n';
    return 1;
  }
}
