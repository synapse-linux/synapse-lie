/* SPDX-License-Identifier: MIT */
/* Generated scalar membership oracles only; no model forward or device use. */
#include "attention.h"
#include <assert.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
static unsigned fail_at;
void *__real_malloc(size_t);
void *__real_calloc(size_t, size_t);
void *__wrap_malloc(size_t n) {
  return fail_at && --fail_at == 0 ? NULL : __real_malloc(n);
}
void *__wrap_calloc(size_t n, size_t size) {
  return fail_at && --fail_at == 0 ? NULL : __real_calloc(n, size);
}
static bool visible(uint32_t query, uint32_t key, const uint32_t *mask) {
  const uint32_t block = key / 4;
  return key <= query &&
      (block >= (query + 1) / 4 ||
       (mask[block / 32] & (UINT32_C(1) << (block % 32))));
}
int main(void) {
  for (size_t n = 0; n < LIE_ATTENTION_FIXTURE_COUNT; ++n) {
    lie_attention_fixture_plan p = {0};
    assert(!lie_attention_fixture_prepare(&lie_attention_fixture_specs[n], &p));
    assert(p.deep_start + p.spec.rows == p.spec.end);
    assert(p.deep_capacity % 4 == 0 && p.short_capacity % 4 == 0);
    assert(p.deep_pitch <= 8192 && p.short_pitch <= 2048);
    assert((p.deep_start >= 65536) == (p.short_start >= 65536));
    for (uint32_t i = 0; i < p.block_count; ++i) {
      assert(!i || p.blocks[i - 1] < p.blocks[i]);
      assert(p.blocks[i] * 4 + 3 < p.deep_capacity);
      assert((p.short_base + i) * 4 + 3 < p.short_capacity);
      for (uint32_t row = 0; row < p.spec.rows; ++row) {
        for (uint32_t tail = 0; tail < 4; ++tail) {
          bool deep = visible(p.deep_start + row, p.blocks[i] * 4 + tail,
                              p.deep_mask + (size_t)row * p.deep_pitch);
          bool short_view = visible(p.short_start + row,
                                  (p.short_base + i) * 4 + tail,
                                  p.short_mask + (size_t)row * p.short_pitch);
          assert(deep == short_view);
        }
      }
    }
    /* No unseen prefix block is selected, and every explicit prefix bit has
     * exactly one translated representation. Popcount is independent of the
     * planner's rank construction. */
    for (uint32_t row = 0; row < p.spec.rows; ++row) {
      unsigned deep_bits = 0, short_bits = 0;
      for (uint32_t i = 0; i < p.deep_pitch; ++i)
        deep_bits += (unsigned)__builtin_popcount(p.deep_mask[(size_t)row * p.deep_pitch + i]);
      for (uint32_t i = 0; i < p.short_pitch; ++i)
        short_bits += (unsigned)__builtin_popcount(p.short_mask[(size_t)row * p.short_pitch + i]);
      assert(deep_bits == short_bits);
      assert(deep_bits == p.spec.selections + (p.spec.zero_mask ? 0u : 1u));
    }
    lie_attention_fixture_plan saved = p;
    assert(lie_attention_fixture_prepare(&p.spec, &p));
    assert(!memcmp(&p, &saved, sizeof(p)));
    lie_attention_fixture_dispose(&p);
    lie_attention_fixture_plan empty = {0}; assert(!memcmp(&p, &empty, sizeof(p)));
    lie_attention_fixture_dispose(&p);
  }
  lie_attention_fixture_plan p = {0}, empty = p;
  const lie_attention_fixture_spec invalid[] = {
      {1048577, 1, 1, false, false}, {UINT_MAX, 1, 1, false, false},
      {16384, 0, 1, false, false}, {16384, 9, 1, false, false},
      {1, 2, 1, false, false}, {16384, 1, 2053, false, false},
      {16384, 1, 1, true, false}, {32, 4, 512, false, false}};
  for (size_t i = 0; i < sizeof(invalid) / sizeof(invalid[0]); ++i) {
    assert(lie_attention_fixture_prepare(&invalid[i], &p));
    assert(!memcmp(&p, &empty, sizeof(p)));
  }
  assert(lie_attention_fixture_prepare(NULL, &p));
  assert(lie_attention_fixture_prepare(&lie_attention_fixture_specs[0], NULL));
  for (unsigned i = 1; i <= 3; ++i) {
    fail_at = i;
    assert(lie_attention_fixture_prepare(&lie_attention_fixture_specs[0], &p));
    fail_at = 0; assert(!memcmp(&p, &empty, sizeof(p)));
  }
  return 0;
}
