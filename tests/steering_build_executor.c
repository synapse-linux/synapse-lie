/* SPDX-License-Identifier: MIT */
/* Synthetic borrowed-row/lifetime fixture. NOT-INFERENCE; no model or device. */
#include "lie/activation_observer.h"
#include <math.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
struct lie_model { uint32_t context, chunk; char mode[32]; };
struct lie_sequence { lie_model *model; size_t position; int32_t first; };
static lie_status error(lie_error *e, lie_status s, const char *message) {
  if (e) snprintf(e->message,sizeof(e->message),"%s",message);
  return s;
}
const char *lie_backend_name(void) { return "steering-build-fixture-NOT-INFERENCE"; }
const char *lie_backend_source_pin(void) { return "synthetic-only"; }
int lie_backend_is_synthetic(void) { return 1; }
lie_status lie_backend_open(const char *path, const lie_model_options *o, lie_model **out, lie_error *e) {
  if (!path || strlen(path)>=32 || !o || !out || *out || o->abi_version!=LIE_EXECUTOR_ABI ||
      o->struct_bytes!=sizeof(*o)) return error(e,LIE_INVALID,"invalid fixture admission");
  *out=calloc(1,sizeof(**out)); if (!*out) return LIE_RESOURCE_LIMIT;
  (*out)->context=o->context_tokens; (*out)->chunk=o->prefill_chunk_tokens;
  snprintf((*out)->mode,sizeof((*out)->mode),"%s",path); return LIE_OK;
}
lie_status lie_model_get_info(lie_model *m, lie_model_info *out, lie_error *e) {
  (void)e; *out=(lie_model_info){.abi_version=LIE_EXECUTOR_ABI,.context_tokens=m->context,
    .prefill_capacity=m->chunk}; return LIE_OK;
}
lie_status lie_model_activation_geometry(lie_model *m, lie_activation_geometry *out, lie_error *e) {
  (void)e; *out=(lie_activation_geometry){LIE_ACTIVATION_OBSERVER_ABI,sizeof(*out),2,
    !strcmp(m->mode,":geometry:")?0u:2u,2,LIE_ACTIVATION_FFN|LIE_ACTIVATION_ATTENTION}; return LIE_OK;
}
lie_status lie_model_tokenize(lie_model *m, const char *text, size_t n, int32_t *out,
  size_t capacity, size_t *required, lie_error *e) {
  (void)m; (void)e; *required=n; if (n>capacity) return LIE_BUFFER_SMALL;
  for (size_t k=0;k<n;++k) out[k]=(unsigned char)text[k];
  return LIE_OK;
}
lie_status lie_model_chat_tokens(lie_model *m, const lie_chat_message *p, size_t count,
  int32_t *out, size_t capacity, size_t *required, lie_error *e) {
  if (count!=1 || p->role!=LIE_CHAT_USER) return LIE_INVALID;
  *required=p->bytes+2; if (*required>capacity) return LIE_BUFFER_SMALL;
  size_t ignored=0; lie_status s=lie_model_tokenize(m,p->content,p->bytes,out,capacity,&ignored,e);
  out[p->bytes]=777; out[p->bytes+1]=888; return s;
}
lie_status lie_sequence_create(lie_model *m, lie_sequence **out, lie_error *e) {
  (void)e; *out=calloc(1,sizeof(**out)); if (!*out) return LIE_RESOURCE_LIMIT;
  (*out)->model=m; return LIE_OK;
}
lie_status lie_sequence_prefill(lie_sequence *s, const int32_t *ids, size_t n, lie_error *e) {
  if (!s || !ids || n<=s->position || n-s->position>s->model->chunk || n>s->model->context ||
      (s->position && ids[0]!=s->first)) return error(e,LIE_INVALID,"noncumulative fixture prefill");
  if (!strcmp(s->model->mode,":early-fail:")) return error(e,LIE_BACKEND_FAILED,"synthetic prefill failure before observations");
  s->first=ids[0]; s->position=n; return LIE_OK;
}
lie_status lie_sequence_prefill_observed(lie_sequence *s, const int32_t *ids, size_t n,
  const lie_activation_observer *o, lie_error *e) {
  lie_status status=lie_sequence_prefill(s,ids,n,e); if (status!=LIE_OK) return status;
  if (!o || o->max_row_bytes<((o->components&LIE_ACTIVATION_FFN)?16u:8u)) return LIE_INVALID;
  bool target=s->first=='T', zero=!strcmp(s->model->mode,":zero:");
  const float delta[2][2]={{3,4},{-4,3}};
  for (unsigned rev=0;rev<2;++rev) {
    unsigned layer=1-rev;
    if (!layer && !strcmp(s->model->mode,":missing:")) continue;
    for (unsigned c=0;c<2;++c) {
      lie_activation_component component=c?LIE_ACTIVATION_ATTENTION:LIE_ACTIVATION_FFN;
      if (!(component&o->components)) continue;
      float values[4]; unsigned branches=c?1:2;
      for (unsigned b=0;b<branches;++b) for (unsigned k=0;k<2;++k)
        values[b*2+k]=(!zero && target?delta[layer][k]:0)+(c?0:(b?1.0f:-1.0f));
      if (!layer && !c && !strcmp(s->model->mode,":nan:")) values[0]=NAN;
      lie_activation_observation row={.abi_version=LIE_ACTIVATION_OBSERVER_ABI,.struct_bytes=sizeof(row),
        .component=component,.layer=layer,.layers=2,.width=2,.branches=branches,.token_position=n-1,
        .values=values,.value_count=2*branches};
      if (!strcmp(s->model->mode,":wrong-token:")) ++row.token_position;
      o->observe(o->context,&row);
      if (!rev && !c && !strcmp(s->model->mode,":duplicate:")) o->observe(o->context,&row);
      /* Deliberately overwrite the borrowed storage before returning. */
      for (unsigned k=0;k<4;++k) values[k]=NAN;
    }
  }
  if (!strcmp(s->model->mode,":fail:")) return error(e,LIE_BACKEND_FAILED,"synthetic failure after complete borrowed rows");
  return LIE_OK;
}
lie_status lie_sequence_close(lie_sequence **out, lie_error *e) {
  bool failed=!strcmp((*out)->model->mode,":close-failure:"); free(*out); *out=NULL;
  return failed?error(e,LIE_BACKEND_FAILED,"synthetic sequence close failure"):LIE_OK;
}
lie_status lie_model_close(lie_model **out, lie_error *e) {
  bool failed=!strcmp((*out)->mode,":model-close-failure:"); free(*out); *out=NULL;
  return failed?error(e,LIE_BACKEND_FAILED,"synthetic model close failure"):LIE_OK;
}
