/* SPDX-License-Identifier: MIT */
/* Small deterministic capture fixture. NOT-INFERENCE; no weights or device. */
#include "lie/executor.h"
#include "lie/sampling.h"
#include <math.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
struct lie_model { unsigned context; bool nonfinite, fail; };
struct lie_sequence {
    lie_model *model;
    unsigned position;
    lie_sampling_options options;
    uint64_t rng;
    uint32_t generated[17];
};
const char *lie_backend_name(void) { return "sampling-capture-fixture-NOT-INFERENCE"; }
const char *lie_backend_source_pin(void) { return "synthetic-capture-only"; }
const char *lie_backend_dense_sampling(void) { return "fixture-C17"; }
int lie_backend_is_synthetic(void) { return 1; }
lie_status lie_backend_open(const char *path, const lie_model_options *o, lie_model **out, lie_error *error) {
    (void)error;
    if (strcmp(path, ":fixture:") && strcmp(path, ":nan:") && strcmp(path, ":failure:")) return LIE_INVALID;
    *out = calloc(1, sizeof(**out)); if (!*out) return LIE_BACKEND_FAILED;
    (*out)->context = o->context_tokens; (*out)->nonfinite = !strcmp(path, ":nan:");
    (*out)->fail = !strcmp(path, ":failure:"); return LIE_OK;
}
lie_status lie_model_close(lie_model **model, lie_error *error) {
    (void)error; free(*model); *model = NULL; return LIE_OK;
}
lie_status lie_model_get_info(lie_model *model, lie_model_info *out, lie_error *error) {
    (void)error; *out = (lie_model_info){.abi_version = LIE_EXECUTOR_ABI,
        .context_tokens = model->context, .vocab_tokens = 17, .prefill_capacity = 2048}; return LIE_OK;
}
lie_status lie_model_chat_tokens(lie_model *model, const lie_chat_message *messages, size_t count,
        int32_t *out, size_t capacity, size_t *required, lie_error *error) {
    (void)model; (void)messages; (void)count; (void)error; *required = 5;
    if (capacity < *required) return LIE_BUFFER_SMALL;
    const int32_t prompt[] = {0, 3, 3, 8, 9}; memcpy(out, prompt, sizeof(prompt)); return LIE_OK;
}
lie_status lie_sequence_create(lie_model *model, lie_sequence **out, lie_error *error) {
    (void)error; *out = calloc(1, sizeof(**out)); if (!*out) return LIE_BACKEND_FAILED;
    (*out)->model = model; return LIE_OK;
}
lie_status lie_sequence_close(lie_sequence **out, lie_error *error) {
    (void)error; free(*out); *out = NULL; return LIE_OK;
}
lie_status lie_sequence_configure(lie_sequence *sequence, const lie_generation_options *o, lie_error *error) {
    (void)error;
    if (o->abi_version != LIE_GENERATION_ABI || o->struct_bytes != sizeof(*o) || sequence->position) return LIE_INVALID;
    lie_sampling_options_init(&sequence->options);
    sequence->options.temperature = (float)o->temperature; sequence->options.top_p = (float)o->top_p;
    sequence->options.top_k = o->top_k; sequence->options.min_p = (float)o->min_p;
    sequence->options.frequency_penalty = (float)o->frequency_penalty;
    sequence->options.presence_penalty = (float)o->presence_penalty; sequence->rng = (uint64_t)o->seed;
    return LIE_OK;
}
lie_status lie_sequence_set_eos_policy(lie_sequence *sequence, lie_eos_policy policy, lie_error *error) {
    (void)error; return !sequence->position && policy == LIE_EOS_IGNORE ? LIE_OK : LIE_INVALID;
}
lie_status lie_sequence_prefill(lie_sequence *sequence, const int32_t *prompt, size_t count, lie_error *error) {
    (void)prompt; (void)error; if (count != 5) return LIE_INVALID;
    sequence->position = (unsigned)count; return LIE_OK;
}
lie_status lie_sequence_logits(lie_sequence *sequence, float *out, size_t capacity, size_t *required, lie_error *error) {
    (void)error; *required = 17; if (capacity < 17) return LIE_BUFFER_SMALL;
    for (unsigned i = 0; i < 17; ++i) out[i] = (float)((i * 7 + sequence->position) % 29) * .125f;
    if (sequence->model->nonfinite) out[7] = NAN;
    return LIE_OK;
}
lie_status lie_sequence_decode(lie_sequence *sequence, lie_decode_result *out, lie_error *error) {
    if (sequence->model->fail) {
        snprintf(error->message, sizeof(error->message), "synthetic decode failure; no retry"); return LIE_BACKEND_FAILED;
    }
    float logits[17]; size_t count = 0; lie_sampling_penalty penalties[17];
    if (lie_sequence_logits(sequence, logits, 17, &count, error) != LIE_OK) return LIE_BACKEND_FAILED;
    for (unsigned i = 0; i < 17; ++i) penalties[i] = (lie_sampling_penalty){i, sequence->generated[i], 0};
    lie_sampling_row row = {.logits = logits, .count = 17, .penalties = penalties, .penalty_count = 17};
    lie_sampling_probability entries[17]; lie_sampling_workspace workspace = {entries, 17, NULL, NULL};
    uint32_t token;
    if (lie_sampling_build(&row, &sequence->options, &workspace, &count) != LIE_SAMPLING_OK ||
        lie_sampling_draw(entries, count, &sequence->rng, &token) != LIE_SAMPLING_OK) return LIE_BACKEND_FAILED;
    ++sequence->generated[token];
    *out = (lie_decode_result){(int32_t)token, 1, 0, ++sequence->position}; return LIE_OK;
}
