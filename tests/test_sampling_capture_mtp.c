/* SPDX-License-Identifier: MIT */
/* Owned native MTP capture/parser/lifetime fixtures; NOT-INFERENCE. */
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <json-c/json.h>
#include <math.h>
#include <openssl/evp.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static json_object *field(json_object *j, const char *name, enum json_type type) {
    json_object *value = NULL;
    assert(json_object_object_get_ex(j, name, &value) && json_object_is_type(value, type));
    return value;
}
static unsigned number(json_object *j, const char *name) {
    int64_t n = json_object_get_int64(field(j, name, json_type_int));
    assert(n >= 0 && n <= UINT32_MAX); return (unsigned)n;
}
static const char *text(json_object *j, const char *name) {
    return json_object_get_string(field(j, name, json_type_string));
}
static int run(const char *binary, const char *model, const char *directory, const char *const *options) {
    char *argv[32] = {(char *)binary, "--model", (char *)model, "--output-dir", (char *)directory};
    unsigned n = 5;
    for (const char *const *p = options; *p; ++p) { assert(n < 31); argv[n++] = (char *)*p; }
    argv[n] = NULL;
    pid_t child = fork(); assert(child >= 0);
    if (!child) { execv(binary, argv); _exit(127); }
    struct timespec pause = {0, 10000000}; int status = 0;
    for (unsigned i = 0; i < 3000; ++i) {
        pid_t seen = waitpid(child, &status, WNOHANG);
        if (seen == child) { assert(WIFEXITED(status)); return WEXITSTATUS(status); }
        assert(seen == 0 || (seen < 0 && errno == EINTR)); nanosleep(&pause, NULL);
    }
    /* Unreaped direct child only. Never look up or signal a foreign process. */
    kill(child, SIGKILL); assert(waitpid(child, &status, 0) == child);
    assert(!"owned MTP fixture timed out"); return 1;
}
static void blob(int directory, json_object *metadata, unsigned profile, unsigned index,
                 const char *suffix, size_t bytes) {
    char expected[96]; snprintf(expected, sizeof(expected), "profile-%u-trace-%u.%s", profile, index, suffix);
    const char *name = text(metadata, "file"); assert(!strcmp(name, expected));
    assert(number(metadata, "bytes") == bytes && bytes <= 68);
    int fd = openat(directory, name, O_RDONLY | O_NOFOLLOW | O_NONBLOCK);
    struct stat stat; unsigned char data[68], hash[32]; unsigned count = 0; char hex[65];
    assert(fd >= 0 && !fstat(fd, &stat) && S_ISREG(stat.st_mode) && stat.st_size == (off_t)bytes);
    assert(read(fd, data, bytes) == (ssize_t)bytes && !close(fd));
    assert(EVP_Digest(data, bytes, hash, &count, EVP_sha256(), NULL) && count == 32);
    for (unsigned i = 0; i < count; ++i) snprintf(hex + i * 2, 3, "%02x", hash[i]);
    assert(!strcmp(text(metadata, "sha256"), hex));
    if (!strcmp(suffix, "f32le")) {
        for (size_t at = 0; at < bytes; at += 4) { float value; memcpy(&value, data + at, 4); assert(isfinite(value)); }
    } else for (size_t at = 0; at < bytes; ++at) assert(data[at] <= 1);
}
static unsigned inspect(const char *path, int code, unsigned budget, bool tools, unsigned drafts) {
    int directory = open(path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW); assert(directory >= 0);
    int fd = openat(directory, "capture.jsonl", O_RDONLY | O_NOFOLLOW); assert(fd >= 0);
    FILE *file = fdopen(fd, "r"); assert(file); char *line = NULL; size_t capacity = 0;
    unsigned profiles = 0, rows = 0, index = 0, cycle = 0, emitted = 0;
    bool identity = false, terminal = false, active = false, in_cycle = false, stopped = false, vocabulary = false;
    while (getline(&line, &capacity, file) > 0) {
        json_object *j = json_tokener_parse(line); assert(j && !terminal);
        const char *event = text(j, "event");
        if (!strcmp(event, "identity")) {
            assert(!identity && !strcmp(text(j, "schema"), "synapse-lie.sampling-capture.v3") &&
                !strcmp(text(j, "classification"), "NOT-INFERENCE") &&
                json_object_get_boolean(field(j, "synthetic", json_type_boolean)) &&
                !strcmp(text(j, "decode_mode"), "mtp") && !strcmp(text(j, "mtp_model"), ":predictor:") &&
                number(j, "mtp_draft_tokens_requested") == drafts && number(j, "greedy_reservation") == 1 &&
                number(j, "tokens_per_profile") == budget &&
                json_object_get_boolean(field(j, "tools", json_type_boolean)) == tools);
            identity = true;
        } else if (!strcmp(event, "vocabulary")) {
            assert(identity && tools && !vocabulary && !active); vocabulary = true;
        } else if (!strcmp(event, "profile_begin")) {
            assert(identity && !active && number(j, "profile") == profiles && number(j, "vocab") == 17);
            active = true; index = cycle = emitted = 0; stopped = false;
        } else if (!strcmp(event, "cycle_begin")) {
            assert(active && !in_cycle && !stopped && cycle < budget && emitted < budget &&
                number(j, "profile") == profiles && number(j, "cycle") == cycle && number(j, "position") == 5 + emitted);
            unsigned expected = !profiles ? 1 : budget - emitted < drafts + 1 ? budget - emitted : drafts + 1;
            assert(number(j, "reservation") == expected); in_cycle = true;
        } else if (!strcmp(event, "sampling_trace")) {
            assert(in_cycle && number(j, "profile") == profiles && number(j, "cycle") == cycle &&
                number(j, "index") == index && index < 128 * 9);
            const char *before = text(j, "rng_before"), *after = text(j, "rng_after");
            assert(strlen(before) == 16 && strlen(after) == 16 && strspn(before, "0123456789abcdef") == 16 &&
                strspn(after, "0123456789abcdef") == 16 && number(j, "token") < 17);
            blob(directory, field(j, "raw", json_type_object), profiles, index, "f32le", number(j, "logit_count") * 4);
            json_object *allowed = NULL; assert(json_object_object_get_ex(j, "allowed", &allowed));
            if (allowed) { assert(tools); blob(directory, allowed, profiles, index, "u8", 17); }
            assert(json_object_array_length(field(j, "history_ids", json_type_array)) <= 64);
            ++index; ++rows;
        } else if (!strcmp(event, "cycle_complete")) {
            assert(in_cycle && number(j, "profile") == profiles && number(j, "cycle") == cycle);
            unsigned n = (unsigned)json_object_array_length(field(j, "output_ids", json_type_array));
            assert(n <= drafts + 1 && n <= budget - emitted && number(j, "accepted") <= number(j, "drafted"));
            emitted += n; stopped = json_object_get_boolean(field(j, "stop", json_type_boolean));
            assert(number(j, "position") == 5 + emitted && (n || stopped));
            ++cycle; in_cycle = false;
        } else if (!strcmp(event, "profile_complete")) {
            assert(active && !in_cycle && number(j, "profile") == profiles && number(j, "rows") == index &&
                number(j, "cycles") == cycle &&
                json_object_array_length(field(j, "output_ids", json_type_array)) == emitted &&
                (tools ? stopped && emitted == 5 : emitted == budget));
            if (tools) assert(!strcmp(text(field(j, "tool_call", json_type_object), "name"), "describe_stack"));
            ++profiles; active = false;
        } else if (!strcmp(event, code ? "failed" : "complete")) {
            assert(number(j, "exit_code") == (unsigned)code);
            if (!code) assert(profiles == 6 && !active && number(j, "rows") == rows && number(j, "profiles") == 6);
            terminal = true;
        } else assert(!"unexpected MTP capture event");
        json_object_put(j);
    }
    assert(identity && terminal && !ferror(file) && (!tools || vocabulary));
    free(line); assert(!fclose(file) && !close(directory)); return rows;
}
int main(int argc, char **argv) {
    assert(argc == 3); char *root = strdup(argv[2]); assert(root && mkdtemp(root));
    char path[4096]; struct stat stat;
    const char *invalid[][12] = {
        {"--draft-tokens", "1", NULL},
        {"--mtp-model", ":predictor:", "--draft-tokens", "0", NULL},
        {"--mtp-model", ":predictor:", "--draft-tokens", "8", NULL},
        {"--mtp-model", ":predictor:", "--draft-tokens", "01", NULL},
        {"--mtp-model", ":predictor:", "--draft-tokens", "1", "--draft-tokens", "2", NULL},
        {"--mtp-model", ":predictor:", "--mtp-model", ":predictor:", NULL},
        {"--mtp-model", "", NULL}, {"--mtp-model", NULL},
        {"--mtp-model", ":predictor:", "--tokens", "129", NULL}
    };
    for (unsigned i = 0; i < sizeof(invalid) / sizeof(*invalid); ++i) {
        snprintf(path, sizeof(path), "%s/invalid-%u", root, i);
        assert(run(argv[1], ":fixture:", path, invalid[i]) == 2);
        assert(lstat(path, &stat) == -1 && errno == ENOENT);
    }
    const char *good[] = {"--tokens", "16", "--mtp-model", ":predictor:", "--draft-tokens", "7", NULL};
    snprintf(path, sizeof(path), "%s/good", root);
    assert(!run(argv[1], ":fixture:", path, good)); assert(inspect(path, 0, 16, false, 7) > 96);
    assert(run(argv[1], ":fixture:", path, good) == 1); inspect(path, 0, 16, false, 7);
    const char *boundary[] = {"--tokens", "128", "--mtp-model", ":predictor:", "--draft-tokens", "1", NULL};
    snprintf(path, sizeof(path), "%s/boundary", root);
    assert(!run(argv[1], ":fixture:", path, boundary)); inspect(path, 0, 128, false, 1);
    const char *minimum[] = {"--tokens", "1", "--mtp-model", ":predictor:", NULL};
    snprintf(path, sizeof(path), "%s/minimum", root);
    assert(!run(argv[1], ":fixture:", path, minimum)); assert(inspect(path, 0, 1, false, 7) == 6);
    const char *tool[] = {"--tokens", "8", "--tools", "--mtp-model", ":predictor:", NULL};
    snprintf(path, sizeof(path), "%s/tools", root);
    assert(!run(argv[1], ":tools:", path, tool)); inspect(path, 0, 8, true, 7);
    for (unsigned i = 0; i < 2; ++i) {
        snprintf(path, sizeof(path), "%s/failure-%u", root, i);
        assert(run(argv[1], i ? ":failure:" : ":nan:", path, good) == 1);
        assert(inspect(path, 1, 16, false, 7) == 0);
    }
    snprintf(path, sizeof(path), "%s/invalid-frontier", root);
    assert(run(argv[1], ":mtp-frontier:", path, good) == 1); assert(inspect(path, 1, 16, false, 7) == 1);
    const char *truncated[] = {"--tokens", "5", "--tools", "--mtp-model", ":predictor:", NULL};
    snprintf(path, sizeof(path), "%s/truncated", root);
    assert(run(argv[1], ":tools:", path, truncated) == 1); assert(inspect(path, 1, 5, true, 7) == 5);
    printf("MTP_CAPTURE_NATIVE_BOUNDS_LIFETIME_PASS_NOT_INFERENCE path=%s\n", root);
    free(root); return 0;
}
