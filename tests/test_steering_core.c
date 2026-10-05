/* SPDX-License-Identifier: MIT */
/* Shared-owner admission and real RAM/SSD protocol with synthetic frontiers.
 * No model weights, numerical steering, GPU allocation or performance proof. */
#include "lie/core.h"
#include "../src/prefix_cache.h"
#include "fake_executor.h"
#include "vision_fixture.h"
#include <assert.h>
#include <dirent.h>
#include <fcntl.h>
#include <math.h>
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
  for(unsigned k=0;k<5000;++k){lie_core_snapshot(c,&i);if(i.state==target)return i;pause_short();}
  fprintf(stderr,"Steering core state %d: %s\n",i.state,i.error);assert(!"state deadline");return i;
}
static lie_core_options options(const char *store,bool mtp){
  lie_core_options o;lie_core_options_init(&o);o.model_path=":fixture:";
  o.context=128;o.chunk=4;o.max_active=2;o.prefix_cache_bytes=1u<<20;
  o.cache_policy.min_tokens=1;o.cache_policy.boundary_trim_tokens=0;
  o.cache_policy.boundary_align_tokens=0;o.cache_policy.capture_finish=false;
  if(!LIE_DS4_CACHE_POLICY)o.cache_policy.enabled=false;
  if(mtp)o.mtp_model_path=":fixture:";
  if(store)o.ssd=(lie_store_options){store,1u<<20,1u<<16};
  return o;
}
static void stop(lie_core *c){
  lie_core_stop(c);lie_core_info i=wait_state(c,LIE_STOPPED);
  assert(!i.ssd.errors&&!i.ssd.pending&&!i.ssd.staging_bytes&&!i.cache.retained_bytes);
  lie_steering_model_info info={.abi_version=LIE_STEERING_MODEL_ABI,.struct_bytes=sizeof(info)};
  lie_steering_model_info before=info;
  assert(lie_core_steering_snapshot(c,&info,NULL)==LIE_UNSUPPORTED&&!memcmp(&info,&before,sizeof(info)));
  lie_core_destroy(c);
}
static lie_job_info run(lie_core *c){
  lie_core_request r;lie_core_request_init(&r);r.kind=LIE_INPUT_TEXT;
  r.text="abcdefgh";r.text_bytes=8;r.max_tokens=4;
  lie_job *j=NULL;assert(!lie_core_submit(c,&r,&j));bool done=false;unsigned count=0;
  for(unsigned k=0;k<5000&&!done;++k){lie_flow_event e;lie_flow_status rc=lie_flow_next(lie_job_flow(j),&e);
    if(rc==LIE_FLOW_WOULD_BLOCK){struct pollfd fd={lie_flow_fd(lie_job_flow(j),LIE_FLOW_OUTPUT_READY),POLLIN,0};
      assert(poll(&fd,1,1)>=0);lie_flow_drain(lie_job_flow(j),LIE_FLOW_OUTPUT_READY);continue;}
    assert(rc==LIE_FLOW_OK);
    if(e.end!=LIE_FLOW_ACTIVE){lie_job_info info;lie_job_snapshot(j,&info);
      if(e.end!=LIE_FLOW_COMPLETE)fprintf(stderr,"Steering fixture job: %s\n",info.error);
      assert(e.end==LIE_FLOW_COMPLETE);done=true;continue;}
    count+=(unsigned)e.tokens;assert(lie_flow_release(lie_job_flow(j),e.ticket)==LIE_FLOW_OK);
    lie_flow_request(lie_job_flow(j),e.tokens);
  }
  assert(done&&count==4);lie_job_info info;lie_job_snapshot(j,&info);
  assert(info.prompt_tokens==8&&info.output_tokens==4&&info.prefill_tokens+info.cached_tokens==8);
  lie_job_release(j);return info;
}
static lie_job_info run_image(lie_core *c,unsigned mutation){
  unsigned char *pixels=NULL;size_t bytes=0;lie_image_format format;
  assert(lie_image_data_url(image_url,strlen(image_url),&pixels,&bytes,&format,NULL)==LIE_OK);
  pixels[40]^=(unsigned char)mutation;
  lie_image_input image={pixels,bytes,format,0,3};lie_chat_message message={LIE_CHAT_USER,"normal",6};
  lie_core_request r;lie_core_request_init(&r);r.chat.messages=&message;r.chat.count=1;
  r.images=&image;r.image_count=1;r.max_tokens=4;lie_job *j=NULL;
  assert(!lie_core_submit(c,&r,&j));free(pixels);bool done=false;unsigned count=0;
  for(unsigned k=0;k<5000&&!done;++k){lie_flow_event e;lie_flow_status rc=lie_flow_next(lie_job_flow(j),&e);
    if(rc==LIE_FLOW_WOULD_BLOCK){struct pollfd fd={lie_flow_fd(lie_job_flow(j),LIE_FLOW_OUTPUT_READY),POLLIN,0};
      assert(poll(&fd,1,1)>=0);lie_flow_drain(lie_job_flow(j),LIE_FLOW_OUTPUT_READY);continue;}
    assert(rc==LIE_FLOW_OK);
    if(e.end!=LIE_FLOW_ACTIVE){lie_job_info i;lie_job_snapshot(j,&i);
      if(e.end!=LIE_FLOW_COMPLETE)fprintf(stderr,"Steering image fixture: %s\n",i.error);
      assert(e.end==LIE_FLOW_COMPLETE);done=true;continue;}
    count+=(unsigned)e.tokens;assert(lie_flow_release(lie_job_flow(j),e.ticket)==LIE_FLOW_OK);
    lie_flow_request(lie_job_flow(j),e.tokens);
  }
  assert(done&&count==4);lie_job_info i;lie_job_snapshot(j,&i);
  assert(i.prompt_tokens==7&&i.output_tokens==4&&i.prefill_tokens+i.cached_tokens==7);
  lie_job_release(j);return i;
}
static void bank_file(const char *path,bool different){
  /* Four exact little-endian binary32 values, 1/2/3/4 or 2/2/3/4. */
  const unsigned char values[]={0,0,128,63,0,0,0,64,0,0,64,64,0,0,128,64};
  unsigned char data[16];memcpy(data,values,16);if(different){data[2]=0;data[3]=64;}
  int fd=open(path,O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600);assert(fd>=0);
  assert(write(fd,data,16)==16&&!close(fd));
}
static void clean(const char *path){
  DIR *d=opendir(path);assert(d);struct dirent *entry;
  while((entry=readdir(d)))if(strcmp(entry->d_name,".")&&strcmp(entry->d_name,".."))assert(!unlinkat(dirfd(d),entry->d_name,0));
  closedir(d);assert(!rmdir(path));
}
static void child(const char *self,const char *bank,const char *store,const char *scale,bool hit,const char *mode){
  pid_t p=fork();assert(p>=0);
  if(!p){execl(self,self,bank,store,scale,hit?"hit":"miss",mode,(char *)NULL);_exit(127);}
  int status;assert(waitpid(p,&status,0)==p&&WIFEXITED(status)&&WEXITSTATUS(status)==0);
}
static void scoped_ram(const char *a,const char *b){
  lie_prefix_cache cache;lie_prefix_cache_init(&cache,1u<<20);
  lie_state *states[2]={0};unsigned char scopes[2][32];lie_error e={0};
  for(unsigned k=0;k<2;++k){
    lie_model_options mo={LIE_EXECUTOR_ABI,sizeof(mo),128,4,LIE_ROPE_NATIVE};
    lie_steering_model_options so;lie_steering_model_options_init(&so);so.file=k?b:a;
    lie_model *m=NULL;lie_sequence *s=NULL;int32_t tokens[]={0,10,10,10};
    assert(lie_backend_open_steered(":fixture:",&mo,1,NULL,0,NULL,&so,&m,&e)==LIE_OK);
    assert(lie_sequence_create(m,&s,&e)==LIE_OK&&lie_sequence_prefill(s,tokens,4,&e)==LIE_OK);
    lie_state_layout layout;uint64_t bytes;
    assert(lie_state_plan(s,&layout,&bytes,&e)==LIE_OK&&lie_state_capture(s,&layout,bytes,&states[k],&e)==LIE_OK);
    assert(lie_state_cache_scope(states[k],scopes[k]));lie_prefix_cache_insert(&cache,states[k]);
    lie_cache_metadata meta={.text="same",.text_bytes=4,.flags=2};
    assert(lie_prefix_cache_metadata(&cache,states[k],&meta));
    assert(lie_sequence_close(&s,&e)==LIE_OK&&lie_model_close(&m,&e)==LIE_OK);
  }
  assert(memcmp(scopes[0],scopes[1],32));const lie_cache_metadata *meta=NULL;
  for(unsigned k=0;k<2;++k){
    assert(lie_prefix_cache_match_text_scope(&cache,"same suffix",11,2,scopes[k],&meta)==states[k]&&meta&&meta->text_bytes==4);
    assert(!lie_prefix_cache_match_text_scope(&cache,"same suffix",11,4,scopes[k],&meta)&&!meta);
  }
  assert(!lie_prefix_cache_match_text(&cache,"same suffix",11,2,&meta)&&!meta);
  lie_prefix_cache_clear(&cache);for(unsigned k=0;k<2;++k)lie_state_destroy(&states[k]);
}
static lie_job_steering_info job_policy(lie_job *j){
  lie_job_steering_info s={.abi_version=LIE_JOB_STEERING_ABI,.struct_bytes=sizeof(s)};
  assert(lie_job_steering_snapshot(j,&s,NULL)==LIE_OK);return s;
}
static lie_job_info drain_job(lie_job *j,bool success){
  bool done=false;lie_job_info info={0};
  for(unsigned k=0;k<5000&&!done;++k){
    lie_flow_event e;lie_flow_status rc=lie_flow_next(lie_job_flow(j),&e);
    if(rc==LIE_FLOW_WOULD_BLOCK){pause_short();continue;}assert(rc==LIE_FLOW_OK);
    if(e.end!=LIE_FLOW_ACTIVE){assert((e.end==LIE_FLOW_COMPLETE)==success);done=true;}
    else {assert(lie_flow_release(lie_job_flow(j),e.ticket)==LIE_FLOW_OK);lie_flow_request(lie_job_flow(j),e.tokens);}
  }
  assert(done);
  for(unsigned k=0;k<5000;++k){lie_job_snapshot(j,&info);if(info.retired)return info;pause_short();}
  assert(!"retirement deadline");return info;
}
/* Each case applies while the first numerical fixture call is held. The client
 * never executes the provider; copied one-slot control completes at position4.
 * Real RAM/SSD codecs must accept the resulting mixed history, not initial scope. */
