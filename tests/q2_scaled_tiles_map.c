/* SPDX-License-Identifier: MIT */
#include "q2_scaled_tiles_map.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(x)                                           \
  do {                                                     \
    if (!(x)) {                                            \
      fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #x); \
      exit(1);                                             \
    }                                                      \
  } while (0)

static struct lie_q2_scaled_tile_spans verify(const uint32_t* counts,
                                              uint32_t experts, uint32_t tokens,
                                              uint32_t used) {
  size_t capacity = 0;
  uint32_t original_reserved = 0;
  for (uint32_t e = 0; e < experts; ++e) {
    const uint32_t padded = (counts[e] + 15u) / 16u * 16u;
    capacity += (padded + 47u) / 48u;
    original_reserved += (padded + 47u) / 48u * 48u;
  }
  int32_t* storage = malloc((capacity + 2u) * sizeof(*storage));
  unsigned char* seen = calloc((size_t)experts * (tokens + 15u), 1);
  unsigned char* widths = calloc(experts, 1);
  CHECK(storage && seen && widths);
  storage[0] = storage[capacity + 1u] = -1729;
  struct lie_q2_scaled_tile_spans spans = {0};
  CHECK(lie_q2_scaled_tiles_map(counts, experts, tokens, used, storage + 1,
                                capacity, &spans));
  uint32_t selected = 0, selected_rows = 0, reserved = 0, max_rows = 0;
  uint32_t histogram[6] = {0};
  for (size_t i = 0; i < (size_t)spans.narrow + spans.wide; ++i) {
    const uint32_t word = (uint32_t)storage[i + 1u];
    const uint32_t e = word & 65535u;
    const uint32_t width = i < spans.narrow ? 48u : 64u;
    const uint32_t begin = (word >> 16) * width;
    CHECK(e < experts);
    const uint32_t padded = (counts[e] + 15u) / 16u * 16u;
    CHECK(begin < padded);
    if (widths[e])
      CHECK(widths[e] == width);
    widths[e] = (unsigned char)width;
    if (width == 64u) {
      CHECK(padded >= 256u);
      CHECK((padded + 63u) / 64u * 64u <= (padded + 47u) / 48u * 48u);
    }
    reserved += width;
    for (uint32_t row = begin; row < padded && row < begin + width; ++row)
      CHECK(++seen[(size_t)e * (tokens + 15u) + row] == 1);
  }
  for (uint32_t e = 0; e < experts; ++e) {
    const uint32_t padded = (counts[e] + 15u) / 16u * 16u;
    for (uint32_t row = 0; row < tokens + 15u; ++row)
      CHECK(seen[(size_t)e * (tokens + 15u) + row] == (row < padded));
    CHECK(!counts[e] || widths[e]);
    if (widths[e] == 64u) {
      ++selected;
      selected_rows += counts[e];
    }
    if (counts[e] > max_rows)
      max_rows = counts[e];
    const uint32_t bin = !counts[e]          ? 0u
                         : counts[e] <= 48u  ? 1u
                         : counts[e] <= 128u ? 2u
                         : counts[e] <= 255u ? 3u
                         : counts[e] <= 511u ? 4u
                                             : 5u;
    ++histogram[bin];
  }
  CHECK(spans.original_tiles == capacity &&
        spans.original_reserved_rows == original_reserved);
  CHECK(spans.reserved_rows == reserved && reserved <= original_reserved);
  CHECK(spans.narrow + spans.wide <= capacity && spans.max_rows == max_rows);
  CHECK(spans.selected_experts == selected &&
        spans.selected_rows == selected_rows);
  CHECK(memcmp(spans.histogram, histogram, sizeof(histogram)) == 0);
  CHECK(storage[0] == -1729 && storage[capacity + 1u] == -1729);
  const size_t exact_capacity = (size_t)spans.narrow + spans.wide;
  int32_t* tight = malloc((exact_capacity + 2u) * sizeof(*tight));
  CHECK(tight);
  tight[0] = tight[exact_capacity + 1u] = -1729;
  struct lie_q2_scaled_tile_spans exact = {0};
  CHECK(lie_q2_scaled_tiles_map(counts, experts, tokens, used, tight + 1,
                                exact_capacity, &exact));
  CHECK(memcmp(&spans, &exact, sizeof(spans)) == 0);
  CHECK(memcmp(storage + 1, tight + 1, exact_capacity * sizeof(*tight)) == 0);
  CHECK(tight[0] == -1729 && tight[exact_capacity + 1u] == -1729);
  free(tight);
  free(widths);
  free(seen);
  free(storage);
  return spans;
}

