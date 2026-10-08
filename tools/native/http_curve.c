/* SPDX-License-Identifier: MIT */
/* Cached conversation depth protocol ported from Gufo f783fedb llm.py.
 * Copyright (c) 2026 gufo contributors; see third_party/gufo-LICENSE.
 * HTTP client only: never starts, tunes, terminates or loads a model server. */
#include "bench_native.h"
#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <math.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>

#define CURVE_SCHEMA "synapse-lie.http-curve-bench.v1"
#define GUFO_PIN "f783fedb9bea2ec7de941f6da4e02f4a4596b29e"
#define RECIPE "gufo-cached-conversation-f783fedb-v1"
#define MAX_CONTEXT 4194304
static volatile sig_atomic_t interrupted;
static void stop(int sig) {
  (void)sig;
  interrupted = 1;
}
static bool eq(json_object *o, const char *k, const char *s) {
  return !strcmp(nb_string(o, k), s);
}
static bool real(json_object *o, const char *k, double lo, double hi,
                 double *out) {
  json_object *v = nb_get(o, k);
  double n = json_object_get_double(v);
  if ((!json_object_is_type(v, json_type_int) &&
       !json_object_is_type(v, json_type_double)) ||
      !isfinite(n) || n < lo || n > hi)
    return false;
  if (out)
    *out = n;
  return true;
}
static bool truth(json_object *o, const char *k) {
  json_object *v = nb_get(o, k);
  return json_object_is_type(v, json_type_boolean) &&
         json_object_get_boolean(v);
}
static bool close_real(double a, double b) {
  return isfinite(a) && isfinite(b) &&
         fabs(a - b) <= fmax(fmax(fabs(a), fabs(b)), 1) * 1e-12;
}
static bool natural(const char *s, uint64_t max, uint64_t *out) {
  uint64_t n = 0;
  if (!*s)
    return false;
  for (; *s; ++s) {
    unsigned k = (unsigned)(*s - '0');
    if (k > 9 || k > max || n > (max - k) / 10)
      return false;
    n = n * 10 + k;
  }
  *out = n;
  return true;
}
static json_object *depths_parse(const char *s, nb_error *e) {
  char *copy = strdup(s), *p = copy;
  json_object *a = json_object_new_array();
  if (!copy)
    goto bad;
  int64_t previous = -1;
  for (;;) {
    char *comma = strchr(p, ',');
    if (comma)
      *comma = 0;
    uint64_t n;
    if (!natural(p, 1048576, &n) || (int64_t)n <= previous ||
        json_object_array_length(a) >= 32)
      goto bad;
    json_object_array_add(a, json_object_new_int64((int64_t)n));
    previous = (int64_t)n;
    if (!comma)
      break;
    p = comma + 1;
  }
  free(copy);
  return a;
bad:
  free(copy);
  json_object_put(a);
  nb_fail(e, "Depths must be increasing distinct integers in 0..1048576");
  return NULL;
}
typedef struct {
  json_object *id, *rows, *points;
  size_t cursor, requests;
  FILE *file;
  nb_error *error;
  double ratio;
  int64_t overhead;
} curve;
typedef struct {
  int64_t prompt, cached, prefill, output, drafted, accepted;
  double pp_ms, tg_ms, wall, ttft;
  const char *source;
} phase;
static bool observe(json_object *row, unsigned budget, bool stream,
                    bool measured, const char *mode, phase *p, nb_error *e) {
  json_object *body = nb_get(row, "request"), *usage = nb_get(row, "usage");
  int64_t begin, end;
  char hash[65];
  if (!json_object_is_type(body, json_type_object) ||
      !nb_json_hash(body, hash) ||
      strcmp(hash, nb_string(row, "request_sha256")) ||
      !nb_count(body, "max_tokens", budget, budget, NULL) ||
      (stream && !truth(row, "stream_complete")) ||
      !nb_count(usage, "prompt_tokens", 1, MAX_CONTEXT, &p->prompt) ||
      !nb_count(usage, "completion_tokens", measured ? budget : 0, budget,
                &p->output) ||
      !nb_count(usage, "total_tokens", p->prompt + p->output,
                p->prompt + p->output, NULL) ||
      !nb_count(row, "prompt_tokens", p->prompt, p->prompt, NULL) ||
      !nb_count(row, "output_tokens", p->output, p->output, NULL) ||
      !nb_count(row, "cached_tokens", 0, p->prompt, &p->cached) ||
      !nb_count(row, "started_ns", 1, INT64_MAX - 1, &begin) ||
      !nb_count(row, "finished_ns", begin + 1, INT64_MAX, &end) ||
      !real(row, "wall_seconds", 0, 7201, &p->wall) ||
      !close_real(p->wall, (end - begin) / 1e9) ||
      (measured &&
       (!truth(row, "full_output_budget") ||
        !real(row, "first_output_seconds", 0, p->wall, &p->ttft))) ||
      !json_object_is_type(nb_get(nb_get(row, "assistant"), "content"),
                           json_type_string))
    return nb_fail(
        e,
        "Incomplete canonical request, output budget, usage or wall witness");
  json_object *details = nb_get(usage, "prompt_tokens_details");
  int64_t cached = 0;
  if ((details && !nb_count(details, "cached_tokens", 0, p->prompt, &cached)) ||
      cached != p->cached)
    return nb_fail(e, "Canonical usage cache count disagrees");
  if (strcmp(nb_string(row, "finish_reason"), "length") &&
      strcmp(nb_string(row, "finish_reason"), "stop"))
    return nb_fail(e, "Invalid canonical completion reason");
  p->prefill = p->prompt - p->cached;
  json_object *timing = nb_get(row, "server_timings");
  if (timing) {
    p->source = "lie";
    if (!nb_http_timing_contract(timing, p->prompt, p->output, p->cached, e))
      return false;
    const char *actual = nb_string(timing, "decode_mode");
    if (measured && strcmp(actual, mode))
      return nb_fail(e, "Server decode mode differs from --mode");
    p->drafted = nb_number(timing, "mtp_drafted_tokens");
    p->accepted = nb_number(timing, "mtp_accepted_tokens");
  } else {
    timing = nb_get(usage, "gufo");
    p->source = "gufo";
    if (!timing ||
        !nb_count(timing, "prefill_tokens", p->prefill, p->prefill, NULL))
      return nb_fail(
          e,
          "LIE or Gufo executed phase timings required; no wall-rate fallback");
    if (nb_get(usage, "draft_tokens") &&
        !nb_count(usage, "draft_tokens", 0, INT64_MAX, &p->drafted))
      return nb_fail(e, "Invalid Gufo draft count");
    if (nb_get(usage, "draft_tokens_accepted") &&
        !nb_count(usage, "draft_tokens_accepted", 0, p->drafted, &p->accepted))
      return nb_fail(e, "Invalid Gufo accepted draft count");
  }
  if (p->accepted > p->output ||
      (measured && !strcmp(mode, "ar") && (p->drafted || p->accepted)) ||
      !real(timing, "prefill_ms", 0, p->wall * 1000 + .001, &p->pp_ms) ||
      !real(timing, "decode_ms", 0, p->wall * 1000 + .001, &p->tg_ms) ||
      (p->prefill && p->pp_ms <= 0) || (p->output && p->tg_ms <= 0) ||
      p->pp_ms + p->tg_ms > p->wall * 1000 + .001)
    return nb_fail(
        e, "Invalid canonical executed phase duration or draft accounting");
  if ((p->prefill && !isfinite(p->prefill * 1000 / p->pp_ms)) ||
      (p->output && !isfinite(p->output * 1000 / p->tg_ms)))
    return nb_fail(e, "Canonical executed phase rate overflow");
  return true;
}
static json_object *message(const char *role, const char *text) {
  json_object *m = json_object_new_object();
  nb_str(m, "role", role);
  nb_str(m, "content", text);
  return m;
}
static json_object *payload(curve *c, json_object *messages, unsigned budget,
                            bool stream, bool thinking) {
  json_object *o = json_object_new_object();
  nb_str(o, "model", nb_string(c->id, "model"));
  nb_add(o, "messages", messages);
  nb_num(o, "max_tokens", budget);
  nb_num(o, "temperature", 0);
  nb_real(o, "top_p", 1);
  nb_real(o, "frequency_penalty", 0);
  nb_real(o, "presence_penalty", 0);
  if (eq(c->id, "endpoint_profile", "gufo")) {
    nb_num(o, "top_k", 0);
    nb_real(o, "min_p", 0);
    nb_num(o, "min_keep", 0);
    nb_real(o, "repeat_penalty", 1);
    nb_num(o, "repeat_last_n", 64);
  }
  json_object_object_add(o, "stream", json_object_new_boolean(stream));
  if (stream) {
    json_object *opts = json_object_new_object();
    json_object_object_add(opts, "include_usage",
                           json_object_new_boolean(true));
    json_object_object_add(o, "stream_options", opts);
  }
  json_object *kwargs = json_object_new_object();
  json_object_object_add(kwargs, "enable_thinking",
                         json_object_new_boolean(thinking));
  json_object_object_add(o, "chat_template_kwargs", kwargs);
  if (thinking)
    nb_str(o, "reasoning_effort", "high");
  return o;
}
/* Replay and collection share the protocol. Reports regenerate every expected
 * request using retained real prefix replies and recalibration observations;
 * they never trust caller-supplied point aggregates. */
