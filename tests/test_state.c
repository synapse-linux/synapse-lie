/* SPDX-License-Identifier: MIT */
/* Structural and synthetic copies only, not numerical inference. */
#include "lie/qwen_state.h"
#include "fake_executor.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

int main(void){
    lie_model_options o={.abi_version=LIE_EXECUTOR_ABI,.struct_bytes=sizeof(o),.context_tokens=128,.prefill_chunk_tokens=4};lie_model *m=NULL,*foreign=NULL;lie_error e={0};
    assert(lie_backend_open(":fixture:",&o,&m,&e)==LIE_OK);
    assert(lie_backend_open(":fixture:",&o,&foreign,&e)==LIE_OK);
    lie_sequence *s=NULL,*a=NULL,*b=NULL;assert(lie_sequence_create(m,&s,&e)==LIE_OK);
    int32_t tokens[]={0,10,11,12};assert(lie_sequence_prefill(s,tokens,4,&e)==LIE_OK);
    lie_state_layout plan;uint64_t bytes=0;assert(lie_state_plan(s,&plan,&bytes,&e)==LIE_OK);
    lie_state *state=NULL;assert(lie_state_capture(s,&plan,bytes-1,&state,&e)==LIE_RESOURCE_LIMIT&&!state);
    assert(!fake_calls_snapshot().capture);
    lie_state_layout malformed=plan;malformed.sections[0].bytes++;
    assert(!lie_state_validate(&malformed,&bytes));
    malformed=plan;malformed.sections[1]=plan.sections[0];assert(!lie_state_validate(&malformed,&bytes));
    malformed=plan;malformed.sections[2].shape[0]=UINT64_MAX;assert(!lie_state_validate(&malformed,&bytes));
    malformed=plan;malformed.sections[1].offset++;assert(!lie_state_validate(&malformed,&bytes));
    malformed=plan;malformed.domain=0;assert(!lie_state_validate(&malformed,&bytes));
    malformed=plan;malformed.section_count=LIE_STATE_MAX_SECTIONS+1;assert(!lie_state_layout_equal(&plan,&malformed));
    assert(lie_state_capture(s,&plan,UINT64_MAX,&state,&e)==LIE_OK);
    assert(lie_state_bytes(state)>sizeof(plan)&&!memcmp(lie_state_tokens(state),tokens,sizeof(tokens)));
    assert(lie_sequence_close(&s,&e)==LIE_OK); /* State outlives its source sequence. */
    assert(lie_sequence_create(foreign,&b,&e)==LIE_OK);
    assert(lie_state_restore(b,state,&e)==LIE_INVALID&&!fake_calls_snapshot().restore);
    assert(lie_sequence_close(&b,&e)==LIE_OK);
    assert(lie_sequence_create(m,&a,&e)==LIE_OK&&lie_sequence_create(m,&b,&e)==LIE_OK);
    assert(lie_state_restore(a,state,&e)==LIE_OK&&lie_state_restore(b,state,&e)==LIE_OK);
    lie_decode_result x,y;assert(lie_sequence_decode(a,&x,&e)==LIE_OK);
    assert(lie_sequence_decode(a,&x,&e)==LIE_OK&&x.token==1);
    assert(lie_sequence_decode(b,&y,&e)==LIE_OK&&y.token==0&&y.position==5);
    assert(lie_state_restore(a,state,&e)==LIE_INVALID); /* Only pristine recipients. */
    assert(lie_sequence_close(&a,&e)==LIE_OK&&lie_sequence_close(&b,&e)==LIE_OK);
    lie_state_destroy(&state);assert(!state);lie_state_destroy(&state);
    assert(lie_model_close(&m,&e)==LIE_OK&&lie_model_close(&foreign,&e)==LIE_OK);

    lie_qwen_state_geometry g={.layers=4,.attention_interval=2,.conv_rows=3,.conv_channels=8,
        .value_heads=2,.head_dim=4,.kv_width=8,.index_width=4,.compress_ratio=4,
        .ple_rows=2,.hidden_width=8,.ngram_count=3,.vocab=32,.index_capacity=8};
    lie_state_layout q={.domain=1,.token_count=11,.context_tokens=128,.prefill_chunk=4,.model_data={1}};
    assert(lie_qwen_state_layout(&g,&q)&&q.section_count==16&&lie_state_validate(&q,&bytes));
    unsigned index=0,keys=0;
    for(unsigned k=0;k<q.section_count;++k){const lie_state_section *part=&q.sections[k];
        if(part->role==LIE_STATE_INDEX){assert(part->shape[0]==7&&part->shape[1]==4);++index;}
        if(part->role==LIE_STATE_BLOCK_KEYS){assert(part->shape[0]==1&&part->dtype==LIE_STATE_F16);++keys;}}
    assert(index==2&&keys==2);
    q.model_data[0]=3;assert(!lie_qwen_state_layout(&g,&q)); /* Future pooled frontier. */
    q.model_data[0]=0;assert(!lie_qwen_state_layout(&g,&q)); /* Ring capacity. */
    q.token_count=8;q.model_data[0]=2;assert(lie_qwen_state_layout(&g,&q));
    for(unsigned k=0;k<q.section_count;++k)assert(q.sections[k].role!=LIE_STATE_INDEX);
    q.model_data[1]=1;assert(!lie_qwen_state_layout(&g,&q));
    puts("C17 typed state bounds, independent clones, domains and model layout: PASS (NOT-INFERENCE)");return 0;
}
