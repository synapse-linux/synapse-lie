/* SPDX-License-Identifier: MIT */
#include "lie/kvc_state.h"
#include "../kvc_internal.h"
#include <float.h>
#include <string.h>

static int field(lie_state_layout *l,uint32_t role,uint32_t layer,uint64_t offset,uint64_t bytes){
    if(l->section_count==LIE_STATE_MAX_SECTIONS)return 0;
    l->sections[l->section_count++]=(lie_state_section){.role=role,.layer=layer,.dtype=LIE_STATE_U8,
        .rank=1,.shape={bytes,0,0,0},.bytes=bytes,.offset=offset};return 1;
}
lie_status lie_kvc_qwen_state_plan(const lie_kvc_qwen_geometry *g,const lie_kvc_qwen_frontier *f,
                                   uint64_t domain,uint8_t model_id,uint8_t quant_bits,
                                   lie_state_layout *out,lie_error *e){
    if(!out||!domain)return kvc_fail(e,LIE_INVALID,"missing live state domain");
    const uint32_t endian=1;
    if(*(const unsigned char *)&endian!=1||sizeof(float)!=4||FLT_RADIX!=2||FLT_MANT_DIG!=24||FLT_MAX_EXP!=128)
        return kvc_fail(e,LIE_UNSUPPORTED,"KVC live state requires little-endian binary32");
    lie_kvc_qwen_layout w;lie_status rc=lie_kvc_qwen_plan(g,f,&w,e);if(rc!=LIE_OK)return rc;
    if(f->mtp_tokens||f->mrope_delta)return kvc_fail(e,LIE_UNSUPPORTED,"KVC live state supports text AR only");
    lie_state_layout l={.abi_version=LIE_STATE_ABI,.representation_version=LIE_KVC_QWEN_TAG,
        .token_count=f->tokens,.context_tokens=f->context_tokens,.prefill_chunk=f->prefill_tokens,
        .domain=domain,.format=LIE_STATE_KVC,.model_id=model_id,.quant_bits=quant_bits,
        .model_data={f->graph_capacity}};
    if(!field(&l,LIE_STATE_HEADER,0,0,52))goto bad;
    for(unsigned i=0;i<w.section_count;++i){
        if(w.sections[i].offset==w.mtp_count_offset+4&&!field(&l,LIE_STATE_SCALAR,0,w.mtp_count_offset,4))goto bad;
        if(w.sections[i].offset==w.mrope_delta_offset+4&&!field(&l,LIE_STATE_SCALAR,1,w.mrope_delta_offset,4))goto bad;
        if(l.section_count==LIE_STATE_MAX_SECTIONS)goto bad;
        l.sections[l.section_count++]=w.sections[i];
    }
    uint64_t bytes;if(!lie_state_validate(&l,&bytes)||bytes!=w.bytes)goto bad;
    *out=l;return LIE_OK;
bad:return kvc_fail(e,LIE_INVALID,"invalid complete KVC state layout");
}
static lie_status expected(const lie_kvc_qwen_geometry *g,const lie_state_layout *l,size_t bytes,
                            lie_kvc_qwen_layout *w,lie_error *e){
    uint64_t n;if(!lie_state_validate(l,&n)||n!=bytes||l->format!=LIE_STATE_KVC)
        return kvc_fail(e,LIE_INVALID,"invalid KVC state descriptor");
    lie_kvc_qwen_frontier f={.tokens=l->token_count,.context_tokens=l->context_tokens,
        .prefill_tokens=l->prefill_chunk,.graph_capacity=l->model_data[0]};
    lie_state_layout want;lie_status rc=lie_kvc_qwen_state_plan(g,&f,l->domain,(uint8_t)l->model_id,
        (uint8_t)l->quant_bits,&want,e);if(rc!=LIE_OK)return rc;
    if(!lie_state_layout_equal(l,&want))return kvc_fail(e,LIE_INVALID,"incompatible KVC state geometry");
    return lie_kvc_qwen_plan(g,&f,w,e);
}
static const lie_state_section *find(const lie_kvc_qwen_layout *w,uint32_t role){
    for(unsigned i=0;i<w->section_count;++i)if(w->sections[i].role==role)return &w->sections[i];
    return NULL;
}
lie_status lie_kvc_qwen_state_finish(const lie_kvc_qwen_geometry *g,const lie_state_layout *l,
                                     uint32_t eos,void *raw,size_t bytes,const lie_kvc_limits *limits,lie_error *e){
    if(!raw||!limits||!g||eos>=g->vocab)return kvc_fail(e,LIE_INVALID,"invalid KVC capture output");
    lie_kvc_qwen_layout w;lie_status rc=expected(g,l,bytes,&w,e);if(rc!=LIE_OK)return rc;
    if(bytes>limits->memory_bytes)return kvc_fail(e,LIE_RESOURCE_LIMIT,"KVC capture budget exceeded");
    unsigned char *p=raw;const lie_state_section *t=find(&w,LIE_STATE_TOKENS),*h=find(&w,LIE_STATE_NGRAM),*pos=find(&w,LIE_KVC_QWEN_POSITIONS);
    for(uint32_t i=0;i<l->token_count;++i){
        if(!(i%16384)&&kvc_cancelled(limits))return kvc_fail(e,LIE_CANCELLED,"KVC capture cancelled");
        if(kvc_u32(p+t->offset+4ull*i)>=g->vocab)return kvc_fail(e,LIE_INVALID,"KVC capture token outside vocabulary");
    }
    const uint32_t head[]={0x34565344u,2,l->context_tokens,l->prefill_chunk,l->model_data[0],l->model_data[0],
        g->hidden_width,l->token_count,g->trunk_layers+g->mtp_layers,g->attention_head_dim,g->index_dim,g->vocab,LIE_KVC_QWEN_TAG};
    for(unsigned i=0;i<13;++i)kvc_put32(p+4*i,head[i]);
    kvc_put32(p+w.mtp_count_offset,0);kvc_put32(p+w.mrope_delta_offset,0);
    for(unsigned i=0;i<8;++i)kvc_put32(p+h->offset+4*i,i<l->token_count?kvc_u32(p+t->offset+4ull*(l->token_count-1-i)):eos);
    for(uint32_t i=0;i<l->token_count;++i){
        if(!(i%4096)&&kvc_cancelled(limits))return kvc_fail(e,LIE_CANCELLED,"KVC capture cancelled");
        for(unsigned j=0;j<4;++j)kvc_put32(p+pos->offset+16ull*i+4*j,j==3?0:i);
    }
    return kvc_cancelled(limits)?kvc_fail(e,LIE_CANCELLED,"KVC capture cancelled"):LIE_OK;
}
lie_status lie_kvc_qwen_state_check(const lie_kvc_qwen_geometry *g,const lie_state_layout *l,
                                    uint32_t eos,lie_kvc_span src,const lie_kvc_limits *limits,lie_error *e){
    if(!g||eos>=g->vocab)return kvc_fail(e,LIE_INVALID,"invalid KVC EOS binding");
    lie_kvc_qwen_layout w;lie_status rc=expected(g,l,src.bytes,&w,e);if(rc!=LIE_OK)return rc;
    lie_kvc_qwen_layout parsed;rc=lie_kvc_qwen_decode(src,g,limits,&parsed,e);if(rc!=LIE_OK)return rc;
    if(parsed.frontier.tokens!=l->token_count||parsed.frontier.context_tokens!=l->context_tokens||
       parsed.frontier.prefill_tokens!=l->prefill_chunk||parsed.frontier.graph_capacity!=l->model_data[0]||
       parsed.frontier.mtp_tokens||!parsed.text_positions)return kvc_fail(e,LIE_INVALID,"KVC frontier differs from binding");
    const lie_state_section *t=find(&w,LIE_STATE_TOKENS),*h=find(&w,LIE_STATE_NGRAM);
    for(unsigned i=0;i<8;++i){uint32_t want=i<l->token_count?kvc_u32(src.data+t->offset+4ull*(l->token_count-1-i)):eos;
        if(kvc_u32(src.data+h->offset+4*i)!=want)return kvc_fail(e,LIE_INVALID,"KVC ngram history differs from physical tokens");}
    return LIE_OK;
}
