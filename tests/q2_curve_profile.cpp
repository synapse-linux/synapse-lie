// SPDX-License-Identifier: MIT
#include <thread>
#include <vector>
#include "q2_curve_profile.hpp"

int main() {
  q2ple::cache_slots = 16;
  q2ple::cache_bytes = 5120;
  q2ple::workers = 4;
  {
    q2curve::Span span{true, 4096, 2};
    q2ple::Add(q2ple::gathers);
    std::vector<std::thread> workers;
    for (unsigned i = 0; i < 4; ++i)
      workers.emplace_back([] {
        for (unsigned j = 0; j < 8; ++j) {
          q2ple::Add(q2ple::rows);
          q2ple::Add(q2ple::unique_rows);
          q2ple::Add(q2ple::cache_hits);
        }
      });
    for (auto& worker : workers)
      worker.join();
    span.completed = true;
  }
  {
    q2curve::Span incomplete{false, 4098, 1};
    // An early failed Forward must not be reported as completed work.
  }
}
