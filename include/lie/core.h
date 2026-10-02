/* SPDX-License-Identifier: MIT */
#ifndef LIE_CORE_H
#define LIE_CORE_H
#include "lie/executor.h"
#include "lie/flow.h"
#include <stdbool.h>
#include <stdint.h>

#define LIE_CORE_JOBS 8
#define LIE_OUTPUT_SLOTS 8
#define LIE_CORE_MAX_CONTEXT 262144u
#define LIE_CORE_MAX_OUTPUT 4096u
#define LIE_CORE_TOKEN_BYTES 256u
#define LIE_CORE_INPUT_BYTES (32u * 1024u * 1024u)
#define LIE_CORE_REQUEST_ABI 1u
#define LIE_PREFIX_CACHE_DEFAULT_BYTES (UINT64_C(4) * 1024u * 1024u * 1024u)
typedef struct {
    uint64_t budget_bytes, retained_bytes, peak_retained_bytes;
    uint64_t lookups, hits, misses, reused_tokens, captures, evictions, skipped;
    unsigned entries;
} lie_prefix_cache_info;
typedef enum { LIE_TOOLS_AUTO, LIE_TOOLS_NONE, LIE_TOOLS_REQUIRED, LIE_TOOLS_NAMED } lie_tool_choice;
typedef enum { LIE_INPUT_MESSAGES, LIE_INPUT_TOKENS, LIE_INPUT_TEXT } lie_input_kind;
/* Borrowed only for submit. Successful admission makes an independent bounded
 * copy; caller data can then be changed/freed. No protocol/parser ownership. */
typedef struct {
    uint32_t abi_version, struct_bytes;
    lie_input_kind kind;
    lie_chat_template chat;
    lie_tool_choice tool_choice;
    const char *named_tool;
    const int32_t *tokens;
    size_t token_count;
    const char *text;
    size_t text_bytes;
    unsigned max_tokens;
    lie_generation_options generation;
} lie_core_request;
void lie_core_request_init(lie_core_request *);

typedef struct lie_core lie_core;
typedef struct lie_job lie_job;
typedef enum { LIE_LOADING, LIE_READY, LIE_FAILED, LIE_STOPPING, LIE_STOPPED } lie_core_state;
typedef enum { LIE_EXECUTOR_IDLE, LIE_EXECUTOR_PREFILL, LIE_EXECUTOR_DECODE,
               LIE_EXECUTOR_CAPTURE, LIE_EXECUTOR_RESTORE } lie_executor_phase;
typedef enum { LIE_FINISH_NONE, LIE_FINISH_STOP, LIE_FINISH_LENGTH, LIE_FINISH_CANCEL,
               LIE_FINISH_INVALID, LIE_FINISH_BACKEND } lie_job_finish;
typedef struct {
    const char *model_path;
    uint32_t context, chunk, max_active;
    uint64_t prefix_cache_bytes; /* Zero explicitly disables RAM retention. */
} lie_core_options;
/* RAM enabled by default; SSD is a separate, currently unsupported facility. */
void lie_core_options_init(lie_core_options *);
typedef struct {
    lie_core_state state;
    unsigned queued, active, output_blocked;
    lie_executor_phase executor_phase;
    uint64_t prefill_started, prefill_returned, decode_started, decode_returned;
    uint64_t decode_batches, decode_batch_rows, decode_single_calls;
    uint64_t cancel_during_prefill, cancel_during_decode;
    /* Completed model output, not client delivery. */
    uint64_t generated_tokens, completed_requests, cancelled_requests, failed_requests;
    lie_prefix_cache_info cache;
    lie_model_info model;
    char error[256];
} lie_core_info;
typedef struct {
    unsigned prompt_tokens, output_tokens;
    lie_job_finish finish;
    bool prepared, retired;
    /* Completed executor-call wall durations. Shared batch durations overlap
     * across jobs; they exclude queue/flow/client waits and are not GPU-only. */
    bool timing_valid;
    unsigned prefill_tokens, prefill_calls, decode_calls;
    uint64_t prefill_ns, decode_ns;
    unsigned cached_tokens;
    uint64_t cache_capture_ns, cache_restore_ns;
    char error[256];
} lie_job_info;

/* One device owner; cancellation is a lifetime-protected cross-thread latch.
 * Request/metadata APIs never call the numerical provider on client threads. */
lie_core *lie_core_create(const lie_core_options *);
void lie_core_stop(lie_core *);
/* STOPPED and all consumer job references released are required. */
void lie_core_destroy(lie_core *);
void lie_core_snapshot(lie_core *, lie_core_info *);
int lie_core_fd(lie_core *);
void lie_core_drain(lie_core *);
/* 0 success, 1 not ready, 2 queue full, 3 invalid input/allocation failure.
 * Input remains caller-owned on every outcome. Queued+active bounded to eight. */
int lie_core_submit(lie_core *, const lie_core_request *, lie_job **out);
lie_flow *lie_job_flow(lie_job *);
void lie_job_snapshot(lie_job *, lie_job_info *);
void lie_job_cancel(lie_job *);
/* Stable snapshots copied while holding metadata ownership. Prompt requires
 * prepared=true; output IDs are validated model output, not delivery receipts.
 * BUFFER_SMALL reports required count; no partial copy or provider call. */
lie_status lie_job_prompt_tokens(lie_job *, int32_t *, size_t, size_t *);
lie_status lie_job_output_tokens(lie_job *, int32_t *, size_t, size_t *);
/* Release any output loan first. In-flight work retains the core job. */
void lie_job_release(lie_job *);
#endif
