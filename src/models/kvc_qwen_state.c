/* SPDX-License-Identifier: MIT */
#include "lie/kvc_state.h"
#include "../kvc_internal.h"
#include <float.h>
#include <math.h>
#include <string.h>
#define MTP_HEADER 100u

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
    if(f->mrope_delta)return kvc_fail(e,LIE_UNSUPPORTED,"KVC live state requires canonical text positions");
    lie_state_layout l={.abi_version=LIE_STATE_ABI,.representation_version=LIE_KVC_QWEN_TAG,
        .token_count=f->tokens,.context_tokens=f->context_tokens,.prefill_chunk=f->prefill_tokens,
        .domain=domain,.format=LIE_STATE_KVC,.model_id=model_id,.quant_bits=quant_bits,
        .model_data={f->graph_capacity,f->mtp_tokens}};
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
lie_status lie_kvc_qwen_mtp_state_plan(const lie_kvc_qwen_geometry *g,const lie_kvc_qwen_frontier *f,
                                      uint64_t domain,uint8_t model_id,uint8_t quant_bits,
                                      uint32_t hidden_rows,uint32_t draft_limit,lie_state_layout *out,lie_error *e){
    if(!g||!f||!out||g->mtp_layers!=1||!draft_limit||draft_limit>LIE_KVC_QWEN_MTP_DEPTHS||
       !hidden_rows||hidden_rows>f->tokens||hidden_rows>LIE_KVC_QWEN_MTP_DEPTHS+1)
        return kvc_fail(e,LIE_INVALID,"invalid Qwen MTP continuation frontier");
    lie_state_layout l;lie_status rc=lie_kvc_qwen_state_plan(g,f,domain,model_id,quant_bits,&l,e);
    if(rc!=LIE_OK)return rc;
    l.format=LIE_STATE_KVC_AUX;l.model_data[3]=hidden_rows;l.model_data[4]=draft_limit;
    uint64_t dims[]={MTP_HEADER,g->hidden_width};
    if(!lie_state_add(&l,LIE_STATE_AUXILIARY,0,LIE_STATE_U8,1,dims))goto bad;
    dims[0]=g->hidden_width;
    if(f->mtp_tokens&&!lie_state_add(&l,LIE_KVC_QWEN_MTP_RESIDUAL,0,LIE_STATE_F32,1,dims))goto bad;
    dims[0]=hidden_rows;
    if(!lie_state_add(&l,LIE_KVC_QWEN_MTP_HIDDEN,0,LIE_STATE_F32,2,dims))goto bad;
    uint64_t bytes;if(!lie_state_validate(&l,&bytes))goto bad;
    *out=l;return LIE_OK;
bad:return kvc_fail(e,LIE_INVALID,"invalid MTP auxiliary component layout");
}
static lie_status expected(const lie_kvc_qwen_geometry *g,const lie_state_layout *l,size_t bytes,
                            lie_kvc_qwen_layout *w,lie_error *e){
    uint64_t n,aux;if(!lie_state_kvc_parts(l,&n,&aux)||n+aux!=bytes)
        return kvc_fail(e,LIE_INVALID,"invalid KVC state descriptor");
    lie_kvc_qwen_frontier f={.tokens=l->token_count,.context_tokens=l->context_tokens,
        .prefill_tokens=l->prefill_chunk,.graph_capacity=l->model_data[0],.mtp_tokens=l->model_data[1]};
    lie_state_layout want;lie_status rc=aux?
        lie_kvc_qwen_mtp_state_plan(g,&f,l->domain,(uint8_t)l->model_id,(uint8_t)l->quant_bits,l->model_data[3],l->model_data[4],&want,e):
        lie_kvc_qwen_state_plan(g,&f,l->domain,(uint8_t)l->model_id,(uint8_t)l->quant_bits,&want,e);
    if(rc!=LIE_OK)return rc;
    if(!lie_state_layout_equal(l,&want))return kvc_fail(e,LIE_INVALID,"incompatible KVC state geometry");
    return lie_kvc_qwen_plan(g,&f,w,e);
}
static const lie_state_section *find(const lie_kvc_qwen_layout *w,uint32_t role){
    for(unsigned i=0;i<w->section_count;++i)if(w->sections[i].role==role)return &w->sections[i];
    return NULL;
}
static lie_status finish(const lie_kvc_qwen_geometry *g,const lie_state_layout *l,
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
    kvc_put32(p+w.mtp_count_offset,l->model_data[1]);kvc_put32(p+w.mrope_delta_offset,0);
    for(unsigned i=0;i<8;++i)kvc_put32(p+h->offset+4*i,i<l->token_count?kvc_u32(p+t->offset+4ull*(l->token_count-1-i)):eos);
    for(uint32_t i=0;i<l->token_count;++i){
        if(!(i%4096)&&kvc_cancelled(limits))return kvc_fail(e,LIE_CANCELLED,"KVC capture cancelled");
        for(unsigned j=0;j<4;++j)kvc_put32(p+pos->offset+16ull*i+4*j,j==3?0:i);
    }
    return kvc_cancelled(limits)?kvc_fail(e,LIE_CANCELLED,"KVC capture cancelled"):LIE_OK;
}
lie_status lie_kvc_qwen_state_finish(const lie_kvc_qwen_geometry *g,const lie_state_layout *l,
                                     uint32_t eos,void *raw,size_t bytes,const lie_kvc_limits *limits,lie_error *e){
    if(!l||l->format==LIE_STATE_KVC_AUX)return kvc_fail(e,LIE_INVALID,"MTP auxiliary state requires its controller");
    return finish(g,l,eos,raw,bytes,limits,e);
}
static int controller_valid(const lie_kvc_qwen_mtp_controller *c,uint32_t limit){
    if(!c||!limit||limit>LIE_KVC_QWEN_MTP_DEPTHS||c->retry_tokens>16||c->probe_depth>limit||
       c->explored_depth>limit||c->probe_delay>16||c->failed_depths>=(1u<<limit))return 0;
    for(unsigned i=0;i<LIE_KVC_QWEN_MTP_DEPTHS;++i){float a=c->successes[i],b=c->failures[i];
        if(!isfinite(a)||!isfinite(b)||a<0||b<0||!isfinite(a+b)||a+b<=0)return 0;
    }
    return 1;
}
static const lie_state_section *auxiliary(const lie_state_layout *l){
    for(unsigned i=0;i<l->section_count;++i)if(l->sections[i].role==LIE_STATE_AUXILIARY)return &l->sections[i];
    return NULL;
}
lie_status lie_kvc_qwen_mtp_state_finish(const lie_kvc_qwen_geometry *g,const lie_state_layout *l,
                                        uint32_t eos,const lie_kvc_qwen_mtp_controller *c,void *raw,size_t bytes,
                                        const lie_kvc_limits *limits,lie_error *e){
    if(!l||l->format!=LIE_STATE_KVC_AUX||!controller_valid(c,l->model_data[4]))
        return kvc_fail(e,LIE_INVALID,"invalid MTP capture controller");
    lie_status rc=finish(g,l,eos,raw,bytes,limits,e);if(rc!=LIE_OK)return rc;
    unsigned char *p=(unsigned char *)raw+auxiliary(l)->offset;
    memcpy(p,"LIEMTP1",8);kvc_put32(p+8,1);kvc_put32(p+12,MTP_HEADER);
    kvc_put32(p+16,l->model_data[4]);kvc_put32(p+20,l->model_data[3]);
    for(unsigned i=0;i<LIE_KVC_QWEN_MTP_DEPTHS;++i){uint32_t a,b;
        memcpy(&a,&c->successes[i],4);memcpy(&b,&c->failures[i],4);
        kvc_put32(p+24+4*i,a);kvc_put32(p+52+4*i,b);
    }
    const uint32_t fields[]={c->retry_tokens,c->probe_depth,c->explored_depth,c->probe_delay,c->failed_depths};
    for(unsigned i=0;i<5;++i)kvc_put32(p+80+4*i,fields[i]);
    return kvc_cancelled(limits)?kvc_fail(e,LIE_CANCELLED,"MTP capture cancelled"):LIE_OK;
}
lie_status lie_kvc_qwen_mtp_state_controller(const lie_state_layout *l,lie_kvc_span src,
                                            lie_kvc_qwen_mtp_controller *out,lie_error *e){
    uint64_t base,tail;if(!out||!src.data||!lie_state_kvc_parts(l,&base,&tail)||base+tail!=src.bytes||
        l->format!=LIE_STATE_KVC_AUX||l->representation_version!=LIE_KVC_QWEN_TAG||
        !l->model_data[3]||l->model_data[3]>l->token_count||l->model_data[3]>LIE_KVC_QWEN_MTP_DEPTHS+1)
        return kvc_fail(e,LIE_INVALID,"invalid MTP state descriptor");
    const lie_state_section *a=auxiliary(l);
    if(a->bytes!=MTP_HEADER)return kvc_fail(e,LIE_INVALID,"invalid MTP controller size");
    const unsigned char *p=src.data+a->offset;
    if(memcmp(p,"LIEMTP1",8)||kvc_u32(p+8)!=1||kvc_u32(p+12)!=MTP_HEADER||
       kvc_u32(p+16)!=l->model_data[4]||kvc_u32(p+20)!=l->model_data[3])
        return kvc_fail(e,LIE_INVALID,"incompatible MTP controller framing");
    lie_kvc_qwen_mtp_controller c={0};
    for(unsigned i=0;i<LIE_KVC_QWEN_MTP_DEPTHS;++i){uint32_t x=kvc_u32(p+24+4*i),y=kvc_u32(p+52+4*i);
        memcpy(&c.successes[i],&x,4);memcpy(&c.failures[i],&y,4);
    }
    c.retry_tokens=kvc_u32(p+80);c.probe_depth=kvc_u32(p+84);c.explored_depth=kvc_u32(p+88);
    c.probe_delay=kvc_u32(p+92);c.failed_depths=kvc_u32(p+96);
    if(!controller_valid(&c,l->model_data[4]))return kvc_fail(e,LIE_INVALID,"invalid MTP restored controller");
    *out=c;return LIE_OK;
}
lie_status lie_kvc_qwen_state_check(const lie_kvc_qwen_geometry *g,const lie_state_layout *l,
                                    uint32_t eos,lie_kvc_span src,const lie_kvc_limits *limits,lie_error *e){
    if(!g||!limits||eos>=g->vocab)return kvc_fail(e,LIE_INVALID,"invalid KVC EOS binding");
    if(src.bytes>limits->memory_bytes)return kvc_fail(e,LIE_RESOURCE_LIMIT,"KVC restore budget exceeded");
    lie_kvc_qwen_layout w;lie_status rc=expected(g,l,src.bytes,&w,e);if(rc!=LIE_OK)return rc;
    uint64_t base,aux;if(!src.data||!lie_state_kvc_parts(l,&base,&aux))return kvc_fail(e,LIE_INVALID,"missing KVC state payload");
    lie_kvc_qwen_layout parsed;rc=lie_kvc_qwen_decode((lie_kvc_span){src.data,(size_t)base},g,limits,&parsed,e);if(rc!=LIE_OK)return rc;
    if(parsed.frontier.tokens!=l->token_count||parsed.frontier.context_tokens!=l->context_tokens||
       parsed.frontier.prefill_tokens!=l->prefill_chunk||parsed.frontier.graph_capacity!=l->model_data[0]||
       parsed.frontier.mtp_tokens!=l->model_data[1]||!parsed.text_positions)return kvc_fail(e,LIE_INVALID,"KVC frontier differs from binding");
    const lie_state_section *t=find(&w,LIE_STATE_TOKENS),*h=find(&w,LIE_STATE_NGRAM);
    for(unsigned i=0;i<8;++i){uint32_t want=i<l->token_count?kvc_u32(src.data+t->offset+4ull*(l->token_count-1-i)):eos;
        if(kvc_u32(src.data+h->offset+4*i)!=want)return kvc_fail(e,LIE_INVALID,"KVC ngram history differs from physical tokens");}
    if(aux){lie_kvc_qwen_mtp_controller c;return lie_kvc_qwen_mtp_state_controller(l,src,&c,e);}
    return LIE_OK;
}
