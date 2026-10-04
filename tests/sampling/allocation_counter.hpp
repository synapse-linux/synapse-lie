// SPDX-License-Identifier: MIT
// Single-threaded host probe only; never linked into runtime clients.
#ifndef LIE_SAMPLING_ALLOCATION_COUNTER_HPP
#define LIE_SAMPLING_ALLOCATION_COUNTER_HPP
#include <cstddef>
struct lie_sampling_allocations {
  std::size_t calls, requested_bytes, peak_live_bytes, live_bytes;
};
void lie_sampling_alloc_begin();
lie_sampling_allocations lie_sampling_alloc_end();
#endif