int main(void) {
  for (uint32_t n = 1; n <= 4096u; ++n)
    verify(&n, 1, n, 1);
  for (uint32_t split = 0; split <= 4096u; ++split) {
    const uint32_t counts[] = {split, 4096u - split};
    verify(counts, 2, 4096, 1);
  }
  uint32_t counts[512] = {0};
  for (uint32_t active = 64; active <= 512; active *= 2u) {
    for (uint32_t e = 0; e < 512u; ++e)
      counts[e] = e < active ? 20480u / active : 0u;
    const struct lie_q2_scaled_tile_spans s = verify(counts, 512, 2048, 10);
    CHECK(s.selected_experts == (active == 64u ? 64u : 0u));
  }
  for (uint32_t e = 0; e < 512u; ++e)
    counts[e] = e < 32u ? 320u : e < 288u ? 40u : 0u;
  const struct lie_q2_scaled_tile_spans mixed = verify(counts, 512, 2048, 10);
  CHECK(mixed.narrow == 256u && mixed.wide == 160u &&
        mixed.selected_rows == 10240u);
  for (uint32_t e = 0; e < 512u; ++e)
    counts[e] = 4096u;
  verify(counts, 512, 4096, 512);
  int32_t map[8], before[8];
  memset(map, 0xa5, sizeof(map));
  memcpy(before, map, sizeof(map));
  struct lie_q2_scaled_tile_spans spans, old;
  memset(&spans, 0x73, sizeof(spans));
  memcpy(&old, &spans, sizeof(old));
  const uint32_t one = 320u;
  CHECK(!lie_q2_scaled_tiles_map(&one, 1, 320, 1, map, 4, &spans));
  CHECK(!lie_q2_scaled_tiles_map(&one, 1, 319, 1, map, 8, &spans));
  CHECK(!lie_q2_scaled_tiles_map(&one, 1, 321, 1, map, 8, &spans));
  CHECK(!lie_q2_scaled_tiles_map(&one, 0, 320, 1, map, 8, &spans));
  CHECK(!lie_q2_scaled_tiles_map(&one, 513, 320, 1, map, 8, &spans));
  CHECK(!lie_q2_scaled_tiles_map(&one, 1, 0, 1, map, 8, &spans));
  CHECK(!lie_q2_scaled_tiles_map(&one, 1, 4097, 1, map, 8, &spans));
  CHECK(!lie_q2_scaled_tiles_map(&one, 1, 320, 0, map, 8, &spans));
  CHECK(!lie_q2_scaled_tiles_map(&one, 1, 320, 2, map, 8, &spans));
  CHECK(!lie_q2_scaled_tiles_map(NULL, 1, 320, 1, map, 8, &spans));
  CHECK(!lie_q2_scaled_tiles_map(&one, 1, 320, 1, NULL, 8, &spans));
  CHECK(!lie_q2_scaled_tiles_map(&one, 1, 320, 1, map, 8, NULL));
  CHECK(memcmp(map, before, sizeof(map)) == 0 &&
        memcmp(&spans, &old, sizeof(spans)) == 0);
  puts(
      "PASS synthetic Q2 selective-map coverage and rejection; no model "
      "inference");
  return 0;
}
