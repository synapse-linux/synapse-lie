/* SPDX-License-Identifier: MIT */
/* Synthetic transport/lifetime fixture. No weights, neural computation or GPU. */
#include "lie/executor.h"
#include "lie/state.h"
#include "lie/store.h"
#include "fake_executor.h"
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
struct lie_model { pthread_t owner; unsigned context, chunk, sequences, width; bool failed; uint64_t domain; };
struct lie_sequence { lie_model *model; unsigned position, step; int mode; int32_t *prompt; atomic_bool cancelled; };
static pthread_mutex_t gate=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t condition=PTHREAD_COND_INITIALIZER;
static bool held, entered;
static fake_phase held_phase;
static atomic_uint prefill_calls, decode_calls, text_calls, create_calls, close_calls, batch_calls, capture_calls, restore_calls, state_fault;
static atomic_uint_fast64_t domain_counter=1;
static atomic_uint state_padding;
static atomic_bool merge_tokenizer;
void fake_tokenizer_merge(bool enabled){atomic_store(&merge_tokenizer,enabled);}
void fake_state_padding(unsigned bytes){atomic_store(&state_padding,bytes);}
void fake_state_fault(unsigned value){atomic_store(&state_fault,value);}
static const char *tool_outputs[]={
    "Reading.\n<tool_call>\n<function=read>\n<parameter=path>\n  caffè 🙂.txt  \n</parameter>\n<parameter=offset>\n3\n</parameter>\n<parameter=options>\n{\"raw\":true}\n</parameter>\n</function>\n</tool_call>",
    "<tool_call>\n<function=read>\n<parameter=path>\nincomplete",
    "<tool_call>\n<function=unknown>\n</function>\n</tool_call>",
    "<tool_call>\n<function=read>\n<parameter=path>a</parameter>\n<parameter=path>b</parameter>\n</function>\n</tool_call>",
    "<tool_call>\n<function=read>\n<parameter=path>x</parameter>\n<parameter=offset>three</parameter>\n</function>\n</tool_call>",
    "Tool result received.",
    "<tool_call>\n<function=read>\n<parameter=path>\nlie-pi-fixture.txt\n</parameter>\n</function>\n</tool_call>",
    "CPU fixture tool result received."
};
enum { BAD_POSITION=20, BAD_EMITTED, BAD_STOP, NO_PROGRESS, BAD_EOS_POSITION,
       NEGATIVE_TOKEN, LARGE_TOKEN, DECODE_REFUSAL, PREFILL_REFUSAL, TEXT_REFUSAL, TEXT_SIZE };
