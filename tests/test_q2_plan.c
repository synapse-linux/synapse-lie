/* SPDX-License-Identifier: MIT */
#include "../adapters/gufo-q2/q2_plan.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void layouts(void) {
  lie_q2_layout x;
  assert(lie_q2_layout_make(LIE_IQ2_XXS, 2560, 2560, &x));
  assert(x.read_cols == 2560 && x.quant_cols == 2560 && x.row_blocks == 10);
  assert(x.weight_row_bytes == 660);
  assert(lie_q2_layout_make(LIE_Q2_K, 640, 768, &x));
  assert(x.read_cols == 640 && x.weight_cols == 768 && x.quant_cols == 1024);
  assert(x.row_blocks == 3 && x.weight_row_bytes == 252);
  assert(!lie_q2_layout_make(39, 640, 640, &x));
  assert(!lie_q2_layout_make(LIE_Q2_K, 640, 640, &x));
  assert(!lie_q2_layout_make(LIE_Q2_K, 768, 768, &x));
  assert(!lie_q2_layout_make(LIE_IQ2_XXS, 2560, 2816, &x));
  assert(!lie_q2_layout_make(LIE_Q2_K, 640, 768, NULL));
}
static void padding(void) {
  lie_q2_layout x;
  assert(lie_q2_layout_make(LIE_Q2_K, 640, 768, &x));
  const size_t rows = 33;
  float *src = malloc(rows * 640 * sizeof(float));
  assert(src);
  for (size_t i = 0; i < rows * 640; ++i)
    src[i] = (float)(i + 1);
  /* CPU simulation of the EXISTING quantizer's guarded source addressing,
     not a GPU quantizer/math test. Allocation ends at the final logical row. */
  for (size_t row = 0; row < rows; ++row) {
    for (size_t col = 0; col < x.quant_cols; ++col) {
      float value = col < x.read_cols ? src[row * x.read_cols + col] : 0.0f;
      assert(value == (col < 640 ? (float)(row * 640 + col + 1) : 0.0f));
    }
  }
  free(src);
}
static void capacities(void) {
  const uint32_t sizes[] = {1, 2, 3, 8, 9, 32, 33, 511, 512, 2048};
  for (size_t n = 0; n < sizeof sizes / sizeof sizes[0]; ++n) {
    for (uint32_t used = 1; used <= 32; ++used) {
      lie_q2_plan p;
      assert(lie_q2_plan_make(sizes[n], 512, used, &p));
      assert(p.slots == (size_t)sizes[n] * used);
      /* IQ2 grouped prefill, Q2 slot-vector decode and MMQ tails. */
      assert(p.bytes[LIE_Q2_QUANT] >= p.slots * 2560 * 36 / 32 + 128 * 144);
      assert(p.bytes[LIE_Q2_QUANT] >= p.slots * 1024 * 36 / 32);
      assert(p.bytes[LIE_Q2_IDS_SRC] == p.slots * sizeof(int32_t));
      assert(p.bytes[LIE_Q2_IDS_DST] == p.bytes[LIE_Q2_IDS_SRC]);
      assert(p.bytes[LIE_Q2_BOUNDS] == 513 * sizeof(int32_t));
      assert(p.bytes[LIE_Q2_RANK] >=
             (p.slots + (p.slots + 255) / 256 * 513) * sizeof(int32_t));
      assert(p.bytes[LIE_Q2_GROUPS] >= 8 * used * 9 * sizeof(int32_t));
      size_t end = 0;
      for (int i = 0; i < LIE_Q2_REGIONS; ++i) {
        assert(p.offset[i] % 64 == 0 && p.offset[i] >= end);
        end = p.offset[i] + p.bytes[i];
      }
      assert(end <= p.total_bytes);
    }
  }
  lie_q2_plan p;
  assert(!lie_q2_plan_make(0, 512, 10, &p));
  assert(!lie_q2_plan_make(2049, 512, 10, &p));
  assert(!lie_q2_plan_make(UINT32_MAX, 512, 10, &p));
  assert(!lie_q2_plan_make(2048, 513, 10, &p));
  assert(!lie_q2_plan_make(1, 2, 3, &p));
  assert(!lie_q2_plan_make(1, 512, 33, &p));
  assert(!lie_q2_plan_make(1, 512, 0, &p));
  assert(!lie_q2_plan_make(1, 512, 10, NULL));
}
int main(void) {
  layouts();
  padding();
  capacities();
  puts("Q2_GEOMETRY_CAPACITY_CPU_PASS_NOT_GPU_OR_MODEL_QUALIFICATION");
  return 0;
}
