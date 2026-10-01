/* SPDX-License-Identifier: MIT */
#ifndef LIE_Q2_PLAN_H
#define LIE_Q2_PLAN_H
#include <stddef.h>
#include <stdint.h>

/* Internal transitional-adapter geometry, not a model memory admission. */
enum {
  LIE_Q2_K = 10,
  LIE_IQ2_XXS = 16,
  LIE_Q2_MAX_TOKENS = 2048,
  LIE_Q2_TILE_GUARD = 128
};
enum lie_q2_region {
  LIE_Q2_QUANT,
  LIE_Q2_IDS_SRC,
  LIE_Q2_IDS_DST,
  LIE_Q2_BOUNDS,
  LIE_Q2_RANK,
  LIE_Q2_GROUPS,
  LIE_Q2_REGIONS
};
typedef struct {
  uint32_t read_cols, weight_cols, quant_cols, row_blocks;
  size_t weight_row_bytes;
} lie_q2_layout;
typedef struct {
  uint32_t max_tokens, experts, used;
  size_t slots, offset[LIE_Q2_REGIONS], bytes[LIE_Q2_REGIONS], total_bytes;
} lie_q2_plan;

static inline int lie_q2_layout_make(int type, uint32_t logical,
                                     uint32_t physical, lie_q2_layout* out) {
  if (!out)
    return 0;
  const lie_q2_layout empty = {0, 0, 0, 0, 0};
  *out = empty;
  if (!((type == LIE_IQ2_XXS && logical == 2560 && physical == 2560) ||
        (type == LIE_Q2_K && logical == 640 && physical == 768)))
    return 0;
  out->read_cols = logical;
  out->weight_cols = physical;
  out->quant_cols = (physical + 511u) / 512u * 512u;
  out->row_blocks = physical / 256u;
  out->weight_row_bytes = out->row_blocks * (type == LIE_Q2_K ? 84u : 66u);
  return 1;
}
static inline int lie_q2_plan_make(uint32_t tokens, uint32_t experts,
                                   uint32_t used, lie_q2_plan* out) {
  if (!out)
    return 0;
  /* Value initialization is valid in both C17 and the HIP adapter's C++17. */
  const lie_q2_plan empty = {0, 0, 0, 0, {0}, {0}, 0};
  *out = empty;
  if (!tokens || tokens > LIE_Q2_MAX_TOKENS || !experts || experts > 512 ||
      !used || used > 32 || used > experts)
    return 0;
  const size_t slots = (size_t)tokens * used;
  const size_t blocks = (slots + 255) / 256;
  /* Bounds above keep all products representable even on a 32-bit host.
     Q8_1: 36 B/32 values; tiled Q8: 144 B/128 values, same ratio.
     Reserve the larger gathered gate/up input, plus MMQ's last tile guard. */
  out->bytes[LIE_Q2_QUANT] = slots * 2880 + LIE_Q2_TILE_GUARD * 144;
  out->bytes[LIE_Q2_IDS_SRC] = slots * sizeof(int32_t);
  out->bytes[LIE_Q2_IDS_DST] = slots * sizeof(int32_t);
  out->bytes[LIE_Q2_BOUNDS] = ((size_t)experts + 1) * sizeof(int32_t);
  out->bytes[LIE_Q2_RANK] = (slots + blocks * (experts + 1)) * sizeof(int32_t);
  out->bytes[LIE_Q2_GROUPS] = (size_t)8 * used * 9 * sizeof(int32_t);
  size_t end = 0;
  for (int i = 0; i < LIE_Q2_REGIONS; ++i) {
    end = (end + 63) / 64 * 64;
    out->offset[i] = end;
    end += out->bytes[i];
  }
  out->max_tokens = tokens;
  out->experts = experts;
  out->used = used;
  out->slots = slots;
  out->total_bytes = end;
  return 1;
}
#endif
