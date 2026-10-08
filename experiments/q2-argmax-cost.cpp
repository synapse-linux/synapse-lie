// SPDX-License-Identifier: MIT
// Host-only diagnostic of the existing harness. No model forward or GPU use.
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <new>
#include <stdexcept>
#include <string>
#include <vector>
#ifdef Q2_TRACK_NEW
static std::uint64_t allocations = 0;
void* operator new(std::size_t n) {
  ++allocations;
  if (void* p = std::malloc(n)) return p;
  throw std::bad_alloc();
}
void operator delete(void* p) noexcept { std::free(p); }
void operator delete(void* p, std::size_t) noexcept { std::free(p); }
#endif
static void Require(bool good, const std::string& why) {
  if (!good) throw std::runtime_error(why);
}
static std::uint32_t Original(const std::vector<float>& logits) {
  for (float x : logits)
    Require(std::isfinite(x), "Non-finite logit frontier");
  return std::uint32_t(std::max_element(logits.begin(), logits.end()) - logits.begin());
}
static std::uint32_t SameChecks(const std::vector<float>& logits) {
  for (float x : logits)
    if (!std::isfinite(x)) throw std::runtime_error("Non-finite logit frontier");
  return std::uint32_t(std::max_element(logits.begin(), logits.end()) - logits.begin());
}
using Fn = std::uint32_t (*)(const std::vector<float>&);
static void Check() {
  for (auto values : {std::vector<float>{-3, 2, 2, -0.f}, std::vector<float>{0.f, -0.f}})
    if (Original(values) != SameChecks(values)) throw std::runtime_error("Different argmax");
  for (float invalid : {std::numeric_limits<float>::infinity(), -std::numeric_limits<float>::infinity(),
                         std::numeric_limits<float>::quiet_NaN()}) {
    unsigned rejects = 0;
    for (Fn fn : {Original, SameChecks}) {
      try { fn({0, invalid, 1}); }
      catch (const std::runtime_error& e) {
        if (std::string(e.what()) != "Non-finite logit frontier") throw;
        ++rejects;
      }
    }
    if (rejects != 2) throw std::runtime_error("Changed nonfinite refusal");
  }
}
int main(int argc, char** argv) {
  try {
    if (argc != 2) throw std::runtime_error("Expected saved logits path");
    Check();
    std::vector<float> values(248320);
    std::ifstream file(argv[1], std::ios::binary);
    if (!file.read(reinterpret_cast<char*>(values.data()), values.size()*sizeof(float)) ||
        file.peek() != std::char_traits<char>::eof()) throw std::runtime_error("Unexpected logits size");
    const auto expected = Original(values);
    if (SameChecks(values) != expected) throw std::runtime_error("Saved argmax differs");
    std::cout << std::setprecision(12);
    for (unsigned rep = 0; rep < 5; ++rep) for (unsigned arm = 0; arm < 2; ++arm) {
      const bool changed = (rep + arm) % 2;
      Fn fn = changed ? SameChecks : Original;
#ifdef Q2_TRACK_NEW
      constexpr unsigned iterations = 1;
      allocations = 0;
#else
      constexpr unsigned iterations = 32;
#endif
      std::uint64_t sum = 0;
      const auto begin = std::chrono::steady_clock::now();
      for (unsigned i = 0; i < iterations; ++i) {
        asm volatile("" : : "g"(values.data()) : "memory");
        sum += fn(values);
      }
      const double us = std::chrono::duration<double, std::micro>(std::chrono::steady_clock::now()-begin).count()/iterations;
#ifdef Q2_TRACK_NEW
      const auto count = allocations;
#endif
      if (sum != std::uint64_t(expected)*iterations) throw std::runtime_error("Timed argmax differs");
      std::cout << "{\"event\":\"argmax_host_cost\",\"changed\":" << (changed ? "true" : "false")
                << ",\"rep\":" << rep << ",\"iterations\":" << iterations
                << ",\"vocab\":" << values.size() << ",\"argmax\":" << expected
#ifdef Q2_TRACK_NEW
                << ",\"allocation_count\":" << count << ",\"timing_valid\":false"
#else
                << ",\"microseconds_per_call\":" << us << ",\"timing_valid\":true"
#endif
                << "}\n";
    }
    std::cout << "PASS host-only diagnostic; not model inference\n";
    return 0;
  } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
