/* SPDX-License-Identifier: MIT */
#include "lie/core.h"
#include "core_input.h"
#include "prefix_cache.h"
#include "lie/inference.h"
#include <errno.h>
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
    int32_t *output_ids;
    lie_flow *flow;
    atomic_uint refs;
    atomic_bool cancel;
    /* Metadata synchronized separately from the model; never holds GPU work. */
    pthread_mutex_t gate;
    lie_job_info info;
    lie_sequence *sequence; /* worker only */
    int32_t *prompt;
    size_t tokens, fed;
    size_t checkpoint;
    bool cache_checked, capture_checked;
    uint32_t position; /* Last validated completed frontier; worker only. */
    bool executing; /* Protected by owner gate; cancellation observation. */
    bool output_blocked; /* Worker-owned, aggregate snapshot under owner gate. */
};
struct lie_core {
    pthread_t thread;
    pthread_mutex_t gate;
    atomic_bool stop;
    lie_core_info info;
    lie_core_options options;
    char *path;
    lie_job *jobs[LIE_CORE_JOBS];
    unsigned preparing; /* Bounded admission copies, protected by gate. */
    int wake, notice;
    lie_model *model;
    lie_prefix_cache cache;
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
    if (atomic_fetch_sub(&j->refs,1)!=1) return;
    if (lie_flow_destroy(&j->flow)!=LIE_FLOW_OK) abort();
    free(j->request_storage); free(j->output_ids); free(j->prompt);
    pthread_mutex_destroy(&j->gate); free(j);
}
void lie_job_snapshot(lie_job *j, lie_job_info *out) {
    pthread_mutex_lock(&j->gate); *out=j->info; pthread_mutex_unlock(&j->gate);
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
static void finish_job(lie_core *w, size_t index, lie_job_finish finish, const char *message) {
    lie_job *j=w->jobs[index]; lie_error error={0};
    set_output_blocked(w,j,false);
    /* Detach under the cancellation gate. An external latch call cannot race
     * sequence destruction; no backend work runs while holding this gate. */
    pthread_mutex_lock(&j->gate);
    lie_sequence *sequence=j->sequence; j->sequence=NULL;
    pthread_mutex_unlock(&j->gate);
    if (sequence) {
        if (finish==LIE_FINISH_CANCEL) lie_sequence_cancel(sequence);
        (void)lie_sequence_close(&sequence,&error);
        pthread_mutex_lock(&w->gate); --w->info.active; pthread_mutex_unlock(&w->gate);
    } else {
        pthread_mutex_lock(&w->gate); --w->info.queued; pthread_mutex_unlock(&w->gate);
    }
    /* Keep immutable physical input/output witnesses until the last consumer
     * reference; protocol/parser storage never belonged to this job. */
    free(j->request_storage); j->request_storage=NULL;
    pthread_mutex_lock(&j->gate);
    j->info.finish=finish; j->info.retired=true;
    if (message) snprintf(j->info.error,sizeof(j->info.error),"%s",message);
    pthread_mutex_unlock(&j->gate);
    if (finish==LIE_FINISH_CANCEL) (void)lie_flow_cancel(j->flow);
    else if (finish==LIE_FINISH_INVALID || finish==LIE_FINISH_BACKEND)
        (void)lie_flow_fail(j->flow,(int)finish);
    else (void)lie_flow_finish(j->flow);
    pthread_mutex_lock(&w->gate);
    w->jobs[index]=NULL;
    if (finish==LIE_FINISH_STOP || finish==LIE_FINISH_LENGTH) ++w->info.completed_requests;
    else if (finish==LIE_FINISH_CANCEL) ++w->info.cancelled_requests;
    else ++w->info.failed_requests;
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
static lie_status cache_step(lie_core *w,lie_job *j,bool restore,lie_error *error) {
    pthread_mutex_lock(&w->gate);
    w->dispatch=j;j->executing=true;
    w->info.executor_phase=restore?LIE_EXECUTOR_RESTORE:LIE_EXECUTOR_CAPTURE;
    pthread_mutex_unlock(&w->gate);
    uint64_t start=0,end=0;bool a=clock_ns(&start);unsigned reused=0;
    lie_status rc=restore?lie_prefix_cache_restore(&w->cache,j->sequence,j->prompt,j->tokens,w->options.chunk,&reused,error):
        lie_prefix_cache_capture(&w->cache,j->sequence,j->prompt,j->fed,error);
    bool b=clock_ns(&end);
    pthread_mutex_lock(&j->gate);
    if(!a||!b||end<start)j->info.timing_valid=false;
    else if(restore)j->info.cache_restore_ns=end-start;
    else j->info.cache_capture_ns=end-start;
    if(restore&&rc==LIE_OK){j->fed=reused;j->position=reused;j->info.cached_tokens=reused;}
    pthread_mutex_unlock(&j->gate);
    pthread_mutex_lock(&w->gate);
    w->info.cache=w->cache.info;w->info.executor_phase=LIE_EXECUTOR_IDLE;
    j->executing=false;w->dispatch=NULL;
    pthread_mutex_unlock(&w->gate);
    return rc;
}
static bool step(lie_core *w, size_t index) {
    lie_job *j=w->jobs[index]; if (!j) return false;
    lie_error error={0}; lie_core_info wi; lie_core_snapshot(w,&wi);
    if (atomic_load(&j->cancel) || atomic_load(&w->stop)) {
        finish_job(w,index,LIE_FINISH_CANCEL,"cancelled"); return true;
    }
    if (wi.state==LIE_FAILED) { finish_job(w,index,LIE_FINISH_BACKEND,"backend_failed"); return true; }
    if (!j->sequence) {
        if (wi.active>=w->options.max_active) return false;
        j->prompt=malloc((size_t)w->options.context*sizeof(*j->prompt));
        if (!j->prompt) { finish_job(w,index,LIE_FINISH_BACKEND,"allocation_failed"); return true; }
        lie_core_request *r=&j->request;
        const lie_chat_tool *tools=r->chat.tools;
        size_t tool_count=r->tool_choice==LIE_TOOLS_NONE?0:r->chat.tool_count;
        if (r->tool_choice==LIE_TOOLS_NAMED) {
            size_t k=0; while (k<r->chat.tool_count && strcmp(r->chat.tools[k].name,r->named_tool)) ++k;
            if (k==r->chat.tool_count) { finish_job(w,index,LIE_FINISH_INVALID,"invalid_tool_choice"); return true; }
            tools=&r->chat.tools[k]; tool_count=1;
        }
        lie_status rc=LIE_OK;
        if (r->kind==LIE_INPUT_TOKENS) {
            j->tokens=r->token_count;
            if (j->tokens>w->options.context) rc=LIE_BUFFER_SMALL;
            else memcpy(j->prompt,r->tokens,j->tokens*sizeof(*j->prompt));
        } else if (r->kind==LIE_INPUT_TEXT) {
            rc=lie_model_tokenize(w->model,r->text,r->text_bytes,j->prompt,w->options.context,&j->tokens,&error);
        } else {
            const lie_chat_template input={r->chat.messages,r->chat.details,r->chat.count,tools,tool_count,
                r->tool_choice>=LIE_TOOLS_REQUIRED || r->chat.require_tool_call};
            rc=lie_model_chat_tokens_ex(w->model,&input,j->prompt,w->options.context,&j->tokens,&error);
        }
        if (rc!=LIE_OK || !j->tokens || j->tokens>w->options.context ||
            j->request.max_tokens>w->options.context-j->tokens) {
            if (rc==LIE_BACKEND_FAILED) poison(w,&error);
            finish_job(w,index,rc==LIE_BACKEND_FAILED?LIE_FINISH_BACKEND:LIE_FINISH_INVALID,
                       rc==LIE_OK || rc==LIE_BUFFER_SMALL?"context_budget_exceeded":error.message);
            return true;
        }
        for (size_t k=0;k<j->tokens;++k) if (j->prompt[k]<0 || (uint32_t)j->prompt[k]>=wi.model.vocab_tokens) {
            finish_job(w,index,LIE_FINISH_INVALID,"invalid_prompt_token");return true;
        }
        lie_sequence *sequence=NULL;
        rc=lie_sequence_create(w->model,&sequence,&error);
        if (rc!=LIE_OK) {
            if (rc==LIE_BACKEND_FAILED) poison(w,&error);
            finish_job(w,index,LIE_FINISH_BACKEND,error.message); return true;
        }
        rc=lie_sequence_configure(sequence,&j->request.generation,&error);
        if (rc!=LIE_OK) {
            lie_error close_error={0};
            lie_status closed=lie_sequence_close(&sequence,&close_error);
            if (closed!=LIE_OK || rc==LIE_BACKEND_FAILED) poison(w,closed!=LIE_OK?&close_error:&error);
            finish_job(w,index,rc==LIE_BACKEND_FAILED || closed!=LIE_OK?LIE_FINISH_BACKEND:LIE_FINISH_INVALID,error.message);
            return true;
        }
        pthread_mutex_lock(&w->gate); --w->info.queued; ++w->info.active; pthread_mutex_unlock(&w->gate);
        pthread_mutex_lock(&j->gate);
        j->sequence=sequence;
        if (atomic_load(&j->cancel)) lie_sequence_cancel(sequence);
        j->info.prompt_tokens=(unsigned)j->tokens; j->info.prepared=true;
        j->checkpoint=j->tokens>=w->options.chunk?j->tokens-j->tokens%w->options.chunk:j->tokens;
        pthread_mutex_unlock(&j->gate);
        signal_fd(w->notice);
    }
    if (atomic_load(&j->cancel)) { finish_job(w,index,LIE_FINISH_CANCEL,"cancelled"); return true; }
    if(w->options.prefix_cache_bytes&&!j->cache_checked){
        j->cache_checked=true;lie_status rc=cache_step(w,j,true,&error);
        if(rc!=LIE_OK){if(rc!=LIE_CANCELLED)poison(w,&error);
            finish_job(w,index,rc==LIE_CANCELLED?LIE_FINISH_CANCEL:LIE_FINISH_BACKEND,error.message);return true;}
        if(j->fed>=j->checkpoint)j->capture_checked=true;
        if(atomic_load(&j->cancel)){finish_job(w,index,LIE_FINISH_CANCEL,"cancelled");return true;}
    }
    if (j->fed<j->tokens) {
        size_t add=j->tokens-j->fed; if (add>w->options.chunk) add=w->options.chunk;
        begin_call(w,j,true);
        uint64_t started=0; bool started_ok=clock_ns(&started);
        lie_status rc=lie_sequence_prefill(j->sequence,j->prompt,j->fed+add,&error);
        record_call(j,true,started_ok,started,rc==LIE_OK?(unsigned)add:0);
        if (rc!=LIE_OK) {
            if (rc!=LIE_CANCELLED) {
                if (!error.message[0]) snprintf(error.message,sizeof(error.message),"executor_prefill_failed");
                poison(w,&error);
            }
            finish_job(w,index,rc==LIE_CANCELLED?LIE_FINISH_CANCEL:LIE_FINISH_BACKEND,error.message);
        } else {
            j->fed+=add;j->position=(uint32_t)j->fed;
            if(w->options.prefix_cache_bytes&&!j->capture_checked&&j->fed==j->checkpoint){
                j->capture_checked=true;rc=cache_step(w,j,false,&error);
                if(rc!=LIE_OK){if(rc!=LIE_CANCELLED)poison(w,&error);
                    finish_job(w,index,rc==LIE_CANCELLED?LIE_FINISH_CANCEL:LIE_FINISH_BACKEND,error.message);}
            }
        }
        return true;
    }
    return false; /* Prefilled rows enter the shared inference dispatcher below. */
}
static bool decode_ready(lie_core *w) {
    lie_inference_row rows[LIE_CORE_JOBS]={0};size_t indices[LIE_CORE_JOBS],n=0;
    lie_core_info wi;lie_core_snapshot(w,&wi);
    if(wi.state!=LIE_READY)return false;
    for(size_t i=0;i<LIE_CORE_JOBS;++i){
        pthread_mutex_lock(&w->gate);lie_job *j=w->jobs[i];pthread_mutex_unlock(&w->gate);
        if(j&&j->sequence&&j->fed==j->tokens&&!atomic_load(&j->cancel)){
            indices[n]=i;rows[n++]=(lie_inference_row){.sequence=j->sequence,.flow=j->flow,
                .position=j->position,.context=w->options.context,.vocab=wi.model.vocab_tokens};
        }
    }
    if(!n)return false;
    lie_inference_batch batch={0};lie_error error={0};
    lie_status rc=lie_inference_prepare(rows,n,wi.model.native_batch_capacity,&batch,&error);
    for(size_t i=0;i<n;++i)set_output_blocked(w,w->jobs[indices[i]],rows[i].blocked);
    if(rc==LIE_OK&&batch.selected){
        pthread_mutex_lock(&w->gate);
        w->info.executor_phase=LIE_EXECUTOR_DECODE;
        ++w->info.decode_started;
        if(batch.selected>1){++w->info.decode_batches;w->info.decode_batch_rows+=batch.selected;}
        else ++w->info.decode_single_calls;
        for(size_t i=0;i<n;++i)if(rows[i].selected)w->jobs[indices[i]]->executing=true;
        pthread_mutex_unlock(&w->gate);
        uint64_t started=0,ended=0;bool a=clock_ns(&started);
        rc=lie_inference_run(&batch,&error);bool b=clock_ns(&ended);
        /* A shared call's duration is attributed to every participating row.
         * These per-request durations overlap; never sum them as GPU elapsed. */
        for(size_t i=0;i<n;++i)if(rows[i].selected){lie_job *j=w->jobs[indices[i]];
            pthread_mutex_lock(&j->gate);++j->info.decode_calls;
            if(!a||!b||ended<started||ended-started>UINT64_MAX-j->info.decode_ns)j->info.timing_valid=false;
            else j->info.decode_ns+=ended-started;
            pthread_mutex_unlock(&j->gate);
        }
        pthread_mutex_lock(&w->gate);
        ++w->info.decode_returned;w->info.executor_phase=LIE_EXECUTOR_IDLE;
        for(size_t i=0;i<n;++i)if(rows[i].selected)w->jobs[indices[i]]->executing=false;
        pthread_mutex_unlock(&w->gate);
    }
    size_t bytes[LIE_CORE_JOBS]={0};
    /* Validate all rows before exposing any output from a shared call. */
    for(size_t i=0;i<n&&rc==LIE_OK;++i)if(rows[i].selected&&rows[i].outcome.status==LIE_OK&&rows[i].outcome.result.emitted){
        lie_inference_row *r=&rows[i];
        rc=lie_model_token_text(w->model,r->outcome.result.token,(char *)r->reservation.data,r->reservation.capacity,&bytes[i],&error);
        if(rc==LIE_OK&&bytes[i]>r->reservation.capacity){snprintf(error.message,sizeof(error.message),"invalid_token_text_size");rc=LIE_BACKEND_FAILED;}
    }
    if(rc!=LIE_OK){
        if(!error.message[0])snprintf(error.message,sizeof(error.message),"executor_dispatch_failed");
        poison(w,&error);
    }
    bool progress=batch.selected>0;
    for(size_t i=0;i<n;++i){lie_inference_row *r=&rows[i];lie_job *j=w->jobs[indices[i]];
        if(rc!=LIE_OK){
            publish_outcome(j,LIE_FINISH_BACKEND,error.message);
            if(r->reserved)(void)lie_flow_abort(j->flow,r->reservation.ticket,LIE_FINISH_BACKEND);
            finish_job(w,indices[i],LIE_FINISH_BACKEND,error.message);progress=true;continue;
        }
        if(r->outcome.status==LIE_CANCELLED||atomic_load(&j->cancel)){
            publish_outcome(j,LIE_FINISH_CANCEL,"cancelled");(void)lie_flow_cancel(j->flow);
            if(r->reserved)(void)lie_flow_abort(j->flow,r->reservation.ticket,LIE_FINISH_CANCEL);
            finish_job(w,indices[i],LIE_FINISH_CANCEL,"cancelled");progress=true;continue;
        }
        if(!r->selected)continue;
        lie_decode_result d=r->outcome.result;j->position=d.position;
        pthread_mutex_lock(&j->gate);
        if (d.emitted) j->output_ids[j->info.output_tokens]=d.token;
        j->info.output_tokens+=d.emitted;
        bool end=d.stop||j->info.output_tokens>=j->request.max_tokens;
        if(end)j->info.finish=d.stop?LIE_FINISH_STOP:LIE_FINISH_LENGTH;
        pthread_mutex_unlock(&j->gate);
        pthread_mutex_lock(&w->gate);w->info.generated_tokens+=d.emitted;pthread_mutex_unlock(&w->gate);
        lie_flow_status f=lie_flow_commit(j->flow,r->reservation.ticket,bytes[i],d.emitted,end);
        if(f!=LIE_FLOW_OK&&f!=LIE_FLOW_CLOSED)abort();
        if(f==LIE_FLOW_CLOSED||atomic_load(&j->cancel))finish_job(w,indices[i],LIE_FINISH_CANCEL,"cancelled");
        else if(end)finish_job(w,indices[i],d.stop?LIE_FINISH_STOP:LIE_FINISH_LENGTH,NULL);
    }
    return progress;
}
static void *work(void *arg) {
    lie_core *w=arg; lie_error error={0};
    lie_model_options options={LIE_EXECUTOR_ABI,sizeof(options),w->options.context,w->options.chunk};
    lie_model_info model={0};
    lie_status rc=lie_backend_open_batch(w->path,&options,w->options.max_active,&w->model,&error);
    if (rc==LIE_OK) rc=lie_model_get_info(w->model,&model,&error);
    if(rc==LIE_OK&&w->options.prefix_cache_bytes&&!lie_backend_prefix_state_supported()){
        rc=LIE_UNSUPPORTED;snprintf(error.message,sizeof(error.message),"provider has no component-state support; rebuild with state access or explicitly disable RAM cache");
    }
    pthread_mutex_lock(&w->gate);
    w->info.model=model;
    w->info.state=atomic_load(&w->stop)?LIE_STOPPING:rc==LIE_OK?LIE_READY:LIE_FAILED;
    if (rc!=LIE_OK) snprintf(w->info.error,sizeof(w->info.error),"%s",error.message);
    pthread_mutex_unlock(&w->gate); signal_fd(w->notice);
    for (;;) {
        bool progress=false; size_t present=0;
        for (size_t i=0;i<LIE_CORE_JOBS;++i) {
            /* Only the worker removes slots; producer publication is under gate. */
            pthread_mutex_lock(&w->gate); bool has=w->jobs[i]!=NULL; pthread_mutex_unlock(&w->gate);
            if (has) { ++present; progress=step(w,i) || progress; }
        }
        progress=decode_ready(w) || progress;
        if (atomic_load(&w->stop) && !present) break;
        if (progress) continue;
        struct pollfd fds[LIE_CORE_JOBS+1]; size_t count=1;
        fds[0]=(struct pollfd){w->wake,POLLIN,0};
        pthread_mutex_lock(&w->gate);
        for (size_t i=0;i<LIE_CORE_JOBS;++i) if (w->jobs[i]) {
            fds[count++]=(struct pollfd){lie_flow_fd(w->jobs[i]->flow,LIE_FLOW_WORK_READY),POLLIN,0};
        }
        pthread_mutex_unlock(&w->gate);
        int result; do { result=poll(fds,count,-1); } while (result<0 && errno==EINTR);
        if (result<0) abort();
        for (size_t i=0;i<count;++i) if (fds[i].revents&POLLIN) drain_fd(fds[i].fd);
    }
    lie_prefix_cache_clear(&w->cache);
    if (w->model) (void)lie_model_close(&w->model,&error);
    pthread_mutex_lock(&w->gate); w->info.cache=w->cache.info;w->info.state=LIE_STOPPED; pthread_mutex_unlock(&w->gate);
    signal_fd(w->notice); return NULL;
}
void lie_core_options_init(lie_core_options *o){
    if(o)*o=(lie_core_options){.context=4096,.chunk=2048,.max_active=1,.prefix_cache_bytes=LIE_PREFIX_CACHE_DEFAULT_BYTES};
}
lie_core *lie_core_create(const lie_core_options *o) {
    if (!o || !o->model_path || !*o->model_path || o->context<128 || o->context>LIE_CORE_MAX_CONTEXT ||
        !o->chunk || o->chunk>2048 || !o->max_active || o->max_active>LIE_DECODE_MAX_ROWS) return NULL;
    lie_core *w=calloc(1,sizeof(*w)); if (!w) return NULL;
    w->wake=w->notice=-1; w->options=*o; w->path=strdup(o->model_path);
    lie_prefix_cache_init(&w->cache,o->prefix_cache_bytes);w->info.cache=w->cache.info;
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
    free(w->path); free(w); return NULL;
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
    pthread_mutex_destroy(&w->gate); free(w->path); free(w);
}
int lie_core_fd(lie_core *w) { return w->notice; }
void lie_core_drain(lie_core *w) { drain_fd(w->notice); }
int lie_core_submit(lie_core *w, const lie_core_request *request, lie_job **out) {
    if (!w || !request || !out || *out) return 3;
    pthread_mutex_lock(&w->gate);
    int result=w->info.state!=LIE_READY || atomic_load(&w->stop)?1:
        w->info.active+w->info.queued+w->preparing>=LIE_CORE_JOBS?2:0;
    if (!result) ++w->preparing;
    pthread_mutex_unlock(&w->gate);
    if (result) return result;
    lie_job *j=calloc(1,sizeof(*j));
    lie_flow_options options={LIE_OUTPUT_SLOTS,LIE_CORE_TOKEN_BYTES,65536};
    if (!j || !lie_core_input_copy(request,&j->request,&j->request_storage) ||
        !(j->output_ids=calloc(j->request.max_tokens,sizeof(*j->output_ids))) ||
        lie_flow_create(&options,&j->flow)!=LIE_FLOW_OK) goto prepare_failed;
    if (pthread_mutex_init(&j->gate,NULL)) goto prepare_failed;
    atomic_init(&j->refs,2); atomic_init(&j->cancel,false); j->owner=w;
    j->info.timing_valid=true;
    (void)lie_flow_request(j->flow,LIE_OUTPUT_SLOTS);
    pthread_mutex_lock(&w->gate);
    --w->preparing;
    size_t index=0;
    if (w->info.state!=LIE_READY || atomic_load(&w->stop)) result=1;
    else {
        while (index<LIE_CORE_JOBS && w->jobs[index]) ++index;
        if (index==LIE_CORE_JOBS) result=2;
    }
    if (!result) {
        w->jobs[index]=j; ++w->info.queued; *out=j;
    }
    pthread_mutex_unlock(&w->gate);
    if (result) {
        (void)lie_flow_cancel(j->flow); atomic_store(&j->refs,1); job_drop(j); return result;
    }
    signal_fd(w->wake); signal_fd(w->notice); return 0;
prepare_failed:
    if (j) {
        if (j->flow) { (void)lie_flow_cancel(j->flow);(void)lie_flow_destroy(&j->flow); }
        free(j->request_storage);free(j->output_ids);free(j);
    }
    pthread_mutex_lock(&w->gate);--w->preparing;pthread_mutex_unlock(&w->gate);
    return 3;
}
lie_flow *lie_job_flow(lie_job *j) { return j->flow; }
void lie_job_cancel(lie_job *j) {
    lie_flow_state state; (void)lie_flow_snapshot(j->flow,&state);
    if (state.terminal_observed) return; /* Normal transport close is not cancellation. */
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
