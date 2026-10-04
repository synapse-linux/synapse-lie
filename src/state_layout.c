/* SPDX-License-Identifier: MIT */
#include "lie/state.h"
#include "state_internal.h"
#include <string.h>
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
    if(!l||!shape||!rank||rank>LIE_STATE_MAX_RANK||l->section_count>=LIE_STATE_MAX_SECTIONS||l->format>LIE_STATE_KVC_AUX)return 0;
    lie_state_section s={.role=role,.layer=layer,.dtype=dtype,.rank=rank};
    memcpy(s.shape,shape,rank*sizeof(*shape));if(!section_size(&s,&s.bytes))return 0;
    if(l->section_count){const lie_state_section *last=&l->sections[l->section_count-1];
        if(last->offset>UINT64_MAX-last->bytes)return 0;
        s.offset=last->offset+last->bytes;
        if(l->format==LIE_STATE_ALIGNED){if(s.offset>UINT64_MAX-7)return 0;s.offset=(s.offset+7)&~UINT64_C(7);}
    }
    if(s.bytes>UINT64_MAX-s.offset)return 0;
    l->sections[l->section_count++]=s;return 1;
}
int lie_state_validate(const lie_state_layout *l,uint64_t *bytes) {
    if(!l||!bytes||l->abi_version!=LIE_STATE_ABI||!l->representation_version||!l->domain||
       !l->token_count||l->token_count>l->context_tokens||!l->prefill_chunk||
       !l->section_count||l->section_count>LIE_STATE_MAX_SECTIONS||l->format>LIE_STATE_KVC_AUX)return 0;
    if(l->format!=LIE_STATE_ALIGNED){
        if(l->model_id>255||(l->quant_bits!=2&&l->quant_bits!=4&&l->quant_bits!=5&&l->quant_bits!=6&&l->quant_bits!=8))return 0;
    }else if(l->model_id||l->quant_bits)return 0;
    uint64_t end=0;unsigned tokens=0,logits=0,aux=0;
    for(unsigned i=0;i<l->section_count;++i){const lie_state_section *s=&l->sections[i];uint64_t n;
        uint64_t next=end;
        if(l->format==LIE_STATE_ALIGNED){if(end>UINT64_MAX-7)return 0;next=(end+7)&~UINT64_C(7);}
        if(!section_size(s,&n)||n!=s->bytes||s->offset!=next||n>UINT64_MAX-s->offset)return 0;
        for(unsigned j=0;j<i;++j)if(s->role==l->sections[j].role&&s->layer==l->sections[j].layer)return 0;
        if(s->role==LIE_STATE_AUXILIARY){
            if(l->format!=LIE_STATE_KVC_AUX||aux++||!end||s->layer||s->dtype!=LIE_STATE_U8||s->rank!=1)return 0;
        }
        if(aux&&(s->role==LIE_STATE_TOKENS||s->role==LIE_STATE_LOGITS))return 0;
        if(s->role==LIE_STATE_CACHE_SCOPE&&(s->layer||s->dtype!=LIE_STATE_U8||s->rank!=1||s->bytes!=32||
           (l->format!=LIE_STATE_ALIGNED&&!aux)))return 0;
        if(s->role==LIE_STATE_TOKENS){++tokens;if(s->layer||s->dtype!=LIE_STATE_I32||s->rank!=1||s->shape[0]!=l->token_count||s->offset%4)return 0;}
        if(s->role==LIE_STATE_LOGITS){++logits;if(s->layer||s->dtype!=LIE_STATE_F32||s->rank!=1)return 0;}
        end=s->offset+n;
    }
    if(tokens!=1||logits!=1||aux!=(l->format==LIE_STATE_KVC_AUX)||end>SIZE_MAX-sizeof(lie_state))return 0;
    *bytes=end;return 1;
}
int lie_state_kvc_parts(const lie_state_layout *l,uint64_t *model,uint64_t *aux){
    uint64_t total;if(!model||!aux||!lie_state_validate(l,&total)||l->format==LIE_STATE_ALIGNED)return 0;
    *model=total;*aux=0;
    for(unsigned i=0;i<l->section_count;++i)if(l->sections[i].role==LIE_STATE_AUXILIARY){
        *model=l->sections[i].offset;*aux=total-*model;break;
    }
    return 1;
}
int lie_state_layout_equal(const lie_state_layout *a,const lie_state_layout *b) {
    if(!a||!b||a->section_count>LIE_STATE_MAX_SECTIONS||b->section_count>LIE_STATE_MAX_SECTIONS)return false;
    if(a->abi_version!=b->abi_version||a->representation_version!=b->representation_version||
       a->token_count!=b->token_count||a->context_tokens!=b->context_tokens||a->prefill_chunk!=b->prefill_chunk||
       a->domain!=b->domain||a->format!=b->format||a->model_id!=b->model_id||a->quant_bits!=b->quant_bits||
       a->section_count!=b->section_count||memcmp(a->model_data,b->model_data,sizeof(a->model_data)))return false;
    for(unsigned i=0;i<a->section_count;++i){const lie_state_section *s=&a->sections[i],*t=&b->sections[i];
        if(s->role!=t->role||s->layer!=t->layer||s->dtype!=t->dtype||s->rank!=t->rank||s->bytes!=t->bytes||s->offset!=t->offset||memcmp(s->shape,t->shape,sizeof(s->shape)))return false;}
    return true;
}
