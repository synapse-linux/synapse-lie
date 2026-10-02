/* SPDX-License-Identifier: MIT */
/* Synthetic core restart/reactive/cancellation checks. NOT-INFERENCE. */
#include "lie/core.h"
#include "fake_executor.h"
#include <assert.h>
#include <dirent.h>
#include <poll.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static atomic_bool held,entered;
static void pause_short(void){struct timespec t={0,1000000};nanosleep(&t,NULL);}
ssize_t __real_pread(int,void *,size_t,off_t);
ssize_t __wrap_pread(int fd,void *out,size_t bytes,off_t offset){
    if(atomic_load(&held)){atomic_store(&entered,true);while(atomic_load(&held))pause_short();}
    return __real_pread(fd,out,bytes,offset);
}
static void wait_read(void){for(unsigned i=0;i<4000;++i){if(atomic_load(&entered))return;pause_short();}assert(!"read barrier deadline");}
static lie_core_info wait_state(lie_core *c,lie_core_state target){
    lie_core_info i;
    for(unsigned n=0;n<5000;++n){lie_core_snapshot(c,&i);if(i.state==target)return i;pause_short();}
    assert(!"core state deadline");return i;
}
static lie_core *start(const char *path,uint64_t ram){
    lie_core_options o;lie_core_options_init(&o);o.cache_policy.enabled=false;o.model_path=":fixture:";o.context=128;o.chunk=4;o.max_active=2;
    o.prefix_cache_bytes=ram;if(path)o.ssd=(lie_store_options){path,1024*1024,65536};
    lie_core *c=lie_core_create(&o);assert(c);wait_state(c,LIE_READY);return c;
}
static lie_core_info stop(lie_core *c){lie_core_stop(c);lie_core_info i=wait_state(c,LIE_STOPPED);assert(!i.ssd.pending&&!i.ssd.staging_bytes);lie_core_destroy(c);return i;}
static lie_job *submit(lie_core *c,const int32_t *tokens,size_t n,unsigned output){
    lie_core_request r;lie_core_request_init(&r);r.kind=LIE_INPUT_TOKENS;r.tokens=tokens;r.token_count=n;r.max_tokens=output;
    lie_job *j=NULL;assert(!lie_core_submit(c,&r,&j)&&j);return j;
}
static lie_job_info consume(lie_job *j,lie_flow_end end){
    bool finished=false;unsigned count=0;
    for(unsigned n=0;n<8000;++n){lie_flow_event e;lie_flow_status rc=lie_flow_next(lie_job_flow(j),&e);
        if(rc==LIE_FLOW_WOULD_BLOCK){struct pollfd fd={lie_flow_fd(lie_job_flow(j),LIE_FLOW_OUTPUT_READY),POLLIN,0};
            assert(poll(&fd,1,1)>=0);assert(lie_flow_drain(lie_job_flow(j),LIE_FLOW_OUTPUT_READY)==LIE_FLOW_OK);continue;}
        assert(rc==LIE_FLOW_OK);if(e.end!=LIE_FLOW_ACTIVE){assert(e.end==end);finished=true;break;}
        count+=(unsigned)e.tokens;assert(lie_flow_release(lie_job_flow(j),e.ticket)==LIE_FLOW_OK);(void)lie_flow_request(lie_job_flow(j),e.tokens);
    }
    assert(finished);lie_job_info info;lie_job_snapshot(j,&info);
    if(end==LIE_FLOW_COMPLETE){assert(info.output_tokens==count&&info.prefill_tokens+info.cached_tokens==info.prompt_tokens);
        int32_t tokens[32];size_t used=0;assert(lie_job_output_tokens(j,tokens,32,&used)==LIE_OK&&used==count);}
    lie_job_release(j);return info;
}
static void child(const char *self,const char *mode,const char *path){
    pid_t pid=fork();assert(pid>=0);if(!pid){execl(self,self,mode,path,(char *)NULL);_exit(127);}
    int status=0;assert(waitpid(pid,&status,0)==pid&&WIFEXITED(status)&&WEXITSTATUS(status)==0);
}
static void clean(const char *path){
    DIR *d=opendir(path);assert(d);struct dirent *entry;
    while((entry=readdir(d)))if(strcmp(entry->d_name,".")&&strcmp(entry->d_name,".."))assert(!unlinkat(dirfd(d),entry->d_name,0));
    closedir(d);assert(!rmdir(path));
}
int main(int argc,char **argv){
    int32_t a[]={0,10,10,10,20,20,20,20},b[]={1,30,30,30};lie_job_info i;
    if(argc==3){
        lie_core *c=start(argv[2],0);i=consume(submit(c,a,4,8),LIE_FLOW_COMPLETE);
        bool restore=!strcmp(argv[1],"restore");assert(i.ssd_cached_tokens==(restore?4u:0u)&&i.prefill_tokens==(restore?0u:4u));
        lie_core_info ci=stop(c);assert(restore?ci.ssd.hits==1:ci.ssd.writes==1);return 0;
    }
    assert(argc==1);char cwd[2048],base[2200],path[2300];assert(getcwd(cwd,sizeof(cwd)));
    snprintf(base,sizeof(base),"%s/ssd-core-XXXXXX",cwd);assert(mkdtemp(base));snprintf(path,sizeof(path),"%s/store",base);
    child(argv[0],"seed",path);child(argv[0],"restore",path); /* Real process exit/restart. */
    fake_calls_reset();lie_core *c=start(path,0);
    i=consume(submit(c,a,8,8),LIE_FLOW_COMPLETE);assert(i.ssd_cached_tokens==4&&i.prefill_tokens==4&&i.ssd_read_ns&&i.cache_restore_ns);
    lie_core_info ci=stop(c);assert(ci.ssd.writes==1&&!ci.cache.entries&&fake_calls_snapshot().restore==1);
    c=start(path,LIE_PREFIX_CACHE_DEFAULT_BYTES);
    i=consume(submit(c,a,8,8),LIE_FLOW_COMPLETE);assert(i.ssd_cached_tokens==8&&!i.prefill_tokens);
    i=consume(submit(c,a,8,8),LIE_FLOW_COMPLETE);assert(!i.ssd_cached_tokens&&i.cached_tokens==8);stop(c);
    /* Disabled SSD never reads the existing store, even with matching tokens. */
    c=start(NULL,LIE_PREFIX_CACHE_DEFAULT_BYTES);i=consume(submit(c,a,4,8),LIE_FLOW_COMPLETE);assert(!i.cached_tokens);stop(c);

    /* A disk read cannot stall an already runnable inference row. Give B eight
     * more credits while A's I/O thread is deliberately blocked in pread. */
    c=start(path,LIE_PREFIX_CACHE_DEFAULT_BYTES);lie_job *peer=submit(c,b,4,16);
    for(unsigned n=0;n<4000;++n){lie_core_snapshot(c,&ci);if(ci.output_blocked&&!ci.ssd.pending)break;pause_short();}
    assert(ci.output_blocked==1&&!ci.ssd.pending);
    atomic_store(&entered,false);atomic_store(&held,true);lie_job *pending=submit(c,a,8,8);wait_read();
    i=consume(peer,LIE_FLOW_COMPLETE);assert(i.output_tokens==16); /* Still held: pure inference progressed. */
    lie_job_cancel(pending);consume(pending,LIE_FLOW_CANCELLED);
    atomic_store(&held,false);stop(c);

    /* A mutating upload failure poisons the core; it cannot turn into prefill. */
    fake_calls_reset();c=start(path,0);fake_state_fault(3);
    consume(submit(c,a,8,8),LIE_FLOW_ERROR);wait_state(c,LIE_FAILED);
    fake_calls calls=fake_calls_snapshot();assert(calls.restore==1&&!calls.prefill&&!calls.decode);stop(c);fake_calls_reset();
    clean(path);assert(!rmdir(base));
    puts("Shared core SSD process restart, RAM promotion, reactive progress and cancellation: PASS (NOT-INFERENCE)");return 0;
}
