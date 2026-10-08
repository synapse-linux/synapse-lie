// SPDX-License-Identifier: MIT
#include <stdio.h>
#include <stdlib.h>

#include "experiments/q2-attention-v-blocks-contract.h"

static unsigned checks;
static void check(int condition, const char* message) {
  ++checks;
  if (!condition) {
    fprintf(stderr, "FAIL: %s\n", message);
    exit(1);
  }
}

int main(void) {
  const lie_q2_attention_v_blocks_contract valid = {
      1,    0,    0,      1,
      1,    2048, 126976, 2048,
      2560, 10,   24,     2,
      256,  4,    1045,   (size_t)2048 * 10 * 2560 * sizeof(float)};
  lie_q2_attention_v_blocks_contract r = valid;
  check(lie_q2_attention_v_blocks_bytes(&r) == 132120576,
        "128K packed extent is not the original half payload");
  check(lie_q2_attention_v_blocks_bytes(NULL) == 0, "Null contract accepted");
  for (uint32_t pos = 28672; pos <= 129024; pos += 2048) {
    r = valid;
    r.start_pos = pos;
    const size_t exact = (size_t)(pos + 2048) * 512 * 2;
    r.scratch_bytes = exact;
    check(lie_q2_attention_v_blocks_bytes(&r) == exact,
          "Exact-fit original full chunk rejected");
    --r.scratch_bytes;
    check(lie_q2_attention_v_blocks_bytes(&r) == 0,
          "One-byte-short scratch accepted");
    r.scratch_bytes = exact;
    r.mask_words = (pos + 2048 + 127) / 128;
    check(lie_q2_attention_v_blocks_bytes(&r) == exact,
          "Exact-fit causal mask rejected");
    --r.mask_words;
    check(lie_q2_attention_v_blocks_bytes(&r) == 0,
          "Truncated causal mask accepted");
  }
#define REJECT(field, value)                                             \
  do {                                                                   \
    r = valid;                                                           \
    r.field = (value);                                                   \
    check(lie_q2_attention_v_blocks_bytes(&r) == 0, #field " accepted"); \
  } while (0)
  REJECT(prefill, 0);
  REJECT(last_only, 1);
  REJECT(pending_experts, 1);
  REJECT(pending_experts, 2);
  REJECT(pending_experts, 4);
  REJECT(base_allocation, 0);
  REJECT(mask_present, 0);
  REJECT(rows, 0);
  REJECT(rows, 1);
  REJECT(rows, 8);
  REJECT(rows, 1901);
  REJECT(rows, 2047);
  REJECT(rows, 2049);
  REJECT(rows, UINT32_MAX);
  REJECT(max_batch, 2047);
  REJECT(max_batch, 4096);
  REJECT(hidden, 4096);
  REJECT(experts_used, 8);
  REJECT(heads, 32);
  REJECT(kv_heads, 4);
  REJECT(head_dim, 128);
  REJECT(ratio, 8);
  REJECT(start_pos, 0);
  REJECT(start_pos, 28671);
  REJECT(start_pos, 129025);
  REJECT(start_pos, UINT32_MAX);
  REJECT(mask_words, 0);
  REJECT(mask_words, 2049);
  REJECT(scratch_bytes, 0);
#undef REJECT
  r = valid;
  r.start_pos = 28673;
  check(lie_q2_attention_v_blocks_bytes(&r) == (size_t)30724 * 1024,
        "Temporary tail padding extent is wrong");
  printf("PASS: %u prefill phase, extent and scratch ownership checks\n",
         checks);
  return 0;
}
