/* SPDX-License-Identifier: MIT */
/* Deterministic ABI fixture for benchmark accounting, never neural computation. */
#include "lie/executor.h"
#include <math.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
struct lie_model { unsigned context,runs,width; int mode; };
struct lie_sequence { lie_model *m; unsigned position,step; atomic_bool cancelled; };
const char *lie_backend_name(void) { return "bench-fixture-NOT-INFERENCE"; }
const char *lie_backend_ownership(void) { return "synthetic-test-fixture"; }
const char *lie_backend_source_pin(void) { return "synthetic"; }
int lie_backend_is_synthetic(void) { return 1; }
lie_status lie_backend_open(const char *p,const lie_model_options *o,lie_model **m,lie_error *e) {
    (void)e; *m=calloc(1,sizeof(**m)); if (!*m) return LIE_BACKEND_FAILED;
    (*m)->context=o->context_tokens;(*m)->width=1;
    const char *names[]={":fixture:",":eos:",":nan:",":drift:",":failure:",":frontier:",":render-bound:"};
    for (int i=0;i<7;++i) if (!strcmp(p,names[i])) { (*m)->mode=i; return LIE_OK; }
    free(*m); *m=NULL; return LIE_INVALID;
}
lie_status lie_model_close(lie_model **m,lie_error *e) { (void)e; free(*m); *m=NULL; return LIE_OK; }
lie_status lie_model_get_info(lie_model *m,lie_model_info *i,lie_error *e) {
    (void)e; *i=(lie_model_info){.abi_version=LIE_EXECUTOR_ABI,.context_tokens=m->context,.vocab_tokens=256,.prefill_capacity=2048,.native_batch_capacity=m->width}; return LIE_OK;
}
lie_status lie_model_chat_tokens(lie_model *m,const lie_chat_message *msg,size_t count,int32_t *p,size_t cap,size_t *n,lie_error *e) {
    (void)count;
    if (m->mode==6 && m->context<=8192 && msg[0].bytes>1024u*1024u-512u) {
        snprintf(e->message,sizeof(e->message),"synthetic rendering safety bound");return LIE_INVALID;
    }
    *n=msg[0].bytes/4+1;
    if (*n>cap) return LIE_BUFFER_SMALL;
    for (size_t i=0;i<*n;++i) p[i]=(int32_t)(i%256);
    return LIE_OK;
}
lie_status lie_sequence_create(lie_model *m,lie_sequence **s,lie_error *e) {
    (void)e; *s=calloc(1,sizeof(**s)); if (!*s) return LIE_BACKEND_FAILED;
    (*s)->m=m;atomic_init(&(*s)->cancelled,0); ++m->runs; return LIE_OK;
}
lie_status lie_sequence_close(lie_sequence **s,lie_error *e) { (void)e; free(*s); *s=NULL; return LIE_OK; }
lie_status lie_sequence_prefill(lie_sequence *s,const int32_t *p,size_t n,lie_error *e) {
    (void)e; (void)p;
    if (atomic_load(&s->cancelled)) return LIE_CANCELLED;
    if (n<=s->position || n-s->position>2048 || n>s->m->context) return LIE_INVALID;
    s->position=(unsigned)n; return LIE_OK;
}
lie_status lie_sequence_decode(lie_sequence *s,lie_decode_result *d,lie_error *e) {
    if (atomic_load(&s->cancelled)) return LIE_CANCELLED;
    if (s->m->mode==4) { snprintf(e->message,sizeof(e->message),"synthetic mutating failure; no retry"); return LIE_BACKEND_FAILED; }
    if (s->m->mode==1 && s->step==7) { *d=(lie_decode_result){.token=-1,.stop=1,.position=s->position}; return LIE_OK; }
    *d=(lie_decode_result){.token=(int32_t)(s->step%256),.emitted=1,.position=++s->position}; ++s->step;
    if (s->m->mode==5) ++d->position;
    return LIE_OK;
}
lie_status lie_sequence_logits(lie_sequence *s,float *p,size_t cap,size_t *n,lie_error *e) {
    (void)e; *n=256; if (cap<*n) return LIE_BUFFER_SMALL;
    for (size_t i=0;i<*n;++i) p[i]=(float)(s->position%256)+(float)i/256.0f;
    if (s->m->mode==2) p[17]=NAN;
    if (s->m->mode==3 && s->m->runs>3) p[23]+=1.0f;
    return LIE_OK;
}

lie_status lie_backend_open_batch(const char *p,const lie_model_options *o,uint32_t w,lie_model **m,lie_error *e) {
    if(!w||w>LIE_DECODE_MAX_ROWS)return LIE_INVALID;
    lie_status rc=lie_backend_open(p,o,m,e);if(rc==LIE_OK)(*m)->width=w;return rc;
}
lie_status lie_model_chat_tokens_ex(lie_model *m,const lie_chat_template *t,int32_t *p,size_t cap,size_t *n,lie_error *e) {
    return lie_model_chat_tokens(m,t->messages,t->count,p,cap,n,e);
}
lie_status lie_model_tokenize(lie_model *m,const char *s,size_t bytes,int32_t *p,size_t cap,size_t *n,lie_error *e) {
    lie_chat_message message={LIE_CHAT_USER,s,bytes};return lie_model_chat_tokens(m,&message,1,p,cap,n,e);
}
lie_status lie_model_token_text(lie_model *m,int32_t token,char *out,size_t cap,size_t *n,lie_error *e) {
    (void)m;(void)e;*n=1;if(cap<1)return LIE_BUFFER_SMALL;out[0]=(char)('a'+token%26);return LIE_OK;
}
lie_status lie_sequence_configure(lie_sequence *s,const lie_generation_options *o,lie_error *e) {
    (void)s;(void)e;return o->abi_version==LIE_GENERATION_ABI?LIE_OK:LIE_INVALID;
}
void lie_sequence_cancel(lie_sequence *s) { atomic_store(&s->cancelled,1); }
lie_status lie_sequences_decode(lie_sequence *const *s,size_t n,lie_decode_outcome *o,lie_error *e) {
    for(size_t i=0;i<n;++i){o[i].status=lie_sequence_decode(s[i],&o[i].result,e);if(o[i].status!=LIE_OK)return o[i].status;}return LIE_OK;
}
