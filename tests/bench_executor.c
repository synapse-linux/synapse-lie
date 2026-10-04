/* SPDX-License-Identifier: MIT */
/* Deterministic ABI fixture for benchmark accounting, never neural computation. */
#include "lie/executor.h"
#include "lie/mtp.h"
#include "lie/vision.h"
#include "lie/state.h"
#include "lie/store.h"
#include <math.h>
#include <errno.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
struct lie_model { unsigned context,runs,width,chunk; uint64_t domain; uint32_t drafts; int mode; bool mtp; unsigned vision; };
struct lie_sequence { lie_model *m; unsigned position,step; int32_t *prompt; unsigned char scope[32]; atomic_bool cancelled; };
static atomic_uint_fast64_t domain_counter=1;
const char *lie_backend_name(void) { return "bench-fixture-NOT-INFERENCE"; }
const char *lie_backend_ownership(void) { return "synthetic-test-fixture"; }
const char *lie_backend_dense_sampling(void) { return "synthetic-test-fixture"; }
const char *lie_backend_source_pin(void) { return "synthetic"; }
int lie_backend_is_synthetic(void) { return 1; }
lie_status lie_model_state_identity(lie_model *m,lie_state_identity *id,uint64_t *domain,lie_error *e){
    (void)e;memset(id,0,sizeof(*id));memcpy(id->bytes,"BENCH-SSD-v1",12);
    if(m->mtp){memcpy(id->bytes,"BENCH-MTP-v1",12);id->bytes[12]=(unsigned char)m->drafts;}
    unsigned values[]={m->context,m->chunk,m->width,(unsigned)m->mode};
    for(unsigned i=0;i<4;++i)for(unsigned k=0;k<4;++k)id->bytes[16+i*4+k]=(unsigned char)(values[i]>>(8*k));
    id->bytes[13]=(unsigned char)m->vision;*domain=m->domain;return LIE_OK;
}
lie_status lie_backend_open(const char *p,const lie_model_options *o,lie_model **m,lie_error *e) {
    if(!strcmp(p,":load-failure:")){snprintf(e->message,sizeof(e->message),"synthetic model allocation failure");return LIE_BACKEND_FAILED;}
    (void)e; *m=calloc(1,sizeof(**m)); if (!*m) return LIE_BACKEND_FAILED;
    (*m)->context=o->context_tokens;(*m)->width=1;(*m)->chunk=o->prefill_chunk_tokens;(*m)->domain=atomic_fetch_add(&domain_counter,1);
    const char *names[]={":fixture:",":eos:",":nan:",":drift:",":failure:",":frontier:",":render-bound:",":sampling:",":progress-fixture:",":progress-failure:",":progress-timeout:"};
    for (unsigned i=0;i<sizeof(names)/sizeof(*names);++i) if (!strcmp(p,names[i])) { (*m)->mode=(int)i; return LIE_OK; }
    free(*m); *m=NULL; return LIE_INVALID;
}
lie_status lie_model_close(lie_model **m,lie_error *e) { (void)e; free(*m); *m=NULL; return LIE_OK; }
lie_status lie_model_get_info(lie_model *m,lie_model_info *i,lie_error *e) {
    (void)e; *i=(lie_model_info){.abi_version=LIE_EXECUTOR_ABI,.context_tokens=m->context,.vocab_tokens=256,.prefill_capacity=2048,.native_batch_capacity=m->width,.speculative_supported=m->mtp}; return LIE_OK;
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
    (*s)->prompt=calloc(m->context,sizeof(int32_t));if(!(*s)->prompt){free(*s);*s=NULL;return LIE_BACKEND_FAILED;}
    (*s)->m=m;atomic_init(&(*s)->cancelled,0); ++m->runs; return LIE_OK;
}
lie_status lie_sequence_close(lie_sequence **s,lie_error *e) { (void)e; free((*s)->prompt);free(*s); *s=NULL; return LIE_OK; }
lie_status lie_sequence_prefill(lie_sequence *s,const int32_t *p,size_t n,lie_error *e) {
    (void)e; (void)p;
    if (atomic_load(&s->cancelled)) return LIE_CANCELLED;
    if (n<=s->position || n-s->position>2048 || n>s->m->context) return LIE_INVALID;
    if(s->m->mode>=8){
        struct timespec delay={s->m->mode==10?1:0,s->m->mode==10?0:s->position?50000000:300000000};
        while(nanosleep(&delay,&delay)&&errno==EINTR){}
        if(s->m->mode==9&&s->position>=4){snprintf(e->message,sizeof(e->message),"synthetic prefill failure after four completed tokens");return LIE_BACKEND_FAILED;}
    }
    memcpy(s->prompt,p,n*sizeof(*p));s->position=(unsigned)n; return LIE_OK;
}
lie_status lie_sequence_decode(lie_sequence *s,lie_decode_result *d,lie_error *e) {
    if (atomic_load(&s->cancelled)) return LIE_CANCELLED;
    if (s->m->mode==4) { snprintf(e->message,sizeof(e->message),"synthetic mutating failure; no retry"); return LIE_BACKEND_FAILED; }
    if(s->m->mode>=8){struct timespec delay={0,10000000};while(nanosleep(&delay,&delay)&&errno==EINTR){}}
    if (s->m->mode==1 && s->step==7) { *d=(lie_decode_result){.token=-1,.stop=1,.position=s->position}; return LIE_OK; }
    *d=(lie_decode_result){.token=(int32_t)(s->step%256),.emitted=1,.position=++s->position}; ++s->step;
    s->prompt[s->position-1]=d->token;
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
    (void)e;
    if (s->m->mode==7 && (o->temperature!=.75 || o->top_p!=.9 ||
        o->top_k!=5 || o->min_p!=.05 ||
        o->frequency_penalty!=.25 || o->presence_penalty!=-.5 || o->seed!=INT64_MAX))
        return LIE_INVALID;
    return o->abi_version==LIE_GENERATION_ABI?LIE_OK:LIE_INVALID;
}
lie_status lie_sequence_constrain(lie_sequence *s,
                                  const lie_generation_constraints *o,
                                  lie_error *e) {
  (void)s;
  (void)o;
  (void)e;
  return LIE_UNSUPPORTED;
}
lie_status lie_sequence_sampling_logits(lie_sequence *s, float *p, size_t c,
                                        size_t *n, lie_error *e) {
  return lie_sequence_logits(s, p, c, n, e);
}
void lie_sequence_cancel(lie_sequence *s) { atomic_store(&s->cancelled,1); }
lie_status lie_sequences_decode(lie_sequence *const *s,size_t n,lie_decode_outcome *o,lie_error *e) {
    for(size_t i=0;i<n;++i){o[i].status=lie_sequence_decode(s[i],&o[i].result,e);if(o[i].status!=LIE_OK)return o[i].status;}return LIE_OK;
}

