// SPDX-License-Identifier: MIT
#include "q2_route_profile.hpp"
#include <array>
#include <string_view>

int main(int argc, char** argv) {
  const bool incomplete = argc == 2 && std::string_view(argv[1]) == "incomplete";
  {
    q2routes::Span span{true, 4096, 1024, 2};
    const std::array<std::uint32_t,7> skewed{192,128,80,64,32,16,512};
    q2routes::Observe(true,skewed.data(),skewed.size(),1,1024,48,24,128,11);
    std::array<std::uint32_t,64> uniform{};
    uniform.fill(16);
    q2routes::Observe(true,uniform.data(),uniform.size(),1,1024,48,64,64,64);
    span.completed = !incomplete;
  }
  {
    q2routes::Span span{false,5120,1,2};
    const std::uint32_t one = 1;
    q2routes::Observe(true,&one,1,1,1,16,1,16,1);  // Decode produces no histograms.
    span.completed = true;
  }
  return 0;
}
