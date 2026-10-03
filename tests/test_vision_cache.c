/* SPDX-License-Identifier: MIT */
/* Semantic image-key isolation and process restart. NOT-INFERENCE. */
#include "lie/core.h"
#include "fake_executor.h"
#include "vision_fixture.h"
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
static lie_core_info ready(lie_core *c,lie_core_state target){
    lie_core_info i={0};for(unsigned n=0;n<5000;++n){lie_core_snapshot(c,&i);if(i.state==target)return i;pause_short();}
    fprintf(stderr,"Core state %d: %s\n",i.state,i.error);assert(!"core deadline");return i;
}
static lie_core *start(const char *family,const char *path,uint64_t ram){
    lie_core_options o;lie_core_options_init(&o);o.model_path=":fixture:";o.vision_model_path=family;o.context=128;o.chunk=4;o.max_active=2;
    o.prefix_cache_bytes=ram;o.cache_policy.min_tokens=1;o.cache_policy.boundary_trim_tokens=0;o.cache_policy.boundary_align_tokens=0;
    o.cache_policy.capture_finish=false;if(path)o.ssd=(lie_store_options){path,1u<<20,1u<<20};
    lie_core *c=lie_core_create(&o);assert(c);ready(c,LIE_READY);return c;
}
static lie_core_info stop(lie_core *c){lie_core_stop(c);lie_core_info i=ready(c,LIE_STOPPED);lie_core_destroy(c);assert(!i.ssd.errors);return i;}
static lie_job_info run(lie_core *c,unsigned mutation,unsigned placement,int32_t physical[128]){
    unsigned char *pixels=NULL;size_t bytes=0;lie_image_format f;
    assert(lie_image_data_url(image_url,strlen(image_url),&pixels,&bytes,&f,NULL)==LIE_OK);
    /* Header and final placeholder token are unchanged. Pixel payload differs
     * while the fixture's physical token vector is exactly equal. */
    pixels[40]^=(unsigned char)mutation;
    lie_image_input image={pixels,bytes,f,0,placement};lie_chat_message msg={LIE_CHAT_USER,"normal",6};
    lie_core_request r;lie_core_request_init(&r);r.chat.messages=&msg;r.chat.count=1;r.images=&image;r.image_count=1;r.max_tokens=4;
    lie_job *j=NULL;assert(!lie_core_submit(c,&r,&j));free(pixels);
    unsigned count=0;bool done=false;
    for(unsigned n=0;n<5000&&!done;++n){lie_flow_event e;lie_flow_status rc=lie_flow_next(lie_job_flow(j),&e);
        if(rc==LIE_FLOW_WOULD_BLOCK){struct pollfd fd={lie_flow_fd(lie_job_flow(j),LIE_FLOW_OUTPUT_READY),POLLIN,0};assert(poll(&fd,1,1)>=0);lie_flow_drain(lie_job_flow(j),LIE_FLOW_OUTPUT_READY);continue;}
        assert(rc==LIE_FLOW_OK);if(e.end!=LIE_FLOW_ACTIVE){if(e.end!=LIE_FLOW_COMPLETE){lie_job_info i;lie_job_snapshot(j,&i);fprintf(stderr,"Job failed: %s\n",i.error);}assert(e.end==LIE_FLOW_COMPLETE);done=true;continue;}
        assert(e.token_offset==count);count+=(unsigned)e.tokens;assert(lie_flow_release(lie_job_flow(j),e.ticket)==LIE_FLOW_OK);lie_flow_request(lie_job_flow(j),e.tokens);
    }
    assert(done&&count==4);lie_job_info info;lie_job_snapshot(j,&info);size_t n=0;
    assert(lie_job_prompt_tokens(j,physical,128,&n)==LIE_OK&&n==info.prompt_tokens);
    assert(info.prefill_tokens+info.cached_tokens==info.prompt_tokens&&info.output_tokens==4);
    int32_t ids[4];assert(lie_job_output_tokens(j,ids,4,&n)==LIE_OK&&n==4);for(unsigned k=0;k<4;++k)assert(ids[k]==(int32_t)k);
    lie_job_release(j);return info;
}
static void family(const char *name,unsigned tokens){
    fake_calls_reset();lie_core *c=start(name,NULL,LIE_PREFIX_CACHE_DEFAULT_BYTES);int32_t a[128],b[128];
    assert(!run(c,0,3,a).cached_tokens);assert(run(c,0,3,b).cached_tokens==tokens);
    assert(!memcmp(a,b,tokens*sizeof(*a)));
    unsigned before=fake_calls_snapshot().restore;
    assert(!run(c,3,3,b).cached_tokens&&!memcmp(a,b,tokens*sizeof(*a)));
    assert(fake_calls_snapshot().restore==before); /* A miss never uploads. */
    assert(run(c,0,3,b).cached_tokens==tokens);
    assert(!run(c,0,1,b).cached_tokens&&!memcmp(a,b,tokens*sizeof(*a)));
    assert(run(c,0,3,b).cached_tokens==tokens);
    lie_core_info i=stop(c);assert(i.cache.captures==3&&i.cache.hits==3);
}
static void child(const char *self,const char *mode,const char *family,const char *path){
    pid_t p=fork();assert(p>=0);if(!p){execl(self,self,mode,family,path,(char *)NULL);_exit(127);}int status;assert(waitpid(p,&status,0)==p&&WIFEXITED(status)&&WEXITSTATUS(status)==0);
}
static void clean(const char *path){DIR *d=opendir(path);assert(d);struct dirent *e;while((e=readdir(d)))if(strcmp(e->d_name,".")&&strcmp(e->d_name,".."))assert(!unlinkat(dirfd(d),e->d_name,0));closedir(d);assert(!rmdir(path));}
int main(int argc,char **argv){
    if(argc==4){lie_core *c=start(argv[2],argv[3],0);unsigned n=!strcmp(argv[2],":vision-a:")?7:17;bool resumed=!strcmp(argv[1],"resume");int32_t a[128],b[128];
        lie_job_info i=run(c,0,3,a);assert(i.ssd_cached_tokens==(resumed?n:0));
        i=run(c,3,3,b);assert(!memcmp(a,b,n*sizeof(*a))&&i.ssd_cached_tokens==(resumed?n:0));
        i=run(c,0,1,b);assert(!memcmp(a,b,n*sizeof(*a))&&i.ssd_cached_tokens==(resumed?n:0));
        lie_core_info ci=stop(c);assert(ci.ssd.entries==3);assert(resumed?ci.ssd.hits==3:ci.ssd.writes==3);return 0;
    }
    assert(argc==1);family(":vision-a:",7);family(":vision-b:",17);
    lie_core_options o;lie_core_options_init(&o);o.model_path=":fixture:";o.vision_model_path=":vision-no-state:";o.context=128;o.chunk=4;
    lie_core *c=lie_core_create(&o);assert(c);lie_core_info refused=ready(c,LIE_FAILED);assert(strstr(refused.error,"semantic prefix state"));lie_core_stop(c);ready(c,LIE_STOPPED);lie_core_destroy(c);
    o.prefix_cache_bytes=0;c=lie_core_create(&o);assert(c);ready(c,LIE_READY);stop(c);
    char cwd[2048],base[2200],path[2300];assert(getcwd(cwd,sizeof(cwd)));snprintf(base,sizeof(base),"%s/vision-cache-XXXXXX",cwd);assert(mkdtemp(base));
    const char *names[]={":vision-a:",":vision-b:"};for(unsigned i=0;i<2;++i){snprintf(path,sizeof(path),"%s/store-%u",base,i);child(argv[0],"seed",names[i],path);child(argv[0],"resume",names[i],path);clean(path);}assert(!rmdir(base));
    puts("Vision semantic scope, equal-token isolation, RAM default, SSD process restart: PASS (NOT-INFERENCE)");return 0;
}
