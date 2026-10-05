/* SPDX-License-Identifier: MIT */
#include "core_events.h"
#include "core_input.h"
#include "generation.h"
#include "lie/core.h"
#include "lie/inference.h"
#include "output_json.h"
#include "prefix_cache.h"
#include <errno.h>
#include <math.h>
#include <openssl/rand.h>
#include <poll.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/eventfd.h>
#include <time.h>
#include <unistd.h>

struct lie_job {
  lie_core *owner;
  lie_core_request request;
  void *request_storage;
  size_t request_bytes;
  bool automatic_output;
  unsigned output_limit; /* Worker-owned; input reservation remains immutable. */
  int32_t *output_ids;
  lie_token_logprobs *scores;
  size_t *score_offsets, visible_bytes, scored_bytes;
  float *reporting_logits;
  lie_stop_state stop;
  lie_flow *flow;
  lie_event_stream *events;
  unsigned
      output_mode; /* Single consumer: 0 unset, 1 legacy raw, 2 semantic. */
  char output_identity[64];
  atomic_uint refs;
  atomic_bool cancel;
  atomic_bool semantic_active, semantic_done;
  /* Metadata synchronized separately from the model; never holds GPU work. */
  pthread_mutex_t gate;
  lie_job_info info;
  lie_sequence *sequence; /* worker only */
  unsigned char cache_scope[32];
  unsigned char semantic_scope[32]; /* Image identity before steering composition. */
  lie_job_steering_info steering; /* Copied requests/snapshots under job gate. */
  lie_steering_schedule_info *schedule; /* Optional copied immutable steps. */
  int32_t *prompt;
  size_t tokens, fed;
  size_t checkpoint, next_continued, last_capture;
  char *rendered;
  size_t rendered_bytes, rendered_capacity;
  size_t *text_offsets;
  bool text_lookup, text_complete, shutdown_saved, finish_pending;
  lie_cache_reason capture_pending;
  lie_cache_metadata restored_metadata;
  bool cache_checked, capture_checked;
  bool ssd_checked;
  uint64_t ssd_ticket;
  uint32_t position;   /* Last validated completed frontier; worker only. */
  bool executing;      /* Protected by owner gate; cancellation observation. */
  bool output_blocked; /* Worker-owned, aggregate snapshot under owner gate. */
};
struct lie_core {
  pthread_t thread;
  pthread_mutex_t gate;
  atomic_bool stop;
  lie_core_info info;
  lie_core_options options;
  char *path;
  char output_namespace[33]; /* Independent of HTTP; unique across core
                                restarts. */
  char *mtp_path, *vision_path;
  char *steering_path;
  lie_steering_model_options steering_options;
  lie_steering_model_info steering_info; /* Immutable READY admission record. */
  lie_job *jobs[LIE_CORE_JOBS];
  unsigned preparing; /* Bounded admission copies, protected by gate. */
  int wake, notice;
  lie_model *model;
  lie_prefix_cache cache;
  lie_store *store;
  char *ssd_path;
  lie_job *dispatch; /* Pinned worker job, protected by owner gate. */
};
static void set_output_blocked(lie_core *w, lie_job *j, bool value) {
    if (j->output_blocked==value) return;
    j->output_blocked=value;
    pthread_mutex_lock(&w->gate);
    if (value) ++w->info.output_blocked;
    else --w->info.output_blocked;
    pthread_mutex_unlock(&w->gate);
}
static void begin_call(lie_core *w, lie_job *j, bool prefill) {
    pthread_mutex_lock(&w->gate);
    if (w->dispatch) abort();
    w->dispatch=j; j->executing=true;
    w->info.executor_phase=prefill?LIE_EXECUTOR_PREFILL:LIE_EXECUTOR_DECODE;
    if (prefill) ++w->info.prefill_started;
    else ++w->info.decode_started;
    pthread_mutex_unlock(&w->gate);
}
static bool clock_ns(uint64_t *out) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC,&t) || t.tv_sec<0 || t.tv_nsec<0 ||
        t.tv_nsec>=1000000000 || (uint64_t)t.tv_sec>(UINT64_MAX-(uint64_t)t.tv_nsec)/1000000000)
        return false;
    *out=(uint64_t)t.tv_sec*1000000000+(uint64_t)t.tv_nsec; return true;
}
static void record_call(lie_job *j, bool prefill, bool started_ok, uint64_t started,
                        unsigned completed_input) {
    /* Read before taking the metadata gate: gate, token rendering, flow credit
     * stalls and other sessions are not part of these executor-call durations. */
    uint64_t ended=0; bool ended_ok=clock_ns(&ended);
    pthread_mutex_lock(&j->gate);
    uint64_t *total=prefill?&j->info.prefill_ns:&j->info.decode_ns;
    if (!started_ok || !ended_ok || ended<started || ended-started>UINT64_MAX-*total)
        j->info.timing_valid=false;
    else *total+=ended-started;
    if (prefill) { ++j->info.prefill_calls; j->info.prefill_tokens+=completed_input; }
    else ++j->info.decode_calls;
    pthread_mutex_unlock(&j->gate);
    lie_core *w=j->owner;
    pthread_mutex_lock(&w->gate);
    if (w->dispatch!=j) abort();
    if (prefill) ++w->info.prefill_returned;
    else ++w->info.decode_returned;
    w->dispatch=NULL; j->executing=false; w->info.executor_phase=LIE_EXECUTOR_IDLE;
    pthread_mutex_unlock(&w->gate);
}
static void signal_fd(int fd) {
    uint64_t one=1; ssize_t n;
    do { n=write(fd,&one,sizeof(one)); } while (n<0 && errno==EINTR);
    if (n!=(ssize_t)sizeof(one) && !(n<0 && errno==EAGAIN)) abort();
}
static void drain_fd(int fd) {
    uint64_t value; ssize_t n;
    do { n=read(fd,&value,sizeof(value)); } while (n<0 && errno==EINTR);
    if (n!=(ssize_t)sizeof(value) && !(n<0 && errno==EAGAIN)) abort();
}
static void job_drop(lie_job *j) {
  if (atomic_fetch_sub(&j->refs, 1) != 1)
    return;
  lie_event_stream_destroy(j->events);
  if (lie_flow_destroy(&j->flow) != LIE_FLOW_OK)
    abort();
  free(j->request_storage);
  free(j->output_ids);
  free(j->scores);
  free(j->score_offsets);
  free(j->reporting_logits);
  free(j->schedule);
  free(j->prompt);
  free(j->rendered);
  free(j->text_offsets);
  lie_cache_metadata_clear(&j->restored_metadata);
  pthread_mutex_destroy(&j->gate);
  free(j);
}
void lie_job_snapshot(lie_job *j, lie_job_info *out) {
    pthread_mutex_lock(&j->gate); *out=j->info; pthread_mutex_unlock(&j->gate);
}
lie_status lie_job_steering_snapshot(lie_job *j,lie_job_steering_info *out,lie_error *e){
    if(!j||!out||out->abi_version!=LIE_JOB_STEERING_ABI||out->struct_bytes!=sizeof(*out)){
        if(e)snprintf(e->message,sizeof(e->message),"invalid job steering snapshot");
        return LIE_INVALID;
    }
    pthread_mutex_lock(&j->gate);*out=j->steering;pthread_mutex_unlock(&j->gate);return LIE_OK;
}
static bool steering_settings_valid(const lie_steering_settings *s){
    return s&&s->abi_version==LIE_STEERING_POLICY_ABI&&s->struct_bytes==sizeof(*s)&&
           isfinite(s->ffn)&&fabsf(s->ffn)<=100&&isfinite(s->attention)&&fabsf(s->attention)<=100;
}
lie_status lie_job_steering_schedule_snapshot(lie_job *j,lie_steering_schedule_info *out,lie_error *e){
    if(!j||!out||out->abi_version!=LIE_STEERING_SCHEDULE_ABI||out->struct_bytes!=sizeof(*out)){
        if(e)snprintf(e->message,sizeof(e->message),"invalid steering schedule snapshot");
        return LIE_INVALID;
    }
    pthread_mutex_lock(&j->gate);
    if(j->schedule)*out=*j->schedule;
    else *out=(lie_steering_schedule_info){.abi_version=LIE_STEERING_SCHEDULE_ABI,.struct_bytes=sizeof(*out),.terminal=j->info.retired};
    pthread_mutex_unlock(&j->gate);return LIE_OK;
}
lie_status lie_job_change_steering(lie_job *j,const lie_steering_settings *settings,uint64_t *ticket,lie_error *e){
    if(!j||!ticket||!steering_settings_valid(settings)){
        if(e)snprintf(e->message,sizeof(e->message),"invalid job steering scales");
        return LIE_INVALID;
    }
    lie_core *w=j->owner;lie_status rc=LIE_OK;
    pthread_mutex_lock(&j->gate);
    if(!w->steering_path)rc=LIE_UNSUPPORTED;
    else if(j->info.retired||j->info.finish!=LIE_FINISH_NONE||atomic_load(&j->cancel)||atomic_load(&w->stop))rc=LIE_CANCELLED;
    else if(j->schedule)rc=LIE_INVALID;
    else if(j->steering.pending||j->steering.submitted==UINT64_MAX)rc=LIE_RESOURCE_LIMIT;
    if(rc==LIE_OK){
        j->steering.requested=*settings;
        if(j->steering.requested.ffn==0)j->steering.requested.ffn=0;
        if(j->steering.requested.attention==0)j->steering.requested.attention=0;
        j->steering.pending=true;*ticket=++j->steering.submitted;
    }
    pthread_mutex_unlock(&j->gate);
    if(rc==LIE_OK)signal_fd(w->wake);
    else if(e)snprintf(e->message,sizeof(e->message),"job steering change refused (%d)",rc);
    return rc;
}
/* Existing inference owner only. Never compose a new policy with an already
 * composed scope. Refresh after every retained call, even when the boundary
 * settings repeat: the first call under a changed scale adds a history epoch. */
