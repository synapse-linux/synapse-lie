/* SPDX-License-Identifier: MIT */
#include "lie/qwen_state.h"
static int add(lie_state_layout *l,uint32_t role,uint32_t layer,lie_state_dtype dtype,
               unsigned rank,uint64_t x,uint64_t y,uint64_t z){
    const uint64_t shape[]={x,y,z};return lie_state_add(l,role,layer,dtype,rank,shape);
}
int lie_qwen_state_layout(const lie_qwen_state_geometry *g,lie_state_layout *l){
    if(!g||!l||!g->layers||g->layers>96||!g->attention_interval||!g->conv_rows||!g->conv_channels||
       !g->value_heads||!g->head_dim||!g->kv_width||!g->index_width||!g->compress_ratio||
       !g->vocab||!g->ngram_count||!g->index_capacity||!l->token_count)return 0;
    for(unsigned i=1;i<8;++i)if(l->model_data[i])return 0;
    uint32_t blocks=l->model_data[0];
    if(blocks>l->token_count/g->compress_ratio)return 0;
    uint32_t rows=l->token_count-blocks*g->compress_ratio;
    if(rows>g->index_capacity)return 0;
    l->abi_version=LIE_STATE_ABI;l->representation_version=LIE_QWEN_STATE_REPRESENTATION;l->section_count=0;
    if(!add(l,LIE_STATE_TOKENS,0,LIE_STATE_I32,1,l->token_count,0,0)||
       !add(l,LIE_STATE_LOGITS,0,LIE_STATE_F32,1,g->vocab,0,0)||
       !add(l,LIE_STATE_NGRAM,0,LIE_STATE_I32,1,g->ngram_count,0,0))return 0;
    if(g->ple_rows&&!add(l,LIE_STATE_PLE,0,LIE_STATE_F32,2,g->ple_rows,g->hidden_width,0))return 0;
    for(uint32_t i=0;i<g->layers;++i){
        if((i+1)%g->attention_interval){
            if(!add(l,LIE_STATE_CONV,i,LIE_STATE_F32,2,g->conv_rows,g->conv_channels,0)||
               !add(l,LIE_STATE_RECURRENT,i,LIE_STATE_F32,3,g->value_heads,g->head_dim,g->head_dim))return 0;
        }else{
            if(!add(l,LIE_STATE_K,i,LIE_STATE_F16,2,l->token_count,g->kv_width,0)||
               !add(l,LIE_STATE_V,i,LIE_STATE_F16,2,l->token_count,g->kv_width,0))return 0;
            if(rows&&!add(l,LIE_STATE_INDEX,i,LIE_STATE_F32,2,rows,g->index_width,0))return 0;
            if(blocks&&!add(l,LIE_STATE_BLOCK_KEYS,i,LIE_STATE_F16,2,blocks,g->index_width,0))return 0;
        }
    }
    uint64_t bytes;return lie_state_validate(l,&bytes);
}
