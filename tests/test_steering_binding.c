/* SPDX-License-Identifier: MIT */
/* Synthetic model transfer; actual shared RAM/SSD codecs, no GPU/inference. */
#include "lie/steering_state.h"
#include "lie/kvc.h"
#include "lie/kvc_state.h"
#include "lie/store.h"
#include "../src/state_internal.h"
#include "../src/state_codec.h"
#include <assert.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <unistd.h>

static lie_steering_bank *bank(unsigned layers, unsigned width) {
  char path[] = "steering-binding-bank-XXXXXX";
  int fd = mkstemp(path); assert(fd >= 0);
  const unsigned char values[] = {0,0,128,63,0,0,0,64,0,0,64,64,0,0,128,64};
  assert(write(fd, values, sizeof(values)) == (ssize_t)sizeof(values) && !close(fd));
  lie_steering_geometry g = {LIE_STEERING_ABI,sizeof(g),layers,width,16};
  lie_steering_bank *b = NULL;
  assert(lie_steering_bank_load(path,&g,&b,NULL)==LIE_OK && !unlink(path));
  return b;
}
static lie_steering_policy *policy(lie_steering_bank *b, float ffn) {
  lie_steering_policy_options o = {.abi_version=LIE_STEERING_POLICY_ABI,
    .struct_bytes=sizeof(o),.max_positions=64,.bank=b};
  lie_steering_settings_init(&o.settings,b!=NULL);o.settings.ffn=ffn;
  lie_steering_policy *p = NULL;
  assert(lie_steering_policy_create(&o,&p,NULL)==LIE_OK);return p;
}
static lie_steering_policy_info info(lie_steering_policy *p) {
  lie_steering_policy_info i = {.abi_version=LIE_STEERING_POLICY_ABI,.struct_bytes=sizeof(i)};
  assert(lie_steering_policy_snapshot(p,&i,NULL)==LIE_OK);return i;
}
static void advance(lie_steering_policy *p, uint64_t n) {
  lie_steering_update *u = NULL;
  assert(lie_steering_forward_prepare(p,info(p).completed_positions,n,&u,NULL)==LIE_OK);
  assert(lie_steering_forward_complete(p,&u,n,NULL)==LIE_OK && !u);
}
static void change(lie_steering_policy *p, float ffn) {
  lie_steering_settings s;lie_steering_settings_init(&s,true);s.ffn=ffn;
  lie_steering_update *u = NULL;
  assert(lie_steering_policy_prepare_change(p,&s,&u,NULL)==LIE_OK);
  assert(lie_steering_update_commit(&u,info(p).completed_positions,NULL)==LIE_OK);
}
static lie_steering_state_view inspect(const lie_state_layout *l, unsigned format) {
  lie_steering_state_view v = {.abi_version=LIE_STEERING_STATE_BINDING_ABI,.struct_bytes=sizeof(v)};
  assert(lie_steering_state_inspect(l,format,&v,NULL)==LIE_OK);return v;
}
static lie_state_layout model(unsigned format, bool auxiliary, bool semantic) {
  lie_state_layout l = {.abi_version=LIE_STATE_ABI,.representation_version=3,
    .token_count=7,.context_tokens=32,.prefill_chunk=4,.domain=77,.format=format};
  if(format!=LIE_STATE_ALIGNED){l.model_id=5;l.quant_bits=4;}
  uint64_t n=64;assert(lie_state_add(&l,LIE_STATE_HEADER,0,LIE_STATE_U8,1,&n));
  n=7;assert(lie_state_add(&l,LIE_STATE_TOKENS,0,LIE_STATE_I32,1,&n));
  n=4;assert(lie_state_add(&l,LIE_STATE_LOGITS,0,LIE_STATE_F32,1,&n));
  if(auxiliary){
    n=8;assert(lie_state_add(&l,LIE_STATE_AUXILIARY,0,LIE_STATE_U8,1,&n));
    n=12;assert(lie_state_add(&l,LIE_STATE_MODEL_COMPONENT,7,LIE_STATE_U8,1,&n));
  }
  if(semantic){n=32;assert(lie_state_add(&l,LIE_STATE_CACHE_SCOPE,0,LIE_STATE_U8,1,&n));}
  uint64_t bytes;assert(lie_state_validate(&l,&bytes));return l;
}
struct lie_sequence {
  lie_state_layout model;
  lie_steering_policy *policy;
  unsigned char semantic[32], bytes[512];
  unsigned writes;
  bool empty;
};
static struct lie_sequence sequence(lie_state_layout m, lie_steering_policy *p, bool empty, bool semantic) {
  struct lie_sequence s = {.model=m,.policy=p,.empty=empty};
  if(semantic)s.semantic[0]=19;
  /* Distinct section bytes make a prefix move/change observable. */
  for(unsigned i=0;i<m.section_count;++i){
    const lie_state_section *part=&m.sections[i];assert(part->offset+part->bytes<=sizeof(s.bytes));
    memset(s.bytes+part->offset,(int)(11+i),part->bytes);
    if(part->role==LIE_STATE_TOKENS){const int32_t ids[]={1,2,3,4,5,6,7};memcpy(s.bytes+part->offset,ids,sizeof(ids));}
    if(part->role==LIE_STATE_CACHE_SCOPE)memcpy(s.bytes+part->offset,s.semantic,32);
  }
  return s;
}
lie_status lie_sequence_state_describe(lie_sequence *s,const lie_state_layout *source,
                                      lie_state_layout *out,lie_error *e) {
  if(!source)return lie_steering_state_plan(s->policy,&s->model,out,e);
  if(!s->empty)return LIE_INVALID;
  lie_steering_state_view v = {.abi_version=LIE_STEERING_STATE_BINDING_ABI,.struct_bytes=sizeof(v)};
  lie_status rc=lie_steering_state_inspect(source,s->model.format,&v,e);
  if(rc!=LIE_OK)return rc;
  if(!lie_state_layout_equal(&v.model,&s->model))return LIE_INVALID;
  *out=*source;return LIE_OK;
}
lie_status lie_sequence_state_read(lie_sequence *s,const lie_state_layout *l,void *out,size_t n,lie_error *e) {
  if(s->empty)return LIE_INVALID;
  lie_steering_state_view v=inspect(l,s->model.format);
  assert(n==v.payload_bytes && n<=sizeof(s->bytes));
  memcpy(out,s->bytes,v.model_bytes);
  return lie_steering_state_capture(s->policy,l,s->model.format,s->semantic,out,n,e);
}
lie_status lie_sequence_state_write(lie_sequence *s,const lie_state_layout *l,const void *raw,size_t n,lie_error *e) {
  if(!s->empty)return LIE_INVALID;
  lie_steering_update *u=NULL;unsigned char scope[32];
  lie_status rc=lie_steering_state_prepare_restore(s->policy,l,s->model.format,s->semantic,raw,n,&u,scope,e);
  if(rc!=LIE_OK)return rc;
  /* Independent model content admission, before any simulated transfer. */
  const unsigned char *bytes=raw;
  for(unsigned i=0;i<s->model.section_count;++i){
    const lie_state_section *part=&s->model.sections[i];
    if(part->role!=LIE_STATE_CACHE_SCOPE && memcmp(bytes+part->offset,s->bytes+part->offset,part->bytes)){
      lie_steering_update_discard(&u);return LIE_INVALID;
    }
  }
  memcpy(s->bytes,raw,n);++s->writes;
  rc=lie_steering_update_commit(&u,l->token_count,e);
  assert(rc==LIE_OK && !u);s->empty=false;return rc;
}
static void framing(void) {
  const struct {unsigned format;bool aux,semantic;} cases[] = {
    {LIE_STATE_ALIGNED,false,false},{LIE_STATE_ALIGNED,false,true},
    {LIE_STATE_KVC,false,false},{LIE_STATE_KVC_AUX,true,false},{LIE_STATE_KVC_AUX,true,true}};
  for(unsigned k=0;k<sizeof(cases)/sizeof(*cases);++k){
    lie_state_layout inner=model(cases[k].format,cases[k].aux,cases[k].semantic),outer={0};
    assert(lie_steering_state_extend(&inner,&outer,NULL)==LIE_OK);
    lie_steering_state_view v=inspect(&outer,inner.format);
    assert(lie_state_layout_equal(&v.model,&inner));
    assert(!memcmp(outer.sections,inner.sections,inner.section_count*sizeof(inner.sections[0])));
    assert(v.policy_offset>=v.model_bytes && v.payload_bytes>v.model_bytes);
    if(inner.format==LIE_STATE_KVC)assert(v.inserted_auxiliary_offset==108);
    else assert(v.inserted_auxiliary_offset==LIE_STEERING_STATE_NO_OFFSET);
    if(cases[k].semantic)assert(v.scope_offset==inner.sections[inner.section_count-1].offset);
    if(inner.format!=LIE_STATE_ALIGNED){uint64_t before,old_aux,after,new_aux;
      assert(lie_state_kvc_parts(&inner,&before,&old_aux) && lie_state_kvc_parts(&outer,&after,&new_aux));
      assert(before==after && old_aux<new_aux);
    }
    lie_state_layout alias=inner;assert(lie_steering_state_extend(&alias,&alias,NULL)==LIE_OK);
    assert(lie_state_layout_equal(&alias,&outer));
    lie_steering_state_view saved=v;v.abi_version=0;
    assert(lie_steering_state_inspect(&outer,inner.format,&v,NULL)==LIE_INVALID && !v.abi_version);
    v=saved;
    lie_state_layout wrong=outer;uint64_t one=1;
    assert(lie_state_add(&wrong,LIE_STATE_MODEL_COMPONENT+1,0,LIE_STATE_U8,1,&one));
    uint64_t n;
    if(lie_state_validate(&wrong,&n))
      assert(lie_steering_state_inspect(&wrong,inner.format,&v,NULL)==LIE_INVALID && !memcmp(&v,&saved,sizeof(v)));
    outer=(lie_state_layout){0};lie_state_layout unchanged=outer;
    assert(lie_steering_state_extend(NULL,&outer,NULL)==LIE_INVALID && !memcmp(&outer,&unchanged,sizeof(outer)));
  }
  /* Existing auxiliary-only model prefix remains auxiliary, even though its
   * eight-byte marker resembles the size of a newly inserted boundary. */
  lie_state_layout inner=model(LIE_STATE_KVC_AUX,true,false);--inner.section_count;
  lie_state_layout outer;
  assert(lie_steering_state_extend(&inner,&outer,NULL)==LIE_OK);
  lie_steering_state_view v=inspect(&outer,LIE_STATE_KVC_AUX);
  assert(lie_state_layout_equal(&v.model,&inner));
}
static void refusal(lie_steering_policy *p,const lie_state_layout *l,unsigned format,
                    const unsigned char semantic[32],const void *raw,size_t n) {
  unsigned char before[LIE_STEERING_STATE_BYTES],after[sizeof(before)],scope[32],saved[32];
  assert(lie_steering_policy_encode(p,before,sizeof(before),NULL)==LIE_OK);
  memset(scope,0xa5,sizeof(scope));memcpy(saved,scope,sizeof(saved));
  lie_steering_update *u=NULL;
  assert(lie_steering_state_prepare_restore(p,l,format,semantic,raw,n,&u,scope,NULL)!=LIE_OK && !u);
  assert(!memcmp(scope,saved,sizeof(scope)) && !info(p).outstanding_updates);
  assert(lie_steering_policy_encode(p,after,sizeof(after),NULL)==LIE_OK && !memcmp(before,after,sizeof(before)));
}
static void roundtrip(unsigned format,bool aux,bool semantic,bool active) {
  lie_steering_bank *b=bank(2,2);
  lie_steering_policy *p=policy(b,active?1:0),*dest=policy(b,active?1:0);
  advance(p,7);
  lie_state_layout inner=model(format,aux,semantic);
  struct lie_sequence source=sequence(inner,p,false,semantic),clone=sequence(inner,dest,true,semantic);
  lie_state_layout plan;uint64_t budget;
  assert(lie_state_plan(&source,&plan,&budget,NULL)==LIE_OK);
  lie_steering_state_view v=inspect(&plan,inner.format);
  if(!active)assert(lie_state_layout_equal(&plan,&inner));
  lie_state *state=NULL;
  assert(lie_state_capture(&source,&plan,budget,&state,NULL)==LIE_OK);
  assert(state->payload_bytes==v.payload_bytes);
  for(unsigned i=0;i<inner.section_count;++i){const lie_state_section *part=&inner.sections[i];
    if(part->role!=LIE_STATE_CACHE_SCOPE)assert(!memcmp(state->payload+part->offset,source.bytes+part->offset,part->bytes));
  }
  if(active && format==LIE_STATE_KVC)assert(!memcmp(state->payload+108,"LIEDIR1",8));
  if(active){
    for(size_t i=0;i<LIE_STEERING_STATE_BYTES;++i){
      state->payload[v.policy_offset+i]^=1;
      refusal(dest,&plan,inner.format,clone.semantic,state->payload,state->payload_bytes);
      state->payload[v.policy_offset+i]^=1;
    }
    lie_steering_policy *wrong=policy(b,2);
    refusal(wrong,&plan,inner.format,clone.semantic,state->payload,state->payload_bytes);
    lie_steering_policy_release(&wrong);
    lie_steering_bank *different=bank(1,4);wrong=policy(different,1);
    refusal(wrong,&plan,inner.format,clone.semantic,state->payload,state->payload_bytes);
    lie_steering_policy_release(&wrong);lie_steering_bank_release(&different);
  }
  refusal(dest,&plan,inner.format,clone.semantic,state->payload,state->payload_bytes-1);
  if(v.scope_offset!=LIE_STEERING_STATE_NO_OFFSET){
    state->payload[v.scope_offset]^=1;
    assert(lie_state_restore(&clone,state,NULL)==LIE_INVALID && clone.empty && !clone.writes);
    state->payload[v.scope_offset]^=1;
  }
  if(v.inserted_auxiliary_offset!=LIE_STEERING_STATE_NO_OFFSET){
    state->payload[v.inserted_auxiliary_offset]^=1;
    refusal(dest,&plan,inner.format,clone.semantic,state->payload,state->payload_bytes);
    state->payload[v.inserted_auxiliary_offset]^=1;
  }
  state->payload[0]^=1;
  assert(lie_state_restore(&clone,state,NULL)==LIE_INVALID && clone.empty && !clone.writes);
  assert(!info(dest).outstanding_updates && !info(dest).completed_positions);
  state->payload[0]^=1;
  assert(lie_state_restore(&clone,state,NULL)==LIE_OK && !clone.empty && clone.writes==1);
  assert(info(dest).completed_positions==7 && info(dest).history_epochs==info(p).history_epochs &&
         !memcmp(info(dest).history_sha256,info(p).history_sha256,32));
  advance(dest,9);advance(p,9);
  assert(!memcmp(info(dest).cache_scope_sha256,info(p).cache_scope_sha256,32));
  if(format!=LIE_STATE_ALIGNED){
    char path[]="steering-binding-ssd-XXXXXX";int fd=mkstemp(path);assert(fd>=0);
    lie_state_identity id={{1}};atomic_bool cancel=false;
    lie_cache_metadata metadata={.reason=LIE_CACHE_COLD,.text="fixture",.text_bytes=7,.trailer="client",.trailer_bytes=6};
    assert(lie_state_file_write_ex(fd,&id,state,&metadata,&cancel));
    lie_kvc_limits limits=lie_kvc_default_limits(1u<<20);lie_kvc *wire=NULL;
    assert(lie_kvc_read_fd(fd,&limits,&wire,NULL)==LIE_OK);
    uint64_t base,extra;assert(lie_state_kvc_parts(&inner,&base,&extra));
    const lie_kvc_view *view=lie_kvc_get_view(wire);
    assert(view->payload.bytes==base && !memcmp(view->payload.data,source.bytes,base));
    assert(view->trailer.bytes>=6 && !memcmp(view->trailer.data,"client",6));
    lie_kvc_destroy(&wire);
    lie_state *loaded=lie_state_file_read(fd,&id,inner.domain,budget,&cancel);assert(loaded);
    lie_steering_policy *restarted=policy(b,active?1:0);
    struct lie_sequence receiver=sequence(inner,restarted,true,semantic);
    assert(lie_state_restore(&receiver,loaded,NULL)==LIE_OK && receiver.writes==1);
    assert(info(restarted).completed_positions==7);
    lie_state_destroy(&loaded);lie_steering_policy_release(&restarted);
    assert(!close(fd) && !unlink(path));
  }
  lie_state_destroy(&state);lie_steering_policy_release(&p);lie_steering_policy_release(&dest);lie_steering_bank_release(&b);
}
static void mixed_history(void) {
  lie_steering_bank *b=bank(2,2);lie_steering_policy *p=policy(b,1),*zero=policy(b,0);
  advance(p,3);change(p,0);advance(p,7);
  lie_state_layout inner=model(LIE_STATE_KVC,false,false),outer;
  assert(lie_steering_state_plan(p,&inner,&outer,NULL)==LIE_OK);
  lie_steering_state_view v=inspect(&outer,inner.format);unsigned char raw[512]={0},scope[32]={0};
  assert(lie_steering_state_capture(p,&outer,inner.format,scope,raw,v.payload_bytes,NULL)==LIE_OK);
  /* Current zero scales cannot relabel a prefix whose past work was steered. */
  refusal(zero,&outer,inner.format,scope,raw,v.payload_bytes);
  lie_state_layout legacy=inner;
  assert(lie_steering_state_plan(zero,&legacy,&outer,NULL)==LIE_BACKEND_FAILED);
  lie_steering_policy_release(&p);lie_steering_policy_release(&zero);lie_steering_bank_release(&b);
}
typedef struct {
  lie_steering_policy *source,*destination;
  const lie_state_layout *inner,*outer;
  unsigned char *raw;
  size_t bytes;
  const unsigned char *semantic;
} owner_args;
static void *other_owner(void *opaque) {
  owner_args *a=opaque;lie_state_layout out={0},before=out;
  assert(lie_steering_state_plan(a->source,a->inner,&out,NULL)==LIE_WRONG_OWNER && !memcmp(&out,&before,sizeof(out)));
  unsigned char *saved=malloc(a->bytes);assert(saved);memcpy(saved,a->raw,a->bytes);
  assert(lie_steering_state_capture(a->source,a->outer,a->inner->format,a->semantic,a->raw,a->bytes,NULL)==LIE_WRONG_OWNER);
  assert(!memcmp(saved,a->raw,a->bytes));free(saved);
  lie_steering_update *u=NULL;unsigned char scope[32]={0},zero[32]={0};
  assert(lie_steering_state_prepare_restore(a->destination,a->outer,a->inner->format,a->semantic,a->raw,a->bytes,&u,scope,NULL)==LIE_WRONG_OWNER && !u);
  assert(!memcmp(scope,zero,32));return NULL;
}
static lie_status model_check(const lie_kvc_qwen_geometry *g,const lie_state_layout *l,
  bool mtp,bool vision,const unsigned char *raw,size_t n,lie_kvc_span positions,
  const unsigned char scope[32],const lie_kvc_limits *limits) {
  if(vision)return mtp?lie_kvc_qwen_mtp_vision_state_check(g,l,31,(lie_kvc_span){raw,n},positions,scope,limits,NULL):
    lie_kvc_qwen_vision_state_check(g,l,31,(lie_kvc_span){raw,n},positions,scope,limits,NULL);
  return lie_kvc_qwen_state_check(g,l,31,(lie_kvc_span){raw,n},limits,NULL);
}
static void actual_model_codecs(void) {
  for(unsigned mode=0;mode<4;++mode){
    const bool mtp=mode&1u,vision=mode&2u;
    const lie_kvc_qwen_geometry g={4,mtp?1u:0u,2,1,4,3,2,3,2,5,2,6,32};
    const lie_kvc_qwen_frontier f={.context_tokens=64,.prefill_tokens=8,.graph_capacity=64,
      .tokens=9,.mtp_tokens=mtp?5u:0u,.mrope_delta=vision?-2:0};
    lie_state_layout inner,outer;
    lie_status rc=mtp&&vision?lie_kvc_qwen_mtp_vision_state_plan(&g,&f,77,5,4,4,7,&inner,NULL):
      mtp?lie_kvc_qwen_mtp_state_plan(&g,&f,77,5,4,4,7,&inner,NULL):
      vision?lie_kvc_qwen_vision_state_plan(&g,&f,77,5,4,&inner,NULL):
      lie_kvc_qwen_state_plan(&g,&f,77,5,4,&inner,NULL);
    assert(rc==LIE_OK);
    lie_steering_bank *b=bank(2,2);
    lie_steering_policy *p=policy(b,1),*destination=policy(b,1);advance(p,9);
    assert(lie_steering_state_plan(p,&inner,&outer,NULL)==LIE_OK);
    lie_steering_state_view view=inspect(&outer,inner.format);
    unsigned char *raw=calloc(1,view.payload_bytes);assert(raw);
    unsigned char positions[9*16]={0},semantic[32]={0},combined[32],restored[32];
    if(vision)semantic[0]=19;
    for(unsigned i=0;i<9;++i){const int32_t row[4]={(int32_t)i,(int32_t)(i/3),(int32_t)(i/2),0};memcpy(positions+16*i,row,16);}
    for(unsigned i=0;i<inner.section_count;++i)if(inner.sections[i].role==LIE_STATE_TOKENS)
      for(unsigned j=0;j<9;++j){int32_t id=(int32_t)j+1;memcpy(raw+inner.sections[i].offset+4*j,&id,4);}
    assert(lie_steering_policy_cache_scope(p,semantic,combined,NULL)==LIE_OK);
    lie_kvc_qwen_mtp_controller controller={.retry_tokens=3,.probe_depth=2,.explored_depth=4,.probe_delay=16,.failed_depths=1};
    for(unsigned i=0;i<7;++i){controller.successes[i]=1.5f+i;controller.failures[i]=.5f;}
    lie_kvc_span at=vision?(lie_kvc_span){positions,sizeof(positions)}:(lie_kvc_span){0};
    lie_kvc_limits limits=lie_kvc_default_limits(1u<<20);
    rc=mtp&&vision?lie_kvc_qwen_mtp_vision_state_finish(&g,&inner,31,&controller,at,combined,raw,view.model_bytes,&limits,NULL):
      mtp?lie_kvc_qwen_mtp_state_finish(&g,&inner,31,&controller,raw,view.model_bytes,&limits,NULL):
      vision?lie_kvc_qwen_vision_state_finish(&g,&inner,31,at,combined,raw,view.model_bytes,&limits,NULL):
      lie_kvc_qwen_state_finish(&g,&inner,31,raw,view.model_bytes,&limits,NULL);
    assert(rc==LIE_OK);
    unsigned char *before=malloc(view.model_bytes);assert(before);memcpy(before,raw,view.model_bytes);
    assert(lie_steering_state_capture(p,&outer,inner.format,semantic,raw,view.payload_bytes,NULL)==LIE_OK);
    assert(!memcmp(before,raw,view.model_bytes));free(before);
    assert(model_check(&g,&view.model,mtp,vision,raw,view.model_bytes,at,combined,&limits)==LIE_OK);
    if(vision)assert(model_check(&g,&view.model,mtp,vision,raw,view.model_bytes,at,semantic,&limits)==LIE_INVALID);
    owner_args args={p,destination,&inner,&outer,raw,view.payload_bytes,semantic};pthread_t thread;
    assert(!pthread_create(&thread,NULL,other_owner,&args) && !pthread_join(thread,NULL));
    lie_steering_update *u=NULL;
    assert(lie_steering_state_prepare_restore(destination,&outer,inner.format,semantic,raw,view.payload_bytes,&u,restored,NULL)==LIE_OK);
    assert(!memcmp(combined,restored,32));
    /* Valid steering metadata does not excuse corrupt numerical model framing.
     * The independent codec rejects it; the prepared policy is discarded. */
    raw[8]^=1; /* Declared context must match the validated descriptor. */
    assert(model_check(&g,&view.model,mtp,vision,raw,view.model_bytes,at,restored,&limits)==LIE_INVALID);
    raw[8]^=1;lie_steering_update_discard(&u);
    assert(!info(destination).completed_positions && !info(destination).outstanding_updates);
    assert(lie_steering_state_prepare_restore(destination,&outer,inner.format,semantic,raw,view.payload_bytes,&u,restored,NULL)==LIE_OK);
    assert(model_check(&g,&view.model,mtp,vision,raw,view.model_bytes,at,restored,&limits)==LIE_OK);
    lie_steering_policy_release(&destination); /* Plan retains its entire policy/bank. */
    assert(lie_steering_update_commit(&u,9,NULL)==LIE_OK && !u);
    free(raw);lie_steering_policy_release(&p);lie_steering_bank_release(&b);
  }
}
int main(void) {
  framing();
  roundtrip(LIE_STATE_ALIGNED,false,false,true);
  roundtrip(LIE_STATE_ALIGNED,false,true,true);
  roundtrip(LIE_STATE_KVC,false,false,true);
  roundtrip(LIE_STATE_KVC_AUX,true,false,true);
  roundtrip(LIE_STATE_KVC_AUX,true,true,true);
  roundtrip(LIE_STATE_KVC,false,false,false);
  roundtrip(LIE_STATE_KVC_AUX,true,true,false);
  mixed_history();
  actual_model_codecs();
  puts("steering model-prefix binding and RAM/SSD compatibility: PASS (NOT-INFERENCE)");
  return 0;
}