static lie_status steering_refresh(lie_job *j,lie_error *e){
    if(!j->owner->steering_path)return LIE_OK;
    lie_steering_policy_info policy={.abi_version=LIE_STEERING_POLICY_ABI,.struct_bytes=sizeof(policy)};
    unsigned char combined[32];lie_status rc=lie_sequence_steering_info(j->sequence,&policy,e);
    if(rc==LIE_OK&&policy.completed_positions!=j->position){
        rc=LIE_BACKEND_FAILED;if(e)snprintf(e->message,sizeof(e->message),"job and steering retained frontiers diverged");
    }
    if(rc==LIE_OK)rc=lie_sequence_steering_cache_scope(j->sequence,j->semantic_scope,combined,e);
    if(rc==LIE_OK){
        memcpy(j->cache_scope,combined,32);
        pthread_mutex_lock(&j->gate);j->steering.policy_ready=true;j->steering.policy=policy;
        memcpy(j->steering.semantic_scope,j->semantic_scope,32);memcpy(j->steering.combined_scope,combined,32);
        pthread_mutex_unlock(&j->gate);
    }
    return rc;
}
void lie_job_retain(lie_job *j) {
  if (j)
    atomic_fetch_add(&j->refs, 1);
}
size_t lie_job_retention_bytes(lie_job *j) {
  if (!j)
    return 0;
  lie_core_info info;
  lie_core_snapshot(j->owner, &info);
  size_t n = sizeof(*j) + j->request_bytes +
             (size_t)info.model.context_tokens * sizeof(int32_t) +
             j->request.max_tokens * sizeof(int32_t);
  if(j->schedule)n+=sizeof(*j->schedule);
  if (j->request.generation.logprobs)
    n += j->request.max_tokens * (sizeof(lie_token_logprobs) + sizeof(size_t));
  n += (size_t)j->request.max_tokens * LIE_CORE_TOKEN_BYTES * 12;
  n += LIE_OUTPUT_SLOTS *
           (LIE_MTP_MAX_OUTPUT * LIE_CORE_TOKEN_BYTES + LIE_STOP_BYTES) +
       4096;
  return n;
}
static void score_copy(lie_job *j, size_t index, lie_token_logprobs *out) {
  *out = j->scores[index];
  if (j->request.stop_count) {
    size_t start = j->score_offsets[index];
    size_t visible = j->visible_bytes > start ? j->visible_bytes - start : 0;
    if (out->token.bytes > visible)
      out->token.bytes = visible;
  }
}
lie_status lie_job_logprob(lie_job *j, size_t index, lie_token_logprobs *out) {
  if (!j || !out)
    return LIE_INVALID;
  pthread_mutex_lock(&j->gate);
  lie_status rc = !j->scores                       ? LIE_UNSUPPORTED
                  : index >= j->info.output_tokens ? LIE_INVALID
                                                   : LIE_OK;
  if (rc == LIE_OK)
    score_copy(j, index, out);
  pthread_mutex_unlock(&j->gate);
  return rc;
}
lie_status lie_job_logprobs(lie_job *j, size_t offset, lie_token_logprobs *out,
                            size_t capacity, size_t *required) {
  if (!j || !required || (!out && capacity))
    return LIE_INVALID;
  pthread_mutex_lock(&j->gate);
  lie_status rc = !j->scores                       ? LIE_UNSUPPORTED
                  : offset > j->info.output_tokens ? LIE_INVALID
                                                   : LIE_OK;
  *required = rc == LIE_OK ? j->info.output_tokens - offset : 0;
  if (rc == LIE_OK && *required > capacity)
    rc = LIE_BUFFER_SMALL;
  if (rc == LIE_OK && *required)
    for (size_t i = 0; i < *required; ++i)
      score_copy(j, offset + i, out + i);
  pthread_mutex_unlock(&j->gate);
  return rc;
}
bool lie_job_cache_metadata(lie_job *j,lie_cache_metadata *out){
    if(!j||!out)return false;
    pthread_mutex_lock(&j->gate);bool ok=lie_cache_metadata_copy(out,&j->restored_metadata);pthread_mutex_unlock(&j->gate);return ok;
}
static bool append_text(lie_job *j,const char *text,size_t n){
    if(n>LIE_CACHE_TEXT_MAX-j->rendered_bytes)return false;
    size_t want=j->rendered_bytes+n+1;
    if(want>j->rendered_capacity){size_t cap=j->rendered_capacity?j->rendered_capacity:4096;
        while(cap<want)cap*=2;
        if(cap>LIE_CACHE_TEXT_MAX+1)cap=LIE_CACHE_TEXT_MAX+1;
        char *p=realloc(j->rendered,cap);if(!p)return false;j->rendered=p;j->rendered_capacity=cap;}
    if(n)memcpy(j->rendered+j->rendered_bytes,text,n);
    j->rendered_bytes+=n;j->rendered[j->rendered_bytes]=0;return true;
}
static bool render_prompt(lie_core *w,lie_job *j){
    j->text_offsets=calloc((size_t)w->options.context+1,sizeof(*j->text_offsets));
    if(!j->text_offsets)return false;
    for(size_t k=0;k<j->tokens;++k){char piece[LIE_CORE_TOKEN_BYTES];size_t n=0;lie_error e={0};
        lie_status rc=lie_model_token_text(w->model,j->prompt[k],piece,sizeof(piece),&n,&e);
        if(rc!=LIE_OK||n>sizeof(piece)||!append_text(j,piece,n)){
            free(j->text_offsets);j->text_offsets=NULL;
            free(j->rendered);j->rendered=NULL;j->rendered_bytes=j->rendered_capacity=0;return false;}
        j->text_offsets[k+1]=j->rendered_bytes;
    }
    return true;
}
/* Core policies choose a live capture frontier, never rewind recurrent state.
 */
static void checkpoint_targets(lie_core *w,lie_job *j){
    const lie_cache_policy *p=&w->options.cache_policy;
    if(!w->options.prefix_cache_bytes&&!w->store){j->checkpoint=j->next_continued=0;return;}
    if(!p->enabled){j->checkpoint=j->tokens>=w->options.chunk?j->tokens-j->tokens%w->options.chunk:j->tokens;return;}
    uint32_t n=(uint32_t)j->tokens;
    if(p->cold_max_tokens&&n>p->cold_max_tokens)n=p->cold_max_tokens;
    if(j->request.kind==LIE_INPUT_MESSAGES){size_t anchor=0;lie_error error={0};
        if(lie_model_chat_anchor(w->model,j->prompt,j->tokens,&anchor,&error)==LIE_OK&&anchor>=p->min_tokens&&anchor<n)n=(uint32_t)anchor;
    }
    n=lie_cache_store_len(p,n);
    j->checkpoint=n>=p->min_tokens?n:0;
    uint32_t interval=lie_cache_continued_step(p);
    j->next_continued=interval?((j->position/interval)+1)*(size_t)interval:0;
}
static const char *lookup_text(lie_job *j,size_t *bytes){
    *bytes=j->request.cache.text_bytes?j->request.cache.text_bytes:j->rendered_bytes;
    return j->request.cache.text_bytes?j->request.cache.text:j->rendered;
}
static bool rebuild_prompt(lie_core *w,lie_job *j,const lie_state *state,const lie_cache_metadata *m){
    const lie_state_layout *l=lie_state_description(state);
    size_t key_bytes;const char *key=lookup_text(j,&key_bytes);
    if(!j->text_lookup||!m->text_bytes||m->text_bytes>key_bytes||
       (m->flags&6u)!=(j->request.cache.flags&6u)||memcmp(m->text,key,m->text_bytes)||l->token_count>w->options.context)return false;
    int32_t *tokens=malloc((size_t)w->options.context*sizeof(*tokens));if(!tokens)return false;
    memcpy(tokens,lie_state_tokens(state),l->token_count*sizeof(*tokens));
    size_t suffix=0;lie_error error={0};
    lie_status rc=m->text_bytes==key_bytes?LIE_OK:
        lie_model_tokenize(w->model,key+m->text_bytes,key_bytes-m->text_bytes,
                           tokens+l->token_count,w->options.context-l->token_count,&suffix,&error);
    size_t count=l->token_count+suffix;
    bool ok=rc==LIE_OK&&count<=w->options.context&&j->output_limit<=w->options.context-count;
    for(size_t i=0;ok&&i<count;++i)if(tokens[i]<0||(uint32_t)tokens[i]>=w->info.model.vocab_tokens)ok=false;
    if(ok){pthread_mutex_lock(&j->gate);memcpy(j->prompt,tokens,count*sizeof(*tokens));j->tokens=count;j->info.prompt_tokens=(unsigned)count;
        pthread_mutex_unlock(&j->gate);
        /* Rebuild byte offsets against the exact saved history and new suffix. */
        free(j->rendered);j->rendered=NULL;j->rendered_bytes=j->rendered_capacity=0;free(j->text_offsets);j->text_offsets=NULL;
        j->text_complete=render_prompt(w,j);j->text_lookup=j->text_complete||j->request.cache.text_bytes;checkpoint_targets(w,j);
    }
    free(tokens);return ok;
}
static lie_status copy_ids(lie_job *j, bool prompt, int32_t *out, size_t cap, size_t *needed) {
    if (!j || !needed || (!out && cap)) return LIE_INVALID;
    pthread_mutex_lock(&j->gate);
    if (prompt && !j->info.prepared) { pthread_mutex_unlock(&j->gate);return LIE_INVALID; }
    *needed=prompt?j->tokens:j->info.output_tokens;
    lie_status rc=*needed>cap?LIE_BUFFER_SMALL:LIE_OK;
    if (rc==LIE_OK && *needed) memcpy(out,prompt?j->prompt:j->output_ids,*needed*sizeof(*out));
    pthread_mutex_unlock(&j->gate);return rc;
}
lie_status lie_job_prompt_tokens(lie_job *j, int32_t *out, size_t cap, size_t *needed) {
    return copy_ids(j,true,out,cap,needed);
}
lie_status lie_job_output_tokens(lie_job *j, int32_t *out, size_t cap, size_t *needed) {
    return copy_ids(j,false,out,cap,needed);
}
void lie_core_snapshot(lie_core *w, lie_core_info *out) {
    pthread_mutex_lock(&w->gate); *out=w->info; pthread_mutex_unlock(&w->gate);
}
static void publish_outcome(lie_job *j, lie_job_finish finish, const char *message) {
    pthread_mutex_lock(&j->gate);
    j->info.finish=finish;
    if (message) snprintf(j->info.error,sizeof(j->info.error),"%s",message);
    pthread_mutex_unlock(&j->gate);
}
static void finish_job(lie_core *w, size_t index, lie_job_finish finish,
                       const char *message) {
  lie_job *j = w->jobs[index];
  lie_error error = {0};
  if (j->ssd_ticket)
    lie_store_cancel(w->store, j->ssd_ticket);
  set_output_blocked(w, j, false);
  /* Detach under the cancellation gate. An external latch call cannot race
   * sequence destruction; no backend work runs while holding this gate. */
  pthread_mutex_lock(&j->gate);
  if(w->steering_path)j->info.finish=finish; /* Refuse controls once retirement begins. */
  if(j->steering.pending){
    j->steering.pending=false;j->steering.completed=j->steering.submitted;
    j->steering.status=finish==LIE_FINISH_BACKEND?LIE_BACKEND_FAILED:LIE_CANCELLED;
    snprintf(j->steering.error,sizeof(j->steering.error),"job retired before steering change applied");
  }
  if(j->schedule){
    j->schedule->terminal=true;
    for(size_t i=j->schedule->completed;i<j->schedule->count;++i)
      j->schedule->results[i].status=finish==LIE_FINISH_BACKEND?LIE_BACKEND_FAILED:LIE_CANCELLED;
  }
  lie_sequence *sequence = j->sequence;
  j->sequence = NULL;
  pthread_mutex_unlock(&j->gate);
  if (sequence) {
    if (finish == LIE_FINISH_CANCEL)
      lie_sequence_cancel(sequence);
    (void)lie_sequence_close(&sequence, &error);
    pthread_mutex_lock(&w->gate);
    --w->info.active;
    pthread_mutex_unlock(&w->gate);
  } else {
    pthread_mutex_lock(&w->gate);
    --w->info.queued;
    pthread_mutex_unlock(&w->gate);
  }
  /* Keep immutable physical input/output witnesses until the last consumer
   * reference; protocol/parser storage never belonged to this job. */
  /* Input policy remains immutable until the last consumer releases the job:
   * semantic events can be validated after the device owner retires. */
  free(j->rendered);
  j->rendered = NULL;
  j->rendered_bytes = j->rendered_capacity = 0;
  free(j->text_offsets);
  j->text_offsets = NULL;
  free(j->reporting_logits);
  j->reporting_logits = NULL;
  pthread_mutex_lock(&j->gate);
  j->info.finish = finish;
  j->info.retired = true;
  if (message)
    snprintf(j->info.error, sizeof(j->info.error), "%s", message);
  pthread_mutex_unlock(&j->gate);
  if (finish == LIE_FINISH_CANCEL)
    (void)lie_flow_cancel(j->flow);
  else if (finish == LIE_FINISH_INVALID || finish == LIE_FINISH_BACKEND)
    (void)lie_flow_fail(j->flow, (int)finish);
  else
    (void)lie_flow_finish(j->flow);
  /* Cancellation can expose a raw terminal during prefill. Semantic clients
   * wait for retired metadata and must be woken after numerical retirement. */
  signal_fd(lie_flow_fd(j->flow, LIE_FLOW_OUTPUT_READY));
  pthread_mutex_lock(&w->gate);
  w->jobs[index] = NULL;
  if (finish == LIE_FINISH_STOP || finish == LIE_FINISH_LENGTH)
    ++w->info.completed_requests;
  else if (finish == LIE_FINISH_CANCEL)
    ++w->info.cancelled_requests;
  else
    ++w->info.failed_requests;
  pthread_mutex_unlock(&w->gate);
  signal_fd(w->notice);
  job_drop(j); /* No access to j after retiring the worker reference. */
}
static void poison(lie_core *w, const lie_error *error) {
    pthread_mutex_lock(&w->gate);
    w->info.state=LIE_FAILED;
    snprintf(w->info.error,sizeof(w->info.error),"%s",error->message);
    pthread_mutex_unlock(&w->gate); signal_fd(w->notice);
}
static lie_status steering_apply(lie_job *j,lie_error *e){
    if(!j->owner->steering_path)return LIE_OK;
    pthread_mutex_lock(&j->gate);bool pending=j->steering.pending;
    lie_steering_settings settings=j->steering.requested;uint64_t ticket=j->steering.submitted;
    pthread_mutex_unlock(&j->gate);if(!pending)return LIE_OK;
    lie_status rc=lie_sequence_change_steering(j->sequence,&settings,e);
    if(rc==LIE_OK&&steering_refresh(j,e)!=LIE_OK)rc=LIE_BACKEND_FAILED;
    if(rc==LIE_OK&&(j->steering.policy.settings.ffn!=settings.ffn||j->steering.policy.settings.attention!=settings.attention)){
      rc=LIE_BACKEND_FAILED;if(e)snprintf(e->message,sizeof(e->message),"steering change did not confirm requested scales");
    }
    pthread_mutex_lock(&j->gate);
    j->steering.pending=false;j->steering.completed=ticket;j->steering.status=rc;
    if(rc==LIE_OK)j->steering.applied_position=j->position;
    snprintf(j->steering.error,sizeof(j->steering.error),"%s",rc!=LIE_OK&&e?e->message:"");
    pthread_mutex_unlock(&j->gate);
    signal_fd(j->owner->notice);signal_fd(lie_flow_fd(j->flow,LIE_FLOW_OUTPUT_READY));
    /* Pure refusal leaves this job usable. A mutating provider failure is
     * fatal to the shared model and is propagated to the owner below. */
    return rc==LIE_BACKEND_FAILED?rc:LIE_OK;
}
static uint64_t steering_boundary(const lie_job *j){
    return j->schedule&&j->schedule->completed<j->schedule->count?
           j->schedule->steps[j->schedule->completed].position:UINT64_MAX;
}
/* Existing owner only. A plan is fixed before publication; no client polling
 * decides where a change occurs, and no speculative burst may cross it. */
