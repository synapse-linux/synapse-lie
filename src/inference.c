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
        if(!rows[i].sequence||!rows[i].flow||!rows[i].vocab||rows[i].position>=rows[i].context||rows[i].step_tokens>LIE_MTP_MAX_OUTPUT)return LIE_INVALID;
        for(size_t j=0;j<i;++j)if(rows[i].sequence==rows[j].sequence||rows[i].flow==rows[j].flow)return LIE_INVALID;
        rows[i].selected=rows[i].reserved=rows[i].blocked=false;
        rows[i].outcome=(lie_decode_outcome){.status=LIE_OK};
        rows[i].burst=(lie_mtp_outcome){.status=LIE_OK};
    }
    for(size_t i=0;i<n&&batch->selected<width;++i){
        lie_inference_row *r=&rows[i];
        uint32_t limit=r->step_tokens?r->step_tokens:1;
        if(limit>r->context-r->position)limit=r->context-r->position;
        lie_flow_status f=lie_flow_reserve(r->flow,limit,&r->reservation);
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
    lie_sequence *seq[LIE_DECODE_MAX_ROWS];lie_decode_outcome out[LIE_DECODE_MAX_ROWS]={0};
    lie_mtp_outcome bursts[LIE_DECODE_MAX_ROWS]={0};uint32_t limits[LIE_DECODE_MAX_ROWS]={0};
    size_t n=0;bool mtp=false;
    for(size_t i=0;i<batch->count;++i)if(batch->rows[i].selected){
        lie_inference_row *r=&batch->rows[i];seq[n]=r->sequence;
        limits[n++]=(uint32_t)r->reservation.tokens;mtp|=r->step_tokens>1;
    }
    if(n!=batch->selected)return LIE_INVALID;
    if(!n)return LIE_OK;
    lie_status rc;
    if(mtp)rc=lie_sequences_decode_mtp(seq,limits,n,bursts,e);
    else {
        if(n==1){out[0].status=lie_sequence_decode(seq[0],&out[0].result,e);rc=out[0].status==LIE_CANCELLED?LIE_OK:out[0].status;}
        else rc=lie_sequences_decode(seq,n,out,e);
        for(size_t i=0;i<n;++i){lie_decode_result d=out[i].result;
            bursts[i]=(lie_mtp_outcome){.status=out[i].status,.tokens={d.token},.emitted=d.emitted,.stop=d.stop,.position=d.position};}
    }
    size_t k=0;
    for(size_t i=0;i<batch->count;++i)if(batch->rows[i].selected){
        lie_inference_row *r=&batch->rows[i];r->burst=bursts[k++];
        const lie_mtp_outcome *d=&r->burst;
        if(d->status==LIE_OK){
            if(d->emitted>r->reservation.tokens||d->emitted>LIE_MTP_MAX_OUTPUT||d->stop>1||(!d->emitted&&!d->stop)||
               d->position!=(uint64_t)r->position+d->emitted||d->position>r->context||d->accepted>d->drafted)
                rc=failure(e,"invalid_decode_frontier");
            for(size_t t=0;t<d->emitted&&t<LIE_MTP_MAX_OUTPUT;++t)
                if(d->tokens[t]<0||(uint32_t)d->tokens[t]>=r->vocab)rc=failure(e,"invalid_decode_frontier");
        }else if(d->status!=LIE_CANCELLED)rc=LIE_BACKEND_FAILED;
        r->outcome=(lie_decode_outcome){d->status,{d->emitted?d->tokens[0]:-1,d->emitted,d->stop,d->position}};
    }
    if(rc!=LIE_OK){
        if(e&&!e->message[0])failure(e,"executor_batch_failed");
        for(size_t i=0;i<batch->count;++i)if(batch->rows[i].selected){
            batch->rows[i].outcome=(lie_decode_outcome){.status=LIE_BACKEND_FAILED};
            batch->rows[i].burst=(lie_mtp_outcome){.status=LIE_BACKEND_FAILED};}
        return LIE_BACKEND_FAILED;
    }
    return LIE_OK;
}
