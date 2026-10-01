/* SPDX-License-Identifier: MIT */
#include "lie/inference.h"
#include <stdio.h>
#include <string.h>
static lie_status failure(lie_error *e,const char *text) {
    if(e)snprintf(e->message,sizeof(e->message),"%s",text);
    return LIE_BACKEND_FAILED;
}
lie_status lie_inference_prepare(lie_inference_row *rows,size_t n,unsigned width,
                                 lie_inference_batch *batch,lie_error *e) {
    if(!rows||!batch||n>LIE_DECODE_MAX_ROWS||!width||width>LIE_DECODE_MAX_ROWS)return LIE_INVALID;
    *batch=(lie_inference_batch){rows,n,0};
    for(size_t i=0;i<n;++i){
        if(!rows[i].sequence||!rows[i].flow||!rows[i].vocab||rows[i].position>=rows[i].context)return LIE_INVALID;
        for(size_t j=0;j<i;++j)if(rows[i].sequence==rows[j].sequence||rows[i].flow==rows[j].flow)return LIE_INVALID;
        rows[i].selected=rows[i].reserved=rows[i].blocked=false;
        rows[i].outcome=(lie_decode_outcome){.status=LIE_OK};
    }
    for(size_t i=0;i<n&&batch->selected<width;++i){
        lie_inference_row *r=&rows[i];
        lie_flow_status f=lie_flow_reserve(r->flow,1,&r->reservation);
        if(f==LIE_FLOW_WOULD_BLOCK){r->blocked=true;continue;}
        if(f==LIE_FLOW_CLOSED){r->outcome.status=LIE_CANCELLED;continue;}
        if(f!=LIE_FLOW_OK)return failure(e,"invalid inference credit state");
        r->reserved=true;
        f=lie_flow_begin(r->flow,r->reservation.ticket);
        if(f==LIE_FLOW_CLOSED){r->outcome.status=LIE_CANCELLED;continue;}
        if(f!=LIE_FLOW_OK)return failure(e,"invalid inference reservation");
        r->selected=true;++batch->selected;
    }
    return LIE_OK;
}
lie_status lie_inference_run(lie_inference_batch *batch,lie_error *e) {
    if(!batch||batch->count>LIE_DECODE_MAX_ROWS||batch->selected>LIE_DECODE_MAX_ROWS)return LIE_INVALID;
    lie_sequence *seq[LIE_DECODE_MAX_ROWS];lie_decode_outcome out[LIE_DECODE_MAX_ROWS];
    size_t n=0;
    for(size_t i=0;i<batch->count;++i)if(batch->rows[i].selected)seq[n++]=batch->rows[i].sequence;
    if(n!=batch->selected)return LIE_INVALID;
    if(!n)return LIE_OK;
    memset(out,0,sizeof(out));lie_status rc;
    if(n==1){out[0].status=lie_sequence_decode(seq[0],&out[0].result,e);rc=out[0].status==LIE_CANCELLED?LIE_OK:out[0].status;}
    else rc=lie_sequences_decode(seq,n,out,e);
    size_t k=0;
    for(size_t i=0;i<batch->count;++i)if(batch->rows[i].selected){
        lie_inference_row *r=&batch->rows[i];r->outcome=out[k++];
        const lie_decode_result *d=&r->outcome.result;
        if(r->outcome.status==LIE_OK&&(d->emitted>1||d->stop>1||(!d->emitted&&!d->stop)||
           d->position!=(uint64_t)r->position+d->emitted||d->position>r->context||
           (d->emitted&&(d->token<0||(uint32_t)d->token>=r->vocab))))rc=failure(e,"invalid_decode_frontier");
        if(r->outcome.status!=LIE_OK&&r->outcome.status!=LIE_CANCELLED)rc=LIE_BACKEND_FAILED;
    }
    if(rc!=LIE_OK){
        if(e&&!e->message[0])failure(e,"executor_batch_failed");
        for(size_t i=0;i<batch->count;++i)if(batch->rows[i].selected)
            batch->rows[i].outcome=(lie_decode_outcome){.status=LIE_BACKEND_FAILED};
        return LIE_BACKEND_FAILED;
    }
    return LIE_OK;
}
