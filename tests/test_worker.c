/* SPDX-License-Identifier: MIT */
#include "lie/worker.h"
#include "fake_executor.h"
#include <assert.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static void pause_short(void) { struct timespec t={0,1000000}; nanosleep(&t,NULL); }
static lie_worker_info wait_state(lie_worker *w, lie_worker_state state) {
    lie_worker_info info={0};
    for (unsigned i=0;i<3000;++i) {
        lie_worker_snapshot(w,&info); if (info.state==state) return info; pause_short();
    }
    assert(!"worker state deadline"); return info;
}
static lie_chat_request request(const char *text, unsigned tokens) {
    lie_chat_request r={.count=1,.max_tokens=tokens};
    r.messages[0]=(lie_chat_message){LIE_CHAT_USER,strdup(text),strlen(text)};
    assert(r.messages[0].content); return r;
}
static lie_job *submit(lie_worker *w, const char *text, unsigned tokens) {
    lie_chat_request r=request(text,tokens); lie_job *job=NULL;
    assert(!lie_worker_submit(w,&r,&job)); assert(!r.count); return job;
}
static lie_flow_event next(lie_job *j) {
    lie_flow_event e;
    for (unsigned i=0;i<3000;++i) {
        lie_flow_status st=lie_flow_next(lie_job_flow(j),&e);
        if (st==LIE_FLOW_OK) return e;
        assert(st==LIE_FLOW_WOULD_BLOCK);
        struct pollfd fd={lie_flow_fd(lie_job_flow(j),LIE_FLOW_OUTPUT_READY),POLLIN,0};
        assert(poll(&fd,1,1)>=0); assert(lie_flow_drain(lie_job_flow(j),LIE_FLOW_OUTPUT_READY)==LIE_FLOW_OK);
    }
    assert(!"output deadline"); return (lie_flow_event){0};
}
static unsigned consume(lie_job *j) {
    unsigned tokens=0;
    for (;;) {
        lie_flow_event e=next(j);
        if (e.end!=LIE_FLOW_ACTIVE) { assert(e.end==LIE_FLOW_COMPLETE); break; }
        assert(e.token_offset==tokens); tokens+=(unsigned)e.tokens;
        assert(lie_flow_release(lie_job_flow(j),e.ticket)==LIE_FLOW_OK);
        (void)lie_flow_request(lie_job_flow(j),e.tokens);
    }
    lie_job_info info; lie_job_snapshot(j,&info);
    assert(info.output_tokens==tokens && (info.finish==LIE_FINISH_STOP || info.finish==LIE_FINISH_LENGTH));
    lie_job_release(j); return tokens;
}
static void stop(lie_worker *w) { lie_worker_stop(w); wait_state(w,LIE_STOPPED); lie_worker_destroy(w); }
int main(void) {
    lie_worker_options opts={":fixture:",1024,2,2,0};
    lie_worker *w=lie_worker_create(&opts); assert(w); wait_state(w,LIE_READY);
    lie_chat_request invalid=request("normal",0); lie_job *none=NULL;
    assert(lie_worker_submit(w,&invalid,&none)==3 && !none && invalid.count==1);
    invalid.max_tokens=LIE_CHAT_MAX_OUTPUT+1; assert(lie_worker_submit(w,&invalid,&none)==3);
    invalid.max_tokens=8; invalid.count=LIE_CHAT_MAX_MESSAGES+1;
    assert(lie_worker_submit(w,&invalid,&none)==3); invalid.count=1; lie_chat_free(&invalid);
    lie_job *jobs[LIE_WORKER_JOBS];
    for (unsigned i=0;i<LIE_WORKER_JOBS;++i) jobs[i]=submit(w,i%2?"LONG-B":"LONG-A",512);
    lie_chat_request extra=request("LONG",512); lie_job *rejected=NULL;
    assert(lie_worker_submit(w,&extra,&rejected)==2 && !rejected && extra.count==1); lie_chat_free(&extra);
    lie_worker_info info={0};
    for (unsigned i=0;i<3000;++i) {
        lie_worker_snapshot(w,&info); if (info.generated_tokens==16 && info.output_blocked==2) break; pause_short();
    }
    assert(info.active==2 && info.queued==6 && info.generated_tokens==16 && info.output_blocked==2);
    assert(info.decode_batches>0 && info.decode_batch_rows>=2*info.decode_batches);
    assert(fake_calls_snapshot().batch>0);
    assert(info.executor_phase==LIE_EXECUTOR_IDLE && info.prefill_started==info.prefill_returned &&
           info.decode_started==info.decode_returned);
    for (unsigned i=0;i<10;++i) pause_short();
    lie_worker_snapshot(w,&info); assert(info.generated_tokens==16); /* no demand, no dispatch */
    lie_flow_event a=next(jobs[0]), b=next(jobs[1]);
    assert(a.bytes==256 && a.data[0]=='A' && b.bytes==256 && b.data[0]=='B');
    assert(lie_flow_release(lie_job_flow(jobs[1]),b.ticket)==LIE_FLOW_OK);
    assert(lie_flow_request(lie_job_flow(jobs[1]),1)==LIE_FLOW_OK);
    for (unsigned i=0;i<3000;++i) { lie_worker_snapshot(w,&info); if (info.generated_tokens==17) break; pause_short(); }
    assert(info.generated_tokens==17); /* peer progresses while A still holds a loan and full buffer */
    lie_job_cancel(jobs[0]); assert(a.data[0]=='A'); /* cancel cannot unpin consumer storage */
    assert(lie_flow_release(lie_job_flow(jobs[0]),a.ticket)==LIE_FLOW_OK);
    for (unsigned i=0;i<LIE_WORKER_JOBS;++i) lie_job_release(jobs[i]);
    for (unsigned i=0;i<3000;++i) { lie_worker_snapshot(w,&info); if (!info.active && !info.queued && info.cancelled_requests==8) break; pause_short(); }
    assert(!info.active && !info.queued && !info.output_blocked && info.cancelled_requests==8);
    assert(consume(submit(w,"normal",128))==8);
    assert(consume(submit(w,"normal",3))==3);
    assert(consume(submit(w,"EMPTY",128))==0);
    lie_job *bad=submit(w,"OVERSIZED",128);
    lie_flow_event e=next(bad); assert(e.end==LIE_FLOW_ERROR);
    lie_job_info ji; lie_job_snapshot(bad,&ji); assert(ji.finish==LIE_FINISH_INVALID);
    lie_job_release(bad);
    fake_barrier_arm(); lie_job *flight=submit(w,"LONG",128); fake_barrier_wait();
    lie_job_cancel(flight); lie_job_release(flight); /* worker reference survives client lifetime */
    fake_barrier_release();
    for (unsigned i=0;i<3000;++i) { lie_worker_snapshot(w,&info); if (!info.active && !info.queued) break; pause_short(); }
    assert(!info.active && !info.queued);
    lie_job *fault=submit(w,"FAULT",128); e=next(fault); assert(e.end==LIE_FLOW_ERROR);
    wait_state(w,LIE_FAILED); lie_job_release(fault);
    extra=request("normal",8); rejected=NULL;
    assert(lie_worker_submit(w,&extra,&rejected)==1); lie_chat_free(&extra);
    stop(w);
    opts.model_path="not-a-fixture"; w=lie_worker_create(&opts); assert(w); wait_state(w,LIE_FAILED); stop(w);
    opts.model_path=":fixture:"; w=lie_worker_create(&opts); assert(w);
    lie_worker_stop(w); lie_worker_snapshot(w,&info);
    assert(info.state==LIE_STOPPING || info.state==LIE_STOPPED);
    wait_state(w,LIE_STOPPED); lie_worker_destroy(w);
    /* All eight admitted sequences share the native-ready dispatch. */
    opts.max_active=8;fake_calls_reset();w=lie_worker_create(&opts);assert(w);wait_state(w,LIE_READY);
    fake_barrier_arm_phase(FAKE_PREFILL);jobs[0]=submit(w,"LONG-A",16);fake_barrier_wait();
    for(unsigned k=1;k<8;++k)jobs[k]=submit(w,k%2?"LONG-B":"LONG-A",16);
    fake_barrier_release();
    for(unsigned k=0;k<3000;++k){lie_worker_snapshot(w,&info);if(info.output_blocked==8)break;pause_short();}
    assert(info.active==8&&!info.queued&&info.generated_tokens==64&&info.output_blocked==8);
    assert(info.decode_batches==8&&info.decode_batch_rows==64&&!info.decode_single_calls);
    for(unsigned k=0;k<8;++k)lie_job_release(jobs[k]);
    for(unsigned k=0;k<3000;++k){lie_worker_snapshot(w,&info);if(!info.active&&!info.queued)break;pause_short();}
    assert(info.cancelled_requests==8&&!info.output_blocked);stop(w);
    puts("bounded worker, backpressure, owner, in-flight cancel and poison fixtures: PASS (not inference)");
    return 0;
}
