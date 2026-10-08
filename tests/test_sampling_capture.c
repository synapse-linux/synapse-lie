/* SPDX-License-Identifier: MIT */
/* Native format/lifetime fixtures. Own child processes and a private directory. */
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
static int run(const char *binary, const char *model, const char *directory, const char *tokens, bool tools) {
    pid_t child = fork(); assert(child >= 0);
    if (!child) {
        execl(binary, binary, "--model", model, "--output-dir", directory, "--tokens", tokens,
            tools ? "--tools" : NULL, NULL);
        _exit(127);
    }
    struct timespec pause = {0, 10000000}; int status = 0;
    for (unsigned i = 0; i < 3000; ++i) {
        pid_t seen = waitpid(child, &status, WNOHANG);
        if (seen == child) { assert(WIFEXITED(status)); return WEXITSTATUS(status); }
        assert(seen == 0 || (seen < 0 && errno == EINTR)); nanosleep(&pause, NULL);
    }
    /* This PID is our unreaped direct child; no foreign process is signalled. */
    kill(child, SIGKILL); assert(waitpid(child, &status, 0) == child);
    assert(!"owned fixture timed out"); return 1;
}
static unsigned inspect(const char *path, int exit_code) {
    int directory = open(path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW); assert(directory >= 0);
    int fd = openat(directory, "capture.jsonl", O_RDONLY | O_NOFOLLOW); assert(fd >= 0);
    FILE *file = fdopen(fd, "r"); assert(file); char *line = NULL; size_t capacity = 0;
    unsigned rows = 0, profiles = 0, stops = 0; bool terminal = false, identity = false, tools = false, vocabulary = false;
    while (getline(&line, &capacity, file) > 0) {
        json_object *j = json_tokener_parse(line); assert(j);
        const char *event = json_object_get_string(json_object_object_get(j, "event")); assert(event);
        assert(!terminal);
        if (!strcmp(event, "identity")) {
            assert(!identity && json_object_get_boolean(json_object_object_get(j, "synthetic")));
            assert(!strcmp(json_object_get_string(json_object_object_get(j, "classification")), "NOT-INFERENCE")); identity = true;
            tools = !strcmp(json_object_get_string(json_object_object_get(j, "schema")), "synapse-lie.sampling-capture.v2");
        } else if (!strcmp(event, "vocabulary")) {
            assert(tools && !vocabulary); vocabulary = true;
            int input = openat(directory, "vocabulary.bin", O_RDONLY | O_NOFOLLOW); assert(input >= 0);
            unsigned char data[4096]; ssize_t bytes = read(input, data, sizeof(data));
            assert(bytes >= 12 && bytes < (ssize_t)sizeof(data) && !close(input));
            assert(!memcmp(data, "LIEVOC01", 8) && data[8] == 17 && !data[9] && !data[10] && !data[11]);
            assert(json_object_get_uint64(json_object_object_get(j, "bytes")) == (uint64_t)bytes);
            unsigned char digest[32]; unsigned count = 0; char hash[65];
            assert(EVP_Digest(data, (size_t)bytes, digest, &count, EVP_sha256(), NULL) && count == 32);
            for (unsigned i = 0; i < count; ++i) snprintf(hash + i * 2, 3, "%02x", digest[i]);
            assert(!strcmp(hash, json_object_get_string(json_object_object_get(j, "sha256"))));
        } else if (!strcmp(event, "row")) {
            const char *name = json_object_get_string(json_object_object_get(j, "file")); assert(name && !strchr(name, '/'));
            int input = openat(directory, name, O_RDONLY | O_NOFOLLOW); assert(input >= 0);
            float data[17]; assert(read(input, data, sizeof(data)) == sizeof(data)); assert(!close(input));
            assert(json_object_get_uint64(json_object_object_get(j, "bytes")) == sizeof(data));
            for (unsigned i = 0; i < 17; ++i) assert(isfinite(data[i]));
            unsigned char digest[32]; unsigned count = 0; char hash[65];
            assert(EVP_Digest(data, sizeof(data), digest, &count, EVP_sha256(), NULL) && count == 32);
            for (unsigned i = 0; i < count; ++i) snprintf(hash + i * 2, 3, "%02x", digest[i]);
            assert(!strcmp(hash, json_object_get_string(json_object_object_get(j, "sha256")))); ++rows;
            if (tools && json_object_get_boolean(json_object_object_get(j, "stop"))) {
                assert(!json_object_get_int(json_object_object_get(j, "emitted")) &&
                    !json_object_object_get(j, "token") && json_object_get_int(json_object_object_get(j, "position")) == 10);
                ++stops;
            }
        } else if (!strcmp(event, "profile_complete")) {
            ++profiles;
            if (tools) {
                json_object *call = json_object_object_get(j, "tool_call"), *arguments = json_object_object_get(call, "arguments");
                assert(call && arguments && !strcmp(json_object_get_string(json_object_object_get(call, "name")), "describe_stack"));
                const char *order = json_object_get_string(json_object_object_get(arguments, "order"));
                assert(order && (!strcmp(order, "LIFO") || !strcmp(order, "FIFO")) &&
                    json_object_get_int(json_object_object_get(arguments, "size")) >= 0 &&
                    json_object_get_int(json_object_object_get(arguments, "size")) <= 9);
                assert(json_object_array_length(json_object_object_get(j, "output_ids")) == 5 &&
                    json_object_get_int(json_object_object_get(j, "rows")) == 6);
            }
        }
        else if (!strcmp(event, exit_code ? "failed" : "complete")) {
            assert(json_object_get_int(json_object_object_get(j, "exit_code")) == exit_code); terminal = true;
        } else assert(!strcmp(event, "profile_begin"));
        json_object_put(j);
    }
    assert(identity && terminal && !ferror(file)); free(line); assert(!fclose(file)); assert(!close(directory));
    assert(!tools || vocabulary);
    assert(exit_code ? !profiles : profiles == 6 && rows == (tools ? 36u : 48u));
    assert(exit_code || !tools || stops == 6); return rows;
}
int main(int argc, char **argv) {
    assert(argc == 3);
    if (!strcmp(argv[1], "--fifo")) return mkfifo(argv[2], 0600) ? 1 : 0;
    if (!strcmp(argv[1], "--invalid-stop") || !strcmp(argv[1], "--oversized-piece")) {
        int fd = open(argv[2], O_WRONLY | O_NOFOLLOW | O_NONBLOCK); struct stat stat;
        if (fd < 0) return 1;
        const uint32_t value = !strcmp(argv[1], "--invalid-stop") ? 2 : UINT32_MAX;
        const off_t offset = !strcmp(argv[1], "--invalid-stop") ? 16 : 12;
        bool ok = !fstat(fd, &stat) && S_ISREG(stat.st_mode) &&
            pwrite(fd, &value, sizeof(value), offset) == sizeof(value);
        if (close(fd)) ok = false;
        return ok ? 0 : 1;
    }
    char *root = strdup(argv[2]); assert(root && mkdtemp(root));
    char path[4096]; struct stat stat;
    for (unsigned i = 0; i < 3; ++i) {
        const char *values[] = {"0", "129", "invalid"};
        assert(snprintf(path, sizeof(path), "%s/invalid-%u", root, i) > 0);
        assert(run(argv[1], ":fixture:", path, values[i], false) == 2);
        assert(lstat(path, &stat) == -1 && errno == ENOENT);
    }
    snprintf(path, sizeof(path), "%s/good", root);
    assert(run(argv[1], ":fixture:", path, "8", false) == 0); assert(inspect(path, 0) == 48);
    assert(run(argv[1], ":fixture:", path, "8", false) == 1); assert(inspect(path, 0) == 48);
    snprintf(path, sizeof(path), "%s/nan", root);
    assert(run(argv[1], ":nan:", path, "8", false) == 1); assert(inspect(path, 1) == 0);
    snprintf(path, sizeof(path), "%s/failure", root);
    assert(run(argv[1], ":failure:", path, "8", false) == 1); assert(inspect(path, 1) == 0);
    snprintf(path, sizeof(path), "%s/tools", root);
    assert(run(argv[1], ":tools:", path, "8", true) == 0); assert(inspect(path, 0) == 36);
    assert(run(argv[1], ":tools:", path, "8", true) == 1); assert(inspect(path, 0) == 36);
    snprintf(path, sizeof(path), "%s/tools-truncated", root);
    assert(run(argv[1], ":tools:", path, "5", true) == 1); assert(inspect(path, 1) == 5);
    snprintf(path, sizeof(path), "%s/tools-nan", root);
    assert(run(argv[1], ":tools-nan:", path, "8", true) == 1); assert(inspect(path, 1) == 0);
    /* Preserve outputs under the caller's private build/evidence directory. */
    printf("SAMPLING_CAPTURE_FORMAT_LIFETIME_PASS_NOT_INFERENCE path=%s\n", root);
    free(root); return 0;
}
