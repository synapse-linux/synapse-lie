/* SPDX-License-Identifier: MIT */
#ifndef LIE_CORE_H
#define LIE_CORE_H
#include "lie/executor.h"
#include "lie/mtp.h"
#include "lie/vision.h"
#include "lie/steering.h"
#include "lie/flow.h"
#include "lie/store.h"
#include <stdbool.h>
#include <stdint.h>

#define LIE_CORE_JOBS 8
#define LIE_OUTPUT_SLOTS 8
#define LIE_CORE_MAX_CONTEXT LIE_CONTEXT_LIMIT
#define LIE_CORE_MAX_OUTPUT 4096u
#define LIE_CORE_TOKEN_BYTES 256u
#define LIE_CORE_INPUT_BYTES (32u * 1024u * 1024u)
#define LIE_CORE_REQUEST_ABI 8u
#define LIE_STOP_MAX 4u
#define LIE_STOP_BYTES 256u
#define LIE_PREFIX_CACHE_DEFAULT_BYTES (UINT64_C(4) * 1024u * 1024u * 1024u)
typedef struct {
    uint64_t budget_bytes, retained_bytes, peak_retained_bytes;
    uint64_t index_bytes, index_budget_bytes;
    uint64_t lookups, hits, misses, reused_tokens, captures, evictions, skipped;
    uint64_t expanded_bytes, compression_attempts, compressed_captures;
    bool utility_policy, compression_enabled;
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
    const lie_image_input *images;
    size_t image_count;
    lie_tool_choice tool_choice;
    bool parallel_tool_calls;
    const char *named_tool;
    const int32_t *tokens;
    size_t token_count;
    const char *text;
    size_t text_bytes;
    unsigned max_tokens; /* Zero: min(remaining context, LIE_CORE_MAX_OUTPUT),
                          * resolved after prompt preparation on the owner.
                          * Nonzero: exact caller budget, never silently capped. */
    lie_generation_options generation;
    lie_output_format format;
    const char *schema_json;
    bool strict;
    bool truncate_oldest; /* Preserve system messages and the latest user turn. */
    const char *stop[LIE_STOP_MAX];
    size_t stop_count;
    lie_cache_metadata cache; /* Optional client-owned visible key / extension bytes. */
    lie_eos_policy eos_policy; /* Default STOP. IGNORE: raw text/tokens only,
                               * no stop strings or constrained output. */
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
    const char *mtp_model_path; /* Explicit sidecar; NULL preserves AR. */
    uint32_t mtp_draft_tokens; /* Zero selects this model provider's default. */
    const char *vision_model_path; /* Explicit encoder admission. */
    uint32_t context, chunk, max_active;
    lie_rope_profile rope_profile; /* Native default; explicit extended profile. */
    uint64_t prefix_cache_bytes; /* Zero explicitly disables RAM retention. */
    lie_cache_policy cache_policy;
    lie_store_options ssd; /* Explicit directory enables; zero defaults off. */
} lie_core_options;
/* RAM enabled by default; independent SSD persistence is opt-in. */
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
    uint64_t output_validation_errors; /* Semantic output; executor counts stay physical. */
    uint64_t mtp_drafted, mtp_accepted;
    lie_prefix_cache_info cache;
    lie_cache_policy cache_policy;
    lie_store_info ssd;
    lie_model_info model;
    lie_rope_profile rope_profile;
    lie_mtp_info mtp;
    lie_vision_info vision;
    char error[256];
} lie_core_info;
typedef struct {
    unsigned prompt_tokens, output_tokens;
    unsigned output_token_limit; /* Zero before preparation; then the resolved
                                 * exact generation budget, including auto. */
    lie_job_finish finish;
    bool prepared, retired;
    bool semantic_checked, output_invalid;
    unsigned tool_calls;
    /* Completed executor-call wall durations. Shared batch durations overlap
     * across jobs; they exclude queue/flow/client waits and are not GPU-only. */
    bool timing_valid;
    unsigned prefill_tokens, prefill_calls, decode_calls;
    uint32_t max_decode_output_tokens; /* Admitted completed burst, AR = 1. */
    uint64_t mtp_drafted, mtp_accepted;
    uint64_t prefill_ns, decode_ns;
    unsigned cached_tokens;
    uint64_t cache_capture_ns, cache_restore_ns;
    unsigned ssd_cached_tokens;
    uint64_t ssd_read_ns; /* File read/validation, excludes owner GPU upload. */
    char error[256];
} lie_job_info;

/* One device owner; cancellation is a lifetime-protected cross-thread latch.
 * Request/metadata APIs never call the numerical provider on client threads. */
lie_core *lie_core_create(const lie_core_options *);
/* Explicit initial model-wide directions. Both option structures and the path
 * are copied before return; admission/load runs on the existing device owner.
 * NULL preserves lie_core_create's exact absent-bank provider path. Existing
 * unversioned options/info layouts and request ABI are unchanged. */
