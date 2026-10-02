/* SPDX-License-Identifier: MIT */
#include "lie/kvc_qwen_map.h"
#include "../kvc_internal.h"
#include <float.h>
#include <stdlib.h>
#include <string.h>
static const lie_state_section *find(const lie_state_section *s,unsigned count,uint32_t role,uint32_t layer) {
    for(unsigned i=0;i<count;++i)if(s[i].role==role&&s[i].layer==layer)return &s[i];
    return NULL;
}
static lie_kvc_span part(lie_kvc_span bytes,const lie_state_section *s) {
    return s?(lie_kvc_span){bytes.data+(size_t)s->offset,(size_t)s->bytes}:(lie_kvc_span){0};
}
static int separate(const void *a,size_t an,const void *b,size_t bn) {
    uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;
    return an<=UINTPTR_MAX-x&&bn<=UINTPTR_MAX-y&&(!(an&&bn)||x+an<=y||y+bn<=x);
}
static lie_status move_or_compare(unsigned char *dst,const unsigned char *src,size_t n,
                                  int compare,const lie_kvc_limits *limits,lie_error *e) {
    while(n){
        if(kvc_cancelled(limits))return kvc_fail(e,LIE_CANCELLED,"Qwen mapping cancelled");
        size_t chunk=n>1048576u?1048576u:n;
        if(compare){if(memcmp(dst,src,chunk))return kvc_fail(e,LIE_INVALID,"Qwen auxiliary history differs from native state");}
        else memcpy(dst,src,chunk);
        dst+=chunk;src+=chunk;n-=chunk;
    }
    return LIE_OK;
}
static lie_status native_plan(const lie_kvc_qwen_geometry *w,const lie_kvc_qwen_mapping *m,
                              const lie_kvc_qwen_frontier *f,lie_state_layout *out,size_t *bytes,lie_error *e) {
    uint32_t endian=1;
    if(*(const unsigned char *)&endian!=1||sizeof(float)!=4||FLT_RADIX!=2||FLT_MANT_DIG!=24||FLT_MAX_EXP!=128)
        return kvc_fail(e,LIE_UNSUPPORTED,"Qwen native mapping requires little-endian binary32");
    if(!w||!m||!f)return kvc_fail(e,LIE_INVALID,"missing Qwen mapping geometry");
    const lie_qwen_state_geometry *g=&m->native;
    if(g->layers!=w->trunk_layers||g->attention_interval!=w->attention_interval||
       g->conv_rows!=w->conv_rows||g->conv_channels!=w->conv_channels||g->value_heads!=w->value_heads||
       g->head_dim!=w->linear_head_dim||(uint64_t)g->kv_width!=(uint64_t)w->attention_heads_kv*w->attention_head_dim||
       g->index_width!=w->index_dim||g->ple_rows!=w->ple_rows||g->hidden_width!=w->hidden_width||
       g->vocab!=w->vocab||g->compress_ratio!=4||!g->ngram_count||g->ngram_count>8||
       !m->indexer_top_k||m->eos_token>=g->vocab)
        return kvc_fail(e,LIE_INVALID,"Qwen wire and native geometry disagree");
    if(f->mtp_tokens||f->mrope_delta)return kvc_fail(e,LIE_UNSUPPORTED,"Qwen mapping supports text AR frontiers only");
    /* A temporary domain validates geometry only. It is never published or
     * passed to a provider: imported data deliberately has no live identity. */
    lie_state_layout l={.domain=1,.token_count=f->tokens,.context_tokens=f->context_tokens,.prefill_chunk=f->prefill_tokens};
    l.model_data[0]=f->tokens>m->indexer_top_k?f->tokens/4:0;
    uint64_t n=0;
    if(!lie_qwen_state_layout(g,&l)||!lie_state_validate(&l,&n))
        return kvc_fail(e,LIE_INVALID,"Qwen native layout or index capacity is invalid");
    l.domain=0;*out=l;*bytes=(size_t)n;return LIE_OK;
}
static lie_status history(lie_kvc_span tokens,lie_kvc_span previous,uint32_t slots,
                          uint32_t eos,int native,lie_error *e) {
    size_t rows=tokens.bytes/4;
    if(previous.bytes!=(size_t)slots*4||!previous.data)return kvc_fail(e,LIE_INVALID,"missing Qwen ngram history");
    for(uint32_t i=0;i<slots;++i){
        uint32_t expected=i<rows?kvc_u32(tokens.data+4*(rows-1-i)):(native?UINT32_MAX:eos);
        if(kvc_u32(previous.data+4*i)!=expected)return kvc_fail(e,LIE_INVALID,"Qwen ngram history disagrees with tokens");
    }
    return LIE_OK;
}
lie_status lie_kvc_qwen_project(const lie_kvc_view *v,const lie_kvc_qwen_geometry *g,
                               const lie_kvc_qwen_mapping *m,const lie_kvc_limits *limits,
                               lie_state_layout *out,void *raw,size_t capacity,size_t *required,lie_error *e) {
    if(!out||!required||!limits)return kvc_fail(e,LIE_INVALID,"invalid Qwen projection request");
    lie_kvc_qwen_layout wire;lie_status rc=lie_kvc_qwen_decode_record(v,g,limits,&wire,e);if(rc!=LIE_OK)return rc;
    if(!wire.text_positions)return kvc_fail(e,LIE_UNSUPPORTED,"Qwen position-adjusted state requires a vision mapping");
    lie_state_layout native;size_t bytes;
    rc=native_plan(g,m,&wire.frontier,&native,&bytes,e);if(rc!=LIE_OK)return rc;
    lie_kvc_span tokens=part(v->payload,find(wire.sections,wire.section_count,LIE_STATE_TOKENS,0));
    lie_kvc_span prev=part(v->payload,find(wire.sections,wire.section_count,LIE_STATE_NGRAM,0));
    rc=history(tokens,prev,8,m->eos_token,0,e);if(rc!=LIE_OK)return rc;
    *required=bytes;
    if(bytes>limits->memory_bytes)return kvc_fail(e,LIE_RESOURCE_LIMIT,"Qwen projection output budget exceeded");
    if(kvc_cancelled(limits))return kvc_fail(e,LIE_CANCELLED,"Qwen mapping cancelled");
    if(!raw||capacity<bytes)return kvc_fail(e,LIE_BUFFER_SMALL,"Qwen projection buffer too small");
    if(!separate(raw,bytes,v->payload.data,v->payload.bytes)||!separate(raw,bytes,out,sizeof(*out))||
       !separate(out,sizeof(*out),v->payload.data,v->payload.bytes)||
       !separate(raw,bytes,m,sizeof(*m))||!separate(raw,bytes,g,sizeof(*g))||
       !separate(raw,bytes,v,sizeof(*v))||!separate(raw,bytes,limits,sizeof(*limits)))
        return kvc_fail(e,LIE_INVALID,"overlapping Qwen projection output");
    unsigned char *dst=raw;size_t end=0;
    for(unsigned i=0;i<native.section_count;++i){const lie_state_section *d=&native.sections[i];
        if(kvc_cancelled(limits))return kvc_fail(e,LIE_CANCELLED,"Qwen mapping cancelled");
        if(d->offset>end)memset(dst+end,0,(size_t)d->offset-end);
        end=(size_t)(d->offset+d->bytes);
        const lie_state_section *s=find(wire.sections,wire.section_count,d->role,d->layer);
        if(d->role==LIE_STATE_NGRAM){
            for(unsigned j=0;j<m->native.ngram_count;++j)
                kvc_put32(dst+(size_t)d->offset+4*j,j<native.token_count?kvc_u32(prev.data+4*j):UINT32_MAX);
            continue;
        }
        size_t skip=d->role==LIE_STATE_INDEX?(size_t)native.model_data[0]*4*m->native.index_width*4:0;
        if(!s||skip>s->bytes||d->bytes>s->bytes-skip)return kvc_fail(e,LIE_INVALID,"incomplete Qwen source component");
        rc=move_or_compare(dst+(size_t)d->offset,v->payload.data+(size_t)s->offset+skip,(size_t)d->bytes,0,limits,e);
        if(rc!=LIE_OK)return rc;
    }
    if(kvc_cancelled(limits))return kvc_fail(e,LIE_CANCELLED,"Qwen mapping cancelled");
    *out=native;return LIE_OK;
}
lie_status lie_kvc_qwen_export(const lie_state_layout *native,lie_kvc_span source,
                              const lie_kvc_qwen_geometry *g,const lie_kvc_qwen_frontier *f,
                              const lie_kvc_qwen_mapping *m,const lie_kvc_qwen_extra *extra,size_t count,
                              const lie_kvc_limits *limits,void *raw,size_t capacity,size_t *required,lie_error *e) {
    if(!native||!limits||!required||!source.data||(count&&!extra)||count>LIE_STATE_MAX_SECTIONS)
        return kvc_fail(e,LIE_INVALID,"invalid Qwen export request");
    lie_kvc_qwen_layout wire;lie_status rc=lie_kvc_qwen_plan(g,f,&wire,e);if(rc!=LIE_OK)return rc;
    lie_state_layout expected;size_t bytes;
    rc=native_plan(g,m,f,&expected,&bytes,e);if(rc!=LIE_OK)return rc;
    expected.domain=native->domain;
    if(!lie_state_layout_equal(native,&expected)||source.bytes!=bytes)
        return kvc_fail(e,LIE_INVALID,"Qwen export native layout mismatch");
    *required=(size_t)wire.bytes;
    uint64_t scratch=16ull*f->tokens;
    if(wire.bytes>limits->memory_bytes||scratch>SIZE_MAX||scratch>limits->memory_bytes-wire.bytes)
        return kvc_fail(e,LIE_RESOURCE_LIMIT,"Qwen export output and scratch budget exceeded");
    if(kvc_cancelled(limits))return kvc_fail(e,LIE_CANCELLED,"Qwen mapping cancelled");
    lie_kvc_span parts[LIE_STATE_MAX_SECTIONS]={0};unsigned char ngram[32];
    lie_kvc_span tokens=part(source,find(native->sections,native->section_count,LIE_STATE_TOKENS,0));
    lie_kvc_span prev=part(source,find(native->sections,native->section_count,LIE_STATE_NGRAM,0));
    rc=history(tokens,prev,m->native.ngram_count,m->eos_token,1,e);if(rc!=LIE_OK)return rc;
    for(unsigned j=0;j<8;++j)kvc_put32(ngram+4*j,j<f->tokens?kvc_u32(tokens.data+4*(f->tokens-1-j)):m->eos_token);
    for(size_t i=0;i<count;++i){const lie_kvc_qwen_extra *x=&extra[i];
        const lie_state_section *w=find(wire.sections,wire.section_count,x->role,x->layer);
        if((x->role!=LIE_STATE_INDEX&&x->role!=LIE_STATE_BLOCK_KEYS)||!w||!x->span.data||x->span.bytes!=w->bytes)
            return kvc_fail(e,LIE_INVALID,"invalid Qwen export auxiliary component");
        for(size_t j=0;j<i;++j)if(extra[j].role==x->role&&extra[j].layer==x->layer)
            return kvc_fail(e,LIE_INVALID,"duplicate Qwen export auxiliary component");
    }
    for(unsigned i=0;i<wire.section_count;++i){const lie_state_section *w=&wire.sections[i];
        if(w->role==LIE_KVC_QWEN_POSITIONS)continue;
        if(w->role==LIE_STATE_NGRAM){parts[i]=(lie_kvc_span){ngram,sizeof(ngram)};continue;}
        const lie_state_section *n=find(native->sections,native->section_count,w->role,w->layer);
        lie_kvc_span available=part(source,n),aux={0};
        for(size_t j=0;j<count;++j)if(extra[j].role==w->role&&extra[j].layer==w->layer)aux=extra[j].span;
        if(aux.data){
            size_t skip=w->role==LIE_STATE_INDEX?(size_t)native->model_data[0]*4*m->native.index_width*4:0;
            if(skip>aux.bytes||available.bytes>aux.bytes-skip)return kvc_fail(e,LIE_INVALID,"Qwen auxiliary range mismatch");
            rc=move_or_compare((unsigned char *)available.data,aux.data+skip,available.bytes,1,limits,e);if(rc!=LIE_OK)return rc;
            parts[i]=aux;
        }else if(available.bytes==w->bytes)parts[i]=available;
        else return kvc_fail(e,LIE_UNSUPPORTED,"Qwen export requires complete index history and pooled keys");
    }
    if(!raw||capacity<wire.bytes)return kvc_fail(e,LIE_BUFFER_SMALL,"Qwen export buffer too small");
    if(!separate(raw,(size_t)wire.bytes,source.data,source.bytes)||
       !separate(raw,(size_t)wire.bytes,native,sizeof(*native))||!separate(raw,(size_t)wire.bytes,g,sizeof(*g))||
       !separate(raw,(size_t)wire.bytes,f,sizeof(*f))||!separate(raw,(size_t)wire.bytes,m,sizeof(*m))||
       !separate(raw,(size_t)wire.bytes,limits,sizeof(*limits))||!separate(raw,(size_t)wire.bytes,extra,count*sizeof(*extra)))
        return kvc_fail(e,LIE_INVALID,"overlapping Qwen export output");
    /* Even unused native fields/extra slices may not alias the output. */
    for(size_t i=0;i<count;++i)if(!separate(raw,(size_t)wire.bytes,extra[i].span.data,extra[i].span.bytes))
        return kvc_fail(e,LIE_INVALID,"overlapping Qwen auxiliary output");
    unsigned char *positions=malloc((size_t)scratch);
    if(!positions)return kvc_fail(e,LIE_RESOURCE_LIMIT,"Qwen position scratch allocation failed");
    for(uint32_t i=0;i<f->tokens;++i){
        if(!(i%4096)&&kvc_cancelled(limits)){free(positions);return kvc_fail(e,LIE_CANCELLED,"Qwen mapping cancelled");}
        for(unsigned j=0;j<4;++j)kvc_put32(positions+16*(size_t)i+4*j,j==3?0:i);
    }
    for(unsigned i=0;i<wire.section_count;++i)if(wire.sections[i].role==LIE_KVC_QWEN_POSITIONS)
        parts[i]=(lie_kvc_span){positions,(size_t)scratch};
    rc=lie_kvc_qwen_encode(g,f,parts,wire.section_count,limits,raw,capacity,required,e);
    free(positions);return rc;
}
