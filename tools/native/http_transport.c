/* SPDX-License-Identifier: MIT */
#include "bench_native.h"
#include <curl/curl.h>
#include <math.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>

static pthread_once_t curl_once = PTHREAD_ONCE_INIT;
static void init_curl(void) { (void)curl_global_init(CURL_GLOBAL_DEFAULT); }
static bool number_equal(double a, double b) {
  return isfinite(a) && isfinite(b) &&
         fabs(a - b) <= fmax(fabs(a), fabs(b)) * 1e-12;
}
bool nb_http_url(const char *s, nb_error *e) {
  CURLU *u = curl_url();
  bool ok = u && !curl_url_set(u, CURLUPART_URL, s, 0);
  char *scheme = NULL, *host = NULL, *extra = NULL;
  if (ok)
    ok = !curl_url_get(u, CURLUPART_SCHEME, &scheme, 0) &&
         (!strcmp(scheme, "http") || !strcmp(scheme, "https")) &&
         !curl_url_get(u, CURLUPART_HOST, &host, 0) && *host;
  const CURLUPart forbidden[] = {CURLUPART_USER, CURLUPART_PASSWORD,
                                 CURLUPART_QUERY, CURLUPART_FRAGMENT};
  for (size_t i = 0; ok && i < 4; i++) {
    if (!curl_url_get(u, forbidden[i], &extra, 0))
      ok = false;
    curl_free(extra);
    extra = NULL;
  }
  curl_free(scheme);
  curl_free(host);
  curl_url_cleanup(u);
  return ok ? true
            : nb_fail(e, "HTTP(S) URL without credentials, query or fragment "
                         "required");
}
struct transfer {
  const nb_http_options *options;
  nb_error *error;
  char *raw;
  size_t bytes, capacity, parsed;
  json_object *chunks, *usage, *timings, *terminal, *tools, *times;
  char *text;
  size_t text_size;
  char event[128], stream_id[256], finish[64];
  unsigned finish_count;
  bool done, failed;
  uint64_t started, first, finished;
};
static bool append(char **dst, size_t *size, const char *s, size_t n) {
  if (n > NB_LIMIT - *size)
    return false;
  char *p = realloc(*dst, *size + n + 1);
  if (!p)
    return false;
  memcpy(p + *size, s, n);
  *size += n;
  p[*size] = 0;
  *dst = p;
  return true;
}
static bool add_text(struct transfer *t, const char *s) {
  size_t n = strlen(s);
  if (!n)
    return true;
  if (!append(&t->text, &t->text_size, s, n))
    return nb_fail(t->error, "Text evidence size limit");
  uint64_t now = nb_now();
  if (!t->first)
    t->first = now;
  json_object_array_add(t->times, json_object_new_int64((int64_t)now));
  if (t->options->on_output)
    t->options->on_output(t->options->userdata);
  return true;
}
static bool observe_tools(struct transfer *t, json_object *calls) {
  if (!calls)
    return true;
  if (!json_object_is_type(calls, json_type_array) ||
      json_object_array_length(calls) > 128)
    return false;
  for (size_t i = 0; i < json_object_array_length(calls); i++) {
    json_object *call = json_object_array_get_idx(calls, i);
    int64_t index;
    if (!nb_count(call, "index", 0, 127, &index))
      return false;
    while (json_object_array_length(t->tools) <= (size_t)index)
      json_object_array_add(t->tools, json_object_new_object());
    json_object *item = json_object_array_get_idx(t->tools, (size_t)index);
    if (!nb_get(item, "type")) {
      nb_str(item, "id", "");
      nb_str(item, "type", "function");
      json_object *f = json_object_new_object();
      nb_str(f, "name", "");
      nb_str(f, "arguments", "");
      json_object_object_add(item, "function", f);
    }
    if (*nb_string(call, "id"))
      nb_str(item, "id", nb_string(call, "id"));
    const char *keys[] = {"name", "arguments"};
    for (unsigned k = 0; k < 2; k++) {
      json_object *fn = nb_get(item, "function");
      const char *old = nb_string(fn, keys[k]),
                 *new = nb_string(nb_get(call, "function"), keys[k]);
      size_t len = strlen(old);
      char *s = strdup(old);
      if (!s || !append(&s, &len, new, strlen(new))) {
        free(s);
        return false;
      }
      nb_str(fn, keys[k], s);
      free(s);
    }
    if (*nb_string(nb_get(call, "function"), "arguments") && !t->first)
      t->first = nb_now();
  }
  return true;
}
static bool frame(struct transfer *t, const char *s, size_t n) {
  if (n == 6 && !memcmp(s, "[DONE]", 6)) {
    if (t->options->responses || t->done || t->finish_count != 1)
      return nb_fail(t->error, "Invalid DONE terminal");
    t->done = true;
    return true;
  }
  if (t->done)
    return nb_fail(t->error, "Data after stream terminal");
  json_object *o = nb_parse(s, n, t->error);
  if (!o)
    return false;
  json_object_array_add(t->chunks, o);
  if (nb_get(o, "error"))
    return nb_fail(t->error, "Server stream error");
  if (t->options->responses) {
    if (strcmp(nb_string(o, "type"), t->event) ||
        !nb_count(o, "sequence_number", 0, 1000000, NULL) ||
        nb_number(o, "sequence_number") !=
            (int64_t)json_object_array_length(t->chunks) - 1)
      return nb_fail(t->error, "Responses event sequence mismatch");
    const char *type = nb_string(o, "type");
    if (!strcmp(type, "response.output_text.delta") &&
        !add_text(t, nb_string(o, "delta")))
      return false;
    if (!strcmp(type, "response.completed") ||
        !strcmp(type, "response.incomplete")) {
      t->terminal = json_object_get(nb_get(o, "response"));
      t->done = true;
    }
    if (!strcmp(type, "response.failed") || !strcmp(type, "error"))
      return nb_fail(t->error, "Responses stream failed");
    return true;
  }
  if (t->options->strict) {
    const char *id = nb_string(o, "id");
    if (strcmp(nb_string(o, "system_fingerprint"), t->options->provider) ||
        strcmp(nb_string(o, "model"), t->options->model) ||
        strcmp(nb_string(o, "object"), "chat.completion.chunk") || !*id ||
        strlen(id) >= sizeof(t->stream_id) ||
        (t->stream_id[0] && strcmp(t->stream_id, id)))
      return nb_fail(t->error, "Stream identity mismatch");
    strcpy(t->stream_id, id);
  }
  json_object *choices = nb_get(o, "choices");
  if (!json_object_is_type(choices, json_type_array) ||
      json_object_array_length(choices) > 1)
    return nb_fail(t->error, "Invalid choice count");
  json_object *usage = nb_get(o, "usage");
  if (usage) {
    if (t->usage || (t->options->strict && (json_object_array_length(choices) ||
                                            t->finish_count != 1)))
      return nb_fail(t->error, "Invalid stream usage ordering");
    t->usage = json_object_get(usage);
  }
  if (nb_get(o, "lie_timings")) {
    json_object_put(t->timings);
    t->timings = json_object_get(nb_get(o, "lie_timings"));
  }
  for (size_t i = 0; i < json_object_array_length(choices); i++) {
    json_object *choice = json_object_array_get_idx(choices, i),
                *delta = nb_get(choice, "delta");
    if (t->finish_count || nb_number(choice, "index") != 0)
      return nb_fail(t->error, "Choice after finish or invalid index");
    if (!add_text(t, nb_string(delta, "content")) ||
        !observe_tools(t, nb_get(delta, "tool_calls")))
      return false;
    const char *finish = nb_string(choice, "finish_reason");
    if (*finish) {
      if (strlen(finish) >= sizeof(t->finish))
        return false;
      strcpy(t->finish, finish);
      t->finish_count++;
    }
  }
  return true;
}
static size_t receive(char *ptr, size_t size, size_t n, void *arg) {
  struct transfer *t = arg;
  if (size && n > SIZE_MAX / size)
    return 0;
  size_t len = size * n;
  if (t->options && t->options->cancel && atomic_load(t->options->cancel))
    return 0;
  bool stored = len <= NB_LIMIT - t->bytes;
  if (stored && t->bytes + len + 1 > t->capacity) {
    size_t capacity = t->capacity ? t->capacity : 8192;
    while (capacity < t->bytes + len + 1)
      capacity = capacity > NB_LIMIT / 2 ? NB_LIMIT + 1 : capacity * 2;
    char *raw = realloc(t->raw, capacity);
    if (raw) {
      t->raw = raw;
      t->capacity = capacity;
    } else
      stored = false;
  }
  if (!stored) {
    nb_fail(t->error, "HTTP evidence size limit");
    t->failed = true;
    return 0;
  }
  memcpy(t->raw + t->bytes, ptr, len);
  t->bytes += len;
  t->raw[t->bytes] = 0;
  if (!t->options || !t->options->stream)
    return len;
  while (t->parsed < t->bytes) {
    char *end = memchr(t->raw + t->parsed, '\n', t->bytes - t->parsed);
    if (!end) {
      if (t->bytes - t->parsed > 1024 * 1024) {
        nb_fail(t->error, "SSE line size limit");
        t->failed = true;
        return 0;
      }
      break;
    }
    const char *line = t->raw + t->parsed;
    size_t count = (size_t)(end - line);
    t->parsed = (size_t)(end - t->raw) + 1;
    if (count > 1024 * 1024) {
      t->failed = true;
      return 0;
    }
    if (count && line[count - 1] == '\r')
      count--;
    if (count >= 6 && !memcmp(line, "event:", 6)) {
      line += 6;
      count -= 6;
      while (count && *line == ' ') {
        line++;
        count--;
      }
      if (count >= sizeof(t->event)) {
        t->failed = true;
        return 0;
      }
      memcpy(t->event, line, count);
      t->event[count] = 0;
    } else if (count >= 5 && !memcmp(line, "data:", 5)) {
      line += 5;
      count -= 5;
      while (count && *line == ' ') {
        line++;
        count--;
      }
      if (!frame(t, line, count)) {
        t->failed = true;
        return 0;
      }
    }
  }
  return len;
}
static int progress(void *arg, curl_off_t a, curl_off_t b, curl_off_t c,
                    curl_off_t d) {
  (void)a;
  (void)b;
  (void)c;
  (void)d;
  struct transfer *t = arg;
  return t->options && t->options->cancel && atomic_load(t->options->cancel);
}
static void release(struct transfer *t) {
  free(t->raw);
  free(t->text);
  json_object_put(t->chunks);
  json_object_put(t->usage);
  json_object_put(t->timings);
  json_object_put(t->terminal);
  json_object_put(t->tools);
  json_object_put(t->times);
}
static bool perform(struct transfer *t, const char *url, json_object *body,
                    double timeout) {
  if (!isfinite(timeout) || timeout <= 0 || timeout > 7200 ||
      !nb_http_url(url, t->error))
    return false;
  pthread_once(&curl_once, init_curl);
  CURL *c = curl_easy_init();
  if (!c)
    return nb_fail(t->error, "HTTP initialization failed");
  struct curl_slist *headers = NULL;
  headers = curl_slist_append(headers, "Content-Type: application/json");
  headers = curl_slist_append(headers, "Expect:");
  curl_easy_setopt(c, CURLOPT_URL, url);
  curl_easy_setopt(c, CURLOPT_PROTOCOLS_STR, "http,https");
  curl_easy_setopt(c, CURLOPT_NOSIGNAL, 1L);
  curl_easy_setopt(c, CURLOPT_FOLLOWLOCATION, 0L);
  curl_easy_setopt(c, CURLOPT_CONNECTTIMEOUT_MS, (long)(timeout * 1000));
  curl_easy_setopt(c, CURLOPT_TIMEOUT_MS, (long)(timeout * 1000));
  curl_easy_setopt(c, CURLOPT_WRITEFUNCTION, receive);
  curl_easy_setopt(c, CURLOPT_WRITEDATA, t);
  curl_easy_setopt(c, CURLOPT_XFERINFOFUNCTION, progress);
  curl_easy_setopt(c, CURLOPT_XFERINFODATA, t);
  curl_easy_setopt(c, CURLOPT_NOPROGRESS, 0L);
  const char *wire = body ? nb_encoded(body) : NULL;
  if (wire) {
    size_t bytes = strlen(wire);
    if (bytes > 8 * 1024 * 1024) {
      curl_easy_cleanup(c);
      curl_slist_free_all(headers);
      return nb_fail(t->error, "HTTP request exceeds 8 MiB");
    }
    curl_easy_setopt(c, CURLOPT_POST, 1L);
    curl_easy_setopt(c, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(c, CURLOPT_POSTFIELDS, wire);
    curl_easy_setopt(c, CURLOPT_POSTFIELDSIZE_LARGE, (curl_off_t)bytes);
  }
  t->started = nb_now();
  CURLcode result = curl_easy_perform(c);
  t->finished = nb_now();
  long status = 0;
  char *type = NULL;
  curl_easy_getinfo(c, CURLINFO_RESPONSE_CODE, &status);
  curl_easy_getinfo(c, CURLINFO_CONTENT_TYPE, &type);
  bool ok = result == CURLE_OK && status == 200 && !t->failed;
  if (ok && t->options && t->options->stream)
    ok = type && strstr(type, "text/event-stream");
  if (!ok && !t->error->message[0])
    snprintf(t->error->message, sizeof(t->error->message),
             "HTTP request failed: status %ld, %s", status,
             curl_easy_strerror(result));
  curl_easy_cleanup(c);
  curl_slist_free_all(headers);
  return ok;
}
json_object *nb_http_get(const char *url, double timeout, nb_error *e) {
  struct transfer t = {.error = e};
  json_object *o = NULL;
  if (perform(&t, url, NULL, timeout))
    o = nb_parse(t.raw, t.bytes, e);
  release(&t);
  return o;
}
static bool timing_contract(json_object *t, int64_t pp, int64_t tg,
                            int64_t cached, nb_error *e) {
  if (strcmp(nb_string(t, "schema"), "synapse-lie.request-timings.v1") ||
      !json_object_is_type(nb_get(t, "valid"), json_type_boolean) ||
      !json_object_get_boolean(nb_get(t, "valid")) ||
      strcmp(nb_string(t, "scope"), "synchronous_executor_calls"))
    return nb_fail(e, "Invalid executor timing schema");
  const char *counts[] = {"prefill_tokens", "decode_tokens",
                          "prefill_calls",  "decode_calls",
                          "cached_tokens",  "ssd_cached_tokens"};
  for (unsigned i = 0; i < 6; i++)
    if (!nb_count(t, counts[i], 0, INT64_MAX, NULL))
      return nb_fail(e, "Invalid executor count");
  if (nb_number(t, "cached_tokens") != cached ||
      nb_number(t, "prefill_tokens") != pp - cached ||
      nb_number(t, "decode_tokens") != tg ||
      nb_number(t, "ssd_cached_tokens") > cached ||
      (nb_number(t, "decode_calls") != tg &&
       nb_number(t, "decode_calls") != tg + 1))
    return nb_fail(e, "Cache/executor accounting mismatch");
  const char *phases[] = {"prefill", "decode"};
  for (unsigned i = 0; i < 2; i++) {
    char key[64];
    snprintf(key, sizeof(key), "%s_tokens", phases[i]);
    int64_t tokens = nb_number(t, key);
    snprintf(key, sizeof(key), "%s_calls", phases[i]);
    int64_t calls = nb_number(t, key);
    snprintf(key, sizeof(key), "%s_ms", phases[i]);
    json_object *duration = nb_get(t, key);
    double ms = json_object_get_double(duration);
    snprintf(key, sizeof(key), "%s_tokens_per_second", phases[i]);
    json_object *rate = nb_get(t, key);
    if ((!json_object_is_type(duration, json_type_double) &&
         !json_object_is_type(duration, json_type_int)) ||
        !isfinite(ms) || ms < 0 || (!calls && (tokens || ms || rate)) ||
        (calls &&
         (ms <= 0 || !rate ||
          !number_equal(json_object_get_double(rate), tokens * 1000.0 / ms))))
      return nb_fail(e, "Invalid executor timing/rate");
  }
  const char *durations[] = {"ssd_read_ms", "cache_restore_ms",
                             "cache_capture_ms"};
  for (unsigned i = 0; i < 3; i++) {
    json_object *v = nb_get(t, durations[i]);
    double x = json_object_get_double(v);
    if ((!json_object_is_type(v, json_type_double) &&
         !json_object_is_type(v, json_type_int)) ||
        !isfinite(x) || x < 0)
      return nb_fail(e, "Invalid cache duration");
  }
  return true;
}
json_object *nb_http_request(const nb_http_options *o, json_object *body,
                             nb_error *e) {
  struct transfer t = {.options = o,
                       .error = e,
                       .chunks = json_object_new_array(),
                       .tools = json_object_new_array(),
                       .times = json_object_new_array()};
  json_object *row = NULL;
  size_t base = strlen(o->url);
  if (base > 8192) {
    nb_fail(e, "URL too long");
    goto end;
  }
  while (base && o->url[base - 1] == '/')
    base--;
  char url[8256];
  snprintf(url, sizeof(url), "%.*s/%s", (int)base, o->url,
           o->responses ? "responses" : "chat/completions");
  if (!perform(&t, url, body, o->timeout))
    goto end;
  if (o->stream) {
    if (!t.done) {
      nb_fail(e, "Incomplete SSE stream");
      goto end;
    }
  } else {
    t.terminal = nb_parse(t.raw, t.bytes, e);
    if (!t.terminal)
      goto end;
  }
  int64_t budget = nb_number(body,
                             o->responses ? "max_output_tokens" : "max_tokens"),
          pp = 0, tg = 0, cached = 0;
  if (o->responses) {
    json_object *terminal = t.terminal;
    const char *status = nb_string(terminal, "status");
    if (strcmp(nb_string(terminal, "object"), "response") ||
        strcmp(nb_string(terminal, "model"), o->model) ||
        (strcmp(status, "completed") && strcmp(status, "incomplete")) ||
        nb_get(terminal, "error")) {
      nb_fail(e, "Invalid Responses terminal");
      goto end;
    }
    json_object *output = nb_get(terminal, "output");
    char *projected = NULL;
    size_t len = 0;
    if (!json_object_is_type(output, json_type_array)) {
      nb_fail(e, "Invalid Responses output");
      goto end;
    }
    for (size_t i = 0; i < json_object_array_length(output); i++) {
      json_object *item = json_object_array_get_idx(output, i);
      if (strcmp(nb_string(item, "type"), "message"))
        continue;
      json_object *parts = nb_get(item, "content");
      if (!json_object_is_type(parts, json_type_array)) {
        free(projected);
        nb_fail(e, "Invalid Responses content");
        goto end;
      }
      for (size_t k = 0; k < json_object_array_length(parts); k++) {
        json_object *p = json_object_array_get_idx(parts, k);
        if (!strcmp(nb_string(p, "type"), "output_text")) {
          const char *s = nb_string(p, "text");
          if (!append(&projected, &len, s, strlen(s))) {
            free(projected);
            goto end;
          }
        }
      }
    }
    if (o->stream && strcmp(t.text ? t.text : "", projected ? projected : "")) {
      free(projected);
      nb_fail(e, "Responses delta/terminal disagreement");
      goto end;
    }
    free(t.text);
    t.text = projected;
    t.text_size = len;
    t.usage = json_object_get(nb_get(terminal, "usage"));
    if (!nb_count(t.usage, "input_tokens", 1, INT64_MAX, &pp) ||
        !nb_count(t.usage, "output_tokens", 0, budget, &tg) ||
        !nb_count(nb_get(t.usage, "input_tokens_details"), "cached_tokens", 0,
                  pp, &cached)) {
      nb_fail(e, "Invalid Responses usage");
      goto end;
    }
    strcpy(t.finish, !strcmp(status, "incomplete") ? "length" : "stop");
  } else {
    if (!o->stream) {
      json_object *terminal = t.terminal,
                  *choices = nb_get(terminal, "choices");
      if (strcmp(nb_string(terminal, "object"), "chat.completion") ||
          strcmp(nb_string(terminal, "model"), o->model) ||
          (o->strict &&
           strcmp(nb_string(terminal, "system_fingerprint"), o->provider)) ||
          !json_object_is_type(choices, json_type_array) ||
          json_object_array_length(choices) != 1) {
        nb_fail(e, "Invalid completion identity");
        goto end;
      }
      json_object *choice = json_object_array_get_idx(choices, 0);
      const char *content = nb_string(nb_get(choice, "message"), "content");
      if (!append(&t.text, &t.text_size, content, strlen(content)))
        goto end;
      t.usage = json_object_get(nb_get(terminal, "usage"));
      t.timings = json_object_get(nb_get(terminal, "lie_timings"));
      snprintf(t.finish, sizeof(t.finish), "%s",
               nb_string(choice, "finish_reason"));
    }
    if (!*t.finish || !nb_count(t.usage, "prompt_tokens", 1, INT64_MAX, &pp) ||
        !nb_count(t.usage, "completion_tokens", 0, budget, &tg)) {
      nb_fail(e, "Incomplete stream or invalid usage");
      goto end;
    }
    json_object *details = nb_get(t.usage, "prompt_tokens_details");
    if (details && !nb_count(details, "cached_tokens", 0, pp, &cached)) {
      nb_fail(e, "Invalid cached token count");
      goto end;
    }
    if (o->strict && !timing_contract(t.timings, pp, tg, cached, e))
      goto end;
  }
  if (pp > INT64_MAX - tg ||
      !nb_count(t.usage, "total_tokens", pp + tg, pp + tg, NULL)) {
    nb_fail(e, "Usage total mismatch");
    goto end;
  }
  if (o->strict && (strcmp(t.finish, "length") && strcmp(t.finish, "stop"))) {
    nb_fail(e, "Invalid completion reason");
    goto end;
  }
  if (o->strict && !strcmp(t.finish, "length") && tg != budget) {
    nb_fail(e, "Completion budget mismatch");
    goto end;
  }
  uint64_t elapsed = t.finished - t.started;
  if (!elapsed) {
    nb_fail(e, "Invalid HTTP duration");
    goto end;
  }
  row = json_object_new_object();
  char hash[65];
  if (!nb_json_hash(body, hash)) {
    json_object_put(row);
    row = NULL;
    goto end;
  }
  nb_add(row, "request", body);
  nb_str(row, "request_sha256", hash);
  nb_num(row, "request_bytes", (int64_t)strlen(nb_encoded(body)));
  nb_add(row, "response_chunks", t.chunks);
  json_object *assistant = json_object_new_object();
  nb_str(assistant, "role", "assistant");
  nb_str(assistant, "content", t.text ? t.text : "");
  if (json_object_array_length(t.tools))
    nb_add(assistant, "tool_calls", t.tools);
  json_object_object_add(row, "assistant", assistant);
  nb_add(row, "usage", t.usage);
  nb_str(row, "finish_reason", t.finish);
  nb_real(row, "wall_seconds", elapsed / 1e9);
  nb_real(row, "first_output_seconds",
          t.first ? (t.first - t.started) / 1e9 : NAN);
  nb_real(row, "prompt_over_wall_tps", pp * 1e9 / elapsed);
  nb_real(row, "output_over_wall_tps", tg * 1e9 / elapsed);
  json_object_object_add(row, "full_output_budget",
                         json_object_new_boolean(tg == budget));
  nb_add(row, "server_timings", t.timings);
  nb_num(row, "started_ns", (int64_t)t.started);
  nb_num(row, "finished_ns", (int64_t)t.finished);
  nb_num(row, "prompt_tokens", pp);
  nb_num(row, "output_tokens", tg);
  nb_num(row, "cached_tokens", cached);
  nb_str(row, "content", t.text ? t.text : "");
  nb_str(row, "finish", t.finish);
  nb_add(row, "timings", t.timings);
  nb_add(row, "output_event_ns", t.times);
  json_object *gaps = json_object_new_array();
  for (size_t i = 1; i < json_object_array_length(t.times); i++)
    json_object_array_add(
        gaps,
        json_object_new_double(
            (json_object_get_int64(json_object_array_get_idx(t.times, i)) -
             json_object_get_int64(json_object_array_get_idx(t.times, i - 1))) /
            1e6));
  json_object_object_add(row, "inter_output_ms", gaps);
  nb_real(row, "wall_ms", elapsed / 1e6);
  nb_real(row, "first_output_ms", t.first ? (t.first - t.started) / 1e6 : NAN);
end:
  release(&t);
  if (!row && !e->message[0])
    nb_fail(e, "HTTP observation failed");
  return row;
}
