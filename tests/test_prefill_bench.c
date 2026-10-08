/* SPDX-License-Identifier: MIT */
/* Native qualification-client fixture. No weights, model forward or GPU. */
#include "bench_native.h"
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static char root[2048];
static pid_t owned = -1;
static void pause_short(void) {
  struct timespec delay = {0, 10000000};
  while (nanosleep(&delay, &delay) && errno == EINTR) {}
}
static void cleanup(void) {
  if (owned <= 0) return;
  (void)kill(owned, SIGTERM);
  int status;
  for (unsigned i = 0; i < 100; ++i) {
    pid_t done = waitpid(owned, &status, WNOHANG);
    if (done == owned || (done < 0 && errno == ECHILD)) {
      owned = -1;
      return;
    }
    pause_short();
  }
  (void)kill(owned, SIGKILL);
  while (waitpid(owned, &status, 0) < 0 && errno == EINTR) {}
  owned = -1;
}
static void require(bool ok, const char *message) {
  if (!ok) {
    fprintf(stderr, "Prefill bench fixture: %s (artifacts: %s)\n", message, root);
    exit(1);
  }
}
static bool flag(json_object *object, const char *name) {
  json_object *value = nb_get(object, name);
  return json_object_is_type(value, json_type_boolean) &&
         json_object_get_boolean(value);
}
static void path(char out[2400], const char *name) {
  require(snprintf(out, 2400, "%s/%s", root, name) < 2400, "path length");
}
typedef struct { char *args[64]; size_t count; } command;
static void append(command *cmd, const char *value) {
  require(cmd->count + 1 < 64, "argument count");
  cmd->args[cmd->count++] = (char *)value;
  cmd->args[cmd->count] = NULL;
}
static void set(command *cmd, const char *key, const char *value) {
  for (size_t i = 1; i + 1 < cmd->count; ++i) {
    if (!strcmp(cmd->args[i], key)) {
      cmd->args[i + 1] = (char *)value;
      return;
    }
  }
  require(false, "missing argument to replace");
}
static void remove_flag(command *cmd, const char *name) {
  for (size_t i = 1; i < cmd->count; ++i) {
    if (!strcmp(cmd->args[i], name)) {
      memmove(cmd->args + i, cmd->args + i + 1,
              (cmd->count - i) * sizeof(*cmd->args));
      --cmd->count;
      return;
    }
  }
  require(false, "missing flag to remove");
}
static void base(command *cmd, const char *binary, const char *mode,
                 const char *output, const char *tokens) {
  *cmd = (command){0};
  const char *args[] = {
      binary, "--suite", "core", "--model",
      !strcmp(mode, "live") ? ":progress-fixture:" : ":fixture:",
      "--output", output, "--tokens-file", tokens, "--context", "128",
      "--prefill-chunk", "8", "--prefill-capacity", "32", "--users",
      !strcmp(mode, "live") ? "2" : "1", "--tg", "32", "--warmups", "0",
      "--repetitions", "1", "--kv-cache-ram-mb",
      !strcmp(mode, "ram") ? "1" : "0", "--ignore-eos",
      "--prefill-probe", mode, "--timeout-ms", "10000",
      "--kv-cache-min-tokens", "16", "--kv-cache-boundary-trim-tokens", "0",
      "--kv-cache-boundary-align-tokens", "8"};
  for (size_t i = 0; i < sizeof(args) / sizeof(*args); ++i) append(cmd, args[i]);
}
static void run(const command *cmd, const char *name, int expected) {
  char log[2400];
  path(log, name);
  owned = fork();
  require(owned >= 0, "fork");
  if (!owned) {
    int fd = open(log, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (fd < 0 || dup2(fd, STDOUT_FILENO) < 0 ||
        dup2(fd, STDERR_FILENO) < 0) _exit(126);
    close(fd);
    execv(cmd->args[0], cmd->args);
    _exit(127);
  }
  int status = 0;
  bool done = false;
  for (unsigned i = 0; i < 3000; ++i) {
    pid_t result = waitpid(owned, &status, WNOHANG);
    if (result == owned) { done = true; owned = -1; break; }
    require(result == 0 || (result < 0 && errno == EINTR), "waitpid");
    pause_short();
  }
  require(done, "owned child deadline");
  if (!WIFEXITED(status) || WEXITSTATUS(status) != expected) {
    fprintf(stderr, "%s: raw wait status %d, expected exit %d; log: %s\n",
            name, status, expected, log);
    require(false, "actual child exit");
  }
  printf("%s: actual exit %d\n", name, WEXITSTATUS(status));
}
static json_object *row(json_object *rows, const char *name, size_t occurrence) {
  for (size_t i = 0; i < json_object_array_length(rows); ++i) {
    json_object *value = json_object_array_get_idx(rows, i);
    if (!strcmp(nb_string(value, "event"), name) && !occurrence--) return value;
  }
  require(false, "missing witness event");
  return NULL;
}
static void validate(const char *output, const char *mode) {
  nb_error error = {0};
  json_object *rows = nb_read(output, true, &error);
  require(rows != NULL, error.message);
  json_object *id = json_object_array_get_idx(rows, 0);
  require(flag(id, "synthetic") &&
              !strcmp(nb_string(id, "prefill_probe"), mode),
          "fixture classification");
  json_object *last = json_object_array_get_idx(
      rows, json_object_array_length(rows) - 1);
  require(!strcmp(nb_string(last, "event"), "complete") &&
              nb_number(last, "exit_code") == 0, "completed client");
  json_object *complete = row(rows, "prefill_probe_complete", 0);
  require(nb_number(complete, "prompt_tokens") == 64 &&
              nb_number(complete, "output_tokens") == 32, "full token budgets");
  json_object *baseline = nb_get(complete, "baseline_output_ids");
  require(json_object_array_length(baseline) == 32, "complete saved baseline");
  if (!strcmp(mode, "live")) {
    json_object *transition = row(rows, "prefill_transition", 0);
    require(flag(transition, "same_owner_call_observed") &&
                flag(transition, "immutable_admissions") &&
                nb_number(transition, "queued_after_changes") >= 1,
            "in-flight immutable queue witness");
    require(nb_number(nb_get(transition, "active_job"), "chunk_tokens") == 8 &&
                nb_number(nb_get(transition, "active_job"), "revision") == 1 &&
                nb_number(nb_get(transition, "queued_job"), "chunk_tokens") == 32 &&
                nb_number(nb_get(transition, "queued_job"), "revision") == 2 &&
                nb_number(nb_get(transition, "current_core"), "revision") == 3,
            "admission choices");
    json_object *live = row(rows, "prefill_live_result", 0);
    require(nb_number(live, "active_prefill_calls") == 8 &&
                nb_number(live, "peer_prefill_calls") == 2 &&
                json_object_equal(baseline, nb_get(live, "peer_output_ids")),
            "completed immutable calls and full output equality");
    json_object *reactive = row(rows, "reactive", 0);
    require(nb_number(reactive, "completed_delta") == 1 &&
                nb_number(reactive, "cancelled_delta") == 1 &&
                nb_number(reactive, "held_output_blocked") == 1,
            "credit isolation and borrowed-loan cancellation");
    json_object *cancel = row(rows, "prefill_cancel", 0);
    require(flag(cancel, "same_owner_call_observed") &&
                flag(cancel, "retired") &&
                nb_number(cancel, "cancel_during_prefill_delta") == 1 &&
                nb_number(cancel, "failed_delta") == 0 &&
                nb_number(cancel, "output_tokens") == 0,
            "in-flight cancellation without failed engine");
    require(json_object_equal(baseline, nb_get(row(rows, "job", 1), "output_ids")),
            "fresh inference after prefill cancellation");
  } else {
    for (size_t step = 0; step < 5; ++step) {
      json_object *cache = row(rows, "prefill_cache_step", step);
      bool hot = step == 1 || step == 3 || step == 4;
      require(flag(cache, "verified") &&
                  nb_number(cache, "cached_tokens") == (hot ? 64 : 0) &&
                  nb_number(cache, "ssd_cached_tokens") ==
                      (hot && !strcmp(mode, "ssd") ? 64 : 0) &&
                  nb_number(cache, "prefill_calls") ==
                      (hot ? 0 : step == 2 ? 2 : 8),
              "cache namespace miss/hit");
      require(json_object_equal(baseline, nb_get(row(rows, "job", step), "output_ids")),
              "complete restored output equality");
    }
  }
  char directory[2400];
  require(snprintf(directory, sizeof(directory), "%s.report", output) <
              (int)sizeof(directory), "refused report path");
  memset(&error, 0, sizeof(error));
  require(nb_report(output, directory, "probe", NULL, NULL, false, &error) != 0 &&
              strstr(error.message, "Functional prefill") != NULL,
          "functional evidence refused as a throughput report");
  json_object_put(rows);
}
int main(int argc, char **argv) {
  require(argc == 3, "binary and private fixture-directory pattern");
  require(strlen(argv[2]) < sizeof(root), "fixture-directory pattern length");
  strcpy(root, argv[2]);
  require(mkdtemp(root) != NULL, "private fixture directory");
  atexit(cleanup);
  char tokens[2400];
  path(tokens, "tokens.json");
  FILE *file = fopen(tokens, "wx");
  require(file != NULL, "exclusive physical-token file");
  fputc('[', file);
  for (unsigned i = 0; i < 64; ++i) fprintf(file, "%s%u", i ? "," : "", i);
  require(fputs("]\n", file) >= 0 && !fclose(file), "save physical tokens");
  const char *modes[] = {"live", "ram", "ssd"};
  for (unsigned mtp = 0; mtp < 2; ++mtp) for (size_t i = 0; i < 3; ++i) {
    char name[64], output[2400], disk[2400], log[64];
    snprintf(name, sizeof(name), "%s-%s.jsonl", modes[i], mtp ? "mtp" : "ar");
    path(output, name);
    command cmd;
    base(&cmd, argv[1], modes[i], output, tokens);
    if (mtp) { append(&cmd, "--model-mtp"); append(&cmd, ":fixture:"); }
    if (i == 2) {
      snprintf(name, sizeof(name), "ssd-%s", mtp ? "mtp" : "ar");
      path(disk, name);
      require(!mkdir(disk, 0700), "private SSD fixture directory");
      append(&cmd, "--kv-disk-dir"); append(&cmd, disk);
      append(&cmd, "--kv-disk-space-mb"); append(&cmd, "4");
      append(&cmd, "--kv-disk-staging-mb"); append(&cmd, "1");
    }
    snprintf(log, sizeof(log), "%s-%s.log", modes[i], mtp ? "mtp" : "ar");
    run(&cmd, log, 0);
    validate(output, modes[i]);
  }
  const char *keys[] = {"--prefill-probe", "--prefill-capacity", "--users",
                       "--warmups", "--repetitions", "--progress-ms",
                       "--temperature", "--frequency-penalty", "--presence-penalty",
                       "--kv-cache-ram-mb", "--graphs"};
  const char *values[] = {"unknown", "8", "1", "1", "2", "100",
                         "0.5", "1", "1", "1", "invalid-probe-graphs"};
  for (size_t i = 0; i < sizeof(keys) / sizeof(*keys) + 3; ++i) {
    char output[2400], name[64], log[64];
    snprintf(name, sizeof(name), "refusal-%zu.jsonl", i);
    snprintf(log, sizeof(log), "refusal-%zu.log", i);
    path(output, name);
    command cmd;
    base(&cmd, argv[1], "live", output, tokens);
    if (i < sizeof(keys) / sizeof(*keys)) {
      if (!strcmp(keys[i], "--progress-ms") || !strcmp(keys[i], "--graphs") ||
          !strcmp(keys[i], "--temperature") || !strcmp(keys[i], "--frequency-penalty") ||
          !strcmp(keys[i], "--presence-penalty")) {
        append(&cmd, keys[i]); append(&cmd, values[i]);
        if (!strcmp(keys[i], "--temperature")) {
          append(&cmd, "--seed"); append(&cmd, "1");
        }
      } else set(&cmd, keys[i], values[i]);
    } else if (i == sizeof(keys) / sizeof(*keys)) remove_flag(&cmd, "--ignore-eos");
    else if (i == sizeof(keys) / sizeof(*keys) + 1) {
      append(&cmd, "--prefill-probe"); append(&cmd, "live");
    } else append(&cmd, "--reactive-probe");
    run(&cmd, log, 2);
    require(access(output, F_OK) != 0 && errno == ENOENT,
            "invalid request opened output or model path");
  }
  char output[2400];
  path(output, "failed-prefill.jsonl");
  command failure;
  base(&failure, argv[1], "live", output, tokens);
  set(&failure, "--model", ":progress-failure:");
  run(&failure, "failed-prefill.log", 1);
  nb_error error = {0};
  json_object *rows = nb_read(output, true, &error);
  require(rows != NULL && !strcmp(nb_string(json_object_array_get_idx(
              rows, json_object_array_length(rows) - 1), "event"), "failed"),
          "failed prefill retained with its actual exit");
  json_object_put(rows);
  printf("Native prefill probes: PASS (NOT-INFERENCE; artifacts: %s)\n", root);
  return 0;
}
