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
/* Host-only descriptor preflight; no pointers to weight payloads or HIP calls.
   NONE delegates unchanged legacy validation. VALID only plans this private
   workspace: it does not authorize upload, runtime linkage or a model run. */
enum {
  LIE_Q2_PROFILE_INVALID = -1,
  LIE_Q2_PROFILE_NONE = 0,
  LIE_Q2_PROFILE_VALID = 1,
  LIE_Q2_MAX_LAYERS = 48
};
typedef struct {
  int type;
  uint32_t cols, rows, experts;
  int present;
} lie_q2_tensor;
typedef struct {
  lie_q2_tensor gate, up, down;
} lie_q2_layer;
static inline int lie_q2_type(int type) {
  return type == LIE_IQ2_XXS || type == LIE_Q2_K;
}
static inline int lie_q2_tensor_matches(lie_q2_tensor t, int type,
                                        uint32_t cols, uint32_t rows,
                                        uint32_t experts) {
  return t.type == type && t.cols == cols && t.rows == rows &&
         t.experts == experts && t.present == 1;
}
static inline int lie_q2_profile_make(uint32_t tokens, uint32_t hidden,
                                      uint32_t ff, uint32_t experts,
                                      uint32_t used, uint32_t trunk_layers,
                                      int has_mtp, const lie_q2_layer* layers,
                                      size_t count, lie_q2_plan* out) {
  if (!out)
    return LIE_Q2_PROFILE_INVALID;
  const lie_q2_plan empty = {0, 0, 0, 0, {0}, {0}, 0};
  *out = empty;
  if (count > LIE_Q2_MAX_LAYERS || (!layers && count))
    return LIE_Q2_PROFILE_INVALID;
  int any = 0;
  for (size_t i = 0; i < count; ++i)
    any |= lie_q2_type(layers[i].gate.type) || lie_q2_type(layers[i].up.type) ||
           lie_q2_type(layers[i].down.type);
  if (!any)
    return LIE_Q2_PROFILE_NONE;
  if (has_mtp != 0 || hidden != 2560 || ff != 640 || count != trunk_layers)
    return LIE_Q2_PROFILE_INVALID;
  for (size_t i = 0; i < count; ++i) {
    if (!lie_q2_tensor_matches(layers[i].gate, LIE_IQ2_XXS, 2560, 640,
                               experts) ||
        !lie_q2_tensor_matches(layers[i].up, LIE_IQ2_XXS, 2560, 640, experts) ||
        !lie_q2_tensor_matches(layers[i].down, LIE_Q2_K, 768, 2560, experts))
      return LIE_Q2_PROFILE_INVALID;
  }
  return lie_q2_plan_make(tokens, experts, used, out) ? LIE_Q2_PROFILE_VALID
                                                      : LIE_Q2_PROFILE_INVALID;
}
#endif
