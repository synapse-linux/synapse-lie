/* SPDX-License-Identifier: MIT */
#include "attention.h"
#include <stdlib.h>
#include <string.h>
const lie_attention_fixture_spec
    lie_attention_fixture_specs[LIE_ATTENTION_FIXTURE_COUNT] = {
        {16384, 4, 512, false, false},
        {262144, 4, 512, false, false},
        {262145, 1, 17, false, false},
        {262147, 3, 512, false, false},
        {524288, 4, 512, false, false},
        {524289, 1, 17, false, false},
        {1048576, 1, 32, false, false},
        {1048576, 7, 512, false, false},
        {1048576, 7, 1536, false, false},
        {1048576, 1, 2051, false, false},
        {1048576, 1, 2052, false, false},
        {1048576, 3, 0, true, false},
        {1048576, 7, 512, false, true},
};
static uint32_t pitch(uint32_t end) { return ((end + 3) / 4 + 31) / 32; }
static void bit(uint32_t *mask, uint32_t words, uint32_t row,
                uint32_t block) {
  mask[(size_t)row * words + block / 32] |= UINT32_C(1) << (block % 32);
}
void lie_attention_fixture_dispose(lie_attention_fixture_plan *p) {
  if (!p) return;
  free(p->blocks); free(p->deep_mask); free(p->short_mask);
  memset(p, 0, sizeof(*p));
}
int lie_attention_fixture_prepare(const lie_attention_fixture_spec *s,
                                  lie_attention_fixture_plan *out) {
  if (!s || !out || out->blocks || out->deep_mask || out->short_mask ||
      !s->rows || s->rows > 8 || s->end < s->rows || s->end > 1048576 ||
      s->selections > 2052 || (s->zero_mask && s->selections)) return 1;
  lie_attention_fixture_plan p = {0}; p.spec = *s;
  p.deep_start = s->end - s->rows;
  const uint32_t pool = p.deep_start / 4;
  p.prefix_blocks = s->rows * s->selections;
  if (pool < p.prefix_blocks) return 1;
  const uint32_t tails = (s->end + 3) / 4 - pool;
  p.block_count = p.prefix_blocks + tails;
  p.short_base = p.deep_start >= 65536 ? 16384 : 0;
  p.short_start = (p.short_base + p.prefix_blocks) * 4 + p.deep_start % 4;
  const uint32_t short_end = p.short_start + s->rows;
  p.deep_capacity = (s->end + 3) / 4 * 4;
  p.short_capacity = (short_end + 3) / 4 * 4;
  p.deep_pitch = pitch(s->end); p.short_pitch = pitch(short_end);
  if (!p.block_count || p.short_capacity > 262144 ||
      p.short_pitch > 2048 || p.deep_pitch > 8192) return 1;
  p.blocks = malloc((size_t)p.block_count * sizeof(*p.blocks));
  p.deep_mask = calloc((size_t)s->rows * p.deep_pitch, sizeof(*p.deep_mask));
  p.short_mask = calloc((size_t)s->rows * p.short_pitch, sizeof(*p.short_mask));
  if (!p.blocks || !p.deep_mask || !p.short_mask) {
    lie_attention_fixture_dispose(&p); return 1;
  }
  for (uint32_t i = 0; i < p.prefix_blocks; ++i) {
    p.blocks[i] = (uint32_t)((uint64_t)i * pool / p.prefix_blocks);
    const uint32_t row = i / s->selections;
    bit(p.deep_mask, p.deep_pitch, row, p.blocks[i]);
    bit(p.short_mask, p.short_pitch, row, p.short_base + i);
  }
  for (uint32_t i = 0; i < tails; ++i)
    p.blocks[p.prefix_blocks + i] = pool + i;
  if (!s->zero_mask) {
    for (uint32_t row = 0; row < s->rows; ++row) {
      bit(p.deep_mask, p.deep_pitch, row, pool);
      bit(p.short_mask, p.short_pitch, row, p.short_base + p.prefix_blocks);
    }
  }
  *out = p; return 0;
}
