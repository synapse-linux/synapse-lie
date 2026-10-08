/* SPDX-License-Identifier: MIT */
/* Shared-engine live configuration and semantic cache isolation. NOT-INFERENCE. */
#include "lie/core.h"
#include "fake_executor.h"
#include <assert.h>
#include <dirent.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static void pause_short(void) {
    struct timespec t={0,1000000}; nanosleep(&t,NULL);
}
static lie_core_info state(lie_core *c,lie_core_state wanted) {
    lie_core_info i={0};
    for(unsigned n=0;n<4000;++n) {
        lie_core_snapshot(c,&i);
        if(i.state==wanted)return i;
        pause_short();
    }
    assert(!"core state deadline"); return i;
}
static lie_core *start_full(unsigned chunk,unsigned capacity,unsigned context,bool cache,const char *disk) {
    fake_calls_reset();
    lie_core_options o; lie_core_options_init(&o);
    o.model_path=":fixture:"; o.context=context; o.chunk=chunk; o.max_active=1;
    o.cache_policy.enabled=false; o.prefix_cache_bytes=cache?1024u*1024u:0;
    if(disk)o.ssd=(lie_store_options){disk,1024u*1024u,65536};
    lie_prefill_options p; lie_prefill_options_init(&p); p.capacity_tokens=capacity;
    lie_core *c=lie_core_create_prefill(&o,&p,NULL); assert(c);
    lie_core_info i=state(c,LIE_READY);
    assert(i.model.prefill_capacity==capacity);
    return c;
}
static lie_core *start(unsigned chunk,unsigned capacity,unsigned context,bool cache) {
    return start_full(chunk,capacity,context,cache,NULL);
}
static void stop(lie_core *c) {
    lie_core_stop(c); state(c,LIE_STOPPED);
    assert(lie_core_set_prefill_chunk(c,1,NULL)==LIE_CANCELLED);
    lie_core_destroy(c);
    fake_calls f=fake_calls_snapshot(); assert(f.create==f.close);
}
static lie_prefill_info core_config(lie_core *c) {
    lie_prefill_info i; lie_prefill_info_init(&i);
    assert(lie_core_prefill_snapshot(c,&i,NULL)==LIE_OK); return i;
}
static lie_prefill_info job_config(lie_job *j) {
    lie_prefill_info i; lie_prefill_info_init(&i);
    assert(lie_job_prefill_snapshot(j,&i,NULL)==LIE_OK); return i;
}
static lie_job *submit(lie_core *c,const int32_t *tokens,size_t n) {
    lie_core_request r; lie_core_request_init(&r); r.kind=LIE_INPUT_TOKENS;
    r.tokens=tokens; r.token_count=n; r.max_tokens=2;
    lie_job *j=NULL; assert(!lie_core_submit(c,&r,&j)&&j); return j;
}
static lie_job_info consume(lie_job *j) {
    unsigned count=0; bool ended=false; lie_job_info i={0};
    for(unsigned n=0;n<8000&&!ended;++n) {
        lie_flow_event e; lie_flow_status rc=lie_flow_next(lie_job_flow(j),&e);
        if(rc==LIE_FLOW_WOULD_BLOCK) {
            struct pollfd fd={lie_flow_fd(lie_job_flow(j),LIE_FLOW_OUTPUT_READY),POLLIN,0};
            assert(poll(&fd,1,1)>=0);
            assert(lie_flow_drain(lie_job_flow(j),LIE_FLOW_OUTPUT_READY)==LIE_FLOW_OK);
            continue;
        }
        assert(rc==LIE_FLOW_OK);
        if(e.end!=LIE_FLOW_ACTIVE) {
            if(e.end!=LIE_FLOW_COMPLETE) {
                lie_job_snapshot(j,&i);
                fprintf(stderr,"Prefill job ended %u: %s (prompt=%u, prefill=%u, cached=%u)\n",
                    (unsigned)e.end,i.error,i.prompt_tokens,i.prefill_tokens,i.cached_tokens);
            }
            assert(e.end==LIE_FLOW_COMPLETE); ended=true; break;
        }
        assert(e.token_offset==count); count+=(unsigned)e.tokens;
        assert(lie_flow_release(lie_job_flow(j),e.ticket)==LIE_FLOW_OK);
        (void)lie_flow_request(lie_job_flow(j),e.tokens);
    }
    assert(ended&&count==2);
    for(unsigned n=0;n<4000;++n) {
        lie_job_snapshot(j,&i); if(i.retired)break; pause_short();
    }
    assert(i.retired&&i.timing_valid&&i.prefill_tokens+i.cached_tokens==i.prompt_tokens);
    return i;
}
static void contracts(void) {
    lie_core_options o; lie_core_options_init(&o); o.model_path=":fixture:";
    lie_prefill_options p; lie_prefill_options_init(&p);
    p.capacity_tokens=1; assert(!lie_core_create_prefill(&o,&p,NULL));
    p.capacity_tokens=LIE_PREFILL_MAX_CHUNK+1;
    assert(!lie_core_create_prefill(&o,&p,NULL));
    p.capacity_tokens=4096; ++p.abi_version;
    assert(!lie_core_create_prefill(&o,&p,NULL));
    lie_prefill_options_init(&p); --p.struct_bytes;
    assert(!lie_core_create_prefill(&o,&p,NULL));
    assert(lie_core_set_prefill_chunk(NULL,1,NULL)==LIE_INVALID);
    lie_prefill_info i; lie_prefill_info_init(&i);
    assert(lie_core_prefill_snapshot(NULL,&i,NULL)==LIE_INVALID);
    assert(lie_job_prefill_snapshot(NULL,&i,NULL)==LIE_INVALID);
    lie_core *c=start(16,64,512,false);
    i=core_config(c); assert(i.chunk_tokens==16&&i.capacity_tokens==64&&i.revision==1);
    assert(lie_core_set_prefill_chunk(c,16,NULL)==LIE_OK);
    assert(core_config(c).revision==1);
    assert(lie_core_set_prefill_chunk(c,0,NULL)==LIE_INVALID);
    assert(lie_core_set_prefill_chunk(c,LIE_PREFILL_MAX_CHUNK+1,NULL)==LIE_INVALID);
    assert(lie_core_set_prefill_chunk(c,65,NULL)==LIE_RESOURCE_LIMIT);
    assert(core_config(c).revision==1&&core_config(c).chunk_tokens==16);
    lie_prefill_info bad=i; ++bad.abi_version; lie_prefill_info before=bad;
    assert(lie_core_prefill_snapshot(c,&bad,NULL)==LIE_INVALID);
    assert(!memcmp(&bad,&before,sizeof(bad)));
    assert(lie_core_prefill_snapshot(c,NULL,NULL)==LIE_INVALID);
    stop(c);
    o.context=512;o.chunk=16;o.prefix_cache_bytes=0;o.model_path=":fixture-prefill-limit:";
    lie_prefill_options_init(&p);p.capacity_tokens=64;
    c=lie_core_create_prefill(&o,&p,NULL);assert(c);
    lie_core_info failed=state(c,LIE_FAILED);
    assert(strstr(failed.error,"requested prefill capacity"));
    assert(lie_core_set_prefill_chunk(c,8,NULL)==LIE_BACKEND_FAILED);
    stop(c);
}
static void running_and_queued(void) {
    lie_core *c=start(16,64,512,false);
    int32_t tokens[256]={0}; for(unsigned n=1;n<256;++n)tokens[n]=10;
    fake_barrier_arm_phase(FAKE_PREFILL);
    lie_job *a=submit(c,tokens,256); fake_barrier_wait();
    /* The setter must return while the numerical owner is blocked. */
    fake_calls before=fake_calls_snapshot();
    assert(lie_core_set_prefill_chunk(c,8,NULL)==LIE_OK);
    fake_calls after=fake_calls_snapshot(); assert(!memcmp(&before,&after,sizeof(before)));
    lie_job *b=submit(c,tokens,256);
    assert(lie_core_set_prefill_chunk(c,64,NULL)==LIE_OK);
    lie_job *d=submit(c,tokens,256);
    lie_prefill_info ai=job_config(a),bi=job_config(b),di=job_config(d);
    assert(ai.chunk_tokens==16&&ai.capacity_tokens==64&&ai.revision==1);
    assert(bi.chunk_tokens==8&&bi.revision==2);
    assert(di.chunk_tokens==64&&di.revision==3);
    lie_core_info ci; lie_core_snapshot(c,&ci); assert(ci.queued>=2);
    fake_barrier_release();
    lie_job_info ia=consume(a),ib=consume(b),id=consume(d);
    assert(ia.prefill_calls==16&&ib.prefill_calls==32&&id.prefill_calls==4);
    assert(job_config(a).chunk_tokens==16&&job_config(b).chunk_tokens==8);
    lie_job_release(a);lie_job_release(b);lie_job_release(d);stop(c);
}
static lie_job_info run(lie_core *c,const int32_t *tokens,size_t n) {
    lie_job *j=submit(c,tokens,n);lie_job_info i=consume(j);lie_job_release(j);return i;
}
static void cache_isolation(void) {
    lie_core *c=start(16,64,512,true);
    int32_t tokens[256]={0};for(unsigned n=1;n<256;++n)tokens[n]=10;
    assert(!run(c,tokens,256).cached_tokens);
    assert(run(c,tokens,256).cached_tokens==256);
    assert(lie_core_set_prefill_chunk(c,8,NULL)==LIE_OK);
    lie_job_info i=run(c,tokens,256);assert(!i.cached_tokens&&i.prefill_calls==32);
    assert(run(c,tokens,256).cached_tokens==256);
    assert(lie_core_set_prefill_chunk(c,16,NULL)==LIE_OK);
    assert(run(c,tokens,256).cached_tokens==256); /* Revision is not numerical identity. */
    assert(lie_core_set_prefill_chunk(c,64,NULL)==LIE_OK);
    i=run(c,tokens,256);assert(!i.cached_tokens&&i.prefill_calls==4);
    assert(run(c,tokens,256).cached_tokens==256);stop(c);
}
static void large_capacity(void) {
    int32_t *tokens=calloc(32768,sizeof(*tokens));assert(tokens);
    for(unsigned n=1;n<32768;++n)tokens[n]=10;
    lie_core *c=start(16384,32768,65536,false);
    assert(run(c,tokens,32768).prefill_calls==2);
    assert(lie_core_set_prefill_chunk(c,32768,NULL)==LIE_OK);
    assert(run(c,tokens,32768).prefill_calls==1);
    stop(c);free(tokens);
}
static void disk_idle(lie_core *c) {
    for(unsigned n=0;n<4000;++n) {
        lie_core_info i;lie_core_snapshot(c,&i);
        if(!i.ssd.pending)return;
        pause_short();
    }
    assert(!"disk deadline");
}
static void ssd_isolation(void) {
    char cwd[2048],directory[2300];assert(getcwd(cwd,sizeof(cwd)));
    assert(snprintf(directory,sizeof(directory),"%s/prefill-ssd-XXXXXX",cwd)<(int)sizeof(directory));
    assert(mkdtemp(directory));
    lie_core *c=start_full(16,64,512,false,directory);
    int32_t tokens[256]={0};for(unsigned n=1;n<256;++n)tokens[n]=10;
    assert(!run(c,tokens,256).ssd_cached_tokens);disk_idle(c);
    assert(run(c,tokens,256).ssd_cached_tokens==256);
    assert(lie_core_set_prefill_chunk(c,8,NULL)==LIE_OK);
    lie_job_info i=run(c,tokens,256);assert(!i.ssd_cached_tokens&&i.prefill_calls==32);disk_idle(c);
    assert(run(c,tokens,256).ssd_cached_tokens==256);
    assert(lie_core_set_prefill_chunk(c,16,NULL)==LIE_OK);
    assert(run(c,tokens,256).ssd_cached_tokens==256);stop(c);
    DIR *d=opendir(directory);assert(d);struct dirent *e;
    while((e=readdir(d))) {
        if(!strcmp(e->d_name,".")||!strcmp(e->d_name,".."))continue;
        char path[2600];assert(snprintf(path,sizeof(path),"%s/%s",directory,e->d_name)<(int)sizeof(path));
        assert(!unlink(path));
    }
    closedir(d);assert(!rmdir(directory));
}
int main(void) {
    contracts();running_and_queued();cache_isolation();ssd_isolation();large_capacity();
    puts("Live prefill chunk, queued-job isolation, reserved capacity and RAM/SSD cache: PASS (NOT-INFERENCE)");
    return 0;
}
