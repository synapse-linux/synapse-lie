// SPDX-License-Identifier: MIT
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <vector>

// Same validation and first-maximum tie rule as the original harness.
// Construct the exception message only on a failed check.
inline std::uint32_t Argmax(const std::vector<float> &logits) {
  for (float x : logits)
    if (!std::isfinite(x))
      throw std::runtime_error("Non-finite logit frontier");
  return std::uint32_t(std::max_element(logits.begin(), logits.end()) -
                       logits.begin());
}
