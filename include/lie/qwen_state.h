/* SPDX-License-Identifier: MIT */
#ifndef LIE_QWEN_STATE_H
#define LIE_QWEN_STATE_H
#include "lie/state.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Qwen Flash Next text AR representation, independently versioned from any
 * provider serializer. Geometry facts are supplied by the model binding.
 * Components and chronological ring layout are owned by this C17 module. */
#define LIE_QWEN_STATE_REPRESENTATION 0x51460001u
typedef struct {
    uint32_t layers, attention_interval, conv_rows, conv_channels;
    uint32_t value_heads, head_dim, kv_width, index_width, compress_ratio;
    uint32_t ple_rows, hidden_width, ngram_count, vocab, index_capacity;
} lie_qwen_state_geometry;
/* Header's domain/context/chunk/token_count must be set. model_data[0] carries
 * the number of pooled blocks; all other metadata is reserved and zero. */
int lie_qwen_state_layout(const lie_qwen_state_geometry *,lie_state_layout *);
#ifdef __cplusplus
}
#endif
#endif
