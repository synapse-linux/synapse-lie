// SPDX-License-Identifier: MIT
#include "q2_decode_q8_oracle_rows.hpp"
#include <cassert>
#include <vector>

int main() {
  bool rejected = false;
  try { (void)Q8OracleRow(0, 0, 0); }
  catch (const std::invalid_argument&) { rejected = true; }
  assert(rejected);
  for (unsigned rows : {1u, 2u, 4u, 7u, 8u, 30u, 31u, 32u, 33u, 640u, 2560u, 16384u}) {
    std::vector<unsigned> values(rows);
    for (unsigned bank = 0; bank < 32; ++bank)
      for (unsigned sample = 0; sample < 64; ++sample) {
        const auto row = Q8OracleRow(rows, sample, bank);
        assert(row < rows);
        values.at(row) = sample;
        if (rows > 31 && sample == 5) assert(row == 31);
      }
  }
  assert(Q8OracleRow(31, 5, 0) == 30);
}
