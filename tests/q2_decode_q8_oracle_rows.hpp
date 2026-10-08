// SPDX-License-Identifier: MIT
#pragma once
#include <algorithm>
#include <array>
#include <stdexcept>

inline unsigned Q8OracleRow(unsigned rows, unsigned sample, unsigned bank) {
  if (rows == 0) throw std::invalid_argument("Oracle needs at least one row");
  if (sample < 8) {
    const std::array<unsigned, 8> anchors = {
        0, 1, 2, 3, 4, 31, rows > 1 ? rows - 2 : 0, rows - 1};
    return std::min(anchors[sample], rows - 1);
  }
  return (sample * 997u + bank * 73u) % rows;
}
