/* SPDX-License-Identifier: MIT */
/* Synthetic provider contract failures through the real worker. NOT-INFERENCE. */
#include "lie/worker.h"
#include "fake_executor.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static void pause_short(void) { struct timespec t={0,1000000}; nanosleep(&t,NULL); }
static lie_worker_info wait_state(lie_worker *w, lie_worker_state state) {
    lie_worker_info i={0};
    for (unsigned n=0;n<3000;++n) {
        lie_worker_snapshot(w,&i); if (i.state==state) return i; pause_short();
    }
    assert(!"worker state deadline"); return i;
}
static lie_worker *start_width(unsigned width) {
    fake_calls_reset(); lie_worker_options o={.model_path=":fixture:",.context=1024,.chunk=2,.max_active=width};
    lie_worker *w=lie_worker_create(&o); assert(w); wait_state(w,LIE_READY); return w;
}
static lie_worker *start(void) { return start_width(1); }
static void stop(lie_worker *w) { lie_worker_stop(w); wait_state(w,LIE_STOPPED); lie_worker_destroy(w); }
static lie_job *submit(lie_worker *w, const char *text, unsigned max_tokens) {
    lie_chat_request r={.count=1,.max_tokens=max_tokens};
    r.messages[0]=(lie_chat_message){LIE_CHAT_USER,strdup(text),strlen(text)};
    lie_job *j=NULL; assert(r.messages[0].content && !lie_worker_submit(w,&r,&j)); return j;
}
static lie_job_info terminal(lie_job *j, lie_flow_end end) {
    for (unsigned n=0;n<3000;++n) {
        lie_flow_event e; lie_flow_status rc=lie_flow_next(lie_job_flow(j),&e);
        if (rc==LIE_FLOW_WOULD_BLOCK) { pause_short(); continue; }
        assert(rc==LIE_FLOW_OK && e.end==end); /* No unconfirmed token may escape. */
        lie_job_info i; lie_job_snapshot(j,&i); return i;
    }
    assert(!"terminal deadline"); return (lie_job_info){0};
}
static lie_worker_info idle(lie_worker *w) {
    lie_worker_info i={0};
    for (unsigned n=0;n<3000;++n) {
        lie_worker_snapshot(w,&i); if (!i.active && !i.queued && i.failed_requests==2) return i; pause_short();
    }
    assert(!"retirement deadline"); return i;
}
static void rejects_after_fault(lie_worker *w) {
    lie_chat_request r={.count=1,.max_tokens=1};
    r.messages[0]=(lie_chat_message){LIE_CHAT_USER,strdup("normal"),6}; lie_job *j=NULL;
    assert(lie_worker_submit(w,&r,&j)==1 && !j && r.count==1); lie_chat_free(&r);
}
static void cancellation(fake_phase phase) {
    lie_worker *w=start(); fake_barrier_arm_phase(phase);
    lie_job *a=submit(w,"LONG",128); fake_barrier_wait();
    lie_worker_info i; lie_worker_snapshot(w,&i);
    assert(i.active==1 && !i.output_blocked);
    assert(i.executor_phase==(phase==FAKE_PREFILL?LIE_EXECUTOR_PREFILL:LIE_EXECUTOR_DECODE));
    assert(i.prefill_started-i.prefill_returned==(phase==FAKE_PREFILL?1u:0u));
    assert(i.decode_started-i.decode_returned==(phase==FAKE_DECODE?1u:0u));
    lie_job_info ji; lie_job_snapshot(a,&ji);
    assert(!ji.output_tokens && !ji.decode_calls && !ji.retired);
    if (phase==FAKE_PREFILL) assert(!ji.prefill_tokens && !ji.prefill_calls);
    lie_job *queued=submit(w,"normal",1);
    lie_job_cancel(queued); lie_job_release(queued); /* Not an in-flight cancellation. */
    lie_job_cancel(a); lie_job_cancel(a); /* Idempotent accounting, no wait. */
    lie_worker_snapshot(w,&i);
    assert(i.cancel_during_prefill==(phase==FAKE_PREFILL?1u:0u));
    assert(i.cancel_during_decode==(phase==FAKE_DECODE?1u:0u));
    lie_job_release(a); /* Lifetime must survive both consumer releases. */
    fake_barrier_release();
    for (unsigned n=0;n<3000;++n) {
        lie_worker_snapshot(w,&i); if (i.cancelled_requests==2 && !i.active && !i.queued) break; pause_short();
    }
    assert(i.state==LIE_READY && i.cancelled_requests==2 && !i.active && !i.queued && !i.output_blocked);
    assert(i.executor_phase==LIE_EXECUTOR_IDLE && i.prefill_started==i.prefill_returned && i.decode_started==i.decode_returned);
    assert(!i.generated_tokens && !i.completed_requests && !i.failed_requests);
    fake_calls c=fake_calls_snapshot();
    assert(c.create==1 && c.close==1 && !c.text);
    assert(c.prefill==(phase==FAKE_PREFILL?1u:2u) && c.decode==(phase==FAKE_DECODE?1u:0u));
    /* A fresh peer remains usable after cancellation, not after poison. */
    a=submit(w,"EMPTY",1); ji=terminal(a,LIE_FLOW_COMPLETE);
    assert(ji.finish==LIE_FINISH_STOP && !ji.output_tokens); lie_job_release(a); stop(w);
}
int main(void) {
    const char *cases[]={"BAD-POSITION","BAD-EMITTED","BAD-STOP","NO-PROGRESS","BAD-EOS-POSITION",
        "NEGATIVE-TOKEN","LARGE-TOKEN","DECODE-REFUSAL","PREFILL-REFUSAL","TEXT-REFUSAL","TEXT-SIZE",
        "FAULT","PREFILL-FAULT"};
    for (unsigned k=0;k<sizeof(cases)/sizeof(*cases);++k) {
        printf("case %s\n",cases[k]); fflush(stdout);
        lie_worker *w=start(); fake_barrier_arm_phase(FAKE_PREFILL);
        lie_job *bad=submit(w,cases[k],1); fake_barrier_wait();
        lie_job *queued=submit(w,"normal",1); fake_barrier_release();
        lie_job_info a=terminal(bad,LIE_FLOW_ERROR), b=terminal(queued,LIE_FLOW_ERROR);
        assert(a.finish==LIE_FINISH_BACKEND && b.finish==LIE_FINISH_BACKEND && !a.output_tokens && !b.prepared);
        lie_worker_info i=idle(w); assert(i.state==LIE_FAILED && i.error[0]);
        assert(!i.generated_tokens && !i.completed_requests && i.failed_requests==2 && !i.cancelled_requests);
        assert(!i.output_blocked && i.executor_phase==LIE_EXECUTOR_IDLE);
        assert(i.prefill_started==i.prefill_returned && i.decode_started==i.decode_returned);
        fake_calls c=fake_calls_snapshot();
        assert(c.create==1 && c.close==1); /* Queued peer never touched the provider. */
        assert(c.prefill==(!strcmp(cases[k],"PREFILL-REFUSAL")?1u:2u));
        assert(c.decode==(!strcmp(cases[k],"PREFILL-REFUSAL") || !strcmp(cases[k],"PREFILL-FAULT")?0u:1u));
        assert(c.text==(!strcmp(cases[k],"TEXT-REFUSAL") || !strcmp(cases[k],"TEXT-SIZE")?1u:0u));
        rejects_after_fault(w); lie_job_release(bad); lie_job_release(queued); stop(w);
    }
    /* One malformed batch peer suppresses both outputs. Terminal metadata must
     * already be visible when abort releases the in-flight flow reservation. */
    lie_worker *w=start_width(2);fake_barrier_arm_phase(FAKE_PREFILL);
    lie_job *a=submit(w,"normal",1);fake_barrier_wait();
    lie_job *b=submit(w,"BAD-POSITION",1);fake_barrier_release();
    lie_job_info ai=terminal(a,LIE_FLOW_ERROR),bi=terminal(b,LIE_FLOW_ERROR);
    assert(ai.finish==LIE_FINISH_BACKEND&&bi.finish==LIE_FINISH_BACKEND&&!ai.output_tokens&&!bi.output_tokens);
    lie_worker_info info=idle(w);assert(info.state==LIE_FAILED&&info.decode_batches==1&&info.decode_batch_rows==2);
    assert(!fake_calls_snapshot().text);lie_job_release(a);lie_job_release(b);stop(w);
    cancellation(FAKE_PREFILL); cancellation(FAKE_DECODE);
    puts("executor frontier/byte guards, fail-closed peers, prefill/decode cancellation and retirement: PASS (NOT-INFERENCE)");
    return 0;
}
