/* SPDX-License-Identifier: MIT */
/* Policy/serialization/reactive fixtures only. NOT-INFERENCE. */
#include "lie/core.h"
#include "../src/retention.h"
#include "../src/state_codec.h"
#include "fake_executor.h"
#include <assert.h>
#include <dirent.h>
#include <fcntl.h>
#include <math.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static lie_store_result wait_store(lie_store *s){
    lie_store_result r={0};
    for(unsigned i=0;i<5000;++i){if(lie_store_take(s,&r))return r;
        struct pollfd fd={lie_store_fd(s),POLLIN,0};assert(poll(&fd,1,1)>=0);}
    assert(!"store deadline");return r;
}
static lie_state *state(lie_model *m,int32_t value){
    lie_sequence *s=NULL;lie_error e={0};lie_state_layout l;uint64_t bytes;lie_state *p=NULL;
    int32_t tokens[]={0,value,value,value};
    assert(lie_sequence_create(m,&s,&e)==LIE_OK&&lie_sequence_prefill(s,tokens,4,&e)==LIE_OK);
    assert(lie_state_plan(s,&l,&bytes,&e)==LIE_OK&&lie_state_capture(s,&l,bytes,&p,&e)==LIE_OK);
    assert(lie_sequence_close(&s,&e)==LIE_OK);return p;
}
static lie_core_info wait_core(lie_core *c,lie_core_state target){
    lie_core_info i={0};for(unsigned n=0;n<5000;++n){lie_core_snapshot(c,&i);if(i.state==target)return i;
        struct pollfd fd={lie_core_fd(c),POLLIN,0};assert(poll(&fd,1,1)>=0);lie_core_drain(c);}
    assert(!"core deadline");return i;
}
static void drain(lie_job *j){
    for(unsigned i=0;i<5000;++i){lie_flow_event event;lie_flow_status rc=lie_flow_next(lie_job_flow(j),&event);
        if(rc==LIE_FLOW_WOULD_BLOCK){struct pollfd fd={lie_flow_fd(lie_job_flow(j),LIE_FLOW_OUTPUT_READY),POLLIN,0};
            assert(poll(&fd,1,1)>=0);assert(lie_flow_drain(lie_job_flow(j),LIE_FLOW_OUTPUT_READY)==LIE_FLOW_OK);continue;}
        assert(rc==LIE_FLOW_OK);if(event.end!=LIE_FLOW_ACTIVE){assert(event.end==LIE_FLOW_COMPLETE);return;}
        assert(lie_flow_release(lie_job_flow(j),event.ticket)==LIE_FLOW_OK);(void)lie_flow_request(lie_job_flow(j),event.tokens);
    }
    assert(!"flow deadline");
}
static void clean(const char *path){
    DIR *d=opendir(path);assert(d);struct dirent *e;
    while((e=readdir(d)))if(strcmp(e->d_name,".")&&strcmp(e->d_name,".."))assert(!unlinkat(dirfd(d),e->d_name,0));
    closedir(d);assert(!rmdir(path));
}
int main(void){
    lie_cache_policy policy;lie_cache_policy_init(&policy);
    assert(policy.min_tokens==512&&lie_cache_continued_step(&policy)==10240);
    assert(lie_cache_store_len(&policy,8192)==6144);
    assert(lie_cache_policy_option(&policy,"--cache-min-tokens","-1")==-1);
    assert(lie_cache_policy_option(&policy,"--cache-min-tokens","4294967296")==-1);
    assert(lie_cache_policy_option(&policy,"--cache-text-prefix","off")==1&&!policy.text_prefix);
    if(LIE_CACHE_UTILITY){
        lie_retention p={.created=100,.touched=100,.hits=10,.reason=LIE_CACHE_COLD};
        assert(fabs(lie_retention_score(&p,100,100,100,false)-22)<1e-12);
        assert(fabs(lie_retention_score(&p,21700,100,100,false)-12)<1e-12);
        assert(fabs(lie_retention_score(&p,50,100,100,false)-22)<1e-12);
        p.reason=LIE_CACHE_CONTINUED;
        assert(fabs(lie_retention_score(&p,100,100,100,true)-5.05)<1e-12);
    }
    char cwd[2048],base[2200],path[2300];assert(getcwd(cwd,sizeof(cwd)));
    snprintf(base,sizeof(base),"%s/ds4-policy-XXXXXX",cwd);assert(mkdtemp(base));snprintf(path,sizeof(path),"%s/store",base);
    lie_model_options mo={LIE_EXECUTOR_ABI,sizeof(mo),128,4};lie_model *m=NULL;lie_error error={0};
    assert(lie_backend_open(":fixture:",&mo,&m,&error)==LIE_OK);
    lie_state *p=state(m,10);uint64_t domain=lie_state_description(p)->domain;lie_state_identity id={{4}};
    lie_store_options options={path,1024u*1024u,1024u*1024u};lie_store *store=NULL;
    assert(lie_store_open(&options,&id,domain,&store,&error)==LIE_OK);
    const unsigned char trailer[]={0,1,0,255};
    lie_cache_metadata metadata={.reason=LIE_CACHE_COLD,.flags=LIE_CACHE_TOOL_MAP,.text="abcd",.text_bytes=4,.trailer=trailer,.trailer_bytes=sizeof(trailer)};
    /* Immutable metadata is digest-bound; advisory hit updates remain readable. */
    char file[2300];snprintf(file,sizeof(file),"%s/metadata",base);
    int fd=open(file,O_RDWR|O_CREAT|O_EXCL,0600);assert(fd>=0);
    assert(lie_state_file_write_ex(fd,&id,p,&metadata,NULL));
    assert(lie_state_file_touch(fd,&id,42,1234));
    lie_state *copy=lie_state_file_read(fd,&id,domain,1024u*1024u,NULL);assert(copy);lie_state_destroy(&copy);
    lie_cache_metadata got={0};assert(lie_state_file_metadata(fd,&id,1024,&got));
    assert(got.hits==42&&got.last_used==1234);lie_cache_metadata_clear(&got);
    off_t last=(off_t)lie_state_file_bytes_ex(p,&metadata)-1;unsigned char flipped=1;
    assert(pwrite(fd,&flipped,1,last)==1&&!lie_state_file_read(fd,&id,domain,1024u*1024u,NULL));
    assert(!close(fd)&&!unlink(file));
    assert(lie_store_write_ex(store,p,&metadata));lie_state_destroy(&p);lie_store_result r=wait_store(store);lie_store_result_release(store,&r);
    for(unsigned i=0;i<8;++i){assert(lie_store_read_text(store,"abcdef",6,4));r=wait_store(store);
        assert(r.state&&r.metadata.hits==i+1&&r.metadata.reason==LIE_CACHE_COLD&&r.metadata.created_at&&r.metadata.last_used);
        assert(r.metadata.text_bytes==4&&r.metadata.trailer_bytes==sizeof(trailer)&&!memcmp(r.metadata.trailer,trailer,sizeof(trailer)));
        lie_store_result_release(store,&r);}
    assert(lie_store_read_text_key(store,"abcdef",6,4,LIE_CACHE_RESPONSES_VISIBLE));r=wait_store(store);
    assert(!r.state);lie_store_result_release(store,&r);
    for(int value=11;value<91;++value){p=state(m,value);assert(lie_store_write(store,p));lie_state_destroy(&p);r=wait_store(store);lie_store_result_release(store,&r);}
    lie_store_info info;lie_store_snapshot(store,&info);assert(info.entries==81&&!info.evictions&&info.index_bytes<=info.index_budget_bytes);
    lie_store_close(&store);
    /* Policy history persists across restart and a reduced quota is enforced. */
    options.quota_bytes=8192;assert(lie_store_open(&options,&id,domain,&store,&error)==LIE_OK);
    lie_store_snapshot(store,&info);assert(info.entries==2&&info.allocated_bytes<=8192);
    assert(lie_store_read_text(store,"abcdef",6,4));r=wait_store(store);
    if(LIE_CACHE_UTILITY)assert(r.state&&r.metadata.hits==9);
    lie_store_result_release(store,&r);lie_store_close(&store);clean(path);
    assert(lie_model_close(&m,&error)==LIE_OK);

    if(LIE_DS4_CACHE_POLICY){
        lie_core_options o;lie_core_options_init(&o);o.model_path=":fixture:";o.context=128;o.chunk=4;
        o.cache_policy=(lie_cache_policy){.enabled=true,.capture_finish=true,.min_tokens=4,.cold_max_tokens=8,
            .continued_interval_tokens=4,.boundary_align_tokens=4};
        o.ssd=(lie_store_options){path,1024u*1024u,1024u*1024u};
        lie_core *core=lie_core_create(&o);assert(core);wait_core(core,LIE_READY);
        int32_t tokens[]={0,10,10,10,10,10,10,10,10,10,10,10};
        lie_core_request request;lie_core_request_init(&request);request.kind=LIE_INPUT_TOKENS;
        request.tokens=tokens;request.token_count=12;request.max_tokens=8;
        lie_job *job=NULL;assert(!lie_core_submit(core,&request,&job));drain(job);lie_job_release(job);
        lie_core_stop(core);lie_core_info ci=wait_core(core,LIE_STOPPED);
        assert(ci.completed_requests==1&&!ci.failed_requests&&ci.ssd.writes==5&&ci.cache.captures==5);
        lie_core_destroy(core);clean(path);
        /* Stop during prefill captures the last completed frontier, drains the
         * asynchronous writer, then cancels the request and closes the model. */
        o.cache_policy=(lie_cache_policy){.enabled=true,.capture_finish=true,.min_tokens=4};
        core=lie_core_create(&o);assert(core);wait_core(core,LIE_READY);
        fake_barrier_arm_phase(FAKE_PREFILL);job=NULL;
        assert(!lie_core_submit(core,&request,&job));fake_barrier_wait();
        lie_core_stop(core);fake_barrier_release();ci=wait_core(core,LIE_STOPPED);
        assert(ci.ssd.writes==1&&!ci.ssd.pending&&ci.cancelled_requests==1&&!ci.failed_requests);
        lie_job_release(job);lie_core_destroy(core);
        assert(lie_backend_open(":fixture:",&mo,&m,&error)==LIE_OK);
        assert(lie_model_state_identity(m,&id,&domain,&error)==LIE_OK);
        options=(lie_store_options){path,1024u*1024u,1024u*1024u};
        assert(lie_store_open(&options,&id,domain,&store,&error)==LIE_OK);
        assert(lie_store_read(store,tokens,12,4));r=wait_store(store);
        assert(r.state&&lie_state_description(r.state)->token_count==4&&r.metadata.reason==LIE_CACHE_SHUTDOWN);
        lie_store_result_release(store,&r);lie_store_close(&store);clean(path);
        assert(lie_model_close(&m,&error)==LIE_OK);
        /* A byte-prefix hit survives a different BPE boundary and retokenizes
         * only the suffix, first in RAM and then after an SSD restart. */
        fake_tokenizer_merge(true);o.cache_policy=(lie_cache_policy){.enabled=true,.text_prefix=true,.min_tokens=4,.cold_max_tokens=4};
        for(unsigned process=0;process<2;++process){
            o.context=process?256:128; /* Smaller saved context admitted into a larger one. */
            core=lie_core_create(&o);assert(core);wait_core(core,LIE_READY);
            for(unsigned request_index=process?1:0;request_index<2;++request_index){
                lie_core_request_init(&request);request.kind=LIE_INPUT_TEXT;request.text=request_index?"abcdx":"abcd";
                request.text_bytes=strlen(request.text);request.max_tokens=4;
                request.cache=(lie_cache_metadata){.flags=LIE_CACHE_TOOL_MAP,.trailer=trailer,.trailer_bytes=sizeof(trailer)};
                job=NULL;assert(!lie_core_submit(core,&request,&job));drain(job);
                lie_job_info ji;lie_job_snapshot(job,&ji);
                if(request_index){assert(ji.cached_tokens==4&&ji.prefill_tokens==1&&ji.prompt_tokens==5);
                    assert(ji.ssd_cached_tokens==(process?4u:0u));
                    lie_cache_metadata got={0};assert(lie_job_cache_metadata(job,&got));
                    assert(got.flags==LIE_CACHE_TOOL_MAP&&got.trailer_bytes==sizeof(trailer)&&!memcmp(got.trailer,trailer,sizeof(trailer)));
                    lie_cache_metadata_clear(&got);
                }
                lie_job_release(job);
            }
            lie_core_stop(core);wait_core(core,LIE_STOPPED);lie_core_destroy(core);
        }
        fake_tokenizer_merge(false);clean(path);
        /* Identical physical tokens cannot bypass a visible-key-kind miss. */
        o.ssd=(lie_store_options){0};core=lie_core_create(&o);assert(core);wait_core(core,LIE_READY);
        for(unsigned k=0;k<3;++k){
            lie_core_request_init(&request);request.kind=LIE_INPUT_TEXT;request.text="abcd";request.text_bytes=4;request.max_tokens=4;
            request.cache=(lie_cache_metadata){.text="abcd",.text_bytes=4,.flags=k?LIE_CACHE_THINKING_VISIBLE:LIE_CACHE_RESPONSES_VISIBLE};
            job=NULL;assert(!lie_core_submit(core,&request,&job));drain(job);
            lie_job_info ji;lie_job_snapshot(job,&ji);assert(ji.cached_tokens==(k==2?4u:0u));lie_job_release(job);
        }
        lie_core_stop(core);wait_core(core,LIE_STOPPED);lie_core_destroy(core);
        /* A disabled cache adds neither prompt rendering nor policy splits. */
        o.prefix_cache_bytes=0;o.cache_policy.min_tokens=1;o.cache_policy.cold_max_tokens=3;
        o.cache_policy.continued_interval_tokens=3;o.cache_policy.boundary_align_tokens=0;
        fake_calls_reset();core=lie_core_create(&o);assert(core);wait_core(core,LIE_READY);
        lie_core_request_init(&request);request.kind=LIE_INPUT_TEXT;request.text="abcdefghijkl";request.text_bytes=12;request.max_tokens=4;
        job=NULL;assert(!lie_core_submit(core,&request,&job));drain(job);lie_job_info no_cache;lie_job_snapshot(job,&no_cache);
        assert(no_cache.prefill_calls==3&&fake_calls_snapshot().text==4&&!fake_calls_snapshot().capture);lie_job_release(job);
        lie_core_stop(core);wait_core(core,LIE_STOPPED);lie_core_destroy(core);
    }
    assert(!rmdir(base));puts("DS4 policy formulas, persistent utility, dynamic index, text keys, trailers, quota and progressive captures: PASS (NOT-INFERENCE)");return 0;
}
