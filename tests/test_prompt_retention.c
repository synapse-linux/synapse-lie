/* SPDX-License-Identifier: MIT */
/* Tiny model-neutral pressure/restart fixtures. NOT-INFERENCE. */
#include "lie/core.h"
#include "fake_executor.h"
#include <assert.h>
#include <dirent.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static void pause_short(void){struct timespec t={0,1000000};nanosleep(&t,NULL);}
static lie_core_info wait_state(lie_core *c,lie_core_state target){
    lie_core_info i={0};
    for(unsigned n=0;n<5000;++n){lie_core_snapshot(c,&i);if(i.state==target)return i;pause_short();}
    assert(!"core deadline");return i;
}
static uint64_t state_bytes(unsigned n){
    lie_model_options o={LIE_EXECUTOR_ABI,sizeof(o),128,4,LIE_ROPE_NATIVE};lie_model *m=NULL;
    lie_sequence *s=NULL;lie_error error={0};lie_state_layout layout;uint64_t bytes=0;
    int32_t tokens[128]={0};
    assert(lie_backend_open(":fixture:",&o,&m,&error)==LIE_OK);
    assert(lie_sequence_create(m,&s,&error)==LIE_OK);
    for(unsigned k=0;k<n;){k=n-k>4?k+4:n;assert(lie_sequence_prefill(s,tokens,k,&error)==LIE_OK);}
    assert(lie_state_plan(s,&layout,&bytes,&error)==LIE_OK);
    assert(lie_sequence_close(&s,&error)==LIE_OK&&lie_model_close(&m,&error)==LIE_OK);
    return bytes;
}
static lie_core *start(uint64_t bytes,const char *path){
    lie_core_options o;lie_core_options_init(&o);o.model_path=":fixture:";
    o.context=128;o.chunk=4;o.max_active=2;o.prefix_cache_bytes=bytes;
    o.cache_policy=(lie_cache_policy){.enabled=true,.capture_finish=true,.min_tokens=4,
        .cold_max_tokens=8,.continued_interval_tokens=4,.boundary_align_tokens=4};
    /* Bounded opaque client trailers make two tiny files exceed this quota. */
    if(path)o.ssd=(lie_store_options){path,65536,1024u*1024u};
    lie_core *c=lie_core_create(&o);assert(c);wait_state(c,LIE_READY);return c;
}
static lie_core_info stop(lie_core *c){
    lie_core_stop(c);lie_core_info i=wait_state(c,LIE_STOPPED);
    assert(!i.failed_requests&&!i.ssd.errors&&!i.ssd.pending&&!i.ssd.staging_bytes);
    assert(!i.cache.entries&&!i.cache.retained_bytes);lie_core_destroy(c);return i;
}
static lie_job_info run_ex(lie_core *c,const int32_t *tokens,size_t n,uint32_t flags,bool fresh_output,bool disk_metadata){
    lie_core_request r;lie_core_request_init(&r);r.kind=LIE_INPUT_TOKENS;
    r.tokens=tokens;r.token_count=n;r.max_tokens=8;r.cache.flags=flags;
    if(flags){r.cache.text="visible prompt";r.cache.text_bytes=strlen(r.cache.text);}
    static const unsigned char trailer[32768]={1,2,3};
    if(disk_metadata){r.cache.trailer=trailer;r.cache.trailer_bytes=sizeof(trailer);}
    lie_job *j=NULL;assert(!lie_core_submit(c,&r,&j));bool ended=false;
    for(unsigned k=0;k<8000;++k){lie_flow_event event;
        lie_flow_status rc=lie_flow_next(lie_job_flow(j),&event);
        if(rc==LIE_FLOW_WOULD_BLOCK){struct pollfd fd={lie_flow_fd(lie_job_flow(j),LIE_FLOW_OUTPUT_READY),POLLIN,0};
            assert(poll(&fd,1,1)>=0);assert(lie_flow_drain(lie_job_flow(j),LIE_FLOW_OUTPUT_READY)==LIE_FLOW_OK);continue;}
        assert(rc==LIE_FLOW_OK);
        if(event.end!=LIE_FLOW_ACTIVE){assert(event.end==LIE_FLOW_COMPLETE);ended=true;break;}
        assert(lie_flow_release(lie_job_flow(j),event.ticket)==LIE_FLOW_OK);
        (void)lie_flow_request(lie_job_flow(j),event.tokens);
    }
    assert(ended);lie_job_info i;lie_job_snapshot(j,&i);
    assert(i.timing_valid&&i.prompt_tokens==n&&i.cached_tokens+i.prefill_tokens==n);
    if(fresh_output)assert(i.output_tokens==8);
    else assert(!i.output_tokens&&i.finish==LIE_FINISH_STOP); /* Fixture's saved EOS. */
    if(fresh_output){int32_t output[8];size_t count=0;
        assert(lie_job_output_tokens(j,output,8,&count)==LIE_OK&&count==8);
        for(unsigned k=0;k<8;++k)assert(output[k]==(int32_t)k);
    }
    lie_job_release(j);return i;
}
static lie_job_info run(lie_core *c,const int32_t *tokens,size_t n,uint32_t flags,bool fresh_output){
    return run_ex(c,tokens,n,flags,fresh_output,false);
}
static void child(const char *self,const char *mode,const char *path){
    pid_t p=fork();assert(p>=0);if(!p){execl(self,self,mode,path,(char *)NULL);_exit(127);}
    int status;assert(waitpid(p,&status,0)==p&&WIFEXITED(status)&&WEXITSTATUS(status)==0);
}
static void clean(const char *path){
    DIR *d=opendir(path);assert(d);struct dirent *e;
    while((e=readdir(d)))if(strcmp(e->d_name,".")&&strcmp(e->d_name,".."))assert(!unlinkat(dirfd(d),e->d_name,0));
    closedir(d);assert(!rmdir(path));
}
int main(int argc,char **argv){
    if(!LIE_DS4_CACHE_POLICY){puts("Progressive policy compiled out (NOT-INFERENCE)");return 0;}
    int32_t a[21]={0},b[13]={0};for(unsigned k=1;k<13;++k){a[k]=10;b[k]=20;}
    for(unsigned k=0;k<8;++k)a[13+k]=(int32_t)k;
    if(argc==3){
        bool reader=!strcmp(argv[1],"read");lie_core *c=start(0,argv[2]);
        lie_job_info i=run_ex(c,a,13,0,true,true);
        assert(i.cached_tokens==(reader?13u:0u)&&i.ssd_cached_tokens==i.cached_tokens);
        lie_core_info ci=stop(c);assert(ci.ssd.entries==1&&ci.ssd.skipped>=2&&!ci.ssd.errors);
        if(reader)assert(!ci.ssd.writes&&!ci.ssd.evictions);
        return 0;
    }
    assert(argc==1);uint64_t one=state_bytes(32);lie_core_info ci;
    /* The complete, unaligned prompt fits, as does a generated checkpoint;
     * the two cannot coexist. Repetition must need no prefill after retirement. */
    lie_core *c=start(one,NULL);lie_job_info i=run(c,a,13,0,true);assert(!i.cached_tokens);
    lie_core_snapshot(c,&ci);assert(ci.cache.entries==1&&ci.cache.captures==4&&ci.cache.skipped>=2);
    for(unsigned k=0;k<3;++k){i=run(c,a,13,0,true);assert(i.cached_tokens==13&&!i.prefill_calls);}
    lie_core_snapshot(c,&ci);assert(ci.cache.retained_bytes==state_bytes(13)&&ci.cache.peak_retained_bytes<=one);
    /* Protection belongs to a single capture, not a permanently pinned entry. */
    assert(!run(c,b,13,0,true).cached_tokens);assert(run(c,b,13,0,true).cached_tokens==13);
    assert(!run(c,a,13,0,true).cached_tokens);
    stop(c);
    /* When only a shorter waypoint fits, decode must not discard that fallback. */
    c=start(state_bytes(8),NULL);run(c,a,13,0,true);i=run(c,a,13,0,true);
    assert(i.cached_tokens==8&&i.prefill_tokens==5);stop(c);
    /* Ample budget still retains generated frontiers for conversation growth. */
    c=start(one*16,NULL);run(c,a,13,0,true);
    assert(run(c,a,21,0,false).cached_tokens==21);stop(c);
    /* Visibility-kind isolation remains intact even for identical tokens. */
    c=start(one,NULL);run(c,a,13,LIE_CACHE_RESPONSES_VISIBLE,true);
    assert(!run(c,a,13,LIE_CACHE_THINKING_VISIBLE,true).cached_tokens);
    assert(run(c,a,13,LIE_CACHE_THINKING_VISIBLE,true).cached_tokens==13);stop(c);
    /* Independent processes prove protected disk state survives shutdown and
     * restart with RAM disabled. Both native and synthetic KVC files run here. */
    char cwd[2048],base[2200],path[2300];assert(getcwd(cwd,sizeof(cwd)));
    snprintf(base,sizeof(base),"%s/prompt-retention-XXXXXX",cwd);assert(mkdtemp(base));
    snprintf(path,sizeof(path),"%s/store",base);
    child(argv[0],"write",path);child(argv[0],"read",path);
    c=start(one+65536,path);i=run_ex(c,a,13,0,true,true);assert(i.ssd_cached_tokens==13);
    i=run_ex(c,a,13,0,true,true);assert(i.cached_tokens==13&&!i.ssd_cached_tokens);stop(c);
    clean(path);
    /* Visible prompt keys must remain protected even though generated raw
     * checkpoints intentionally have a different key kind. */
    for(unsigned process=0;process<2;++process){
        c=start(0,path);i=run_ex(c,a,13,LIE_CACHE_RESPONSES_VISIBLE,true,true);
        assert(i.ssd_cached_tokens==(process?13u:0u));ci=stop(c);
        assert(ci.ssd.entries==1&&ci.ssd.skipped>=2);
    }
    clean(path);assert(!rmdir(base));
    puts("Prompt retention under RAM/SSD pressure, restart and key isolation: PASS (NOT-INFERENCE)");
    return 0;
}
