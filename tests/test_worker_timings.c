/* SPDX-License-Identifier: MIT */
/* Synthetic executor plus link-time fake clock. NOT inference or performance.
 * --wrap is used only by this test executable; production has no clock override. */
#include "lie/worker.h"
#include "lie/wire.h"
#include "fake_executor.h"
#include <assert.h>
#include <errno.h>
#include <json-c/json.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

enum clock_fault { NONE, START_ERROR, END_ERROR, BACKWARD, BAD_NSEC, NEGATIVE_SEC,
                   CLOCK_OVERFLOW, SUM_OVERFLOW };
static enum clock_fault fault;
static atomic_uint reads;
static atomic_uint_fast64_t ticks;
static uint64_t stride=1000000;
int __wrap_clock_gettime(clockid_t clock, struct timespec *out);
int __wrap_clock_gettime(clockid_t clock, struct timespec *out) {
    assert(clock==CLOCK_MONOTONIC);
    unsigned n=atomic_fetch_add(&reads,1);
    uint64_t t=atomic_fetch_add(&ticks,stride);
    if ((fault==START_ERROR && !n) || (fault==END_ERROR && n==1)) { errno=EIO; return -1; }
    if (fault==BACKWARD && n==1) t=0;
    if (fault==SUM_OVERFLOW) t=n%2?UINT64_MAX:0;
    out->tv_sec=(time_t)(t/1000000000); out->tv_nsec=(long)(t%1000000000);
    if (fault==BAD_NSEC && !n) out->tv_nsec=1000000000;
    if (fault==NEGATIVE_SEC && !n) out->tv_sec=-1;
    if (fault==CLOCK_OVERFLOW && !n) out->tv_sec=(time_t)(UINT64_MAX/1000000000+1);
    return 0;
}
static void pause_short(void) { struct timespec t={0,1000000}; nanosleep(&t,NULL); }
static lie_worker *start(enum clock_fault f, uint64_t step) {
    fault=f; stride=step; atomic_store(&ticks,1000000); atomic_store(&reads,0);
    lie_worker_options opts={":fixture:",1024,2,1,0,{0}};
    lie_worker *w=lie_worker_create(&opts); assert(w);
    for (unsigned i=0;i<3000;++i) {
        lie_worker_info info; lie_worker_snapshot(w,&info);
        if (info.state==LIE_READY) return w;
        pause_short();
    }
    assert(!"worker ready deadline"); return NULL;
}
static void stop(lie_worker *w) {
    lie_worker_stop(w);
    for (unsigned i=0;i<3000;++i) {
        lie_worker_info info; lie_worker_snapshot(w,&info);
        if (info.state==LIE_STOPPED) { lie_worker_destroy(w); return; }
        pause_short();
    }
    assert(!"worker stop deadline");
}
static lie_job *submit(lie_worker *w, const char *text, unsigned tokens) {
    lie_chat_request r={.count=1,.max_tokens=tokens};
    r.messages[0]=(lie_chat_message){LIE_CHAT_USER,strdup(text),strlen(text)};
    lie_job *j=NULL; assert(r.messages[0].content && !lie_worker_submit(w,&r,&j)); return j;
}
static lie_job_info consume(lie_job *j, lie_flow_end end) {
    unsigned tokens=0;
    for (unsigned n=0;n<3000;++n) {
        lie_flow_event e;
        lie_flow_status rc=lie_flow_next(lie_job_flow(j),&e);
        if (rc==LIE_FLOW_WOULD_BLOCK) { pause_short(); continue; }
        assert(rc==LIE_FLOW_OK);
        if (e.end!=LIE_FLOW_ACTIVE) {
            assert(e.end==end);
            lie_job_info info; lie_job_snapshot(j,&info);
            /* Already final even when sequence retirement has not finished. */
            assert(info.output_tokens==tokens && info.finish!=LIE_FINISH_NONE);
            return info;
        }
        assert(e.token_offset==tokens); tokens+=(unsigned)e.tokens;
        assert(lie_flow_release(lie_job_flow(j),e.ticket)==LIE_FLOW_OK);
        (void)lie_flow_request(lie_job_flow(j),e.tokens);
    }
    assert(!"output deadline"); return (lie_job_info){0};
}
static void null_field(json_object *j, const char *name) {
    json_object *v; assert(json_object_object_get_ex(j,name,&v) && json_object_is_type(v,json_type_null));
}
static void wire_timing(const lie_job_info *i, bool valid, bool zero) {
    char *text=lie_wire_completion("id","fixture-NOT-INFERENCE",1,"",0,i); assert(text);
    json_object *j=json_tokener_parse(text), *t, *v;
    assert(j && json_object_object_get_ex(j,"lie_timings",&t));
    assert(json_object_object_get_ex(t,"valid",&v) && json_object_get_boolean(v)==valid);
    if (!valid) { null_field(t,"prefill_ms"); null_field(t,"decode_ms"); }
    if (!valid || zero) { null_field(t,"prefill_tokens_per_second"); null_field(t,"decode_tokens_per_second"); }
    else {
        assert(json_object_object_get_ex(t,"prefill_ms",&v) && json_object_get_double(v)==2.0);
        assert(json_object_object_get_ex(t,"prefill_tokens_per_second",&v) && json_object_get_double(v)==2000.0);
        if (!i->output_tokens)
            assert(json_object_object_get_ex(t,"decode_tokens_per_second",&v) && json_object_get_double(v)==0.0);
    }
    json_object_put(j); free(text);
}
static void check_counts(lie_job_info i, unsigned tokens, unsigned calls) {
    assert(i.timing_valid && i.prompt_tokens==4 && i.prefill_tokens==4 && i.prefill_calls==2);
    assert(i.output_tokens==tokens && i.decode_calls==calls);
    assert(i.prefill_ns==2000000 && i.decode_ns==(uint64_t)calls*1000000);
}
int main(void) {
    lie_worker *w=start(NONE,1000000);
    const char *texts[]={"normal","normal","EMPTY"}; unsigned budgets[]={128,3,128};
    unsigned tokens[]={8,3,0}, calls[]={9,3,1};
    for (unsigned k=0;k<3;++k) {
        lie_job *j=submit(w,texts[k],budgets[k]);
        lie_job_info i=consume(j,LIE_FLOW_COMPLETE); check_counts(i,tokens[k],calls[k]);
        wire_timing(&i,true,false); lie_job_release(j);
    }
    /* Stalled credit/consumer time and queue time must not become executor time. */
    lie_job *a=submit(w,"LONG",16), *b=submit(w,"normal",3);
    lie_job_info ai={0}, bi={0};
    for (unsigned n=0;n<3000;++n) {
        lie_job_snapshot(a,&ai); if (ai.output_tokens==8) break; pause_short();
    }
    check_counts(ai,8,8);
    lie_job_snapshot(b,&bi); assert(!bi.prepared && !bi.prefill_calls && !bi.decode_calls);
    unsigned before=atomic_load(&reads); atomic_fetch_add(&ticks,10000000000ULL);
    for (unsigned n=0;n<20;++n) pause_short();
    assert(atomic_load(&reads)==before); lie_job_snapshot(a,&ai); check_counts(ai,8,8);
    ai=consume(a,LIE_FLOW_COMPLETE); check_counts(ai,16,16); lie_job_release(a);
    bi=consume(b,LIE_FLOW_COMPLETE); check_counts(bi,3,3); lie_job_release(b);
    /* In-flight calls have not yet completed and cannot be timed/counted early. */
    fake_barrier_arm(); a=submit(w,"LONG",128); fake_barrier_wait();
    lie_job_snapshot(a,&ai); assert(ai.prefill_calls==2 && ai.decode_calls==0 && ai.decode_ns==0);
    lie_job_cancel(a); fake_barrier_release(); ai=consume(a,LIE_FLOW_CANCELLED);
    check_counts(ai,0,1); assert(ai.finish==LIE_FINISH_CANCEL); lie_job_release(a);
    a=submit(w,"FAULT",128); ai=consume(a,LIE_FLOW_ERROR);
    check_counts(ai,0,1); assert(ai.finish==LIE_FINISH_BACKEND); lie_job_release(a); stop(w);
    w=start(NONE,1000000); a=submit(w,"PREFILL-FAULT",128); ai=consume(a,LIE_FLOW_ERROR);
    assert(ai.finish==LIE_FINISH_BACKEND && ai.prompt_tokens==4 && ai.prefill_tokens==2);
    assert(ai.prefill_calls==2 && ai.prefill_ns==2000000 && !ai.decode_calls && !ai.output_tokens);
    char *terminal=lie_wire_end("id","fixture",1,&ai,true);
    assert(terminal && !strstr(terminal,"lie_timings") && !strstr(terminal,"\"usage\"")); free(terminal);
    lie_job_release(a); stop(w);
    for (enum clock_fault f=START_ERROR;f<=SUM_OVERFLOW;++f) {
        w=start(f,1000000); a=submit(w,"normal",3); ai=consume(a,LIE_FLOW_COMPLETE);
        assert(!ai.timing_valid && ai.prefill_tokens==4 && ai.prefill_calls==2 && ai.decode_calls==3);
        wire_timing(&ai,false,false); lie_job_release(a); stop(w);
    }
    w=start(NONE,0); a=submit(w,"normal",3); ai=consume(a,LIE_FLOW_COMPLETE);
    assert(ai.timing_valid && !ai.prefill_ns && !ai.decode_ns); wire_timing(&ai,true,true);
    lie_job_release(a); stop(w);
    puts("worker completed-call timing, EOS, queue/credit exclusion and invalid clock: PASS (NOT-INFERENCE)");
    return 0;
}
