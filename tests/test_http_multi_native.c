/* SPDX-License-Identifier: MIT */
/* Synthetic wire/math fixtures. No model or GPU execution. The server waits
 * for every participant before replying, so a serial transport cannot pass. */
#include "bench_native.h"
#include <arpa/inet.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <poll.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
static char root[2048];
static pid_t server = -1;
static void own_stop(void) {
  if (server > 0) {
    kill(server, SIGTERM);
    while (waitpid(server, NULL, 0) < 0 && errno == EINTR) {
    }
    server = -1;
  }
}
static void require(bool ok, const char *why) {
  if (!ok) {
    fprintf(stderr, "HTTP multi CPU fixture: %s; evidence %s\n", why, root);
    own_stop();
    exit(1);
  }
}
static void pause_ms(unsigned ms) {
  struct timespec delay = {ms / 1000, (long)(ms % 1000) * 1000000};
  while (nanosleep(&delay, &delay) && errno == EINTR) {
  }
}
static void path(char out[2300], const char *name) {
  require(snprintf(out, 2300, "%s/%s", root, name) < 2300, "path");
}
static void save_rows(const char *name, json_object *rows) {
  char p[2300];
  path(p, name);
  FILE *f = fopen(p, "w");
  require(f != NULL, "save");
  for (size_t i = 0; i < json_object_array_length(rows); ++i)
    require(nb_emit(f, json_object_array_get_idx(rows, i)), "emit");
  require(!fclose(f), "close");
}
static json_object *read_rows(const char *name) {
  char p[2300];
  path(p, name);
  nb_error e = {0};
  json_object *r = nb_read(p, true, &e);
  require(r != NULL, e.message);
  return r;
}
static void send_all(int fd, const char *bytes, size_t n) {
  while (n) {
    ssize_t done = send(fd, bytes, n, MSG_NOSIGNAL);
    if (done <= 0)
      _exit(3);
    bytes += done;
    n -= (size_t)done;
  }
}
static unsigned accept_body(int fd, char client[192], unsigned budget) {
  char wire[16384];
  size_t bytes = 0;
  char *tail = NULL;
  unsigned length = 0;
  for (;;) {
    ssize_t got = recv(fd, wire + bytes, sizeof(wire) - bytes - 1, 0);
    if (got <= 0)
      _exit(4);
    bytes += (size_t)got;
    wire[bytes] = 0;
    tail = strstr(wire, "\r\n\r\n");
    if (tail) {
      char *header = strstr(wire, "Content-Length:");
      if (!header)
        _exit(5);
      if (sscanf(header, "Content-Length: %u", &length) != 1 || length > 8192)
        _exit(5);
      if (bytes >= (size_t)(tail + 4 - wire) + length)
        break;
    }
    if (bytes + 1 == sizeof(wire))
      _exit(5);
  }
  char *header = strstr(wire, "X-Client-ID: ");
  if (!header)
    _exit(6);
  header += 13;
  char *end = strstr(header, "\r\n");
  if (!end || end - header >= 191)
    _exit(6);
  memcpy(client, header, (size_t)(end - header));
  client[end - header] = 0;
  char *index = strrchr(client, 'i');
  if (!index)
    _exit(6);
  unsigned slot;
  if (sscanf(index, "i%u", &slot) != 1 || slot > 7)
    _exit(6);
  nb_error error = {0};
  json_object *body = nb_parse(tail + 4, length, &error);
  if (!body || nb_number(body, "max_tokens") != budget ||
      strcmp(nb_string(body, "model"), "fixture") ||
      !json_object_get_boolean(nb_get(body, "stream")) ||
      json_object_get_boolean(
          nb_get(nb_get(body, "chat_template_kwargs"), "enable_thinking")))
    _exit(7);
  json_object_put(body);
  return slot;
}
static json_object *chunk(json_object *choices) {
  json_object *o = json_object_new_object();
  nb_str(o, "id", "fixture-NOT-INFERENCE");
  nb_str(o, "model", "fixture");
  nb_str(o, "object", "chat.completion.chunk");
  json_object_object_add(o, "choices", choices);
  return o;
}
static void frame(int fd, json_object *o) {
  const char *json = nb_encoded(o);
  send_all(fd, "data: ", 6);
  send_all(fd, json, strlen(json));
  send_all(fd, "\n\n", 2);
  json_object_put(o);
}
static void reply(int fd, unsigned slot, unsigned budget, bool gufo, int fault,
                  bool measured) {
  const char *head = "HTTP/1.1 200 OK\r\nContent-Type: "
                     "text/event-stream\r\nConnection: close\r\n\r\n";
  send_all(fd, head, strlen(head));
  json_object *choices = json_object_new_array(),
              *choice = json_object_new_object(),
              *delta = json_object_new_object();
  char text[16];
  memset(text, 'x', budget);
  text[budget] = 0;
  nb_str(delta, "content", text);
  nb_num(choice, "index", 0);
  json_object_object_add(choice, "delta", delta);
  json_object_object_add(choice, "finish_reason", NULL);
  json_object_array_add(choices, choice);
  frame(fd, chunk(choices));
  if (fault == 2 && measured && slot == 0) {
    close(fd);
    return;
  }
  choices = json_object_new_array();
  choice = json_object_new_object();
  nb_num(choice, "index", 0);
  json_object_object_add(choice, "delta", json_object_new_object());
  nb_str(choice, "finish_reason", "length");
  json_object_array_add(choices, choice);
  frame(fd, chunk(choices));
  json_object *o = chunk(json_object_new_array()),
              *usage = json_object_new_object(),
              *details = json_object_new_object();
  int64_t cached = measured ? 2047 : 0;
  if (fault == 1 && measured)
    cached = 2040;
  nb_num(usage, "prompt_tokens", 2048);
  nb_num(usage, "completion_tokens", budget);
  nb_num(usage, "total_tokens", 2048 + budget);
  nb_num(details, "cached_tokens", cached);
  json_object_object_add(usage, "prompt_tokens_details", details);
  double ms = 2 + slot;
  json_object *timing = json_object_new_object();
  nb_num(timing, "prefill_tokens", 2048 - cached);
  nb_real(timing, "prefill_ms", 1);
  nb_real(timing, "decode_ms", ms);
  if (gufo)
    json_object_object_add(usage, "gufo", timing);
  else {
    nb_str(timing, "schema", "synapse-lie.request-timings.v1");
    nb_str(timing, "scope", "synchronous_executor_calls");
    json_object_object_add(timing, "valid", json_object_new_boolean(true));
    nb_str(timing, "decode_mode", "ar");
    nb_num(timing, "decode_tokens", budget);
    nb_num(timing, "decode_calls", budget);
    nb_num(timing, "prefill_calls", 1);
    nb_num(timing, "cached_tokens", cached);
    nb_num(timing, "ssd_cached_tokens", 0);
    nb_real(timing, "prefill_tokens_per_second", (2048 - cached) * 1000);
    nb_real(timing, "decode_tokens_per_second", budget * 1000 / ms);
    nb_real(timing, "cache_restore_ms", 0);
    nb_real(timing, "cache_capture_ms", 0);
    nb_real(timing, "ssd_read_ms", 0);
    json_object_object_add(o, "lie_timings", timing);
  }
  json_object_object_add(o, "usage", usage);
  frame(fd, o);
  send_all(fd, "data: [DONE]\n\n", 14);
  close(fd);
}
static void fake_server(int listener, bool gufo, const unsigned *levels,
                        size_t n, unsigned runs, int fault) {
  signal(SIGPIPE, SIG_IGN);
  for (size_t l = 0; l < n; ++l)
    for (unsigned r = 0; r < runs; ++r) {
      char prepared[8][192] = {{0}};
      for (unsigned phase = 0; phase < 2; ++phase) {
        int clients[8];
        unsigned slots[8];
        bool used[8] = {0};
        for (unsigned i = 0; i < levels[l]; ++i) {
          clients[i] = accept(listener, NULL, NULL);
          if (clients[i] < 0)
            _exit(2);
          struct timeval timeout = {3, 0};
          setsockopt(clients[i], SOL_SOCKET, SO_RCVTIMEO, &timeout,
                     sizeof(timeout));
          char id[192];
          slots[i] = accept_body(clients[i], id, phase ? 8 : 1);
          if (slots[i] >= levels[l] || used[slots[i]])
            _exit(8);
          used[slots[i]] = true;
          if (!phase)
            strcpy(prepared[slots[i]], id);
          else if (strcmp(prepared[slots[i]], id))
            _exit(8);
        }
        /* No response until ALL requests arrived; independently known phase
         * durations differ between participants, exposing sum-vs-wall mistakes.
         */
        pause_ms(20);
        for (unsigned i = 0; i < levels[l]; ++i)
          reply(clients[i], slots[i], phase ? 8 : 1, gufo, fault, phase != 0);
      }
    }
  close(listener);
  _exit(0);
}
static void launch_server(char url[128], bool gufo, const unsigned *levels,
                          size_t n, unsigned runs, int fault) {
  int fd = socket(AF_INET, SOCK_STREAM, 0);
  require(fd >= 0, "socket");
  struct sockaddr_in address = {.sin_family = AF_INET,
                                .sin_addr.s_addr = htonl(INADDR_LOOPBACK)};
  require(!bind(fd, (struct sockaddr *)&address, sizeof(address)) &&
              !listen(fd, 16),
          "listen");
  socklen_t bytes = sizeof(address);
  require(!getsockname(fd, (struct sockaddr *)&address, &bytes), "address");
  snprintf(url, 128, "http://127.0.0.1:%u/v1", ntohs(address.sin_port));
  server = fork();
  require(server >= 0, "server fork");
  if (!server)
    fake_server(fd, gufo, levels, n, runs, fault);
  close(fd);
}
static void server_done(void) {
  int status;
  pid_t pid = server;
  while (waitpid(pid, &status, 0) < 0 && errno == EINTR) {
  }
  server = -1;
  require(WIFEXITED(status) && WEXITSTATUS(status) == 0, "fixture server exit");
}
static volatile sig_atomic_t cohort_interrupted;
static void interrupt_cohort(int number) {
  (void)number;
  cohort_interrupted = 1;
}
/* A silent owned peer exposes deadline and cancellation cleanup independently
 * of SSE parsing. The peer requires EOF on every connection it receives. */
