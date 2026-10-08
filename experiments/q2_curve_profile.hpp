// SPDX-License-Identifier: MIT
// Diagnostic-only host observation. Never use instrumented rates as a benchmark.
#ifndef LIE_Q2_CURVE_PROFILE_HPP
#define LIE_Q2_CURVE_PROFILE_HPP
#include <cstdio>
#include <cstdint>
#include <fstream>
#include <sstream>
#include <string>
#include <time.h>
#include "q2_ple_diag.hpp"

namespace q2curve {
inline std::uint64_t Now() {
  timespec t{};
  if (clock_gettime(CLOCK_MONOTONIC, &t) != 0)
    return 0;
  return std::uint64_t(t.tv_sec) * 1000000000 + std::uint64_t(t.tv_nsec);
}
struct Io {
  std::uint64_t read_bytes{0};
  bool valid{false};
};
inline Io ReadIo() {
  std::ifstream in("/proc/self/io");
  std::string key;
  std::uint64_t value;
  while (in >> key >> value)
    if (key == "read_bytes:")
      return {value, true};
  return {};
}
struct Span {
  const bool prefill;
  const std::uint32_t position;
  const std::size_t tokens;
  const Io io = ReadIo();
  const q2ple::Snapshot before = q2ple::Read();
  const std::uint64_t started_ns = Now();
  bool completed{false};
  Span(bool p, std::uint32_t pos, std::size_t n)
      : prefill(p), position(pos), tokens(n) {}
  Span(const Span&) = delete;
  Span& operator=(const Span&) = delete;
  ~Span() noexcept {
    try {
      const auto ended_ns = Now();
      auto delta = q2ple::Read();
      bool valid = started_ns != 0 && ended_ns >= started_ns;
      for (std::size_t i = 0; i < delta.size(); ++i) {
        valid = valid && delta[i] >= before[i];
        delta[i] -= before[i];
      }
      const Io after = ReadIo();
      const bool io_valid = io.valid && after.valid && after.read_bytes >= io.read_bytes;
      std::ostringstream out;
      out << "{\"event\":\"q2_curve_forward\",\"schema\":1,\"diagnostic_only\":true"
          << ",\"prefill\":" << (prefill ? "true" : "false")
          << ",\"position\":" << position << ",\"tokens\":" << tokens
          << ",\"completed\":" << (completed ? "true" : "false")
          << ",\"valid\":" << (valid ? "true" : "false")
          << ",\"started_ns\":" << started_ns << ",\"ended_ns\":" << ended_ns
          << ",\"process_io_valid\":" << (io_valid ? "true" : "false")
          << ",\"process_read_bytes\":" << (io_valid ? after.read_bytes - io.read_bytes : 0)
          << ",\"cache_slots\":" << q2ple::cache_slots
          << ",\"cache_bytes\":" << q2ple::cache_bytes
          << ",\"workers\":" << q2ple::workers
          << ",\"direct_io\":" << (q2ple::direct ? "true" : "false")
          << ",\"ple\":";
      q2ple::Json(out, delta);
      out << "}\n";
      const auto text = out.str();
      (void)std::fwrite(text.data(), 1, text.size(), stderr);
    } catch (...) {
      std::fputs("{\"event\":\"q2_curve_profile_error\"}\n", stderr);
    }
  }
};
} // namespace q2curve
#endif
