/* SPDX-License-Identifier: MIT */
/* Native parser/artifact/failure checks; only owned HOST-fixture children. */
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <json-c/json.h>
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

static int run(const char *binary, char *const *argv, const char *fault) {
  pid_t child = fork(); assert(child >= 0);
  if (!child) {
    if (fault) assert(!setenv("LIE_ATTENTION_FIXTURE_FAULT", fault, 1));
    else assert(!unsetenv("LIE_ATTENTION_FIXTURE_FAULT"));
    execv(binary, argv); _exit(127);
  }
  struct timespec pause = {0, 10000000}; int status = 0;
  for (unsigned i = 0; i < 3000; ++i) {
    pid_t seen = waitpid(child, &status, WNOHANG);
    if (seen == child) { assert(WIFEXITED(status)); return WEXITSTATUS(status); }
    assert(seen == 0 || (seen < 0 && errno == EINTR)); nanosleep(&pause, NULL);
  }
  /* Our unreaped direct child only. */
  kill(child, SIGKILL); assert(waitpid(child, &status, 0) == child);
  assert(!"owned fixture timed out"); return 1;
}
static void artifact(int directory, json_object *record) {
  assert(record);
  const char *name = json_object_get_string(json_object_object_get(record, "file"));
  assert(name && !strchr(name, '/'));
  int fd = openat(directory, name, O_RDONLY | O_NOFOLLOW); assert(fd >= 0);
  struct stat st; assert(!fstat(fd, &st) && S_ISREG(st.st_mode) && st.st_size > 0);
  assert((uint64_t)st.st_size == json_object_get_uint64(json_object_object_get(record, "bytes")));
  assert((st.st_mode & 0777) == 0600);
  EVP_MD_CTX *ctx = EVP_MD_CTX_new(); assert(ctx && EVP_DigestInit_ex(ctx, EVP_sha256(), NULL));
  unsigned char data[4096], digest[32]; ssize_t n;
  while ((n = read(fd, data, sizeof(data))) > 0) assert(EVP_DigestUpdate(ctx, data, (size_t)n));
  assert(n == 0 && !close(fd)); unsigned bytes = 0;
  assert(EVP_DigestFinal_ex(ctx, digest, &bytes) && bytes == 32); EVP_MD_CTX_free(ctx);
  char hash[65]; for (unsigned i = 0; i < bytes; ++i) snprintf(hash + i * 2, 3, "%02x", digest[i]);
  assert(!strcmp(hash, json_object_get_string(json_object_object_get(record, "sha256"))));
}
static void inspect(const char *path, int exit_code, unsigned cases) {
  int dir = open(path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW); assert(dir >= 0);
  struct stat st; assert(!fstat(dir, &st) && (st.st_mode & 0777) == 0700);
  int fd = openat(dir, "attention.jsonl", O_RDONLY | O_NOFOLLOW); assert(fd >= 0);
  FILE *file = fdopen(fd, "r"); assert(file);
  char *line = NULL; size_t capacity = 0; unsigned seen = 0; bool identity = false, terminal = false;
  while (getline(&line, &capacity, file) > 0) {
    json_object *j = json_tokener_parse(line); assert(j && !terminal);
    const char *event = json_object_get_string(json_object_object_get(j, "event")); assert(event);
    if (!strcmp(event, "identity")) {
      assert(!identity && !seen); identity = true;
      assert(json_object_get_boolean(json_object_object_get(j, "host_fixture")));
      assert(json_object_get_boolean(json_object_object_get(j, "synthetic")));
      assert(!json_object_get_boolean(json_object_object_get(j, "model_inference")));
      assert(!strcmp(json_object_get_string(json_object_object_get(j, "schema")), "synapse-lie.attention-fixture.v1"));
    } else if (!strcmp(event, "case")) {
      assert(identity && json_object_get_int(json_object_object_get(j, "index")) == (int)seen);
      assert(!json_object_get_boolean(json_object_object_get(j, "gpu_execution")) || exit_code);
      const char *keys[] = {"deep_output", "short_output", "blocks", "deep_mask", "short_mask"};
      for (unsigned i = 0; i < 5; ++i) artifact(dir, json_object_object_get(j, keys[i]));
      assert(json_object_get_boolean(json_object_object_get(j, "artifacts_complete")));
      assert(json_object_get_boolean(json_object_object_get(j, "passed")) == (seen + 1 < cases || !exit_code));
      ++seen;
    } else {
      assert(!strcmp(event, exit_code ? "failed" : "complete")); terminal = true;
      assert(json_object_get_int(json_object_object_get(j, "exit_code")) == exit_code);
      assert(json_object_get_int(json_object_object_get(j, "completed_cases")) == (int)(cases - (exit_code ? 1 : 0)));
    }
    json_object_put(j);
  }
  assert(identity && terminal && seen == cases && !ferror(file)); free(line);
  assert(!fclose(file) && !close(dir));
}
int main(int argc, char **argv) {
  assert(argc == 3); char *root = strdup(argv[2]); assert(root && mkdtemp(root));
  char path[4096]; snprintf(path, sizeof(path), "%s/invalid", root);
  char *invalid[][8] = {
    {argv[1], NULL}, {argv[1], "--run", NULL},
    {argv[1], "--output-dir", path, NULL},
    {argv[1], "--run", "--run", "--output-dir", path, NULL},
    {argv[1], "--run", "--output-dir", path, "--output-dir", path, NULL},
    {argv[1], "--run", "--output-dir", NULL},
    {argv[1], "--run", "--output-dir", "", NULL},
    {argv[1], "--run", "--output-dir", path, "--unknown", NULL},
    {argv[1], "--help", "--run", NULL}};
  struct stat st;
  for (unsigned i = 0; i < sizeof(invalid) / sizeof(invalid[0]); ++i) {
    assert(run(argv[1], invalid[i], NULL) == 2);
    assert(lstat(path, &st) == -1 && errno == ENOENT);
  }
  char *help[] = {argv[1], "--help", NULL}; assert(!run(argv[1], help, NULL));
  snprintf(path, sizeof(path), "%s/good", root);
  char *valid[] = {argv[1], "--run", "--output-dir", path, NULL};
  assert(!run(argv[1], valid, NULL)); inspect(path, 0, 13);
  assert(run(argv[1], valid, NULL) == 1); inspect(path, 0, 13);
  char link[4096]; snprintf(link, sizeof(link), "%s/link", root); assert(!symlink(path, link));
  valid[3] = link; assert(run(argv[1], valid, NULL) == 1); inspect(path, 0, 13); valid[3] = path;
  const char *faults[] = {"mismatch", "nan", "primary", "cleanup", "gpu", "refusal", "short", "uniform"};
  for (unsigned i = 0; i < sizeof(faults) / sizeof(faults[0]); ++i) {
    snprintf(path, sizeof(path), "%s/fault-%s", root, faults[i]);
    assert(run(argv[1], valid, faults[i]) == 1); inspect(path, 1, i == 7 ? 13 : 1);
  }
  free(root); return 0;
}