lie_core *lie_core_create_steered(const lie_core_options *,
                                  const lie_steering_model_options *);
/* READY-only admission record copied under the core gate; never a provider
 * call on the client. Tagged output required; refusal leaves it unchanged.
 * Host vector bytes and provider-reported device vector bytes are separate
 * from model weights/KV and do not include allocation overhead/workspaces. */
lie_status lie_core_steering_snapshot(lie_core *, lie_steering_model_info *, lie_error *);
/* Copied last completed owner observation; callable from clients in any state.
 * No numerical provider call, lock overlap, thread or device synchronization.
 * Tagged output required; unavailable observations never imply zero GPU work. */
lie_status lie_core_attention_dispatch_snapshot(lie_core *,
  lie_attention_dispatch_info *, lie_error *);
#define LIE_JOB_STEERING_ABI 1u
typedef struct {
    uint32_t abi_version, struct_bytes;
    bool policy_ready, pending;
    uint64_t submitted, completed, applied_position;
    lie_status status; /* Latest completed change; pending is separate. */
    lie_steering_settings requested;
    lie_steering_policy_info policy; /* Last owner-confirmed retained frontier. */
    unsigned char semantic_scope[32], combined_scope[32];
    char error[256];
} lie_job_steering_info;
/* One pending copied change per job; no provider call, wait or added thread.
 * Ticket output stays unchanged on refusal. Success means admission only:
 * observe completed==ticket and status in the snapshot. The existing owner
 * applies at a scheduling boundary; an already selected call can finish first.
 * applied_position names the retained boundary, never a promised output index.
 * Latest completion is retained until the next completion, including retirement.
 * Caller must hold a live job pin; scales require a model-admitted bank. */
lie_status lie_job_change_steering(lie_job *, const lie_steering_settings *,
                                  uint64_t *ticket, lie_error *);
lie_status lie_job_steering_snapshot(lie_job *, lie_job_steering_info *, lie_error *);
#define LIE_STEERING_SCHEDULE_ABI 1u
#define LIE_STEERING_SCHEDULE_MAX 64u
typedef struct {
    uint64_t position; /* Retained physical frontier, including prompt positions. */
    lie_steering_settings settings;
} lie_steering_step;
typedef struct {
    uint32_t abi_version, struct_bytes;
    size_t count;
    const lie_steering_step *steps;
} lie_steering_schedule;
typedef struct {
    bool attempted, applied;
    lie_status status;
    uint64_t actual_position;
} lie_steering_step_result;
typedef struct {
    uint32_t abi_version, struct_bytes;
    size_t count, completed, applied;
    bool terminal;
    lie_steering_step steps[LIE_STEERING_SCHEDULE_MAX];
    lie_steering_step_result results[LIE_STEERING_SCHEDULE_MAX];
} lie_steering_schedule_info;
/* Admission copies 1..64 strictly increasing steps before job publication.
 * Position zero changes the initial session policy before cache lookup; later
 * boundaries split prefill and limit each row's retained AR/MTP burst. Existing
 * logits/tensors remain unchanged. Cache reuse cannot cross an unapplied step.
 * Positions must fit the prepared prompt plus output budget; natural EOS can
 * retire before a step, which remains unapplied/Cancelled in the final snapshot.
 * Live unscheduled changes are refused for planned jobs to preserve identity.
 * NULL schedule preserves lie_core_submit. Return codes are those of submit. */
int lie_core_submit_steering(lie_core *, const lie_core_request *,
                              const lie_steering_schedule *, lie_job **out);
/* Tagged snapshot, unchanged on refusal. No plan reports count zero. */
lie_status lie_job_steering_schedule_snapshot(lie_job *,
                                             lie_steering_schedule_info *, lie_error *);
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
/* Independent owned metadata copy; caller clears it with lie_cache_metadata_clear. */
bool lie_job_cache_metadata(lie_job *,lie_cache_metadata *);
/* Stable snapshots copied while holding metadata ownership. Prompt requires
 * prepared=true; output IDs are validated model output, not delivery receipts.
 * BUFFER_SMALL reports required count; no partial copy or provider call. */
lie_status lie_job_prompt_tokens(lie_job *, int32_t *, size_t, size_t *);
lie_status lie_job_output_tokens(lie_job *, int32_t *, size_t, size_t *);
/* Completed target logit witnesses. Opt-in: ordinary requests do not copy
 * logits or change their speculative dispatch width. */
lie_status lie_job_logprobs(lie_job *, size_t offset, lie_token_logprobs *,
                            size_t capacity, size_t *required);
/* Release any output loan first. In-flight work retains the core job. */
void lie_job_release(lie_job *);
lie_status lie_job_logprob(lie_job *,size_t index,lie_token_logprobs *);
void lie_job_retain(lie_job *); /* Caller already owns a live reference. */
size_t lie_job_retention_bytes(lie_job *); /* Conservative, excludes model/KV cache. */
#endif
