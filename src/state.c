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
uint64_t lie_state_restore_workspace(const lie_state *p){
    if(!p||!p->codec)return 0;
    uint64_t scratch=lie_state_decode_workspace(p->codec);
    return p->payload_bytes>UINT64_MAX-scratch?UINT64_MAX:p->payload_bytes+scratch;
}
bool lie_state_is_compressed(const lie_state *p){return p&&p->codec;}
const lie_state_layout *lie_state_description(const lie_state *p){return p?&p->layout:NULL;}
const int32_t *lie_state_tokens(const lie_state *p){
    if(p)for(unsigned i=0;i<p->layout.section_count;++i)if(p->layout.sections[i].role==LIE_STATE_TOKENS)
        return (const int32_t *)(p->payload+p->layout.sections[i].offset);
    return NULL;
}