void fake_barrier_arm_phase(fake_phase phase) {
    pthread_mutex_lock(&gate); held=true; entered=false; held_phase=phase; pthread_mutex_unlock(&gate);
}
void fake_barrier_arm(void) { fake_barrier_arm_phase(FAKE_DECODE); }
void fake_barrier_wait(void) { pthread_mutex_lock(&gate); while (!entered) pthread_cond_wait(&condition,&gate); pthread_mutex_unlock(&gate); }
void fake_barrier_release(void) { pthread_mutex_lock(&gate); held=false; pthread_cond_broadcast(&condition); pthread_mutex_unlock(&gate); }
void fake_calls_reset(void) {
    atomic_store(&capture_calls,0);atomic_store(&restore_calls,0);atomic_store(&state_fault,0);
    atomic_store(&prefill_calls,0); atomic_store(&decode_calls,0); atomic_store(&text_calls,0);
    atomic_store(&batch_calls,0); atomic_store(&create_calls,0); atomic_store(&close_calls,0);
}
fake_calls fake_calls_snapshot(void) {
    return (fake_calls){atomic_load(&prefill_calls),atomic_load(&decode_calls),atomic_load(&text_calls),
                       atomic_load(&create_calls),atomic_load(&close_calls),atomic_load(&batch_calls),atomic_load(&capture_calls),atomic_load(&restore_calls)};
}
static void barrier(fake_phase phase) {
    pthread_mutex_lock(&gate);
    if (held && held_phase==phase) { entered=true; pthread_cond_broadcast(&condition); while (held) pthread_cond_wait(&condition,&gate); }
    pthread_mutex_unlock(&gate);
    if (phase==FAKE_DECODE) { struct timespec delay={0,1000000}; nanosleep(&delay,NULL); }
}
static void owner(lie_model *m) { assert(m && pthread_equal(m->owner,pthread_self())); }
static lie_status error(lie_error *e, lie_status code, const char *message) {
    if (e) snprintf(e->message,sizeof(e->message),"%s",message);
    return code;
}
const char *lie_backend_name(void) { return "cpu-test-fixture-NOT-INFERENCE"; }
const char *lie_backend_ownership(void) { return "synthetic-test-fixture"; }
const char *lie_backend_source_pin(void) { return "synthetic"; }
lie_status lie_backend_open(const char *p, const lie_model_options *o, lie_model **m, lie_error *e) { return lie_gufo_open(p,o,m,e); }
int lie_backend_is_synthetic(void) { return 1; }
lie_status lie_model_state_identity(lie_model *m,lie_state_identity *id,uint64_t *domain,lie_error *e){
    (void)e;owner(m);memset(id,0,sizeof(*id));
    memcpy(id->bytes,"NOT-INFERENCE-state-v1",22);
    unsigned values[]={1,m->chunk,m->width};
    for(unsigned i=0;i<3;++i)for(unsigned k=0;k<3;++k)id->bytes[22+i*3+k]=(unsigned char)(values[i]>>(8*k));
    *domain=m->domain;return LIE_OK;
}
lie_status lie_gufo_open(const char *path, const lie_model_options *o, lie_model **out, lie_error *e) {
    if (strcmp(path,":fixture:") || o->abi_version!=LIE_EXECUTOR_ABI) return error(e,LIE_INVALID,"fixture_path_required");
    lie_model *m=calloc(1,sizeof(*m)); assert(m);
    m->domain=atomic_fetch_add(&domain_counter,1);m->owner=pthread_self(); m->width=1; m->context=o->context_tokens; m->chunk=o->prefill_chunk_tokens; *out=m; return LIE_OK;
}
lie_status lie_model_get_info(lie_model *m, lie_model_info *out, lie_error *e) {
    (void)e; owner(m); *out=(lie_model_info){.abi_version=LIE_EXECUTOR_ABI,.context_tokens=m->context,.vocab_tokens=2048,.prefill_capacity=m->chunk,.native_batch_capacity=m->width}; return LIE_OK;
}
lie_status lie_model_close(lie_model **m, lie_error *e) { (void)e; owner(*m); assert(!(*m)->sequences); free(*m); *m=NULL; return LIE_OK; }
lie_status lie_model_chat_tokens(lie_model *m, const lie_chat_message *messages, size_t count, int32_t *out, size_t capacity, size_t *required, lie_error *e) {
    owner(m); assert(count && !m->failed);
    const char *text=messages[count-1].content;
    int mode=!strcmp(text,"FAULT")?2:!strcmp(text,"LONG-A")?3:!strcmp(text,"LONG-B")?4:
             !strcmp(text,"CONTROL")?10:!strcmp(text,"EMPTY")?6:!strcmp(text,"PREFILL-FAULT")?7:!strcmp(text,"SLOW-PREFILL")?8:
             !strcmp(text,"SLOW-DECODE")?9:!strcmp(text,"LONG")?1:0;
    const char *faults[]={"BAD-POSITION","BAD-EMITTED","BAD-STOP","NO-PROGRESS","BAD-EOS-POSITION",
        "NEGATIVE-TOKEN","LARGE-TOKEN","DECODE-REFUSAL","PREFILL-REFUSAL","TEXT-REFUSAL","TEXT-SIZE"};
    for (unsigned i=0;i<sizeof(faults)/sizeof(*faults);++i) if (!strcmp(text,faults[i])) mode=BAD_POSITION+(int)i;
    const char *tool_modes[]={"TOOL","TOOL-TRUNCATED","TOOL-UNKNOWN","TOOL-DUPLICATE","TOOL-JSON-BAD","TOOL-RESULT","PI-SYNTHETIC-READ"};
    for (size_t i=0;i<sizeof(tool_modes)/sizeof(*tool_modes);++i) if (!strcmp(text,tool_modes[i])) mode=100+(int)i;
    *required=!strcmp(text,"OVERSIZED")?(size_t)m->context+1:4;
    /* Synthetic physical-token count for HTTP admission/chunk boundaries.
     * This does not tokenize text or perform model computation. */
    if (!strncmp(text,"FIXTURE-TOKENS:",15)) {
        char *end=NULL; unsigned long n=strtoul(text+15,&end,10);
        assert(end && *end=='\n' && n>=4 && n<=(unsigned long)m->context+1);
        *required=(size_t)n;
    }
    if (*required>capacity) return error(e,LIE_BUFFER_SMALL,"fixture_context_bound");
    out[0]=mode; for (size_t i=1;i<*required;++i) out[i]=10; return LIE_OK;
}
lie_status lie_model_chat_tokens_ex(lie_model *m, const lie_chat_template *t, int32_t *out, size_t cap, size_t *needed, lie_error *e) {
    owner(m); assert(t && t->count && t->count<=LIE_CHAT_MAX_MESSAGES && t->tool_count<=LIE_CHAT_MAX_TOOLS);
    if (t->messages[t->count-1].role==LIE_CHAT_TOOL) {
        assert(t->details && t->details[t->count-1].tool_call_id && t->count>=3);
        assert(t->details[t->count-2].call_count==1);
        assert(!strcmp(t->details[t->count-2].calls[0].id,t->details[t->count-1].tool_call_id));
        const char *path=t->details[t->count-2].calls[0].arguments[0].value;
        if (!strcmp(path,"lie-pi-fixture.txt")) {
            assert(strstr(t->messages[t->count-1].content,"LIE-PI-FIXTURE-CONTENT"));
            *needed=4; if (cap<4) return LIE_BUFFER_SMALL;
            out[0]=107; out[1]=out[2]=out[3]=10; return LIE_OK;
        }
        assert(!strcmp(path,"  caffè 🙂.txt  "));
    }
    return lie_model_chat_tokens(m,t->messages,t->count,out,cap,needed,e);
}
lie_status lie_model_tokenize(lie_model *m, const char *s, size_t n, int32_t *out, size_t cap, size_t *needed, lie_error *e) {
    owner(m);bool merged=atomic_load(&merge_tokenizer)&&n>=5&&s[0]=='a'&&s[1]=='b';
    *needed=n-(merged?1:0);if(*needed>cap)return error(e,LIE_BUFFER_SMALL,"fixture_byte_bound");
    if(merged)out[0]=500;
    for(size_t i=merged?2:0;i<n;++i)out[i-(merged?1:0)]=128+(unsigned char)s[i];
    return LIE_OK;
}
lie_status lie_model_token_text(lie_model *m, int32_t token, char *out, size_t capacity, size_t *required, lie_error *e) {
    owner(m); assert(!m->failed); atomic_fetch_add(&text_calls,1);
    if (token==1010 || token==1011) {
        *required=capacity+1;
        if (token==1010) { out[0]='X'; return LIE_OK; } /* Invalid claimed size, not an actual overrun. */
        return error(e,LIE_BUFFER_SMALL,"synthetic_text_refusal");
    }
    if (token>=128 && token<384) {
        *required=1; if (!capacity) return error(e,LIE_BUFFER_SMALL,"fixture_byte_bound");
        out[0]=(char)(token-128); return LIE_OK;
    }
    const char *pieces[]={"fixture:"," ","\xf0","\x9f\x99","\x82","\"\\\n","\xff","\xe2"};
    if (token>=1000) {
        *required=256; if (capacity<256) return error(e,LIE_BUFFER_SMALL,"fixture_piece_bound");
        memset(out,token==1003?1:token==1001?'A':token==1002?'B':'Z',256); return LIE_OK;
    }
    if(token==500&&atomic_load(&merge_tokenizer)){*required=2;if(capacity<2)return LIE_BUFFER_SMALL;memcpy(out,"ab",2);return LIE_OK;}
    if(token>=8&&token<1000){*required=1;if(!capacity)return LIE_BUFFER_SMALL;out[0]='x';return LIE_OK;}
    assert(token>=0 && token<8); *required=strlen(pieces[token]);
    if (*required>capacity) return error(e,LIE_BUFFER_SMALL,"fixture_piece_bound");
    memcpy(out,pieces[token],*required); return LIE_OK;
}
lie_status lie_sequence_create(lie_model *m, lie_sequence **out, lie_error *e) {
    (void)e; owner(m); assert(!m->failed); atomic_fetch_add(&create_calls,1);
    lie_sequence *s=calloc(1,sizeof(*s)); assert(s);
    s->prompt=calloc(m->context,sizeof(*s->prompt));assert(s->prompt);s->model=m; atomic_init(&s->cancelled,false); ++m->sequences; *out=s; return LIE_OK;
}
lie_status lie_sequence_close(lie_sequence **s, lie_error *e) {
    (void)e; owner((*s)->model); atomic_fetch_add(&close_calls,1);
    --(*s)->model->sequences; free((*s)->prompt);free(*s); *s=NULL; return LIE_OK;
}
lie_status lie_sequence_prefill(lie_sequence *s, const int32_t *tokens, size_t count, lie_error *e) {
    owner(s->model); assert(!s->model->failed && count>s->position && count-s->position<=s->model->chunk);
    atomic_fetch_add(&prefill_calls,1); barrier(FAKE_PREFILL);
    if (atomic_load(&s->cancelled)) return LIE_CANCELLED;
    s->mode=tokens[0];
    if (s->mode==8) { struct timespec t={0,500000000}; nanosleep(&t,NULL); }
    if (atomic_load(&s->cancelled)) return LIE_CANCELLED;
    if (s->mode==PREFILL_REFUSAL) return error(e,LIE_INVALID,"synthetic_prefill_refusal");
    if (s->mode==7 && count>2) { s->model->failed=true; return error(e,LIE_BACKEND_FAILED,"synthetic_prefill_failure"); }
    memcpy(s->prompt,tokens,count*sizeof(*tokens));s->position=(unsigned)count; return LIE_OK;
}
lie_status lie_sequence_decode(lie_sequence *s, lie_decode_result *out, lie_error *e) {
    owner(s->model); assert(!s->model->failed); atomic_fetch_add(&decode_calls,1); barrier(FAKE_DECODE);
    if (s->mode==9) { struct timespec t={0,50000000}; nanosleep(&t,NULL); }
    if (s->mode==DECODE_REFUSAL) return error(e,LIE_INVALID,"synthetic_decode_refusal");
    if (s->mode==2) { s->model->failed=true; return error(e,LIE_BACKEND_FAILED,"synthetic_mutating_failure"); }
    if (atomic_load(&s->cancelled)) return LIE_CANCELLED;
    if (s->mode>=100 && s->mode<=107) {
        const char *text=tool_outputs[s->mode-100];
        bool done=s->step==strlen(text);
        *out=(lie_decode_result){.stop=done,.position=s->position};
        if (!done) { out->token=128+(unsigned char)text[s->step++];s->prompt[s->position]=out->token;out->emitted=1;out->position=++s->position; }
        return LIE_OK;
    }
    bool done=s->mode==6 || (s->mode==0 && s->step==8);
    *out=(lie_decode_result){.stop=done,.position=s->position};
    if (!done) {
        out->token=s->mode==0?(int)s->step:s->mode==3?1001:s->mode==4?1002:s->mode==10?1003:1000;
        out->emitted=1; out->position=++s->position; ++s->step;
    }
    switch (s->mode) {
        case BAD_POSITION: ++out->position; break;
        case BAD_EMITTED: out->emitted=2; ++out->position; break;
        case BAD_STOP: out->stop=2; break;
        case NO_PROGRESS: out->emitted=out->stop=0; --out->position; break;
        case BAD_EOS_POSITION: out->emitted=0; out->stop=1; break;
        case NEGATIVE_TOKEN: out->token=-1; break;
        case LARGE_TOKEN: out->token=2048; break;
        case TEXT_REFUSAL: out->token=1011; break;
        case TEXT_SIZE: out->token=1010; break;
    }
    if(out->emitted==1&&out->position<=s->model->context)s->prompt[out->position-1]=out->token;
    return LIE_OK;
}
lie_status lie_sequence_logits(lie_sequence *s, float *out, size_t capacity, size_t *required, lie_error *e) {
    (void)out; (void)capacity; (void)required; owner(s->model); return error(e,LIE_UNSUPPORTED,"fixture_has_no_logits");
}
void lie_sequence_cancel(lie_sequence *s) { atomic_store(&s->cancelled,true); }

