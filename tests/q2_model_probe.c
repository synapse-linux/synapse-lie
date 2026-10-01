/* SPDX-License-Identifier: MIT */
/* First real Q2 test, not a stable benchmark or independent numerical oracle. */
#include "lie/executor.h"
#include "q2_model_memory.h"
#include <fcntl.h>
#include <inttypes.h>
#include <json-c/json.h>
#include <math.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#define CONTEXT 9216u
#define OUTPUT 128u
extern int lie_q2_model_admit(const char *, uint64_t, lie_q2_test_memory *, char *, size_t);
static volatile sig_atomic_t interrupted;
static void stop(int s) { (void)s; interrupted = 1; }
static void num(json_object *j, const char *k, uint64_t n) { json_object_object_add(j,k,json_object_new_uint64(n)); }
static void str(json_object *j, const char *k, const char *s) { json_object_object_add(j,k,json_object_new_string(s)); }
static json_object *event(const char *kind) { json_object *j=json_object_new_object(); str(j,"event",kind); return j; }
static bool emit(FILE *f, json_object *j) {
    bool ok=fputs(json_object_to_json_string_ext(j,JSON_C_TO_STRING_PLAIN),f)>=0 && fputc('\n',f)!=EOF && fflush(f)==0;
    json_object_put(j); return ok;
}
static uint64_t clock_ns(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC,&t) || t.tv_sec<0 || t.tv_nsec<0 || t.tv_nsec>=1000000000 ||
        (uint64_t)t.tv_sec > (UINT64_MAX-999999999)/1000000000) return 0;
    return (uint64_t)t.tv_sec*1000000000+(uint64_t)t.tv_nsec;
}
static uint64_t available(void) {
    FILE *f=fopen("/proc/meminfo","r"); if (!f) return 0;
    char line[256]; uint64_t kb=0;
    while (fgets(line,sizeof line,f)) if (sscanf(line,"MemAvailable: %" SCNu64 " kB",&kb)==1) break;
    fclose(f); return kb<=UINT64_MAX/1024 ? kb*1024 : 0;
}
static bool finite_logits(lie_sequence *s, float *row, size_t vocab, lie_error *e) {
    size_t n=0;
    if (lie_sequence_logits(s,row,vocab,&n,e)!=LIE_OK || n!=vocab) return false;
    for (size_t i=0;i<n;++i) if (!isfinite(row[i])) {
        snprintf(e->message,sizeof e->message,"nonfinite frontier logits"); return false;
    }
    return true;
}
static bool run_sample(lie_model *m, const char *prompt, const char *expected, unsigned max_output,
                       unsigned index, unsigned vocab, FILE *file, lie_error *error) {
    lie_sequence *s=NULL;
    int32_t input[CONTEXT], output[OUTPUT]; size_t count=0, n=0, bytes=0;
    char text[32768]={0}; unsigned position=0; bool stopped=false, ok=false;
    float *logits=malloc((size_t)vocab*sizeof *logits);
    if (!logits) return false;
    lie_chat_message message={LIE_CHAT_USER,prompt,strlen(prompt)};
    if (lie_model_chat_tokens(m,&message,1,input,CONTEXT,&n,error)!=LIE_OK ||
        !n || n+max_output>CONTEXT || lie_sequence_create(m,&s,error)!=LIE_OK) goto done;
    json_object *j=event("sample_begin"), *ids=json_object_new_array();
    num(j,"sample",index); num(j,"prompt_tokens",n); num(j,"output_limit",max_output);
    for (size_t i=0;i<n;++i) json_object_array_add(ids,json_object_new_int(input[i]));
    json_object_object_add(j,"physical_input_ids",ids);
    if (!emit(file,j)) goto done;
    uint64_t pp_begin=clock_ns();
    for (size_t at=0;at<n;) {
        at=n-at>2048 ? at+2048 : n;
        if (interrupted || lie_sequence_prefill(s,input,at,error)!=LIE_OK) goto done;
    }
    uint64_t pp_end=clock_ns(), tg_ns=0;
    if (!pp_begin || pp_end<=pp_begin || !finite_logits(s,logits,vocab,error)) goto done;
    position=(unsigned)n;
    for (unsigned i=0;i<max_output;++i) {
        lie_decode_result d={0}; uint64_t begin=clock_ns();
        if (interrupted || lie_sequence_decode(s,&d,error)!=LIE_OK) goto done;
        uint64_t end=clock_ns();
        if (!begin || end<=begin || end-begin>UINT64_MAX-tg_ns || d.emitted>1 || d.stop>1 ||
            (!d.emitted && !d.stop) || d.position!=position+d.emitted ||
            (d.emitted && (d.token<0 || (unsigned)d.token>=vocab))) goto done;
        tg_ns+=end-begin; position=d.position;
        /* Copies/finite checks and token rendering are OUTSIDE measured calls. */
        if (!finite_logits(s,logits,vocab,error)) goto done;
        if (d.emitted) {
            size_t written=0;
            if (lie_model_token_text(m,d.token,text+bytes,sizeof text-1-bytes,&written,error)!=LIE_OK ||
                written>sizeof text-1-bytes) goto done;
            bytes+=written; output[count++]=d.token;
        }
        stopped=d.stop!=0;
        if (stopped) break;
    }
    text[bytes]=0;
    j=event("sample"); ids=json_object_new_array();
    for (size_t i=0;i<count;++i) json_object_array_add(ids,json_object_new_int(output[i]));
    json_object_object_add(j,"output_ids",ids);
    /* Hex preserves even a truncated UTF-8 token sequence without invalid JSON. */
    char hex[sizeof text*2+1];
    for (size_t i=0;i<bytes;++i) snprintf(hex+2*i,3,"%02x",(unsigned char)text[i]);
    hex[2*bytes]=0;
    str(j,"output_utf8_hex",hex); num(j,"sample",index); num(j,"prompt_tokens",n);
    num(j,"decode_tokens",count); num(j,"final_position",position); num(j,"stop",stopped);
    num(j,"prefill_ns",pp_end-pp_begin); num(j,"decode_ns",tg_ns);
    json_object_object_add(j,"prefill_tok_s",json_object_new_double((double)n*1e9/(double)(pp_end-pp_begin)));
    json_object_object_add(j,"decode_tok_s",tg_ns ? json_object_new_double((double)count*1e9/(double)tg_ns) : NULL);
    json_object_object_add(j,"finite_frontiers",json_object_new_boolean(true));
    bool answer=!expected || (bytes==strlen(expected) && !memcmp(text,expected,bytes));
    json_object_object_add(j,"expected_answer_match",expected ? json_object_new_boolean(answer) : NULL);
    ok=emit(file,j) && answer && count>0;
    if (!answer) snprintf(error->message,sizeof error->message,"Q2 arithmetic smoke output mismatch");
    fprintf(stderr,"sample=%u pp=%zu tg=%zu output=%.*s\n",index,n,count,(int)bytes,text);
 done:
    if (s && lie_sequence_close(&s,error)!=LIE_OK) ok=false;
    free(logits); return ok;
}
int main(int argc,char **argv) {
    if (argc==2 && !strcmp(argv[1],"--build-info")) {
        puts("q2-model-first-test: experimental Gufo Q2; context=9216 chunk=2048 AR-only; NOT QUALIFIED"); return 0;
    }
    if (argc!=5 || strcmp(argv[1],"--model") || strcmp(argv[3],"--output")) {
        fputs("Usage: q2-model-first-test --model Q2-GGUF --output NEW-JSONL\n",stderr); return 2;
    }
    struct sigaction action={0}; action.sa_handler=stop; sigemptyset(&action.sa_mask);
    if (sigaction(SIGINT,&action,NULL) || sigaction(SIGTERM,&action,NULL)) return 1;
    int fd=open(argv[4],O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600);
    if (fd<0) { perror("exclusive output"); return 1; }
    FILE *f=fdopen(fd,"w"); if (!f) { close(fd); return 1; }
    lie_model *m=NULL; lie_error error={{0}}; int code=1, model_fd=-1;
    lie_q2_test_memory plan={0};
    json_object *j=event("identity"); str(j,"engine","gufo-q2-model-test-f783fedb");
    str(j,"build_id",LIE_BUILD_ID); str(j,"scope","first model smoke and cold samples; not matched benchmark or independent parity");
    num(j,"context",CONTEXT); num(j,"chunk",2048);
    if (!emit(f,j)) goto done;
    model_fd=open(argv[2],O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK);
    struct stat st;
    if (model_fd<0 || fstat(model_fd,&st) || !S_ISREG(st.st_mode)) goto done;
    /* Retain one descriptor: preflight and both readers reopen this same inode. */
    char path[80]; snprintf(path,sizeof path,"/proc/self/fd/%d",model_fd);
    uint64_t avail=available();
    bool admitted=lie_q2_model_admit(path,avail,&plan,error.message,sizeof error.message)!=0;
    j=event("memory_admission"); num(j,"available",avail); num(j,"ple_addressed",plan.ple_addressed);
    num(j,"weight_upper",plan.weight_upper); num(j,"allocation_limit",plan.allocation_limit);
    num(j,"host_allowance",plan.host_allowance); num(j,"system_reserve",plan.system_reserve);
    num(j,"required_available",plan.required_available);
    json_object_object_add(j,"admitted",json_object_new_boolean(admitted));
    if (!emit(f,j) || !admitted || interrupted) goto done;
    lie_model_options options={LIE_EXECUTOR_ABI,sizeof options,CONTEXT,2048}; lie_model_info info={0};
    uint64_t begin=clock_ns();
    if (lie_backend_open(path,&options,&m,&error)!=LIE_OK || interrupted ||
        lie_model_get_info(m,&info,&error)!=LIE_OK || !info.vocab_tokens || info.vocab_tokens>1048576) goto done;
    uint64_t end=clock_ns(); if (!begin || end<=begin) goto done;
    j=event("loaded"); num(j,"load_ns",end-begin); num(j,"reported_weight_bytes",info.weights_bytes);
    num(j,"reported_session_bytes",info.session_bytes); num(j,"reported_deferred_workspace_bytes",info.deferred_workspace_bytes);
    num(j,"hip_bytes_requested_cumulative",lie_q2_test_memory_charged());
    if (!emit(f,j)) goto done;
    if (!run_sample(m,"What is 2 + 2? Reply with only the digit, without punctuation or explanation.",
                    "4",16,0,info.vocab_tokens,f,&error)) goto done;
    /* Same deterministic reference-padding vocabulary as the historical C1
       harness. Physical token count is recorded; it is NOT claimed to be 512. */
    char prompt[4096]="Reference material follows. Ignore it for the counting task.\n";
    for (unsigned i=0;i<36;++i) strcat(prompt,"The quick brown fox jumps over the lazy dog.\n");
    strcat(prompt,"\nList the integers from 1 to 10000, one integer per line. Start immediately at 1 and continue. Do not add an introduction, summary or code fence.");
    if (!run_sample(m,prompt,NULL,128,1,info.vocab_tokens,f,&error)) goto done;
    code=0;
 done:
    if (m && lie_model_close(&m,&error)!=LIE_OK) code=1;
    if (model_fd>=0) close(model_fd);
    if (interrupted) code=1;
    j=event(code ? "failed" : "complete"); num(j,"exit_code",(unsigned)code);
    num(j,"hip_bytes_requested_cumulative",lie_q2_test_memory_charged());
    if (code) str(j,"error",interrupted ? "interrupted; no retry" : error.message[0] ? error.message : "first-test contract, allocation or I/O failure");
    if (!emit(f,j)) code=1;
    if (fclose(f)) code=1;
    return code;
}
