/* SPDX-License-Identifier: MIT */
#ifndef LIE_WORKER_H
#define LIE_WORKER_H
#include "lie/chat.h"
#include "lie/flow.h"
#include <stdint.h>
#define LIE_WORKER_JOBS 8
#define LIE_OUTPUT_SLOTS 8

typedef struct lie_worker lie_worker;
typedef struct lie_job lie_job;
typedef enum { LIE_LOADING, LIE_READY, LIE_FAILED, LIE_STOPPING, LIE_STOPPED } lie_worker_state;
/* Owner dispatch interval, not proof that a GPU kernel is running. */
typedef enum { LIE_EXECUTOR_IDLE, LIE_EXECUTOR_PREFILL, LIE_EXECUTOR_DECODE } lie_executor_phase;
typedef enum { LIE_FINISH_NONE, LIE_FINISH_STOP, LIE_FINISH_LENGTH, LIE_FINISH_CANCEL,
               LIE_FINISH_INVALID, LIE_FINISH_BACKEND } lie_job_finish;
typedef struct {
    const char *model_path;
    uint32_t context, chunk, max_active;
} lie_worker_options;
typedef struct {
    lie_worker_state state;
    unsigned queued, active, output_blocked;
    lie_executor_phase executor_phase;
    uint64_t prefill_started, prefill_returned, decode_started, decode_returned;
    uint64_t decode_batches, decode_batch_rows, decode_single_calls;
    uint64_t cancel_during_prefill, cancel_during_decode;
    /* Executor outcomes, not client receipt. Later transport abandonment may
     * cancel a completed flow without changing a retired generation outcome. */
    uint64_t generated_tokens, completed_requests, cancelled_requests, failed_requests;
    lie_model_info model;
    char error[256];
} lie_worker_info;
typedef struct {
    unsigned prompt_tokens, output_tokens;
    lie_job_finish finish;
    bool prepared, retired;
    /* Sum of wall durations around synchronous executor calls, not phase span
     * or GPU-only time. Shared batch durations overlap across requests.
     * Calls count returns (including EOS/error/cancellation);
     * prefill_tokens counts only successfully completed physical input deltas.
     * Failure/regression/overflow of the monotonic clock latches invalid.
     * Timing and token counts are published before the flow terminal. */
    bool timing_valid;
    unsigned prefill_tokens, prefill_calls, decode_calls;
    uint64_t prefill_ns, decode_ns;
    char error[256];
} lie_job_info;

/* Worker alone calls blocking model/session APIs. The cancellation latch is
 * the sole exception, protected against handle detachment by the job gate.
 * No blocking backend work is performed under either metadata gate. */
lie_worker *lie_worker_create(const lie_worker_options *);
void lie_worker_stop(lie_worker *);
/* Call only after STOPPED and after releasing all consumer job references. */
void lie_worker_destroy(lie_worker *);
void lie_worker_snapshot(lie_worker *, lie_worker_info *);
int lie_worker_fd(lie_worker *);
void lie_worker_drain(lie_worker *);
/* Takes request ownership only on success. Queued+executing bounded to eight.
 * 0 success, 1 not ready, 2 queue full, 3 allocation/configuration error. */
int lie_worker_submit(lie_worker *, lie_chat_request *, lie_job **out);
lie_flow *lie_job_flow(lie_job *);
void lie_job_snapshot(lie_job *, lie_job_info *);
void lie_job_cancel(lie_job *);
/* Consumer retires its borrowed output loan/poll handle first. Worker reference
 * keeps in-flight jobs alive after client disconnect. No backend call here. */
void lie_job_release(lie_job *);
#endif