static lie_status steering_schedule_apply(lie_job *j,lie_error *e){
    uint64_t boundary=steering_boundary(j);
    if(boundary>j->position)return LIE_OK;
    if(boundary<j->position){
      if(e)snprintf(e->message,sizeof(e->message),"steering schedule boundary %llu crossed at %u",(unsigned long long)boundary,j->position);
      return LIE_BACKEND_FAILED;
    }
    size_t index=j->schedule->completed;
    lie_status rc=lie_sequence_change_steering(j->sequence,&j->schedule->steps[index].settings,e);
    if(rc==LIE_OK&&steering_refresh(j,e)!=LIE_OK)rc=LIE_BACKEND_FAILED;
    if(rc==LIE_OK&&(j->steering.policy.settings.ffn!=j->schedule->steps[index].settings.ffn||
       j->steering.policy.settings.attention!=j->schedule->steps[index].settings.attention)){
      rc=LIE_BACKEND_FAILED;if(e)snprintf(e->message,sizeof(e->message),"steering schedule did not confirm requested scales");
    }
    pthread_mutex_lock(&j->gate);
    j->schedule->results[index]=(lie_steering_step_result){true,rc==LIE_OK,rc,j->position};
    ++j->schedule->completed;if(rc==LIE_OK)++j->schedule->applied;
    pthread_mutex_unlock(&j->gate);
    signal_fd(j->owner->notice);
    return rc;
}
static size_t steering_restore_limit(const lie_job *j){
    uint64_t boundary=steering_boundary(j);
    return boundary<j->tokens?(size_t)boundary:j->tokens;
}
static lie_status cache_step(lie_core *w,lie_job *j,bool restore,lie_cache_reason reason,lie_error *error) {
    if(!restore){lie_status checked=steering_refresh(j,error);if(checked!=LIE_OK)return checked;}
    size_t frontier=restore?j->tokens:j->position;
    int32_t *owned=NULL;const int32_t *tokens=j->prompt;
    if(!restore&&frontier>j->tokens){
        if(frontier-j->tokens>j->info.output_tokens)return LIE_INVALID;
        owned=malloc(frontier*sizeof(*owned));if(!owned)return LIE_OK;
        memcpy(owned,j->prompt,j->tokens*sizeof(*owned));memcpy(owned+j->tokens,j->output_ids,(frontier-j->tokens)*sizeof(*owned));tokens=owned;
    }
    lie_cache_metadata metadata={.reason=reason,.flags=j->request.cache.flags&~6u,.trailer=j->request.cache.trailer,.trailer_bytes=j->request.cache.trailer_bytes};
    if(j->text_complete&&j->text_offsets&&frontier<=w->options.context){metadata.text=j->rendered;metadata.text_bytes=j->text_offsets[frontier];}
    if(frontier==j->tokens&&j->request.cache.text_bytes){metadata.text=j->request.cache.text;metadata.text_bytes=j->request.cache.text_bytes;metadata.flags=j->request.cache.flags;}
    if(restore&&j->text_lookup){const lie_cache_metadata *m=NULL;
        size_t key_bytes;const char *key=lookup_text(j,&key_bytes);
        lie_state *candidate=lie_prefix_cache_match_text_scope(&w->cache,key,key_bytes,j->request.cache.flags,j->cache_scope,&m);
        if(candidate)(void)rebuild_prompt(w,j,candidate,m);
        tokens=j->prompt;
    }
    pthread_mutex_lock(&w->gate);
    w->dispatch=j;j->executing=true;
    w->info.executor_phase=restore?LIE_EXECUTOR_RESTORE:LIE_EXECUTOR_CAPTURE;
    pthread_mutex_unlock(&w->gate);
    uint64_t start=0,end=0;bool a=clock_ns(&start);unsigned reused=0;
    lie_status rc=restore?lie_prefix_cache_restore_scope(&w->cache,j->sequence,j->prompt,steering_restore_limit(j),w->options.cache_policy.enabled?1:w->options.chunk,j->request.cache.flags,j->cache_scope,&reused,error):
        lie_prefix_cache_capture_scope(&w->cache,j->sequence,tokens,frontier,w->options.cache_policy.enabled?&metadata:NULL,
                                        w->options.cache_policy.enabled&&frontier>j->tokens?j->tokens:0,j->request.cache.flags,j->cache_scope,error);
    if(!restore&&rc==LIE_OK&&w->store){
        lie_state *state=lie_prefix_cache_find_scope(&w->cache,tokens,frontier,j->cache_scope),*temporary=NULL;
        if(!state){lie_state_layout layout;uint64_t bytes=0;
            rc=lie_state_plan(j->sequence,&layout,&bytes,error);
            if(rc==LIE_OK&&layout.token_count!=frontier){rc=LIE_BACKEND_FAILED;snprintf(error->message,sizeof(error->message),"SSD capture token frontier mismatch");}
            if(rc==LIE_OK&&lie_store_can_write(w->store,bytes)){
                rc=lie_state_capture(j->sequence,&layout,w->options.ssd.staging_bytes,&temporary,error);
                if(rc==LIE_RESOURCE_LIMIT)rc=LIE_OK;
                if(temporary&&(!lie_state_scope_equal(temporary,j->cache_scope)||memcmp(lie_state_tokens(temporary),tokens,frontier*sizeof(*tokens)))){
                    lie_state_destroy(&temporary);rc=LIE_BACKEND_FAILED;snprintf(error->message,sizeof(error->message),"SSD capture token contents mismatch");}
                if(temporary)(void)lie_state_compress(&temporary,w->options.ssd.staging_bytes);
                state=temporary;
            }
        }
        if(state)(void)lie_store_write_prompt(w->store,state,&metadata,
                                             w->options.cache_policy.enabled&&frontier>j->tokens?j->tokens:0,j->request.cache.flags);
        lie_state_destroy(&temporary);
    }
    bool b=clock_ns(&end);
    pthread_mutex_lock(&j->gate);
    if(!a||!b||end<start)j->info.timing_valid=false;
    else if(restore)j->info.cache_restore_ns=end-start;
    else j->info.cache_capture_ns+=end-start;
    if(restore&&rc==LIE_OK){j->fed=reused;j->position=reused;j->info.cached_tokens=reused;
        uint32_t interval=lie_cache_continued_step(&w->options.cache_policy);
        j->next_continued=interval?((reused/interval)+1)*(size_t)interval:0;
        lie_state *state=lie_prefix_cache_find_scope(&w->cache,j->prompt,reused,j->cache_scope);
        const lie_cache_metadata *m=lie_prefix_cache_record(&w->cache,state);
        if(m){lie_cache_metadata_clear(&j->restored_metadata);(void)lie_cache_metadata_copy(&j->restored_metadata,m);}
    }
    pthread_mutex_unlock(&j->gate);
    if(restore&&rc==LIE_OK)rc=steering_refresh(j,error);
    pthread_mutex_lock(&w->gate);
    w->info.cache=w->cache.info;w->info.executor_phase=LIE_EXECUTOR_IDLE;
    j->executing=false;w->dispatch=NULL;
    pthread_mutex_unlock(&w->gate);
    if(!restore&&rc==LIE_OK)j->last_capture=frontier;
    free(owned);return rc;
}
static bool ssd_collect(lie_core *w){
    lie_store_result result={0};if(!lie_store_take(w->store,&result))return false;
    lie_job *j=NULL;
    if(result.read){pthread_mutex_lock(&w->gate);
        for(unsigned i=0;i<LIE_CORE_JOBS;++i)if(w->jobs[i]&&w->jobs[i]->ssd_ticket==result.ticket){j=w->jobs[i];break;}
        pthread_mutex_unlock(&w->gate);
    }
    if(j){j->ssd_ticket=0;j->ssd_checked=true;
        pthread_mutex_lock(&j->gate);j->info.ssd_read_ns=result.read_ns;pthread_mutex_unlock(&j->gate);
    }
    if(j&&result.state&&!atomic_load(&j->cancel)&&!atomic_load(&w->stop)){
        lie_core_info info;lie_core_snapshot(w,&info);lie_error error={0};lie_state_layout expected;
        const lie_state_layout *layout=lie_state_description(result.state);
        /* Complete file validation precedes this model geometry check. Both
         * are nonmutating; only a compatible admitted upload is fatal on error. */
        bool text_ok=layout->token_count<=steering_restore_limit(j)&&lie_state_scope_equal(result.state,j->cache_scope)&&(!j->text_lookup||rebuild_prompt(w,j,result.state,&result.metadata));
        lie_status rc=info.state==LIE_READY&&text_ok?lie_sequence_state_describe(j->sequence,layout,&expected,&error):LIE_INVALID;
        if(rc==LIE_OK&&lie_state_layout_equal(layout,&expected)){
            pthread_mutex_lock(&w->gate);w->dispatch=j;j->executing=true;w->info.executor_phase=LIE_EXECUTOR_RESTORE;pthread_mutex_unlock(&w->gate);
            uint64_t start=0,end=0;bool a=clock_ns(&start);rc=lie_state_restore(j->sequence,result.state,&error);bool b=clock_ns(&end);
            pthread_mutex_lock(&j->gate);
            if(!a||!b||end<start||end-start>UINT64_MAX-j->info.cache_restore_ns)j->info.timing_valid=false;
            else j->info.cache_restore_ns+=end-start;
            if(rc==LIE_OK){j->fed=j->position=layout->token_count;j->info.cached_tokens=layout->token_count;
                j->info.ssd_cached_tokens=layout->token_count;
                uint32_t interval=lie_cache_continued_step(&w->options.cache_policy);
                j->next_continued=interval?((j->position/interval)+1)*(size_t)interval:0;
                lie_cache_metadata_clear(&j->restored_metadata);(void)lie_cache_metadata_copy(&j->restored_metadata,&result.metadata);
                if(j->fed>=j->checkpoint)j->capture_checked=true;}
            pthread_mutex_unlock(&j->gate);
            if(rc==LIE_OK)rc=steering_refresh(j,&error);
            pthread_mutex_lock(&w->gate);w->dispatch=NULL;j->executing=false;w->info.executor_phase=LIE_EXECUTOR_IDLE;pthread_mutex_unlock(&w->gate);
            if(rc==LIE_OK){lie_prefix_cache_insert(&w->cache,result.state);
                (void)lie_prefix_cache_metadata(&w->cache,result.state,&result.metadata);}
            else if(rc!=LIE_CANCELLED)poison(w,&error);
        }else if(rc!=LIE_OK&&rc!=LIE_INVALID&&rc!=LIE_UNSUPPORTED&&rc!=LIE_CANCELLED)poison(w,&error);
    }
    lie_store_result_release(w->store,&result);return true;
}
/* Mutate only the independently owned admission arena. Remove an entire old
 * turn so function results cannot outlive the corresponding assistant calls. */
