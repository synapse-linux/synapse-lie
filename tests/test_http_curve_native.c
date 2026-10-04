/* SPDX-License-Identifier: MIT */
/* Independent pinned Gufo text/sequence goldens and owned HTTP CPU fixtures.
 * Synthetic counts and timings are NOT-INFERENCE, never performance evidence.
 */
#include "bench_native.h"
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static pid_t server = -1;
static char root[4096];
static void stop_owned(void) {
  if (server > 0) {
    kill(server, SIGTERM);
    while (waitpid(server, NULL, 0) < 0 && errno == EINTR) {
    }
    server = -1;
  }
}
static void check(bool ok, const char *why) {
  if (!ok) {
    fprintf(stderr, "Canonical CPU fixture: %s; evidence %s\n", why, root);
    stop_owned();
    exit(1);
  }
}
static void filename(char path[8192], const char *name) {
  check(snprintf(path, 8192, "%s/%s", root, name) < 8192, "path");
}
static int invoke(const char *binary, const char *const *args) {
  pid_t pid = fork();
  check(pid >= 0, "CLI fork");
  if (!pid) {
    setenv("PATH", "/no-interpreter-or-tools", 1);
    setenv("LC_ALL", "C", 1);
    execv(binary, (char *const *)args);
    _exit(127);
  }
  int status = 0;
  check(waitpid(pid, &status, 0) == pid && WIFEXITED(status),
        "CLI normal exit");
  return WEXITSTATUS(status);
}
static void send_all(int fd, const char *text, size_t bytes) {
  while (bytes) {
    ssize_t n = send(fd, text, bytes, MSG_NOSIGNAL);
    if (n < 0 && errno == EINTR)
      continue;
    if (n <= 0)
      _exit(20);
    text += n;
    bytes -= (size_t)n;
  }
}
static json_object *accept_body(int fd) {
  size_t used = 0, capacity = 8 * 1024 * 1024;
  char *buffer = malloc(capacity);
  if (!buffer)
    _exit(21);
  char *tail = NULL;
  while (!tail) {
    ssize_t n = recv(fd, buffer + used, capacity - used - 1, 0);
    if (n <= 0)
      _exit(22);
    used += (size_t)n;
    buffer[used] = 0;
    tail = strstr(buffer, "\r\n\r\n");
  }
  size_t header = (size_t)(tail + 4 - buffer), length = 0;
  char *size = strstr(buffer, "Content-Length: ");
  if (!size || sscanf(size, "Content-Length: %zu", &length) != 1 ||
      length > capacity - header - 1 ||
      !strstr(buffer, "X-Client-ID: model-bench\r\n") ||
      strncmp(buffer, "POST /v1/chat/completions HTTP/", 30))
    _exit(23);
  while (used < header + length) {
    ssize_t n = recv(fd, buffer + used, header + length - used, 0);
    if (n <= 0)
      _exit(24);
    used += (size_t)n;
  }
  nb_error e = {0};
  json_object *o = nb_parse(buffer + header, length, &e);
  free(buffer);
  if (!o)
    _exit(25);
  return o;
}
static void frame(int fd, json_object *o) {
  const char *s = nb_encoded(o);
  send_all(fd, "data: ", 6);
  send_all(fd, s, strlen(s));
  send_all(fd, "\n\n", 2);
  json_object_put(o);
}
static json_object *completion(bool stream, json_object *choices) {
  json_object *o = json_object_new_object();
  nb_str(o, "id", "fixture-NOT-INFERENCE");
  nb_str(o, "model", "bench");
  nb_str(o, "object", stream ? "chat.completion.chunk" : "chat.completion");
  json_object_object_add(o, "choices", choices);
  return o;
}
static void response(int fd, json_object *expected, bool gufo, bool mtp,
                     int fault) {
  bool stream = json_object_get_boolean(nb_get(expected, "stream"));
  unsigned budget = (unsigned)nb_number(expected, "budget");
  int64_t pp = nb_number(expected, "prompt"),
          cached = nb_number(expected, "cached"),
          tg = nb_number(expected, "output");
  bool measured = !strcmp(nb_string(expected, "phase"), "measured");
  if (fault == 1 && measured)
    --tg;
  json_object *usage = json_object_new_object(),
              *timing = json_object_new_object(),
              *details = json_object_new_object();
  nb_num(usage, "prompt_tokens", pp);
  nb_num(usage, "completion_tokens", tg);
  nb_num(usage, "total_tokens", pp + tg);
  nb_num(details, "cached_tokens", cached);
  json_object_object_add(usage, "prompt_tokens_details", details);
  nb_num(timing, "prefill_tokens", pp - cached);
  nb_real(timing, "prefill_ms", .05);
  nb_real(timing, "decode_ms", fault == 2 && measured ? -1 : .1);
  if (gufo) {
    json_object_object_add(usage, "gufo", timing);
    if (mtp) {
      nb_num(usage, "draft_tokens", 3);
      nb_num(usage, "draft_tokens_accepted", 1);
    }
  } else {
    nb_str(timing, "schema", "synapse-lie.request-timings.v1");
    nb_str(timing, "scope", "synchronous_executor_calls");
    json_object_object_add(timing, "valid", json_object_new_boolean(true));
    nb_str(timing, "decode_mode", mtp ? "mtp" : "ar");
    nb_num(timing, "decode_tokens", tg);
    nb_num(timing, "decode_calls", tg);
    nb_num(timing, "prefill_calls", 1);
    nb_num(timing, "cached_tokens", cached);
    nb_num(timing, "ssd_cached_tokens", 0);
    nb_real(timing, "prefill_tokens_per_second", (pp - cached) * 1000 / .05);
    nb_real(timing, "decode_tokens_per_second", tg * 1000 / .1);
    nb_real(timing, "cache_capture_ms", 0);
    nb_real(timing, "cache_restore_ms", 0);
    nb_real(timing, "ssd_read_ms", 0);
    if (mtp) {
      nb_num(timing, "max_decode_output_tokens", 4);
      nb_num(timing, "mtp_drafted_tokens", 3);
      nb_num(timing, "mtp_accepted_tokens", 1);
    }
  }
  const char *content = nb_string(expected, "content");
  json_object *choices = json_object_new_array(),
              *choice = json_object_new_object(),
              *text = json_object_new_object();
  nb_num(choice, "index", 0);
  nb_str(text, "content", content);
  nb_str(text, "role", "assistant");
  json_object_object_add(choice, stream ? "delta" : "message", text);
  json_object_array_add(choices, choice);
  struct timespec delay = {.tv_nsec = 3000000};
  nanosleep(&delay, NULL);
  if (stream) {
    const char *head = "HTTP/1.1 200 OK\r\nContent-Type: "
                       "text/event-stream\r\nConnection: close\r\n\r\n";
    send_all(fd, head, strlen(head));
    frame(fd, completion(true, choices));
    choices = json_object_new_array();
    choice = json_object_new_object();
    nb_num(choice, "index", 0);
    json_object_object_add(choice, "delta", json_object_new_object());
    nb_str(choice, "finish_reason", tg == budget ? "length" : "stop");
    json_object_array_add(choices, choice);
    json_object *o = completion(true, choices);
    json_object_object_add(o, "usage", usage);
    if (!gufo)
      json_object_object_add(o, "lie_timings", timing);
    frame(fd, o);
    if (fault != 3 || !measured)
      send_all(fd, "data: [DONE]\n\n", 14);
  } else {
    nb_str(choice, "finish_reason", tg == budget ? "length" : "stop");
    json_object *o = completion(false, choices);
    json_object_object_add(o, "usage", usage);
    if (!gufo)
      json_object_object_add(o, "lie_timings", timing);
    const char *s = nb_encoded(o);
    char head[256];
    snprintf(
        head, sizeof(head),
        "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
        "%zu\r\nConnection: close\r\n\r\n",
        strlen(s));
    send_all(fd, head, strlen(head));
    send_all(fd, s, strlen(s));
    json_object_put(o);
  }
  close(fd);
}
static void launch(char url[128], json_object *trace, bool gufo, bool mtp,
                   int fault) {
  int fd = socket(AF_INET, SOCK_STREAM, 0);
  check(fd >= 0, "fixture socket");
  struct sockaddr_in addr = {.sin_family = AF_INET,
                             .sin_addr.s_addr = htonl(INADDR_LOOPBACK)};
  check(!bind(fd, (struct sockaddr *)&addr, sizeof(addr)) && !listen(fd, 4),
        "private ephemeral fixture port");
  socklen_t length = sizeof(addr);
  check(!getsockname(fd, (struct sockaddr *)&addr, &length), "port");
  snprintf(url, 128, "http://127.0.0.1:%u/v1", ntohs(addr.sin_port));
  server = fork();
  check(server >= 0, "server fork");
  if (!server) {
    signal(SIGPIPE, SIG_IGN);
    for (size_t i = 0; i < json_object_array_length(trace); ++i) {
      int client = accept(fd, NULL, NULL);
      if (client < 0)
        _exit(26);
      struct timeval timeout = {.tv_sec = 3};
      setsockopt(client, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
      json_object *body = accept_body(client),
                  *expected = json_object_array_get_idx(trace, i);
      char hash[65];
      if (!nb_json_hash(nb_get(body, "messages"), hash) ||
          strcmp(hash, nb_string(expected, "messages_sha256")) ||
          nb_number(body, "max_tokens") != nb_number(expected, "budget") ||
          json_object_get_boolean(nb_get(body, "stream")) !=
              json_object_get_boolean(nb_get(expected, "stream")) ||
          strcmp(nb_string(body, "model"), "bench") ||
          json_object_get_double(nb_get(body, "temperature")) != 0 ||
          json_object_get_double(nb_get(body, "top_p")) != 1 ||
          json_object_get_double(nb_get(body, "frequency_penalty")) != 0 ||
          json_object_get_double(nb_get(body, "presence_penalty")) != 0 ||
          json_object_get_boolean(nb_get(nb_get(body, "chat_template_kwargs"),
                                         "enable_thinking")) !=
              json_object_get_boolean(nb_get(expected, "thinking")) ||
          (json_object_get_boolean(nb_get(expected, "thinking")) &&
           strcmp(nb_string(body, "reasoning_effort"), "high")) ||
          (gufo && (!nb_get(body, "top_k") || !nb_get(body, "min_p") ||
                    !nb_get(body, "repeat_penalty"))) ||
          (!gufo && (nb_get(body, "top_k") || nb_get(body, "min_p"))))
        _exit(27);
      json_object_put(body);
      response(client, expected, gufo, mtp, fault);
      if (fault && !strcmp(nb_string(expected, "phase"), "measured"))
        break;
    }
    close(fd);
    _exit(0);
  }
  close(fd);
}
static void done(void) {
  int status = 0;
  check(waitpid(server, &status, 0) == server, "server wait");
  server = -1;
  check(WIFEXITED(status) && WEXITSTATUS(status) == 0,
        "independent upstream request sequence");
}
static json_object *read_file(const char *path, bool lines) {
  nb_error e = {0};
  json_object *o = nb_read(path, lines, &e);
  check(o != NULL, e.message);
  return o;
}
static void goldens(const char *file) {
  json_object *data = read_file(file, false), *cases = nb_get(data, "cases");
  for (size_t i = 0; i < json_object_array_length(cases); ++i) {
    json_object *v = json_object_array_get_idx(cases, i);
    nb_error e = {0};
    char *text;
    if (!strcmp(nb_string(v, "kind"), "text"))
      text = nb_gufo_text((uint64_t)nb_number(v, "seed"),
                          (size_t)nb_number(v, "words"), &e);
    else
      text = nb_gufo_turn(json_object_get_double(nb_get(v, "target")),
                          json_object_get_double(nb_get(v, "ratio")),
                          nb_string(v, "task"), (uint64_t)nb_number(v, "depth"),
                          (unsigned)nb_number(v, "rep"),
                          (unsigned)nb_number(v, "attempt"), &e);
    char hash[65];
    check(text && nb_hash(text, strlen(text), hash) &&
              !strcmp(hash, nb_string(v, "sha256")) &&
              (int64_t)strlen(text) == nb_number(v, "bytes"),
          "exact Gufo seeded prompt golden");
    free(text);
  }
  check(nb_gufo_words(2.5, 1) == 2 && nb_gufo_words(3.5, 1) == 4 &&
            nb_gufo_words(-3, 1) == 1 && nb_gufo_words(1, 0) == 0 &&
            nb_gufo_words(INFINITY, 1) == 0,
        "bounded ties-to-even calibration rounding");
  nb_error e = {0};
  check(!nb_gufo_text(0, SIZE_MAX, &e) &&
            !nb_gufo_turn(2048, 1, "unknown", 0, 0, 0, &e),
        "bounded invalid workload");
  json_object_put(data);
}
static void mutate_reject(json_object *rows, const char *key) {
  json_object *copy = nb_copy(rows);
  json_object *row = json_object_array_get_idx(copy, 4);
  /* The first measured request follows identity, two probes, calibration, and
   * warmup: locate by phase rather than relying on event indices. */
  for (size_t i = 0; i < json_object_array_length(copy); ++i) {
    json_object *r = json_object_array_get_idx(copy, i);
    if (!strcmp(nb_string(r, "phase"), "measured")) {
      row = r;
      break;
    }
  }
  json_object *observation = nb_get(row, "observation");
  if (!strcmp(key, "budget"))
    nb_num(nb_get(observation, "usage"), "completion_tokens", 127);
  else if (!strcmp(key, "payload"))
    nb_str(nb_get(observation, "request"), "model", "changed");
  else if (!strcmp(key, "terminal"))
    json_object_object_add(observation, "stream_complete",
                           json_object_new_boolean(false));
  else if (!strcmp(key, "overflow"))
    nb_real(nb_get(nb_get(observation, "usage"), "gufo"), "prefill_ms", 1e-310);
  else if (!strcmp(key, "point")) {
    for (size_t i = 0; i < json_object_array_length(copy); ++i) {
      json_object *r = json_object_array_get_idx(copy, i);
      if (!strcmp(nb_string(r, "event"), "point")) {
        nb_real(r, "pp_tps", 1);
        break;
      }
    }
  } else
    nb_num(json_object_array_get_idx(copy, json_object_array_length(copy) - 1),
           "requests", 999);
  nb_error e = {0};
  json_object *result = nb_http_curve_summary(copy, &e);
  check(!result && e.message[0],
        "tampered or incomplete curve rejected by offline report");
  if (!strcmp(key, "overflow"))
    check(strstr(e.message, "rate overflow") != NULL,
          "nonfinite executed rate rejected before aggregation");
  json_object_put(result);
  json_object_put(copy);
}
int main(int argc, char **argv) {
  check(argc == 5,
        "binary, goldens, trace, persistent evidence template required");
  check(snprintf(root, sizeof(root), "%s", argv[4]) < (int)sizeof(root) &&
            mkdtemp(root),
        "persistent fixture directory");
  goldens(argv[2]);
  json_object *fixture = read_file(argv[3], false),
              *trace = nb_get(fixture, "requests");
  char url[128], lie[8192], gufo[8192], mtp[8192], graphs[8192];
  filename(lie, "lie-NOT-INFERENCE.jsonl");
  filename(gufo, "gufo-NOT-INFERENCE.jsonl");
  filename(mtp, "mtp-NOT-INFERENCE.jsonl");
  filename(graphs, "fixture-graphs");
  const char *outcomes[] = {lie, gufo, mtp};
  for (unsigned mode = 0; mode < 3; ++mode) {
    launch(url, trace, mode == 1, mode == 2, 0);
    const char *args[] = {argv[1],
                          "--suite",
                          "http-curve",
                          "--url",
                          url,
                          "--output",
                          outcomes[mode],
                          "--repetitions",
                          "2",
                          "--endpoint-profile",
                          mode == 1 ? "gufo" : "openai",
                          "--mode",
                          mode == 2 ? "mtp" : "ar",
                          "--server-label",
                          "NOT-INFERENCE",
                          "--timeout",
                          "3",
                          NULL};
    check(invoke(argv[1], args) == 0,
          "canonical CLI independent of Python/PATH");
    done();
    json_object *rows = read_file(outcomes[mode], true);
    nb_error e = {0};
    json_object *summary = nb_http_curve_summary(rows, &e);
    check(summary != NULL, e.message);
    json_object *points = nb_get(summary, "configurations");
    check(json_object_array_length(points) == 8, "all depths through128K");
    json_object *first = json_object_array_get_idx(points, 0),
                *last = json_object_array_get_idx(points, 7);
    check(nb_number(first, "depth") == 0 &&
              nb_number(last, "depth") == 131072 &&
              nb_number(last, "samples") == 2 &&
              nb_number(nb_get(last, "pp_tps"), "n") == 2 &&
              nb_get(nb_get(first, "pp_tps"), "sd"),
          "complete counts and statistics");
    if (!mode) {
      mutate_reject(rows, "payload");
      mutate_reject(rows, "budget");
      mutate_reject(rows, "terminal");
      mutate_reject(rows, "point");
      mutate_reject(rows, "count");
      const char *repeat[] = {argv[1], "--suite",  "http-curve", "--url",
                              url,     "--output", lie,          NULL};
      check(invoke(argv[1], repeat) != 0, "raw output cannot be overwritten");
    }
    if (mode == 1)
      mutate_reject(rows, "overflow");
    json_object_put(summary);
    json_object_put(rows);
  }
  const struct {
    const char *key, *depths, *task, *capacity;
    bool succeeds;
  } special[] = {{"exhausted_requests", "0", "prose", "133760", false},
                 {"thinking_requests", "0,4096", "thinking", "133760", true},
                 {"prefix_eos_requests", "4096", "prose", "133760", true},
                 {"million_requests", "1048576", "prose", "1051264", true}};
  for (size_t i = 0; i < sizeof(special) / sizeof(*special); ++i) {
    launch(url, nb_get(fixture, special[i].key), false, false, 0);
    char name[64], out[8192];
    snprintf(name, sizeof(name), "special-%zu.jsonl", i);
    filename(out, name);
    const char *args[] = {argv[1],
                          "--suite",
                          "http-curve",
                          "--url",
                          url,
                          "--output",
                          out,
                          "--depths",
                          special[i].depths,
                          "--task",
                          special[i].task,
                          "--context-capacity",
                          special[i].capacity,
                          "--server-label",
                          "NOT-INFERENCE",
                          "--timeout",
                          "3",
                          NULL};
    check((invoke(argv[1], args) == 0) == special[i].succeeds,
          "independent boundary protocol trace");
    done();
    json_object *rows = read_file(out, true);
    nb_error e = {0};
    json_object *s = nb_http_curve_summary(rows, &e);
    check((s != NULL) == special[i].succeeds,
          "offline boundary trace validation");
    if (!special[i].succeeds) {
      json_object *last =
          json_object_array_get_idx(rows, json_object_array_length(rows) - 1);
      check(nb_number(last, "requests") == 7 &&
                strstr(nb_string(last, "error"), "four attempts"),
            "four-attempt retry bound");
    }
    json_object_put(s);
    json_object_put(rows);
  }
  const char *report[] = {argv[1],
                          "--suite",
                          "report",
                          "--input",
                          lie,
                          "--output",
                          graphs,
                          "--compare",
                          gufo,
                          "--label",
                          "LIE NOT-INFERENCE",
                          "--reference-label",
                          "Gufo NOT-INFERENCE",
                          NULL};
  /* Report option names are independently checked by its public CLI. */
  check(invoke(argv[1], report) == 0,
        "native comparison, CSV and SVG/PNG without interpreter");
  char path[8192];
  filename(path, "fixture-graphs/summary.json");
  json_object *report_data = read_file(path, false);
  check(json_object_array_length(nb_get(report_data, "comparison")) == 8,
        "complete comparison");
  json_object_put(report_data);
  filename(path, "fixture-graphs/benchmark.svg");
  FILE *svg = fopen(path, "r");
  check(svg != NULL, "native SVG");
  char subtitle[4096];
  size_t bytes = fread(subtitle, 1, sizeof(subtitle) - 1, svg);
  subtitle[bytes] = 0;
  fclose(svg);
  check(strstr(subtitle, "Mean and observed min/max") != NULL,
        "graph accurately labels mean aggregation");
  for (unsigned fault = 1; fault <= 3; ++fault) {
    launch(url, trace, false, false, (int)fault);
    char name[64], output[8192];
    snprintf(name, sizeof(name), "failure-%u.jsonl", fault);
    filename(output, name);
    const char *args[] = {argv[1], "--suite",   "http-curve", "--url",
                          url,     "--output",  output,       "--repetitions",
                          "2",     "--timeout", "3",          NULL};
    check(invoke(argv[1], args) != 0,
          "EOS, invalid timing and missing SSE terminal fail");
    done();
    json_object *rows = read_file(output, true);
    nb_error e = {0};
    json_object *s = nb_http_curve_summary(rows, &e);
    check(!s && e.message[0], "failed curves cannot be averaged");
    json_object_put(s);
    json_object_put(rows);
  }
  const char *bad[] = {argv[1],    "--suite", "http-curve", "--url",     url,
                       "--output", lie,       "--depths",   "0,1048576", NULL};
  check(invoke(argv[1], bad) == 2,
        "unsupported declared capacity refused before contact");
  const char *help[] = {argv[1], "--suite", "http-curve", "--help", NULL};
  check(invoke(argv[1], help) == 0, "native help");
  json_object_put(fixture);
  printf("Canonical Gufo CPU contracts passed; NOT-INFERENCE. Evidence: %s\n",
         root);
  return 0;
}