int lie_backend_prefix_state_supported(void){return 1;}
const char *lie_backend_state_format(void){return "synthetic-aligned-components";}
lie_status lie_sequence_state_describe(lie_sequence *s,const lie_state_layout *from,lie_state_layout *out,lie_error *e){
    (void)e;if(atomic_load(&s->cancelled))return LIE_CANCELLED;
    if(from?(s->position||s->step||from->domain!=s->m->domain):!s->position)return LIE_INVALID;
    *out=(lie_state_layout){.abi_version=LIE_STATE_ABI,.representation_version=2,.domain=s->m->domain,
        .token_count=from?from->token_count:s->position,.context_tokens=s->m->context,.prefill_chunk=s->m->chunk};
    out->model_data[0]=from?from->model_data[0]:s->step;
    out->model_data[1]=s->m->drafts;if(from&&from->model_data[1]!=out->model_data[1])return LIE_INVALID;
    uint64_t shape=out->token_count;if(!lie_state_add(out,LIE_STATE_TOKENS,0,LIE_STATE_I32,1,&shape))return LIE_INVALID;
    shape=256;if(!lie_state_add(out,LIE_STATE_LOGITS,0,LIE_STATE_F32,1,&shape))return LIE_INVALID;
    unsigned char zero[32]={0};if(memcmp(s->scope,zero,32)){shape=32;if(!lie_state_add(out,LIE_STATE_CACHE_SCOPE,0,LIE_STATE_U8,1,&shape))return LIE_INVALID;}
    return LIE_OK;
}
lie_status lie_sequence_state_read(lie_sequence *s,const lie_state_layout *l,void *p,size_t n,lie_error *e){
    uint64_t bytes;if(!lie_state_validate(l,&bytes)||bytes!=n)return LIE_INVALID;
    if(atomic_load(&s->cancelled))return LIE_CANCELLED;
    memcpy((char*)p+l->sections[0].offset,s->prompt,l->sections[0].bytes);
    if(l->section_count==3)memcpy((char*)p+l->sections[2].offset,s->scope,32);
    size_t used;return lie_sequence_logits(s,(float*)((char*)p+l->sections[1].offset),256,&used,e);
}
lie_status lie_sequence_state_write(lie_sequence *s,const lie_state_layout *l,const void *p,size_t n,lie_error *e){
    (void)e;uint64_t bytes;if(!lie_state_validate(l,&bytes)||bytes!=n||s->position)return LIE_INVALID;
    if(atomic_load(&s->cancelled))return LIE_CANCELLED;
    if(l->section_count==3&&memcmp((const char*)p+l->sections[2].offset,s->scope,32))return LIE_INVALID;
    memcpy(s->prompt,(const char*)p+l->sections[0].offset,l->sections[0].bytes);s->position=l->token_count;s->step=l->model_data[0];return LIE_OK;
}

