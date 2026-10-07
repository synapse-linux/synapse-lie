/* SPDX-License-Identifier: MIT */
/* Numerical qualification data, not a throughput or reactive-serving benchmark.
 * The selected executor performs GPU forward. This client copies completed raw
 * rows before the ordinary AR draw; it never samples, edits logits or retries. */
#include "lie/executor.h"
#include "lie/output.h"
#include "sampling-capture-format.h"
#include <errno.h>
#include <fcntl.h>
#include <float.h>
#include <json-c/json.h>
#include <math.h>
#include <openssl/evp.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define CAPTURE_CONTEXT 8192u
#define CAPTURE_CHUNK 2048u
#define CAPTURE_PROFILES 6u
#define CAPTURE_VOCAB_MAX 1048576u
static volatile sig_atomic_t interrupted;
static void stop(int signal_number) { (void)signal_number; interrupted = 1; }
static void number(json_object *j, const char *k, uint64_t n) {
    json_object_object_add(j, k, json_object_new_uint64(n));
}
static void text(json_object *j, const char *k, const char *s) {
    json_object_object_add(j, k, json_object_new_string(s));
}
static json_object *event(const char *name) {
    json_object *j = json_object_new_object(); text(j, "event", name); return j;
}
static bool emit(FILE *f, json_object *j) {
    bool ok = fputs(json_object_to_json_string_ext(j, JSON_C_TO_STRING_PLAIN), f) >= 0 &&
              fputc('\n', f) != EOF && !fflush(f);
    json_object_put(j); return ok;
}
static json_object *ids(const int32_t *tokens, size_t count) {
    json_object *j = json_object_new_array();
    for (size_t i = 0; i < count; ++i)
        json_object_array_add(j, json_object_new_int(tokens[i]));
    return j;
}
static json_object *identity(unsigned tokens, bool tools) {
    json_object *j = event("identity");
    text(j, "schema", tools ? "synapse-lie.sampling-capture.v2" : "synapse-lie.sampling-capture.v1");
    text(j, "program", "lie-sampling-capture"); text(j, "build_id", LIE_BUILD_ID);
    text(j, "engine", lie_backend_name()); text(j, "source_pin", lie_backend_source_pin());
    text(j, "dense_sampling", lie_backend_dense_sampling());
    json_object_object_add(j, "synthetic", json_object_new_boolean(lie_backend_is_synthetic()));
    text(j, "classification", lie_backend_is_synthetic() ? "NOT-INFERENCE" : "ORIGINAL-WEIGHT-ROW-CAPTURE");
    text(j, "scope", tools ? "Strict required-function AR raw rows, vocabulary and completed calls; no MTP-controller or performance acceptance" :
         "Unconstrained AR raw rows and committed tokens; no probability, MTP-controller, quality or performance acceptance");
    text(j, "row_encoding", "IEEE754-F32-little-endian"); text(j, "decode_mode", "ar");
    text(j, "eos_policy", tools ? "stop; un-emitted EOS is captured without position advance" :
         "ignore; EOS remains an ordinary sampled token");
    number(j, "context", CAPTURE_CONTEXT); number(j, "prefill_chunk", CAPTURE_CHUNK);
    number(j, "profiles", CAPTURE_PROFILES); number(j, "tokens_per_profile", tokens);
    return j;
}
static lie_chat_tool tool_definition(void) {
    return (lie_chat_tool){LIE_CAPTURE_TOOL_NAME, "Describe the stack order and size.",
        LIE_CAPTURE_TOOL_PARAMETERS, LIE_CAPTURE_TOOL_DEFINITION};
}
static json_object *constraint_identity(void) {
    json_object *j = json_object_new_object(); text(j, "format", "json_object");
    json_object_object_add(j, "required", json_object_new_boolean(true));
    json_object_object_add(j, "parallel", json_object_new_boolean(false));
    text(j, "name", LIE_CAPTURE_TOOL_NAME);
    text(j, "parameters_json", LIE_CAPTURE_TOOL_PARAMETERS);
    text(j, "definition_json", LIE_CAPTURE_TOOL_DEFINITION);
    return j;
}
static bool write_bytes(int fd, const void *data, size_t bytes) {
    const unsigned char *p = data;
    for (size_t at = 0; at < bytes;) {
        ssize_t used = write(fd, p + at, bytes - at);
        if (used < 0 && errno == EINTR && !interrupted) continue;
        if (used <= 0 || interrupted) return false;
        at += (size_t)used;
    }
    return true;
}
static bool vocabulary(lie_model *model, unsigned vocab, int dir, FILE *file, lie_error *error) {
    int fd = openat(dir, LIE_CAPTURE_VOCAB_FILE, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (fd < 0) return false;
    EVP_MD_CTX *digest = EVP_MD_CTX_new(); unsigned char raw[32]; unsigned n = 0;
    bool ok = digest && EVP_DigestInit_ex(digest, EVP_sha256(), NULL);
    size_t total = 12; const uint32_t count = vocab;
    if (ok) ok = write_bytes(fd, LIE_CAPTURE_VOCAB_MAGIC, 8) && write_bytes(fd, &count, 4) &&
        EVP_DigestUpdate(digest, LIE_CAPTURE_VOCAB_MAGIC, 8) && EVP_DigestUpdate(digest, &count, 4);
    char *piece = malloc(LIE_CAPTURE_PIECE_BYTES_MAX);
    if (!piece) ok = false;
    for (unsigned token = 0; ok && token < vocab; ++token) {
        size_t bytes = 0; uint32_t stop_token = 0;
        ok = !interrupted && lie_model_token_text(model, (int32_t)token, piece, LIE_CAPTURE_PIECE_BYTES_MAX,
            &bytes, error) == LIE_OK && bytes <= LIE_CAPTURE_PIECE_BYTES_MAX &&
            lie_model_token_is_stop(model, (int32_t)token, &stop_token, error) == LIE_OK && stop_token <= 1 &&
            total <= LIE_CAPTURE_VOCAB_BYTES_MAX - 8 - bytes;
        if (!ok) break;
        const uint32_t header[2] = {(uint32_t)bytes, stop_token}; total += 8 + bytes;
        ok = write_bytes(fd, header, sizeof(header)) && write_bytes(fd, piece, bytes) &&
            EVP_DigestUpdate(digest, header, sizeof(header)) && EVP_DigestUpdate(digest, piece, bytes);
    }
    if (ok) ok = EVP_DigestFinal_ex(digest, raw, &n) && n == sizeof(raw);
    EVP_MD_CTX_free(digest); free(piece); if (close(fd)) ok = false;
    if (ok) {
        char hash[65]; for (unsigned i = 0; i < n; ++i) snprintf(hash + i * 2, 3, "%02x", raw[i]);
        json_object *j = event("vocabulary"); text(j, "file", LIE_CAPTURE_VOCAB_FILE);
        text(j, "sha256", hash); number(j, "bytes", total); number(j, "tokens", vocab); ok = emit(file, j);
    }
    return ok;
}
static lie_generation_options generation(unsigned profile) {
    lie_generation_options o = {.abi_version = LIE_GENERATION_ABI,
        .struct_bytes = sizeof(o), .top_p = 1, .seed = 123};
    if (profile) o.temperature = 1;
    if (profile == 1) o.min_p = .05;
    if (profile == 2) o.top_k = 32;
    if (profile == 3) { o.temperature = .7; o.top_p = .9; o.min_p = .05; }
    if (profile == 4) { o.top_k = 32; o.min_p = .05;
        o.frequency_penalty = .4; o.presence_penalty = .2; }
    if (profile == 5) { o.temperature = 2; o.min_p = .2;
        o.frequency_penalty = -.3; o.presence_penalty = -.1; }
    return o;
}
static json_object *controls(const lie_generation_options *o) {
    json_object *j = json_object_new_object();
    const char *names[] = {"temperature", "top_p", "min_p", "frequency_penalty", "presence_penalty"};
    const double values[] = {o->temperature, o->top_p, o->min_p, o->frequency_penalty, o->presence_penalty};
    for (unsigned i = 0; i < 5; ++i)
        json_object_object_add(j, names[i], json_object_new_double(values[i]));
    number(j, "top_k", (uint32_t)o->top_k); number(j, "seed", (uint64_t)o->seed);
    return j;
}
static bool write_row(int dir, const char *name, const float *row, size_t count, char hash[65]) {
    int fd = openat(dir, name, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (fd < 0) return false;
    const unsigned char *data = (const unsigned char *)row; size_t bytes = count * sizeof(*row);
    unsigned char digest[32]; unsigned n = 0;
    bool ok = EVP_Digest(data, bytes, digest, &n, EVP_sha256(), NULL) && n == sizeof(digest);
    if (ok) ok = write_bytes(fd, data, bytes);
    if (close(fd)) ok = false;
    if (ok) for (unsigned i = 0; i < n; ++i) snprintf(hash + i * 2, 3, "%02x", digest[i]);
    return ok;
}
static bool capture(lie_model *model, const int32_t *prompt, size_t count,
                    unsigned vocab, unsigned profile, unsigned budget,
                    float *row, int dir, FILE *file, bool tools,
                    unsigned *rows_completed, lie_error *error) {
    static const char *names[CAPTURE_PROFILES] = {
        "greedy", "ds4-temperature1-minp", "top-k", "nucleus-minp",
        "generated-penalties", "temperature2-negative-penalties"};
    lie_sequence *sequence = NULL; lie_generation_options options = generation(profile);
    bool ok = false, stopped = false; int32_t output[128]; unsigned rows = 0, emitted = 0;
    char *reply = tools ? calloc(1, LIE_CAPTURE_OUTPUT_BYTES_MAX + 1) : NULL; size_t reply_bytes = 0;
    lie_output_turn turn = {0}; lie_chat_tool tool = tool_definition();
    json_object *j = event("profile_begin"); number(j, "profile", profile);
    text(j, "name", names[profile]); number(j, "vocab", vocab);
    json_object_object_add(j, "generation", controls(&options));
    json_object_object_add(j, "prompt_ids", ids(prompt, count));
    if (tools) json_object_object_add(j, "constraint", constraint_identity());
    if (!emit(file, j) || lie_sequence_create(model, &sequence, error) != LIE_OK ||
        lie_sequence_configure(sequence, &options, error) != LIE_OK ||
        lie_sequence_set_eos_policy(sequence, tools ? LIE_EOS_STOP : LIE_EOS_IGNORE, error) != LIE_OK ||
        (tools && !reply)) goto done;
    if (tools) {
        const lie_generation_constraints constraints = {.format = LIE_FORMAT_JSON_OBJECT,
            .tools = &tool, .tool_count = 1, .required = 1};
        if (lie_sequence_constrain(sequence, &constraints, error) != LIE_OK) goto done;
    }
    for (size_t at = 0; at < count;) {
        at = count - at > CAPTURE_CHUNK ? at + CAPTURE_CHUNK : count;
        if (interrupted || lie_sequence_prefill(sequence, prompt, at, error) != LIE_OK) goto done;
    }
    for (unsigned step = 0; step < budget; ++step) {
        size_t actual = 0; char name[64], hash[65]; lie_decode_result decoded = {0};
        if (interrupted || lie_sequence_logits(sequence, row, vocab, &actual, error) != LIE_OK || actual != vocab)
            goto done;
        for (size_t i = 0; i < actual; ++i) if (!isfinite(row[i])) {
            snprintf(error->message, sizeof(error->message), "nonfinite raw frontier logits"); goto done;
        }
        snprintf(name, sizeof(name), "profile-%u-row-%u.f32le", profile, step);
        if (!write_row(dir, name, row, actual, hash) || interrupted ||
            lie_sequence_decode(sequence, &decoded, error) != LIE_OK) goto done;
        if (decoded.stop > 1 || decoded.emitted > 1 || decoded.emitted == decoded.stop ||
            (!tools && decoded.stop) || (decoded.emitted && (decoded.token < 0 || (unsigned)decoded.token >= vocab)) ||
            (!decoded.emitted && decoded.token != -1) || decoded.position != count + emitted + decoded.emitted) {
            snprintf(error->message, sizeof(error->message), "invalid completed AR capture frontier"); goto done;
        }
        if (decoded.emitted) {
            output[emitted++] = decoded.token;
            if (tools) {
                size_t bytes = 0; uint32_t stop_token = 0;
                if (lie_model_token_text(model, decoded.token, reply + reply_bytes,
                    LIE_CAPTURE_OUTPUT_BYTES_MAX - reply_bytes, &bytes, error) != LIE_OK ||
                    bytes > LIE_CAPTURE_OUTPUT_BYTES_MAX - reply_bytes ||
                    lie_model_token_is_stop(model, decoded.token, &stop_token, error) != LIE_OK || stop_token ||
                    memchr(reply + reply_bytes, 0, bytes)) goto done;
                reply_bytes += bytes; reply[reply_bytes] = 0;
            }
        }
        j = event("row"); number(j, "profile", profile); number(j, "step", step);
        text(j, "file", name); text(j, "sha256", hash); number(j, "bytes", actual * sizeof(*row));
        if (decoded.emitted) number(j, "token", (uint32_t)decoded.token);
        else json_object_object_add(j, "token", NULL);
        number(j, "position", decoded.position);
        if (tools) { number(j, "emitted", decoded.emitted);
            json_object_object_add(j, "stop", json_object_new_boolean(decoded.stop)); }
        if (!emit(file, j)) goto done;
        ++rows;
        if (decoded.stop) { stopped = true; break; }
    }
    if (tools) {
        const lie_output_policy policy = {&tool, 1, LIE_TOOLS_REQUIRED, false, NULL};
        if (!stopped || !lie_output_parse(&policy, reply, reply_bytes, true,
            "sampling-capture", &turn, error->message) || turn.count != 1 || turn.bytes ||
            strcmp(turn.calls[0].name, LIE_CAPTURE_TOOL_NAME)) {
            if (!error->message[0]) snprintf(error->message, sizeof(error->message), "required tool not completed before row budget");
            goto done;
        }
    }
    ok = true;
done:
    if (sequence && lie_sequence_close(&sequence, error) != LIE_OK) ok = false;
    if (ok) {
        j = event("profile_complete"); number(j, "profile", profile); number(j, "rows", rows);
        json_object_object_add(j, "output_ids", ids(output, emitted));
        if (tools) {
            json_object *call = json_object_new_object(); text(call, "name", turn.calls[0].name);
            json_object_object_add(call, "arguments", json_tokener_parse(turn.calls[0].arguments_json));
            json_object_object_add(j, "tool_call", call);
        }
        ok = emit(file, j); if (ok) *rows_completed += rows;
    }
    free(reply); lie_output_turn_clear(&turn);
    return ok;
}
int main(int argc, char **argv) {
    _Static_assert(sizeof(float) == 4 && FLT_RADIX == 2 && FLT_MANT_DIG == 24,
                   "IEEE754 float32 capture required");
    const uint32_t endian = 1; unsigned budget = 16, total_rows = 0; bool tools = false, budget_set = false;
    if (*(const unsigned char *)&endian != 1) {
        fputs("Little-endian capture required\n", stderr); return 2;
    }
    if (argc == 2 && !strcmp(argv[1], "--build-info")) return emit(stdout, identity(budget, false)) ? 0 : 1;
    if (argc < 5 || strcmp(argv[1], "--model") || strcmp(argv[3], "--output-dir")) goto usage;
    for (int i = 5; i < argc; ++i) {
        if (!strcmp(argv[i], "--tools") && !tools) { tools = true; continue; }
        if (strcmp(argv[i], "--tokens") || budget_set || ++i >= argc ||
            !*argv[i] || strspn(argv[i], "0123456789") != strlen(argv[i])) goto usage;
        char *end; errno = 0; unsigned long n = strtoul(argv[i], &end, 10);
        if (errno || *end || n < 1 || n > 128) goto usage;
        budget = (unsigned)n; budget_set = true;
    }
    if (tools && !budget_set) budget = 128;
#ifndef LIE_SAMPLING_CAPTURE_FIXTURE
    if (lie_backend_is_synthetic()) { fputs("Synthetic executor refused\n", stderr); return 2; }
#endif
    struct sigaction sa = {0}; sa.sa_handler = stop; sigemptyset(&sa.sa_mask);
    if (sigaction(SIGINT, &sa, NULL) || sigaction(SIGTERM, &sa, NULL)) return 1;
    if (mkdir(argv[4], 0700)) { perror("exclusive capture directory"); return 1; }
    int dir = open(argv[4], O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
    if (dir < 0) return 1;
    int fd = openat(dir, "capture.jsonl", O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (fd < 0) { close(dir); return 1; }
    FILE *file = fdopen(fd, "w");
    if (!file) { close(fd); close(dir); return 1; }
    lie_model *model = NULL; lie_error error = {{0}}; float *row = NULL; int code = 1;
    lie_model_options options = {LIE_EXECUTOR_ABI, sizeof(options), CAPTURE_CONTEXT, CAPTURE_CHUNK, LIE_ROPE_NATIVE};
    lie_model_info info = {0}; int32_t prompt[CAPTURE_CONTEXT]; size_t count = 0;
    const char *question = tools ? LIE_CAPTURE_TOOL_PROMPT : "Explain how a stack works. Give short numbered steps, repeat the word stack in every step, and continue with examples. Do not add an introduction.";
    lie_chat_message message = {LIE_CHAT_USER, question, strlen(question)}; lie_chat_tool tool = tool_definition();
    const lie_chat_template input = {&message, NULL, 1, &tool, 1, 1};
    if (!emit(file, identity(budget, tools)) || interrupted ||
        lie_backend_open(argv[2], &options, &model, &error) != LIE_OK ||
        lie_model_get_info(model, &info, &error) != LIE_OK || info.abi_version != LIE_EXECUTOR_ABI ||
        !info.vocab_tokens || info.vocab_tokens > CAPTURE_VOCAB_MAX ||
        info.context_tokens != CAPTURE_CONTEXT ||
        (tools ? lie_model_chat_tokens_ex(model, &input, prompt, CAPTURE_CONTEXT, &count, &error) :
            lie_model_chat_tokens(model, &message, 1, prompt, CAPTURE_CONTEXT, &count, &error)) != LIE_OK ||
        !count || count + budget > CAPTURE_CONTEXT) goto done;
    for (size_t i = 0; i < count; ++i) if (prompt[i] < 0 || (unsigned)prompt[i] >= info.vocab_tokens) goto done;
    row = malloc((size_t)info.vocab_tokens * sizeof(*row)); if (!row) goto done;
    if (tools && !vocabulary(model, info.vocab_tokens, dir, file, &error)) goto done;
    for (unsigned i = 0; i < CAPTURE_PROFILES; ++i)
        if (!capture(model, prompt, count, info.vocab_tokens, i, budget, row, dir, file, tools, &total_rows, &error)) goto done;
    code = 0;
done:
    if (model && lie_model_close(&model, &error) != LIE_OK) code = 1;
    if (interrupted) code = 1;
    free(row);
    json_object *j = event(code ? "failed" : "complete"); number(j, "exit_code", (unsigned)code);
    if (code) text(j, "error", interrupted ? "interrupted after owned work completion" :
                   error.message[0] ? error.message : "capture allocation, identity, frontier or I/O failure");
    else { number(j, "profiles", CAPTURE_PROFILES); number(j, "rows", total_rows); }
    if (!emit(file, j)) code = 1;
    if (fclose(file)) code = 1;
    if (close(dir)) code = 1;
    return code;
usage:
    fputs("Usage: lie-sampling-capture --model ORIGINAL-FIRST-SHARD --output-dir NEW-DIRECTORY [--tokens 1..128] [--tools]\n", stderr);
    return 2;
}
