/* SPDX-License-Identifier: MIT */
/* Headless ownership/lifecycle fixture. No JSON, HTTP, model weights or GPU. */
#include "lie/core.h"
#include "fake_executor.h"
#include <assert.h>
#include <math.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
static void pause_short(void) { struct timespec t={0,1000000};nanosleep(&t,NULL); }
static lie_core_info wait_state(lie_core *c, lie_core_state state) {
    lie_core_info info={0};
    for (unsigned n=0;n<4000;++n) { lie_core_snapshot(c,&info);if(info.state==state)return info;pause_short(); }
    assert(!"core state deadline");return info;
}
static void stopped(lie_core *c) { lie_core_stop(c);wait_state(c,LIE_STOPPED);lie_core_destroy(c); }
static lie_flow_event next(lie_job *j) {
    lie_flow_event e;
    for(unsigned n=0;n<4000;++n) {
        lie_flow_status rc=lie_flow_next(lie_job_flow(j),&e);
        if(rc==LIE_FLOW_OK)return e;
        assert(rc==LIE_FLOW_WOULD_BLOCK);
        struct pollfd fd={lie_flow_fd(lie_job_flow(j),LIE_FLOW_OUTPUT_READY),POLLIN,0};
        assert(poll(&fd,1,1)>=0);assert(lie_flow_drain(lie_job_flow(j),LIE_FLOW_OUTPUT_READY)==LIE_FLOW_OK);
    }
    assert(!"core output deadline");return (lie_flow_event){0};
}
static unsigned consume(lie_job *j) {
    unsigned count=0;
    for (;;) {
        lie_flow_event e=next(j);
        if(e.end!=LIE_FLOW_ACTIVE) { assert(e.end==LIE_FLOW_COMPLETE);break; }
        assert(e.token_offset==count);count+=(unsigned)e.tokens;
        assert(lie_flow_release(lie_job_flow(j),e.ticket)==LIE_FLOW_OK);
        (void)lie_flow_request(lie_job_flow(j),e.tokens);
    }
    lie_job_info info;lie_job_snapshot(j,&info);assert(info.output_tokens==count && info.timing_valid);
    return count;
}
static void eos_sequence_contract(void) {
    lie_model_options o={.abi_version=LIE_EXECUTOR_ABI,.struct_bytes=sizeof(o),
                         .context_tokens=128,.prefill_chunk_tokens=4};
    lie_model *m=NULL;lie_sequence *s=NULL;
    assert(lie_sequence_set_eos_policy(NULL,LIE_EOS_STOP,NULL)==LIE_INVALID);
    assert(lie_backend_open(":fixture:",&o,&m,NULL)==LIE_OK);
    assert(lie_sequence_create(m,&s,NULL)==LIE_OK);
    assert(lie_sequence_set_eos_policy(s,LIE_EOS_IGNORE,NULL)==LIE_OK);
    assert(lie_sequence_set_eos_policy(s,(lie_eos_policy)2,NULL)==LIE_INVALID);
    int32_t prompt[]={0,10,10,10};
    assert(lie_sequence_prefill(s,prompt,4,NULL)==LIE_OK);
    assert(lie_sequence_set_eos_policy(s,LIE_EOS_STOP,NULL)==LIE_INVALID);
    for(unsigned i=0;i<16;++i){lie_decode_result d;
        assert(lie_sequence_decode(s,&d,NULL)==LIE_OK&&d.emitted==1&&!d.stop&&d.token==(int32_t)i);}
    assert(lie_sequence_close(&s,NULL)==LIE_OK);
    assert(lie_model_close(&m,NULL)==LIE_OK);
}
static void automatic_output_budget(void) {
    lie_core_options o={.model_path=":fixture:",.context=256,.chunk=16,.max_active=2};
    lie_core *c=lie_core_create(&o);assert(c);wait_state(c,LIE_READY);
    lie_core_request r;lie_core_request_init(&r);r.kind=LIE_INPUT_TOKENS;
    int32_t prompt[]={1,10,10,10};r.tokens=prompt;r.token_count=4;r.max_tokens=0;
    lie_job *j=NULL;fake_barrier_arm_phase(FAKE_PREFILL);
    assert(!lie_core_submit(c,&r,&j));fake_barrier_wait();
    r.max_tokens=1;fake_barrier_release();assert(consume(j)==252);
    lie_job_info info;lie_job_snapshot(j,&info);
    assert(info.output_token_limit==252&&info.finish==LIE_FINISH_LENGTH);
    lie_job_release(j);
    r.max_tokens=0;prompt[0]=0;j=NULL;
    assert(!lie_core_submit(c,&r,&j));assert(consume(j)==8);
    lie_job_snapshot(j,&info);assert(info.output_token_limit==252&&info.finish==LIE_FINISH_STOP);
    lie_job_release(j);
    /* A near-full automatic row and an explicit peer use independent budgets. */
    int32_t near[256]={1};for(unsigned k=1;k<256;++k)near[k]=10;
    r.tokens=near;r.token_count=253;j=NULL;fake_barrier_arm_phase(FAKE_PREFILL);
    assert(!lie_core_submit(c,&r,&j));fake_barrier_wait();
    lie_core_request peer=r;prompt[0]=1;peer.tokens=prompt;peer.token_count=4;peer.max_tokens=7;
    lie_job *b=NULL;assert(!lie_core_submit(c,&peer,&b));fake_barrier_release();
    assert(consume(j)==3&&consume(b)==7);
    lie_job_snapshot(j,&info);assert(info.output_token_limit==3);
    lie_job_release(j);lie_job_release(b);
    /* Zero room and explicit overflow refuse before sequence creation. */
    r.token_count=256;j=NULL;fake_calls before=fake_calls_snapshot();
    assert(!lie_core_submit(c,&r,&j));lie_flow_event e=next(j);
    assert(e.end==LIE_FLOW_ERROR&&fake_calls_snapshot().create==before.create);
    lie_job_release(j);r.token_count=253;r.max_tokens=4;j=NULL;
    assert(!lie_core_submit(c,&r,&j));e=next(j);
    assert(e.end==LIE_FLOW_ERROR&&fake_calls_snapshot().create==before.create);
    lie_job_release(j);j=NULL;r.max_tokens=0;r.abi_version=7;
    assert(lie_core_submit(c,&r,&j)==3&&!j);
    stopped(c);
    /* Existing advertised engine ceiling is retained; no new output cap. */
    o.context=8192;c=lie_core_create(&o);assert(c);wait_state(c,LIE_READY);
    lie_core_request_init(&r);r.kind=LIE_INPUT_TOKENS;r.tokens=prompt;r.token_count=4;r.max_tokens=0;
    assert(!lie_core_submit(c,&r,&j));assert(consume(j)==LIE_CORE_MAX_OUTPUT);
    lie_job_snapshot(j,&info);assert(info.output_token_limit==LIE_CORE_MAX_OUTPUT);
    lie_job_release(j);stopped(c);
#if LIE_MTP
    /* The final speculative burst cannot exceed the remaining three tokens. */
    o.context=130;o.mtp_model_path=":wide-fixture:";o.mtp_draft_tokens=12;
    c=lie_core_create(&o);assert(c);wait_state(c,LIE_READY);
    r.tokens=near;r.token_count=127;j=NULL;
    assert(!lie_core_submit(c,&r,&j));assert(consume(j)==3);
    lie_job_snapshot(j,&info);
    assert(info.output_token_limit==3&&info.finish==LIE_FINISH_LENGTH&&info.mtp_drafted>0);
    lie_job_release(j);stopped(c);
#endif
}
int main(void) {
    eos_sequence_contract();
    automatic_output_budget();
    lie_core_options options={.model_path=":fixture:",.context=1024,.chunk=2,.max_active=2};
    lie_core *c=lie_core_create(&options);assert(c);wait_state(c,LIE_READY);
    lie_core_request r;lie_core_request_init(&r);r.kind=LIE_INPUT_TOKENS;
    int32_t prompt[]={0,10,10,10};r.tokens=prompt;r.token_count=4;r.max_tokens=8;
    fake_barrier_arm_phase(FAKE_PREFILL);lie_job *j=NULL;
    assert(!lie_core_submit(c,&r,&j));fake_barrier_wait();
    prompt[0]=2; /* Would poison the fixture if the core borrowed input storage. */
    fake_barrier_release();assert(consume(j)==8);
    int32_t ids[16];size_t n=0;
    assert(lie_job_prompt_tokens(j,ids,16,&n)==LIE_OK && n==4 && ids[0]==0);
    assert(lie_job_output_tokens(j,NULL,0,&n)==LIE_BUFFER_SMALL && n==8);
    assert(lie_job_output_tokens(j,ids,16,&n)==LIE_OK && n==8);
    for(size_t k=0;k<n;++k)assert(ids[k]==(int32_t)k);
    lie_job_release(j);

    /* Same device owner, independent EOS policies; changing caller storage
     * after admission cannot change a queued job's fixed-token reservation. */
    prompt[0]=0;r.max_tokens=16;j=NULL;
    assert(r.eos_policy==LIE_EOS_STOP);
    assert(!lie_core_submit(c,&r,&j));assert(consume(j)==8);
    lie_job_info eos;lie_job_snapshot(j,&eos);assert(eos.finish==LIE_FINISH_STOP);
    lie_job_release(j);j=NULL;
    r.eos_policy=LIE_EOS_IGNORE;fake_barrier_arm_phase(FAKE_PREFILL);
    assert(!lie_core_submit(c,&r,&j));fake_barrier_wait();
    r.eos_policy=LIE_EOS_STOP;fake_barrier_release();assert(consume(j)==16);
    lie_job_snapshot(j,&eos);assert(eos.finish==LIE_FINISH_LENGTH);
    lie_job_release(j);j=NULL;
    fake_calls policy_before=fake_calls_snapshot();
    r.eos_policy=(lie_eos_policy)2;assert(lie_core_submit(c,&r,&j)==3&&!j);
    r.eos_policy=(lie_eos_policy)-1;assert(lie_core_submit(c,&r,&j)==3&&!j);
    r.eos_policy=LIE_EOS_IGNORE;r.stop_count=1;r.stop[0]="end";
    assert(lie_core_submit(c,&r,&j)==3&&!j);r.stop_count=0;r.stop[0]=NULL;
    r.format=LIE_FORMAT_JSON_OBJECT;assert(lie_core_submit(c,&r,&j)==3&&!j);
    r.format=LIE_FORMAT_TEXT;r.abi_version=6;assert(lie_core_submit(c,&r,&j)==3&&!j);
    assert(fake_calls_snapshot().create==policy_before.create);

    /* Deep copy nested tool strings/arrays and message content before return. */
    char content[]="normal",path[]="  caffè 🙂.txt  ",id[]="call1",name[]="read";
    char description[]="Read",params[]="{}",definition[]="{}";
    lie_tool_argument arg={"path",path,1};lie_tool_call call={id,name,&arg,1};
    lie_chat_message messages[]={{LIE_CHAT_USER,content,strlen(content)},
        {LIE_CHAT_ASSISTANT,"",0},{LIE_CHAT_TOOL,"result",6}};
    lie_chat_details details[3]={{0},{.calls=&call,.call_count=1},{.tool_call_id=id,.name=name}};
    lie_chat_tool tool={name,description,params,definition};
    lie_core_request_init(&r);r.chat=(lie_chat_template){messages,details,3,&tool,1,0};r.max_tokens=3;
    r.eos_policy=LIE_EOS_IGNORE;assert(lie_core_submit(c,&r,&j)==3&&!j);
    r.eos_policy=LIE_EOS_STOP;
    /* Occupy the owner before admission, so no input can be read prematurely. */
    lie_core_request blocker;lie_core_request_init(&blocker);blocker.kind=LIE_INPUT_TOKENS;
    int32_t blocking[]={1,10,10,10};blocker.tokens=blocking;blocker.token_count=4;blocker.max_tokens=512;
    lie_job *hold=NULL;fake_barrier_arm_phase(FAKE_PREFILL);
    assert(!lie_core_submit(c,&blocker,&hold));fake_barrier_wait();
    j=NULL;assert(!lie_core_submit(c,&r,&j));
    memset(content,'X',strlen(content));memset(path,'X',strlen(path));memset(id,'X',strlen(id));
    memset(name,'X',strlen(name));memset(description,'X',strlen(description));
    params[0]='!';definition[0]='!';arg=(lie_tool_argument){0};call=(lie_tool_call){0};
    memset(messages,0,sizeof(messages));memset(details,0,sizeof(details));tool=(lie_chat_tool){0};
    fake_barrier_release();assert(consume(j)==3);lie_job_release(j);lie_job_release(hold);
    for(unsigned k=0;k<4000;++k){lie_core_info i;lie_core_snapshot(c,&i);if(!i.active&&!i.queued)break;pause_short();}

    /* Rejections never start a model sequence and never steal caller storage. */
    lie_core_request_init(&r);r.kind=LIE_INPUT_TOKENS;r.tokens=prompt;r.token_count=4;r.max_tokens=8;
    prompt[0]=-1;j=NULL;fake_calls before=fake_calls_snapshot();
    assert(lie_core_submit(c,&r,&j)==3 && !j && prompt[0]==-1);
    prompt[0]=0;r.generation.temperature=NAN;assert(lie_core_submit(c,&r,&j)==3 && !j);
    r.generation.temperature=0;r.token_count=LIE_CORE_MAX_CONTEXT+1;assert(lie_core_submit(c,&r,&j)==3);
    r.token_count=4;r.text="ambiguous";assert(lie_core_submit(c,&r,&j)==3);
    assert(fake_calls_snapshot().create==before.create);
    r.text=NULL;prompt[0]=2048;assert(!lie_core_submit(c,&r,&j));
    lie_flow_event e=next(j);assert(e.end==LIE_FLOW_ERROR && fake_calls_snapshot().create==before.create);
    lie_job_release(j);prompt[0]=0;

    /* Direct clients obey the same bounded credit and per-row cancellation. */
    options.max_active=2;stopped(c);c=lie_core_create(&options);assert(c);wait_state(c,LIE_READY);
    lie_core_request_init(&r);r.kind=LIE_INPUT_TOKENS;r.tokens=blocking;r.token_count=4;r.max_tokens=512;
    lie_job *a=NULL,*b=NULL;fake_barrier_arm_phase(FAKE_PREFILL);
    assert(!lie_core_submit(c,&r,&a));fake_barrier_wait();assert(!lie_core_submit(c,&r,&b));fake_barrier_release();
    lie_core_info info={0};
    for(unsigned k=0;k<4000;++k){lie_core_snapshot(c,&info);if(info.output_blocked==2)break;pause_short();}
    assert(info.output_blocked==2 && info.generated_tokens==16 && info.decode_batches>0);
    for(unsigned k=0;k<10;++k)pause_short();
    lie_core_snapshot(c,&info);assert(info.generated_tokens==16);
    e=next(a);assert(e.end==LIE_FLOW_ACTIVE);
    lie_flow_event peer=next(b);assert(peer.end==LIE_FLOW_ACTIVE);
    assert(lie_flow_release(lie_job_flow(b),peer.ticket)==LIE_FLOW_OK);
    assert(lie_flow_request(lie_job_flow(b),1)==LIE_FLOW_OK);
    for(unsigned k=0;k<4000;++k){lie_core_snapshot(c,&info);if(info.generated_tokens==17)break;pause_short();}
    assert(info.generated_tokens==17);lie_job_cancel(a);
    assert(e.bytes==256 && e.data[0]=='Z'); /* Cancellation cannot unpin a loan. */
    assert(lie_flow_release(lie_job_flow(a),e.ticket)==LIE_FLOW_OK);
    lie_job_release(a);lie_job_release(b);stopped(c);
    puts("headless C core ownership, token witnesses and reactive lifecycle: PASS (NOT-INFERENCE)");
    return 0;
}
