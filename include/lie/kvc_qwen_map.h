/* SPDX-License-Identifier: MIT */
#ifndef LIE_KVC_QWEN_MAP_H
#define LIE_KVC_QWEN_MAP_H
#include "lie/kvc_qwen.h"
#include "lie/qwen_state.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct {
    lie_qwen_state_geometry native;
    uint32_t indexer_top_k, eos_token;
} lie_kvc_qwen_mapping;
typedef struct {
    uint32_t role, layer; /* Only INDEX and BLOCK_KEYS, complete wire arrays. */
    lie_kvc_span span;
} lie_kvc_qwen_extra;
/* Pure host representation conversion, no model forward, allocation, device
 * calls or live binding. Supports text AR (MTP frontier must be zero).
 * Success returns native QF1 component bytes and a DETACHED layout: domain=0.
 * It cannot be restored by lie_state_restore/provider APIs. Runtime adoption
 * requires independent model/tokenizer identity and numerical qualification.
 * Input immutable until completion; output must not overlap input. Failure
 * leaves layout unchanged; discard byte output after any error/cancellation.
 * BUFFER_SMALL reports required payload bytes without writing output.
 * Limits cover input wire bytes (decoder) and output bytes separately; the
 * caller accounts their combined resident peak. No hidden retained copy. */
lie_status lie_kvc_qwen_project(const lie_kvc_view *,const lie_kvc_qwen_geometry *,
                               const lie_kvc_qwen_mapping *,const lie_kvc_limits *,
                               lie_state_layout *,void *,size_t,size_t *,lie_error *);
/* Reverse conversion into the exact DS4 payload ABI. The source is raw native
 * component bytes, never compressed checkpoint bytes. Required lost history
 * must be supplied in extra; known native slices must match extra bit-for-bit.
 * Missing history is UNSUPPORTED, inconsistent/duplicate data is INVALID.
 * Eight ngram slots are reconstructed from complete physical token history;
 * text positions are canonical. All numerical tensors are copied bit-for-bit.
 * Limits bound output payload + generated position scratch; borrowed native
 * and extra buffers are accounted by the caller. Layout/domain are never
 * changed or used as model authentication. Wire geometry/frontier must match.
 * Output cannot overlap native or extra buffers. Error means discard output. */
lie_status lie_kvc_qwen_export(const lie_state_layout *,lie_kvc_span,
                              const lie_kvc_qwen_geometry *,const lie_kvc_qwen_frontier *,
                              const lie_kvc_qwen_mapping *,const lie_kvc_qwen_extra *,size_t,
                              const lie_kvc_limits *,void *,size_t,size_t *,lie_error *);
#ifdef __cplusplus
}
#endif
#endif
