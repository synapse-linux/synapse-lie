/* SPDX-License-Identifier: MIT */
/* Real C inference dispatch with synthetic outcomes. No GPU/model computation. */
#include "lie/inference.h"
#include "fake_executor.h"
#include <assert.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>
typedef struct {lie_sequence *seq;lie_flow *flow;} peer;
static void *cancel_peer(void *arg) {
    peer *p=arg;fake_barrier_wait();lie_sequence_cancel(p->seq);
    assert(lie_flow_cancel(p->flow)==LIE_FLOW_OK);fake_barrier_release();return NULL;
}
static lie_inference_row row(lie_sequence *s,lie_flow *f,unsigned position) {
    return (lie_inference_row){.sequence=s,.flow=f,.position=position,.context=128,.vocab=2048};
}
static void retire(lie_inference_row *r,bool publish) {
    if(!r->reserved)return;
    if(publish){assert(lie_flow_commit(r->flow,r->reservation.ticket,0,r->outcome.result.emitted,r->outcome.result.stop)==LIE_FLOW_OK);
        lie_flow_event e;assert(lie_flow_next(r->flow,&e)==LIE_FLOW_OK);
        if(e.end==LIE_FLOW_ACTIVE)assert(lie_flow_release(r->flow,e.ticket)==LIE_FLOW_OK);
    }else assert(lie_flow_abort(r->flow,r->reservation.ticket,1)==LIE_FLOW_OK);
}
int main(void) {
    lie_error e={0};lie_model *m=NULL;lie_model_options o={LIE_EXECUTOR_ABI,sizeof(o),128,4};
    assert(lie_backend_open_batch(":fixture:",&o,2,&m,&e)==LIE_OK);
    lie_sequence *seq[2]={0};lie_flow *f[2]={0};lie_flow_options fo={1,8,4096};
    int32_t ids[]={1,10,10,10};
    for(unsigned i=0;i<2;++i){assert(lie_sequence_create(m,&seq[i],&e)==LIE_OK);assert(lie_sequence_prefill(seq[i],ids,4,&e)==LIE_OK);assert(lie_flow_create(&fo,&f[i])==LIE_FLOW_OK);}
    fake_calls_reset();lie_inference_row rows[]={row(seq[0],f[0],4),row(seq[1],f[1],4)};lie_inference_batch b;
    assert(lie_inference_prepare(rows,2,2,&b,&e)==LIE_OK&&b.selected==0);
    assert(lie_inference_run(&b,&e)==LIE_OK&&!fake_calls_snapshot().decode);
    assert(lie_flow_request(f[1],1)==LIE_FLOW_OK);
    assert(lie_inference_prepare(rows,2,2,&b,&e)==LIE_OK&&b.selected==1&&rows[0].blocked);
    assert(lie_inference_run(&b,&e)==LIE_OK&&fake_calls_snapshot().decode==1&&!fake_calls_snapshot().batch);
    retire(&rows[1],true);rows[1].position=5;
    for(unsigned i=0;i<2;++i)assert(lie_flow_request(f[i],1)==LIE_FLOW_OK);
    /* Different positions are independent; one cancellation must not suppress
     * the completed peer or release either in-flight reservation too early. */
    fake_barrier_arm();peer cancelled={seq[0],f[0]};pthread_t thread;
    assert(!pthread_create(&thread,NULL,cancel_peer,&cancelled));
    assert(lie_inference_prepare(rows,2,2,&b,&e)==LIE_OK&&b.selected==2);
    assert(lie_inference_run(&b,&e)==LIE_OK);assert(!pthread_join(thread,NULL));
    assert(rows[0].outcome.status==LIE_CANCELLED&&rows[1].outcome.status==LIE_OK&&rows[1].outcome.result.position==6);
    assert(fake_calls_snapshot().batch==1);retire(&rows[0],false);retire(&rows[1],true);
    for(unsigned i=0;i<2;++i){assert(lie_sequence_close(&seq[i],&e)==LIE_OK);(void)lie_flow_cancel(f[i]);assert(lie_flow_destroy(&f[i])==LIE_FLOW_OK);}
    /* A malformed completed row invalidates the entire dispatch before publish. */
    const int modes[]={1,20};
    for(unsigned i=0;i<2;++i){ids[0]=modes[i];assert(lie_sequence_create(m,&seq[i],&e)==LIE_OK);assert(lie_sequence_prefill(seq[i],ids,4,&e)==LIE_OK);assert(lie_flow_create(&fo,&f[i])==LIE_FLOW_OK);assert(lie_flow_request(f[i],1)==LIE_FLOW_OK);rows[i]=row(seq[i],f[i],4);}
    lie_inference_row duplicate[]={rows[0],rows[0]};
    assert(lie_inference_prepare(duplicate,2,2,&b,&e)==LIE_INVALID);
    lie_flow_state state;assert(lie_flow_snapshot(f[0],&state)==LIE_FLOW_OK&&state.demand==1&&!state.in_flight);
    assert(lie_inference_prepare(rows,2,2,&b,&e)==LIE_OK&&b.selected==2);
    assert(lie_inference_run(&b,&e)==LIE_BACKEND_FAILED&&!strcmp(e.message,"invalid_decode_frontier"));
    for(unsigned i=0;i<2;++i){assert(rows[i].outcome.status==LIE_BACKEND_FAILED&&!rows[i].outcome.result.emitted);retire(&rows[i],false);assert(lie_sequence_close(&seq[i],&e)==LIE_OK);assert(lie_flow_destroy(&f[i])==LIE_FLOW_OK);}
    assert(lie_model_close(&m,&e)==LIE_OK);
    puts("Reactive inference credits, single/batch dispatch, cancellation, heterogeneous positions and fail-closed outputs: PASS (NOT-INFERENCE)");
}
