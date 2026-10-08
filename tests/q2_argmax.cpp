// SPDX-License-Identifier: MIT
// Host-only control checks, never a model forward or GPU benchmark.
#include "q2_argmax.hpp"
#include <iostream>
#include <limits>
#include <string>

int main() {
  try {
    for (const auto &v :
         {std::vector<float>{-3, 2, 2, -0.f}, std::vector<float>{0.f, -0.f},
          std::vector<float>{-9, -3, -4}}) {
      const auto expected =
          std::uint32_t(std::max_element(v.begin(), v.end()) - v.begin());
      if (Argmax(v) != expected)
        throw std::runtime_error("Tie or negative argmax changed");
    }
    std::vector<float> v(248320, -1.f);
    v.back() = 2.f;
    if (Argmax(v) != v.size() - 1)
      throw std::runtime_error("Vocabulary tail missed");
    for (std::size_t at : {std::size_t(0), v.size() / 2, v.size() - 1}) {
      for (float invalid : {std::numeric_limits<float>::infinity(),
                            -std::numeric_limits<float>::infinity(),
                            std::numeric_limits<float>::quiet_NaN()}) {
        const float previous = v[at];
        v[at] = invalid;
        bool rejected = false;
        try {
          (void)Argmax(v);
        } catch (const std::runtime_error &e) {
          rejected = std::string(e.what()) == "Non-finite logit frontier";
        }
        v[at] = previous;
        if (!rejected)
          throw std::runtime_error("Nonfinite frontier accepted");
      }
    }
    std::cout << "PASS host argmax controls; no model inference\n";
    return 0;
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
