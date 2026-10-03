/* SPDX-License-Identifier: MIT */
/* Direct client of the production C core. Reports client and executor scopes. */
#include "lie/core.h"
#include "bench_native.h"
#include "lie/text.h"
#include <errno.h>
#include <fcntl.h>
#include <json-c/json.h>
#include <limits.h>
#include <openssl/evp.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
int lie_bench_graphs(const char *,const char *,const char *);
static volatile sig_atomic_t interrupted;
static void stop_signal(int signo) { (void)signo;interrupted=1; }
static uint64_t now(void) {
    struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t)||t.tv_sec<0)return 0;
    return (uint64_t)t.tv_sec*1000000000u+(uint64_t)t.tv_nsec;
}
static void number(json_object *o,const char *key,uint64_t n) { json_object_object_add(o,key,json_object_new_uint64(n)); }
static void text(json_object *o,const char *key,const char *s) { json_object_object_add(o,key,json_object_new_string(s)); }
static json_object *event(const char *name) { json_object *o=json_object_new_object();text(o,"event",name);return o; }
static bool emit(FILE *f,json_object *o) {
    bool ok=fputs(json_object_to_json_string_ext(o,JSON_C_TO_STRING_PLAIN),f)>=0 && fputc('\n',f)!=EOF && !fflush(f);
    json_object_put(o);return ok;
}
static bool integer(const char *s,unsigned lo,unsigned hi,unsigned *out) {
    char *end;errno=0;unsigned long value=strtoul(s,&end,10);
    if(errno||!*s||*s=='-'||*end||value<lo||value>hi)return false;
    *out=(unsigned)value;return true;
}
static json_object *ids_json(const int32_t *p,size_t n) {
    json_object *a=json_object_new_array();for(size_t i=0;i<n;++i)json_object_array_add(a,json_object_new_int(p[i]));return a;
}
static bool ids_hash(const int32_t *p,size_t n,char hex[65]) {
    EVP_MD_CTX *ctx=EVP_MD_CTX_new();if(!ctx)return false;
    bool ok=EVP_DigestInit_ex(ctx,EVP_sha256(),NULL)==1;
    for(size_t i=0;ok&&i<n;++i){uint32_t v=(uint32_t)p[i];unsigned char b[]={v,v>>8,v>>16,v>>24};ok=EVP_DigestUpdate(ctx,b,4)==1;}
    unsigned char bytes[32];unsigned count=0;
    ok=ok&&EVP_DigestFinal_ex(ctx,bytes,&count)==1&&count==32;EVP_MD_CTX_free(ctx);
    if(ok)for(unsigned i=0;i<32;++i)snprintf(hex+2*i,3,"%02x",bytes[i]);
    return ok;
}
static char *read_input(const char *path,size_t *bytes) {
    FILE *f=fopen(path,"rb");if(!f)return NULL;
    char *p=malloc(LIE_CHAT_BODY_BYTES+1u);if(!p){fclose(f);return NULL;}
    *bytes=fread(p,1,LIE_CHAT_BODY_BYTES+1u,f);
    bool valid=*bytes && *bytes<=LIE_CHAT_BODY_BYTES && !ferror(f);fclose(f);
    if(!valid){free(p);return NULL;}p[*bytes]=0;return p;
}
static bool wait_core(lie_core *c,lie_core_state wanted,uint64_t deadline) {
    for(;;){lie_core_info info;lie_core_snapshot(c,&info);if(info.state==wanted)return true;
        if(wanted!=LIE_STOPPED && (interrupted||info.state==LIE_FAILED||!now()||now()>=deadline))return false;
        struct pollfd fd={lie_core_fd(c),POLLIN,0};
        int rc=poll(&fd,1,100);if(rc<0&&errno!=EINTR)return false;
        if(rc>0)lie_core_drain(c);
    }
}
typedef struct {
    lie_job *job;uint64_t start,first,end,tokens,bytes;bool terminal;
} consumer;
typedef struct { int32_t *prompt;size_t count;bool initialized;int32_t output[LIE_CORE_MAX_OUTPUT];size_t output_count; } witness;
static bool sample(lie_core *c,const lie_core_request *r,unsigned users,unsigned rep,bool warmup,
                   unsigned timeout,witness *w,FILE *f,char error[256]) {
    consumer rows[LIE_CORE_JOBS]={0};bool ok=false;unsigned finished=0;
    uint64_t begin=now(),last=0,deadline=begin+(uint64_t)timeout*1000000u;
    if(!begin){snprintf(error,256,"clock failure");return false;}
    lie_core_info before;lie_core_snapshot(c,&before);
    for(unsigned i=0;i<users;++i){rows[i].start=now();
        if(!rows[i].start||lie_core_submit(c,r,&rows[i].job)){snprintf(error,256,"core admission refused");goto done;}}
    while(finished<users){
        if(interrupted||!now()||now()>=deadline){snprintf(error,256,"interrupted or core deadline exceeded");goto done;}
        struct pollfd fds[LIE_CORE_JOBS];nfds_t count=0;
        for(unsigned i=0;i<users;++i)if(!rows[i].terminal){
            lie_flow *flow=lie_job_flow(rows[i].job);
            if(lie_flow_drain(flow,LIE_FLOW_OUTPUT_READY)!=LIE_FLOW_OK)goto done;
            for(;;){lie_flow_event e;lie_flow_status rc=lie_flow_next(flow,&e);
                if(rc==LIE_FLOW_WOULD_BLOCK)break;
                if(rc!=LIE_FLOW_OK){snprintf(error,256,"core output contract failure");goto done;}
                uint64_t seen=now();
                if(!seen||seen<rows[i].start){
                    if(e.end==LIE_FLOW_ACTIVE)(void)lie_flow_release(flow,e.ticket);
                    snprintf(error,256,"clock failure");goto done;
                }
                if(e.end!=LIE_FLOW_ACTIVE){
                    rows[i].terminal=true;rows[i].end=seen;last=seen;++finished;
                    if(e.end!=LIE_FLOW_COMPLETE){lie_job_info info;lie_job_snapshot(rows[i].job,&info);
                        snprintf(error,256,"core job failed: %.220s",info.error);goto done;}
                    break;
                }
                if(!rows[i].first && e.tokens)rows[i].first=seen;
                bool ordered=e.token_offset==rows[i].tokens;
                rows[i].tokens+=e.tokens;rows[i].bytes+=e.bytes;
                if(lie_flow_release(flow,e.ticket)!=LIE_FLOW_OK||!ordered){snprintf(error,256,"core token order failure");goto done;}
                (void)lie_flow_request(flow,e.tokens);
            }
            if(!rows[i].terminal)fds[count++]=(struct pollfd){lie_flow_fd(flow,LIE_FLOW_OUTPUT_READY),POLLIN,0};
        }
        if(count && poll(fds,count,100)<0 && errno!=EINTR){snprintf(error,256,"core event wait failed");goto done;}
    }
    if(last<=begin){snprintf(error,256,"invalid core elapsed time");goto done;}
    /* Model retirement can follow the observable terminal by a few instructions. */
    for(unsigned i=0;i<users;++i)for(;;){lie_job_info info;lie_job_snapshot(rows[i].job,&info);if(info.retired)break;
        if(interrupted||now()>=deadline){snprintf(error,256,"core retirement deadline");goto done;}
        struct pollfd fd={lie_core_fd(c),POLLIN,0};if(poll(&fd,1,100)>0)lie_core_drain(c);
    }
    for(unsigned i=0;i<users;++i){
        lie_job_info info;lie_job_snapshot(rows[i].job,&info);size_t n=0;
        int32_t *input=malloc((size_t)info.prompt_tokens*sizeof(*input));
        int32_t output[LIE_CORE_MAX_OUTPUT];
        if(!input||!info.timing_valid||info.output_tokens!=rows[i].tokens||
           lie_job_prompt_tokens(rows[i].job,input,info.prompt_tokens,&n)!=LIE_OK||n!=info.prompt_tokens){
            free(input);snprintf(error,256,"core prompt/timing witness failed");goto done;}
        if(!w->initialized){
            w->prompt=input;w->count=n;input=NULL;
            char digest[65];if(!ids_hash(w->prompt,w->count,digest)){snprintf(error,256,"input digest failure");goto done;}
            json_object *in=event("input");number(in,"prompt_tokens",n);text(in,"physical_ids_sha256",digest);
            json_object_object_add(in,"physical_ids",ids_json(w->prompt,n));if(!emit(f,in))goto done;
        }else if(n!=w->count||memcmp(input,w->prompt,n*sizeof(*input))){free(input);snprintf(error,256,"physical prompt drift");goto done;}
        free(input);
        if(lie_job_output_tokens(rows[i].job,output,LIE_CORE_MAX_OUTPUT,&n)!=LIE_OK||n!=info.output_tokens){snprintf(error,256,"output witness failure");goto done;}
        if(w->initialized && (n!=w->output_count||memcmp(output,w->output,n*sizeof(*output)))){snprintf(error,256,"greedy output drift");goto done;}
        if(!w->initialized){w->output_count=n;memcpy(w->output,output,n*sizeof(*output));w->initialized=true;}
        json_object *job=event("job");number(job,"rep",rep);number(job,"warmup",warmup);number(job,"user",i);
        number(job,"prompt_tokens",info.prompt_tokens);number(job,"output_tokens",info.output_tokens);number(job,"output_bytes",rows[i].bytes);
        number(job,"prefill_tokens",info.prefill_tokens);number(job,"prefill_ns",info.prefill_ns);number(job,"decode_ns",info.decode_ns);
        number(job,"cached_tokens",info.cached_tokens);number(job,"cache_capture_ns",info.cache_capture_ns);number(job,"cache_restore_ns",info.cache_restore_ns);
        number(job,"ssd_cached_tokens",info.ssd_cached_tokens);number(job,"ssd_read_ns",info.ssd_read_ns);
        number(job,"prefill_calls",info.prefill_calls);number(job,"decode_calls",info.decode_calls);
        number(job,"total_ns",rows[i].end-rows[i].start);
        json_object_object_add(job,"first_token_ns",rows[i].first?json_object_new_uint64(rows[i].first-rows[i].start):NULL);
        text(job,"finish",info.finish==LIE_FINISH_STOP?"stop":"length");json_object_object_add(job,"output_ids",ids_json(output,n));
        if(!emit(f,job))goto done;
    }
    lie_core_info after;lie_core_snapshot(c,&after);
    json_object *point=event("sample");number(point,"rep",rep);number(point,"warmup",warmup);number(point,"users",users);
    uint64_t tokens=0;for(unsigned i=0;i<users;++i)tokens+=rows[i].tokens;
    number(point,"output_tokens",tokens);number(point,"wall_ns",last-begin);
    json_object_object_add(point,"output_per_total_wall_tps",json_object_new_double(tokens*1e9/(last-begin)));
    number(point,"decode_batches",after.decode_batches-before.decode_batches);number(point,"decode_batch_rows",after.decode_batch_rows-before.decode_batch_rows);
    number(point,"decode_single_calls",after.decode_single_calls-before.decode_single_calls);
    number(point,"cache_hits",after.cache.hits-before.cache.hits);number(point,"cache_misses",after.cache.misses-before.cache.misses);
    number(point,"cache_captures",after.cache.captures-before.cache.captures);number(point,"cache_evictions",after.cache.evictions-before.cache.evictions);
    number(point,"cache_skipped",after.cache.skipped-before.cache.skipped);
    number(point,"cache_retained_bytes",after.cache.retained_bytes);number(point,"cache_budget_bytes",after.cache.budget_bytes);
    number(point,"cache_expanded_bytes",after.cache.expanded_bytes);
    number(point,"cache_compressed_captures",after.cache.compressed_captures-before.cache.compressed_captures);
    number(point,"ssd_hits",after.ssd.hits-before.ssd.hits);number(point,"ssd_misses",after.ssd.misses-before.ssd.misses);
    number(point,"ssd_writes",after.ssd.writes-before.ssd.writes);number(point,"ssd_read_ns",after.ssd.read_ns-before.ssd.read_ns);
    number(point,"ssd_evictions",after.ssd.evictions-before.ssd.evictions);number(point,"ssd_skipped",after.ssd.skipped-before.ssd.skipped);
    number(point,"ssd_errors",after.ssd.errors-before.ssd.errors);
    number(point,"ssd_write_ns",after.ssd.write_ns-before.ssd.write_ns);number(point,"ssd_disk_bytes",after.ssd.disk_bytes);
    ok=emit(f,point);
done:
    for(unsigned i=0;i<users;++i)if(rows[i].job)lie_job_release(rows[i].job);
    return ok;
}
int lie_core_bench_main(int argc,char **argv) {
    const char *model=NULL,*output=NULL,*prompt_path=NULL,*tokens_path=NULL,*graphs=NULL;
    const char *encoder=NULL,*image_path=NULL;
    lie_store_options ssd={0};lie_cache_policy policy;lie_cache_policy_init(&policy);policy.enabled=LIE_DS4_CACHE_POLICY!=0;
    unsigned context=4096,chunk=2048,users=1,tg=128,repetitions=3,warmups=0,timeout=600000;
    unsigned cache_mib=(unsigned)(LIE_PREFIX_CACHE_DEFAULT_BYTES/(1024u*1024u));
    bool build_info=false;unsigned seen=0;
    for(int i=1;i<argc;++i){
        if(!strcmp(argv[i],"--help")){puts("Usage: synapse-lie-bench --suite core --model FIRST-SHARD --output NEW-JSONL\n  (--prompt-file UTF8 | --tokens-file JSON-INT-ARRAY) [--context 4096]\n  [--model-vision ENCODER.gguf --image-file PNG-OR-JPEG] [--chunk 2048] [--users 1..8] [--tg 128] [--warmups 0] [--repetitions 3]\n  [--timeout-ms 600000] [--graphs DIRECTORY] [--kv-cache-ram-mb 4096] [--kv-cache-policy ds4|legacy]\n  [--kv-cache-min-tokens 512] [--kv-cache-cold-max-tokens 30000] [--kv-cache-continued-interval-tokens 10000]\n  [--kv-cache-boundary-trim-tokens 32] [--kv-cache-boundary-align-tokens 2048] [--kv-cache-text-prefix on|off] [--kv-cache-capture-finish on|off]\n  [--kv-disk-dir ABSOLUTE-DIRECTORY --kv-disk-space-mb N --kv-disk-staging-mb N]\nDirect shared reactive core; raw text has no chat template. Greedy AR, RAM prefix cache on by default (zero disables); KV disk persistence is opt-in; vision requires a prompt file, explicit encoder, one image file and both KV caches off; MTP is separate.\nReports core-client total/first-token latency and separate per-job executor calls.\nShared GPU requires coordinated admission. Synthetic builds are NOT-INFERENCE.");return 0;}
        if(!strcmp(argv[i],"--build-info")){build_info=true;continue;}
        if(i+1==argc)goto usage;
        const char *key=lie_cache_option_name(argv[i]),*value=argv[++i];unsigned bit=0;
        if(!strcmp(key,"--suite")){bit=1u;if(strcmp(value,"core"))goto usage;}
        else if(!strcmp(key,"--model")){bit=2u;model=value;}
        else if(!strcmp(key,"--model-vision")){bit=131072u;encoder=value;}
        else if(!strcmp(key,"--image-file")){bit=262144u;image_path=value;}
        else if(!strcmp(key,"--output")){bit=4u;output=value;}
        else if(!strcmp(key,"--prompt-file")){bit=8u;prompt_path=value;}
        else if(!strcmp(key,"--tokens-file")){bit=16u;tokens_path=value;}
        else if(!strcmp(key,"--context")){bit=32u;if(!integer(value,128,LIE_CORE_MAX_CONTEXT,&context))goto usage;}
        else if(!strcmp(key,"--chunk")){bit=64u;if(!integer(value,1,2048,&chunk))goto usage;}
        else if(!strcmp(key,"--users")){bit=128u;if(!integer(value,1,LIE_CORE_JOBS,&users))goto usage;}
        else if(!strcmp(key,"--tg")){bit=256u;if(!integer(value,1,LIE_CORE_MAX_OUTPUT,&tg))goto usage;}
        else if(!strcmp(key,"--repetitions")){bit=512u;if(!integer(value,1,100,&repetitions))goto usage;}
        else if(!strcmp(key,"--warmups")){bit=1024u;if(!integer(value,0,10,&warmups))goto usage;}
        else if(!strcmp(key,"--timeout-ms")){bit=2048u;if(!integer(value,1,3600000,&timeout))goto usage;}
        else if(!strcmp(key,"--graphs")){bit=4096u;graphs=value;}
        else if(!strcmp(key,"--kv-cache-ram-mb")){bit=8192u;if(!integer(value,0,1048576,&cache_mib))goto usage;}
        else if(!strcmp(key,"--kv-disk-dir")){bit=16384u;ssd.directory=value;}
        else if(!strcmp(key,"--kv-disk-space-mb")){unsigned mib;bit=32768u;if(!integer(value,1,1048576,&mib))goto usage;ssd.quota_bytes=(uint64_t)mib*1024u*1024u;}
        else if(!strcmp(key,"--kv-disk-staging-mb")){unsigned mib;bit=65536u;if(!integer(value,1,1048576,&mib))goto usage;ssd.staging_bytes=(uint64_t)mib*1024u*1024u;}
        else if(lie_cache_policy_option(&policy,key,value)!=1)goto usage;
        if(seen&bit)goto usage;
        seen|=bit;
    }
    if((ssd.directory&&(*ssd.directory!='/'||!ssd.quota_bytes||!ssd.staging_bytes))||
       (!ssd.directory&&(ssd.quota_bytes||ssd.staging_bytes)))goto usage;
    if((encoder||image_path)&&(!LIE_VISION||!encoder||!*encoder||!image_path||!*image_path||!prompt_path||cache_mib||ssd.directory))goto usage;
    json_object *identity=event("identity");text(identity,"schema","synapse-lie.core-bench.v1");text(identity,"suite","core");
    text(identity,"execution","shared-reactive-core");text(identity,"vision_model",encoder?encoder:"");text(identity,"provider",lie_backend_name());text(identity,"build_id",LIE_BUILD_ID);
    text(identity,"ownership",lie_backend_ownership());text(identity,"source_pin",lie_backend_source_pin());
    json_object_object_add(identity,"synthetic",json_object_new_boolean(lie_backend_is_synthetic()));
    text(identity,"scope","core client submit through confirmed output; per-job executor durations overlap in batches; cache transfer timing is separate; no HTTP");
    text(identity,"cache_policy",ssd.directory?(cache_mib?"ram+ssd":"ssd"):(cache_mib?"ram":"off"));number(identity,"prefix_cache_bytes",(uint64_t)cache_mib*1024u*1024u);
    text(identity,"cache_retention_policy",LIE_CACHE_UTILITY?"ds4-time-token-byte-utility-v1":"lru");
    json_object_object_add(identity,"checkpoint_compression",json_object_new_boolean(lie_state_compression_enabled()));
    text(identity,"checkpoint_codec",lie_state_compression_codec());
    text(identity,"state_format",lie_backend_state_format());
    text(identity,"checkpoint_policy",policy.enabled?"ds4":"legacy");
    number(identity,"cache_min_tokens",policy.min_tokens);number(identity,"cache_cold_max_tokens",policy.cold_max_tokens);
    number(identity,"cache_continued_tokens",policy.continued_interval_tokens);number(identity,"cache_trim_tokens",policy.boundary_trim_tokens);
    number(identity,"cache_align_tokens",policy.boundary_align_tokens);
    json_object_object_add(identity,"cache_text_prefix",json_object_new_boolean(policy.text_prefix));
    json_object_object_add(identity,"cache_capture_finish",json_object_new_boolean(policy.capture_finish));
    number(identity,"ssd_quota_bytes",ssd.quota_bytes);number(identity,"ssd_staging_bytes",ssd.staging_bytes);
    number(identity,"context_capacity",context);number(identity,"prefill_chunk",chunk);number(identity,"users",users);
    number(identity,"output_limit",tg);number(identity,"warmups",warmups);number(identity,"repetitions",repetitions);
    if(build_info)return emit(stdout,identity)?0:1;
    if(!model||!*model||!output||!*output||!!prompt_path==!!tokens_path||tg>=context){json_object_put(identity);goto usage;}
    lie_core_request request;lie_core_request_init(&request);request.max_tokens=tg;
    size_t bytes=0;char *data=read_input(prompt_path?prompt_path:tokens_path,&bytes);int32_t *ids=NULL;
    if(!data){json_object_put(identity);goto usage;}
    if(prompt_path){request.kind=LIE_INPUT_TEXT;request.text=data;request.text_bytes=bytes;
        if(!lie_utf8_valid(data,bytes,false)){free(data);json_object_put(identity);goto usage;}}
    else {
        json_tokener *t=json_tokener_new_ex(4);if(!t){free(data);json_object_put(identity);return 1;}
        json_tokener_set_flags(t,JSON_TOKENER_STRICT);json_object *array=json_tokener_parse_ex(t,data,(int)bytes+1);
        size_t end=json_tokener_get_parse_end(t);while(end<bytes&&(data[end]==' '||data[end]=='\n'||data[end]=='\r'||data[end]=='\t'))++end;
        bool valid=json_tokener_get_error(t)==json_tokener_success&&(end==bytes||end==bytes+1)&&json_object_is_type(array,json_type_array);
        size_t n=valid?json_object_array_length(array):0;valid=valid&&n>0&&n<=context-tg;
        if(valid){ids=malloc(n*sizeof(*ids));valid=ids!=NULL;}
        for(size_t i=0;valid&&i<n;++i){json_object *v=json_object_array_get_idx(array,i);int64_t value=json_object_get_int64(v);
            valid=json_object_is_type(v,json_type_int)&&value>=0&&value<=INT32_MAX;if(valid)ids[i]=(int32_t)value;}
        json_object_put(array);json_tokener_free(t);
        if(!valid){free(ids);free(data);json_object_put(identity);goto usage;}
        request.kind=LIE_INPUT_TOKENS;request.tokens=ids;request.token_count=n;
    }
    text(identity,"input_kind",image_path?"messages-with-image":prompt_path?"raw-text":"physical-tokens");
    struct sigaction sa={0};sa.sa_handler=stop_signal;sigemptyset(&sa.sa_mask);
    if(sigaction(SIGINT,&sa,NULL)||sigaction(SIGTERM,&sa,NULL)){free(ids);free(data);json_object_put(identity);return 1;}
    int fd=open(output,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
    if(fd<0){perror("exclusive core benchmark output");free(ids);free(data);json_object_put(identity);return 1;}
    FILE *f=fdopen(fd,"w");if(!f){close(fd);free(ids);free(data);json_object_put(identity);return 1;}
    int code=1;lie_core *core=NULL;char error[256]="core benchmark failed";witness w={0};
    char *encoded=NULL;lie_image_input image={0};lie_chat_message message={0};
    if(image_path){
        size_t image_bytes=0;encoded=read_input(image_path,&image_bytes);
        image=(lie_image_input){.data=(const unsigned char *)encoded,.bytes=image_bytes,.format=LIE_IMAGE_PNG};
        lie_image_dimensions dimensions;
        if(lie_image_inspect(&image,&dimensions,NULL)!=LIE_OK){image.format=LIE_IMAGE_JPEG;
            if(lie_image_inspect(&image,&dimensions,NULL)!=LIE_OK){snprintf(error,256,"invalid PNG/JPEG image header or budget");emit(f,identity);goto done;}}
        char image_hash[65];if(!nb_hash(encoded,image_bytes,image_hash)){emit(f,identity);goto done;}
        text(identity,"image_sha256",image_hash);number(identity,"image_bytes",image_bytes);
        message=(lie_chat_message){LIE_CHAT_USER,data,bytes};image.text_offset=bytes;
        request.kind=LIE_INPUT_MESSAGES;request.text=NULL;request.text_bytes=0;
        request.chat.messages=&message;request.chat.count=1;request.images=&image;request.image_count=1;
    }
    if(!emit(f,identity))goto done;
    uint64_t started=now();lie_core_options options;lie_core_options_init(&options);options.model_path=model;options.context=context;options.vision_model_path=encoder;
    options.chunk=chunk;options.max_active=users;options.prefix_cache_bytes=(uint64_t)cache_mib*1024u*1024u;options.ssd=ssd;options.cache_policy=policy;
    core=lie_core_create(&options);
    if(!started||!core||!wait_core(core,LIE_READY,started+(uint64_t)timeout*1000000u)){snprintf(error,256,"core readiness failed");goto done;}
    json_object *ready=event("core_ready");number(ready,"load_to_ready_ns",now()-started);if(!emit(f,ready))goto done;
    for(unsigned rep=0;rep<warmups+repetitions;++rep)if(!sample(core,&request,users,rep,rep<warmups,timeout,&w,f,error))goto done;
    code=0;
done:
    if(core){lie_core_stop(core);if(!wait_core(core,LIE_STOPPED,0))code=1;else {
        if(ssd.directory){lie_core_info info;lie_core_snapshot(core,&info);json_object *store=event("ssd_drained");
            number(store,"writes",info.ssd.writes);number(store,"errors",info.ssd.errors);number(store,"disk_bytes",info.ssd.disk_bytes);
            number(store,"evictions",info.ssd.evictions);number(store,"skipped",info.ssd.skipped);
            number(store,"allocated_bytes",info.ssd.allocated_bytes);number(store,"entries",info.ssd.entries);
            number(store,"write_ns",info.ssd.write_ns);number(store,"pending",info.ssd.pending);if(!emit(f,store))code=1;}
        lie_core_destroy(core);
    }}
    json_object *end=event(code?"failed":"complete");number(end,"exit_code",code);if(code)text(end,"error",error);
    bool written=emit(f,end);if(fclose(f)||!written)code=1;
    free(encoded);free(w.prompt);free(ids);free(data);
    if(!code&&graphs)code=lie_bench_graphs(output,graphs,NULL);
    return code;
usage:
    fputs("Invalid core benchmark arguments; use --suite core --help\n",stderr);return 2;
}
