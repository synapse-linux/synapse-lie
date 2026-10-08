/* SPDX-License-Identifier: MIT */
/* Physical-token admission and lifecycle fixture. NOT-INFERENCE. */
#include "lie/core.h"
#include <assert.h>
#include <poll.h>
#include <stdlib.h>
#include <stdio.h>
#include <time.h>
static void ready(lie_core *c,lie_core_state state) {
    for(unsigned i=0;i<20000;++i) {
        lie_core_info s; lie_core_snapshot(c,&s);
        assert(s.state!=LIE_FAILED);
        if(s.state==state)return;
        struct timespec t={0,1000000}; nanosleep(&t,NULL);
    }
    assert(!"fixture lifecycle deadline");
}
int main(void) {
    lie_core_options o; lie_core_options_init(&o);
    o.model_path=":fixture:"; o.context=LIE_CONTEXT_LIMIT;
    o.rope_profile=LIE_ROPE_YARN4; o.prefix_cache_bytes=0;
    lie_core *c=lie_core_create(&o); assert(c); ready(c,LIE_READY);
    lie_core_info info; lie_core_snapshot(c,&info);
    assert(info.model.context_tokens==1048576 && info.rope_profile==LIE_ROPE_YARN4);
    size_t count=o.context-1;
    int32_t *tokens=calloc(count,sizeof(*tokens)); assert(tokens);
    lie_core_request r; lie_core_request_init(&r);
    r.kind=LIE_INPUT_TOKENS;r.tokens=tokens;r.token_count=count;r.max_tokens=1;
    lie_job *j=NULL; assert(!lie_core_submit(c,&r,&j)); free(tokens);
    unsigned output=0;
    lie_flow *flow=lie_job_flow(j); assert(flow);
    for(;;) {
        lie_flow_event e; lie_flow_status rc=lie_flow_next(flow,&e);
        if(rc==LIE_FLOW_WOULD_BLOCK) {
            struct pollfd fd={lie_flow_fd(flow,LIE_FLOW_OUTPUT_READY),POLLIN,0};
            assert(poll(&fd,1,20000)>0);
            assert(lie_flow_drain(flow,LIE_FLOW_OUTPUT_READY)==LIE_FLOW_OK);
            continue;
        }
        assert(rc==LIE_FLOW_OK);
        if(e.end!=LIE_FLOW_ACTIVE){assert(e.end==LIE_FLOW_COMPLETE);break;}
        output+=(unsigned)e.tokens;
        assert(lie_flow_release(flow,e.ticket)==LIE_FLOW_OK);
        (void)lie_flow_request(flow,e.tokens);
    }
    lie_job_info result; lie_job_snapshot(j,&result);
    assert(result.prompt_tokens==count && result.prefill_tokens==count &&
           result.prefill_calls==512 && output==1 && result.output_tokens==1);
    lie_job_release(j);lie_core_stop(c);ready(c,LIE_STOPPED);lie_core_destroy(c);
    o.context=LIE_CONTEXT_LIMIT+1;assert(!lie_core_create(&o));
    o.context=4096;o.rope_profile=(lie_rope_profile)99;assert(!lie_core_create(&o));
    puts("1M physical admission/lifecycle fixture: PASS (NOT-INFERENCE)");
    return 0;
}
