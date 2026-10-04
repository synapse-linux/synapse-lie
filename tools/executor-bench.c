/* SPDX-License-Identifier: MIT */
/* C1 completed-work baseline over the selected LIE ABI, not a pristine oracle.
 * No HTTP, synthetic switch, kernel change, EOS override or automatic retry. */
#include "lie/executor.h"
#include <fcntl.h>
#include <float.h>
#include <json-c/json.h>
#include <math.h>
#include <openssl/evp.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define CONTEXT 9216u
#define CHUNK 2048u
#define OUTPUT 128u
#define PROFILES 3u
static const unsigned targets[PROFILES]={512,2048,8192};
static volatile sig_atomic_t interrupted;
static void stop(int sig) { (void)sig; interrupted=1; }
static void number(json_object *j,const char *k,int64_t v) { json_object_object_add(j,k,json_object_new_int64(v)); }
static void text(json_object *j,const char *k,const char *v) { json_object_object_add(j,k,json_object_new_string(v)); }
static json_object *event(const char *kind) { json_object *j=json_object_new_object(); text(j,"event",kind); return j; }
static bool record(FILE *f,json_object *j) {
    bool ok=fputs(json_object_to_json_string_ext(j,JSON_C_TO_STRING_PLAIN),f)>=0 && fputc('\n',f)!=EOF && fflush(f)==0;
    json_object_put(j); return ok;
}
static uint64_t ns(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC,&t)) return 0;
    return (uint64_t)t.tv_sec*UINT64_C(1000000000)+(uint64_t)t.tv_nsec;
}
static bool digest(const void *p,size_t n,char out[65]) {
    unsigned char bytes[EVP_MAX_MD_SIZE]; unsigned size=0;
    if (!EVP_Digest(p,n,bytes,&size,EVP_sha256(),NULL) || size!=32) return false;
    for (unsigned i=0;i<size;++i) snprintf(out+i*2,3,"%02x",bytes[i]);
    return true;
}
static json_object *tokens(const int32_t *p,size_t n) {
    json_object *a=json_object_new_array();
    for (size_t i=0;i<n;++i) json_object_array_add(a,json_object_new_int(p[i]));
    return a;
}
static json_object *identity(void) {
    json_object *j=event("identity");
    text(j,"program","lie-executor-bench"); text(j,"build_id",LIE_BUILD_ID);
    text(j,"engine",lie_backend_name()); text(j,"ownership",lie_backend_ownership());
    text(j,"dense_sampling",lie_backend_dense_sampling());
    text(j,"source_pin",lie_backend_source_pin());
    json_object_object_add(j,"synthetic",json_object_new_boolean(lie_backend_is_synthetic()));
    number(j,"context",CONTEXT); number(j,"chunk",CHUNK); number(j,"output_limit",OUTPUT);
    text(j,"timing","CLOCK_MONOTONIC; synchronous completed LIE calls; fresh session");
    text(j,"eos_policy","honor EOS; report actual emitted tokens, no replacement run");
    text(j,"scope","C1 embedded-provider baseline; not pristine numerical qualification or speedup");
    return j;
}
struct prompt { int32_t ids[CONTEXT]; size_t n; unsigned padding_lines; };
static lie_status render(lie_model *m,unsigned lines,struct prompt *p,lie_error *e) {
    static const char lead[]="Reference material follows. Ignore it for the counting task.\n";
    static const char pad[]="The quick brown fox jumps over the lazy dog.\n";
    static const char tail[]="\nList the integers from 1 to 10000, one integer per line. Start immediately at 1 and continue. Do not add an introduction, summary or code fence.";
    char content[sizeof(lead)+1024*(sizeof(pad)-1)+sizeof(tail)]; size_t at=0;
    memcpy(content,lead,sizeof(lead)-1); at+=sizeof(lead)-1;
    for (unsigned i=0;i<lines;++i) { memcpy(content+at,pad,sizeof(pad)-1); at+=sizeof(pad)-1; }
    memcpy(content+at,tail,sizeof(tail)-1); at+=sizeof(tail)-1;
    p->padding_lines=lines;
    lie_chat_message msg={LIE_CHAT_USER,content,at};
    return lie_model_chat_tokens(m,&msg,1,p->ids,CONTEXT,&p->n,e);
}
static bool make_prompt(lie_model *m,unsigned target,struct prompt *p,lie_error *e) {
    unsigned lo=0,hi=1024;
    while (lo<hi) {
        unsigned mid=lo+(hi-lo+1)/2;
        lie_status s=render(m,mid,p,e);
        if (s!=LIE_OK && s!=LIE_BUFFER_SMALL) return false;
        if (p->n>target) hi=mid-1; else lo=mid;
    }
    return render(m,lo,p,e)==LIE_OK && p->n>0 && p->n<=target && p->n+OUTPUT<CONTEXT;
}
static bool logits(lie_sequence *s,float *out,unsigned vocab,char hash[65],lie_error *e) {
    size_t n=0;
    if (lie_sequence_logits(s,out,vocab,&n,e)!=LIE_OK || n!=vocab) return false;
    for (size_t i=0;i<n;++i) if (!isfinite(out[i])) { snprintf(e->message,sizeof(e->message),"nonfinite frontier logits"); return false; }
    return digest(out,n*sizeof(*out),hash);
}
struct witness { float *pp,*tg; int32_t ids[OUTPUT]; unsigned count,position,stopped; };
static bool sample(lie_model *m,const struct prompt *p,unsigned profile,unsigned rep,
                   struct witness *w,unsigned vocab,FILE *file,lie_error *e) {
    lie_sequence *s=NULL; float *row=malloc((size_t)vocab*sizeof(*row));
    int32_t generated[OUTPUT]={0}; unsigned count=0,position=(unsigned)p->n,stopped=0;
    char pp_hash[65],tg_hash[65]; bool ok=false; uint64_t pp_start,pp_end,tg_start,tg_end;
    if (!row) { snprintf(e->message,sizeof(e->message),"logit allocation"); return false; }
    json_object *j=event("sample_begin"); number(j,"profile",profile); number(j,"rep",rep);
    if (!record(file,j) || lie_sequence_create(m,&s,e)!=LIE_OK) goto done;
    pp_start=ns();
    for (size_t at=0;at<p->n;) {
        at=p->n-at>CHUNK ? at+CHUNK : p->n;
        if (interrupted || lie_sequence_prefill(s,p->ids,at,e)!=LIE_OK) goto done;
    }
    pp_end=ns();
    /* Full host logits copy/finite checks and hashes are outside both intervals. */
    if (!logits(s,row,vocab,pp_hash,e)) goto done;
    if (!rep) memcpy(w->pp,row,(size_t)vocab*sizeof(*row));
    else if (memcmp(w->pp,row,(size_t)vocab*sizeof(*row))) { snprintf(e->message,sizeof(e->message),"prefill repeatability mismatch"); goto done; }
    tg_start=ns();
    for (unsigned i=0;i<OUTPUT;++i) {
        lie_decode_result d={0};
        if (interrupted || lie_sequence_decode(s,&d,e)!=LIE_OK) goto done;
        if (d.emitted>1 || d.stop>1 || (!d.emitted && !d.stop) ||
            d.position!=position+d.emitted || (d.emitted && (d.token<0 || (unsigned)d.token>=vocab))) {
            snprintf(e->message,sizeof(e->message),"invalid completed decode frontier"); goto done;
        }
        if (d.emitted) generated[count++]=d.token;
        position=d.position; stopped=d.stop;
        if (stopped) break;
    }
    tg_end=ns();
    if (interrupted || !pp_start || pp_end<=pp_start || !tg_start || tg_end<=tg_start || !logits(s,row,vocab,tg_hash,e)) goto done;
    if (!rep) {
        memcpy(w->tg,row,(size_t)vocab*sizeof(*row)); memcpy(w->ids,generated,count*sizeof(*generated));
        w->count=count; w->position=position; w->stopped=stopped;
    } else if (w->count!=count || w->position!=position || w->stopped!=stopped ||
               memcmp(w->tg,row,(size_t)vocab*sizeof(*row)) || memcmp(w->ids,generated,count*sizeof(*generated))) {
        snprintf(e->message,sizeof(e->message),"decode repeatability mismatch"); goto done;
    }
    j=event("sample"); number(j,"profile",profile); number(j,"rep",rep);
    json_object_object_add(j,"warmup",json_object_new_boolean(rep==0));
    number(j,"requested_prompt_target",targets[profile]); number(j,"prompt_tokens",(int64_t)p->n);
    number(j,"completed_decode_tokens",count); number(j,"final_position",position); number(j,"stop",stopped);
    number(j,"prefill_ns",(int64_t)(pp_end-pp_start)); number(j,"decode_ns",(int64_t)(tg_end-tg_start));
    text(j,"prefill_logits_sha256",pp_hash); text(j,"decode_logits_sha256",tg_hash);
    json_object_object_add(j,"output_ids",tokens(generated,count));
    json_object_object_add(j,"finite_logits",json_object_new_boolean(true));
    json_object_object_add(j,"matches_warmup",json_object_new_boolean(rep!=0));
    ok=record(file,j);
    fprintf(stderr,"profile=%u rep=%u pp=%zu tg=%u completed\n",profile,rep,p->n,count);
 done:
    if (s && lie_sequence_close(&s,e)!=LIE_OK) ok=false;
    free(row); return ok;
}
int main(int argc,char **argv) {
    _Static_assert(sizeof(float)==4 && FLT_RADIX==2 && FLT_MANT_DIG==24,"float32 witness required");
    const uint32_t one=1;
    if (*(const unsigned char *)&one!=1) { fprintf(stderr,"Little-endian witness required\n"); return 2; }
    if (argc==2 && !strcmp(argv[1],"--build-info")) return record(stdout,identity())?0:1;
    if (argc!=5 || strcmp(argv[1],"--model") || strcmp(argv[3],"--output")) {
        fprintf(stderr,"Usage: lie-executor-bench --model ORIGINAL-FIRST-SHARD --output NEW-JSONL\n"); return 2;
    }
    struct sigaction sa={0}; sa.sa_handler=stop; sigemptyset(&sa.sa_mask);
    if (sigaction(SIGINT,&sa,NULL) || sigaction(SIGTERM,&sa,NULL)) return 1;
    int fd=open(argv[4],O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600);
    if (fd<0) { perror("exclusive output"); return 1; }
    FILE *file=fdopen(fd,"w"); if (!file) { close(fd); return 1; }
    lie_model *model=NULL; lie_error error={{0}}; int code=1;
    struct prompt prompts[PROFILES]={0}; struct witness witnesses[PROFILES]={0};
    lie_model_options options={LIE_EXECUTOR_ABI,sizeof(options),CONTEXT,CHUNK,LIE_ROPE_NATIVE}; lie_model_info info={0};
    if (!record(file,identity()) || lie_backend_open(argv[2],&options,&model,&error)!=LIE_OK || interrupted ||
        lie_model_get_info(model,&info,&error)!=LIE_OK) goto done;
    if (info.abi_version!=LIE_EXECUTOR_ABI || info.context_tokens!=CONTEXT || !info.vocab_tokens || info.vocab_tokens>1048576) goto done;
    for (unsigned i=0;i<PROFILES;++i) {
        if (!make_prompt(model,targets[i],&prompts[i],&error)) goto done;
        witnesses[i].pp=malloc((size_t)info.vocab_tokens*sizeof(float));
        witnesses[i].tg=malloc((size_t)info.vocab_tokens*sizeof(float));
        if (!witnesses[i].pp || !witnesses[i].tg) goto done;
        json_object *j=event("input"); number(j,"profile",i); number(j,"target",targets[i]);
        number(j,"padding_lines",prompts[i].padding_lines);
        number(j,"prompt_tokens",(int64_t)prompts[i].n); number(j,"vocab",info.vocab_tokens);
        text(j,"fixture","synthetic reference padding plus pinned thinking-off chat template and counting task");
        json_object_object_add(j,"physical_ids",tokens(prompts[i].ids,prompts[i].n));
        if (!record(file,j)) goto done;
    }
    /* Fixed order: one warmup per profile, then three rounds asc/desc/asc. */
    for (unsigned rep=0;rep<4;++rep) for (unsigned i=0;i<PROFILES;++i) {
        unsigned profile=rep==2 ? PROFILES-i-1 : i;
        if (!sample(model,&prompts[profile],profile,rep,&witnesses[profile],info.vocab_tokens,file,&error)) goto done;
    }
    code=0;
 done:
    if (model && lie_model_close(&model,&error)!=LIE_OK) code=1;
    for (unsigned i=0;i<PROFILES;++i) { free(witnesses[i].pp); free(witnesses[i].tg); }
    if (interrupted) code=1;
    json_object *j=event(code?"failed":"complete");
    if (code) text(j,"error",interrupted?"interrupted after owned work completion":
                   error.message[0]?error.message:"benchmark allocation, timing or I/O validation failed");
    number(j,"exit_code",code);
    if (!record(file,j)) code=1;
    if (fclose(file)) code=1;
    return code;
}
