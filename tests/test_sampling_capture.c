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
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
static int run(const char *binary, const char *model, const char *directory, const char *tokens) {
    pid_t child = fork(); assert(child >= 0);
    if (!child) {
        execl(binary, binary, "--model", model, "--output-dir", directory, "--tokens", tokens, NULL);
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
    unsigned rows = 0, profiles = 0; bool terminal = false, identity = false;
    while (getline(&line, &capacity, file) > 0) {
        json_object *j = json_tokener_parse(line); assert(j);
        const char *event = json_object_get_string(json_object_object_get(j, "event")); assert(event);
        assert(!terminal);
        if (!strcmp(event, "identity")) {
            assert(!identity && json_object_get_boolean(json_object_object_get(j, "synthetic")));
            assert(!strcmp(json_object_get_string(json_object_object_get(j, "classification")), "NOT-INFERENCE")); identity = true;
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
        } else if (!strcmp(event, "profile_complete")) ++profiles;
        else if (!strcmp(event, exit_code ? "failed" : "complete")) {
            assert(json_object_get_int(json_object_object_get(j, "exit_code")) == exit_code); terminal = true;
        } else assert(!strcmp(event, "profile_begin"));
        json_object_put(j);
    }
    assert(identity && terminal && !ferror(file)); free(line); assert(!fclose(file)); assert(!close(directory));
    assert(exit_code ? !profiles : profiles == 6 && rows == 48); return rows;
}
int main(int argc, char **argv) {
    assert(argc == 3);
    if (!strcmp(argv[1], "--fifo")) return mkfifo(argv[2], 0600) ? 1 : 0;
    char *root = strdup(argv[2]); assert(root && mkdtemp(root));
    char path[4096]; struct stat stat;
    for (unsigned i = 0; i < 3; ++i) {
        const char *values[] = {"0", "129", "invalid"};
        assert(snprintf(path, sizeof(path), "%s/invalid-%u", root, i) > 0);
        assert(run(argv[1], ":fixture:", path, values[i]) == 2);
        assert(lstat(path, &stat) == -1 && errno == ENOENT);
    }
    snprintf(path, sizeof(path), "%s/good", root);
    assert(run(argv[1], ":fixture:", path, "8") == 0); assert(inspect(path, 0) == 48);
    assert(run(argv[1], ":fixture:", path, "8") == 1); assert(inspect(path, 0) == 48);
    snprintf(path, sizeof(path), "%s/nan", root);
    assert(run(argv[1], ":nan:", path, "8") == 1); assert(inspect(path, 1) == 0);
    snprintf(path, sizeof(path), "%s/failure", root);
    assert(run(argv[1], ":failure:", path, "8") == 1); assert(inspect(path, 1) == 0);
    /* Preserve outputs under the caller's private build/evidence directory. */
    printf("SAMPLING_CAPTURE_FORMAT_LIFETIME_PASS_NOT_INFERENCE path=%s\n", root);
    free(root); return 0;
}
