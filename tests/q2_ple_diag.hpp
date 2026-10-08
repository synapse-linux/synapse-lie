// SPDX-License-Identifier: MIT
// Diagnostic-only counters. Reset only after the previous gather has completed.
#ifndef LIE_Q2_PLE_DIAG_HPP
#define LIE_Q2_PLE_DIAG_HPP
#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <ostream>

namespace q2ple {
enum Metric {
  hash_ns,
  start_ns,
  wait_ns,
  blocked_ns,
  copies_ns,
  decode_ns,
  pread_ns,
  gathers,
  rows,
  unique_rows,
  cache_hits,
  io_rows,
  pread_calls,
  requested_bytes,
  returned_bytes,
  count
};
inline constexpr std::array<const char*, count> names{
    "hash_ns",     "start_ns",        "wait_ns",       "blocked_ns",
    "copies_ns",   "decode_ns",       "pread_ns",      "gathers",
    "rows",        "unique_rows",     "cache_hits",    "io_rows",
    "pread_calls", "requested_bytes", "returned_bytes"};
inline std::array<std::atomic<std::uint64_t>, count> values{};
inline std::uint64_t cache_slots = 0, cache_bytes = 0, workers = 0;
inline bool direct = false;
inline void Add(Metric m, std::uint64_t value = 1) {
  values[m].fetch_add(value, std::memory_order_relaxed);
}
struct Timer {
  Metric metric;
  std::chrono::steady_clock::time_point start =
      std::chrono::steady_clock::now();
  ~Timer() {
    Add(metric, std::chrono::duration_cast<std::chrono::nanoseconds>(
                    std::chrono::steady_clock::now() - start)
                    .count());
  }
};
inline void Reset() {
  for (auto& value : values)
    value.store(0, std::memory_order_relaxed);
}
using Snapshot = std::array<std::uint64_t, count>;
inline Snapshot Read() {
  Snapshot result{};
  for (int i = 0; i < count; ++i)
    result[i] = values[i].load(std::memory_order_relaxed);
  return result;
}
inline void Json(std::ostream& out, const Snapshot& snapshot) {
  out << '{';
  for (int i = 0; i < count; ++i)
    out << (i ? "," : "") << '"' << names[i] << "\":" << snapshot[i];
  out << '}';
}
}  // namespace q2ple
#endif
