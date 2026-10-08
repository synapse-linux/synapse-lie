// SPDX-License-Identifier: MIT
// Isolated diagnostic controls, set only between NgramTable instances.
#ifndef LIE_Q2_PLE_IO_HPP
#define LIE_Q2_PLE_IO_HPP
#include <fcntl.h>

#include <cstddef>
namespace q2pleio {
inline int advice = POSIX_FADV_NORMAL;
inline int advice_result = -1;
inline std::size_t bf16_cache_budget = 8 * 1024 * 1024;
}  // namespace q2pleio
#endif