lie_status lie_model_chat_anchor(lie_model *m,const int32_t *t,size_t n,size_t *out,lie_error *e){
    (void)m;(void)t;(void)n;(void)e;*out=0;return LIE_OK;
}

lie_status lie_backend_open_mtp(const char *p,const lie_model_options *o,uint32_t width,const char *predictor,uint32_t drafts,lie_model **m,lie_error *e){
    if(!predictor)return LIE_INVALID;
    uint32_t cap=!strcmp(predictor,":wide-fixture:")?12:!strcmp(predictor,":fixture:")?7:0;
    if(!cap||drafts>cap)return LIE_INVALID;
    if(!drafts)drafts=cap;
    lie_status rc=lie_backend_open_batch(p,o,width,m,e);if(rc==LIE_OK){(*m)->mtp=true;(*m)->drafts=drafts;}return rc;
}
lie_status lie_sequences_decode_mtp(lie_sequence *const *rows,const uint32_t *limits,size_t n,lie_mtp_outcome *out,lie_error *e){
    if(!rows||!limits||!out||!n||n>LIE_DECODE_MAX_ROWS)return LIE_INVALID;
    for(size_t i=0;i<n;++i){
        out[i]=(lie_mtp_outcome){.status=LIE_OK};
        if(!limits[i]||limits[i]>LIE_MTP_MAX_OUTPUT)return LIE_INVALID;
        for(uint32_t k=0;k<limits[i];++k){lie_decode_result d={0};lie_status rc=lie_sequence_decode(rows[i],&d,e);
            if(rc!=LIE_OK){out[i]=(lie_mtp_outcome){.status=rc};if(rc!=LIE_CANCELLED)return rc;break;}
            out[i].stop=d.stop;out[i].position=d.position;
            if(d.emitted){out[i].tokens[out[i].emitted++]=d.token;if(d.emitted>1)out[i].emitted=limits[i]+1;}
            if(d.stop||d.emitted!=1)break;
        }
        if(out[i].emitted){out[i].drafted=out[i].emitted-1;out[i].accepted=out[i].drafted;}
    }
    return LIE_OK;
}

lie_status lie_model_mtp_info(lie_model *m,lie_mtp_info *out,lie_error *e){
    (void)e;if(!m||!out||!m->mtp)return LIE_UNSUPPORTED;
    *out=(lie_mtp_info){LIE_MTP_ABI,sizeof(*out),m->drafts,m->drafts+1,1};return LIE_OK;
}