static void bounded_transport(bool interrupt) {
  int fd = socket(AF_INET, SOCK_STREAM, 0);
  struct sockaddr_in address = {.sin_family = AF_INET,
                                .sin_addr.s_addr = htonl(INADDR_LOOPBACK)};
  require(fd >= 0 && !bind(fd, (struct sockaddr *)&address, sizeof(address)) &&
              !listen(fd, 4),
          "silent peer listen");
  socklen_t bytes = sizeof(address);
  require(!getsockname(fd, (struct sockaddr *)&address, &bytes),
          "silent address");
  unsigned count = interrupt ? 2 : 1;
  server = fork();
  require(server >= 0, "silent peer fork");
  if (!server) {
    int connections[2], accepted = 0;
    for (unsigned i = 0; i < count; ++i) {
      struct pollfd waiting = {.fd = fd, .events = POLLIN};
      if (poll(&waiting, 1, 500) <= 0)
        break;
      connections[accepted] = accept(fd, NULL, NULL);
      if (connections[accepted] < 0)
        _exit(12);
      ++accepted;
    }
    close(fd);
    for (int i = 0; i < accepted; ++i) {
      struct timeval deadline = {.tv_sec = 1};
      setsockopt(connections[i], SOL_SOCKET, SO_RCVTIMEO, &deadline,
                 sizeof(deadline));
      char buffer[16384];
      ssize_t got;
      do {
        got = recv(connections[i], buffer, sizeof(buffer), 0);
      } while (got > 0 || (got < 0 && errno == EINTR));
      if (got != 0)
        _exit(13);
      close(connections[i]);
    }
    _exit(0);
  }
  close(fd);
  char url[128];
  snprintf(url, sizeof(url), "http://127.0.0.1:%u/v1", ntohs(address.sin_port));
  nb_error error = {0};
  json_object *bodies = json_object_new_array();
  for (unsigned i = 0; i < count; ++i)
    json_object_array_add(bodies, nb_parse("{}", 2, &error));
  nb_http_options options = {.url = url,
                             .model = "NOT-INFERENCE",
                             .stream = true,
                             .timeout = interrupt ? 3 : 0.0001,
                             .interrupted = &cohort_interrupted};
  struct sigaction handler = {0}, old;
  handler.sa_handler = interrupt_cohort;
  sigemptyset(&handler.sa_mask);
  cohort_interrupted = 0;
  if (interrupt) {
    require(!sigaction(SIGALRM, &handler, &old), "interrupt handler");
    struct itimerval timer = {.it_value = {.tv_usec = 100000}};
    require(!setitimer(ITIMER_REAL, &timer, NULL), "interrupt timer");
  }
  bool complete = true;
  uint64_t begin = nb_now();
  json_object *rows = nb_http_cohort(&options, bodies, &complete, &error);
  double elapsed = (nb_now() - begin) / 1e9;
  if (interrupt) {
    struct itimerval timer = {0};
    require(!setitimer(ITIMER_REAL, &timer, NULL) &&
                !sigaction(SIGALRM, &old, NULL),
            "restore interrupt handler");
  }
  require(rows && json_object_array_length(rows) == count && !complete &&
              error.message[0] && elapsed < (interrupt ? 0.5 : 0.1),
          "deadline or interrupted cohort did not retire promptly");
  for (unsigned i = 0; i < count; ++i)
    require(!strcmp(nb_string(json_object_array_get_idx(rows, i), "event"),
                    "failed-request"),
            "incomplete transport became a successful observation");
  require(!interrupt || cohort_interrupted, "interrupt not observed");
  json_object_put(rows);
  json_object_put(bodies);
  server_done();
}
static void run(char **argv, int expected, const char *log_name) {
  char logfile[2300];
  path(logfile, log_name);
  pid_t pid = fork();
  require(pid >= 0, "client fork");
  if (!pid) {
    int fd = open(logfile, O_WRONLY | O_CREAT | O_TRUNC, 0600);
    if (fd < 0)
      _exit(120);
    dup2(fd, STDOUT_FILENO);
    dup2(fd, STDERR_FILENO);
    close(fd);
    setenv("PATH", "/nonexistent", 1);
    execv(argv[0], argv);
    _exit(121);
  }
  int status;
  while (waitpid(pid, &status, 0) < 0 && errno == EINTR) {
  }
  require(WIFEXITED(status) && WEXITSTATUS(status) == expected,
          "client exit (see log)");
}
static json_object *campaign(const char *binary, const char *corpus,
                             const char *name, bool gufo, int fault) {
  unsigned levels[] = {1, 2, 4, 6, 8}, bad[] = {2};
  char url[128], output[2300], log[100];
  launch_server(url, gufo, fault ? bad : levels, fault ? 1 : 5, fault ? 1 : 3,
                fault);
  path(output, name);
  snprintf(log, sizeof(log), "%s.log", name);
  char *argv[] = {(char *)binary,
                  "--suite",
                  "http-multi",
                  "--url",
                  url,
                  "--model",
                  "fixture",
                  "--requests",
                  (char *)corpus,
                  "--users",
                  fault ? "2" : "1,2,4,6,8",
                  "--tg",
                  "8",
                  "--context-capacity",
                  "4096",
                  "--warmups",
                  fault ? "0" : "1",
                  "--repetitions",
                  fault ? "1" : "2",
                  "--timeout",
                  fault ? "3" : "86400",
                  "--server-label",
                  "NOT-INFERENCE",
                  "--output",
                  output,
                  NULL};
  run(argv, fault ? 1 : 0, log);
  server_done();
  return read_rows(name);
}
static void corruption(json_object *original, unsigned mode) {
  json_object *rows = nb_copy(original),
              *row = json_object_array_get_idx(rows, mode >= 17 ? 4 : 1);
  json_object *p = json_object_array_get_idx(nb_get(row, "preparations"), 0),
              *job = json_object_array_get_idx(nb_get(row, "requests"), 0);
  switch (mode) {
  case 0:
    nb_real(nb_get(job, "server_timings"), "decode_ms", 0);
    break;
  case 1:
    nb_num(job, "started_ns", INT64_MAX);
    break;
  case 2:
    nb_num(p, "finished_ns", nb_number(job, "started_ns") + 1);
    break;
  case 3:
    nb_str(job, "request_sha256", "corrupt");
    break;
  case 4:
    json_object_object_del(job, "server_timings");
    break;
  case 5:
    nb_num(nb_get(job, "usage"), "completion_tokens", 7);
    break;
  case 6:
    nb_num(row, "rep", 99);
    break;
  case 7:
    nb_str(row, "case", "unbound");
    break;
  case 8:
    nb_num(nb_get(job, "server_timings"), "cached_tokens", 2000);
    break;
  case 9:
    nb_str(json_object_array_get_idx(rows, json_object_array_length(rows) - 1),
           "event", "failed");
    break;
  case 10:
    json_object_object_add(job, "stream_complete",
                           json_object_new_boolean(false));
    break;
  case 11:
    nb_real(job, "output_over_wall_tps", 0);
    break;
  case 12:
    nb_num(nb_get(job, "request"), "max_tokens", 1);
    break;
  case 13:
    json_object_object_add(row, "requests", json_object_new_array());
    break;
  case 14:
    nb_str(job, "stream_complete", "true");
    break;
  case 15:
    nb_num(nb_get(nb_get(job, "usage"), "prompt_tokens_details"),
           "cached_tokens", 0);
    break;
  case 16:
    nb_num(json_object_array_get_idx(rows, 0), "max_replayed_prompt_tokens", 8);
    break;
  case 17: {
    json_object *second = json_object_array_get_idx(nb_get(row, "requests"), 1),
                *second_p =
                    json_object_array_get_idx(nb_get(row, "preparations"), 1);
    nb_str(second, "client_id", nb_string(job, "client_id"));
    nb_str(second_p, "client_id", nb_string(job, "client_id"));
    break;
  }
  case 18: {
    json_object *second = json_object_array_get_idx(nb_get(row, "requests"), 1);
    nb_num(second, "started_ns", nb_number(second, "started_ns") + 1);
    nb_num(second, "finished_ns", nb_number(second, "finished_ns") + 1);
    break;
  }
  }
  nb_error error = {0};
  json_object *sum = nb_http_multi_summary(rows, &error);
  require(sum == NULL && error.message[0],
          "corrupted/warmup evidence accepted");
  if (mode == 13) {
    save_rows("corrupt.jsonl", rows);
    char input[2300], output[2300];
    path(input, "corrupt.jsonl");
    path(output, "refused-graphs");
    require(nb_report(input, output, "NOT-INFERENCE", NULL, "", false,
                      &error) != 0 &&
                access(output, F_OK),
            "corrupt report created artifacts");
  }
  json_object_put(sum);
  json_object_put(rows);
}
static void graph_present(const char *name) {
  char p[2300], file[100];
  snprintf(file, sizeof(file), "%s/benchmark.png", name);
  path(p, file);
  FILE *f = fopen(p, "rb");
  unsigned char bytes[8];
  require(f && fread(bytes, 1, 8, f) == 8 &&
              !memcmp(bytes, "\x89PNG\r\n\x1a\n", 8),
          "PNG");
  fclose(f);
  snprintf(file, sizeof(file), "%s/summary.csv", name);
  path(p, file);
  require(!access(p, R_OK), "CSV");
}
static void remove_tree(const char *name) {
  DIR *dir = opendir(name);
  require(dir != NULL, "cleanup");
  struct dirent *entry;
  while ((entry = readdir(dir)))
    if (strcmp(entry->d_name, ".") && strcmp(entry->d_name, "..")) {
      char child[4096];
      require(snprintf(child, sizeof(child), "%s/%s", name, entry->d_name) <
                  4096,
              "cleanup path");
      struct stat st;
      require(!lstat(child, &st), "cleanup stat");
      if (S_ISDIR(st.st_mode))
        remove_tree(child);
      else
        require(!unlink(child), "unlink");
    }
  closedir(dir);
  require(!rmdir(name), "rmdir");
}
int main(int argc, char **argv) {
  require(argc == 2, "binary argument");
  strcpy(root, "/tmp/lie-http-multi-native-XXXXXX");
  require(mkdtemp(root) != NULL, "mkdtemp");
  atexit(own_stop);
  char corpus[2300];
  path(corpus, "corpus.jsonl");
  FILE *f = fopen(corpus, "w");
  require(f != NULL, "corpus");
  fputs("{\"id\":\"wire-fixture-NOT-INFERENCE\",\"expected_prompt_tokens\":"
        "2048,\"body\":{\"messages\":[{\"role\":\"user\",\"content\":"
        "\"Synthetic wire fixture, not a tokenized model prompt.\"}]}}\n",
        f);
  require(!fclose(f), "corpus close");
  json_object *lie = campaign(argv[1], corpus, "lie.jsonl", false, 0),
              *gufo = campaign(argv[1], corpus, "gufo.jsonl", true, 0);
  nb_error error = {0};
  json_object *a = nb_http_multi_summary(lie, &error),
              *b = nb_http_multi_summary(gufo, &error);
  require(a && b, error.message);
  json_object *points = nb_get(a, "configurations");
  require(json_object_array_length(points) == 5, "all concurrency levels");
  for (size_t i = 0; i < 5; ++i) {
    json_object *point = json_object_array_get_idx(points, i);
    double expected = 0;
    for (int64_t slot = 0; slot < nb_number(point, "users"); ++slot)
      expected += 8000.0 / (2 + slot);
    require(fabs(json_object_get_double(nb_get(
                     nb_get(point, "sum_request_decode_tps"), "median")) -
                 expected) < 1e-8,
            "sum individual rates");
    require(json_object_get_double(nb_get(nb_get(point, "aggregate_output_tps"),
                                          "median")) < expected / 2,
            "common wall conflated with server rate sum");
  }
  for (unsigned mode = 0; mode < 19; ++mode)
    corruption(lie, mode);
  char graphs[2300];
  path(graphs, "graphs");
  require(!nb_http_multi_export(a, b, graphs, "NOT-INFERENCE LIE",
                                "NOT-INFERENCE Gufo", &error),
          error.message);
  graph_present("graphs");
  char summary_path[2300];
  path(summary_path, "graphs/summary.json");
  json_object *summary = nb_read(summary_path, false, &error);
  require(summary &&
              json_object_array_length(nb_get(summary, "comparison")) == 5,
          "comparison groups");
  for (size_t i = 0; i < 5; ++i)
    require(json_object_get_boolean(nb_get(
                json_object_array_get_idx(nb_get(summary, "comparison"), i),
                "eligible")),
            "matched output eligibility");
  json_object_put(summary);
  char lie_path[2300], gufo_path[2300], routed[2300];
  path(lie_path, "lie.jsonl");
  path(gufo_path, "gufo.jsonl");
  path(routed, "routed-graphs");
  require(!nb_report(lie_path, routed, "NOT-INFERENCE LIE", gufo_path,
                     "NOT-INFERENCE Gufo", false, &error),
          error.message);
  graph_present("routed-graphs");
  json_object *reordered = nb_copy(gufo);
  size_t length = json_object_array_length(reordered);
  for (size_t i = 1; i < length / 2; ++i) {
    json_object *left =
                    json_object_get(json_object_array_get_idx(reordered, i)),
                *right = json_object_get(
                    json_object_array_get_idx(reordered, length - 1 - i));
    json_object_array_put_idx(reordered, i, right);
    json_object_array_put_idx(reordered, length - 1 - i, left);
  }
  json_object *sorted = nb_http_multi_summary(reordered, &error);
  require(sorted != NULL, error.message);
  json_object_put(sorted);
  json_object_put(reordered);
  /* All-hit preparation must not invent a zero or infinite PP measurement. */
  json_object *cached = nb_copy(lie);
  for (size_t i = 1; i + 1 < json_object_array_length(cached); ++i) {
    json_object *prep =
        nb_get(json_object_array_get_idx(cached, i), "preparations");
    for (size_t j = 0; j < json_object_array_length(prep); ++j) {
      json_object *p = json_object_array_get_idx(prep, j),
                  *timing = nb_get(p, "server_timings");
      nb_num(p, "cached_tokens", 2048);
      nb_num(nb_get(nb_get(p, "usage"), "prompt_tokens_details"),
             "cached_tokens", 2048);
      nb_num(timing, "cached_tokens", 2048);
      nb_num(timing, "prefill_tokens", 0);
      nb_num(timing, "prefill_calls", 0);
      nb_real(timing, "prefill_ms", 0);
      json_object_object_add(timing, "prefill_tokens_per_second", NULL);
    }
  }
  json_object *hits = nb_http_multi_summary(cached, &error);
  require(hits != NULL, error.message);
  for (size_t i = 0; i < 5; ++i)
    require(
        !nb_get(json_object_array_get_idx(nb_get(hits, "configurations"), i),
                "executed_preparation_pp_tps"),
        "cache hits invented executed PP throughput");
  path(graphs, "all-hit-graphs");
  require(!nb_http_multi_export(hits, NULL, graphs, "NOT-INFERENCE cache hits",
                                "", &error),
          error.message);
  graph_present("all-hit-graphs");
  json_object_put(hits);
  json_object_put(cached);
  bounded_transport(false);
  bounded_transport(true);
  for (unsigned fault = 1; fault <= 2; ++fault) {
    json_object *failed =
        campaign(argv[1], corpus, fault == 1 ? "miss.jsonl" : "partial.jsonl",
                 false, (int)fault);
    require(!strcmp(nb_string(json_object_array_get_idx(
                                  failed, json_object_array_length(failed) - 1),
                              "event"),
                    "failed"),
            "failed cohort terminal");
    json_object *refused = nb_http_multi_summary(failed, &error);
    require(!refused, "failed cohort averaged");
    json_object_put(refused);
    json_object_put(failed);
  }
  json_object_put(a);
  json_object_put(b);
  json_object_put(lie);
  json_object_put(gufo);
  remove_tree(root);
  puts("Prepared C1/2/4/6/8 LIE/Gufo wire, barrier, sum/common-wall math, "
       "corruption and partial-failure fixtures: PASS (NOT-INFERENCE; no "
       "Python)");
  return 0;
}