static bool event(curve *c, json_object *want) {
  bool ok;
  if (c->rows) {
    json_object *got = json_object_array_get_idx(c->rows, c->cursor++);
    ok = got && json_object_equal(want, got);
    if (!ok)
      nb_fail(c->error, "Canonical protocol event or point differs from its "
                        "retained requests");
  } else {
    ok = nb_emit(c->file, want);
    if (!ok)
      nb_fail(c->error, "Cannot write canonical protocol event");
  }
  json_object_put(want);
  return ok;
}
static json_object *request(curve *c, const char *kind, int64_t depth,
                            unsigned rep, unsigned attempt,
                            json_object *messages, unsigned budget, bool stream,
                            bool thinking) {
  json_object *body = payload(c, messages, budget, stream, thinking),
              *row = NULL;
  json_object *record = nb_event("request");
  nb_str(record, "phase", kind);
  nb_num(record, "depth", depth);
  nb_num(record, "rep", rep);
  nb_num(record, "attempt", attempt);
  nb_num(record, "index", (int64_t)c->requests++);
  if (c->rows) {
    json_object *got = json_object_array_get_idx(c->rows, c->cursor++);
    const char *keys[] = {"event", "phase", "depth", "rep", "attempt", "index"};
    bool ok = got != NULL;
    for (size_t i = 0; i < sizeof(keys) / sizeof(*keys); ++i)
      ok = ok && nb_same(got, record, keys[i]);
    row = json_object_get(nb_get(got, "observation"));
    if (!ok || !row || !json_object_equal(body, nb_get(row, "request")) ||
        !eq(row, "client_id", "model-bench")) {
      json_object_put(row);
      row = NULL;
      nb_fail(c->error,
              "Canonical request order, payload or session identity changed");
    }
  } else {
    nb_http_options options = {
        .url = nb_string(c->id, "url"),
        .model = nb_string(c->id, "model"),
        .timeout = json_object_get_double(nb_get(c->id, "timeout_seconds")),
        .stream = stream,
        .client_id = "model-bench",
        .interrupted = &interrupted};
    json_object *bodies = json_object_new_array();
    json_object_array_add(bodies, json_object_get(body));
    bool complete = false;
    json_object *observations =
        nb_http_cohort(&options, bodies, &complete, c->error);
    row = json_object_get(json_object_array_get_idx(observations, 0));
    nb_add(record, "observation", row);
    if (!complete)
      nb_str(record, "error", c->error->message);
    bool written = nb_emit(c->file, record);
    if (!written)
      nb_fail(c->error, "Cannot write canonical request evidence");
    json_object_put(observations);
    json_object_put(bodies);
    if (!written || !complete) {
      json_object_put(row);
      row = NULL;
    }
  }
  json_object_put(body);
  json_object_put(record);
  return row;
}
static bool setup(curve *c) {
  phase p = {0};
  json_object *messages = json_object_new_array();
  json_object_array_add(messages, message("user", "Hi"));
  json_object *o =
      request(c, "calibration-overhead", 0, 0, 0, messages, 1, true, false);
  bool ok = o && observe(o, 1, true, false, "ar", &p, c->error);
  json_object_put(o);
  json_object_put(messages);
  if (!ok)
    return false;
  c->overhead = p.prompt - 1;
  char *text = nb_gufo_text(7777, 3000, c->error);
  if (!text)
    return false;
  messages = json_object_new_array();
  json_object_array_add(messages, message("user", text));
  free(text);
  o = request(c, "calibration-probe", 0, 0, 0, messages, 1, true, false);
  p = (phase){0};
  ok = o && observe(o, 1, true, false, "ar", &p, c->error);
  json_object_put(o);
  json_object_put(messages);
  if (!ok || p.prompt <= c->overhead)
    return nb_fail(c->error, "Invalid tokenizer calibration");
  c->ratio = (p.prompt - c->overhead) / 3000.0;
  json_object *calibration = nb_event("calibration");
  nb_num(calibration, "template_overhead", c->overhead);
  nb_real(calibration, "tokens_per_word", c->ratio);
  if (!event(c, calibration))
    return false;
  unsigned warm = (unsigned)nb_number(c->id, "warmups"),
           pp = (unsigned)nb_number(c->id, "prompt_limit");
  for (unsigned i = 0; i < warm; ++i) {
    text = nb_gufo_text(8888, nb_gufo_words(pp, c->ratio), c->error);
    if (!text)
      return false;
    messages = json_object_new_array();
    json_object_array_add(messages, message("user", text));
    free(text);
    o = request(c, "warmup", 0, i, 0, messages, 16, true, false);
    p = (phase){0};
    ok = o && observe(o, 16, true, false, "ar", &p, c->error);
    json_object_put(o);
    json_object_put(messages);
    if (!ok)
      return false;
  }
  return true;
}
static json_object *point(curve *c, int64_t depth, unsigned rep) {
  unsigned pp = (unsigned)nb_number(c->id, "prompt_limit"),
           tg = (unsigned)nb_number(c->id, "output_limit");
  double ratio = c->ratio,
         fraction = json_object_get_double(nb_get(c->id, "depth_tolerance"));
  const char *task = nb_string(c->id, "task");
  bool thinking = !strcmp(task, "thinking");
  double new_target = pp - c->overhead;
  for (unsigned attempt = 0; attempt < 4; ++attempt) {
    double ratio_before = ratio;
    json_object *messages = json_object_new_array(), *reply = NULL, *o = NULL,
                *out = NULL;
    phase p = {0};
    if (depth > 0) {
      char *prefix = nb_gufo_text(
          (uint64_t)nb_number(c->id, "seed") + (uint64_t)depth,
          nb_gufo_words((double)depth - c->overhead - 8, ratio), c->error);
      if (!prefix) {
        json_object_put(messages);
        return NULL;
      }
      json_object_array_add(messages, message("user", prefix));
      free(prefix);
      reply = request(c, "prefix", depth, rep, attempt, messages, 8, false,
                      thinking);
      if (!reply || !observe(reply, 8, false, false, "ar", &p, c->error))
        goto end;
      json_object_array_add(messages, nb_copy(nb_get(reply, "assistant")));
    }
    char *text = nb_gufo_turn(new_target, ratio, task, (uint64_t)depth, rep,
                              attempt, c->error);
    if (!text)
      goto end;
    json_object_array_add(messages, message("user", text));
    free(text);
    o = request(c, "measured", depth, rep, attempt, messages, tg, true,
                thinking);
    p = (phase){0};
    if (!o ||
        !observe(o, tg, true, true, nb_string(c->id, "mode"), &p, c->error))
      goto end;
    if (p.prompt + p.output > nb_number(c->id, "context_capacity_declared")) {
      nb_fail(c->error,
              "Physical prompt plus output exceeds declared context capacity");
      goto end;
    }
    double cache_tolerance = fmax(32, floor(depth * fraction)),
           pp_tolerance = fmax(32, floor(pp * fraction));
    bool accepted = fabs((double)p.cached - depth) <= cache_tolerance &&
                    fabs((double)p.prefill - pp) <= pp_tolerance;
    if (accepted) {
      out = nb_event("point");
      nb_num(out, "depth", depth);
      nb_num(out, "rep", rep);
      nb_num(out, "attempt", attempt);
      nb_num(out, "request_index", (int64_t)c->requests - 1);
      nb_real(out, "tokens_per_word", ratio_before);
      nb_str(out, "timing_source", p.source);
      nb_num(out, "prompt_tokens", p.prompt);
      nb_num(out, "cached_tokens", p.cached);
      nb_num(out, "prefill_tokens", p.prefill);
      nb_num(out, "output_tokens", p.output);
      nb_num(out, "draft_tokens", p.drafted);
      nb_num(out, "accepted_draft_tokens", p.accepted);
      nb_real(out, "pp_tps", p.prefill ? p.prefill * 1000 / p.pp_ms : NAN);
      nb_real(out, "tg_tps", p.output ? p.output * 1000 / p.tg_ms : NAN);
      nb_real(out, "wall_seconds", p.wall);
      nb_real(out, "ttft_seconds", p.ttft);
      nb_real(out, "output_over_wall_tps", p.output / p.wall);
      nb_real(out, "draft_acceptance",
              p.drafted ? (double)p.accepted / p.drafted : NAN);
      nb_real(out, "accepted_per_step",
              p.drafted && p.output > p.accepted
                  ? (double)p.accepted / (p.output - p.accepted)
                  : NAN);
      char hash[65];
      const char *content = nb_string(nb_get(o, "assistant"), "content");
      if (!nb_hash(content, strlen(content), hash)) {
        json_object_put(out);
        out = NULL;
        goto end;
      }
      nb_str(out, "completion_sha256", hash);
      nb_add(out, "request_sha256", nb_get(o, "request_sha256"));
      json_object_array_add(c->points, nb_copy(out));
      if (!event(c, out)) {
        out = NULL;
        goto end;
      }
      /* event consumed out; return a separate owned success marker. */
      out = json_object_new_boolean(true);
    } else {
      size_t words = 0;
      for (size_t i = 0; i < json_object_array_length(messages); ++i) {
        json_object *m = json_object_array_get_idx(messages, i);
        if (eq(m, "role", "user"))
          words += nb_gufo_word_count(nb_string(m, "content"));
      }
      ratio = (p.prompt - c->overhead) / (double)words;
      if (!words || !isfinite(ratio) || ratio <= 0) {
        nb_fail(c->error, "Invalid depth recalibration");
        goto end;
      }
      c->ratio = ratio;
      json_object *r = nb_event("recalibration");
      nb_num(r, "depth", depth);
      nb_num(r, "rep", rep);
      nb_num(r, "attempt", attempt);
      nb_real(r, "tokens_per_word", ratio);
      nb_num(r, "cached_tokens", p.cached);
      nb_num(r, "prefill_tokens", p.prefill);
      if (!event(c, r))
        goto end;
    }
  end:
    json_object_put(reply);
    json_object_put(o);
    json_object_put(messages);
    if (out)
      return out;
    if (c->error->message[0])
      return NULL;
  }
  nb_fail(c->error,
          "Cached prefix or new prefill outside tolerance after four attempts");
  return NULL;
}
static bool run(curve *c) {
  if (!setup(c))
    return false;
  json_object *depths = nb_get(c->id, "depths");
  for (size_t i = 0; i < json_object_array_length(depths); ++i)
    for (unsigned rep = 0; rep < (unsigned)nb_number(c->id, "repetitions");
         ++rep) {
      json_object *p = point(
          c, json_object_get_int64(json_object_array_get_idx(depths, i)), rep);
      if (!p)
        return false;
      json_object_put(p);
    }
  return true;
}
static bool valid_id(json_object *id, nb_error *e) {
  json_object *depths = nb_get(id, "depths");
  if (!eq(id, "schema", CURVE_SCHEMA) || !eq(id, "recipe", RECIPE) ||
      !eq(id, "gufo_commit", GUFO_PIN) || !*nb_string(id, "model") ||
      !*nb_string(id, "server_label") ||
      (!eq(id, "endpoint_profile", "openai") &&
       !eq(id, "endpoint_profile", "gufo")) ||
      (!eq(id, "mode", "ar") && !eq(id, "mode", "mtp")) ||
      !nb_gufo_instruction(nb_string(id, "task")) ||
      !nb_count(id, "prompt_limit", 1, 1048576, NULL) ||
      !nb_count(id, "output_limit", 1, 65536, NULL) ||
      !nb_count(id, "context_capacity_declared", 32, MAX_CONTEXT, NULL) ||
      !nb_count(id, "repetitions", 1, 100, NULL) ||
      !nb_count(id, "warmups", 0, 100, NULL) ||
      !nb_count(id, "seed", 0, UINT32_MAX, NULL) ||
      !real(id, "depth_tolerance", 0, .1, NULL) ||
      !real(id, "timeout_seconds", .001, NB_HTTP_TIMEOUT_MAX_SECONDS, NULL) ||
      !eq(id, "client_id", "model-bench") ||
      !nb_count(id, "prefix_reply_tokens", 8, 8, NULL) ||
      !nb_count(id, "max_attempts", 4, 4, NULL) ||
      !json_object_is_type(depths, json_type_array) ||
      !json_object_array_length(depths) ||
      json_object_array_length(depths) > 32)
    return nb_fail(e, "Invalid canonical benchmark identity");
  int64_t previous = -1, capacity = nb_number(id, "context_capacity_declared");
  for (size_t i = 0; i < json_object_array_length(depths); ++i) {
    json_object *v = json_object_array_get_idx(depths, i);
    int64_t d = json_object_get_int64(v);
    if (!json_object_is_type(v, json_type_int) || d <= previous ||
        d > 1048576 ||
        d + nb_number(id, "prompt_limit") + nb_number(id, "output_limit") >
            capacity)
      return nb_fail(e,
                     "Depth plus prefill and output exceeds declared context");
    previous = d;
  }
  return nb_http_url(nb_string(id, "url"), e);
}
int nb_http_curve_main(int argc, char **argv) {
  nb_error e = {0};
  int rc = 2;
  FILE *file = NULL;
  const char *output = NULL, *graphs = NULL, *compare = NULL;
  json_object *id = nb_event("identity"), *points = json_object_new_array();
  nb_str(id, "schema", CURVE_SCHEMA);
  nb_str(id, "recipe", RECIPE);
  nb_str(id, "gufo_commit", GUFO_PIN);
  nb_str(id, "model", "bench");
  nb_str(id, "server_label", "LIE");
  nb_str(id, "mode", "ar");
  nb_str(id, "task", "prose");
  nb_str(id, "endpoint_profile", "openai");
  nb_str(id, "client_id", "model-bench");
  nb_str(id, "client_execution", "curl-multi-single-event-loop");
  nb_str(id, "timing_scope",
         "executed-server-phases; HTTP-wall-and-TTFT-separate");
  nb_num(id, "prompt_limit", 2048);
  nb_num(id, "output_limit", 128);
  nb_num(id, "repetitions", 1);
  nb_num(id, "warmups", 1);
  nb_num(id, "seed", 1);
  nb_num(id, "prefix_reply_tokens", 8);
  nb_num(id, "max_attempts", 4);
  nb_num(id, "context_capacity_declared", 133760);
  nb_real(id, "depth_tolerance", .005);
  nb_real(id, "timeout_seconds", 3600);
  json_object_object_add(
      id, "depths",
      depths_parse("0,4096,8192,12288,16384,32768,65536,131072", &e));
  uint64_t seen = 0;
  const char *options[] = {"--suite",
                           "--url",
                           "--model",
                           "--server-label",
                           "--output",
                           "--graphs",
                           "--compare",
                           "--depths",
                           "--pp",
                           "--tg",
                           "--repetitions",
                           "--warmups",
                           "--seed",
                           "--task",
                           "--mode",
                           "--endpoint-profile",
                           "--context-capacity",
                           "--depth-tolerance",
                           "--timeout"};
  const char *keys[] = {NULL,
                        "url",
                        "model",
                        "server_label",
                        NULL,
                        NULL,
                        NULL,
                        NULL,
                        "prompt_limit",
                        "output_limit",
                        "repetitions",
                        "warmups",
                        "seed",
                        "task",
                        "mode",
                        "endpoint_profile",
                        "context_capacity_declared",
                        "depth_tolerance",
                        "timeout_seconds"};
  for (int i = 1; i < argc; ++i) {
    if (!strcmp(argv[i], "--help")) {
      puts("Usage: synapse-lie-bench --suite http-curve --url HTTP-BASE/v1 "
           "--output NEW-JSONL\n"
           "  [--model bench] [--server-label LIE] [--endpoint-profile "
           "openai|gufo]\n"
           "  [--depths 0,4096,8192,12288,16384,32768,65536,131072]\n"
           "  [--pp 2048] [--tg 128] [--context-capacity 133760] [--mode "
           "ar|mtp]\n"
           "  [--task prose|repetition|copy|story|thinking] [--seed 1]\n"
           "  [--warmups 1] [--repetitions 1] [--depth-tolerance 0.005] "
           "[--timeout 3600]\n"
           "  [--graphs NEW-DIRECTORY] [--compare REFERENCE-JSONL]\n"
           "Canonical Gufo cached conversation: calibration, actual 8-token "
           "prefix reply,\n"
           "up to four depth corrections; exact seeded prose recipe, greedy "
           "decoding.\n"
           "Native C HTTP/JSONL/CSV/SVG/PNG; no Python. Requires an authorized "
           "running\n"
           "server with executed LIE or Gufo phase timings and sufficient "
           "context/cache.\n"
           "Does not start a server, load models or bypass coordinated GPU "
           "leases.");
      rc = 0;
      goto end;
    }
    size_t k = 0;
    while (k < sizeof(options) / sizeof(*options) &&
           strcmp(argv[i], options[k]))
      ++k;
    if (k == sizeof(options) / sizeof(*options) || i + 1 == argc ||
        (seen & (UINT64_C(1) << k)))
      goto usage;
    seen |= UINT64_C(1) << k;
    const char *value = argv[++i];
    if (!k) {
      if (strcmp(value, "http-curve"))
        goto usage;
    } else if (k == 4)
      output = value;
    else if (k == 5)
      graphs = value;
    else if (k == 6)
      compare = value;
    else if (k == 7) {
      json_object *d = depths_parse(value, &e);
      if (!d)
        goto usage;
      json_object_object_add(id, "depths", d);
    } else if ((k >= 8 && k <= 12) || k == 16) {
      uint64_t n;
      if (!natural(value, UINT32_MAX, &n))
        goto usage;
      nb_num(id, keys[k], (int64_t)n);
    } else if (k == 17 || k == 18) {
      char *tail = NULL;
      errno = 0;
      double n = strtod(value, &tail);
      if (!*value || !tail || *tail || errno || !isfinite(n))
        goto usage;
      nb_real(id, keys[k], n);
    } else
      nb_str(id, keys[k], value);
  }
  if (!output || (compare && !graphs) || !valid_id(id, &e))
    goto usage;
  file = nb_exclusive(output, &e);
  if (!file) {
    rc = 1;
    goto end;
  }
  if (!nb_emit(file, id)) {
    nb_fail(&e, "Cannot write canonical benchmark identity");
    rc = 1;
    goto end;
  }
  struct sigaction action = {0}, old_int, old_term;
  action.sa_handler = stop;
  sigemptyset(&action.sa_mask);
  interrupted = 0;
  bool int_set = !sigaction(SIGINT, &action, &old_int),
       term_set = !sigaction(SIGTERM, &action, &old_term);
  curve c = {.id = id, .points = points, .file = file, .error = &e};
  bool ok = int_set && term_set && run(&c);
  if (int_set)
    sigaction(SIGINT, &old_int, NULL);
  if (term_set)
    sigaction(SIGTERM, &old_term, NULL);
  json_object *last = nb_event(ok ? "complete" : "failed");
  nb_num(last, "exit_code", ok ? 0 : 1);
  nb_num(last, "requests", (int64_t)c.requests);
  nb_num(last, "points", (int64_t)json_object_array_length(points));
  if (!ok)
    nb_str(last, "error",
           e.message[0] ? e.message
                        : "Canonical benchmark interrupted or write failed");
  bool written = nb_emit(file, last);
  json_object_put(last);
  if (fclose(file))
    written = false;
  file = NULL;
  rc = ok && written ? 0 : 1;
  if (!rc && graphs)
    rc = nb_report(output, graphs, nb_string(id, "server_label"), compare,
                   "Reference", false, &e);
  goto end;
usage:
  if (!e.message[0])
    nb_fail(
        &e,
        "Invalid canonical HTTP curve options; use --suite http-curve --help");
end:
  if (file)
    fclose(file);
  json_object_put(id);
  json_object_put(points);
  if (rc)
    fprintf(stderr, "%s\n",
            e.message[0] ? e.message : "Canonical HTTP benchmark failed");
  return rc;
}
static const char *metrics[] = {"pp_tps",
                                "tg_tps",
                                "wall_seconds",
                                "ttft_seconds",
                                "output_over_wall_tps",
                                "draft_acceptance",
                                "accepted_per_step"};