static bool truncate_turn(lie_core_request *r) {
  size_t latest = SIZE_MAX, first = SIZE_MAX;
  for (size_t i = 0; i < r->chat.count; ++i) {
    if (r->chat.messages[i].role == LIE_CHAT_USER)
      latest = i;
    if (first == SIZE_MAX && r->chat.messages[i].role != LIE_CHAT_SYSTEM)
      first = i;
  }
  if (latest == SIZE_MAX)
    latest = r->chat.count - 1;
  if (first == SIZE_MAX || first >= latest)
    return false;
  size_t end = first + 1;
  while (end < latest && r->chat.messages[end].role != LIE_CHAT_USER)
    ++end;
  size_t map[LIE_CHAT_MAX_MESSAGES], count = 0;
  lie_chat_message *messages = (lie_chat_message *)r->chat.messages;
  lie_chat_details *details = (lie_chat_details *)r->chat.details;
  for (size_t i = 0; i < r->chat.count; ++i) {
    map[i] = SIZE_MAX;
    if (i >= first && i < end && messages[i].role != LIE_CHAT_SYSTEM)
      continue;
    map[i] = count;
    messages[count] = messages[i];
    details[count] = details[i];
    ++count;
  }
  lie_image_input *images = (lie_image_input *)r->images;
  size_t image_count = 0;
  for (size_t i = 0; i < r->image_count; ++i)
    if (map[images[i].message_index] != SIZE_MAX) {
      images[image_count] = images[i];
      images[image_count++].message_index = map[images[i].message_index];
    }
  r->chat.count = count;
  r->image_count = image_count;
  if (!image_count)
    r->images = NULL;
  return true;
}
static bool step(lie_core *w, size_t index) {
  lie_job *j = w->jobs[index];
  if (!j)
    return false;
  lie_error error = {0};
  lie_core_info wi;
  lie_core_snapshot(w, &wi);
  if (j->capture_pending && !atomic_load(&j->cancel) &&
      wi.state != LIE_FAILED) {
    lie_store_info store;
    lie_store_snapshot(w->store, &store);
    if (store.pending)
      return false;
    lie_cache_reason reason = j->capture_pending;
    j->capture_pending = LIE_CACHE_UNKNOWN;
    lie_status rc = cache_step(w, j, false, reason, &error);
    if (rc != LIE_OK && rc != LIE_CANCELLED) {
      poison(w, &error);
      finish_job(w, index, LIE_FINISH_BACKEND, error.message);
      return true;
    }
    if (j->finish_pending) {
      finish_job(w, index, j->info.finish, NULL);
      return true;
    }
    return true;
  }
  if (atomic_load(&w->stop) && !atomic_load(&j->cancel) && j->sequence &&
      !wi.error[0] && w->options.cache_policy.enabled &&
      w->options.cache_policy.capture_finish && !j->shutdown_saved &&
      (w->options.prefix_cache_bytes || w->store) && j->position &&
      j->position >= w->options.cache_policy.min_tokens) {
    j->shutdown_saved = true;
    j->capture_pending = LIE_CACHE_SHUTDOWN;
    return true;
  }
  if (atomic_load(&j->cancel) || atomic_load(&w->stop)) {
    finish_job(w, index, LIE_FINISH_CANCEL, "cancelled");
    return true;
  }
  if (wi.state == LIE_FAILED) {
    finish_job(w, index, LIE_FINISH_BACKEND, "backend_failed");
    return true;
  }
  if (!j->sequence) {
    if (wi.active >= w->options.max_active)
      return false;
    j->prompt = malloc((size_t)w->options.context * sizeof(*j->prompt));
    if (!j->prompt) {
      finish_job(w, index, LIE_FINISH_BACKEND, "allocation_failed");
      return true;
    }
    lie_core_request *r = &j->request;
    if (r->image_count) {
      uint64_t pixels = 0, bytes = 0;
      for (size_t k = 0; k < r->image_count; ++k) {
        lie_image_dimensions d;
        if (lie_image_inspect(&r->images[k], &d, &error) != LIE_OK ||
            !(wi.vision.format_mask & (1u << r->images[k].format))) {
          finish_job(w, index, LIE_FINISH_INVALID,
                     "unsupported image encoding");
          return true;
        }
        pixels += (uint64_t)d.width * d.height;
        bytes += r->images[k].bytes;
      }
      if (pixels > wi.vision.max_pixels ||
          bytes > wi.vision.max_encoded_bytes) {
        finish_job(w, index, LIE_FINISH_INVALID, "model image budget exceeded");
        return true;
      }
    }
    const lie_chat_tool *tools = r->chat.tools;
    size_t tool_count =
        r->tool_choice == LIE_TOOLS_NONE ? 0 : r->chat.tool_count;
    if (r->tool_choice == LIE_TOOLS_NAMED) {
      size_t k = 0;
      while (k < r->chat.tool_count &&
             strcmp(r->chat.tools[k].name, r->named_tool))
        ++k;
      if (k == r->chat.tool_count) {
        finish_job(w, index, LIE_FINISH_INVALID, "invalid_tool_choice");
        return true;
      }
      tools = &r->chat.tools[k];
      tool_count = 1;
    }
    lie_status rc = LIE_OK;
    lie_vision_prompt *vision = NULL;
    if (r->kind == LIE_INPUT_TOKENS) {
      j->tokens = r->token_count;
      if (j->tokens > w->options.context)
        rc = LIE_BUFFER_SMALL;
      else
        memcpy(j->prompt, r->tokens, j->tokens * sizeof(*j->prompt));
    } else if (r->kind == LIE_INPUT_TEXT) {
      rc = lie_model_tokenize(w->model, r->text, r->text_bytes, j->prompt,
                              w->options.context, &j->tokens, &error);
    } else {
      do {
        const lie_chat_template input = {r->chat.messages,
                                         r->chat.details,
                                         r->chat.count,
                                         tools,
                                         tool_count,
                                         r->tool_choice >= LIE_TOOLS_REQUIRED ||
                                             r->chat.require_tool_call};
        rc = r->image_count
                 ? lie_model_prepare_vision(
                       w->model, &input, r->images, r->image_count, j->prompt,
                       w->options.context, &j->tokens, &vision, &error)
                 : lie_model_chat_tokens_ex(w->model, &input, j->prompt,
                                            w->options.context, &j->tokens,
                                            &error);
        bool overflow =
            rc == LIE_BUFFER_SMALL ||
            (rc == LIE_OK &&
             (j->tokens >= w->options.context ||
              (!j->automatic_output &&
               r->max_tokens > w->options.context - j->tokens)));
        if (!overflow || !r->truncate_oldest)
          break;
        if (vision)
          (void)lie_vision_prompt_close(&vision, NULL);
        if (!truncate_turn(r))
          break;
        error = (lie_error){0};
      } while (true);
    }
    if (rc != LIE_OK || !j->tokens || j->tokens >= w->options.context ||
        (!j->automatic_output &&
         j->request.max_tokens > w->options.context - j->tokens)) {
      if (vision)
        (void)lie_vision_prompt_close(&vision, NULL);
      if (rc == LIE_BACKEND_FAILED)
        poison(w, &error);
      finish_job(
          w, index,
          rc == LIE_BACKEND_FAILED ? LIE_FINISH_BACKEND : LIE_FINISH_INVALID,
          rc == LIE_OK || rc == LIE_BUFFER_SMALL ? "context_budget_exceeded"
                                                 : error.message);
      return true;
    }
    if (j->automatic_output && j->output_limit > w->options.context - j->tokens)
      j->output_limit = (unsigned)(w->options.context - j->tokens);
    if(j->schedule&&j->schedule->steps[j->schedule->count-1].position>=j->tokens+j->output_limit){
      if(vision)(void)lie_vision_prompt_close(&vision,NULL);
      finish_job(w,index,LIE_FINISH_INVALID,"steering_schedule_outside_generation");return true;
    }
    for (size_t k = 0; k < j->tokens; ++k)
      if (j->prompt[k] < 0 || (uint32_t)j->prompt[k] >= wi.model.vocab_tokens) {
        if (vision)
          (void)lie_vision_prompt_close(&vision, NULL);
        finish_job(w, index, LIE_FINISH_INVALID, "invalid_prompt_token");
        return true;
      }
    lie_sequence *sequence = NULL;
    rc = lie_sequence_create(w->model, &sequence, &error);
    if (rc != LIE_OK) {
      if (vision)
        (void)lie_vision_prompt_close(&vision, NULL);
      if (rc == LIE_BACKEND_FAILED)
        poison(w, &error);
      finish_job(w, index, LIE_FINISH_BACKEND, error.message);
      return true;
    }
    rc = vision ? lie_vision_prompt_cache_scope(vision, j->semantic_scope, &error)
                : LIE_OK;
    memcpy(j->cache_scope,j->semantic_scope,32);
    if (rc == LIE_OK && vision)
      rc = lie_sequence_attach_vision(sequence, vision, &error);
    if (vision)
      (void)lie_vision_prompt_close(&vision, NULL);
    if (rc == LIE_OK && w->steering_path) {
      unsigned char combined[32];
      rc = lie_sequence_steering_cache_scope(sequence, j->semantic_scope, combined, &error);
      if (rc == LIE_OK) memcpy(j->cache_scope, combined, sizeof(combined));
    }
    if (rc == LIE_OK)
      rc = lie_sequence_configure(sequence, &j->request.generation, &error);
    if (rc == LIE_OK && r->eos_policy != LIE_EOS_STOP)
      rc = lie_sequence_set_eos_policy(sequence, r->eos_policy, &error);
    if (rc == LIE_OK) {
      lie_generation_constraints constraints = {
          .format = r->format,
          .schema_json = r->schema_json,
          .strict = r->strict,
          .required =
              r->tool_choice >= LIE_TOOLS_REQUIRED || r->chat.require_tool_call,
          .parallel = r->parallel_tool_calls};
      bool constrained = false;
      for (size_t t = 0; t < tool_count; ++t) {
        oj_node *def = oj_parse(tools[t].definition_json,
                                strlen(tools[t].definition_json));
        const oj_node *strict = oj_field(oj_field(def, "function"), "strict");
        constrained |= strict && strict->type == OJ_BOOL && strict->boolean;
        oj_free(def);
      }
      if (constrained) {
        constraints.tools = tools;
        constraints.tool_count = tool_count;
      }
      if (r->format != LIE_FORMAT_TEXT || constrained)
        rc = lie_sequence_constrain(sequence, &constraints, &error);
    }
    if (rc == LIE_OK && r->generation.logprobs) {
      j->reporting_logits =
          calloc(wi.model.vocab_tokens, sizeof(*j->reporting_logits));
      if (!j->reporting_logits) {
        rc = LIE_RESOURCE_LIMIT;
        snprintf(error.message, sizeof(error.message),
                 "logprob_allocation_failed");
      }
    }
    if (rc != LIE_OK) {
      lie_error close_error = {0};
      lie_status closed = lie_sequence_close(&sequence, &close_error);
      if (closed != LIE_OK || rc == LIE_BACKEND_FAILED)
        poison(w, closed != LIE_OK ? &close_error : &error);
      finish_job(w, index,
                 rc == LIE_BACKEND_FAILED || closed != LIE_OK
                     ? LIE_FINISH_BACKEND
                     : LIE_FINISH_INVALID,
                 error.message);
      return true;
    }
    pthread_mutex_lock(&w->gate);
    --w->info.queued;
    ++w->info.active;
    pthread_mutex_unlock(&w->gate);
    pthread_mutex_lock(&j->gate);
    j->sequence = sequence;
    if (atomic_load(&j->cancel))
      lie_sequence_cancel(sequence);
    j->info.prompt_tokens = (unsigned)j->tokens;
    j->info.output_token_limit = j->output_limit;
    j->info.prepared = true;
    checkpoint_targets(w, j);
    pthread_mutex_unlock(&j->gate);
    rc=steering_schedule_apply(j,&error);
    if(rc==LIE_OK)rc=steering_refresh(j,&error);
    if(rc!=LIE_OK){if(rc==LIE_BACKEND_FAILED)poison(w,&error);finish_job(w,index,rc==LIE_BACKEND_FAILED?LIE_FINISH_BACKEND:rc==LIE_CANCELLED?LIE_FINISH_CANCEL:LIE_FINISH_INVALID,error.message);return true;}
    if (w->store || ((w->options.prefix_cache_bytes || w->store) &&
                     w->options.cache_policy.enabled &&
                     w->options.cache_policy.text_prefix &&
                     j->request.kind != LIE_INPUT_TOKENS)) {
      j->text_complete = render_prompt(w, j);
      j->text_lookup = !j->schedule && !j->request.image_count &&
                       j->request.kind != LIE_INPUT_TOKENS &&
                       w->options.cache_policy.enabled &&
                       w->options.cache_policy.text_prefix &&
                       (j->text_complete || j->request.cache.text_bytes);
    }
    signal_fd(w->notice);
  }
  if (atomic_load(&j->cancel)) {
    finish_job(w, index, LIE_FINISH_CANCEL, "cancelled");
    return true;
  }
  if (w->options.prefix_cache_bytes && !j->cache_checked) {
    j->cache_checked = true;
    lie_status rc = cache_step(w, j, true, LIE_CACHE_UNKNOWN, &error);
    if (rc != LIE_OK) {
      if (rc != LIE_CANCELLED)
        poison(w, &error);
      finish_job(w, index,
                 rc == LIE_CANCELLED ? LIE_FINISH_CANCEL : LIE_FINISH_BACKEND,
                 error.message);
      return true;
    }
    if (j->fed >= j->checkpoint)
      j->capture_checked = true;
    if (atomic_load(&j->cancel)) {
      finish_job(w, index, LIE_FINISH_CANCEL, "cancelled");
      return true;
    }
  }
  if (w->store && !j->ssd_checked && !j->fed) {
    if (j->ssd_ticket)
      return false;
    size_t key_bytes;
    const char *key = lookup_text(j, &key_bytes);
    j->ssd_ticket =
        j->text_lookup
            ? lie_store_read_text_scoped_key(w->store, key, key_bytes,
                                      w->options.chunk, j->request.cache.flags,j->cache_scope)
            : lie_store_read_scoped_key(w->store, j->prompt, steering_restore_limit(j),
                                        w->options.chunk,
                                        j->request.cache.flags, j->cache_scope);
    if (j->ssd_ticket)
      return true;
    lie_store_info store;
    lie_store_snapshot(w->store, &store);
    if (store.pending)
      return false;        /* Other rows may still prefill/decode. */
    j->ssd_checked = true; /* Allocation/budget refusal before any mutation. */
  }
  if(steering_apply(j,&error)!=LIE_OK){
    poison(w,&error);finish_job(w,index,LIE_FINISH_BACKEND,error.message);return true;
  }
  lie_status planned=steering_schedule_apply(j,&error);
  if(planned!=LIE_OK){
    if(planned==LIE_BACKEND_FAILED)poison(w,&error);
    finish_job(w,index,planned==LIE_BACKEND_FAILED?LIE_FINISH_BACKEND:planned==LIE_CANCELLED?LIE_FINISH_CANCEL:LIE_FINISH_INVALID,error.message);return true;
  }
  if (j->fed < j->tokens) {
    size_t add = j->tokens - j->fed;
    if (add > w->options.chunk)
      add = w->options.chunk;
    uint64_t boundary=steering_boundary(j);
    if(boundary-j->fed<add)add=(size_t)(boundary-j->fed);
    if (w->options.cache_policy.enabled) {
      if (j->checkpoint > j->fed && j->checkpoint - j->fed < add)
        add = j->checkpoint - j->fed;
      if (j->next_continued > j->fed && j->next_continued - j->fed < add)
        add = j->next_continued - j->fed;
    }
    begin_call(w, j, true);
    uint64_t started = 0;
    bool started_ok = clock_ns(&started);
    lie_status rc =
        lie_sequence_prefill(j->sequence, j->prompt, j->fed + add, &error);
    record_call(j, true, started_ok, started, rc == LIE_OK ? (unsigned)add : 0);
    if (rc != LIE_OK) {
      if (rc != LIE_CANCELLED) {
        if (!error.message[0])
          snprintf(error.message, sizeof(error.message),
                   "executor_prefill_failed");
        poison(w, &error);
      }
      finish_job(w, index,
                 rc == LIE_CANCELLED ? LIE_FINISH_CANCEL : LIE_FINISH_BACKEND,
                 error.message);
    } else {
      j->fed += add;
      j->position = (uint32_t)j->fed;
      rc=steering_refresh(j,&error);
      if(rc!=LIE_OK){poison(w,&error);finish_job(w,index,LIE_FINISH_BACKEND,error.message);return true;}
      bool cold =
          !j->capture_checked && j->checkpoint && j->fed == j->checkpoint;
      bool continued = j->next_continued && j->fed == j->next_continued;
      /* Preserve a repeatable input frontier before decode extends the
       * recurrent state beyond it. No rewind or additional prefill. */
      bool prompt = w->options.cache_policy.enabled && j->fed == j->tokens;
      if (continued)
        j->next_continued += lie_cache_continued_step(&w->options.cache_policy);
      if ((w->options.prefix_cache_bytes || w->store) &&
          (cold || continued || prompt) &&
          (!w->options.cache_policy.enabled ||
           j->fed >= w->options.cache_policy.min_tokens)) {
        if (cold)
          j->capture_checked = true;
        lie_store_info store;
        lie_store_snapshot(w->store, &store);
        if (store.pending)
          j->capture_pending = cold ? LIE_CACHE_COLD : LIE_CACHE_CONTINUED;
        else
          rc = cache_step(w, j, false,
                          cold ? LIE_CACHE_COLD : LIE_CACHE_CONTINUED, &error);
        if (rc != LIE_OK) {
          if (rc != LIE_CANCELLED)
            poison(w, &error);
          finish_job(w, index,
                     rc == LIE_CANCELLED ? LIE_FINISH_CANCEL
                                         : LIE_FINISH_BACKEND,
                     error.message);
        }
      }
    }
    return true;
  }
  return false; /* Prefilled rows enter the shared inference dispatcher below.
                 */
}
static bool decode_ready(lie_core *w) {
  lie_inference_row rows[LIE_CORE_JOBS] = {0};
  size_t indices[LIE_CORE_JOBS], n = 0;
  lie_core_info wi;
  lie_core_snapshot(w, &wi);
  if (wi.state != LIE_READY)
    return false;
  for (size_t i = 0; i < LIE_CORE_JOBS; ++i) {
    pthread_mutex_lock(&w->gate);
    lie_job *j = w->jobs[i];
    pthread_mutex_unlock(&w->gate);
    if (j && j->sequence && j->fed == j->tokens && !j->capture_pending &&
        !j->finish_pending && steering_boundary(j)>j->position && !atomic_load(&j->cancel) &&
        !atomic_load(&w->stop)) {
      indices[n] = i;
      rows[n] = (lie_inference_row){
          .sequence = j->sequence,
          .flow = j->flow,
          .position = j->position,
          .context = w->options.context,
          .vocab = wi.model.vocab_tokens,
          .step_tokens =
              wi.model.speculative_supported && !j->request.stop_count &&
                      !j->request.generation.logprobs &&
                      !j->request.generation.logit_bias_count
                  ? (j->output_limit - j->info.output_tokens <
                             wi.mtp.max_output_tokens
                         ? j->output_limit - j->info.output_tokens
                         : wi.mtp.max_output_tokens)
                  : 1};
      uint64_t boundary=steering_boundary(j);
      if(boundary-j->position<rows[n].step_tokens)rows[n].step_tokens=(uint32_t)(boundary-j->position);
      ++n;
    }
  }
  if (!n)
    return false;
  lie_inference_batch batch = {0};
  lie_error error = {0};
  lie_status rc = lie_inference_prepare(rows, n, wi.model.native_batch_capacity,
                                        &batch, &error);
  for (size_t i = 0; i < n; ++i)
    set_output_blocked(w, w->jobs[indices[i]], rows[i].blocked);
  if (rc == LIE_OK && batch.selected) {
    for (size_t i = 0; i < n && rc == LIE_OK; ++i) {
      if (rows[i].selected) {
        lie_job *j = w->jobs[indices[i]];
        if (j->request.generation.logprobs) {
          size_t needed = 0;
          rc = lie_sequence_sampling_logits(j->sequence, j->reporting_logits,
                                            wi.model.vocab_tokens, &needed,
                                            &error);
          if (rc == LIE_OK &&
              (needed != wi.model.vocab_tokens ||
               !lie_logprob_row(j->reporting_logits, needed,
                                j->request.generation.top_logprobs,
                                j->scores + j->info.output_tokens))) {
            rc = LIE_BACKEND_FAILED;
            snprintf(error.message, sizeof(error.message),
                     "invalid_target_reporting_logits");
          }
        }
      }
    }
    pthread_mutex_lock(&w->gate);
    w->info.executor_phase = LIE_EXECUTOR_DECODE;
    ++w->info.decode_started;
    if (batch.selected > 1) {
      ++w->info.decode_batches;
      w->info.decode_batch_rows += batch.selected;
    } else
      ++w->info.decode_single_calls;
    for (size_t i = 0; i < n; ++i)
      if (rows[i].selected)
        w->jobs[indices[i]]->executing = true;
    pthread_mutex_unlock(&w->gate);
    uint64_t started = 0, ended = 0;
    bool a = clock_ns(&started);
    if (rc == LIE_OK)
      rc = lie_inference_run(&batch, &error);
    bool b = clock_ns(&ended);
    /* A shared call's duration is attributed to every participating row.
     * These per-request durations overlap; never sum them as GPU elapsed. */
    for (size_t i = 0; i < n; ++i)
      if (rows[i].selected) {
        lie_job *j = w->jobs[indices[i]];
        pthread_mutex_lock(&j->gate);
        ++j->info.decode_calls;
        if (!a || !b || ended < started ||
            ended - started > UINT64_MAX - j->info.decode_ns)
          j->info.timing_valid = false;
        else
          j->info.decode_ns += ended - started;
        pthread_mutex_unlock(&j->gate);
      }
    pthread_mutex_lock(&w->gate);
    ++w->info.decode_returned;
    w->info.executor_phase = LIE_EXECUTOR_IDLE;
    for (size_t i = 0; i < n; ++i)
      if (rows[i].selected)
        w->jobs[indices[i]]->executing = false;
    pthread_mutex_unlock(&w->gate);
  }
  size_t bytes[LIE_CORE_JOBS] = {0}, original_bytes[LIE_CORE_JOBS] = {0};
  char original[LIE_CORE_JOBS][LIE_CORE_TOKEN_BYTES];
  for(size_t i=0;w->steering_path&&i<n&&rc==LIE_OK;++i)if(rows[i].selected&&rows[i].outcome.status==LIE_OK){
    lie_job *j=w->jobs[indices[i]];j->position=rows[i].outcome.result.position;
    rc=steering_refresh(j,&error);
  }
  /* Validate all rows before exposing any output from a shared call. */
  for (size_t i = 0; i < n && rc == LIE_OK; ++i)
    if (rows[i].selected && rows[i].outcome.status == LIE_OK &&
        rows[i].outcome.result.emitted) {
      lie_inference_row *r = &rows[i];
      for (size_t t = 0; t < r->burst.emitted && rc == LIE_OK; ++t) {
        size_t part = 0;
        rc = lie_model_token_text(w->model, r->burst.tokens[t],
                                  (char *)r->reservation.data + bytes[i],
                                  r->reservation.capacity - bytes[i], &part,
                                  &error);
        if (rc == LIE_OK && (part > r->reservation.capacity - bytes[i] ||
                             part > LIE_CORE_TOKEN_BYTES)) {
          snprintf(error.message, sizeof(error.message),
                   "invalid_token_text_size");
          rc = LIE_BACKEND_FAILED;
        }
        if (rc == LIE_OK)
          bytes[i] += part;
      }
    }
  for (size_t i = 0; i < n && rc == LIE_OK; ++i)
    if (rows[i].selected && rows[i].outcome.status == LIE_OK) {
      lie_job *j = w->jobs[indices[i]];
      lie_decode_result *d = &rows[i].outcome.result;
      if (j->request.eos_policy == LIE_EOS_IGNORE && d->stop) {
        rc = LIE_BACKEND_FAILED;
        snprintf(error.message, sizeof(error.message), "executor_violated_eos_policy");
        break;
      }
      if (j->scores && d->emitted) {
        lie_token_logprobs *score = j->scores + j->info.output_tokens;
        score->token.token = d->token;
        score->token.logprob =
            isfinite(j->reporting_logits[d->token])
                ? j->reporting_logits[d->token] - score->token.logprob
                : -9999.0;
        rc = lie_model_token_text(w->model, d->token, score->token.text,
                                  sizeof(score->token.text),
                                  &score->token.bytes, &error);
        j->score_offsets[j->info.output_tokens] = j->scored_bytes;
        j->scored_bytes += score->token.bytes;
        for (unsigned k = 0; k < score->top_count && rc == LIE_OK; ++k)
          rc = lie_model_token_text(
              w->model, score->top[k].token, score->top[k].text,
              sizeof(score->top[k].text), &score->top[k].bytes, &error);
      }
      original_bytes[i] = bytes[i];
      if (j->request.stop_count && bytes[i])
        memcpy(original[i], rows[i].reservation.data, bytes[i]);
      bool end = d->stop ||
                 j->info.output_tokens + d->emitted >= j->output_limit;
      if (rc == LIE_OK &&
          !lie_stop_feed(&j->stop, &j->request,
                         (char *)rows[i].reservation.data, &bytes[i],
                         rows[i].reservation.capacity, end)) {
        rc = LIE_BACKEND_FAILED;
        snprintf(error.message, sizeof(error.message), "stop_filter_capacity");
      }
      if (j->stop.matched)
        d->stop = 1;
    }
  if (rc != LIE_OK) {
    if (!error.message[0])
      snprintf(error.message, sizeof(error.message),
               "executor_dispatch_failed");
    poison(w, &error);
  }
  bool progress = batch.selected > 0;
  for (size_t i = 0; i < n; ++i) {
    lie_inference_row *r = &rows[i];
    lie_job *j = w->jobs[indices[i]];
    if (rc != LIE_OK) {
      publish_outcome(j, LIE_FINISH_BACKEND, error.message);
      if (r->reserved)
        (void)lie_flow_abort(j->flow, r->reservation.ticket,
                             LIE_FINISH_BACKEND);
      finish_job(w, indices[i], LIE_FINISH_BACKEND, error.message);
      progress = true;
      continue;
    }
    if (r->outcome.status == LIE_CANCELLED || atomic_load(&j->cancel)) {
      publish_outcome(j, LIE_FINISH_CANCEL, "cancelled");
      (void)lie_flow_cancel(j->flow);
      if (r->reserved)
        (void)lie_flow_abort(j->flow, r->reservation.ticket, LIE_FINISH_CANCEL);
      finish_job(w, indices[i], LIE_FINISH_CANCEL, "cancelled");
      progress = true;
      continue;
    }
    if (!r->selected)
      continue;
    lie_decode_result d = r->outcome.result;
    j->position = d.position;
    pthread_mutex_lock(&j->gate);
    j->visible_bytes += bytes[i];
    for (size_t t = 0; t < d.emitted; ++t)
      j->output_ids[j->info.output_tokens + t] = r->burst.tokens[t];
    j->info.mtp_drafted += r->burst.drafted;
    j->info.mtp_accepted += r->burst.accepted;
    j->info.output_tokens += d.emitted;
    bool end = d.stop || j->info.output_tokens >= j->output_limit;
    if (end)
      j->info.finish = d.stop ? LIE_FINISH_STOP : LIE_FINISH_LENGTH;
    pthread_mutex_unlock(&j->gate);
    pthread_mutex_lock(&w->gate);
    w->info.generated_tokens += d.emitted;
    w->info.mtp_drafted += r->burst.drafted;
    w->info.mtp_accepted += r->burst.accepted;
    pthread_mutex_unlock(&w->gate);
    if (j->text_complete && j->text_offsets && d.emitted) {
      if (!append_text(j,
                       j->request.stop_count
                           ? original[i]
                           : (const char *)r->reservation.data,
                       original_bytes[i])) {
        j->text_lookup = false;
        j->text_complete = false;
      } else
        j->text_offsets[j->position] = j->rendered_bytes;
    }
    if (w->options.cache_policy.enabled &&
        (w->options.prefix_cache_bytes || w->store) &&
        j->position >= w->options.cache_policy.min_tokens &&
        j->position != j->last_capture &&
        ((j->next_continued && j->position >= j->next_continued) ||
         (end && w->options.cache_policy.capture_finish))) {
      lie_store_info store;
      lie_store_snapshot(w->store, &store);
      lie_status saved = LIE_OK;
      if (store.pending) {
        j->capture_pending = end ? LIE_CACHE_EVICT : LIE_CACHE_CONTINUED;
        j->finish_pending = end;
      } else
        saved = cache_step(w, j, false,
                           end ? LIE_CACHE_EVICT : LIE_CACHE_CONTINUED, &error);
      uint32_t interval = lie_cache_continued_step(&w->options.cache_policy);
      j->next_continued =
          interval ? ((j->position / interval) + 1) * (size_t)interval : 0;
      if (saved != LIE_OK && saved != LIE_CANCELLED) {
        poison(w, &error);
        publish_outcome(j, LIE_FINISH_BACKEND, error.message);
        (void)lie_flow_abort(j->flow, r->reservation.ticket,
                             LIE_FINISH_BACKEND);
        finish_job(w, indices[i], LIE_FINISH_BACKEND, error.message);
        continue;
      }
    }
    /* The legacy raw flow can close at EOS. Semantic TURN_END additionally
     * waits for finish_job to retire the sequence and cache work. */
    lie_flow_status f = lie_flow_commit(j->flow, r->reservation.ticket,
                                        bytes[i], d.emitted, end);
    if (f != LIE_FLOW_OK && f != LIE_FLOW_CLOSED)
      abort();
    if (f == LIE_FLOW_CLOSED || atomic_load(&j->cancel))
      finish_job(w, indices[i], LIE_FINISH_CANCEL, "cancelled");
    else if (end && !j->finish_pending)
      finish_job(w, indices[i], d.stop ? LIE_FINISH_STOP : LIE_FINISH_LENGTH,
                 NULL);
  }
  return progress;
}
static void *work(void *arg) {
    lie_core *w=arg; lie_error error={0};
    lie_model_options options={LIE_EXECUTOR_ABI,sizeof(options),w->options.context,w->options.chunk,w->options.rope_profile};
    lie_model_info model={0};lie_mtp_info mtp={.abi_version=LIE_MTP_ABI,.struct_bytes=sizeof(mtp)};
    lie_vision_info vision={.abi_version=LIE_VISION_ABI,.struct_bytes=sizeof(vision)};
    lie_steering_model_info steering={.abi_version=LIE_STEERING_MODEL_ABI,.struct_bytes=sizeof(steering)};
    steering.bank.abi_version=LIE_STEERING_ABI;steering.bank.struct_bytes=sizeof(steering.bank);
    lie_steering_settings_init(&steering.defaults,false);
    steering.prefix_state_supported=lie_backend_prefix_state_supported()!=0;
    lie_status rc=w->steering_path?
        lie_backend_open_steered(w->path,&options,w->options.max_active,w->mtp_path,w->options.mtp_draft_tokens,w->vision_path,&w->steering_options,&w->model,&error):
        w->mtp_path&&w->vision_path?
        lie_backend_open_mtp_vision(w->path,&options,w->options.max_active,w->mtp_path,w->options.mtp_draft_tokens,w->vision_path,&w->model,&error):
        w->vision_path?lie_backend_open_vision(w->path,&options,w->options.max_active,w->vision_path,&w->model,&error):
        w->mtp_path?lie_backend_open_mtp(w->path,&options,w->options.max_active,w->mtp_path,w->options.mtp_draft_tokens,&w->model,&error):
        lie_backend_open_batch(w->path,&options,w->options.max_active,&w->model,&error);
    if (rc==LIE_OK) rc=lie_model_get_info(w->model,&model,&error);
    if(rc==LIE_OK&&w->steering_path){
        rc=lie_model_steering_info(w->model,&steering,&error);
        uint64_t elements=(uint64_t)steering.bank.layers*steering.bank.width;
        if(rc==LIE_OK&&(steering.abi_version!=LIE_STEERING_MODEL_ABI||steering.struct_bytes!=sizeof(steering)||
           !steering.admitted||steering.bank.abi_version!=LIE_STEERING_ABI||steering.bank.struct_bytes!=sizeof(steering.bank)||
           !elements||elements>UINT64_MAX/4||steering.bank.bytes!=elements*4||
           steering.bank.bytes>w->steering_options.vector_budget_bytes||
           steering.defaults.abi_version!=LIE_STEERING_POLICY_ABI||steering.defaults.struct_bytes!=sizeof(steering.defaults)||
           steering.defaults.ffn!=w->steering_options.defaults.ffn||steering.defaults.attention!=w->steering_options.defaults.attention)){
            rc=LIE_BACKEND_FAILED;snprintf(error.message,sizeof(error.message),"invalid admitted steering capabilities");}
    }
    if(rc==LIE_OK&&w->steering_path&&(w->options.prefix_cache_bytes||w->options.ssd.directory)&&!steering.prefix_state_supported){
        rc=LIE_UNSUPPORTED;snprintf(error.message,sizeof(error.message),"admitted steering model has no complete prefix-state support; rebuild with state access or explicitly disable prefix caches");
    }
    if(rc==LIE_OK&&w->mtp_path){
        rc=lie_model_mtp_info(w->model,&mtp,&error);
        if(rc==LIE_OK&&(!model.speculative_supported||mtp.abi_version!=LIE_MTP_ABI||mtp.struct_bytes!=sizeof(mtp)||
           !mtp.max_draft_tokens||!mtp.max_output_tokens||mtp.max_output_tokens>LIE_MTP_MAX_OUTPUT)){
            rc=LIE_BACKEND_FAILED;snprintf(error.message,sizeof(error.message),"invalid admitted MTP capabilities");}
    }
    if(rc==LIE_OK&&w->vision_path){
        rc=lie_model_vision_info(w->model,&vision,&error);
        if(rc==LIE_OK&&(vision.abi_version!=LIE_VISION_ABI||vision.struct_bytes!=sizeof(vision)||
           !vision.max_images||vision.max_images>LIE_VISION_MAX_IMAGES||!vision.max_pixels||
           vision.max_pixels>LIE_VISION_MAX_PIXELS||!vision.max_encoded_bytes||
           vision.max_encoded_bytes>LIE_VISION_MAX_BYTES||!(vision.format_mask&6u))){
            rc=LIE_BACKEND_FAILED;snprintf(error.message,sizeof(error.message),"invalid admitted vision capabilities");}
    }
    if(rc==LIE_OK&&w->vision_path&&(w->options.prefix_cache_bytes||w->options.ssd.directory)&&!vision.prefix_state_supported){
        rc=LIE_UNSUPPORTED;snprintf(error.message,sizeof(error.message),"admitted vision model has no complete prefix-state support (semantic prefix state); rebuild with image state access or explicitly disable prefix caches");
    }
    if(rc==LIE_OK&&(w->options.prefix_cache_bytes||w->options.ssd.directory)&&!lie_backend_prefix_state_supported()){
        rc=LIE_UNSUPPORTED;snprintf(error.message,sizeof(error.message),"provider has no component-state support; rebuild with state access or explicitly disable prefix caches");
    }
    if(rc==LIE_OK&&w->mtp_path&&(w->options.prefix_cache_bytes||w->options.ssd.directory)&&!mtp.prefix_state_supported){
        rc=LIE_UNSUPPORTED;snprintf(error.message,sizeof(error.message),"admitted MTP model has no complete prefix-state support; rebuild with predictor state access or explicitly disable prefix caches");
    }
    if(rc==LIE_OK&&w->options.ssd.directory){
        lie_state_identity identity;uint64_t domain=0;
        rc=lie_model_state_identity(w->model,&identity,&domain,&error);
        if(rc==LIE_OK&&!atomic_load(&w->stop))rc=lie_store_open(&w->options.ssd,&identity,domain,&w->store,&error);
    }
    lie_store_info initial_store;lie_store_snapshot(w->store,&initial_store);
    pthread_mutex_lock(&w->gate);
    w->info.model=model;w->info.mtp=mtp;w->info.vision=vision;
    w->steering_info=steering;
    w->info.ssd=initial_store;
    w->info.state=atomic_load(&w->stop)?LIE_STOPPING:rc==LIE_OK?LIE_READY:LIE_FAILED;
    if (rc!=LIE_OK) snprintf(w->info.error,sizeof(w->info.error),"%s",error.message);
    pthread_mutex_unlock(&w->gate); signal_fd(w->notice);
    for (;;) {
        bool progress=ssd_collect(w); size_t present=0;
        for (size_t i=0;i<LIE_CORE_JOBS;++i) {
            /* Only the worker removes slots; producer publication is under gate. */
            pthread_mutex_lock(&w->gate); bool has=w->jobs[i]!=NULL; pthread_mutex_unlock(&w->gate);
            if (has) { ++present; progress=step(w,i) || progress; }
        }
        progress=decode_ready(w) || progress;
        lie_store_info store;lie_store_snapshot(w->store,&store);
        pthread_mutex_lock(&w->gate);w->info.ssd=store;w->info.cache=w->cache.info;pthread_mutex_unlock(&w->gate);
        if (atomic_load(&w->stop) && !present && !store.pending) break;
        if (progress) continue;
        struct pollfd fds[LIE_CORE_JOBS+2]; size_t count=1;
        fds[0]=(struct pollfd){w->wake,POLLIN,0};
        if(w->store)fds[count++]=(struct pollfd){lie_store_fd(w->store),POLLIN,0};
        pthread_mutex_lock(&w->gate);
        for (size_t i=0;i<LIE_CORE_JOBS;++i) if (w->jobs[i]) {
            fds[count++]=(struct pollfd){lie_flow_fd(w->jobs[i]->flow,LIE_FLOW_WORK_READY),POLLIN,0};
        }
        pthread_mutex_unlock(&w->gate);
        int result; do { result=poll(fds,count,-1); } while (result<0 && errno==EINTR);
        if (result<0) abort();
        for (size_t i=0;i<count;++i) if ((fds[i].revents&POLLIN)&&fds[i].fd!=lie_store_fd(w->store)) drain_fd(fds[i].fd);
    }
    /* Drain the bounded independent writer before reporting STOPPED. */
    lie_store_close(&w->store);
    lie_prefix_cache_clear(&w->cache);
    if (w->model) (void)lie_model_close(&w->model,&error);
    pthread_mutex_lock(&w->gate); w->info.cache=w->cache.info;w->info.state=LIE_STOPPED; pthread_mutex_unlock(&w->gate);
    signal_fd(w->notice); return NULL;
}
void lie_core_options_init(lie_core_options *o){
    if(o){*o=(lie_core_options){.context=4096,.chunk=2048,.max_active=1,.mtp_draft_tokens=0,.prefix_cache_bytes=LIE_PREFIX_CACHE_DEFAULT_BYTES};
        lie_cache_policy_init(&o->cache_policy);o->cache_policy.enabled=LIE_DS4_CACHE_POLICY!=0;}
}
lie_core *lie_core_create_steered(const lie_core_options *o,const lie_steering_model_options *steering) {
    if (!o || !o->model_path || !*o->model_path || o->context<128 || o->context>LIE_CORE_MAX_CONTEXT ||
        !o->chunk || o->chunk>2048 || !o->max_active || o->max_active>LIE_DECODE_MAX_ROWS ||
        !lie_rope_profile_name(o->rope_profile)) return NULL;
    if(!LIE_DS4_CACHE_POLICY&&o->cache_policy.enabled)return NULL;
    /* Prefix support is model-specific and checked after capability admission.
     * A provider without predictor state may run only with caches disabled. */
    if(o->mtp_draft_tokens&&!o->mtp_model_path)return NULL;
    if(o->mtp_model_path&&(!LIE_MTP||!*o->mtp_model_path||
       o->mtp_draft_tokens>LIE_MTP_MAX_DRAFT))return NULL;
    if(o->vision_model_path&&(!LIE_VISION||!*o->vision_model_path))return NULL;
    if(steering&&(!LIE_DIRECTIONAL_STEERING||steering->abi_version!=LIE_STEERING_MODEL_ABI||
       steering->struct_bytes!=sizeof(*steering)||!steering->file||!*steering->file||!steering->vector_budget_bytes||
       steering->defaults.abi_version!=LIE_STEERING_POLICY_ABI||steering->defaults.struct_bytes!=sizeof(steering->defaults)||
       !isfinite(steering->defaults.ffn)||fabsf(steering->defaults.ffn)>100||
       !isfinite(steering->defaults.attention)||fabsf(steering->defaults.attention)>100))return NULL;
    lie_core *w=calloc(1,sizeof(*w)); if (!w) return NULL;
    w->info.rope_profile=o->rope_profile;
    w->wake=w->notice=-1; w->options=*o; w->path=strdup(o->model_path);
    unsigned char output_nonce[16];
    if(RAND_bytes(output_nonce,sizeof(output_nonce))!=1)goto fail;
    for(unsigned k=0;k<sizeof(output_nonce);++k)
        snprintf(w->output_namespace+2*k,3,"%02x",output_nonce[k]);
    if(o->mtp_model_path){w->mtp_path=strdup(o->mtp_model_path);if(!w->mtp_path)goto fail;w->options.mtp_model_path=w->mtp_path;}
    if(o->vision_model_path){w->vision_path=strdup(o->vision_model_path);if(!w->vision_path)goto fail;w->options.vision_model_path=w->vision_path;}
    if(steering){w->steering_path=strdup(steering->file);if(!w->steering_path)goto fail;
        w->steering_options=*steering;w->steering_options.file=w->steering_path;}
    if(o->ssd.directory){
        w->ssd_path=strdup(o->ssd.directory);w->options.ssd.directory=w->ssd_path;
        if(!w->ssd_path||*w->ssd_path!='/'||o->ssd.quota_bytes<4096||o->ssd.staging_bytes<32768||
           o->ssd.quota_bytes>INT64_MAX||o->ssd.staging_bytes>SIZE_MAX)goto fail;
    }else if(o->ssd.quota_bytes||o->ssd.staging_bytes)goto fail;
    lie_prefix_cache_init(&w->cache,o->prefix_cache_bytes);w->info.cache=w->cache.info;w->info.cache_policy=o->cache_policy;
    atomic_init(&w->stop,false);
    if (!w->path) goto fail;
    w->wake=eventfd(0,EFD_NONBLOCK|EFD_CLOEXEC); w->notice=eventfd(0,EFD_NONBLOCK|EFD_CLOEXEC);
    if (w->wake<0 || w->notice<0) goto fail;
    if (pthread_mutex_init(&w->gate,NULL)) goto fail;
    if (pthread_create(&w->thread,NULL,work,w)) { pthread_mutex_destroy(&w->gate); goto fail; }
    return w;
fail:
    if (w->wake>=0) close(w->wake);
    if (w->notice>=0) close(w->notice);
    free(w->steering_path);free(w->vision_path);free(w->mtp_path);free(w->ssd_path);free(w->path); free(w); return NULL;
}
lie_core *lie_core_create(const lie_core_options *o){return lie_core_create_steered(o,NULL);}
lie_status lie_core_steering_snapshot(lie_core *w,lie_steering_model_info *out,lie_error *e){
    if(!w||!out||out->abi_version!=LIE_STEERING_MODEL_ABI||out->struct_bytes!=sizeof(*out)){
        if(e)snprintf(e->message,sizeof(e->message),"invalid core steering snapshot");
        return LIE_INVALID;
    }
    pthread_mutex_lock(&w->gate);
    lie_status rc=w->info.state==LIE_READY?LIE_OK:
        w->info.state==LIE_FAILED?LIE_BACKEND_FAILED:LIE_UNSUPPORTED;
    if(rc==LIE_OK)*out=w->steering_info;
    else if(e)snprintf(e->message,sizeof(e->message),"%s",w->info.error[0]?w->info.error:"core steering admission is not READY");
    pthread_mutex_unlock(&w->gate);return rc;
}
void lie_core_stop(lie_core *w) {
    atomic_store(&w->stop,true);
    pthread_mutex_lock(&w->gate);
    if (w->info.state!=LIE_STOPPED) w->info.state=LIE_STOPPING;
    pthread_mutex_unlock(&w->gate); signal_fd(w->wake);
}
void lie_core_destroy(lie_core *w) {
    lie_core_info info; lie_core_snapshot(w,&info); if (info.state!=LIE_STOPPED) abort();
    pthread_join(w->thread,NULL); close(w->wake); close(w->notice);
    pthread_mutex_destroy(&w->gate);free(w->steering_path);free(w->vision_path);free(w->mtp_path);free(w->ssd_path); free(w->path); free(w);
}
int lie_core_fd(lie_core *w) { return w->notice; }
void lie_core_drain(lie_core *w) { drain_fd(w->notice); }
int lie_core_submit_steering(lie_core *w, const lie_core_request *request,
                            const lie_steering_schedule *schedule,lie_job **out) {
  if (!w || !request || !out || *out ||
      request->abi_version != LIE_CORE_REQUEST_ABI ||
      request->struct_bytes != sizeof(*request))
    return 3;
  if(schedule){
    if(!w->steering_path||schedule->abi_version!=LIE_STEERING_SCHEDULE_ABI||
       schedule->struct_bytes!=sizeof(*schedule)||!schedule->count||schedule->count>LIE_STEERING_SCHEDULE_MAX||!schedule->steps)return 3;
    for(size_t i=0;i<schedule->count;++i)
      if(!steering_settings_valid(&schedule->steps[i].settings)||schedule->steps[i].position>=w->options.context||
         (i&&schedule->steps[i-1].position>=schedule->steps[i].position))return 3;
  }
  pthread_mutex_lock(&w->gate);
  int result = w->info.state != LIE_READY || atomic_load(&w->stop) ? 1
               : w->info.active + w->info.queued + w->preparing >= LIE_CORE_JOBS
                   ? 2
                   : 0;
  if (!result && request->image_count &&
      (!w->vision_path || request->image_count > w->info.vision.max_images))
    result = 3;
  if (!result)
    ++w->preparing;
  pthread_mutex_unlock(&w->gate);
  if (result)
    return result;
  lie_job *j = calloc(1, sizeof(*j));
  lie_flow_options options = {
      LIE_OUTPUT_SLOTS,
      LIE_CORE_TOKEN_BYTES * (w->mtp_path ? w->info.mtp.max_output_tokens : 1) +
          (request->stop_count ? LIE_STOP_BYTES : 0),
      131072};
  if (!j ||
      !lie_core_input_copy_sized(request, &j->request, &j->request_storage,
                                 &j->request_bytes))
    goto prepare_failed;
  if(schedule){
    j->schedule=calloc(1,sizeof(*j->schedule));if(!j->schedule)goto prepare_failed;
    j->schedule->abi_version=LIE_STEERING_SCHEDULE_ABI;j->schedule->struct_bytes=sizeof(*j->schedule);
    j->schedule->count=schedule->count;
    for(size_t i=0;i<schedule->count;++i){j->schedule->steps[i]=schedule->steps[i];
      if(j->schedule->steps[i].settings.ffn==0)j->schedule->steps[i].settings.ffn=0;
      if(j->schedule->steps[i].settings.attention==0)j->schedule->steps[i].settings.attention=0;
    }
  }
  j->automatic_output = !j->request.max_tokens;
  if (j->automatic_output)
    j->request.max_tokens = w->options.context - 1 < LIE_CORE_MAX_OUTPUT
                               ? w->options.context - 1
                               : LIE_CORE_MAX_OUTPUT;
  j->output_limit = j->request.max_tokens;
  if (
      !(j->output_ids =
            calloc(j->request.max_tokens, sizeof(*j->output_ids))) ||
      (j->request.generation.logprobs &&
       (!(j->scores = calloc(j->request.max_tokens, sizeof(*j->scores))) ||
        !(j->score_offsets =
              calloc(j->request.max_tokens, sizeof(*j->score_offsets))))) ||
      lie_flow_create(&options, &j->flow) != LIE_FLOW_OK)
    goto prepare_failed;
  if (pthread_mutex_init(&j->gate, NULL))
    goto prepare_failed;
  atomic_init(&j->refs, 2);
  atomic_init(&j->cancel, false);
  atomic_init(&j->semantic_active, false);
  atomic_init(&j->semantic_done, false);
  j->owner = w;
  j->steering.abi_version=LIE_JOB_STEERING_ABI;
  j->steering.struct_bytes=sizeof(j->steering);
  static atomic_uint_fast64_t output_serial = 1;
  snprintf(j->output_identity, sizeof(j->output_identity), "lie-%s-%llu",
           w->output_namespace,
           (unsigned long long)atomic_fetch_add(&output_serial, 1));
  j->info.timing_valid = true;
  j->info.max_decode_output_tokens =
      w->mtp_path && !request->stop_count && !request->generation.logprobs &&
              !request->generation.logit_bias_count
          ? w->info.mtp.max_output_tokens
          : 1;
  (void)lie_flow_request(j->flow, LIE_OUTPUT_SLOTS);
  pthread_mutex_lock(&w->gate);
  --w->preparing;
  size_t index = 0;
  if (w->info.state != LIE_READY || atomic_load(&w->stop))
    result = 1;
  else {
    while (index < LIE_CORE_JOBS && w->jobs[index])
      ++index;
    if (index == LIE_CORE_JOBS)
      result = 2;
  }
  if (!result) {
    w->jobs[index] = j;
    ++w->info.queued;
    *out = j;
  }
  pthread_mutex_unlock(&w->gate);
  if (result) {
    (void)lie_flow_cancel(j->flow);
    atomic_store(&j->refs, 1);
    job_drop(j);
    return result;
  }
  signal_fd(w->wake);
  signal_fd(w->notice);
  return 0;
prepare_failed:
  if (j) {
    if (j->flow) {
      (void)lie_flow_cancel(j->flow);
      (void)lie_flow_destroy(&j->flow);
    }
    free(j->request_storage);
    free(j->output_ids);
    free(j->scores);
    free(j->score_offsets);
    free(j->schedule);
    free(j);
  }
  pthread_mutex_lock(&w->gate);
  --w->preparing;
  pthread_mutex_unlock(&w->gate);
  return 3;
}
int lie_core_submit(lie_core *w,const lie_core_request *r,lie_job **out){
    return lie_core_submit_steering(w,r,NULL,out);
}
lie_flow *lie_job_flow(lie_job *j) {
    if(!j||j->output_mode==2)return NULL;
    j->output_mode=1;return j->flow;
}
static bool semantic_mode(lie_job *j) {
    if(!j||j->output_mode==1)return false;
    if(!j->events){lie_job_info info;lie_job_snapshot(j,&info);
        j->events=lie_event_stream_create(j,j->flow,&j->request,info.max_decode_output_tokens,j->output_identity);}
    if(!j->events)return false;
    j->output_mode=2;atomic_store(&j->semantic_active,true);return true;
}
int lie_job_event_fd(lie_job *j){return semantic_mode(j)?lie_flow_fd(j->flow,LIE_FLOW_OUTPUT_READY):-1;}
lie_flow_status lie_job_event_drain(lie_job *j){return semantic_mode(j)?lie_flow_drain(j->flow,LIE_FLOW_OUTPUT_READY):LIE_FLOW_INVALID;}
lie_flow_status lie_job_event_request(lie_job *j,uint64_t n){return semantic_mode(j)?lie_flow_request(j->flow,n):LIE_FLOW_INVALID;}
lie_flow_status lie_job_event_next(lie_job *j,lie_event *e){
    if(!semantic_mode(j))return LIE_FLOW_INVALID;
    lie_flow_status rc=lie_event_stream_next(j->events,e);
    if(rc==LIE_FLOW_OK&&e->kind==LIE_EVENT_TURN_END)atomic_store(&j->semantic_done,true);
    return rc;
}
lie_flow_status lie_job_event_release(lie_job *j,lie_event_ticket t){return semantic_mode(j)?lie_event_stream_release(j->events,t):LIE_FLOW_INVALID;}
bool lie_job_semantic_cancelled(lie_job *j){return atomic_load(&j->cancel);}
void lie_job_semantic_result(lie_job *j,unsigned calls,const char *error){
    pthread_mutex_lock(&j->gate);
    bool first=!j->info.semantic_checked;
    if(first){j->info.semantic_checked=true;j->info.tool_calls=calls;
        if(error){j->info.output_invalid=true;j->info.finish=LIE_FINISH_INVALID;snprintf(j->info.error,256,"%s",error);}}
    pthread_mutex_unlock(&j->gate);
    if(first&&error){pthread_mutex_lock(&j->owner->gate);++j->owner->info.output_validation_errors;pthread_mutex_unlock(&j->owner->gate);}
}
void lie_job_cancel(lie_job *j) {
    lie_flow_state state; (void)lie_flow_snapshot(j->flow,&state);
    if (state.terminal_observed && (!atomic_load(&j->semantic_active)||atomic_load(&j->semantic_done))) return;
    bool first=!atomic_exchange(&j->cancel,true);
    pthread_mutex_lock(&j->gate);
    if (j->sequence) lie_sequence_cancel(j->sequence); /* ABI latch only, no wait. */
    pthread_mutex_unlock(&j->gate);
    /* Never nest metadata gates or wait for provider completion. This records
     * first cancellation observed within the owner dispatch interval, not HIP
     * submission, kernel preemption or every possible cancellation race. */
    lie_core *w=j->owner;
    if (first) {
        pthread_mutex_lock(&w->gate);
        if (j->executing) {
            if (w->info.executor_phase==LIE_EXECUTOR_PREFILL) ++w->info.cancel_during_prefill;
            else if (w->info.executor_phase==LIE_EXECUTOR_DECODE) ++w->info.cancel_during_decode;
        }
        pthread_mutex_unlock(&w->gate);
    }
    (void)lie_flow_cancel(j->flow); signal_fd(w->wake);
}
void lie_job_release(lie_job *j) { lie_job_cancel(j); job_drop(j); }
