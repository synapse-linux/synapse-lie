/* SPDX-License-Identifier: MIT */
#include "lie/state.h"
#include "state_internal.h"
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static lie_status fail(lie_error *e, lie_status rc, const char *message) {
    if(e)snprintf(e->message,sizeof(e->message),"%s",message);
    return rc;
}
static uint64_t element_bytes(uint32_t dtype) {
    switch(dtype){case LIE_STATE_U8:return 1;case LIE_STATE_F16:return 2;
        case LIE_STATE_I32:case LIE_STATE_F32:return 4;default:return 0;}
}
static int section_size(const lie_state_section *s,uint64_t *bytes) {
    uint64_t n=element_bytes(s->dtype);if(!n||!s->role||!s->rank||s->rank>LIE_STATE_MAX_RANK)return 0;
    for(unsigned i=0;i<LIE_STATE_MAX_RANK;++i){
        if(i<s->rank){if(!s->shape[i]||s->shape[i]>UINT64_MAX/n)return 0;n*=s->shape[i];}
        else if(s->shape[i])return 0;
    }
    *bytes=n;return 1;
}
int lie_state_add(lie_state_layout *l,uint32_t role,uint32_t layer,lie_state_dtype dtype,
                  uint32_t rank,const uint64_t *shape) {
    if(!l||!shape||!rank||rank>LIE_STATE_MAX_RANK||l->section_count>=LIE_STATE_MAX_SECTIONS)return 0;
    lie_state_section s={.role=role,.layer=layer,.dtype=dtype,.rank=rank};
    memcpy(s.shape,shape,rank*sizeof(*shape));if(!section_size(&s,&s.bytes))return 0;
    if(l->section_count){const lie_state_section *last=&l->sections[l->section_count-1];
        if(last->offset>UINT64_MAX-last->bytes||last->offset+last->bytes>UINT64_MAX-7)return 0;
        s.offset=(last->offset+last->bytes+7)&~UINT64_C(7);
    }
    if(s.bytes>UINT64_MAX-s.offset)return 0;
    l->sections[l->section_count++]=s;return 1;
}
int lie_state_validate(const lie_state_layout *l,uint64_t *bytes) {
    if(!l||!bytes||l->abi_version!=LIE_STATE_ABI||!l->representation_version||!l->domain||
       !l->token_count||l->token_count>l->context_tokens||!l->prefill_chunk||
       !l->section_count||l->section_count>LIE_STATE_MAX_SECTIONS)return 0;
    uint64_t end=0;unsigned tokens=0,logits=0;
    for(unsigned i=0;i<l->section_count;++i){const lie_state_section *s=&l->sections[i];uint64_t n;
        if(end>UINT64_MAX-7||!section_size(s,&n)||n!=s->bytes||s->offset!=((end+7)&~UINT64_C(7))||n>UINT64_MAX-s->offset)return 0;
        for(unsigned j=0;j<i;++j)if(s->role==l->sections[j].role&&s->layer==l->sections[j].layer)return 0;
        if(s->role==LIE_STATE_TOKENS){++tokens;if(s->layer||s->dtype!=LIE_STATE_I32||s->rank!=1||s->shape[0]!=l->token_count)return 0;}
        if(s->role==LIE_STATE_LOGITS){++logits;if(s->layer||s->dtype!=LIE_STATE_F32||s->rank!=1)return 0;}
        end=s->offset+n;
    }
    if(tokens!=1||logits!=1||end>SIZE_MAX-sizeof(lie_state))return 0;
    *bytes=end;return 1;
}
int lie_state_layout_equal(const lie_state_layout *a,const lie_state_layout *b) {
    if(!a||!b||a->section_count>LIE_STATE_MAX_SECTIONS||b->section_count>LIE_STATE_MAX_SECTIONS)return false;
    if(a->abi_version!=b->abi_version||a->representation_version!=b->representation_version||
       a->token_count!=b->token_count||a->context_tokens!=b->context_tokens||a->prefill_chunk!=b->prefill_chunk||
       a->domain!=b->domain||a->section_count!=b->section_count||memcmp(a->model_data,b->model_data,sizeof(a->model_data)))return false;
    for(unsigned i=0;i<a->section_count;++i){const lie_state_section *s=&a->sections[i],*t=&b->sections[i];
        if(s->role!=t->role||s->layer!=t->layer||s->dtype!=t->dtype||s->rank!=t->rank||s->bytes!=t->bytes||s->offset!=t->offset||memcmp(s->shape,t->shape,sizeof(s->shape)))return false;}
    return true;
}
lie_status lie_state_plan(lie_sequence *s,lie_state_layout *l,uint64_t *bytes,lie_error *e) {
    if(!s||!l||!bytes)return fail(e,LIE_INVALID,"invalid state plan");
    memset(l,0,sizeof(*l));*bytes=0;
    lie_status rc=lie_sequence_state_describe(s,NULL,l,e);if(rc!=LIE_OK)return rc;
    if(!lie_state_validate(l,bytes))return fail(e,LIE_BACKEND_FAILED,"invalid provider state layout");
    *bytes+=sizeof(lie_state);return LIE_OK;
}
lie_status lie_state_capture(lie_sequence *s,const lie_state_layout *l,uint64_t budget,lie_state **out,lie_error *e) {
    uint64_t bytes=0;if(!s||!out||*out||!lie_state_validate(l,&bytes))return fail(e,LIE_INVALID,"invalid capture plan");
    if(bytes+sizeof(lie_state)>budget)return fail(e,LIE_RESOURCE_LIMIT,"prefix cache budget exceeded");
    lie_state_layout current;uint64_t retained;
    lie_status rc=lie_state_plan(s,&current,&retained,e);if(rc!=LIE_OK)return rc;
    if(!lie_state_layout_equal(l,&current))return fail(e,LIE_INVALID,"capture frontier changed");
    lie_state *p=lie_state_allocate(&current,budget);if(!p)return fail(e,LIE_RESOURCE_LIMIT,"prefix cache allocation failed");
    /* Only padding is cleared; touching the whole tensor payload here would
     * add a second multi-GiB memory pass before the provider's completed copy. */
    uint64_t end=0;
    for(unsigned i=0;i<l->section_count;++i){const lie_state_section *part=&l->sections[i];
        if(part->offset>end)memset(p->payload+end,0,(size_t)(part->offset-end));
        end=part->offset+part->bytes;
    }
    rc=lie_sequence_state_read(s,&p->layout,p->payload,(size_t)bytes,e);
    if(rc!=LIE_OK){free(p);return rc;}*out=p;return LIE_OK;
}
lie_status lie_state_restore(lie_sequence *s,const lie_state *p,lie_error *e) {
    uint64_t bytes=0;if(!s||!p||!lie_state_validate(&p->layout,&bytes)||bytes!=p->payload_bytes)return fail(e,LIE_INVALID,"invalid prefix state");
    lie_state_layout expected={0};
    lie_status rc=lie_sequence_state_describe(s,&p->layout,&expected,e);if(rc!=LIE_OK)return rc;
    if(!lie_state_layout_equal(&p->layout,&expected))return fail(e,LIE_INVALID,"incompatible prefix state");
    if(!p->codec)return lie_sequence_state_write(s,&p->layout,p->payload,(size_t)bytes,e);
    void *raw=malloc((size_t)bytes);
    if(!raw)return fail(e,LIE_RESOURCE_LIMIT,"checkpoint expansion allocation failed");
    if(!lie_state_unpack_payload(p,raw,(size_t)bytes)){free(raw);return fail(e,LIE_INVALID,"invalid compressed checkpoint");}
    rc=lie_sequence_state_write(s,&p->layout,raw,(size_t)bytes,e);free(raw);return rc;
}
lie_state *lie_state_allocate(const lie_state_layout *l,uint64_t budget){
    uint64_t bytes=0;
    if(!lie_state_validate(l,&bytes)||bytes+sizeof(lie_state)>budget)return NULL;
    lie_state *p=malloc(sizeof(*p)+(size_t)bytes);
    if(p){p->layout=*l;p->payload_bytes=p->storage_bytes=bytes;p->codec=0;atomic_init(&p->refs,1);}
    return p;
}
void lie_state_retain(lie_state *p){
    assert(p);unsigned before=atomic_fetch_add(&p->refs,1);
    if(!before||before==UINT32_MAX)abort();
}
void lie_state_destroy(lie_state **p){if(p&&*p){if(atomic_fetch_sub(&(*p)->refs,1)==1)free(*p);*p=NULL;}}
uint64_t lie_state_bytes(const lie_state *p){return p?sizeof(*p)+p->storage_bytes:0;}
uint64_t lie_state_expanded_bytes(const lie_state *p){return p?sizeof(*p)+p->payload_bytes:0;}
uint64_t lie_state_restore_workspace(const lie_state *p){return p&&p->codec?p->payload_bytes:0;}
bool lie_state_is_compressed(const lie_state *p){return p&&p->codec;}
const lie_state_layout *lie_state_description(const lie_state *p){return p?&p->layout:NULL;}
const int32_t *lie_state_tokens(const lie_state *p){
    if(p)for(unsigned i=0;i<p->layout.section_count;++i)if(p->layout.sections[i].role==LIE_STATE_TOKENS)
        return (const int32_t *)(p->payload+p->layout.sections[i].offset);
    return NULL;
}
