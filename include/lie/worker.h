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
typedef enum { LIE_FINISH_NONE, LIE_FINISH_STOP, LIE_FINISH_LENGTH, LIE_FINISH_CANCEL,
               LIE_FINISH_INVALID, LIE_FINISH_BACKEND } lie_job_finish;
typedef struct {
    const char *model_path;
    uint32_t context, chunk, max_active;
} lie_worker_options;
typedef struct {
    lie_worker_state state;
    unsigned queued, active;
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
