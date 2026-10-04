// SPDX-License-Identifier: MIT
// Host-only routing observations. Instrumented rates are not benchmark evidence.
#ifndef LIE_Q2_ROUTE_PROFILE_HPP
#define LIE_Q2_ROUTE_PROFILE_HPP
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <locale>
#include <sstream>
#include <time.h>

namespace q2routes {
inline std::uint64_t Now() {
  timespec t{};
  return clock_gettime(CLOCK_MONOTONIC, &t) == 0
             ? std::uint64_t(t.tv_sec) * 1000000000 + t.tv_nsec : 0;
}
inline void Write(const std::ostringstream& out) {
  const auto text = out.str();
  if (std::fwrite(text.data(), 1, text.size(), stderr) != text.size())
    std::fputs("{\"event\":\"q2_route_error\"}\n", stderr);
}
struct Span;
inline thread_local Span* active = nullptr;
inline std::atomic<std::uint64_t> sequence{0};
struct Span {
  Span* const previous = active;
  const std::uint64_t id = sequence.fetch_add(1);
  const bool prefill;
  const std::uint32_t position, tokens, expected_layers;
  const std::uint64_t started_ns = Now();
  std::uint32_t observed_layers{0};
  bool completed{false};
  Span(bool p, std::uint32_t pos, std::uint32_t n, std::uint32_t layers)
      : prefill(p), position(pos), tokens(n), expected_layers(layers) {
    active = this;
  }
  Span(const Span&) = delete;
  Span& operator=(const Span&) = delete;
  ~Span() noexcept {
    const auto ended_ns = Now();
    active = previous;
    try {
      std::ostringstream out;
      out.imbue(std::locale::classic());
      out << "{\"event\":\"q2_route_forward\",\"schema\":1,\"diagnostic_only\":true"
          << ",\"id\":" << id << ",\"prefill\":" << (prefill ? "true" : "false")
          << ",\"position\":" << position << ",\"tokens\":" << tokens
          << ",\"expected_layers\":" << expected_layers
          << ",\"observed_layers\":" << observed_layers
          << ",\"started_ns\":" << started_ns << ",\"ended_ns\":" << ended_ns
          << ",\"completed\":" << (completed ? "true" : "false")
          << ",\"valid\":" << (!previous && started_ns && ended_ns > started_ns
                                      ? "true" : "false") << "}\n";
      Write(out);
    } catch (...) {
      std::fputs("{\"event\":\"q2_route_error\"}\n", stderr);
    }
  }
};
inline void Observe(bool iq2, const std::uint32_t* counts, std::uint32_t experts,
                    std::uint32_t used, std::uint32_t tokens,
                    std::uint32_t down_rows, std::uint32_t down_tiles,
                    std::uint32_t gate_rows, std::uint32_t gate_tiles) {
  if (!active || !active->prefill) return;
  if (!counts || experts == 0 || experts > 4096) {
    std::fputs("{\"event\":\"q2_route_error\"}\n", stderr);
    return;
  }
  std::ostringstream out;
  out.imbue(std::locale::classic());
  out << "{\"event\":\"q2_route_counts\",\"schema\":1,\"diagnostic_only\":true"
      << ",\"forward_id\":" << active->id
      << ",\"layer\":" << active->observed_layers++
      << ",\"at_ns\":" << Now() << ",\"iq2_wmma\":" << (iq2 ? "true" : "false")
      << ",\"tokens\":" << tokens << ",\"experts\":" << experts
      << ",\"used\":" << used << ",\"down_rows\":" << down_rows
      << ",\"down_tiles\":" << down_tiles << ",\"gate_rows\":" << gate_rows
      << ",\"gate_tiles\":" << gate_tiles << ",\"counts\":[";
  for (std::uint32_t i = 0; i < experts; ++i) {
    if (i) out << ',';
    out << counts[i];
  }
  out << "]}\n";
  Write(out);
}
}  // namespace q2routes
#endif