struct lie_vision_prompt { lie_model *model;unsigned char scope[32]; };
lie_status lie_backend_open_vision(const char *p,const lie_model_options *o,uint32_t width,const char *encoder,lie_model **m,lie_error *e){
    unsigned count=!strcmp(encoder,":vision-a:")?16:!strcmp(encoder,":vision-b:")?2:0;if(!count)return LIE_INVALID;
    lie_status rc=lie_backend_open_batch(p,o,width,m,e);if(rc==LIE_OK)(*m)->vision=count;return rc;
}
lie_status lie_model_vision_info(lie_model *m,lie_vision_info *out,lie_error *e){
    (void)e;if(!m||!out||!m->vision)return LIE_UNSUPPORTED;
    *out=(lie_vision_info){LIE_VISION_ABI,sizeof(*out),m->vision,LIE_VISION_MAX_PIXELS,LIE_VISION_MAX_BYTES,6,1};return LIE_OK;
}
lie_status lie_model_prepare_vision(lie_model *m,const lie_chat_template *t,const lie_image_input *images,size_t count,
    int32_t *tokens,size_t cap,size_t *n,lie_vision_prompt **out,lie_error *e){
    if(!m||!t||!images||!count||count>m->vision||!out||*out)return LIE_INVALID;
    lie_status rc=lie_model_chat_tokens_ex(m,t,tokens,cap,n,e);if(rc!=LIE_OK)return rc;
    unsigned stride=m->vision==2?13:3;size_t extra=count*stride;
    if(*n>cap||extra>cap-*n){*n+=extra;return LIE_BUFFER_SMALL;}
    for(size_t i=0;i<count;++i){lie_image_dimensions d;if(lie_image_inspect(&images[i],&d,e)!=LIE_OK)return LIE_INVALID;
        for(unsigned j=0;j<stride;++j)tokens[(*n)++]=images[i].data[images[i].bytes-1];}
    *out=calloc(1,sizeof(**out));if(!*out)return LIE_RESOURCE_LIMIT;(*out)->model=m;
    /* Deliberately non-cryptographic fixture identity; production Qwen hashes
     * decoded/resized pixels, grid/preprocessor and actual encoder identity. */
    uint64_t hash=UINT64_C(1469598103934665603)^m->vision;
    for(size_t i=0;i<count;++i){for(size_t j=0;j<images[i].bytes;++j)hash=(hash^images[i].data[j])*UINT64_C(1099511628211);
        hash=(hash^images[i].text_offset)*UINT64_C(1099511628211);hash=(hash^images[i].message_index)*UINT64_C(1099511628211);
    }
    for(unsigned i=0;i<32;++i)(*out)->scope[i]=(unsigned char)(hash>>(8*(i%8)));
    return LIE_OK;
}
lie_status lie_sequence_attach_vision(lie_sequence *s,const lie_vision_prompt *p,lie_error *e){
    (void)e;if(!s||!p||s->m!=p->model||s->position)return LIE_INVALID;memcpy(s->scope,p->scope,32);return LIE_OK;
}
lie_status lie_vision_prompt_close(lie_vision_prompt **p,lie_error *e){(void)e;if(!p||!*p)return LIE_INVALID;free(*p);*p=NULL;return LIE_OK;}

lie_status lie_vision_prompt_cache_scope(const lie_vision_prompt *p,unsigned char out[32],lie_error *e){(void)e;if(!p||!out)return LIE_INVALID;memcpy(out,p->scope,32);return LIE_OK;}

lie_status lie_backend_open_mtp_vision(const char *p,const lie_model_options *o,uint32_t w,const char *d,uint32_t n,const char *v,lie_model **out,lie_error *e){
    lie_model *encoder=NULL;lie_status rc=lie_backend_open_vision(p,o,w,v,&encoder,e);if(rc!=LIE_OK)return rc;
    rc=lie_backend_open_mtp(p,o,w,d,n,out,e);
    if(rc==LIE_OK){(*out)->vision=encoder->vision;}
    (void)lie_model_close(&encoder,NULL);return rc;
}
