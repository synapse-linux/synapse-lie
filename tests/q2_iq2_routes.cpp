// SPDX-License-Identifier: MIT
#include "q2_iq2_routes.hpp"
#include <iostream>

int main(int argc, char **argv) {
  try {
    iq2_routes::Require(argc == 2, "Expected route plan path");
    const auto cases = iq2_routes::Load(argv[1]);
    iq2_routes::Require(cases.size() == 5 && cases.back().live == 1280 &&
                           cases.back().reserved == 1280,
                       "Full-tile control has an empty fragment");
    for (unsigned i = 0; i < 4; ++i)
      iq2_routes::Require(cases[i].live < cases[i].reserved,
                         "Measured routing lost its empty fragments");
    for (unsigned tokens : {1U, 15U, 16U, 17U, 4096U}) {
      std::vector<std::uint32_t> counts(512);
      std::fill_n(counts.begin(), 10, tokens);
      const auto extreme = iq2_routes::Make("extreme", tokens, 128, counts);
      for (unsigned t = 0; t < tokens; ++t)
        for (unsigned slot = 0; slot < 10; ++slot)
          iq2_routes::Require(extreme.ids[t * 10 + slot] == int(slot),
                             "Saturated expert assignment changed");
    }
    for (unsigned bad : {0U, 1U, 2U, 3U}) {
      auto counts = cases[0].counts;
      unsigned tokens = 2040, tile = 128;
      if (bad == 0) ++counts[0];
      if (bad == 1) counts[0] = 2041;
      if (bad == 2) tokens = 0;
      if (bad == 3) tile = 32;
      bool rejected = false;
      try { (void)iq2_routes::Make("invalid", tokens, tile, counts); }
      catch (const std::runtime_error &) { rejected = true; }
      iq2_routes::Require(rejected, "Invalid route data was accepted");
    }
    for (const auto &text : {"true", "-1", "1.5", "null", "4097"}) {
      bool rejected = false;
      try { (void)iq2_routes::Integer(gufo::json::parse(text), 4096); }
      catch (const std::runtime_error &) { rejected = true; }
      iq2_routes::Require(rejected, "Invalid route integer was accepted");
    }
    std::cout << "PASS synthetic route construction; no model inference\n";
    return 0;
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
