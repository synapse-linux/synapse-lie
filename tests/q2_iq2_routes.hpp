// SPDX-License-Identifier: MIT
#pragma once
// Synthetic operands with measured count distributions; no model execution.
#include "src/core/json.hpp"
#include <algorithm>
#include <array>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <limits>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

namespace iq2_routes {
inline void Require(bool value, const char *message) {
  if (!value)
    throw std::runtime_error(message);
}

struct Case {
  std::string name;
  unsigned tokens, tile;
  std::vector<std::uint32_t> counts;
  std::vector<std::int32_t> ids, tiles;
  unsigned active = 0, live = 0, reserved = 0;
};

inline Case Make(std::string name, unsigned tokens, unsigned tile,
                 std::vector<std::uint32_t> counts) {
  Require(tokens > 0 && tokens <= 4096 && (tile == 64 || tile == 128) &&
              counts.size() == 512,
          "Invalid IQ2 route dimensions");
  Require(std::all_of(counts.begin(), counts.end(),
                      [tokens](auto n) { return n <= tokens; }) &&
              std::accumulate(counts.begin(), counts.end(), 0U) == tokens * 10,
          "Invalid IQ2 expert counts");
  Case out{std::move(name), tokens, tile, std::move(counts),
           std::vector<std::int32_t>(tokens * 10, -1), {}};
  // Lay each expert along distinct tokens. A count never exceeds tokens,
  // so even a wrapped segment cannot repeat an expert within one token.
  unsigned cursor = 0;
  for (unsigned e = 0; e < 512; ++e) {
    for (unsigned i = 0; i < out.counts[e]; ++i, ++cursor)
      out.ids[(cursor % tokens) * 10 + cursor / tokens] = e;
    out.active += out.counts[e] != 0;
    out.live += (out.counts[e] + 15) / 16;
    for (unsigned row = 0; row < (out.counts[e] + 15) / 16 * 16; row += tile)
      out.tiles.push_back(static_cast<std::int32_t>(e | ((row / tile) << 16)));
  }
  out.reserved = out.tiles.size() * (tile / 16);
  // Independently check all slots, per-token uniqueness and the histogram.
  std::vector<std::uint32_t> observed(512);
  for (unsigned t = 0; t < tokens; ++t) {
    std::array<bool, 512> seen{};
    for (unsigned s = 0; s < 10; ++s) {
      const auto e = out.ids[t * 10 + s];
      Require(e >= 0 && e < 512 && !seen[e], "Invalid IQ2 route assignment");
      seen[e] = true;
      ++observed[e];
    }
  }
  Require(observed == out.counts, "IQ2 route histogram changed");
  return out;
}

inline unsigned Integer(const gufo::json::Value &value, unsigned maximum) {
  const auto n = value.as_size(std::numeric_limits<std::size_t>::max());
  Require(value.is_number() && n <= maximum, "Invalid IQ2 plan integer");
  return static_cast<unsigned>(n);
}

inline std::vector<Case> Load(const std::filesystem::path &path) {
  Require(std::filesystem::file_size(path) <= 128000, "Oversized IQ2 route plan");
  std::ifstream file(path);
  const std::string text((std::istreambuf_iterator<char>(file)), {});
  Require(!file.bad(), "Cannot read IQ2 route plan");
  const auto plan = gufo::json::parse(text);
  const auto *rows = plan.find("representative_routing");
  Require(plan.member_str("schema") == "synapse-lie.q2-iq2-live-epilogue-plan.v1" &&
              rows && rows->is_array() && rows->size() == 4,
          "Invalid IQ2 route plan");
  std::vector<Case> result;
  constexpr std::array<unsigned, 4> depths{0, 0, 131072, 131072};
  constexpr std::array<unsigned, 4> layers{6, 0, 16, 6};
  for (unsigned i = 0; i < rows->size(); ++i) {
    const auto &row = rows->items()[i];
    const auto get = [&](const char *key, unsigned max) {
      const auto *value = row.find(key);
      Require(value != nullptr, "Missing IQ2 plan field");
      return Integer(*value, max);
    };
    const unsigned depth = get("depth", 131072), layer = get("layer", 47);
    const unsigned tokens = get("tokens", 4096), tile = get("gate_rows", 128);
    Require(depth == depths[i] && layer == layers[i] &&
                tokens == (i < 2 ? 2040U : 2046U) &&
                tile == (i % 2 == 0 ? 128U : 64U) &&
                get("experts", 512) == 512 && get("used", 10) == 10,
            "Unexpected canonical IQ2 route case");
    const auto *values = row.find("counts");
    Require(values && values->is_array() && values->size() == 512,
            "Missing IQ2 expert counts");
    std::vector<std::uint32_t> counts;
    for (const auto &value : values->items())
      counts.push_back(Integer(value, tokens));
    result.push_back(Make("depth" + std::to_string(depth) + "-layer" +
                              std::to_string(layer), tokens, tile, std::move(counts)));
  }
  std::vector<std::uint32_t> full(512);
  std::fill_n(full.begin(), 160, 128);
  result.push_back(Make("full-tiles", 2048, 128, std::move(full)));
  return result;
}
} // namespace iq2_routes