static void live_case(const char *bank,const char *store,bool mtp,bool vision,
                      unsigned fault,bool cancel,bool noop){
  lie_core_options o=options(store,mtp);o.cache_policy.capture_finish=!fault&&!cancel;
  if(vision)o.vision_model_path=":vision-a:";
  lie_steering_model_options so;lie_steering_model_options_init(&so);so.file=bank;
  lie_core *c=lie_core_create_steered(&o,&so);assert(c);wait_state(c,LIE_READY);
  lie_core_request r;lie_core_request_init(&r);r.kind=LIE_INPUT_TEXT;r.text="abcdefgh";r.text_bytes=8;r.max_tokens=4;
  unsigned char *pixels=NULL;size_t bytes=0;lie_image_format format;lie_image_input image={0};
  lie_chat_message message={LIE_CHAT_USER,"normal",6};
  if(vision){assert(lie_image_data_url(image_url,strlen(image_url),&pixels,&bytes,&format,NULL)==LIE_OK);
    image=(lie_image_input){pixels,bytes,format,0,3};r.kind=LIE_INPUT_MESSAGES;r.text=NULL;r.text_bytes=0;
    r.images=&image;r.image_count=1;r.chat.messages=&message;r.chat.count=1;}
  fake_barrier_arm_phase(FAKE_PREFILL);lie_job *j=NULL;assert(!lie_core_submit(c,&r,&j));free(pixels);fake_barrier_wait();
  lie_job_steering_info initial=job_policy(j);assert(initial.policy_ready&&!initial.pending&&!initial.submitted&&initial.policy.completed_positions==0);
  lie_steering_settings settings;lie_steering_settings_init(&settings,true);settings.ffn=noop?1:2;
  settings.attention=noop?0:0.25f;uint64_t ticket=999,refused=888;
  lie_steering_settings invalid=settings;invalid.ffn=NAN;
  assert(lie_job_change_steering(j,&invalid,&refused,NULL)==LIE_INVALID&&refused==888);
  assert(lie_job_change_steering(j,&settings,&ticket,NULL)==LIE_OK&&ticket==1);
  assert(lie_job_change_steering(j,&settings,&refused,NULL)==LIE_RESOURCE_LIMIT&&refused==888);
  lie_job_steering_info pending=job_policy(j);assert(pending.pending&&pending.submitted==ticket&&!pending.completed);
  memset(&settings,0,sizeof(settings));fake_steering_fault(fault);
  if(cancel)lie_job_cancel(j);
  fake_barrier_release();lie_job_info result=drain_job(j,!cancel&&fault!=2);
  lie_job_steering_info final=job_policy(j);
  assert(!final.pending&&final.completed==ticket&&final.submitted==ticket);
  lie_status expected=cancel?LIE_CANCELLED:fault==1?LIE_INVALID:fault==2?LIE_BACKEND_FAILED:LIE_OK;
  assert(final.status==expected);
  if(!cancel&&fault!=2){
    assert(result.output_tokens==4&&final.policy.completed_positions==result.prompt_tokens+4);
    assert(final.policy.settings.ffn==(noop||fault==1?1:2));
    assert(final.policy.settings.attention==(noop||fault==1?0:0.25f));
    assert(final.policy.history_epochs==(noop||fault==1?1u:2u));
    assert(!memcmp(initial.semantic_scope,final.semantic_scope,32));
    assert((memcmp(initial.combined_scope,final.combined_scope,32)==0)==(noop||fault==1));
    if(!fault)assert(final.applied_position==4);
    if(vision)assert(memcmp(final.semantic_scope,(unsigned char[32]){0},32));
  }
  assert(lie_job_change_steering(j,&so.defaults,&refused,NULL)==LIE_CANCELLED&&refused==888);
  lie_job_steering_info tagged={0},before=tagged;
  assert(lie_job_steering_snapshot(j,&tagged,NULL)==LIE_INVALID&&!memcmp(&tagged,&before,sizeof(tagged)));
  lie_job_release(j);if(fault==2)wait_state(c,LIE_FAILED);stop(c);fake_steering_fault(0);
  if(store)clean(store);
}
static void live_peers(const char *bank){
  lie_core_options o=options(NULL,LIE_MTP!=0);o.prefix_cache_bytes=0;
  lie_steering_model_options so;lie_steering_model_options_init(&so);so.file=bank;
  lie_core *c=lie_core_create_steered(&o,&so);assert(c);wait_state(c,LIE_READY);
  lie_core_request r;lie_core_request_init(&r);r.kind=LIE_INPUT_TEXT;r.text="abcdefgh";r.text_bytes=8;r.max_tokens=4;
  lie_job *a=NULL,*b=NULL;fake_barrier_arm_phase(FAKE_PREFILL);
  assert(!lie_core_submit(c,&r,&a));fake_barrier_wait();assert(!lie_core_submit(c,&r,&b));
  lie_steering_settings settings;lie_steering_settings_init(&settings,true);settings.ffn=-2;
  uint64_t ticket=0;assert(lie_job_change_steering(a,&settings,&ticket,NULL)==LIE_OK);
  fake_barrier_release();assert(drain_job(a,true).output_tokens==4&&drain_job(b,true).output_tokens==4);
  lie_job_steering_info sa=job_policy(a),sb=job_policy(b);
  assert(sa.completed==ticket&&sa.status==LIE_OK&&sa.policy.settings.ffn==-2&&sa.policy.history_epochs==2);
  assert(!sb.submitted&&!sb.pending&&sb.policy.settings.ffn==1&&sb.policy.history_epochs==1);
  assert(sa.policy.completed_positions==12&&sb.policy.completed_positions==12);
  assert(memcmp(sa.combined_scope,sb.combined_scope,32));
  lie_core_info info;lie_core_snapshot(c,&info);assert(info.decode_batches&&info.decode_batch_rows>=2);
  lie_job_release(a);lie_job_release(b);stop(c);
}
int main(int argc,char **argv){
  if(argc==6){
    bool bank=strcmp(argv[1],"none")!=0,mtp=!strcmp(argv[5],"mtp")||!strcmp(argv[5],"mtp-vision"),
         vision=strstr(argv[5],"vision")!=NULL,hit=!strcmp(argv[4],"hit");
    lie_core_options o=options(argv[2],mtp);lie_steering_model_options so;lie_steering_model_options_init(&so);
    if(vision)o.vision_model_path=":vision-a:";
    so.file=argv[1];assert(lie_steering_model_option(&so,"--dir-steering-ffn",argv[3])==1);
    lie_core *c=bank?lie_core_create_steered(&o,&so):lie_core_create(&o);assert(c);wait_state(c,LIE_READY);
    lie_steering_model_info si={.abi_version=LIE_STEERING_MODEL_ABI,.struct_bytes=sizeof(si)};
    assert(lie_core_steering_snapshot(c,&si,NULL)==LIE_OK&&si.admitted==bank&&!si.device_vector_bytes);
    assert(si.bank.bytes==(bank?16u:0u));
    unsigned n=vision?7:8;lie_job_info i=vision?run_image(c,0):run(c);
    assert(i.ssd_cached_tokens==(hit?n:0u)&&i.prefill_tokens==(hit?0u:n));
    i=vision?run_image(c,0):run(c);assert(i.cached_tokens==n&&!i.ssd_cached_tokens&&!i.prefill_tokens);
    if(vision){unsigned uploads=fake_calls_snapshot().restore;i=run_image(c,1);
      assert(i.cached_tokens==(hit?7u:0u)&&i.ssd_cached_tokens==(hit?7u:0u));
      if(!hit)assert(fake_calls_snapshot().restore==uploads);
    }
    stop(c);return 0;
  }
  assert(argc==1);lie_core_options o=options(NULL,false);lie_steering_model_options so;lie_steering_model_options_init(&so);
  if(!LIE_DIRECTIONAL_STEERING){so.file="unused.f32";assert(!lie_core_create_steered(&o,&so));
    assert(lie_steering_model_option(&so,"--dir-steering-ffn","1")==-1);
    puts("Steering build-off refusal: PASS (NOT-INFERENCE)");return 0;}
  assert(!lie_core_create_steered(&o,&so));so.file="unused.f32";so.defaults.ffn=NAN;assert(!lie_core_create_steered(&o,&so));
  lie_steering_model_options_init(&so);assert(lie_steering_model_option(&so,"--unrelated","1")==0);
  const char *bad[]={"nan","inf","101","-101","1x",""," 1","1,5","1e99"};
  for(unsigned k=0;k<sizeof(bad)/sizeof(*bad);++k){lie_steering_model_options before=so;
    assert(lie_steering_model_option(&so,"--dir-steering-ffn",bad[k])==-1&&!memcmp(&so,&before,sizeof(so)));}
  char cwd[2048],base[2200],a[2300],b[2300],store[2300];assert(getcwd(cwd,sizeof(cwd)));
  snprintf(base,sizeof(base),"%s/steering-core-XXXXXX",cwd);assert(mkdtemp(base));
  snprintf(a,sizeof(a),"%s/a.f32",base);snprintf(b,sizeof(b),"%s/b.f32",base);bank_file(a,false);bank_file(b,true);
  scoped_ram(a,b);fake_calls_reset();
  char *borrowed=strdup(a);assert(borrowed);so.file=borrowed;so.defaults.attention=0.25f;
  fake_barrier_arm_phase(FAKE_STEERING_OPEN);lie_core *c=lie_core_create_steered(&o,&so);assert(c);fake_barrier_wait();
  lie_steering_model_info si={.abi_version=LIE_STEERING_MODEL_ABI,.struct_bytes=sizeof(si)},before=si;
  assert(lie_core_steering_snapshot(c,&si,NULL)==LIE_UNSUPPORTED&&!memcmp(&si,&before,sizeof(si)));
  memset(borrowed,'x',strlen(borrowed));free(borrowed);so.file=NULL;so.vector_budget_bytes=1;so.defaults.ffn=-2;
  fake_barrier_release();wait_state(c,LIE_READY);
  assert(lie_core_steering_snapshot(c,&si,NULL)==LIE_OK&&si.admitted&&si.bank.layers==1&&si.bank.width==4&&si.bank.bytes==16);
  assert(si.defaults.ffn==1&&si.defaults.attention==0.25f&&!si.device_vector_bytes);
  assert(!run(c).cached_tokens&&run(c).cached_tokens==8);stop(c);
  assert(fake_calls_snapshot().create==fake_calls_snapshot().close);
  for(unsigned k=0;k<4;++k){if((k&1)&&!LIE_MTP)continue;if(k>=2&&!LIE_VISION)continue;
    snprintf(store,sizeof(store),"%s/live-store-%u",base,k);
    live_case(a,store,(k&1)!=0,k>=2,0,false,false);
  }
  live_case(a,NULL,false,false,0,false,true);
  live_case(a,NULL,LIE_MTP!=0,false,0,true,false);
  live_case(a,NULL,false,false,1,false,false);
  live_case(a,NULL,LIE_MTP!=0,false,2,false,false);
  live_peers(a);
  assert(fake_calls_snapshot().create==fake_calls_snapshot().close);
  lie_steering_model_options_init(&so);so.file=a;so.vector_budget_bytes=15;
  c=lie_core_create_steered(&o,&so);assert(c);wait_state(c,LIE_FAILED);stop(c);
  const char *modes[]={"ar","mtp","vision","mtp-vision"};
  for(unsigned k=0;k<4;++k){if((k&1)&&!LIE_MTP)continue;if(k>=2&&!LIE_VISION)continue;
    snprintf(store,sizeof(store),"%s/store-%u",base,k);
    child(argv[0],a,store,"1",false,modes[k]);child(argv[0],a,store,"1",true,modes[k]);
    child(argv[0],a,store,"2",false,modes[k]);child(argv[0],b,store,"1",false,modes[k]);
    child(argv[0],"none",store,"0",false,modes[k]);child(argv[0],a,store,"0",true,modes[k]);
    child(argv[0],a,store,"1",true,modes[k]);clean(store);
  }
  assert(!unlink(a)&&!unlink(b)&&!rmdir(base));
  puts("Shared core steering admission, scopes, RAM/SSD restart and AR/MTP/vision lifetimes: PASS (NOT-INFERENCE)");return 0;
}