lie_status lie_sequence_configure(lie_sequence *s,const lie_generation_options *o,lie_error *e) {
    (void)e; owner(s->model); assert(!s->position);
    /* Internal synthetic submissions historically use an all-zero request. */
    assert(!o->abi_version || (o->abi_version==LIE_GENERATION_ABI && o->struct_bytes==sizeof(*o)));
    return LIE_OK;
}

lie_status lie_backend_open_batch(const char *p,const lie_model_options *o,uint32_t w,lie_model **m,lie_error *e) {
    if(!w||w>LIE_DECODE_MAX_ROWS)return LIE_INVALID;
    lie_status rc=lie_backend_open(p,o,m,e);if(rc==LIE_OK)(*m)->width=w;return rc;
}
lie_status lie_sequences_decode(lie_sequence *const *s,size_t n,lie_decode_outcome *o,lie_error *e) {
    assert(n>1&&n<=s[0]->model->width);atomic_fetch_add(&batch_calls,1);
    for(size_t i=0;i<n;++i){o[i].result=(lie_decode_result){0};o[i].status=lie_sequence_decode(s[i],&o[i].result,e);
        if(o[i].status!=LIE_OK&&o[i].status!=LIE_CANCELLED){for(size_t j=0;j<n;++j)o[j]=(lie_decode_outcome){.status=LIE_BACKEND_FAILED};return LIE_BACKEND_FAILED;}}
    return LIE_OK;
}

