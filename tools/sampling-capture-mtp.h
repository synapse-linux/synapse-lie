/* SPDX-License-Identifier: MIT */
/* Private C17 writer of borrowed numerical observations; no inference policy. */
#ifndef LIE_SAMPLING_CAPTURE_MTP_H
#define LIE_SAMPLING_CAPTURE_MTP_H
#include "lie/sampling_observer.h"
#define CAPTURE_TRACE_MAX (128u * 9u)
#define CAPTURE_TRACE_BYTES_MAX (UINT64_C(4) * 1024u * 1024u * 1024u)
typedef struct {
    int dir;
    FILE *file;
    unsigned profile, cycle, traces, vocab;
    uint64_t *bytes;
    bool failed;
} mtp_writer;
static json_object *u32_ids(const uint32_t *tokens, size_t count) {
    json_object *j = json_object_new_array();
    for (size_t i = 0; i < count; ++i)
        json_object_array_add(j, json_object_new_uint64(tokens[i]));
    return j;
}
static void rng_text(json_object *j, const char *key, uint64_t rng) {
    char value[17]; snprintf(value, sizeof(value), "%016llx", (unsigned long long)rng);
    text(j, key, value);
}
static bool unique_ids(const uint32_t *tokens, size_t count, unsigned vocab) {
    if (!tokens && count) return false;
    for (size_t i = 0; i < count; ++i) {
        if (tokens[i] >= vocab) return false;
        for (size_t k = 0; k < i; ++k) if (tokens[k] == tokens[i]) return false;
    }
    return true;
}
static bool trace_blob(mtp_writer *writer, const char *name, const void *data,
                       size_t bytes, json_object *object) {
    char hash[65];
    if (bytes > CAPTURE_TRACE_BYTES_MAX - *writer->bytes ||
        !write_blob(writer->dir, name, data, bytes, hash)) return false;
    *writer->bytes += bytes;
    text(object, "file", name); text(object, "sha256", hash); number(object, "bytes", bytes);
    return true;
}
static void capture_observation(void *context, const lie_sampling_observation *r) {
    mtp_writer *writer = context;
    if (writer->failed) return;
    if (!r) { writer->failed = true; return; }
    const bool proposal = r->kind == LIE_SAMPLING_OBSERVE_PROPOSAL;
    const bool verification = r->kind == LIE_SAMPLING_OBSERVE_VERIFICATION;
    bool valid = !interrupted && r->abi_version == LIE_SAMPLING_OBSERVER_ABI &&
        r->struct_bytes == sizeof(*r) && writer->traces < CAPTURE_TRACE_MAX &&
        (proposal || verification || r->kind == LIE_SAMPLING_OBSERVE_TARGET_DRAW) &&
        r->logits && r->logit_count && r->token < writer->vocab &&
        r->accepted <= 1 && r->deferred <= 1 && r->history_count <= 64 &&
        (r->history || !r->history_count) && r->penalty_count <= 256 &&
        (r->penalties || !r->penalty_count) &&
        (proposal ? r->logit_count <= 64 && unique_ids(r->logit_ids, r->logit_count, writer->vocab) :
                    r->logit_count == writer->vocab && !r->logit_ids) &&
        (!r->allowed_count || (!proposal && r->allowed_count == writer->vocab && r->allowed)) &&
        (proposal || verification ? r->proposal_count && r->proposal_count <= 64 &&
            unique_ids(r->proposal_ids, r->proposal_count, writer->vocab) && r->proposal_probabilities &&
            r->proposal_token < writer->vocab && isfinite(r->proposal_probability) &&
            r->proposal_probability > 0 && r->proposal_probability <= 1 : !r->proposal_count);
    for (size_t i = 0; valid && i < r->logit_count; ++i) valid = isfinite(r->logits[i]);
    for (size_t i = 0; valid && i < r->history_count; ++i) valid = r->history[i] < writer->vocab;
    for (size_t i = 0; valid && i < r->allowed_count; ++i) valid = r->allowed[i] <= 1;
    for (size_t i = 0; valid && i < r->penalty_count; ++i)
        valid = r->penalties[i].token < writer->vocab && r->penalties[i].generated_count <= 135 &&
            r->penalties[i].repeated <= 64 && (!i || r->penalties[i - 1].token < r->penalties[i].token);
    double total = 0, selected = 0;
    for (size_t i = 0; valid && i < r->proposal_count; ++i) {
        const float p = r->proposal_probabilities[i]; valid = isfinite(p) && p >= 0 && p <= 1;
        total += p; if (r->proposal_ids[i] == r->proposal_token) selected += p;
    }
    if (r->proposal_count) valid = valid && total == 1 && selected == r->proposal_probability;
    if (!valid) { writer->failed = true; return; }
    char name[80]; json_object *j = event("sampling_trace"), *raw = json_object_new_object();
    number(j, "profile", writer->profile); number(j, "cycle", writer->cycle); number(j, "index", writer->traces);
    text(j, "kind", proposal ? "proposal" : verification ? "verification" : "target-draw");
    number(j, "token", r->token); number(j, "accepted", r->accepted); number(j, "deferred", r->deferred);
    rng_text(j, "rng_before", r->rng_before); rng_text(j, "rng_after", r->rng_after);
    number(j, "logit_count", r->logit_count);
    snprintf(name, sizeof(name), "profile-%u-trace-%u.f32le", writer->profile, writer->traces);
    if (!trace_blob(writer, name, r->logits, r->logit_count * sizeof(float), raw)) {
        json_object_put(raw); json_object_put(j); writer->failed = true; return;
    }
    json_object_object_add(j, "raw", raw);
    json_object_object_add(j, "logit_ids", u32_ids(r->logit_ids, proposal ? r->logit_count : 0));
    json_object_object_add(j, "history_ids", u32_ids(r->history, r->history_count));
    json_object *penalties = json_object_new_array();
    for (size_t i = 0; i < r->penalty_count; ++i) {
        json_object *p = json_object_new_object();
        number(p, "token", r->penalties[i].token); number(p, "generated_count", r->penalties[i].generated_count);
        number(p, "repeated", r->penalties[i].repeated); json_object_array_add(penalties, p);
    }
    json_object_object_add(j, "penalties", penalties);
    json_object *mask = NULL;
    if (r->allowed_count) {
        mask = json_object_new_object();
        snprintf(name, sizeof(name), "profile-%u-trace-%u.u8", writer->profile, writer->traces);
        if (!trace_blob(writer, name, r->allowed, r->allowed_count, mask)) {
            json_object_put(mask); json_object_put(j); writer->failed = true; return;
        }
    }
    json_object_object_add(j, "allowed", mask);
    json_object *q = NULL;
    if (r->proposal_count) {
        q = json_object_new_object(); json_object *mass = json_object_new_array();
        for (size_t i = 0; i < r->proposal_count; ++i)
            json_object_array_add(mass, json_object_new_double(r->proposal_probabilities[i]));
        json_object_object_add(q, "ids", u32_ids(r->proposal_ids, r->proposal_count));
        json_object_object_add(q, "probabilities", mass); number(q, "token", r->proposal_token);
        json_object_object_add(q, "probability", json_object_new_double(r->proposal_probability));
    }
    json_object_object_add(j, "proposal", q);
    if (!emit(writer->file, j)) writer->failed = true;
    else ++writer->traces;
}
static bool capture_mtp(lie_model *model, const int32_t *prompt, size_t count,
    unsigned vocab, unsigned profile, unsigned budget, unsigned burst,
    int dir, FILE *file, bool tools, unsigned *rows_completed, uint64_t *written_bytes, lie_error *error) {
    static const char *names[CAPTURE_PROFILES] = {"greedy", "ds4-temperature1-minp", "top-k", "nucleus-minp",
        "generated-penalties", "temperature2-negative-penalties"};
    lie_generation_options options = generation(profile); lie_sequence *sequence = NULL;
    lie_chat_tool tool = tool_definition(); lie_output_turn turn = {0};
    mtp_writer writer = {.dir = dir, .file = file, .profile = profile, .vocab = vocab, .bytes = written_bytes};
    const lie_sampling_observer observer = {LIE_SAMPLING_OBSERVER_ABI, sizeof(observer), capture_observation, &writer};
    bool ok = false, stopped = false; unsigned emitted = 0, cycles = 0; int32_t output[128];
    char *reply = tools ? calloc(1, LIE_CAPTURE_OUTPUT_BYTES_MAX + 1) : NULL; size_t reply_bytes = 0;
    json_object *j = event("profile_begin"); number(j, "profile", profile); text(j, "name", names[profile]);
    number(j, "vocab", vocab); json_object_object_add(j, "generation", controls(&options));
    json_object_object_add(j, "prompt_ids", ids(prompt, count));
    if (tools) json_object_object_add(j, "constraint", constraint_identity());
    if (!emit(file, j) || lie_sequence_create(model, &sequence, error) != LIE_OK ||
        lie_sequence_configure(sequence, &options, error) != LIE_OK ||
        lie_sequence_set_eos_policy(sequence, tools ? LIE_EOS_STOP : LIE_EOS_IGNORE, error) != LIE_OK ||
        (tools && !reply)) goto done;
    if (tools) {
        const lie_generation_constraints constraint = {.format = LIE_FORMAT_JSON_OBJECT, .tools = &tool, .tool_count = 1, .required = 1};
        if (lie_sequence_constrain(sequence, &constraint, error) != LIE_OK) goto done;
    }
    for (size_t at = 0; at < count;) {
        at = count - at > CAPTURE_CHUNK ? at + CAPTURE_CHUNK : count;
        if (interrupted || lie_sequence_prefill(sequence, prompt, at, error) != LIE_OK) goto done;
    }
    while (emitted < budget && cycles < budget) {
        /* Greedy host-head baseline; GPU greedy verification has no raw host row. */
        const uint32_t limit = profile ? (budget - emitted < burst ? budget - emitted : burst) : 1;
        writer.cycle = cycles; lie_mtp_outcome result = {0};
        j = event("cycle_begin"); number(j, "profile", profile); number(j, "cycle", cycles);
        number(j, "position", count + emitted); number(j, "reservation", limit);
        if (!emit(file, j) || interrupted || lie_sequence_decode_mtp_observed(sequence, limit, &observer, &result, error) != LIE_OK ||
            writer.failed || result.status != LIE_OK || result.stop > 1 || result.emitted > limit ||
            (!result.emitted && !result.stop) || (!tools && result.stop) ||
            result.position != count + emitted + result.emitted || result.drafted >= limit ||
            result.accepted > result.drafted || result.accepted != (result.emitted ? result.emitted - 1 : 0)) goto done;
        for (uint32_t i = 0; i < result.emitted; ++i) {
            const int32_t token = result.tokens[i];
            if (token < 0 || (unsigned)token >= vocab) goto done;
            output[emitted++] = token;
            if (tools) {
                size_t bytes = 0; uint32_t stop_token = 0;
                if (lie_model_token_text(model, token, reply + reply_bytes, LIE_CAPTURE_OUTPUT_BYTES_MAX - reply_bytes, &bytes, error) != LIE_OK ||
                    bytes > LIE_CAPTURE_OUTPUT_BYTES_MAX - reply_bytes || lie_model_token_is_stop(model, token, &stop_token, error) != LIE_OK ||
                    stop_token || memchr(reply + reply_bytes, 0, bytes)) goto done;
                reply_bytes += bytes; reply[reply_bytes] = 0;
            }
        }
        j = event("cycle_complete"); number(j, "profile", profile); number(j, "cycle", cycles);
        number(j, "position", result.position); number(j, "drafted", result.drafted); number(j, "accepted", result.accepted);
        json_object_object_add(j, "stop", json_object_new_boolean(result.stop));
        json_object_object_add(j, "output_ids", ids(result.tokens, result.emitted));
        if (!emit(file, j)) goto done;
        ++cycles; if (result.stop) { stopped = true; break; }
    }
    if (tools) {
        const lie_output_policy policy = {&tool, 1, LIE_TOOLS_REQUIRED, false, NULL};
        if (!stopped || !lie_output_parse(&policy, reply, reply_bytes, true, "sampling-capture", &turn, error->message) ||
            turn.count != 1 || turn.bytes || strcmp(turn.calls[0].name, LIE_CAPTURE_TOOL_NAME)) goto done;
    }
    ok = writer.traces > 0;
done:
    if (sequence && lie_sequence_close(&sequence, error) != LIE_OK) ok = false;
    if (ok) {
        j = event("profile_complete"); number(j, "profile", profile); number(j, "rows", writer.traces);
        number(j, "cycles", cycles); json_object_object_add(j, "output_ids", ids(output, emitted));
        if (tools) {
            json_object *call = json_object_new_object(); text(call, "name", turn.calls[0].name);
            json_object_object_add(call, "arguments", json_tokener_parse(turn.calls[0].arguments_json));
            json_object_object_add(j, "tool_call", call);
        }
        ok = emit(file, j); if (ok) *rows_completed += writer.traces;
    } else if (!error->message[0]) snprintf(error->message, sizeof(error->message),
        "MTP observation, frontier, completion or bounded writer failure");
    free(reply); lie_output_turn_clear(&turn); return ok;
}
#endif