json_object *nb_http_curve_summary(json_object *rows, nb_error *e) {
  size_t n = json_object_array_length(rows);
  json_object *id = json_object_array_get_idx(rows, 0),
              *last = json_object_array_get_idx(rows, n ? n - 1 : 0);
  if (n < 3 || !eq(id, "event", "identity") || !valid_id(id, e) ||
      !eq(last, "event", "complete") ||
      !nb_count(last, "exit_code", 0, 0, NULL)) {
    nb_fail(e, "Incomplete canonical benchmark evidence");
    return NULL;
  }
  json_object *points = json_object_new_array(), *summary = NULL;
  curve c = {.id = id, .rows = rows, .points = points, .cursor = 1, .error = e};
  if (!run(&c) || c.cursor != n - 1 ||
      !nb_count(last, "requests", (int64_t)c.requests, (int64_t)c.requests,
                NULL) ||
      !nb_count(last, "points", (int64_t)json_object_array_length(points),
                (int64_t)json_object_array_length(points), NULL)) {
    if (!e->message[0])
      nb_fail(e, "Unexpected canonical request/event count");
    goto end;
  }
  summary = json_object_new_object();
  nb_add(summary, "identity", id);
  nb_str(summary, "scope",
         "canonical-cached-conversation; dynamic histories, not numerical "
         "qualification");
  json_object *configurations = json_object_new_array();
  json_object_object_add(summary, "configurations", configurations);
  unsigned reps = (unsigned)nb_number(id, "repetitions");
  json_object *depths = nb_get(id, "depths");
  const char *source = NULL;
  for (size_t i = 0; i < json_object_array_length(depths); ++i) {
    json_object *p = json_object_new_object(),
                *samples = json_object_new_array();
    nb_add(p, "depth", json_object_array_get_idx(depths, i));
    nb_num(p, "samples", reps);
    json_object_object_add(p, "observations", samples);
    for (unsigned r = 0; r < reps; ++r) {
      json_object *point_row = json_object_array_get_idx(points, i * reps + r);
      if (source && strcmp(source, nb_string(point_row, "timing_source"))) {
        json_object_put(p);
        json_object_put(summary);
        summary = NULL;
        nb_fail(e, "Mixed timing sources inside a canonical run");
        goto end;
      }
      source = nb_string(point_row, "timing_source");
      json_object_array_add(samples, nb_copy(point_row));
    }
    nb_str(p, "timing_source", source);
    for (size_t k = 0; k < sizeof(metrics) / sizeof(*metrics); ++k) {
      double values[100];
      size_t count = 0;
      for (unsigned r = 0; r < reps; ++r) {
        json_object *s = json_object_array_get_idx(samples, r);
        double v;
        if (real(s, metrics[k], 0, 1e30, &v))
          values[count++] = v;
      }
      json_object *distribution = nb_distribution(values, count);
      if (distribution && count > 1) {
        double mean = json_object_get_double(nb_get(distribution, "mean")),
               variance = 0;
        for (size_t j = 0; j < count; ++j)
          variance += (values[j] - mean) * (values[j] - mean);
        nb_real(distribution, "sd", sqrt(variance / (count - 1)));
      } else if (distribution)
        nb_real(distribution, "sd", NAN);
      json_object_object_add(p, metrics[k], distribution);
    }
    json_object_array_add(configurations, p);
  }
end:
  json_object_put(points);
  return summary;
}
static void csv_text(FILE *f, const char *s) {
  fputc('"', f);
  for (; *s; ++s) {
    if (*s == '"')
      fputc('"', f);
    fputc(*s, f);
  }
  fputc('"', f);
}
int nb_http_curve_export(json_object *a, json_object *b, const char *directory,
                         const char *label, const char *ref_label,
                         nb_error *e) {
  int rc = 1;
  json_object *ai = nb_get(a, "identity"), *ap = nb_get(a, "configurations"),
              *bp = nb_get(b, "configurations");
  json_object *summary = json_object_new_object(),
              *checks = json_object_new_array();
  nb_add(summary, "primary", a);
  nb_add(summary, "reference", b);
  nb_add(summary, "comparison", checks);
  nb_str(summary, "comparison_scope",
         "Matched workload recipe; dynamic prefix replies and calibrated token "
         "counts may differ. No numerical qualification is inferred.");
  if (b) {
    json_object *bi = nb_get(b, "identity");
    const char *keys[] = {"schema",
                          "recipe",
                          "gufo_commit",
                          "mode",
                          "task",
                          "seed",
                          "depths",
                          "prompt_limit",
                          "output_limit",
                          "repetitions",
                          "warmups",
                          "depth_tolerance",
                          "context_capacity_declared",
                          "prefix_reply_tokens",
                          "max_attempts"};
    for (size_t i = 0; i < sizeof(keys) / sizeof(*keys); ++i)
      if (!nb_same(ai, bi, keys[i])) {
        nb_fail(e, "Canonical comparison workload declarations differ");
        goto end;
      }
    if (json_object_array_length(ap) != json_object_array_length(bp)) {
      nb_fail(e, "Canonical comparison point counts differ");
      goto end;
    }
    for (size_t i = 0; i < json_object_array_length(ap); ++i) {
      json_object *p = json_object_array_get_idx(ap, i),
                  *q = json_object_array_get_idx(bp, i);
      if (!nb_same(p, q, "depth")) {
        nb_fail(e, "Canonical comparison depths differ");
        goto end;
      }
      json_object *check = json_object_new_object();
      nb_add(check, "depth", nb_get(p, "depth"));
      json_object *ps = nb_get(p, "observations"),
                  *qs = nb_get(q, "observations");
      bool inputs = true, outputs = true, counts = true;
      for (size_t j = 0; j < json_object_array_length(ps); ++j) {
        json_object *x = json_object_array_get_idx(ps, j),
                    *y = json_object_array_get_idx(qs, j);
        inputs = inputs && nb_same(x, y, "request_sha256");
        outputs = outputs && nb_same(x, y, "completion_sha256");
        counts = counts && nb_same(x, y, "cached_tokens") &&
                 nb_same(x, y, "prefill_tokens") &&
                 nb_same(x, y, "output_tokens");
      }
      json_object_object_add(check, "exact_request_equal",
                             json_object_new_boolean(inputs));
      json_object_object_add(check, "completion_equal",
                             json_object_new_boolean(outputs));
      json_object_object_add(check, "physical_counts_equal",
                             json_object_new_boolean(counts));
      nb_add(check, "primary_timing_source", nb_get(p, "timing_source"));
      nb_add(check, "reference_timing_source", nb_get(q, "timing_source"));
      for (size_t k = 0; k < 2; ++k) {
        char key[64];
        snprintf(key, sizeof(key), "%s_mean_ratio", metrics[k]);
        double denominator =
            json_object_get_double(nb_get(nb_get(q, metrics[k]), "mean"));
        nb_real(check, key,
                denominator > 0 ? json_object_get_double(
                                      nb_get(nb_get(p, metrics[k]), "mean")) /
                                      denominator
                                : NAN);
      }
      json_object_array_add(checks, check);
    }
  }
  if (!nb_mkdir(directory, e))
    goto end;
  char path[4096];
  if (snprintf(path, sizeof(path), "%s/summary.json", directory) >=
      (int)sizeof(path)) {
    nb_fail(e, "Canonical report path too long");
    goto end;
  }
  if (!nb_write_json(path, summary, e))
    goto end;
  snprintf(path, sizeof(path), "%s/summary.csv", directory);
  FILE *csv = nb_exclusive(path, e);
  if (!csv)
    goto end;
  fputs("label,depth,samples,timing_source,metric,n,mean,sd,median,min,max\n",
        csv);
  json_object *sets[] = {a, b};
  const char *labels[] = {label, ref_label};
  for (unsigned s = 0; s < (b ? 2u : 1u); ++s) {
    json_object *points = nb_get(sets[s], "configurations");
    for (size_t i = 0; i < json_object_array_length(points); ++i) {
      json_object *p = json_object_array_get_idx(points, i);
      for (size_t k = 0; k < sizeof(metrics) / sizeof(*metrics); ++k) {
        csv_text(csv, labels[s]);
        fprintf(csv, ",%" PRId64 ",%" PRId64 ",", nb_number(p, "depth"),
                nb_number(p, "samples"));
        csv_text(csv, nb_string(p, "timing_source"));
        fputc(',', csv);
        csv_text(csv, metrics[k]);
        json_object *value = nb_get(p, metrics[k]);
        const char *keys[] = {"n", "mean", "sd", "median", "min", "max"};
        for (size_t j = 0; j < sizeof(keys) / sizeof(*keys); ++j) {
          fputc(',', csv);
          json_object *v = nb_get(value, keys[j]);
          if (v)
            fputs(nb_encoded(v), csv);
        }
        fputc('\n', csv);
      }
    }
  }
  bool written = !ferror(csv);
  if (fclose(csv))
    written = false;
  if (!written) {
    nb_fail(e, "Canonical CSV write failed");
    goto end;
  }
  nb_plot_panel panels[4] = {0};
  const char *titles[] = {"Executed new-turn prefill (mean, min/max)",
                          "Server decode (mean, min/max)",
                          "Complete HTTP request wall time",
                          "Client first output"};
  const char *units[] = {"new tokens/s", "output tokens/s", "seconds",
                         "seconds"};
  bool plotted = true;
  for (unsigned k = 0; k < 4 && plotted; ++k) {
    panels[k].title = titles[k];
    panels[k].mean = true;
    panels[k].unit = units[k];
    panels[k].x_label = "Cached conversation depth (tokens)";
    panels[k].count = b ? 2 : 1;
    for (unsigned s = 0; s < panels[k].count && plotted; ++s) {
      nb_plot_series *v = &panels[k].series[s];
      v->count = json_object_array_length(ap);
      v->label = labels[s];
      v->ticks = calloc(v->count, sizeof(*v->ticks));
      v->median = malloc(v->count * sizeof(double));
      v->low = malloc(v->count * sizeof(double));
      v->high = malloc(v->count * sizeof(double));
      if (!v->ticks || !v->median || !v->low || !v->high) {
        plotted = false;
        break;
      }
      json_object *points = s ? bp : ap;
      for (size_t i = 0; i < v->count; ++i) {
        json_object *p = json_object_array_get_idx(points, i),
                    *m = nb_get(p, metrics[k]);
        int64_t depth = nb_number(p, "depth");
        char tick[32];
        if (depth && depth % 1024 == 0)
          snprintf(tick, sizeof(tick), "%" PRId64 "K", depth / 1024);
        else
          snprintf(tick, sizeof(tick), "%" PRId64, depth);
        v->ticks[i] = strdup(tick);
        if (!v->ticks[i]) {
          plotted = false;
          break;
        }
        v->median[i] = m ? json_object_get_double(nb_get(m, "mean")) : NAN;
        v->low[i] = m ? json_object_get_double(nb_get(m, "min")) : NAN;
        v->high[i] = m ? json_object_get_double(nb_get(m, "max")) : NAN;
      }
    }
  }
  if (plotted)
    plotted =
        nb_plot(directory,
                "Canonical Gufo cached conversation - recorded server phases",
                panels, 4, e);
  for (unsigned k = 0; k < 4; ++k)
    for (unsigned s = 0; s < panels[k].count; ++s) {
      nb_plot_series *v = &panels[k].series[s];
      if (v->ticks)
        for (size_t i = 0; i < v->count; ++i)
          free((void *)v->ticks[i]);
      free(v->ticks);
      free(v->median);
      free(v->low);
      free(v->high);
    }
  if (plotted)
    rc = 0;
  else if (!e->message[0])
    nb_fail(e, "Canonical graph allocation failed");
end:
  json_object_put(summary);
  json_object_put(checks);
  return rc;
}