int lie_backend_prefix_state_supported(void){return 1;}
const char *lie_backend_state_format(void){
#ifdef LIE_TEST_KVC_STATE
    return "synthetic-kvc-payload";
#else
    return "synthetic-aligned-components";
#endif
}
lie_status lie_sequence_state_describe(lie_sequence *s,const lie_state_layout *from,lie_state_layout *out,lie_error *e){
    owner(s->model);if(atomic_load(&s->cancelled))return LIE_CANCELLED;
    if((from?(s->position||from->domain!=s->model->domain||from->context_tokens>s->model->context):!s->position))return error(e,LIE_INVALID,"fixture state domain/frontier");
    *out=(lie_state_layout){.abi_version=LIE_STATE_ABI,.representation_version=1,.domain=s->model->domain,
        .token_count=from?from->token_count:s->position,.context_tokens=from?from->context_tokens:s->model->context,.prefill_chunk=s->model->chunk};
#ifdef LIE_TEST_KVC_STATE
    /* Deliberately synthetic family; exercises the shared core/store without
     * Qwen geometry, numerical computation or model inference claims. */
    out->format=LIE_STATE_KVC;out->model_id=250;out->quant_bits=8;
#endif
    uint64_t shape=out->token_count;assert(lie_state_add(out,LIE_STATE_TOKENS,0,LIE_STATE_I32,1,&shape));
    shape=4;assert(lie_state_add(out,LIE_STATE_LOGITS,0,LIE_STATE_F32,1,&shape));
    shape=2;assert(lie_state_add(out,LIE_STATE_RECURRENT,0,LIE_STATE_I32,1,&shape));
    shape=atomic_load(&state_padding);if(shape)assert(lie_state_add(out,LIE_STATE_MODEL_COMPONENT,0,LIE_STATE_U8,1,&shape));
    if(atomic_load(&state_fault)==1)out->sections[0].bytes++;
    return LIE_OK;
}
lie_status lie_sequence_state_read(lie_sequence *s,const lie_state_layout *l,void *bytes,size_t n,lie_error *e){
    owner(s->model);uint64_t expected;assert(lie_state_validate(l,&expected)&&n==expected);
    atomic_fetch_add(&capture_calls,1);barrier(FAKE_CAPTURE);if(atomic_load(&s->cancelled))return LIE_CANCELLED;
    if(atomic_load(&state_fault)==2){s->model->failed=true;return error(e,LIE_BACKEND_FAILED,"synthetic state read fault");}
    memcpy((char*)bytes+l->sections[0].offset,s->prompt,l->sections[0].bytes);
    const float logits[]={1,2,3,4};memcpy((char*)bytes+l->sections[1].offset,logits,sizeof(logits));
    const int32_t recurrent[]={s->mode,(int32_t)s->step};memcpy((char*)bytes+l->sections[2].offset,recurrent,sizeof(recurrent));
    if(l->section_count==4)memset((char*)bytes+l->sections[3].offset,0x5a,(size_t)l->sections[3].bytes);
    return LIE_OK;
}
lie_status lie_sequence_state_write(lie_sequence *s,const lie_state_layout *l,const void *bytes,size_t n,lie_error *e){
    owner(s->model);uint64_t expected;assert(lie_state_validate(l,&expected)&&n==expected&&!s->position);
    atomic_fetch_add(&restore_calls,1);barrier(FAKE_RESTORE);if(atomic_load(&s->cancelled))return LIE_CANCELLED;
    s->position=l->token_count;
    if(atomic_load(&state_fault)==3){s->model->failed=true;return error(e,LIE_BACKEND_FAILED,"synthetic mutating state write fault");}
    memcpy(s->prompt,(const char*)bytes+l->sections[0].offset,l->sections[0].bytes);
    int32_t recurrent[2];memcpy(recurrent,(const char*)bytes+l->sections[2].offset,sizeof(recurrent));
    if(l->section_count==4)for(uint64_t i=0;i<l->sections[3].bytes;++i)assert(((const unsigned char *)bytes)[l->sections[3].offset+i]==0x5a);
    s->mode=recurrent[0];s->step=(unsigned)recurrent[1];return LIE_OK;
}

lie_status lie_model_chat_anchor(lie_model *m,const int32_t *t,size_t n,size_t *out,lie_error *e){
    (void)m;(void)t;(void)n;(void)e;*out=0;return LIE_OK;
}
