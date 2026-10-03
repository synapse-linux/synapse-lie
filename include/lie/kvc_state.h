/* SPDX-License-Identifier: MIT */
#ifndef LIE_KVC_STATE_H
#define LIE_KVC_STATE_H
#include "lie/kvc_qwen.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Direct retained DS4 payload, separate from the older detached QF1 converter.
 * The provider supplies a trusted live domain and loaded model geometry.
 * No tensor conversion, allocation, device call or hidden identity inference. */
lie_status lie_kvc_qwen_state_plan(const lie_kvc_qwen_geometry *,const lie_kvc_qwen_frontier *,
                                   uint64_t domain,uint8_t model_id,uint8_t quant_bits,
                                   lie_state_layout *,lie_error *);
/* Called after the provider has copied every numerical component. Generates
 * framing, physical text positions and eight ngram slots from TOKENS. Bounds
 * and token validation precede all writes. The caller discards output on error. */
lie_status lie_kvc_qwen_state_finish(const lie_kvc_qwen_geometry *,const lie_state_layout *,
                                     uint32_t eos,void *,size_t,const lie_kvc_limits *,lie_error *);
/* Completed read/restore admission: checks exact descriptor, payload framing,
 * geometry, canonical text positions and EOS history before device mutation. */
lie_status lie_kvc_qwen_state_check(const lie_kvc_qwen_geometry *,const lie_state_layout *,
                                    uint32_t eos,lie_kvc_span,const lie_kvc_limits *,lie_error *);
/* Model-bound multimodal positions, N rows of four little-endian int32 values.
 * The fourth lane is reserved zero. Restore must receive the independently
 * prepared matching positions. Capture input must be disjoint from the output,
 * or point exactly at its position section. Image content/grid/preprocessing/encoder identity
 * is a separate admission requirement, not established by equal positions. */
lie_status lie_kvc_qwen_state_finish_positions(const lie_kvc_qwen_geometry *,const lie_state_layout *,
                                               uint32_t eos,lie_kvc_span positions,void *,size_t,
                                               const lie_kvc_limits *,lie_error *);
lie_status lie_kvc_qwen_state_check_positions(const lie_kvc_qwen_geometry *,const lie_state_layout *,
                                              uint32_t eos,lie_kvc_span payload,lie_kvc_span positions,
                                              const lie_kvc_limits *,lie_error *);
/* Vision keeps the DS4 tensor payload unchanged and appends a typed semantic
 * scope. Positions and scope must come from the independently prepared prompt.
 * Combined MTP/vision is deliberately refused by this binding. */
lie_status lie_kvc_qwen_vision_state_plan(const lie_kvc_qwen_geometry *,const lie_kvc_qwen_frontier *,uint64_t,uint8_t,uint8_t,lie_state_layout *,lie_error *);
lie_status lie_kvc_qwen_vision_state_finish(const lie_kvc_qwen_geometry *,const lie_state_layout *,uint32_t,lie_kvc_span,const unsigned char scope[32],void *,size_t,const lie_kvc_limits *,lie_error *);
lie_status lie_kvc_qwen_vision_state_check(const lie_kvc_qwen_geometry *,const lie_state_layout *,uint32_t,lie_kvc_span,lie_kvc_span,const unsigned char scope[32],const lie_kvc_limits *,lie_error *);
/* Qwen-specific continuation binding. The core's auxiliary storage is model
 * neutral; these roles and controller limits belong to this model codec.
 * KVC predictor tensors retain DS4 offsets. Residual/kept hidden rows and the
 * adaptive controller follow the client trailer in the authenticated extension.
 * This is prefix reuse with a fresh destination sampler, not RNG replay. */
#define LIE_KVC_QWEN_MTP_DEPTHS 7u
#define LIE_KVC_QWEN_MTP_RESIDUAL (LIE_STATE_MODEL_COMPONENT+2u)
#define LIE_KVC_QWEN_MTP_HIDDEN (LIE_STATE_MODEL_COMPONENT+3u)
typedef struct {
    float successes[LIE_KVC_QWEN_MTP_DEPTHS],failures[LIE_KVC_QWEN_MTP_DEPTHS];
    uint32_t retry_tokens,probe_depth,explored_depth,probe_delay,failed_depths;
} lie_kvc_qwen_mtp_controller;
lie_status lie_kvc_qwen_mtp_state_plan(const lie_kvc_qwen_geometry *,const lie_kvc_qwen_frontier *,
                                      uint64_t domain,uint8_t model_id,uint8_t quant_bits,
                                      uint32_t hidden_rows,uint32_t draft_limit,lie_state_layout *,lie_error *);
lie_status lie_kvc_qwen_mtp_state_finish(const lie_kvc_qwen_geometry *,const lie_state_layout *,
                                        uint32_t eos,const lie_kvc_qwen_mtp_controller *,void *,size_t,
                                        const lie_kvc_limits *,lie_error *);
lie_status lie_kvc_qwen_mtp_state_controller(const lie_state_layout *,lie_kvc_span,
                                            lie_kvc_qwen_mtp_controller *,lie_error *);
#ifdef __cplusplus
}
#endif
#endif
