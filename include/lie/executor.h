/* SPDX-License-Identifier: MIT */
/* Experimental transitional execution ABI; linking is opt-in, qualification separate.
 * Not an autonomous LIE backend or its eventual numerical/device ABI.
 * Evolve behind LIE-owned contracts: see docs/BACKEND.md and docs/ABI.md. */
#ifndef LIE_EXECUTOR_H
#define LIE_EXECUTOR_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_EXECUTOR_ABI 2u
typedef struct lie_model lie_model;
typedef struct lie_sequence lie_sequence;
typedef enum {
    LIE_OK = 0, LIE_INVALID = 1, LIE_UNSUPPORTED = 2, LIE_BUFFER_SMALL = 3,
    LIE_CANCELLED = 4, LIE_BACKEND_FAILED = 5, LIE_WRONG_OWNER = 6
} lie_status;
typedef struct { char message[256]; } lie_error;
typedef struct {
    uint32_t abi_version;
    uint32_t struct_bytes;
    uint32_t context_tokens;
    uint32_t prefill_chunk_tokens;
} lie_model_options;
typedef struct {
    uint32_t abi_version, context_tokens, vocab_tokens, prefill_capacity;
    uint32_t native_batch_capacity; /* Exposed adapter capacity, not a GPU claim. */
    uint32_t speculative_supported;
    uint64_t weights_bytes, session_bytes, deferred_workspace_bytes;
} lie_model_info;
typedef struct { int32_t token; uint32_t emitted, stop, position; } lie_decode_result;
typedef enum { LIE_CHAT_SYSTEM, LIE_CHAT_USER, LIE_CHAT_ASSISTANT, LIE_CHAT_TOOL } lie_chat_role;
typedef struct { lie_chat_role role; const char *content; size_t bytes; } lie_chat_message;
#define LIE_CHAT_BODY_BYTES (1024u * 1024u)
#define LIE_CHAT_MAX_MESSAGES 128u
#define LIE_CHAT_MAX_TOOLS 128u
#define LIE_CHAT_MAX_CALLS 16u
#define LIE_CHAT_MAX_ARGUMENTS 128u
/* Additive text-template entry point; existing ABI-2 structs/layouts unchanged.
 * Strings are NUL-terminated, pointers borrowed until the completed call returns.
 * No upstream types or executable tool callbacks cross this interface. */
typedef struct { const char *name, *value; uint32_t is_string; } lie_tool_argument;
typedef struct {
    const char *id, *name;
    const lie_tool_argument *arguments;
    size_t argument_count;
} lie_tool_call;
typedef struct {
    const char *tool_call_id, *name;
    const lie_tool_call *calls;
    size_t call_count;
} lie_chat_details;
typedef struct {
    const char *name, *description, *parameters_json, *definition_json;
} lie_chat_tool;
typedef struct {
    const lie_chat_message *messages;
    const lie_chat_details *details; /* Optional for ordinary text-only history. */
    size_t count;
    const lie_chat_tool *tools;
    size_t tool_count;
    uint32_t require_tool_call;
} lie_chat_template;
/* Additive generation controls; default initialization is greedy. The caller
 * supplies ABI/version size; configuration occurs before any prefill/dispatch. */
#define LIE_GENERATION_ABI 1u
typedef struct {
    uint32_t abi_version, struct_bytes;
    double temperature, top_p, frequency_penalty, presence_penalty;
    int64_t seed; /* -1 = provider entropy; nonnegative = reproducible draw seed. */
} lie_generation_options;
lie_status lie_sequence_configure(lie_sequence *,const lie_generation_options *,lie_error *);
/* Link-time selected provider, never an automatic failure fallback. */
const char *lie_backend_name(void);
const char *lie_backend_ownership(void);
const char *lie_backend_source_pin(void);
int lie_backend_is_synthetic(void);
/* Selected composition binding; the scheduler does not select/fallback engines. */
lie_status lie_backend_open(const char *, const lie_model_options *, lie_model **, lie_error *);
/* Additive explicit capacity at model admission. Existing open retains width 1. */
#define LIE_DECODE_MAX_ROWS 8u
lie_status lie_backend_open_batch(const char *, const lie_model_options *, uint32_t,
                                  lie_model **, lie_error *);
/* Experimental blocking ABI. All operations except cancel must be called by
 * the same device worker that opened the model. No independent scheduler in
 * the adapter. C pointers/lengths are borrowed for the duration of the call.
 * Success means completion, not enqueue. FAILED poisons the model instance;
 * it must not be retried or treated as a cache miss. No CPU-forward fallback.
 * No handle can be freed while another thread can still cancel/use it. */
lie_status lie_gufo_open(const char *path, const lie_model_options *, lie_model **out, lie_error *);
lie_status lie_model_get_info(lie_model *, lie_model_info *, lie_error *);
lie_status lie_model_close(lie_model **, lie_error *);
lie_status lie_model_tokenize(lie_model *, const char *utf8, size_t bytes,
                              int32_t *out, size_t capacity, size_t *required, lie_error *);
lie_status lie_model_token_text(lie_model *, int32_t token, char *out, size_t capacity,
                                size_t *required, lie_error *);
/* Bounded text-only Qwen rendering, thinking disabled; caller owns token buffer.
 * BUFFER_SMALL reports required physical tokens without creating/mutating a session. */
lie_status lie_model_chat_tokens(lie_model *, const lie_chat_message *, size_t count,
                                 int32_t *out, size_t capacity, size_t *required, lie_error *);
lie_status lie_model_chat_tokens_ex(lie_model *, const lie_chat_template *,
                                    int32_t *out, size_t capacity, size_t *required, lie_error *);
lie_status lie_sequence_create(lie_model *, lie_sequence **out, lie_error *);
lie_status lie_sequence_close(lie_sequence **, lie_error *);
/* Append-only cumulative physical token prefix. Delta <= configured chunk.
 * Prefix mismatch/refusal occurs before GPU submission; no arbitrary truncate. */
lie_status lie_sequence_prefill(lie_sequence *, const int32_t *prefix, size_t tokens, lie_error *);
/* AR only, one confirmed token maximum. Sampling state is per sequence. */
lie_status lie_sequence_decode(lie_sequence *, lie_decode_result *, lie_error *);
typedef struct { lie_status status; lie_decode_result result; } lie_decode_outcome;
/* Completed independent rows, same model/owner, unique handles, 1..admitted width.
 * Cancelled rows have no publishable output. Any non-cancellation execution
 * failure poisons the shared model and invalidates every output from this call.
 * LIE never retries a failed batch. Upstream may internally recover an untouched
 * row; this remains delegated behavior, not a LIE scheduling retry. */
lie_status lie_sequences_decode(lie_sequence *const *, size_t,
                                lie_decode_outcome *, lie_error *);
lie_status lie_sequence_logits(lie_sequence *, float *out, size_t capacity, size_t *required, lie_error *);
/* Thread-safe latch only; no GPU preemption. In-flight work completes; its
 * output is suppressed on cancellation. Lifetime must be pinned externally. */
void lie_sequence_cancel(lie_sequence *);
#ifdef __cplusplus
}
#endif
#endif
