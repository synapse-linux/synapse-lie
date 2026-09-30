/* SPDX-License-Identifier: MIT */
/* Historical reference-only Gufo interoperability ABI, NOT the production LIE
 * backend or its numerical/device ABI. See docs/BACKEND.md and docs/ABI.md. */
#ifndef LIE_EXECUTOR_H
#define LIE_EXECUTOR_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_EXECUTOR_ABI 1u
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
lie_status lie_sequence_create(lie_model *, lie_sequence **out, lie_error *);
lie_status lie_sequence_close(lie_sequence **, lie_error *);
/* Append-only cumulative physical token prefix. Delta <= configured chunk.
 * Prefix mismatch/refusal occurs before GPU submission; no arbitrary truncate. */
lie_status lie_sequence_prefill(lie_sequence *, const int32_t *prefix, size_t tokens, lie_error *);
/* AR only, greedy, one confirmed token maximum. Sampling state is per sequence. */
lie_status lie_sequence_decode(lie_sequence *, lie_decode_result *, lie_error *);
lie_status lie_sequence_logits(lie_sequence *, float *out, size_t capacity, size_t *required, lie_error *);
/* Thread-safe latch only; no GPU preemption. In-flight work completes; its
 * output is suppressed on cancellation. Lifetime must be pinned externally. */
void lie_sequence_cancel(lie_sequence *);
#ifdef __cplusplus
}
#endif
#endif
