/* SPDX-License-Identifier: MIT */
#ifndef LIE_Q2_ATTENTION_CAPACITY_H
#define LIE_Q2_ATTENTION_CAPACITY_H

#include <stdbool.h>
#include <stdint.h>

/* The selected GPU kernel covers four tokens per bit, with 32 bits per word.
 * Allocation pitch may exceed the visible extent. Keep those bounds separate.
 * These limits cover the private 256K-prefix benchmark plus its headroom. */
enum {
  LIE_Q2_ATTENTION_TOKENS_PER_WORD = 128,
  LIE_Q2_ATTENTION_MAX_TOKENS = 266240,
  LIE_Q2_ATTENTION_MASK_WORDS = 2080,
  LIE_Q2_ATTENTION_SCAN_THREADS = 256,
  LIE_Q2_ATTENTION_WORDS_PER_THREAD = 9
};

static inline bool lie_q2_attention_mask_supported(uint32_t start_pos,
                                                   uint32_t tokens,
                                                   uint32_t mask_words) {
  const uint64_t end = (uint64_t)start_pos + tokens;
  if (tokens == 0 || end > LIE_Q2_ATTENTION_MAX_TOKENS)
    return false;
  const uint32_t visible_words = (uint32_t)((end + 127u) / 128u);
  return mask_words >= visible_words;
}

#endif
