/* SPDX-License-Identifier: MIT */
#include "q2_scaled_tiles_map.h"

static uint32_t width_for(uint32_t padded) {
  const uint32_t narrow = (padded + 47u) / 48u;
  const uint32_t wide = (padded + 63u) / 64u;
  return padded >= 256u && wide * 64u <= narrow * 48u ? 64u : 48u;
}

int lie_q2_scaled_tiles_map(const uint32_t* counts, uint32_t experts,
                            uint32_t tokens, uint32_t used, int32_t* map,
                            size_t capacity,
                            struct lie_q2_scaled_tile_spans* spans) {
  if (!counts || !map || !spans || !experts || experts > 512u || !tokens ||
      tokens > 4096u || !used || used > experts)
    return 0;
  uint32_t total = 0;
  struct lie_q2_scaled_tile_spans result = {0};
  for (uint32_t e = 0; e < experts; ++e) {
    const uint32_t count = counts[e];
    if (count > tokens)
      return 0;
    const uint32_t padded = (count + 15u) / 16u * 16u;
    const uint32_t original = (padded + 47u) / 48u;
    const uint32_t width = width_for(padded);
    const uint32_t tiles = (padded + width - 1u) / width;
    total += count;
    result.original_tiles += original;
    result.original_reserved_rows += original * 48u;
    result.reserved_rows += tiles * width;
    if (count > result.max_rows)
      result.max_rows = count;
    const uint32_t bin = !count          ? 0u
                         : count <= 48u  ? 1u
                         : count <= 128u ? 2u
                         : count <= 255u ? 3u
                         : count <= 511u ? 4u
                                         : 5u;
    ++result.histogram[bin];
    if (width == 64u) {
      result.wide += tiles;
      ++result.selected_experts;
      result.selected_rows += count;
    } else {
      result.narrow += tiles;
    }
  }
  if (total != tokens * used || (size_t)result.narrow + result.wide > capacity)
    return 0;
  uint32_t ni = 0, wi = result.narrow;
  for (uint32_t e = 0; e < experts; ++e) {
    const uint32_t padded = (counts[e] + 15u) / 16u * 16u;
    const uint32_t width = width_for(padded);
    uint32_t* index = width == 64u ? &wi : &ni;
    for (uint32_t j = 0; j * width < padded; ++j)
      map[(*index)++] = (int32_t)(e | (j << 16));
  }
  *spans = result;
  return 1;
}
