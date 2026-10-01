/* SPDX-License-Identifier: MIT */
/* Simplified Gufo-style workloads over completed GPU executor calls. */
#include "lie/executor.h"
#include "lie/inference.h"
#include <errno.h>
#include <fcntl.h>
#include <float.h>
#include <json-c/json.h>
#include <math.h>
#include <limits.h>
#include <openssl/evp.h>
#include <signal.h>
#include <spawn.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/wait.h>
#include <unistd.h>

#define MAX_POINTS 32u
#define MAX_USERS 8u
#define MAX_CONTEXT 262144u
#define MAX_OUTPUT 4096u
#define PAD_BYTES (2u*1024u*1024u)
static volatile sig_atomic_t interrupted;
static void stop(int sig) {(void)sig;interrupted=1;}
static uint64_t ns(void) {struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))return 0;return (uint64_t)t.tv_sec*1000000000u+(uint64_t)t.tv_nsec;}
static void num(json_object *j,const char *k,int64_t v) {json_object_object_add(j,k,json_object_new_int64(v));}
static void str(json_object *j,const char *k,const char *v) {json_object_object_add(j,k,json_object_new_string(v));}
static json_object *event(const char *kind) {json_object *j=json_object_new_object();str(j,"event",kind);return j;}
static bool emit(FILE *f,json_object *j) {bool ok=fputs(json_object_to_json_string_ext(j,JSON_C_TO_STRING_PLAIN),f)>=0&&fputc('\n',f)!=EOF&&fflush(f)==0;json_object_put(j);return ok;}
static bool hash(const void *p,size_t n,char out[65]) {unsigned char digest[32];unsigned count=0;if(!EVP_Digest(p,n,digest,&count,EVP_sha256(),NULL)||count!=32)return false;for(unsigned i=0;i<32;++i)snprintf(out+2*i,3,"%02x",digest[i]);return true;}
static json_object *ids_json(const int32_t *ids,size_t n) {json_object *a=json_object_new_array();for(size_t i=0;i<n;++i)json_object_array_add(a,json_object_new_int(ids[i]));return a;}
static bool integer(const char *s,unsigned maximum,unsigned *out) {char *end;errno=0;unsigned long n=strtoul(s,&end,10);if(errno||!*s||*end||*s=='-'||n>maximum)return false;*out=(unsigned)n;return true;}
static bool list(const char *s,unsigned maximum,unsigned *values,unsigned *count) {
    char *copy=strdup(s);if(!copy)return false;char *save=NULL;*count=0;bool ok=true;
    if(!*s||s[strlen(s)-1]==','||strstr(s,",,"))ok=false;
    for(char *part=ok?strtok_r(copy,",",&save):NULL;part;part=strtok_r(NULL,",",&save)){
        if(*count==MAX_POINTS||!integer(part,maximum,&values[*count])){ok=false;break;}
        for(unsigned i=0;i<*count;++i)if(values[i]==values[*count])ok=false;
        ++*count;
    }
    free(copy);return ok&&*count>0;
}
struct config {const char *model,*output,*suite,*graphs,*compare,*execution;unsigned pp,tg,repetitions,warmups,depths[MAX_POINTS],depth_count,users[MAX_POINTS],user_count;};
static int graphs(const struct config *c) {
    char script[PATH_MAX];ssize_t n=readlink("/proc/self/exe",script,sizeof(script)-1);
    if(n<0)return 3;
    script[n]=0;char *slash=strrchr(script,'/');if(!slash)return 3;
    size_t prefix=(size_t)(slash-script)+1;
    if(prefix+strlen("synapse-lie-bench-report.py")>=sizeof(script))return 3;
    strcpy(script+prefix,"synapse-lie-bench-report.py");
    char *args[]={"python3",script,(char *)c->output,"--output",(char *)c->graphs,"--compare",(char *)c->compare,NULL};
    if(!c->compare)args[5]=NULL;
    extern char **environ;pid_t pid;int status;
    if(posix_spawnp(&pid,"python3",NULL,NULL,args,environ))return 3;
    while(waitpid(pid,&status,0)<0)if(errno!=EINTR)return 3;
    if(!WIFEXITED(status)||WEXITSTATUS(status)){fputs("Graph export failed; benchmark JSONL is preserved\n",stderr);return 3;}
    return 0;
}
static json_object *identity(const struct config *c) {
    json_object *j=event("identity");str(j,"schema","synapse-lie.bench.v1");str(j,"program","synapse-lie-bench");str(j,"build_id",LIE_BUILD_ID);
    str(j,"engine",lie_backend_name());str(j,"source_pin",lie_backend_source_pin());str(j,"ownership",lie_backend_ownership());
    json_object_object_add(j,"synthetic",json_object_new_boolean(lie_backend_is_synthetic()));
    str(j,"suite",c->suite);str(j,"mode","ar");num(j,"pp_target",c->pp);num(j,"output_limit",c->tg);num(j,"repetitions",c->repetitions);num(j,"warmups",c->warmups);
    str(j,"scope","simplified direct executor; physical-prefix reuse, not HTTP conversation/cache restore or independent kernels");
    str(j,"unsupported","MTP, cold-file loading, allocation-exact HIP peak, quality/FP64 oracle");
#ifdef LIE_BENCH_REFERENCE
    str(j,"execution","upstream-native-batch");
#else
    str(j,"execution",!strcmp(c->execution,"reactive")?"LIE-reactive-ready-batch":"LIE-serial-interleaved");
#endif
    return j;
}
#ifdef LIE_BENCH_REFERENCE
extern void lie_bench_reference_width(unsigned width);
#endif
static bool open_model(const struct config *c,unsigned context,unsigned users,lie_model **m,lie_model_info *info,FILE *f,lie_error *e) {
#ifdef LIE_BENCH_REFERENCE
    lie_bench_reference_width(users);
#else
    (void)users;
#endif
    lie_model_options o={LIE_EXECUTOR_ABI,sizeof(o),context,2048};uint64_t begin=ns();
#ifdef LIE_BENCH_REFERENCE
    if(lie_backend_open(c->model,&o,m,e)!=LIE_OK)return false;
#else
    lie_status opened=!strcmp(c->execution,"reactive")?lie_backend_open_batch(c->model,&o,users,m,e):lie_backend_open(c->model,&o,m,e);
    if(opened!=LIE_OK)return false;
#endif
    uint64_t elapsed=ns()-begin;
    if(lie_model_get_info(*m,info,e)!=LIE_OK||info->context_tokens!=context||!info->vocab_tokens||info->vocab_tokens>1048576)return false;
    json_object *j=event("model_loaded");num(j,"context_capacity",context);num(j,"users",users);num(j,"model_load_ns",(int64_t)elapsed);
    num(j,"resident_bytes_estimate",(int64_t)info->weights_bytes);num(j,"session_bytes_estimate",(int64_t)info->session_bytes);
    str(j,"loading_scope","model load in existing OS cache conditions; excludes HTTP readiness, not cold-file loading");return emit(f,j);
}
struct prompt {int32_t *ids;size_t n;};
static bool make_prompt(lie_model *m,unsigned target,unsigned capacity,struct prompt *p,lie_error *e) {
    static const char lead[]="The following independent project notes are reference material.\n";
    static const char tail[]="\nWrite a detailed analysis of the project notes, then a long fictional account of the teams solving their problems. Continue with substantial prose for at least 2000 words; do not give a short answer.";
    char *padding=malloc(PAD_BYTES+512),*content=malloc(PAD_BYTES+sizeof(lead)+sizeof(tail));if(!padding||!content){free(padding);free(content);return false;}
    size_t at=0;unsigned i=0;
    while(at<PAD_BYTES){int n=snprintf(padding+at,512,"In district %u, team %u reviews water, transit and energy plans. Their survey records %u observations, compares practical alternatives and schedules a public review. The report preserves budgets, reasons and unresolved questions.\n",i,1+i%17,13+i%97);if(n<0||n>=512){free(padding);free(content);return false;}at+=(size_t)n;++i;}
    p->ids=malloc((size_t)capacity*sizeof(*p->ids));if(!p->ids){free(padding);free(content);return false;}
    /* Small sessions render within upstream's 1-MiB minimum bound. Leave
     * framing space in calibration probes, not just in the accepted prompt. */
    unsigned lo=0,hi=capacity<=8192?PAD_BYTES/2:PAD_BYTES;lie_status status=LIE_OK;
    while(lo<hi){unsigned mid=lo+(hi-lo+1)/2;memcpy(content,lead,sizeof(lead)-1);memcpy(content+sizeof(lead)-1,padding,mid);memcpy(content+sizeof(lead)-1+mid,tail,sizeof(tail)-1);
        lie_chat_message msg={LIE_CHAT_USER,content,sizeof(lead)-1+mid+sizeof(tail)-1};status=lie_model_chat_tokens(m,&msg,1,p->ids,capacity,&p->n,e);
        if(status!=LIE_OK&&status!=LIE_BUFFER_SMALL)break;
        if(p->n>target)hi=mid-1;else lo=mid;
    }
    memcpy(content,lead,sizeof(lead)-1);memcpy(content+sizeof(lead)-1,padding,lo);memcpy(content+sizeof(lead)-1+lo,tail,sizeof(tail)-1);
    lie_chat_message msg={LIE_CHAT_USER,content,sizeof(lead)-1+lo+sizeof(tail)-1};
    if(status==LIE_OK||status==LIE_BUFFER_SMALL)status=lie_model_chat_tokens(m,&msg,1,p->ids,capacity,&p->n,e);
    free(padding);free(content);return status==LIE_OK&&p->n<=target&&target-p->n<=32;
}
static bool prefill(lie_sequence *s,const struct prompt *p,size_t from,size_t end,lie_error *e) {
    while(from<end){from=end-from>2048?from+2048:end;if(interrupted||lie_sequence_prefill(s,p->ids,from,e)!=LIE_OK)return false;}return true;
}
static bool frontier(lie_sequence *s,float *out,unsigned vocab,char digest[65],lie_error *e) {
    size_t n=0;if(lie_sequence_logits(s,out,vocab,&n,e)!=LIE_OK||n!=vocab)return false;
    for(size_t i=0;i<n;++i)if(!isfinite(out[i])){snprintf(e->message,sizeof(e->message),"nonfinite frontier");return false;}
    return hash(out,n*sizeof(*out),digest);
}
#ifndef LIE_BENCH_REFERENCE
struct dispatch_counts {unsigned single,batches,rows;};
static bool reactive_step(lie_sequence **seq,lie_flow **flows,unsigned users,unsigned vocab,unsigned context,
                          size_t prompt,const unsigned *counts,const unsigned *stopped,
                          lie_decode_result *results,struct dispatch_counts *stats,lie_error *e) {
    lie_inference_row rows[MAX_USERS]={0};unsigned map[MAX_USERS],n=0;
    for(unsigned i=0;i<users;++i)if(!stopped[i]){map[n]=i;rows[n++]=(lie_inference_row){.sequence=seq[i],.flow=flows[i],.position=(uint32_t)prompt+counts[i],.context=context,.vocab=vocab};}
    if(!n)return true;
    lie_inference_batch batch={0};lie_status rc=lie_inference_prepare(rows,n,users,&batch,e);
    if(rc==LIE_OK){if(batch.selected!=n)rc=LIE_INVALID;
        else {rc=lie_inference_run(&batch,e);if(n>1){++stats->batches;stats->rows+=n;}else ++stats->single;}}
    for(unsigned k=0;k<n;++k){lie_inference_row *row=&rows[k];unsigned i=map[k];
        if(!row->reserved)continue;
        if(rc!=LIE_OK||row->outcome.status!=LIE_OK){(void)lie_flow_abort(flows[i],row->reservation.ticket,1);rc=LIE_BACKEND_FAILED;continue;}
        results[i]=row->outcome.result;
        lie_flow_status f=lie_flow_commit(flows[i],row->reservation.ticket,0,results[i].emitted,results[i].stop);
        if(f!=LIE_FLOW_OK){(void)lie_flow_abort(flows[i],row->reservation.ticket,1);rc=LIE_BACKEND_FAILED;continue;}
        lie_flow_event event;
        if(lie_flow_next(flows[i],&event)!=LIE_FLOW_OK){rc=LIE_BACKEND_FAILED;continue;}
        if(event.end==LIE_FLOW_ACTIVE){
            if(lie_flow_release(flows[i],event.ticket)!=LIE_FLOW_OK)rc=LIE_BACKEND_FAILED;
            if(!results[i].stop&&lie_flow_request(flows[i],1)!=LIE_FLOW_OK)rc=LIE_BACKEND_FAILED;
        }
    }
    return rc==LIE_OK;
}
#endif
struct witness {char pp[65],tg[65];int32_t *ids;unsigned count,stop;bool set;};
static bool sample(lie_model *m,const struct prompt *p,unsigned depth,unsigned users,unsigned point,unsigned rep,bool warmup,const struct config *c,unsigned vocab,struct witness *w,FILE *f,lie_error *e) {
    lie_sequence *seq[MAX_USERS]={0};unsigned handles=users;
#ifndef LIE_BENCH_REFERENCE
    lie_flow *flows[MAX_USERS]={0};struct dispatch_counts stats={0};
    bool reactive=!strcmp(c->execution,"reactive");
#endif
#ifdef LIE_BENCH_REFERENCE
    handles=1;
#endif
    int32_t *output=calloc((size_t)users*c->tg,sizeof(*output));float *logits=malloc((size_t)vocab*sizeof(*logits));
    unsigned counts[MAX_USERS]={0},stopped[MAX_USERS]={0};char pp_hash[65],tg_hash[65];bool ok=false;
    if(!output||!logits)goto done;
    json_object *begin=event("sample_begin");num(begin,"point",point);num(begin,"rep",rep);num(begin,"depth",depth);num(begin,"users",users);num(begin,"warmup",warmup);if(!emit(f,begin))goto done;
    for(unsigned i=0;i<handles;++i)if(lie_sequence_create(m,&seq[i],e)!=LIE_OK||!prefill(seq[i],p,0,depth,e))goto done;
    uint64_t pp_begin=ns();
    for(unsigned i=0;i<handles;++i)if(!prefill(seq[i],p,depth,p->n,e))goto done;
    uint64_t pp_ns=ns()-pp_begin;
    if(!frontier(seq[0],logits,vocab,pp_hash,e))goto done;
#ifndef LIE_BENCH_REFERENCE
    if(reactive)for(unsigned i=0;i<users;++i){lie_flow_options o={1,1,4096};if(lie_flow_create(&o,&flows[i])!=LIE_FLOW_OK||lie_flow_request(flows[i],1)!=LIE_FLOW_OK)goto done;}
#endif
    uint64_t tg_begin=ns();
    for(unsigned step=0;step<c->tg;++step){bool active=false;
        lie_decode_result decoded[MAX_USERS]={0};
#ifndef LIE_BENCH_REFERENCE
        if(reactive&&(interrupted||!reactive_step(seq,flows,users,vocab,!strcmp(c->suite,"multi")?4096:!strcmp(c->suite,"memory")?133121:133760,p->n,counts,stopped,decoded,&stats,e)))goto done;
#endif
        for(unsigned i=0;i<handles;++i){if(stopped[i])continue;active=true;lie_decode_result d={0};
            lie_status rc=LIE_OK;
#ifndef LIE_BENCH_REFERENCE
            if(reactive)d=decoded[i];else
#else
            (void)decoded;
#endif
            rc=lie_sequence_decode(seq[i],&d,e);
            if(interrupted||rc!=LIE_OK||d.emitted>1||d.stop>1||(!d.emitted&&!d.stop)||d.position!=p->n+counts[i]+d.emitted||(d.emitted&&(d.token<0||(unsigned)d.token>=vocab)))goto done;
            if(d.emitted)output[(size_t)i*c->tg+counts[i]++]=d.token;
            stopped[i]=d.stop;
        }if(!active)break;
    }
    uint64_t tg_ns=ns()-tg_begin;
    if(!frontier(seq[0],logits,vocab,tg_hash,e))goto done;
    for(unsigned i=1;i<handles;++i){char other[65];if(counts[i]!=counts[0]||stopped[i]!=stopped[0]||memcmp(output+(size_t)i*c->tg,output,counts[0]*sizeof(*output))||!frontier(seq[i],logits,vocab,other,e)||strcmp(other,tg_hash)){snprintf(e->message,sizeof(e->message),"identical-input peer mismatch");goto done;}}
    if(w->set){if(strcmp(w->pp,pp_hash)||strcmp(w->tg,tg_hash)||w->count!=counts[0]||w->stop!=stopped[0]||memcmp(w->ids,output,counts[0]*sizeof(*output))){snprintf(e->message,sizeof(e->message),"repeatability mismatch");goto done;}}
    else {strcpy(w->pp,pp_hash);strcpy(w->tg,tg_hash);w->count=counts[0];w->stop=stopped[0];memcpy(w->ids,output,counts[0]*sizeof(*output));w->set=true;}
    json_object *j=event("sample");num(j,"point",point);num(j,"rep",rep);num(j,"warmup",warmup);num(j,"depth",depth);num(j,"users",users);
    num(j,"prompt_tokens",(int64_t)p->n);num(j,"cache_tokens",depth);num(j,"prefill_tokens_per_user",(int64_t)p->n-depth);num(j,"output_tokens_per_user",counts[0]);num(j,"output_tokens",counts[0]*users);
    num(j,"prefill_ns",(int64_t)pp_ns);num(j,"decode_ns",(int64_t)tg_ns);num(j,"stop",stopped[0]);num(j,"finite_frontiers",1);num(j,"identical_input_peers_verified",1);
    str(j,"prefill_logits_sha256",pp_hash);str(j,"decode_logits_sha256",tg_hash);json_object_object_add(j,"output_ids",ids_json(output,counts[0]));
    json_object_object_add(j,"prefill_tps",json_object_new_double((double)(p->n-depth)*users*1e9/(double)pp_ns));json_object_object_add(j,"decode_tps",json_object_new_double((double)counts[0]*users*1e9/(double)tg_ns));
#ifndef LIE_BENCH_REFERENCE
    if(reactive){num(j,"decode_single_calls",stats.single);num(j,"decode_batches",stats.batches);num(j,"decode_batch_rows",stats.rows);}
#endif
    num(j,"full_output_budget",counts[0]==c->tg);ok=emit(f,j);
    fprintf(stderr,"point=%u depth=%u users=%u warmup=%u output=%u completed\n",point,depth,users,warmup,counts[0]);
done:
#ifndef LIE_BENCH_REFERENCE
    for(unsigned i=0;i<users;++i)if(flows[i]){(void)lie_flow_cancel(flows[i]);if(lie_flow_destroy(&flows[i])!=LIE_FLOW_OK)ok=false;}
#endif
    for(unsigned i=0;i<handles;++i)if(seq[i]&&lie_sequence_close(&seq[i],e)!=LIE_OK)ok=false;
    free(output);free(logits);return ok;
}
int main(int argc,char **argv) {
    _Static_assert(sizeof(float)==4&&FLT_RADIX==2&&FLT_MANT_DIG==24,"float32 required");
    struct config c={.suite="single",.execution="reactive",.pp=2048,.tg=128,.repetitions=1,.warmups=1,.depths={0,4096,8192,12288,16384,32768,65536,131072},.depth_count=8,.users={1,2,4,6,8},.user_count=5};
    for(int i=1;i<argc;++i){
        if(!strcmp(argv[i],"--help")){puts("Usage: synapse-lie-bench --model FIRST-SHARD --output NEW-JSONL [--suite single|multi|loading|memory] [--depths 0,4096,8192,12288,16384,32768,65536,131072] [--users 1,2,4,6,8] [--pp 2048] [--tg 128] [--warmups 1] [--repetitions 1] [--execution reactive|serial] [--graphs DIRECTORY] [--compare REFERENCE-JSONL]\n--build-info opens no model. AR, greedy, thinking off; MTP unavailable.\nDirect GPU executor timings; no HTTP, cold-file claim or exact allocation peak.\nShared GPU requires the coordinated lease supervisor. Synthetic builds are NOT-INFERENCE.\nGraphs use the adjacent Python report helper and matplotlib; no package installation.");return 0;}
        if(!strcmp(argv[i],"--build-info"))return emit(stdout,identity(&c))?0:1;
        if(i+1==argc)goto usage;
        const char *key=argv[i],*value=argv[++i];
        if(!strcmp(key,"--model"))c.model=value;else if(!strcmp(key,"--output"))c.output=value;else if(!strcmp(key,"--suite"))c.suite=value;
        else if(!strcmp(key,"--graphs"))c.graphs=value;else if(!strcmp(key,"--compare"))c.compare=value;
        else if(!strcmp(key,"--execution")){
#ifdef LIE_BENCH_REFERENCE
            goto usage;
#else
            c.execution=value;
#endif
        }
        else if(!strcmp(key,"--depths")){if(!list(value,131072,c.depths,&c.depth_count))goto usage;}
        else if(!strcmp(key,"--users")){if(!list(value,MAX_USERS,c.users,&c.user_count))goto usage;for(unsigned k=0;k<c.user_count;++k)if(!c.users[k])goto usage;}
        else if(!strcmp(key,"--pp")){if(!integer(value,8192,&c.pp)||!c.pp)goto usage;}
        else if(!strcmp(key,"--tg")){if(!integer(value,MAX_OUTPUT,&c.tg)||!c.tg)goto usage;}
        else if(!strcmp(key,"--warmups")){if(!integer(value,10,&c.warmups))goto usage;}
        else if(!strcmp(key,"--repetitions")){if(!integer(value,100,&c.repetitions)||!c.repetitions)goto usage;}
        else goto usage;
    }
    if((strcmp(c.execution,"reactive")&&strcmp(c.execution,"serial"))||!c.model||!*c.model||!c.output||!*c.output||(c.compare&&!c.graphs)||(strcmp(c.suite,"single")&&strcmp(c.suite,"multi")&&strcmp(c.suite,"loading")&&strcmp(c.suite,"memory")))goto usage;
    struct sigaction sa={0};sa.sa_handler=stop;sigemptyset(&sa.sa_mask);if(sigaction(SIGINT,&sa,NULL)||sigaction(SIGTERM,&sa,NULL))return 1;
    int fd=open(c.output,O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600);if(fd<0){perror("exclusive output");return 1;}FILE *f=fdopen(fd,"w");if(!f){close(fd);return 1;}
    lie_model *m=NULL;lie_model_info info={0};lie_error e={{0}};int code=1;
    if(!emit(f,identity(&c)))goto done;
    unsigned points=!strcmp(c.suite,"multi")?c.user_count:!strcmp(c.suite,"memory")?2:!strcmp(c.suite,"loading")?1:c.depth_count;
    for(unsigned point=0;point<points;++point){unsigned depth=!strcmp(c.suite,"single")?c.depths[point]:!strcmp(c.suite,"memory")&&point?16384:0;
        unsigned pp=!strcmp(c.suite,"memory")&&point?4096:c.pp;unsigned users=!strcmp(c.suite,"multi")?c.users[point]:1;
        unsigned context=!strcmp(c.suite,"multi")?4096:!strcmp(c.suite,"loading")?262144:!strcmp(c.suite,"memory")?133121:133760;
        if((uint64_t)depth+pp+c.tg>=context){snprintf(e.message,sizeof(e.message),"workload exceeds context capacity");goto done;}
        if(!m&&!open_model(&c,context,users,&m,&info,f,&e))goto done;
        if(strcmp(c.suite,"loading")){
            struct prompt p={0};struct witness w={.ids=calloc(c.tg,sizeof(int32_t))};bool ok=w.ids&&make_prompt(m,depth+pp,context,&p,&e)&&p.n>depth;
            if(ok){char digest[65];ok=hash(p.ids,p.n*sizeof(*p.ids),digest);json_object *j=event("input");num(j,"point",point);num(j,"depth",depth);num(j,"users",users);num(j,"context_capacity",context);num(j,"prompt_tokens",(int64_t)p.n);str(j,"physical_ids_sha256",digest);json_object_object_add(j,"physical_ids",ids_json(p.ids,p.n));ok=ok&&emit(f,j);}
            for(unsigned rep=0;ok&&rep<c.warmups+c.repetitions;++rep)ok=sample(m,&p,depth,users,point,rep,rep<c.warmups,&c,info.vocab_tokens,&w,f,&e);
            free(p.ids);free(w.ids);if(!ok)goto done;
        }
        if(strcmp(c.suite,"single")&&lie_model_close(&m,&e)!=LIE_OK)goto done;
        if(interrupted)goto done;
    }
    code=0;
done:
    if(m&&lie_model_close(&m,&e)!=LIE_OK)code=1;
    json_object *end=event(code?"failed":"complete");num(end,"exit_code",code);if(code)str(end,"error",e.message);
    bool written=emit(f,end);if(fclose(f)||!written)code=1;
    if(!code&&c.graphs)code=graphs(&c);
    return code;
usage:
    fputs("Invalid arguments; use --help\n",stderr);return 2;
}
