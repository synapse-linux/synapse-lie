/* SPDX-License-Identifier: MIT */
#include "bench_native.h"
#include <curl/curl.h>
#include <errno.h>
#include <math.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>

typedef struct {
  const char *url, *management, *model, *provider, *cases_path, *output, *phase,
      *reference_path, *graphs;
  unsigned chunk, reps;
  double timeout;
  bool overlap, slow, inconclusive, full_prompt;
  FILE *file;
  void (*read_gate)(void *, bool);
  void *gate_context;
  pthread_mutex_t lock;
  nb_error error;
} client;
static bool truth(json_object *o, const char *k) {
  return json_object_get_boolean(nb_get(o, k));
}
static void delay(unsigned ms) {
  struct timespec t = {ms / 1000, (long)(ms % 1000) * 1000000};
  while (nanosleep(&t, &t) && errno == EINTR) {
  }
}
static bool inconclusive(client *c, const char *why) {
  c->inconclusive = true;
  return nb_fail(&c->error, why);
}
static bool event(client *c, const char *kind, json_object *row) {
  nb_str(row, "event", kind);
  nb_num(row, "monotonic_ns", (int64_t)nb_now());
  pthread_mutex_lock(&c->lock);
  bool ok = nb_emit(c->file, row);
  pthread_mutex_unlock(&c->lock);
  return ok;
}
static json_object *state(client *c) {
  char url[8400];
  size_t len = strlen(c->management);
  while (len && c->management[len - 1] == '/')
    len--;
  if (snprintf(url, sizeof(url), "%.*s/actuator/llm", (int)len,
               c->management) >= (int)sizeof(url)) {
    nb_fail(&c->error, "Management URL too long");
    return NULL;
  }
  json_object *o = nb_http_get(url, c->timeout, &c->error);
  if (!o)
    return NULL;
  json_object *backend = nb_get(o, "backend"), *cache = nb_get(o, "cache"),
              *disk = nb_get(cache, "ssd"), *scheduler = nb_get(o, "scheduler");
  bool ok = json_object_is_type(nb_get(o, "ready"), json_type_boolean) &&
            truth(o, "ready") &&
            !strcmp(nb_string(backend, "engine"), c->provider) &&
            !strcmp(nb_string(backend, "model"), c->model) &&
            !truth(cache, "enabled") && truth(cache, "ssd_enabled") &&
            truth(disk, "enabled");
  const char *counts[] = {"active",    "queued", "output_blocked",  "completed",
                          "cancelled", "failed", "generated_tokens"};
  for (unsigned i = 0; i < 7; i++)
    ok = ok && nb_count(scheduler, counts[i], 0, INT64_MAX, NULL);
  ok = ok &&
       !strcmp(nb_string(scheduler, "mode"),
               "single-owner-reactive-ready-batch") &&
       nb_count(scheduler, "max_active", 2, 8, NULL) &&
       nb_number(scheduler, "output_blocked") <=
           nb_number(scheduler, "active") &&
       nb_number(scheduler, "active") <= nb_number(scheduler, "max_active") &&
       nb_number(scheduler, "active") + nb_number(scheduler, "queued") <= 8;
  const char *dc[] = {"pending", "staging_bytes", "staging_budget_bytes",
                      "writes",  "hits",          "errors",
                      "entries"};
  for (unsigned i = 0; i < 7; i++)
    ok = ok && nb_count(disk, dc[i], 0, INT64_MAX, NULL);
  ok = ok && nb_number(disk, "pending") <= 1 &&
       nb_number(disk, "staging_bytes") <=
           nb_number(disk, "staging_budget_bytes") &&
       !nb_number(disk, "errors");
  if (!ok) {
    json_object_put(o);
    nb_fail(&c->error,
            "KV disk experiment requires ready matching backend, RAM retention "
            "off, disk on and bounded error-free scheduler");
    return NULL;
  }
  return o;
}
typedef enum {
  IDLE,
  PENDING,
  PROGRESS,
  CANCELLED,
  BLOCKED,
  PEER_COMPLETED
} condition;
static json_object *poll_state(client *c, condition what, json_object *before) {
  uint64_t deadline = nb_now() + (uint64_t)(c->timeout * 1e9);
  for (;;) {
    json_object *o = state(c);
    if (!o)
      return NULL;
    json_object *s = nb_get(o, "scheduler"),
                *disk = nb_get(nb_get(o, "cache"), "ssd"),
                *base = nb_get(before, "scheduler");
    bool match = false;
    switch (what) {
    case IDLE:
      match = !nb_number(s, "active") && !nb_number(s, "queued") &&
              !nb_number(s, "output_blocked") && !nb_number(disk, "pending");
      break;
    case PENDING:
      match = nb_number(disk, "pending") == 1 && nb_number(s, "active") == 2;
      break;
    case PROGRESS:
      if (!nb_number(disk, "pending")) {
        json_object_put(o);
        inconclusive(c, "KV disk read completed before peer progress witness");
        return NULL;
      }
      match = nb_number(s, "generated_tokens") >
              nb_number(base, "generated_tokens");
      break;
    case CANCELLED:
      match = nb_number(s, "cancelled") == nb_number(base, "cancelled") + 1;
      break;
    case BLOCKED:
      match = nb_number(s, "output_blocked") == 1 &&
              !strcmp(nb_string(nb_get(s, "executor"), "phase"), "none");
      break;
    case PEER_COMPLETED:
      match = nb_number(s, "completed") == nb_number(base, "completed") + 1 &&
              nb_number(s, "output_blocked") == 1;
      break;
    }
    if (match)
      return o;
    json_object_put(o);
    if (nb_now() >= deadline) {
      inconclusive(c,
                   "Required scheduler state was not observed before deadline");
      return NULL;
    }
    delay(10);
  }
}
static json_object *payload(client *c, json_object *item, bool responses,
                            bool stream) {
  json_object *o = json_object_new_object();
  nb_str(o, "model", c->model);
  nb_num(o, "temperature", 0);
  json_object_object_add(o, "stream", json_object_new_boolean(stream));
  if (responses) {
    nb_add(o, "input", nb_get(item, "prompt"));
    nb_num(o, "max_output_tokens", nb_number(item, "max_tokens"));
    json_object_object_add(o, "store", json_object_new_boolean(false));
  } else {
    json_object *messages = json_object_new_array(),
                *m = json_object_new_object(), *kw = json_object_new_object();
    nb_str(m, "role", "user");
    nb_add(m, "content", nb_get(item, "prompt"));
    json_object_array_add(messages, m);
    json_object_object_add(o, "messages", messages);
    nb_num(o, "max_tokens", nb_number(item, "max_tokens"));
    json_object_object_add(kw, "enable_thinking",
                           json_object_new_boolean(false));
    json_object_object_add(o, "chat_template_kwargs", kw);
    if (stream) {
      json_object *opts = json_object_new_object();
      json_object_object_add(opts, "include_usage",
                             json_object_new_boolean(true));
      json_object_object_add(o, "stream_options", opts);
    }
  }
  return o;
}
static json_object *send_request(client *c, json_object *item, bool responses,
                                 bool stream, const char *label, unsigned rep,
                                 void (*output)(void *), void *userdata,
                                 atomic_bool *cancel, nb_error *e) {
  json_object *body = payload(c, item, responses, stream);
  nb_http_options options = {.url = c->url,
                             .model = c->model,
                             .provider = c->provider,
                             .timeout = c->timeout,
                             .responses = responses,
                             .stream = stream,
                             .strict = true,
                             .on_output = output,
                             .userdata = userdata,
                             .cancel = cancel};
  json_object *row = nb_http_request(&options, body, e);
  if (row) {
    nb_str(row, "label", label);
    nb_num(row, "rep", rep);
    nb_str(row, "case", nb_string(item, "id"));
    nb_str(row, "api", responses ? "responses" : "chat");
    json_object_object_add(row, "stream", json_object_new_boolean(stream));
    if (!event(c, "sample", row)) {
      json_object_put(row);
      row = NULL;
      nb_fail(e, "KV disk evidence write failed");
    }
  } else {
    json_object *failure = json_object_new_object();
    nb_str(failure, "case", nb_string(item, "id"));
    nb_str(failure, "api", responses ? "responses" : "chat");
    nb_str(failure, "label", label);
    nb_str(failure, "error", e->message);
    char hash[65];
    if (nb_json_hash(body, hash))
      nb_str(failure, "request_sha256", hash);
    event(c, "request_failed", failure);
    json_object_put(failure);
  }
  json_object_put(body);
  return row;
}
static bool same(client *c, json_object *row, json_object *reference) {
  const char *keys[] = {"prompt_tokens", "output_tokens", "finish", "content"};
  if (!row || !reference)
    return nb_fail(&c->error, "Missing fresh/restored sample");
  for (unsigned i = 0; i < 4; i++)
    if (!nb_same(row, reference, keys[i]))
      return nb_fail(&c->error, "Fresh/restored output mismatch");
  int64_t pp = nb_number(row, "prompt_tokens"),
          expected = c->full_prompt            ? pp
                     : pp >= (int64_t)c->chunk ? pp / c->chunk * c->chunk
                                               : pp;
  if (nb_number(row, "cached_tokens") != expected ||
      (!strcmp(nb_string(row, "api"), "chat") &&
       nb_number(nb_get(row, "timings"), "ssd_cached_tokens") != expected))
    return nb_fail(&c->error, "Required KV disk prefix was not reused");
  return true;
}
static json_object *reference_case(json_object *reference, const char *id) {
  json_object *a = nb_get(reference, "samples"), *found = NULL;
  if (!json_object_is_type(a, json_type_array))
    return NULL;
  for (size_t i = 0; i < json_object_array_length(a); i++) {
    json_object *r = json_object_array_get_idx(a, i);
    if (!strcmp(nb_string(r, "case"), id)) {
      if (found)
        return NULL;
      found = r;
    }
  }
  return found;
}
typedef struct {
  client *c;
  json_object *item, *row;
  const char *label;
  unsigned rep;
  pthread_mutex_t *start_lock;
  pthread_cond_t *start_cond;
  bool *start;
  atomic_bool first, done, cancel;
  nb_error error;
} request_task;
static void first_output(void *ptr) {
  request_task *t = ptr;
  atomic_store(&t->first, true);
}
static void *request_thread(void *ptr) {
  request_task *t = ptr;
  if (t->start_lock) {
    pthread_mutex_lock(t->start_lock);
    while (!*t->start)
      pthread_cond_wait(t->start_cond, t->start_lock);
    pthread_mutex_unlock(t->start_lock);
  }
  t->row = send_request(t->c, t->item, false, true, t->label, t->rep,
                        first_output, t, &t->cancel, &t->error);
  atomic_store(&t->done, true);
  return NULL;
}
static json_object *run_phase(client *c, json_object *cases,
                              json_object *reference) {
  json_object *initial = poll_state(c, IDLE, NULL), *final = NULL,
              *out = json_object_new_object(),
              *samples = json_object_new_array(),
              *cohorts = json_object_new_array();
  json_object_object_add(out, "samples", samples);
  json_object_object_add(out, "cohorts", cohorts);
  if (!initial)
    goto bad;
  nb_add(out, "initial", initial);
  c->full_prompt = !strcmp(
      nb_string(nb_get(nb_get(initial, "cache"), "checkpoint_policy"), "kind"),
      "ds4");
  bool read = !strcmp(c->phase, "read");
  char hash[65];
  if (!nb_json_hash(cases, hash))
    goto bad;
  if (!read && nb_number(nb_get(nb_get(initial, "cache"), "ssd"), "entries")) {
    nb_fail(&c->error, "Writer requires an empty KV store");
    goto bad;
  }
  if (read) {
    if (!reference || strcmp(nb_string(reference, "state"), "PASS") ||
        strcmp(nb_string(reference, "phase"), "write") ||
        strcmp(nb_string(reference, "cases_sha256"), hash) ||
        strcmp(nb_string(reference, "provider"), c->provider) ||
        nb_number(reference, "chunk") != c->chunk ||
        !json_object_equal(nb_get(reference, "backend"),
                           nb_get(initial, "backend")) ||
        !nb_same(nb_get(nb_get(reference, "initial"), "cache"),
                 nb_get(initial, "cache"), "checkpoint_policy")) {
      nb_fail(&c->error, "Incompatible or incomplete producer reference");
      goto bad;
    }
    for (size_t i = 0; i < json_object_array_length(cases); i++)
      if (!reference_case(
              reference,
              nb_string(json_object_array_get_idx(cases, i), "id"))) {
        nb_fail(&c->error, "Missing or duplicate producer cases");
        goto bad;
      }
  }
  for (size_t i = 0; i < json_object_array_length(cases); i++) {
    json_object *item = json_object_array_get_idx(cases, i);
    for (unsigned rep = 0; rep < (read ? c->reps : 1); rep++)
      for (unsigned v = 0; v < (read ? 4u : 1u); v++) {
        json_object *r = send_request(c, item, v >= 2, v % 2,
                                      read ? "restart-read" : "restart-write",
                                      rep, NULL, NULL, NULL, &c->error);
        if (!r)
          goto bad;
        json_object_array_add(samples, r);
        if (read) {
          if (!same(c, r, reference_case(reference, nb_string(item, "id"))))
            goto bad;
        } else if (nb_number(r, "cached_tokens")) {
          nb_fail(&c->error, "Producer unexpectedly reused a prefix");
          goto bad;
        }
        json_object *idle = poll_state(c, IDLE, NULL);
        if (!idle)
          goto bad;
        json_object_put(idle);
      }
  }
  if (read)
    for (unsigned rep = 0; rep < c->reps; rep++) {
      pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
      pthread_cond_t cond = PTHREAD_COND_INITIALIZER;
      bool start = false;
      char label[64];
      snprintf(label, sizeof(label), "concurrent-%u", rep);
      request_task tasks[2] = {0};
      pthread_t threads[2];
      unsigned launched = 0;
      uint64_t begun = nb_now();
      for (unsigned i = 0; i < 2; i++) {
        tasks[i] = (request_task){.c = c,
                                  .item = json_object_array_get_idx(cases, i),
                                  .label = label,
                                  .rep = rep,
                                  .start_lock = &lock,
                                  .start_cond = &cond,
                                  .start = &start};
        if (pthread_create(&threads[i], NULL, request_thread, &tasks[i]))
          break;
        launched++;
      }
      pthread_mutex_lock(&lock);
      start = true;
      pthread_cond_broadcast(&cond);
      pthread_mutex_unlock(&lock);
      for (unsigned i = 0; i < launched; i++)
        pthread_join(threads[i], NULL);
      uint64_t elapsed = nb_now() - begun;
      pthread_cond_destroy(&cond);
      pthread_mutex_destroy(&lock);
      bool ok = launched == 2;
      int64_t tokens = 0;
      for (unsigned i = 0; i < launched; i++) {
        if (!tasks[i].row) {
          ok = false;
          c->error = tasks[i].error;
        } else {
          json_object_array_add(samples, tasks[i].row);
          if (!same(c, tasks[i].row,
                    reference_case(reference, nb_string(tasks[i].item, "id"))))
            ok = false;
          tokens += nb_number(tasks[i].row, "output_tokens");
        }
      }
      if (!ok || !elapsed)
        goto bad;
      json_object *idle = poll_state(c, IDLE, NULL);
      if (!idle)
        goto bad;
      json_object_put(idle);
      json_object *cohort = json_object_new_object();
      nb_num(cohort, "rep", rep);
      nb_num(cohort, "users", 2);
      nb_real(cohort, "wall_ms", elapsed / 1e6);
      nb_real(cohort, "output_over_wall_tps", tokens * 1e9 / elapsed);
      json_object_array_add(cohorts, cohort);
      if (!event(c, "cohort", cohort))
        goto bad;
    }
  final = poll_state(c, IDLE, NULL);
  if (!final)
    goto bad;
  json_object *before = nb_get(initial, "scheduler"),
              *after = nb_get(final, "scheduler"),
              *disk = nb_get(nb_get(final, "cache"), "ssd");
  if (!nb_same(before, after, "failed") ||
      !nb_same(before, after, "cancelled") ||
      nb_number(after, "completed") !=
          nb_number(before, "completed") +
              (int64_t)json_object_array_length(samples)) {
    nb_fail(&c->error, "Unexpected server activity or request accounting");
    goto bad;
  }
  if (read ? nb_number(disk, "writes") !=
                 nb_number(nb_get(nb_get(initial, "cache"), "ssd"), "writes")
           : nb_number(disk, "writes") !=
                 (int64_t)json_object_array_length(cases)) {
    nb_fail(&c->error, "Unexpected or missing durable KV writes");
    goto bad;
  }
  nb_add(out, "final", final);
  nb_str(out, "schema", "synapse-lie.http-ssd-bench.v1");
  nb_str(out, "state", "PASS");
  nb_str(out, "phase", c->phase);
  nb_str(out, "provider", c->provider);
  nb_add(out, "synthetic", nb_get(nb_get(initial, "backend"), "synthetic"));
  nb_add(out, "backend", nb_get(initial, "backend"));
  nb_num(out, "chunk", c->chunk);
  nb_str(out, "cases_sha256", hash);
  nb_str(out, "quantile_method",
         "nearest rank; small n is not a tail-latency confidence estimate");
  nb_str(out, "inter_output_scope",
         "nonempty SSE text events, not one measurement per model token");
  json_object *ev = json_object_new_object();
  nb_add(ev, "result", out);
  bool written = event(c, "phase_complete", ev);
  json_object_put(ev);
  if (!written)
    goto bad;
  json_object_put(initial);
  json_object_put(final);
  return out;
bad:
  json_object_put(initial);
  json_object_put(final);
  json_object_put(out);
  if (!c->error.message[0])
    nb_fail(&c->error, "KV disk phase failed");
  return NULL;
}
static int small_window(void *unused, curl_socket_t fd, curlsocktype purpose) {
  (void)unused;
  (void)purpose;
  int bytes = 1024;
  return setsockopt(fd, SOL_SOCKET, SO_RCVBUF, &bytes, sizeof(bytes))
             ? CURL_SOCKOPT_ERROR
             : CURL_SOCKOPT_OK;
}
/* An unread client-owned connection produces actual TCP pressure. libcurl owns
 * connection setup/TLS; this is solely a benchmark probe, not a server path. */
