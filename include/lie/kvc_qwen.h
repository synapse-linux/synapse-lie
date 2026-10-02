/* SPDX-License-Identifier: MIT */
#ifndef LIE_KVC_QWEN_H
#define LIE_KVC_QWEN_H
#include "lie/kvc.h"
#include "lie/state.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_KVC_QWEN_TAG 0x51573802u
#define LIE_KVC_QWEN_NGRAM_SLOTS 8u
/* Geometry is supplied by an audited model binding, NOT guessed from a KVC
 * model id. The wire header lacks several of these dimensions. No weights,
 * device pointers, host model forward or upstream types enter this contract. */
typedef struct {
    uint32_t trunk_layers, mtp_layers, attention_interval;
    uint32_t attention_heads_kv, attention_head_dim, index_dim;
    uint32_t value_heads, linear_head_dim, conv_rows, conv_channels;
    uint32_t ple_rows, hidden_width, vocab;
} lie_kvc_qwen_geometry;
typedef struct {
    uint32_t context_tokens, prefill_tokens, graph_capacity, tokens, mtp_tokens;
    int32_t mrope_delta;
} lie_kvc_qwen_frontier;
enum { LIE_KVC_QWEN_POSITIONS=LIE_STATE_MODEL_COMPONENT+1 };
typedef struct {
    lie_kvc_qwen_frontier frontier;
    uint64_t bytes, mtp_count_offset, mrope_delta_offset;
    uint32_t section_count, text_positions;
    /* Same typed component vocabulary as LIE state, but no alignment padding,
     * and INDEX contains ALL chronological rows, including pooled history. */
    lie_state_section sections[LIE_STATE_MAX_SECTIONS];
} lie_kvc_qwen_layout;
lie_status lie_kvc_qwen_plan(const lie_kvc_qwen_geometry *,const lie_kvc_qwen_frontier *,
                            lie_kvc_qwen_layout *,lie_error *);
/* Decode validates exact length, header geometry and token/ngram bounds.
 * text_positions reports delta==0 and every position==(i,i,i,0). Parsing MTP
 * or vision records does NOT establish support for executing those records. */
lie_status lie_kvc_qwen_decode(lie_kvc_span,const lie_kvc_qwen_geometry *,
                              const lie_kvc_limits *,lie_kvc_qwen_layout *,lie_error *);
/* Adds outer KVC token/context consistency checks. Does not authenticate the
 * model: callers must independently bind weights, tokenizer and geometry. */
lie_status lie_kvc_qwen_decode_record(const lie_kvc_view *,const lie_kvc_qwen_geometry *,
                                     const lie_kvc_limits *,lie_kvc_qwen_layout *,lie_error *);
/* Canonical wire serializer. Input spans in plan order must contain EVERY
 * component in the DS4 orientation/precision, already little-endian. Missing
 * raw index history, pooled keys, PLE, MTP or positions is an error. No values
 * are invented, rounded or recomputed. Output and inputs must not overlap.
 * On any error discard output; *required is set after a valid plan. No alloc.
 * Limits apply to output bytes; caller separately accounts borrowed inputs. */
lie_status lie_kvc_qwen_encode(const lie_kvc_qwen_geometry *,const lie_kvc_qwen_frontier *,
                              const lie_kvc_span *,size_t,const lie_kvc_limits *,
                              void *,size_t,size_t *required,lie_error *);
#ifdef __cplusplus
}
#endif
#endif
