/* SPDX-License-Identifier: MIT */
#include "lie/worker.h"
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
    lie_worker *owner;
    lie_chat_request request;
    lie_flow *flow;
    atomic_uint refs;
    atomic_bool cancel;
    /* Metadata synchronized separately from the model; never holds GPU work. */
    pthread_mutex_t gate;
    lie_job_info info;
    lie_sequence *sequence; /* worker only */
    int32_t *prompt;
    size_t tokens, fed;
    uint32_t position; /* Last validated completed frontier; worker only. */
    bool output_blocked; /* Worker-owned, aggregate snapshot under owner gate. */
};
struct lie_worker {
    pthread_t thread;
    pthread_mutex_t gate;
    atomic_bool stop;
    lie_worker_info info;
    lie_worker_options options;
    char *path;
    lie_job *jobs[LIE_WORKER_JOBS];
    int wake, notice;
    lie_model *model;
    lie_job *dispatch; /* Pinned worker job, protected by owner gate. */
};
static void set_output_blocked(lie_worker *w, lie_job *j, bool value) {
    if (j->output_blocked==value) return;
    j->output_blocked=value;
    pthread_mutex_lock(&w->gate);
    if (value) ++w->info.output_blocked;
    else --w->info.output_blocked;
    pthread_mutex_unlock(&w->gate);
}
static void begin_call(lie_worker *w, lie_job *j, bool prefill) {
    pthread_mutex_lock(&w->gate);
    if (w->dispatch) abort();
    w->dispatch=j;
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
    lie_worker *w=j->owner;
    pthread_mutex_lock(&w->gate);
    if (w->dispatch!=j) abort();
    if (prefill) ++w->info.prefill_returned;
    else ++w->info.decode_returned;
    w->dispatch=NULL; w->info.executor_phase=LIE_EXECUTOR_IDLE;
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
    lie_chat_free(&j->request); free(j->prompt);
    pthread_mutex_destroy(&j->gate); free(j);
}
void lie_job_snapshot(lie_job *j, lie_job_info *out) {
    pthread_mutex_lock(&j->gate); *out=j->info; pthread_mutex_unlock(&j->gate);
}
void lie_worker_snapshot(lie_worker *w, lie_worker_info *out) {
    pthread_mutex_lock(&w->gate); *out=w->info; pthread_mutex_unlock(&w->gate);
}
static void publish_outcome(lie_job *j, lie_job_finish finish, const char *message) {
    pthread_mutex_lock(&j->gate);
    j->info.finish=finish;
    if (message) snprintf(j->info.error,sizeof(j->info.error),"%s",message);
    pthread_mutex_unlock(&j->gate);
}
static void finish_job(lie_worker *w, size_t index, lie_job_finish finish, const char *message) {
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
    free(j->prompt); j->prompt=NULL; lie_chat_free(&j->request);
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
static void poison(lie_worker *w, const lie_error *error) {
    pthread_mutex_lock(&w->gate);
    w->info.state=LIE_FAILED;
    snprintf(w->info.error,sizeof(w->info.error),"%s",error->message);
    pthread_mutex_unlock(&w->gate); signal_fd(w->notice);
}
static bool step(lie_worker *w, size_t index) {
    lie_job *j=w->jobs[index]; if (!j) return false;
    lie_error error={0}; lie_worker_info wi; lie_worker_snapshot(w,&wi);
    if (atomic_load(&j->cancel) || atomic_load(&w->stop)) {
        finish_job(w,index,LIE_FINISH_CANCEL,"cancelled"); return true;
    }
    if (wi.state==LIE_FAILED) { finish_job(w,index,LIE_FINISH_BACKEND,"backend_failed"); return true; }
    if (!j->sequence) {
        if (wi.active>=w->options.max_active) return false;
        j->prompt=malloc((size_t)w->options.context*sizeof(*j->prompt));
        if (!j->prompt) { finish_job(w,index,LIE_FINISH_BACKEND,"allocation_failed"); return true; }
        lie_chat_request *r=&j->request;
        const lie_chat_tool *tools=r->tools;
        size_t tool_count=r->tool_choice==LIE_TOOLS_NONE?0:r->tool_count;
        if (r->tool_choice==LIE_TOOLS_NAMED) {
            size_t k=0; while (k<r->tool_count && strcmp(r->tools[k].name,r->named_tool)) ++k;
            if (k==r->tool_count) { finish_job(w,index,LIE_FINISH_INVALID,"invalid_tool_choice"); return true; }
            tools=&r->tools[k]; tool_count=1;
        }
        const lie_chat_template input={r->messages,r->details,r->count,tools,tool_count,r->tool_choice>=LIE_TOOLS_REQUIRED};
        lie_status rc=lie_model_chat_tokens_ex(w->model,&input,
                         j->prompt,w->options.context,&j->tokens,&error);
        if (rc!=LIE_OK || !j->tokens || j->tokens>w->options.context ||
            j->request.max_tokens>w->options.context-j->tokens) {
            if (rc==LIE_BACKEND_FAILED) poison(w,&error);
            finish_job(w,index,rc==LIE_BACKEND_FAILED?LIE_FINISH_BACKEND:LIE_FINISH_INVALID,
                       rc==LIE_OK || rc==LIE_BUFFER_SMALL?"context_budget_exceeded":error.message);
            return true;
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
        pthread_mutex_unlock(&j->gate);
        signal_fd(w->notice);
    }
    if (atomic_load(&j->cancel)) { finish_job(w,index,LIE_FINISH_CANCEL,"cancelled"); return true; }
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
        } else { j->fed+=add; j->position=(uint32_t)j->fed; }
        return true;
    }
    lie_flow_reservation reservation;
    lie_flow_status flow=lie_flow_reserve(j->flow,1,&reservation);
    if (flow==LIE_FLOW_WOULD_BLOCK) { set_output_blocked(w,j,true); return false; }
    set_output_blocked(w,j,false);
    if (flow==LIE_FLOW_CLOSED) { finish_job(w,index,LIE_FINISH_CANCEL,"cancelled"); return true; }
    if (flow!=LIE_FLOW_OK) abort();
    if (lie_flow_begin(j->flow,reservation.ticket)!=LIE_FLOW_OK) {
        publish_outcome(j,LIE_FINISH_CANCEL,"cancelled");
        (void)lie_flow_abort(j->flow,reservation.ticket,LIE_FINISH_CANCEL);
        finish_job(w,index,LIE_FINISH_CANCEL,"cancelled"); return true;
    }
    lie_decode_result result={0};
    begin_call(w,j,false);
    uint64_t started=0; bool started_ok=clock_ns(&started);
    lie_status rc=lie_sequence_decode(j->sequence,&result,&error);
    record_call(j,false,started_ok,started,0);
    if (rc==LIE_CANCELLED) {
        publish_outcome(j,LIE_FINISH_CANCEL,"cancelled");
        (void)lie_flow_cancel(j->flow);
        (void)lie_flow_abort(j->flow,reservation.ticket,LIE_FINISH_CANCEL);
        finish_job(w,index,LIE_FINISH_CANCEL,"cancelled"); return true;
    }
    /* Validate the completed frontier before token lookup, accounting or flow
     * publication. A corrupt successful return is a provider contract failure,
     * not a recoverable per-request error or permission to dispatch its peer. */
    if (rc==LIE_OK && (result.emitted>1 || result.stop>1 || (!result.emitted && !result.stop) ||
        result.position!=(uint64_t)j->position+result.emitted || result.position>w->options.context ||
        (result.emitted && (result.token<0 || (uint32_t)result.token>=wi.model.vocab_tokens)))) {
        snprintf(error.message,sizeof(error.message),"invalid_decode_frontier"); rc=LIE_BACKEND_FAILED;
    }
    size_t bytes=0;
    if (rc==LIE_OK && result.emitted) {
        rc=lie_model_token_text(w->model,result.token,(char *)reservation.data,reservation.capacity,&bytes,&error);
        if (rc==LIE_OK && bytes>reservation.capacity) {
            snprintf(error.message,sizeof(error.message),"invalid_token_text_size"); rc=LIE_BACKEND_FAILED;
        }
    }
    if (rc!=LIE_OK) {
        if (!error.message[0]) snprintf(error.message,sizeof(error.message),"executor_decode_failed");
        poison(w,&error);
        publish_outcome(j,LIE_FINISH_BACKEND,error.message);
        (void)lie_flow_abort(j->flow,reservation.ticket,LIE_FINISH_BACKEND);
        finish_job(w,index,LIE_FINISH_BACKEND,error.message); return true;
    }
    j->position=result.position;
    pthread_mutex_lock(&j->gate); j->info.output_tokens+=result.emitted;
    unsigned generated=j->info.output_tokens;
    bool end=result.stop || generated>=j->request.max_tokens;
    /* Publish terminal metadata before flow can make its terminal observable.
     * Worker reference still pins the job during subsequent session retirement. */
    if (end) j->info.finish=result.stop?LIE_FINISH_STOP:LIE_FINISH_LENGTH;
    pthread_mutex_unlock(&j->gate);
    pthread_mutex_lock(&w->gate); w->info.generated_tokens+=result.emitted; pthread_mutex_unlock(&w->gate);
    flow=lie_flow_commit(j->flow,reservation.ticket,bytes,result.emitted,end);
    if (flow!=LIE_FLOW_OK && flow!=LIE_FLOW_CLOSED) abort();
    if (flow==LIE_FLOW_CLOSED || atomic_load(&j->cancel)) finish_job(w,index,LIE_FINISH_CANCEL,"cancelled");
    else if (end) finish_job(w,index,result.stop?LIE_FINISH_STOP:LIE_FINISH_LENGTH,NULL);
    return true;
}
static void *work(void *arg) {
    lie_worker *w=arg; lie_error error={0};
    lie_model_options options={LIE_EXECUTOR_ABI,sizeof(options),w->options.context,w->options.chunk};
    lie_model_info model={0};
    lie_status rc=lie_backend_open(w->path,&options,&w->model,&error);
    if (rc==LIE_OK) rc=lie_model_get_info(w->model,&model,&error);
    pthread_mutex_lock(&w->gate);
    w->info.model=model;
    w->info.state=atomic_load(&w->stop)?LIE_STOPPING:rc==LIE_OK?LIE_READY:LIE_FAILED;
    if (rc!=LIE_OK) snprintf(w->info.error,sizeof(w->info.error),"%s",error.message);
    pthread_mutex_unlock(&w->gate); signal_fd(w->notice);
    for (;;) {
        bool progress=false; size_t present=0;
        for (size_t i=0;i<LIE_WORKER_JOBS;++i) {
            /* Only the worker removes slots; producer publication is under gate. */
            pthread_mutex_lock(&w->gate); bool has=w->jobs[i]!=NULL; pthread_mutex_unlock(&w->gate);
            if (has) { ++present; progress=step(w,i) || progress; }
        }
        if (atomic_load(&w->stop) && !present) break;
        if (progress) continue;
        struct pollfd fds[LIE_WORKER_JOBS+1]; size_t count=1;
        fds[0]=(struct pollfd){w->wake,POLLIN,0};
        pthread_mutex_lock(&w->gate);
        for (size_t i=0;i<LIE_WORKER_JOBS;++i) if (w->jobs[i]) {
            fds[count++]=(struct pollfd){lie_flow_fd(w->jobs[i]->flow,LIE_FLOW_WORK_READY),POLLIN,0};
        }
        pthread_mutex_unlock(&w->gate);
        int result; do { result=poll(fds,count,-1); } while (result<0 && errno==EINTR);
        if (result<0) abort();
        for (size_t i=0;i<count;++i) if (fds[i].revents&POLLIN) drain_fd(fds[i].fd);
    }
    if (w->model) (void)lie_model_close(&w->model,&error);
    pthread_mutex_lock(&w->gate); w->info.state=LIE_STOPPED; pthread_mutex_unlock(&w->gate);
    signal_fd(w->notice); return NULL;
}
lie_worker *lie_worker_create(const lie_worker_options *o) {
    if (!o || !o->model_path || !*o->model_path || o->context<128 || o->context>32768 ||
        !o->chunk || o->chunk>2048 || !o->max_active || o->max_active>2) return NULL;
    lie_worker *w=calloc(1,sizeof(*w)); if (!w) return NULL;
    w->wake=w->notice=-1; w->options=*o; w->path=strdup(o->model_path);
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
void lie_worker_stop(lie_worker *w) {
    atomic_store(&w->stop,true);
    pthread_mutex_lock(&w->gate);
    if (w->info.state!=LIE_STOPPED) w->info.state=LIE_STOPPING;
    pthread_mutex_unlock(&w->gate); signal_fd(w->wake);
}
void lie_worker_destroy(lie_worker *w) {
    lie_worker_info info; lie_worker_snapshot(w,&info); if (info.state!=LIE_STOPPED) abort();
    pthread_join(w->thread,NULL); close(w->wake); close(w->notice);
    pthread_mutex_destroy(&w->gate); free(w->path); free(w);
}
int lie_worker_fd(lie_worker *w) { return w->notice; }
void lie_worker_drain(lie_worker *w) { drain_fd(w->notice); }
int lie_worker_submit(lie_worker *w, lie_chat_request *request, lie_job **out) {
    if (!w || !request || !request->count || request->count>LIE_CHAT_MAX_MESSAGES ||
        !request->max_tokens || request->max_tokens>LIE_CHAT_MAX_OUTPUT || !out || *out) return 3;
    lie_job *j=calloc(1,sizeof(*j)); if (!j) return 3;
    lie_flow_options options={LIE_OUTPUT_SLOTS,LIE_CHAT_TOKEN_BYTES,65536};
    if (lie_flow_create(&options,&j->flow)!=LIE_FLOW_OK) { free(j); return 3; }
    if (pthread_mutex_init(&j->gate,NULL)) { (void)lie_flow_cancel(j->flow); (void)lie_flow_destroy(&j->flow); free(j); return 3; }
    atomic_init(&j->refs,2); atomic_init(&j->cancel,false); j->owner=w;
    j->info.timing_valid=true;
    (void)lie_flow_request(j->flow,LIE_OUTPUT_SLOTS);
    pthread_mutex_lock(&w->gate);
    int result=0; size_t index=0;
    if (w->info.state!=LIE_READY || atomic_load(&w->stop)) result=1;
    else {
        while (index<LIE_WORKER_JOBS && w->jobs[index]) ++index;
        if (index==LIE_WORKER_JOBS) result=2;
    }
    if (!result) {
        j->request=*request; memset(request,0,sizeof(*request));
        w->jobs[index]=j; ++w->info.queued; *out=j;
    }
    pthread_mutex_unlock(&w->gate);
    if (result) {
        (void)lie_flow_cancel(j->flow); atomic_store(&j->refs,1); job_drop(j); return result;
    }
    signal_fd(w->wake); signal_fd(w->notice); return 0;
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
    lie_worker *w=j->owner;
    if (first) {
        pthread_mutex_lock(&w->gate);
        if (w->dispatch==j) {
            if (w->info.executor_phase==LIE_EXECUTOR_PREFILL) ++w->info.cancel_during_prefill;
            else if (w->info.executor_phase==LIE_EXECUTOR_DECODE) ++w->info.cancel_during_decode;
        }
        pthread_mutex_unlock(&w->gate);
    }
    (void)lie_flow_cancel(j->flow); signal_fd(w->wake);
}
void lie_job_release(lie_job *j) { lie_job_cancel(j); job_drop(j); }
