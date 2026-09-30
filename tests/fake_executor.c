/* SPDX-License-Identifier: MIT */
/* Synthetic transport/lifetime fixture. No weights, neural computation or GPU. */
#include "lie/executor.h"
#include "fake_executor.h"
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
struct lie_model { pthread_t owner; unsigned context, chunk, sequences; bool failed; };
struct lie_sequence { lie_model *model; unsigned position, step; int mode; atomic_bool cancelled; };
static pthread_mutex_t gate=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t condition=PTHREAD_COND_INITIALIZER;
static bool held, entered;
void fake_barrier_arm(void) { pthread_mutex_lock(&gate); held=true; entered=false; pthread_mutex_unlock(&gate); }
void fake_barrier_wait(void) { pthread_mutex_lock(&gate); while (!entered) pthread_cond_wait(&condition,&gate); pthread_mutex_unlock(&gate); }
void fake_barrier_release(void) { pthread_mutex_lock(&gate); held=false; pthread_cond_broadcast(&condition); pthread_mutex_unlock(&gate); }
static void barrier(void) {
    pthread_mutex_lock(&gate);
    if (held) { entered=true; pthread_cond_broadcast(&condition); while (held) pthread_cond_wait(&condition,&gate); }
    pthread_mutex_unlock(&gate);
    struct timespec delay={0,1000000}; nanosleep(&delay,NULL);
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
lie_status lie_gufo_open(const char *path, const lie_model_options *o, lie_model **out, lie_error *e) {
    if (strcmp(path,":fixture:") || o->abi_version!=LIE_EXECUTOR_ABI) return error(e,LIE_INVALID,"fixture_path_required");
    lie_model *m=calloc(1,sizeof(*m)); assert(m);
    m->owner=pthread_self(); m->context=o->context_tokens; m->chunk=o->prefill_chunk_tokens; *out=m; return LIE_OK;
}
lie_status lie_model_get_info(lie_model *m, lie_model_info *out, lie_error *e) {
    (void)e; owner(m); *out=(lie_model_info){.abi_version=LIE_EXECUTOR_ABI,.context_tokens=m->context,.vocab_tokens=2048,.prefill_capacity=m->chunk,.native_batch_capacity=1}; return LIE_OK;
}
lie_status lie_model_close(lie_model **m, lie_error *e) { (void)e; owner(*m); assert(!(*m)->sequences); free(*m); *m=NULL; return LIE_OK; }
lie_status lie_model_chat_tokens(lie_model *m, const lie_chat_message *messages, size_t count, int32_t *out, size_t capacity, size_t *required, lie_error *e) {
    owner(m); assert(count && !m->failed);
    const char *text=messages[count-1].content;
    int mode=!strcmp(text,"FAULT")?2:!strcmp(text,"LONG-A")?3:!strcmp(text,"LONG-B")?4:
             !strcmp(text,"EMPTY")?6:!strcmp(text,"LONG")?1:0;
    *required=!strcmp(text,"OVERSIZED")?(size_t)m->context+1:4;
    if (*required>capacity) return error(e,LIE_BUFFER_SMALL,"fixture_context_bound");
    out[0]=mode; out[1]=out[2]=out[3]=10; return LIE_OK;
}
lie_status lie_model_tokenize(lie_model *m, const char *s, size_t n, int32_t *out, size_t cap, size_t *needed, lie_error *e) {
    (void)s; (void)n; (void)out; (void)cap; (void)needed; owner(m); return error(e,LIE_UNSUPPORTED,"fixture_has_no_tokenizer");
}
lie_status lie_model_token_text(lie_model *m, int32_t token, char *out, size_t capacity, size_t *required, lie_error *e) {
    owner(m); assert(!m->failed);
    const char *pieces[]={"fixture:"," ","\xf0","\x9f\x99","\x82","\"\\\n","\xff","\xe2"};
    if (token>=1000) {
        *required=256; if (capacity<256) return error(e,LIE_BUFFER_SMALL,"fixture_piece_bound");
        memset(out,token==1001?'A':token==1002?'B':'Z',256); return LIE_OK;
    }
    assert(token>=0 && token<8); *required=strlen(pieces[token]);
    if (*required>capacity) return error(e,LIE_BUFFER_SMALL,"fixture_piece_bound");
    memcpy(out,pieces[token],*required); return LIE_OK;
}
lie_status lie_sequence_create(lie_model *m, lie_sequence **out, lie_error *e) {
    (void)e; owner(m); assert(!m->failed); lie_sequence *s=calloc(1,sizeof(*s)); assert(s);
    s->model=m; atomic_init(&s->cancelled,false); ++m->sequences; *out=s; return LIE_OK;
}
lie_status lie_sequence_close(lie_sequence **s, lie_error *e) {
    (void)e; owner((*s)->model); --(*s)->model->sequences; free(*s); *s=NULL; return LIE_OK;
}
lie_status lie_sequence_prefill(lie_sequence *s, const int32_t *tokens, size_t count, lie_error *e) {
    (void)e; owner(s->model); assert(!s->model->failed && count>s->position && count-s->position<=s->model->chunk);
    s->mode=tokens[0]; s->position=(unsigned)count; return LIE_OK;
}
lie_status lie_sequence_decode(lie_sequence *s, lie_decode_result *out, lie_error *e) {
    owner(s->model); assert(!s->model->failed); barrier();
    if (s->mode==2) { s->model->failed=true; return error(e,LIE_BACKEND_FAILED,"synthetic_mutating_failure"); }
    if (atomic_load(&s->cancelled)) return LIE_CANCELLED;
    bool done=s->mode==6 || (s->mode==0 && s->step==8);
    *out=(lie_decode_result){.stop=done,.position=s->position};
    if (!done) {
        out->token=s->mode==0?(int)s->step:s->mode==3?1001:s->mode==4?1002:1000;
        out->emitted=1; out->position=++s->position; ++s->step;
    }
    return LIE_OK;
}
lie_status lie_sequence_logits(lie_sequence *s, float *out, size_t capacity, size_t *required, lie_error *e) {
    (void)out; (void)capacity; (void)required; owner(s->model); return error(e,LIE_UNSUPPORTED,"fixture_has_no_logits");
}
void lie_sequence_cancel(lie_sequence *s) { atomic_store(&s->cancelled,true); }
