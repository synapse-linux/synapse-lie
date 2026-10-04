/* SPDX-License-Identifier: MIT */
#include "lie/kvc_qwen.h"
#include "../kvc_internal.h"
#include <string.h>
#define PAYLOAD_MAGIC 0x34565344u
#define PAYLOAD_VERSION 2u
#define PAYLOAD_HEADER 52u
static int add(lie_kvc_qwen_layout *l,uint32_t role,uint32_t layer,uint32_t dtype,
               uint32_t rank,uint64_t x,uint64_t y,uint64_t z) {
    if(l->section_count==LIE_STATE_MAX_SECTIONS)return 0;
    lie_state_section s={.role=role,.layer=layer,.dtype=dtype,.rank=rank,.offset=l->bytes,.shape={x,y,z,0}};
    uint64_t n=dtype==LIE_STATE_F16?2:4;
    for(unsigned i=0;i<rank;++i){if(!s.shape[i]||s.shape[i]>UINT64_MAX/n)return 0;n*=s.shape[i];}
    if(n>SIZE_MAX||l->bytes>SIZE_MAX-n)return 0;
    s.bytes=n;l->sections[l->section_count++]=s;l->bytes+=n;return 1;
}
lie_status lie_kvc_qwen_plan(const lie_kvc_qwen_geometry *g,const lie_kvc_qwen_frontier *f,
                            lie_kvc_qwen_layout *out,lie_error *e) {
    if(!g||!f||!out||!g->trunk_layers||g->trunk_layers>96||g->mtp_layers>8||
       !g->attention_interval||!g->attention_heads_kv||!g->attention_head_dim||!g->index_dim||
       !g->value_heads||!g->linear_head_dim||!g->conv_rows||!g->conv_channels||
       !g->ple_rows||!g->hidden_width||!g->vocab||g->vocab>INT32_MAX||
       !f->tokens||f->tokens>f->context_tokens||f->tokens>f->graph_capacity||
       !f->prefill_tokens||f->mtp_tokens>f->tokens||(!g->mtp_layers&&f->mtp_tokens))
        return kvc_fail(e,LIE_INVALID,"invalid Qwen KVC geometry or frontier");
    lie_kvc_qwen_layout l={.frontier=*f,.bytes=PAYLOAD_HEADER};
    if(!add(&l,LIE_STATE_TOKENS,0,LIE_STATE_I32,1,f->tokens,0,0)||
       !add(&l,LIE_STATE_LOGITS,0,LIE_STATE_F32,1,g->vocab,0,0))goto overflow;
    l.mtp_count_offset=l.bytes;if(l.bytes>SIZE_MAX-4)goto overflow;l.bytes+=4;
    uint64_t kv=(uint64_t)g->attention_heads_kv*g->attention_head_dim;
    for(uint32_t i=0;i<g->trunk_layers+g->mtp_layers;++i){
        if(i<g->trunk_layers&&(i+1)%g->attention_interval){
            if(!add(&l,LIE_STATE_RECURRENT,i,LIE_STATE_F32,3,g->value_heads,g->linear_head_dim,g->linear_head_dim)||
               !add(&l,LIE_STATE_CONV,i,LIE_STATE_F32,2,g->conv_rows,g->conv_channels,0))goto overflow;
        }else{
            uint32_t rows=i<g->trunk_layers?f->tokens:f->mtp_tokens;
            if(!rows)continue;
            if(!add(&l,LIE_STATE_K,i,LIE_STATE_F16,2,rows,kv,0)||
               !add(&l,LIE_STATE_V,i,LIE_STATE_F16,2,rows,kv,0)||
               !add(&l,LIE_STATE_INDEX,i,LIE_STATE_F32,2,rows,g->index_dim,0))goto overflow;
            if(rows/4&&!add(&l,LIE_STATE_BLOCK_KEYS,i,LIE_STATE_F16,2,rows/4,g->index_dim,0))goto overflow;
        }
    }
    if(!add(&l,LIE_STATE_PLE,0,LIE_STATE_F32,2,g->ple_rows,g->hidden_width,0)||
       !add(&l,LIE_STATE_NGRAM,0,LIE_STATE_I32,1,LIE_KVC_QWEN_NGRAM_SLOTS,0,0))goto overflow;
    l.mrope_delta_offset=l.bytes;if(l.bytes>SIZE_MAX-4)goto overflow;l.bytes+=4;
    if(!add(&l,LIE_KVC_QWEN_POSITIONS,0,LIE_STATE_I32,2,f->tokens,4,0))goto overflow;
    *out=l;return LIE_OK;
overflow:
    return kvc_fail(e,LIE_RESOURCE_LIMIT,"Qwen KVC layout exceeds size or section bounds");
}
static lie_status check_part(lie_kvc_span s,const lie_state_section *p,uint32_t vocab,
                             const lie_kvc_limits *limits,uint32_t *text,lie_error *e) {
    if(s.bytes!=p->bytes||(!s.data&&s.bytes))return kvc_fail(e,LIE_INVALID,"missing or incomplete Qwen KVC component");
    if(p->role==LIE_STATE_TOKENS||p->role==LIE_STATE_NGRAM){
        for(size_t i=0;i<s.bytes;i+=4){
            if(!(i%65536)&&kvc_cancelled(limits))return kvc_fail(e,LIE_CANCELLED,"KVC operation cancelled");
            if(kvc_u32(s.data+i)>=vocab)return kvc_fail(e,LIE_INVALID,"Qwen KVC token outside vocabulary");
        }
    }else if(p->role==LIE_KVC_QWEN_POSITIONS){
        for(size_t i=0;i<s.bytes;i+=16){
            if(!(i%65536)&&kvc_cancelled(limits))return kvc_fail(e,LIE_CANCELLED,"KVC operation cancelled");
            uint32_t row=(uint32_t)(i/16);
            if(kvc_u32(s.data+i)!=row||kvc_u32(s.data+i+4)!=row||
               kvc_u32(s.data+i+8)!=row||kvc_u32(s.data+i+12)) *text=0;
        }
    }
    return LIE_OK;
}
lie_status lie_kvc_qwen_decode(lie_kvc_span s,const lie_kvc_qwen_geometry *g,
                              const lie_kvc_limits *limits,lie_kvc_qwen_layout *out,lie_error *e) {
    if(!s.data||s.bytes<PAYLOAD_HEADER||!g||!limits||!out)return kvc_fail(e,LIE_INVALID,"truncated Qwen KVC payload");
    if(s.bytes>limits->memory_bytes)return kvc_fail(e,LIE_RESOURCE_LIMIT,"Qwen KVC payload budget exceeded");
    if(kvc_cancelled(limits))return kvc_fail(e,LIE_CANCELLED,"KVC operation cancelled");
    uint32_t h[13];for(unsigned i=0;i<13;++i)h[i]=kvc_u32(s.data+4*i);
    if(h[0]!=PAYLOAD_MAGIC||h[1]!=PAYLOAD_VERSION||h[12]!=LIE_KVC_QWEN_TAG)
        return kvc_fail(e,LIE_UNSUPPORTED,"unsupported Qwen KVC payload version or family");
    if(g->trunk_layers>96||g->mtp_layers>8||h[8]!=g->trunk_layers+g->mtp_layers||
       h[6]!=g->hidden_width||h[9]!=g->attention_head_dim||h[10]!=g->index_dim||h[11]!=g->vocab||h[4]!=h[5])
        return kvc_fail(e,LIE_INVALID,"Qwen KVC model geometry mismatch");
    uint64_t mtp=PAYLOAD_HEADER+4ull*h[7]+4ull*h[11];
    if(mtp>s.bytes||s.bytes-mtp<4)return kvc_fail(e,LIE_INVALID,"truncated Qwen KVC token or logit array");
    lie_kvc_qwen_frontier f={.context_tokens=h[2],.prefill_tokens=h[3],.graph_capacity=h[4],
        .tokens=h[7],.mtp_tokens=kvc_u32(s.data+(size_t)mtp)};
    lie_kvc_qwen_layout l;lie_status rc=lie_kvc_qwen_plan(g,&f,&l,e);if(rc!=LIE_OK)return rc;
    if(l.bytes!=s.bytes)return kvc_fail(e,LIE_INVALID,"Qwen KVC payload length mismatch");
    uint32_t delta=kvc_u32(s.data+(size_t)l.mrope_delta_offset);
    l.frontier.mrope_delta=delta<=INT32_MAX?(int32_t)delta:-1-(int32_t)(UINT32_MAX-delta);
    l.text_positions=delta==0;
    for(unsigned i=0;i<l.section_count;++i){const lie_state_section *p=&l.sections[i];
        rc=check_part((lie_kvc_span){s.data+(size_t)p->offset,(size_t)p->bytes},p,g->vocab,limits,&l.text_positions,e);
        if(rc!=LIE_OK)return rc;
    }
    if(kvc_cancelled(limits))return kvc_fail(e,LIE_CANCELLED,"KVC operation cancelled");
    *out=l;return LIE_OK;
}
lie_status lie_kvc_qwen_decode_record(const lie_kvc_view *v,const lie_kvc_qwen_geometry *g,
                                     const lie_kvc_limits *limits,lie_kvc_qwen_layout *out,lie_error *e) {
    if(!v||!out)return kvc_fail(e,LIE_INVALID,"invalid Qwen KVC record");
    lie_kvc_qwen_layout l;lie_status rc=lie_kvc_qwen_decode(v->payload,g,limits,&l,e);
    if(rc!=LIE_OK)return rc;
    if(l.frontier.tokens!=v->header.tokens||l.frontier.context_tokens!=v->header.context_tokens)
        return kvc_fail(e,LIE_INVALID,"KVC envelope and Qwen frontier disagree");
    *out=l;return LIE_OK;
}
lie_status lie_kvc_qwen_encode(const lie_kvc_qwen_geometry *g,const lie_kvc_qwen_frontier *f,
                              const lie_kvc_span *parts,size_t count,const lie_kvc_limits *limits,
                              void *raw,size_t capacity,size_t *required,lie_error *e) {
    if(!limits||!required)return kvc_fail(e,LIE_INVALID,"invalid Qwen KVC encode request");
    lie_kvc_qwen_layout l;lie_status rc=lie_kvc_qwen_plan(g,f,&l,e);if(rc!=LIE_OK)return rc;
    *required=(size_t)l.bytes;
    if(l.bytes>limits->memory_bytes)return kvc_fail(e,LIE_RESOURCE_LIMIT,"Qwen KVC payload budget exceeded");
    if(kvc_cancelled(limits))return kvc_fail(e,LIE_CANCELLED,"KVC operation cancelled");
    if(!parts||count!=l.section_count)return kvc_fail(e,LIE_INVALID,"missing Qwen KVC components");
    if(!raw||capacity<l.bytes)return kvc_fail(e,LIE_BUFFER_SMALL,"Qwen KVC output buffer too small");
    uintptr_t dst=(uintptr_t)raw;if(l.bytes>UINTPTR_MAX-dst)return kvc_fail(e,LIE_INVALID,"invalid Qwen KVC output range");
    uint32_t text=f->mrope_delta==0;
    for(unsigned i=0;i<l.section_count;++i){
        uintptr_t src=(uintptr_t)parts[i].data;
        if(parts[i].bytes>UINTPTR_MAX-src||(src<dst+l.bytes&&dst<src+parts[i].bytes))
            return kvc_fail(e,LIE_INVALID,"overlapping Qwen KVC components");
        rc=check_part(parts[i],&l.sections[i],g->vocab,limits,&text,e);if(rc!=LIE_OK)return rc;
    }
    unsigned char *p=raw;
    const uint32_t h[]={PAYLOAD_MAGIC,PAYLOAD_VERSION,f->context_tokens,f->prefill_tokens,
        f->graph_capacity,f->graph_capacity,g->hidden_width,f->tokens,g->trunk_layers+g->mtp_layers,
        g->attention_head_dim,g->index_dim,g->vocab,LIE_KVC_QWEN_TAG};
    for(unsigned i=0;i<13;++i)kvc_put32(p+4*i,h[i]);
    kvc_put32(p+(size_t)l.mtp_count_offset,f->mtp_tokens);
    kvc_put32(p+(size_t)l.mrope_delta_offset,(uint32_t)f->mrope_delta);
    for(unsigned i=0;i<l.section_count;++i){
        size_t pos=0;
        while(pos<parts[i].bytes){
            if(kvc_cancelled(limits))return kvc_fail(e,LIE_CANCELLED,"KVC operation cancelled");
            size_t n=parts[i].bytes-pos;if(n>1024u*1024u)n=1024u*1024u;
            memcpy(p+(size_t)l.sections[i].offset+pos,parts[i].data+pos,n);pos+=n;
        }
    }
    if(kvc_cancelled(limits))return kvc_fail(e,LIE_CANCELLED,"KVC operation cancelled");
    return LIE_OK;
}
