// SPDX-License-Identifier: MIT
#ifndef LIE_Q2_ATTENTION_V_BLOCKS_CONTRACT_H
#define LIE_Q2_ATTENTION_V_BLOCKS_CONTRACT_H

#include <stddef.h>
#include <stdint.h>

/* Eligibility for reusing the base expert output allocation during prefill.
 * A cleared pending flag means its last consumer was enqueued, not completed.
 * The caller must order that consumer, packing, attention and the next expert
 * producer on the same stream. This contract never authorizes another stream.
 */
typedef struct {
  unsigned prefill;
  unsigned last_only;
  unsigned pending_experts;
  unsigned base_allocation;
  unsigned mask_present;
  uint32_t rows;
  uint32_t start_pos;
  uint32_t max_batch;
  uint32_t hidden;
  uint32_t experts_used;
  uint32_t heads;
  uint32_t kv_heads;
  uint32_t head_dim;
  uint32_t ratio;
  uint32_t mask_words;
  size_t scratch_bytes;
} lie_q2_attention_v_blocks_contract;

static inline size_t lie_q2_attention_v_blocks_bytes(
    const lie_q2_attention_v_blocks_contract* r) {
  if (r == NULL || !r->prefill || r->last_only || r->pending_experts ||
      !r->base_allocation || !r->mask_present || r->rows != 2048 ||
      r->max_batch != 2048 || r->hidden != 2560 || r->experts_used != 10 ||
      r->heads != 24 || r->kv_heads != 2 || r->head_dim != 256 ||
      r->ratio != 4 || r->start_pos < 28672 || r->start_pos > 129024 ||
      r->mask_words > 2048) {
    return 0;
  }
  /* Bounds above precede all extent arithmetic. No wrapped context or
   * invented tokens: temporary padding alone is rounded to four rows. */
  const uint32_t end = r->start_pos + r->rows;
  const uint32_t required_words = (end + 127) / 128;
  const size_t bytes = (size_t)((end + 3) & ~UINT32_C(3)) * 512 * 2;
  return r->mask_words >= required_words && r->scratch_bytes >= bytes ? bytes
                                                                      : 0;
}

#endif