static CURL *held_request(client *c, json_object *item, bool pressure) {
  CURLU *u = curl_url();
  CURL *h = NULL;
  char *host = NULL, *port = NULL, *path = NULL, *scheme = NULL, *wire = NULL;
  json_object *body = NULL;
  if (!u || curl_url_set(u, CURLUPART_URL, c->url, 0) ||
      curl_url_get(u, CURLUPART_HOST, &host, 0) ||
      curl_url_get(u, CURLUPART_PATH, &path, 0) ||
      curl_url_get(u, CURLUPART_SCHEME, &scheme, 0))
    goto bad;
  (void)curl_url_get(u, CURLUPART_PORT, &port, 0);
  if (pressure && strcmp(scheme, "http")) {
    nb_fail(&c->error, "TCP pressure probe requires plain HTTP");
    goto bad;
  }
  if (strpbrk(host, "\r\n") || strpbrk(path, "\r\n"))
    goto bad;
  body = payload(c, item, false, true);
  const char *data = nb_encoded(body);
  size_t n = strlen(data), pathlen = strlen(path);
  if (n > 8 * 1024 * 1024)
    goto bad;
  while (pathlen && path[pathlen - 1] == '/')
    path[--pathlen] = 0;
  size_t bytes = n + strlen(host) + pathlen + 1024;
  wire = malloc(bytes);
  if (!wire)
    goto bad;
  int size = snprintf(
      wire, bytes,
      "POST %s/chat/completions HTTP/1.1\r\nHost: %s%s%s\r\nContent-Type: "
      "application/json\r\nContent-Length: %zu\r\nConnection: close\r\n\r\n%s",
      path, host, port ? ":" : "", port ? port : "", n, data);
  if (size < 0 || (size_t)size >= bytes)
    goto bad;
  h = curl_easy_init();
  if (!h)
    goto bad;
  curl_easy_setopt(h, CURLOPT_URL, c->url);
  curl_easy_setopt(h, CURLOPT_CONNECT_ONLY, 1L);
  curl_easy_setopt(h, CURLOPT_NOSIGNAL, 1L);
  curl_easy_setopt(h, CURLOPT_TIMEOUT_MS, (long)(c->timeout * 1000));
  curl_easy_setopt(h, CURLOPT_PROTOCOLS_STR, "http,https");
  if (pressure)
    curl_easy_setopt(h, CURLOPT_SOCKOPTFUNCTION, small_window);
  if (curl_easy_perform(h) != CURLE_OK)
    goto bad;
  uint64_t deadline = nb_now() + (uint64_t)(c->timeout * 1e9);
  size_t sent = 0;
  while (sent < (size_t)size) {
    size_t wrote = 0;
    CURLcode rc = curl_easy_send(h, wire + sent, (size_t)size - sent, &wrote);
    if (rc == CURLE_AGAIN) {
      if (nb_now() >= deadline)
        goto bad;
      delay(1);
      continue;
    }
    if (rc != CURLE_OK)
      goto bad;
    sent += wrote;
  }
  goto end;
bad:
  if (h)
    curl_easy_cleanup(h);
  h = NULL;
  if (!c->error.message[0])
    nb_fail(&c->error, "Unread HTTP probe connection failed");
end:
  free(wire);
  json_object_put(body);
  curl_free(host);
  curl_free(port);
  curl_free(path);
  curl_free(scheme);
  curl_url_cleanup(u);
  return h;
}
static json_object *overlap(client *c, json_object *disk_case,
                            json_object *peer_case, json_object *reference) {
  json_object *before = poll_state(c, IDLE, NULL), *pending = NULL,
              *progressed = NULL, *cancelled = NULL, *result = NULL;
  CURL *held = NULL;
  pthread_t thread;
  bool launched = false;
  request_task task = {.c = c, .item = peer_case, .label = "overlap-peer"};
  if (!before)
    goto end;
  if (pthread_create(&thread, NULL, request_thread, &task)) {
    nb_fail(&c->error, "Peer thread creation failed");
    goto end;
  }
  launched = true;
  uint64_t deadline = nb_now() + (uint64_t)(c->timeout * 1e9);
  while (!atomic_load(&task.first)) {
    if (atomic_load(&task.done) || nb_now() >= deadline) {
      inconclusive(c, "Peer produced no output before overlap deadline");
      goto end;
    }
    delay(1);
  }
  if (c->read_gate)
    c->read_gate(c->gate_context, true);
  held = held_request(c, disk_case, false);
  if (!held)
    goto end;
  pending = poll_state(c, PENDING, NULL);
  if (!pending)
    goto end;
  progressed = poll_state(c, PROGRESS, pending);
  if (!progressed)
    goto end;
  json_object *witness = json_object_new_object();
  nb_add(witness, "pending", pending);
  nb_add(witness, "progress", progressed);
  bool written = event(c, "ssd_overlap_witness", witness);
  json_object_put(witness);
  if (!written)
    goto end;
  curl_easy_cleanup(held);
  held = NULL;
  cancelled = poll_state(c, CANCELLED, before);
  if (!cancelled)
    goto end;
  bool while_pending =
      nb_number(nb_get(nb_get(cancelled, "cache"), "ssd"), "pending") != 0;
  witness = json_object_new_object();
  nb_add(witness, "state", cancelled);
  json_object_object_add(witness, "cancelled_while_io_pending",
                         json_object_new_boolean(while_pending));
  written = event(c, "ssd_cancel_witness", witness);
  json_object_put(witness);
  if (!written)
    goto end;
  if (!while_pending) {
    inconclusive(c, "KV disk I/O retired before cancellation witness");
    goto end;
  }
  if (!nb_same(nb_get(before, "scheduler"), nb_get(cancelled, "scheduler"),
               "failed")) {
    nb_fail(&c->error, "Overlap request failure");
    goto end;
  }
  pthread_join(thread, NULL);
  launched = false;
  if (!task.row) {
    c->error = task.error;
    goto end;
  }
  if (!same(c, task.row, reference_case(reference, nb_string(peer_case, "id"))))
    goto end;
  result = json_object_new_object();
  nb_str(result, "state", "PASS");
  json_object_object_add(result, "peer_progress_while_ssd_pending",
                         json_object_new_boolean(true));
  json_object_object_add(result, "cancelled_while_io_pending",
                         json_object_new_boolean(true));
  nb_add(result, "peer", task.row);
end:
  if (c->read_gate)
    c->read_gate(c->gate_context, false);
  if (held)
    curl_easy_cleanup(held);
  if (launched) {
    atomic_store(&task.cancel, true);
    pthread_join(thread, NULL);
  }
  json_object_put(task.row);
  json_object_put(before);
  json_object_put(pending);
  json_object_put(progressed);
  json_object_put(cancelled);
  return result;
}
static json_object *slow_client(client *c, json_object *blocked_case,
                                json_object *peer_case,
                                json_object *reference) {
  json_object *before = poll_state(c, IDLE, NULL), *stalled = NULL,
              *progressed = NULL, *final = NULL, *row = NULL, *result = NULL;
  CURL *held = NULL;
  if (!before)
    goto end;
  held = held_request(c, blocked_case, true);
  if (!held)
    goto end;
  stalled = poll_state(c, BLOCKED, NULL);
  if (!stalled)
    goto end;
  json_object *ss = nb_get(stalled, "scheduler");
  int64_t produced = nb_number(ss, "generated_tokens") -
                     nb_number(nb_get(before, "scheduler"), "generated_tokens");
  if (produced <= 0 || produced >= nb_number(blocked_case, "max_tokens")) {
    inconclusive(c, "Unread client did not stall before its output budget");
    goto end;
  }
  for (unsigned i = 0; i < 5; i++) {
    delay(50);
    json_object *o = state(c);
    if (!o)
      goto end;
    json_object *s = nb_get(o, "scheduler");
    bool stable = nb_number(s, "output_blocked") == 1 &&
                  nb_same(s, ss, "generated_tokens") &&
                  nb_same(nb_get(s, "executor"), nb_get(ss, "executor"),
                          "decode_started");
    json_object_put(o);
    if (!stable) {
      inconclusive(c, "Decode did not remain credit-stalled");
      goto end;
    }
  }
  row = send_request(c, peer_case, false, true, "slow-client-peer", 0, NULL,
                     NULL, NULL, &c->error);
  if (!same(c, row, reference_case(reference, nb_string(peer_case, "id"))))
    goto end;
  progressed = poll_state(c, PEER_COMPLETED, before);
  if (!progressed)
    goto end;
  curl_easy_cleanup(held);
  held = NULL;
  json_object *cancelled = poll_state(c, CANCELLED, before);
  if (!cancelled)
    goto end;
  json_object_put(cancelled);
  final = poll_state(c, IDLE, NULL);
  if (!final)
    goto end;
  if (!nb_same(nb_get(before, "scheduler"), nb_get(final, "scheduler"),
               "failed")) {
    nb_fail(&c->error, "Slow-client peer isolation failed");
    goto end;
  }
  result = json_object_new_object();
  nb_str(result, "state", "PASS");
  nb_add(result, "before", before);
  nb_add(result, "stalled", stalled);
  nb_add(result, "progressed", progressed);
  nb_add(result, "final", final);
  json_object *witness = json_object_new_object();
  nb_add(witness, "result", result);
  bool written = event(c, "slow_client_witness", witness);
  json_object_put(witness);
  if (!written) {
    json_object_put(result);
    result = NULL;
  }
end:
  if (held)
    curl_easy_cleanup(held);
  json_object_put(before);
  json_object_put(stalled);
  json_object_put(progressed);
  json_object_put(final);
  json_object_put(row);
  return result;
}
static bool validate_cases(json_object *a, nb_error *e) {
  if (!json_object_is_type(a, json_type_array) ||
      json_object_array_length(a) < 2 || json_object_array_length(a) > 8)
    return nb_fail(e, "Two to eight distinct prompt cases required");
  for (size_t i = 0; i < json_object_array_length(a); i++) {
    json_object *r = json_object_array_get_idx(a, i);
    if (!json_object_is_type(r, json_type_object) ||
        json_object_object_length(r) != 3 || !*nb_string(r, "id") ||
        strlen(nb_string(r, "id")) > 80 || !*nb_string(r, "prompt") ||
        strlen(nb_string(r, "prompt")) > 7 * 1024 * 1024 ||
        !nb_count(r, "max_tokens", 1, 4096, NULL))
      return nb_fail(e, "Invalid KV disk prompt case");
    for (size_t j = 0; j < i; j++)
      if (nb_same(r, json_object_array_get_idx(a, j), "id"))
        return nb_fail(e, "Duplicate prompt case ID");
  }
  return true;
}
int nb_ssd_main_with_gate(int argc, char **argv, void (*gate)(void *, bool),
                          void *context) {
  client c = {.reps = 3,
              .timeout = 180,
              .read_gate = gate,
              .gate_context = context,
              .lock = PTHREAD_MUTEX_INITIALIZER};
  json_object *cases = NULL, *reference = NULL, *result = NULL;
  int rc = 2;
  for (int i = 1; i < argc; i++) {
    const char *k = argv[i];
    if (!strcmp(k, "--help")) {
      puts("Usage: synapse-lie-bench --suite http-kv-disk --url HTTP-BASE/v1 "
           "--management-url HTTP-ORIGIN\n  --model ID --provider ID --cases "
           "JSON --output NEW-JSONL --phase write|read --chunk N\n  "
           "[--reference WRITE-SUMMARY.json] [--repetitions 3] [--timeout "
           "180]\n  [--overlap] [--slow-client] [--graphs DIRECTORY]\nNative C "
           "KV disk benchmark. Requires a ready server with RAM retention off, "
           "KV disk on, and max-active 2..8.\nRead requires a matching "
           "successful producer reference and a server restart controlled by "
           "the operator.\nChecks actual restored output, JSON/SSE APIs, C2 "
           "cohorts and optional real scheduling witnesses.\nA missed "
           "overlap/backpressure window is INCONCLUSIVE, never a passing "
           "witness. No model or server control.\nThe http-ssd suite name "
           "remains an alias.");
      rc = 0;
      goto end;
    }
    if (!strcmp(k, "--overlap")) {
      c.overlap = true;
      continue;
    }
    if (!strcmp(k, "--slow-client")) {
      c.slow = true;
      continue;
    }
    if (i + 1 == argc)
      goto usage;
    const char *v = argv[++i];
    if (!strcmp(k, "--suite")) {
      if (strcmp(v, "http-ssd") && strcmp(v, "http-kv-disk"))
        goto usage;
    }
#define OPTION(name, member) else if (!strcmp(k, name)) c.member = v
    OPTION("--url", url);
    OPTION("--management-url", management);
    OPTION("--model", model);
    OPTION("--provider", provider);
    OPTION("--cases", cases_path);
    OPTION("--output", output);
    OPTION("--phase", phase);
    OPTION("--reference", reference_path);
    OPTION("--graphs", graphs);
#undef OPTION
    else if (!strcmp(k, "--timeout")) {
      char *tail = NULL;
      errno = 0;
      c.timeout = strtod(v, &tail);
      if (errno || tail == v || *tail || !isfinite(c.timeout) ||
          c.timeout <= 0 || c.timeout > 7200)
        goto usage;
    }
    else {
      if (!*v || strspn(v, "0123456789") != strlen(v))
        goto usage;
      char *tail = NULL;
      errno = 0;
      unsigned long n = strtoul(v, &tail, 10);
      if (errno || *tail || !n)
        goto usage;
      if (!strcmp(k, "--chunk")) {
        if (n > 262144)
          goto usage;
        c.chunk = (unsigned)n;
      } else if (!strcmp(k, "--repetitions")) {
        if (n > 100)
          goto usage;
        c.reps = (unsigned)n;
      } else
        goto usage;
    }
  }
  if (!c.url || !c.management || !c.model || !*c.model || !c.provider ||
      !*c.provider || !c.cases_path || !c.output || !c.phase || !c.chunk ||
      (strcmp(c.phase, "write") && strcmp(c.phase, "read")) ||
      ((!strcmp(c.phase, "read")) != (c.reference_path != NULL)) ||
      ((c.overlap || c.slow) && strcmp(c.phase, "read")))
    goto usage;
  if (strlen(c.management) > 8192 || !nb_http_url(c.url, &c.error) ||
      !nb_http_url(c.management, &c.error))
    goto end;
  cases = nb_read(c.cases_path, false, &c.error);
  if (!validate_cases(cases, &c.error))
    goto end;
  if (c.reference_path) {
    reference = nb_read(c.reference_path, false, &c.error);
    if (!reference)
      goto end;
  }
  c.file = nb_exclusive(c.output, &c.error);
  if (!c.file) {
    rc = 1;
    goto end;
  }
  char hash[65];
  json_object *id = json_object_new_object();
  nb_str(id, "schema", "synapse-lie.http-ssd-bench.v1");
  nb_str(id, "phase", c.phase);
  if (nb_json_hash(cases, hash))
    nb_str(id, "cases_sha256", hash);
  if (c.reference_path && nb_file_hash(c.reference_path, hash))
    nb_str(id, "reference_sha256", hash);
  else
    nb_add(id, "reference_sha256", NULL);
  bool ok = event(&c, "identity", id);
  json_object_put(id);
  if (ok)
    result = run_phase(&c, cases, reference);
  ok = ok && result;
  if (ok && c.overlap) {
    json_object *witness =
        overlap(&c, json_object_array_get_idx(cases, 0),
                json_object_array_get_idx(cases, 1), reference);
    ok = witness != NULL;
    if (ok) {
      json_object_object_add(result, "overlap", witness);
      json_object *idle = poll_state(&c, IDLE, NULL);
      ok = idle != NULL;
      json_object_put(idle);
      if (ok) {
        json_object *r =
            send_request(&c, json_object_array_get_idx(cases, 0), false, true,
                         "post-cancel-recovery", 0, NULL, NULL, NULL, &c.error);
        ok = same(&c, r,
                  reference_case(
                      reference,
                      nb_string(json_object_array_get_idx(cases, 0), "id")));
        json_object_put(r);
      }
    }
  }
  if (ok && c.slow) {
    json_object *witness =
        slow_client(&c, json_object_array_get_idx(cases, 1),
                    json_object_array_get_idx(cases, 0), reference);
    ok = witness != NULL;
    if (ok)
      json_object_object_add(result, "slow_client", witness);
  }
  if (ok && (c.overlap || c.slow)) {
    json_object *final = poll_state(&c, IDLE, NULL);
    ok = final != NULL;
    if (ok)
      json_object_object_add(result, "final", final);
  }
  if (ok) {
    extern json_object *nb_ssd_summary(json_object *, nb_error *);
    json_object *stats = nb_ssd_summary(result, &c.error);
    ok = stats != NULL;
    if (ok)
      json_object_object_add(result, "distributions", stats);
  }
  char summary[4096];
  if (snprintf(summary, sizeof(summary), "%s.summary.json", c.output) >=
      (int)sizeof(summary))
    ok = nb_fail(&c.error, "Summary path too long");
  if (ok)
    ok = nb_write_json(summary, result, &c.error);
  json_object *terminal = json_object_new_object();
  if (ok) {
    nb_str(terminal, "state", "PASS");
    nb_str(terminal, "summary", summary);
  } else {
    nb_str(terminal, "outcome", c.inconclusive ? "INCONCLUSIVE" : "FAILED");
    nb_str(terminal, "error", c.error.message);
  }
  bool written = event(&c, ok ? "complete" : "failed", terminal);
  json_object_put(terminal);
  if (fclose(c.file))
    written = false;
  c.file = NULL;
  rc = ok && written ? 0 : c.inconclusive ? 3 : 1;
  if (!rc && c.graphs)
    rc = nb_report(c.output, c.graphs, "LIE", NULL, "Reference", false,
                   &c.error);
  goto end;
usage:
  nb_fail(&c.error,
          "Invalid KV disk HTTP options; use --suite http-kv-disk --help");
end:
  if (c.file)
    fclose(c.file);
  json_object_put(cases);
  json_object_put(reference);
  json_object_put(result);
  pthread_mutex_destroy(&c.lock);
  if (rc && c.error.message[0])
    fprintf(stderr, "%s%s\n", c.inconclusive ? "INCONCLUSIVE: " : "",
            c.error.message);
  return rc;
}

int nb_ssd_main(int argc, char **argv) {
  return nb_ssd_main_with_gate(argc, argv, NULL, NULL);
}
