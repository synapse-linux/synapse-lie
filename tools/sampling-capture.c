/* SPDX-License-Identifier: MIT */
/* Numerical qualification data, not a throughput or reactive-serving benchmark.
 * The selected executor performs GPU forward. This client copies completed raw
 * rows before the ordinary AR draw; it never samples, edits logits or retries. */
#include "lie/executor.h"
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
static json_object *identity(unsigned tokens) {
    json_object *j = event("identity");
    text(j, "schema", "synapse-lie.sampling-capture.v1");
    text(j, "program", "lie-sampling-capture"); text(j, "build_id", LIE_BUILD_ID);
    text(j, "engine", lie_backend_name()); text(j, "source_pin", lie_backend_source_pin());
    text(j, "dense_sampling", lie_backend_dense_sampling());
    json_object_object_add(j, "synthetic", json_object_new_boolean(lie_backend_is_synthetic()));
    text(j, "classification", lie_backend_is_synthetic() ? "NOT-INFERENCE" : "ORIGINAL-WEIGHT-ROW-CAPTURE");
    text(j, "scope", "Unconstrained AR raw rows and committed tokens; no probability, MTP-controller, quality or performance acceptance");
    text(j, "row_encoding", "IEEE754-F32-little-endian"); text(j, "decode_mode", "ar");
    text(j, "eos_policy", "ignore; EOS remains an ordinary sampled token");
    number(j, "context", CAPTURE_CONTEXT); number(j, "prefill_chunk", CAPTURE_CHUNK);
    number(j, "profiles", CAPTURE_PROFILES); number(j, "tokens_per_profile", tokens);
    return j;
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
    for (size_t at = 0; ok && at < bytes;) {
        ssize_t used = write(fd, data + at, bytes - at);
        if (used < 0 && errno == EINTR && !interrupted) continue;
        if (used <= 0 || interrupted) { ok = false; break; }
        at += (size_t)used;
    }
    if (close(fd)) ok = false;
    if (ok) for (unsigned i = 0; i < n; ++i) snprintf(hash + i * 2, 3, "%02x", digest[i]);
    return ok;
}
static bool capture(lie_model *model, const int32_t *prompt, size_t count,
                    unsigned vocab, unsigned profile, unsigned budget,
                    float *row, int dir, FILE *file, lie_error *error) {
    static const char *names[CAPTURE_PROFILES] = {
        "greedy", "ds4-temperature1-minp", "top-k", "nucleus-minp",
        "generated-penalties", "temperature2-negative-penalties"};
    lie_sequence *sequence = NULL; lie_generation_options options = generation(profile);
    bool ok = false; int32_t output[128];
    json_object *j = event("profile_begin"); number(j, "profile", profile);
    text(j, "name", names[profile]); number(j, "vocab", vocab);
    json_object_object_add(j, "generation", controls(&options));
    json_object_object_add(j, "prompt_ids", ids(prompt, count));
    if (!emit(file, j) || lie_sequence_create(model, &sequence, error) != LIE_OK ||
        lie_sequence_configure(sequence, &options, error) != LIE_OK ||
        lie_sequence_set_eos_policy(sequence, LIE_EOS_IGNORE, error) != LIE_OK) goto done;
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
        if (decoded.emitted != 1 || decoded.stop || decoded.token < 0 ||
            (unsigned)decoded.token >= vocab || decoded.position != count + step + 1) {
            snprintf(error->message, sizeof(error->message), "invalid completed AR capture frontier"); goto done;
        }
        output[step] = decoded.token;
        j = event("row"); number(j, "profile", profile); number(j, "step", step);
        text(j, "file", name); text(j, "sha256", hash); number(j, "bytes", actual * sizeof(*row));
        number(j, "token", (uint32_t)decoded.token); number(j, "position", decoded.position);
        if (!emit(file, j)) goto done;
    }
    ok = true;
done:
    if (sequence && lie_sequence_close(&sequence, error) != LIE_OK) ok = false;
    if (ok) {
        j = event("profile_complete"); number(j, "profile", profile); number(j, "rows", budget);
        json_object_object_add(j, "output_ids", ids(output, budget)); ok = emit(file, j);
    }
    return ok;
}
int main(int argc, char **argv) {
    _Static_assert(sizeof(float) == 4 && FLT_RADIX == 2 && FLT_MANT_DIG == 24,
                   "IEEE754 float32 capture required");
    const uint32_t endian = 1; unsigned budget = 16;
    if (*(const unsigned char *)&endian != 1) {
        fputs("Little-endian capture required\n", stderr); return 2;
    }
    if (argc == 2 && !strcmp(argv[1], "--build-info")) return emit(stdout, identity(budget)) ? 0 : 1;
    if ((argc != 5 && argc != 7) || strcmp(argv[1], "--model") || strcmp(argv[3], "--output-dir")) goto usage;
    if (argc == 7) {
        if (strcmp(argv[5], "--tokens") || !*argv[6] || strspn(argv[6], "0123456789") != strlen(argv[6])) goto usage;
        char *end; errno = 0; unsigned long n = strtoul(argv[6], &end, 10);
        if (errno || *end || n < 1 || n > 128) goto usage;
        budget = (unsigned)n;
    }
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
    static const char question[] = "Explain how a stack works. Give short numbered steps, repeat the word stack in every step, and continue with examples. Do not add an introduction.";
    lie_chat_message message = {LIE_CHAT_USER, question, sizeof(question) - 1};
    if (!emit(file, identity(budget)) || interrupted ||
        lie_backend_open(argv[2], &options, &model, &error) != LIE_OK ||
        lie_model_get_info(model, &info, &error) != LIE_OK || info.abi_version != LIE_EXECUTOR_ABI ||
        !info.vocab_tokens || info.vocab_tokens > CAPTURE_VOCAB_MAX ||
        info.context_tokens != CAPTURE_CONTEXT ||
        lie_model_chat_tokens(model, &message, 1, prompt, CAPTURE_CONTEXT, &count, &error) != LIE_OK ||
        !count || count + budget > CAPTURE_CONTEXT) goto done;
    for (size_t i = 0; i < count; ++i) if (prompt[i] < 0 || (unsigned)prompt[i] >= info.vocab_tokens) goto done;
    row = malloc((size_t)info.vocab_tokens * sizeof(*row)); if (!row) goto done;
    for (unsigned i = 0; i < CAPTURE_PROFILES; ++i)
        if (!capture(model, prompt, count, info.vocab_tokens, i, budget, row, dir, file, &error)) goto done;
    code = 0;
done:
    if (model && lie_model_close(&model, &error) != LIE_OK) code = 1;
    if (interrupted) code = 1;
    free(row);
    json_object *j = event(code ? "failed" : "complete"); number(j, "exit_code", (unsigned)code);
    if (code) text(j, "error", interrupted ? "interrupted after owned work completion" :
                   error.message[0] ? error.message : "capture allocation, identity, frontier or I/O failure");
    else { number(j, "profiles", CAPTURE_PROFILES); number(j, "rows", CAPTURE_PROFILES * budget); }
    if (!emit(file, j)) code = 1;
    if (fclose(file)) code = 1;
    if (close(dir)) code = 1;
    return code;
usage:
    fputs("Usage: lie-sampling-capture --model ORIGINAL-FIRST-SHARD --output-dir NEW-DIRECTORY [--tokens 1..128]\n", stderr);
    return 2;
}
