/* SPDX-License-Identifier: MIT */
/* Small deterministic capture fixture. NOT-INFERENCE; no weights or device. */
#include "lie/executor.h"
#include "lie/sampling.h"
#include "lie/sampling_distribution.h"
#include "lie/sampling_observer.h"
#include "../tools/sampling-capture-format.h"
#include <math.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
struct lie_model { unsigned context, drafts; bool nonfinite, fail, tools, invalid_outcome; };
struct lie_sequence {
    lie_model *model;
    unsigned position;
    lie_sampling_options options;
    uint64_t rng;
    uint32_t generated[17];
    uint32_t history[8192], pending_token;
    bool pending;
    bool stop_at_eos, constrained;
};
static const char *tool_pieces[17] = {
    "<STOP>", "<tool_call>{\"name\":\"describe_stack\",\"arguments\":{\"order\":",
    "\"LIFO\"", "\"FIFO\"", ",\"size\":", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "}}</tool_call>", "ignored"
};
const char *lie_backend_name(void) { return "sampling-capture-fixture-NOT-INFERENCE"; }
const char *lie_backend_source_pin(void) { return "synthetic-capture-only"; }
const char *lie_backend_dense_sampling(void) { return "fixture-C17"; }
int lie_backend_is_synthetic(void) { return 1; }
lie_status lie_backend_open(const char *path, const lie_model_options *o, lie_model **out, lie_error *error) {
    (void)error;
    if (strcmp(path, ":fixture:") && strcmp(path, ":nan:") && strcmp(path, ":failure:") &&
        strcmp(path, ":tools:") && strcmp(path, ":tools-nan:") && strcmp(path, ":mtp-frontier:")) return LIE_INVALID;
    *out = calloc(1, sizeof(**out)); if (!*out) return LIE_BACKEND_FAILED;
    (*out)->context = o->context_tokens; (*out)->nonfinite = !strcmp(path, ":nan:");
    (*out)->fail = !strcmp(path, ":failure:"); (*out)->tools = !strncmp(path, ":tools", 6);
    (*out)->nonfinite |= !strcmp(path, ":tools-nan:");
    (*out)->invalid_outcome = !strcmp(path, ":mtp-frontier:"); return LIE_OK;
}
lie_status lie_model_token_text(lie_model *model, int32_t token, char *out,
        size_t capacity, size_t *required, lie_error *error) {
    (void)error;
    if (!model || !required || (!out && capacity) || token < 0 || token >= 17) return LIE_INVALID;
    const char *piece = tool_pieces[token]; *required = strlen(piece);
    if (*required > capacity) return LIE_BUFFER_SMALL;
    if (*required) memcpy(out, piece, *required);
    return LIE_OK;
}
lie_status lie_model_token_is_stop(lie_model *model, int32_t token, uint32_t *out, lie_error *error) {
    (void)error;
    if (!model || !out || token < 0 || token >= 17) return LIE_INVALID;
    *out = token == 0; return LIE_OK;
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
lie_status lie_model_chat_tokens_ex(lie_model *model, const lie_chat_template *input,
        int32_t *out, size_t capacity, size_t *required, lie_error *error) {
    if (!input || input->tool_count != 1 || !input->require_tool_call ||
        strcmp(input->tools[0].name, LIE_CAPTURE_TOOL_NAME)) return LIE_INVALID;
    return lie_model_chat_tokens(model, input->messages, input->count, out, capacity, required, error);
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
    (void)error;
    if (sequence->position || (policy != LIE_EOS_IGNORE && policy != LIE_EOS_STOP)) return LIE_INVALID;
    sequence->stop_at_eos = policy == LIE_EOS_STOP; return LIE_OK;
}
lie_status lie_sequence_constrain(lie_sequence *sequence, const lie_generation_constraints *c, lie_error *error) {
    (void)error;
    if (!c || !sequence->model->tools || !sequence->stop_at_eos || sequence->position ||
        c->format != LIE_FORMAT_JSON_OBJECT || c->tool_count != 1 || !c->required || c->parallel ||
        strcmp(c->tools[0].parameters_json, LIE_CAPTURE_TOOL_PARAMETERS) ||
        strcmp(c->tools[0].definition_json, LIE_CAPTURE_TOOL_DEFINITION)) return LIE_INVALID;
    sequence->constrained = true; return LIE_OK;
}
lie_status lie_sequence_prefill(lie_sequence *sequence, const int32_t *prompt, size_t count, lie_error *error) {
    (void)error; if (count != 5) return LIE_INVALID;
    for (size_t i = 0; i < count; ++i) sequence->history[i] = (uint32_t)prompt[i];
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
    uint8_t allowed[17] = {0};
    if (sequence->constrained) {
        switch (sequence->position - 5) {
        case 0: allowed[1] = 1; break;
        case 1: allowed[2] = allowed[3] = 1; break;
        case 2: allowed[4] = 1; break;
        case 3: for (unsigned i = 5; i <= 14; ++i) allowed[i] = 1; break;
        case 4: allowed[15] = 1; break;
        case 5: allowed[0] = 1; break;
        default: return LIE_INVALID;
        }
    }
    lie_sampling_row row = {.logits = logits, .count = 17, .penalties = penalties, .penalty_count = 17,
        .allowed = sequence->constrained ? allowed : NULL, .allowed_count = sequence->constrained ? 17 : 0};
    lie_sampling_probability entries[17]; lie_sampling_workspace workspace = {entries, 17, NULL, NULL};
    uint32_t token;
    if (lie_sampling_build(&row, &sequence->options, &workspace, &count) != LIE_SAMPLING_OK ||
        lie_sampling_draw(entries, count, &sequence->rng, &token) != LIE_SAMPLING_OK) return LIE_BACKEND_FAILED;
    if (sequence->stop_at_eos && token == 0) {
        *out = (lie_decode_result){-1, 0, 1, sequence->position}; return LIE_OK;
    }
    ++sequence->generated[token];
    sequence->history[sequence->position] = token;
    *out = (lie_decode_result){(int32_t)token, 1, 0, ++sequence->position}; return LIE_OK;
}
lie_status lie_backend_open_mtp(const char *path, const lie_model_options *options, uint32_t width,
    const char *predictor, uint32_t drafts, lie_model **model, lie_error *error) {
    if (width != 1 || !predictor || strcmp(predictor, ":predictor:") || drafts < 1 || drafts > 7) return LIE_INVALID;
    lie_status status = lie_backend_open(path, options, model, error);
    if (status == LIE_OK) (*model)->drafts = drafts;
    return status;
}
lie_status lie_model_mtp_info(lie_model *model, lie_mtp_info *info, lie_error *error) {
    (void)error;
    if (!model || !model->drafts || !info || info->abi_version != LIE_MTP_ABI || info->struct_bytes != sizeof(*info)) return LIE_INVALID;
    *info = (lie_mtp_info){LIE_MTP_ABI, sizeof(*info), model->drafts, model->drafts + 1, 0}; return LIE_OK;
}
static bool fixture_mask(const lie_sequence *sequence, unsigned position, uint8_t mask[17]) {
    memset(mask, 0, 17);
    if (!sequence->constrained) return true;
    switch (position - 5) {
    case 0: mask[1] = 1; break;
    case 1: mask[2] = mask[3] = 1; break;
    case 2: mask[4] = 1; break;
    case 3: for (unsigned i = 5; i <= 14; ++i) mask[i] = 1; break;
    case 4: mask[15] = 1; break;
    case 5: mask[0] = 1; break;
    default: return false;
    }
    return true;
}
static size_t fixture_penalties(const uint32_t *history, size_t length, const uint32_t generated[17],
    lie_sampling_penalty penalties[17], const lie_sampling_options *options) {
    uint32_t repeated[17] = {0}; size_t count = 0;
    if (options->repeat_penalty != 1)
        for (size_t i = length > 64 ? length - 64 : 0; i < length; ++i) repeated[history[i]] = 1;
    const bool generated_penalties = options->frequency_penalty != 0 || options->presence_penalty != 0;
    for (unsigned i = 0; i < 17; ++i) {
        const uint32_t n = generated_penalties ? generated[i] : 0;
        if (n || repeated[i]) penalties[count++] = (lie_sampling_penalty){i, n, repeated[i]};
    }
    return count;
}
static void fixture_logits(unsigned position, float row[17]) {
    for (unsigned i = 0; i < 17; ++i) row[i] = (float)((i * 7 + position) % 29) * .125f;
}
static void fixture_observe(const lie_sampling_observer *observer, lie_sampling_observation *event,
    const uint32_t *history, unsigned length, const uint32_t generated[17], const lie_sampling_options *options) {
    lie_sampling_penalty penalties[17];
    event->abi_version = LIE_SAMPLING_OBSERVER_ABI; event->struct_bytes = sizeof(*event);
    event->history_count = length > 64 ? 64 : length;
    event->history = history + length - event->history_count;
    event->penalty_count = fixture_penalties(history, length, generated, penalties, options); event->penalties = penalties;
    observer->observe(observer->context, event);
}
static bool fixture_distribution(lie_sequence *sequence, const float logits[17], uint8_t mask[17],
    lie_sampling_probability entries[17], size_t *count) {
    lie_sampling_penalty penalties[17];
    size_t n = fixture_penalties(sequence->history, sequence->position, sequence->generated, penalties, &sequence->options);
    if (!fixture_mask(sequence, sequence->position, mask)) return false;
    lie_sampling_row row = {.logits = logits, .count = 17, .penalties = penalties, .penalty_count = n,
        .allowed = sequence->constrained ? mask : NULL, .allowed_count = sequence->constrained ? 17 : 0};
    lie_sampling_workspace workspace = {entries, 17, NULL, NULL};
    return lie_sampling_build(&row, &sequence->options, &workspace, count) == LIE_SAMPLING_OK;
}
lie_status lie_sequence_decode_mtp_observed(lie_sequence *sequence, uint32_t limit,
    const lie_sampling_observer *input, lie_mtp_outcome *out, lie_error *error) {
    if (!sequence || !out || !input || input->abi_version != LIE_SAMPLING_OBSERVER_ABI ||
        input->struct_bytes != sizeof(*input) || !input->observe || !limit || limit > sequence->model->drafts + 1) return LIE_INVALID;
    const lie_sampling_observer observer = *input;
    if (sequence->model->fail) { snprintf(error->message, sizeof(error->message), "synthetic MTP failure; no retry"); return LIE_BACKEND_FAILED; }
    const unsigned base = sequence->position; const uint64_t before = sequence->rng;
    const bool deferred = sequence->pending; uint32_t old_generated[17]; memcpy(old_generated, sequence->generated, sizeof(old_generated));
    float logits[17]; uint8_t mask[17]; lie_sampling_probability entries[17]; size_t count = 0;
    fixture_logits(base, logits); if (sequence->model->nonfinite) logits[7] = NAN;
    if (!fixture_distribution(sequence, logits, mask, entries, &count)) return LIE_BACKEND_FAILED;
    uint32_t anchor;
    if (deferred) { anchor = sequence->pending_token; sequence->pending = false; }
    else if (lie_sampling_draw(entries, count, &sequence->rng, &anchor) != LIE_SAMPLING_OK) return LIE_BACKEND_FAILED;
    lie_sampling_observation event = {.kind = LIE_SAMPLING_OBSERVE_TARGET_DRAW, .token = anchor, .deferred = deferred,
        .rng_before = before, .rng_after = sequence->rng, .logits = logits, .logit_count = 17,
        .allowed = sequence->constrained ? mask : NULL, .allowed_count = sequence->constrained ? 17 : 0};
    fixture_observe(&observer, &event, sequence->history, base, old_generated, &sequence->options);
    *out = (lie_mtp_outcome){.status = LIE_OK, .position = base};
    if (sequence->stop_at_eos && anchor == 0) { out->stop = 1; return LIE_OK; }
    sequence->history[sequence->position++] = anchor; ++sequence->generated[anchor];
    out->tokens[out->emitted++] = (int32_t)anchor;
    if (limit == 1) {
        out->position = sequence->position;
        if (sequence->model->invalid_outcome) { out->drafted = 1; out->accepted = 1; }
        return LIE_OK;
    }
    /* A deterministic toy controller only. No model forward, predictor or GPU. */
    if (!sequence->options.temperature) return LIE_INVALID;
    uint64_t draft_rng = lie_sampling_next_random(&sequence->rng);
    uint32_t draft_history[8192], draft_generated[17]; unsigned draft_length = sequence->position;
    memcpy(draft_history, sequence->history, draft_length * sizeof(*draft_history));
    memcpy(draft_generated, sequence->generated, sizeof(draft_generated));
    uint32_t qids[7][17]; float qprobabilities[7][17]; lie_sampling_proposal q[7];
    for (unsigned step = 0; step + 1 < limit; ++step) {
        uint32_t mapping[17]; float compact[17];
        for (unsigned i = 0; i < 17; ++i) { mapping[i] = (i * 5 + 3) % 17; compact[i] = (float)((i * 11 + draft_length + 7) % 31) * .125f; }
        lie_sampling_penalty penalties[17]; size_t n = fixture_penalties(draft_history, draft_length, draft_generated, penalties, &sequence->options);
        lie_sampling_probability p[17], scratch[17]; lie_sampling_workspace workspace = {p, 17, NULL, NULL}, work = {scratch, 17, NULL, NULL};
        lie_sampling_ranked_row row; lie_sampling_ranked_row_init(&row);
        row.logits = compact; row.count = 17; row.token_ids = mapping; row.token_id_count = 17; row.penalties = penalties; row.penalty_count = n;
        size_t used = 0; if (lie_sampling_distribution_ranked(&row, &sequence->options, &workspace, &work, &used) != LIE_SAMPLING_OK) return LIE_BACKEND_FAILED;
        lie_sampling_proposal_init(&q[step]); q[step].ids = qids[step]; q[step].probabilities = qprobabilities[step]; q[step].capacity = 17;
        const uint64_t rng = draft_rng;
        if (lie_sampling_proposal_quantize(p, used, mapping, 17, &draft_rng, &q[step]) != LIE_SAMPLING_OK) return LIE_BACKEND_FAILED;
        event = (lie_sampling_observation){.kind = LIE_SAMPLING_OBSERVE_PROPOSAL, .token = q[step].token,
            .rng_before = rng, .rng_after = draft_rng, .logits = compact, .logit_count = 17, .logit_ids = mapping,
            .proposal_ids = q[step].ids, .proposal_probabilities = q[step].probabilities, .proposal_count = q[step].count,
            .proposal_token = q[step].token, .proposal_probability = q[step].probability};
        fixture_observe(&observer, &event, draft_history, draft_length, draft_generated, &sequence->options);
        draft_history[draft_length++] = q[step].token; ++draft_generated[q[step].token]; ++out->drafted;
    }
    for (unsigned step = 0; step < out->drafted; ++step) {
        fixture_logits(sequence->position, logits);
        if (!fixture_distribution(sequence, logits, mask, entries, &count)) return LIE_BACKEND_FAILED;
        const uint64_t rng = sequence->rng; uint32_t token = 0; bool accepted = false;
        lie_sampling_probability d[17], r[17]; lie_sampling_workspace draft = {d, 17, NULL, NULL}, residual = {r, 17, NULL, NULL};
        lie_sampling_proposal_view view; lie_sampling_proposal_view_init(&view);
        view.ids = q[step].ids; view.probabilities = q[step].probabilities; view.count = q[step].count;
        view.token = q[step].token; view.probability = q[step].probability;
        if (lie_sampling_proposal_verify(entries, count, 17, &view, &draft, &residual, &sequence->rng, &token, &accepted) != LIE_SAMPLING_OK) return LIE_BACKEND_FAILED;
        event = (lie_sampling_observation){.kind = LIE_SAMPLING_OBSERVE_VERIFICATION, .token = token, .accepted = accepted,
            .rng_before = rng, .rng_after = sequence->rng, .logits = logits, .logit_count = 17,
            .allowed = sequence->constrained ? mask : NULL, .allowed_count = sequence->constrained ? 17 : 0,
            .proposal_ids = view.ids, .proposal_probabilities = view.probabilities, .proposal_count = view.count,
            .proposal_token = view.token, .proposal_probability = view.probability};
        fixture_observe(&observer, &event, sequence->history, sequence->position, sequence->generated, &sequence->options);
        if (sequence->stop_at_eos && token == 0) { out->stop = 1; break; }
        if (!accepted) { sequence->pending = true; sequence->pending_token = token; break; }
        sequence->history[sequence->position++] = token; ++sequence->generated[token];
        out->tokens[out->emitted++] = (int32_t)token; ++out->accepted;
    }
    out->position = sequence->position; return LIE_OK;
}
