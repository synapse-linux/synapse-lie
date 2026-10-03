/* SPDX-License-Identifier: MIT */
/* Synthetic state/lifetime tests. No model forward or GPU. */
#include "lie/core.h"
#include "fake_executor.h"
#include <assert.h>
#include <poll.h>
#include <stdio.h>
#include <time.h>

static void pause_short(void){struct timespec t={0,1000000};nanosleep(&t,NULL);}
static lie_core_info wait_state(lie_core *c,lie_core_state state){
    lie_core_info i={0};
    for(unsigned n=0;n<4000;++n){lie_core_snapshot(c,&i);if(i.state==state)return i;pause_short();}
    assert(!"state deadline");return i;
}
static lie_core *start(uint64_t budget){
    fake_calls_reset();lie_core_options o;lie_core_options_init(&o);o.cache_policy.enabled=false;
    assert(o.prefix_cache_bytes==LIE_PREFIX_CACHE_DEFAULT_BYTES);
    o.model_path=":fixture:";o.context=128;o.chunk=4;o.max_active=2;o.prefix_cache_bytes=budget;
    lie_core *c=lie_core_create(&o);assert(c);wait_state(c,LIE_READY);return c;
}
static void stop(lie_core *c){
    lie_core_stop(c);lie_core_info i=wait_state(c,LIE_STOPPED);
    assert(!i.cache.retained_bytes&&!i.cache.entries);lie_core_destroy(c);
    fake_calls f=fake_calls_snapshot();assert(f.create==f.close);
}
static lie_job *submit(lie_core *c,const int32_t *tokens,size_t n){
    lie_core_request r;lie_core_request_init(&r);r.kind=LIE_INPUT_TOKENS;
    r.tokens=tokens;r.token_count=n;r.max_tokens=8;lie_job *j=NULL;
    assert(!lie_core_submit(c,&r,&j)&&j);return j;
}
static lie_job_info consume(lie_job *j,lie_flow_end expected){
    unsigned count=0;lie_job_info i={0};bool ended=false;
    for(unsigned n=0;n<8000&&!ended;++n){
        lie_flow_event e;lie_flow_status rc=lie_flow_next(lie_job_flow(j),&e);
        if(rc==LIE_FLOW_WOULD_BLOCK){struct pollfd fd={lie_flow_fd(lie_job_flow(j),LIE_FLOW_OUTPUT_READY),POLLIN,0};
            assert(poll(&fd,1,1)>=0);assert(lie_flow_drain(lie_job_flow(j),LIE_FLOW_OUTPUT_READY)==LIE_FLOW_OK);continue;}
        assert(rc==LIE_FLOW_OK);
        if(e.end!=LIE_FLOW_ACTIVE){assert(e.end==expected);ended=true;break;}
        assert(e.token_offset==count);count+=(unsigned)e.tokens;
        assert(lie_flow_release(lie_job_flow(j),e.ticket)==LIE_FLOW_OK);
        (void)lie_flow_request(lie_job_flow(j),e.tokens);
    }
    assert(ended);lie_job_snapshot(j,&i);
    if(expected==LIE_FLOW_COMPLETE){
        assert(i.timing_valid&&count==8&&i.output_tokens==count);
        int32_t ids[8];size_t used=0;assert(lie_job_output_tokens(j,ids,8,&used)==LIE_OK&&used==8);
        for(unsigned k=0;k<8;++k)assert(ids[k]==(int32_t)k);
        assert(i.prefill_tokens+i.cached_tokens==i.prompt_tokens);
    }
    lie_job_release(j);return i;
}
static lie_job_info run(lie_core *c,const int32_t *tokens,size_t n){return consume(submit(c,tokens,n),LIE_FLOW_COMPLETE);}
int main(void){
    int32_t a[]={0,10,10,10,11,12,13,14,15},b[]={0,20,20,20,21,22,23,24};
    lie_core *c=start(LIE_PREFIX_CACHE_DEFAULT_BYTES);
    lie_job_info i=run(c,a,4);assert(!i.cached_tokens&&i.prefill_tokens==4&&i.cache_capture_ns);
    lie_core_info ci;lie_core_snapshot(c,&ci);uint64_t one=ci.cache.retained_bytes;
    assert(one&&ci.cache.captures==1&&ci.cache.misses==1);
    i=run(c,a,4);assert(i.cached_tokens==4&&!i.prefill_calls&&!i.prefill_ns&&i.cache_restore_ns);
    i=run(c,a,9);assert(i.cached_tokens==4&&i.prefill_tokens==5&&i.prefill_calls==2);
    i=run(c,a,9);assert(i.cached_tokens==8&&i.prefill_tokens==1);
    i=run(c,b,8);assert(!i.cached_tokens&&i.prefill_tokens==8);
    i=run(c,a,3);assert(!i.cached_tokens&&i.prefill_tokens==3); /* No truncation of recurrent state. */
    i=run(c,a,3);assert(i.cached_tokens==3&&!i.prefill_calls);
    int32_t short_extended[]={0,10,10,99,99};
    i=run(c,short_extended,5);assert(!i.cached_tokens); /* No new chunk partition after short hit. */
    lie_core_snapshot(c,&ci);assert(ci.cache.hits==4&&ci.cache.entries==5&&ci.cache.reused_tokens==19);
    stop(c);

    c=start(0);run(c,a,4);run(c,a,4);
    fake_calls f=fake_calls_snapshot();assert(f.prefill==2&&!f.capture&&!f.restore);
    lie_core_snapshot(c,&ci);assert(!ci.cache.lookups&&!ci.cache.retained_bytes);stop(c);
    c=start(one-1);run(c,a,4);run(c,a,4);lie_core_snapshot(c,&ci);
    assert(ci.cache.skipped==2&&!ci.cache.entries&&!fake_calls_snapshot().capture);stop(c);
    c=start(one);run(c,a,4);run(c,b,4);run(c,a,4);lie_core_snapshot(c,&ci);
    assert(ci.cache.evictions==2&&ci.cache.entries==1&&ci.cache.peak_retained_bytes==one);stop(c);

    /* A repeatedly reused prefix survives a newer one-use prefix under utility
     * pressure; compiling the feature out restores the ordinary LRU choice. */
    c=start(one*2);run(c,a,4);
    for(unsigned k=0;k<8;++k)assert(run(c,a,4).cached_tokens==4);
    run(c,b,4);int32_t third[]={0,30,30,30};run(c,third,4);
    i=run(c,a,4);assert(i.cached_tokens==(LIE_CACHE_UTILITY?4u:0u));stop(c);

    /* Exercise real capture/expansion/provider writes, not only codec helpers. */
    c=start(16u*1024u*1024u);fake_state_padding(2u*1024u*1024u);
    run(c,a,4);lie_core_snapshot(c,&ci);
    assert(ci.cache.compressed_captures==(LIE_CHECKPOINT_COMPRESSION?1u:0u));
    assert((ci.cache.expanded_bytes>ci.cache.retained_bytes)==(LIE_CHECKPOINT_COMPRESSION!=0));
    assert(run(c,a,4).cached_tokens==4);assert(run(c,a,9).cached_tokens==4);
    stop(c);fake_state_padding(0);

    /* Cancellation while a completed transfer is pinned must retire only its
     * own sequence. A peer uses the checkpoint and fresh generation state. */
    c=start(LIE_PREFIX_CACHE_DEFAULT_BYTES);run(c,a,4);
    fake_barrier_arm_phase(FAKE_RESTORE);lie_job *j=submit(c,a,4);fake_barrier_wait();
    lie_core_snapshot(c,&ci);assert(ci.executor_phase==LIE_EXECUTOR_RESTORE);
    lie_job *peer=submit(c,a,4);lie_job_cancel(j);fake_barrier_release();
    consume(j,LIE_FLOW_CANCELLED);i=consume(peer,LIE_FLOW_COMPLETE);assert(i.cached_tokens==4);stop(c);
    c=start(LIE_PREFIX_CACHE_DEFAULT_BYTES);
    fake_barrier_arm_phase(FAKE_CAPTURE);j=submit(c,a,4);fake_barrier_wait();
    lie_core_snapshot(c,&ci);assert(ci.executor_phase==LIE_EXECUTOR_CAPTURE);
    lie_job_cancel(j);fake_barrier_release();consume(j,LIE_FLOW_CANCELLED);
    i=run(c,a,4);assert(!i.cached_tokens);i=run(c,a,4);assert(i.cached_tokens==4);stop(c);

    for(unsigned fault=1;fault<=3;++fault){
        c=start(LIE_PREFIX_CACHE_DEFAULT_BYTES);if(fault==3)run(c,a,4);
        f=fake_calls_snapshot();fake_state_fault(fault);consume(submit(c,a,4),LIE_FLOW_ERROR);
        wait_state(c,LIE_FAILED);fake_calls after=fake_calls_snapshot();
        assert(after.decode==f.decode); /* Never decode a partial/invalid state. */
        if(fault==3)assert(after.prefill==f.prefill&&after.restore==f.restore+1); /* No fallback. */
        stop(c);
    }
    puts("RAM prefix cache ownership, budget, cancellation and fail-closed checks: PASS (NOT-INFERENCE)");
    return 0;
}
