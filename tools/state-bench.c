/* SPDX-License-Identifier: MIT */
/* Completed C-owned component-state qualification, no HTTP or opaque payload. */
#include "lie/state.h"
#include "lie/store.h"
#include <errno.h>
#include <fcntl.h>
#include <json-c/json.h>
#include <math.h>
#include <openssl/evp.h>
#include <poll.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#define STEPS 16u
static volatile sig_atomic_t interrupted;
static void stop(int sig){(void)sig;interrupted=1;}
static uint64_t ns(void){struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))return 0;return (uint64_t)t.tv_sec*1000000000u+t.tv_nsec;}
static void num(json_object *j,const char *k,uint64_t v){json_object_object_add(j,k,json_object_new_uint64(v));}
static void str(json_object *j,const char *k,const char *v){json_object_object_add(j,k,json_object_new_string(v));}
static json_object *event(const char *s){json_object *j=json_object_new_object();str(j,"event",s);return j;}
static bool emit(FILE *f,json_object *j){bool ok=fputs(json_object_to_json_string_ext(j,JSON_C_TO_STRING_PLAIN),f)>=0&&fputc('\n',f)!=EOF&&fflush(f)==0;json_object_put(j);return ok;}
static bool hash(const void *p,size_t n,char out[65]){unsigned char b[32];unsigned count=0;if(!EVP_Digest(p,n,b,&count,EVP_sha256(),NULL)||count!=32)return false;for(unsigned i=0;i<32;++i)snprintf(out+i*2,3,"%02x",b[i]);return true;}
static json_object *identity(void){
    json_object *j=event("identity");str(j,"schema","synapse-lie.state-bench.v1");str(j,"suite","state");str(j,"build_id",LIE_BUILD_ID);
    str(j,"engine",lie_backend_name());str(j,"ownership",lie_backend_ownership());str(j,"source_pin",lie_backend_source_pin());
    json_object_object_add(j,"synthetic",json_object_new_boolean(lie_backend_is_synthetic()));
    json_object_object_add(j,"checkpoint_compression",json_object_new_boolean(lie_state_compression_enabled()));
    str(j,"checkpoint_codec",lie_state_compression_codec());
    num(j,"state_abi",LIE_STATE_ABI);str(j,"scope","C17 typed state; RAM pairs or explicit SSD write/read across processes; exact full logits each AR step; fresh sampler; no MTP/vision");return j;
}
static bool integer(const char *s,unsigned *v){char *end=NULL;unsigned long n=strtoul(s,&end,10);if(!*s||*end||*s=='-'||!n||n>1048576)return false;*v=(unsigned)n;return true;}
static bool prefill(lie_sequence *s,const int32_t *tokens,unsigned from,unsigned to,unsigned chunk,lie_error *e){
    while(from<to){from+=to-from>chunk?chunk:to-from;if(interrupted||lie_sequence_prefill(s,tokens,from,e)!=LIE_OK)return false;}return true;
}
static bool frontier(lie_sequence *s,float *out,unsigned vocab,lie_error *e){
    size_t n=0;if(lie_sequence_logits(s,out,vocab,&n,e)!=LIE_OK||n!=vocab)return false;
    for(unsigned i=0;i<vocab;++i)if(!isfinite(out[i]))return false;
    return true;
}
static bool store_wait(lie_store *store,lie_store_result *result){
    uint64_t start=ns();
    while(!interrupted&&ns()-start<UINT64_C(300)*1000000000){
        if(lie_store_take(store,result))return true;
        struct pollfd fd={lie_store_fd(store),POLLIN,0};
        if(poll(&fd,1,100)<0&&errno!=EINTR)return false;
    }
    return false;
}
int lie_state_bench_main(int argc,char **argv){
    const char *model=NULL,*output=NULL,*input=NULL;unsigned context=262144,chunk=2048,checkpoint=0;bool info=false;unsigned seen=0;
    const char *ssd_mode=NULL;lie_store_options ssd={0};
    for(int i=1;i<argc;++i){
        if(!strcmp(argv[i],"--build-info")){info=true;continue;}
        if(!strcmp(argv[i],"--help")){puts("Usage: synapse-lie-bench --suite state --model FIRST-SHARD --output NEW-JSONL --tokens-file JSON-IDS --pp CHECKPOINT [--context 262144] [--chunk 2048]\nThree fresh/restored pairs: greedy, seeded sampling, independent greedy clone; full logits at every step.\nOptional SSD: --state-ssd-mode write|read --prefix-ssd-dir PRIVATE-PATH --prefix-ssd-quota-mib N --prefix-ssd-staging-mib N.\nWrite requires an empty store and durably saves one checkpoint; read requires an exact checkpoint from an earlier process and runs the three pairs.\nPrefix checkpoint must align to chunks unless it is the whole prompt. RAM capture budget: 4 GiB. MTP/vision unsupported. Shared GPU requires leased supervisor.");return 0;}
        if(i+1==argc)goto usage;
        const char *k=argv[i],*v=argv[++i];unsigned bit=0;
        if(!strcmp(k,"--suite")){bit=1;if(strcmp(v,"state"))goto usage;}
        else if(!strcmp(k,"--model")){bit=2;model=v;}
        else if(!strcmp(k,"--output")){bit=4;output=v;}
        else if(!strcmp(k,"--tokens-file")){bit=8;input=v;}
        else if(!strcmp(k,"--context")){bit=16;if(!integer(v,&context))goto usage;}
        else if(!strcmp(k,"--chunk")){bit=32;if(!integer(v,&chunk)||chunk>2048)goto usage;}
        else if(!strcmp(k,"--pp")){bit=64;if(!integer(v,&checkpoint))goto usage;}
        else if(!strcmp(k,"--state-ssd-mode")){bit=128;ssd_mode=v;if(strcmp(v,"write")&&strcmp(v,"read"))goto usage;}
        else if(!strcmp(k,"--prefix-ssd-dir")){bit=256;ssd.directory=v;if(*v!='/')goto usage;}
        else if(!strcmp(k,"--prefix-ssd-quota-mib")){unsigned value;bit=512;if(!integer(v,&value))goto usage;ssd.quota_bytes=(uint64_t)value*1024*1024;}
        else if(!strcmp(k,"--prefix-ssd-staging-mib")){unsigned value;bit=1024;if(!integer(v,&value))goto usage;ssd.staging_bytes=(uint64_t)value*1024*1024;}
        else goto usage;
        if(seen&bit)goto usage;
        seen|=bit;
    }
    if((seen&1920)&&((seen&1920)!=1920))goto usage;
    if(info)return emit(stdout,identity())?0:1;
    if(!model||!output||!input||!checkpoint||context<=STEPS||!lie_backend_prefix_state_supported())goto usage;
    int fd=open(input,O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK);struct stat sb;
    if(fd<0)return 2;
    if(fstat(fd,&sb)||!S_ISREG(sb.st_mode)||sb.st_size<=0||sb.st_size>8*1024*1024){close(fd);return 2;}
    char *raw=malloc((size_t)sb.st_size+1);if(!raw){close(fd);return 1;}
    size_t at=0;while(at<(size_t)sb.st_size){ssize_t n=read(fd,raw+at,(size_t)sb.st_size-at);if(n<=0)break;at+=(size_t)n;}close(fd);
    raw[at]=0;json_tokener *parser=json_tokener_new();json_tokener_set_flags(parser,JSON_TOKENER_STRICT);
    json_object *array=json_tokener_parse_ex(parser,raw,(int)at+1);
    bool valid=at==(size_t)sb.st_size&&json_tokener_get_error(parser)==json_tokener_success&&json_object_is_type(array,json_type_array);
    size_t end=json_tokener_get_parse_end(parser);while(end<at&&strchr(" \t\r\n",raw[end]))++end;
    valid=valid&&(end==at||end==at+1);unsigned n=valid?(unsigned)json_object_array_length(array):0;
    valid=valid&&n&&n<=context-STEPS&&checkpoint<=n&&(checkpoint==n||checkpoint%chunk==0);
    int32_t *tokens=valid?malloc((size_t)n*sizeof(*tokens)):NULL;valid=valid&&tokens;
    for(unsigned i=0;valid&&i<n;++i){json_object *v=json_object_array_get_idx(array,i);int64_t x=json_object_get_int64(v);valid=json_object_is_type(v,json_type_int)&&x>=0&&x<=INT32_MAX;if(valid)tokens[i]=(int32_t)x;}
    json_object_put(array);json_tokener_free(parser);free(raw);if(!valid){free(tokens);goto usage;}
    fd=open(output,O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600);if(fd<0){free(tokens);return 1;}
    FILE *f=fdopen(fd,"w");if(!f){close(fd);free(tokens);return 1;}
    struct sigaction sa={0};sa.sa_handler=stop;sigemptyset(&sa.sa_mask);sigaction(SIGINT,&sa,NULL);sigaction(SIGTERM,&sa,NULL);
    lie_model *m=NULL;lie_sequence *s=NULL;lie_state *state=NULL;lie_error e={0};float *witness=NULL,*row=NULL;int code=1;
    lie_store *store=NULL;lie_store_result disk={0};bool read_ssd=ssd_mode&&!strcmp(ssd_mode,"read");
    lie_model_options o={LIE_EXECUTOR_ABI,sizeof(o),context,chunk};lie_model_info mi={0};
    uint64_t load_start=ns();
    if(!emit(f,identity())||lie_backend_open(model,&o,&m,&e)!=LIE_OK||lie_model_get_info(m,&mi,&e)!=LIE_OK||!mi.vocab_tokens||mi.vocab_tokens>1048576)goto done;
    uint64_t load_ns=ns()-load_start;
    for(unsigned i=0;i<n;++i)if((uint32_t)tokens[i]>=mi.vocab_tokens)goto done;
    witness=malloc((STEPS+1)*(size_t)mi.vocab_tokens*sizeof(float));row=malloc((size_t)mi.vocab_tokens*sizeof(float));if(!witness||!row)goto done;
    char input_hash[65];if(!hash(tokens,(size_t)n*sizeof(*tokens),input_hash))goto done;
    json_object *j=event("input");str(j,"physical_ids_sha256",input_hash);num(j,"prompt_tokens",n);num(j,"checkpoint_tokens",checkpoint);num(j,"context",context);num(j,"chunk",chunk);num(j,"vocab",mi.vocab_tokens);if(!emit(f,j))goto done;
    lie_state_layout layout;uint64_t bytes=0,start=ns();
    if(ssd_mode){
        lie_state_identity id;uint64_t domain=0;char hex[65];
        if(lie_model_state_identity(m,&id,&domain,&e)!=LIE_OK)goto done;
        uint64_t identity_ns=ns()-start;
        for(unsigned i=0;i<32;++i)snprintf(hex+i*2,3,"%02x",id.bytes[i]);
        j=event("ssd_identity");str(j,"mode",ssd_mode);str(j,"stable_identity_sha256",hex);
        num(j,"model_load_ns",load_ns);num(j,"identity_ns",identity_ns);num(j,"quota_bytes",ssd.quota_bytes);num(j,"staging_bytes",ssd.staging_bytes);
        if(!emit(f,j)||lie_store_open(&ssd,&id,domain,&store,&e)!=LIE_OK)goto done;
    }
    if(read_ssd){
        uint64_t ticket=lie_store_read(store,tokens,checkpoint,chunk);
        if(!ticket||!store_wait(store,&disk)||!disk.read||disk.ticket!=ticket||!disk.state){snprintf(e.message,sizeof(e.message),"required SSD checkpoint unavailable");goto done;}
        state=disk.state;const lie_state_layout *stored=lie_state_description(state);
        if(stored->token_count!=checkpoint||memcmp(tokens,lie_state_tokens(state),(size_t)checkpoint*sizeof(*tokens))){snprintf(e.message,sizeof(e.message),"SSD checkpoint frontier mismatch");goto done;}
        lie_store_info si;lie_store_snapshot(store,&si);
        if(si.errors||si.hits!=1||si.lookups!=1)goto done;
        j=event("ssd_read");num(j,"retained_bytes",lie_state_bytes(state));num(j,"expanded_bytes",lie_state_expanded_bytes(state));
        json_object_object_add(j,"compressed",json_object_new_boolean(lie_state_is_compressed(state)));num(j,"sections",stored->section_count);
        num(j,"read_ns",disk.read_ns);num(j,"read_bytes",si.read_bytes);num(j,"peak_staging_bytes",si.peak_staging_bytes);
        if(!emit(f,j))goto done;
    }else{
        if(store){lie_store_info si;lie_store_snapshot(store,&si);if(si.entries){snprintf(e.message,sizeof(e.message),"SSD write requires an empty store");goto done;}}
        if(lie_sequence_create(m,&s,&e)!=LIE_OK||!prefill(s,tokens,0,checkpoint,chunk,&e))goto done;
        start=ns();
        if(lie_state_plan(s,&layout,&bytes,&e)!=LIE_OK||lie_state_capture(s,&layout,ssd_mode?ssd.staging_bytes:UINT64_C(4)*1024*1024*1024,&state,&e)!=LIE_OK)goto done;
        (void)lie_state_compress(&state,ssd_mode?ssd.staging_bytes:UINT64_C(4)*1024*1024*1024);
        j=event("capture");num(j,"retained_bytes",lie_state_bytes(state));num(j,"expanded_bytes",lie_state_expanded_bytes(state));
        json_object_object_add(j,"compressed",json_object_new_boolean(lie_state_is_compressed(state)));
        num(j,"sections",layout.section_count);num(j,"capture_ns",ns()-start);if(!emit(f,j)||lie_sequence_close(&s,&e)!=LIE_OK)goto done;
        if(store){
            if(!lie_store_write(store,state)||!store_wait(store,&disk))goto done;
            lie_store_result_release(store,&disk);disk=(lie_store_result){0};lie_store_info si;lie_store_snapshot(store,&si);
            if(si.writes!=1||si.errors||si.pending){snprintf(e.message,sizeof(e.message),"SSD durable write failed");goto done;}
            j=event("ssd_write");num(j,"writes",si.writes);num(j,"write_ns",si.write_ns);num(j,"written_bytes",si.written_bytes);
            num(j,"disk_bytes",si.disk_bytes);num(j,"allocated_bytes",si.allocated_bytes);num(j,"peak_staging_bytes",si.peak_staging_bytes);
            if(!emit(f,j))goto done;
            code=0;goto done;
        }
    }
    for(unsigned pair=0;pair<3;++pair){
        lie_generation_options gen={.abi_version=LIE_GENERATION_ABI,.struct_bytes=sizeof(gen),.temperature=pair==1?.7:0,.top_p=.9,.seed=123,.frequency_penalty=pair==1?.1:0,.presence_penalty=pair==1?.1:0};
        lie_decode_result expected[STEPS]={0};unsigned count=0;uint64_t pp_ns=0,restore_ns=0,tail_ns=0;char hashes[2][65];
        for(unsigned restored=0;restored<2;++restored){
            if(lie_sequence_create(m,&s,&e)!=LIE_OK||lie_sequence_configure(s,&gen,&e)!=LIE_OK)goto done;
            start=ns();if(restored&&lie_state_restore(s,state,&e)!=LIE_OK)goto done;
            if(restored)restore_ns=ns()-start;
            start=ns();if(!prefill(s,tokens,restored?checkpoint:0,n,chunk,&e))goto done;
            if(restored)tail_ns=ns()-start;else pp_ns=ns()-start;
            for(unsigned step=0;step<=STEPS;++step){
                if(interrupted||!frontier(s,row,mi.vocab_tokens,&e))goto done;
                float *reference=witness+(size_t)step*mi.vocab_tokens;
                if(!restored)memcpy(reference,row,(size_t)mi.vocab_tokens*sizeof(float));
                else if(memcmp(reference,row,(size_t)mi.vocab_tokens*sizeof(float))){snprintf(e.message,sizeof(e.message),"state logits mismatch pair=%u step=%u",pair,step);goto done;}
                if(step==STEPS||(step&&expected[step-1].stop)){if(!hash(witness,(size_t)(step+1)*mi.vocab_tokens*sizeof(float),hashes[restored]))goto done;break;}
                lie_decode_result d={0};if(lie_sequence_decode(s,&d,&e)!=LIE_OK||d.emitted>1||d.stop>1||(!d.emitted&&!d.stop))goto done;
                if(!restored){expected[step]=d;count=step+1;}
                else if(d.token!=expected[step].token||d.position!=expected[step].position||d.emitted!=expected[step].emitted||d.stop!=expected[step].stop){snprintf(e.message,sizeof(e.message),"state decode mismatch");goto done;}
            }
            if(lie_sequence_close(&s,&e)!=LIE_OK)goto done;
        }
        j=event("pair");num(j,"pair",pair);num(j,"decode_calls",count);num(j,"fresh_prefill_ns",pp_ns);num(j,"restore_ns",restore_ns);num(j,"tail_prefill_ns",tail_ns);num(j,"reused_tokens",checkpoint);num(j,"new_tokens",n-checkpoint);
        str(j,"generation",pair==1?"seeded-sampling":"greedy");str(j,"full_logits_sha256",hashes[0]);num(j,"exact_logits_and_tokens",1);
        json_object *ids=json_object_new_array();for(unsigned i=0;i<count;++i)if(expected[i].emitted)json_object_array_add(ids,json_object_new_int(expected[i].token));json_object_object_add(j,"output_ids",ids);
        if(!emit(f,j))goto done;
    }
    code=0;
done:
    if(s&&lie_sequence_close(&s,&e)!=LIE_OK)code=1;
    if(disk.ticket){if(read_ssd)state=NULL;lie_store_result_release(store,&disk);}
    lie_store_close(&store);
    lie_state_destroy(&state);if(m&&lie_model_close(&m,&e)!=LIE_OK)code=1;
    free(tokens);free(witness);free(row);json_object *last=event(code?"failed":"complete");num(last,"exit_code",code);if(code)str(last,"error",e.message[0]?e.message:"state qualification bounds, interrupted, allocation or I/O failure");
    bool written=emit(f,last);if(fclose(f)||!written)code=1;return code;
usage:fputs("Invalid state benchmark arguments; use --suite state --help\n",stderr);return 2;
}
