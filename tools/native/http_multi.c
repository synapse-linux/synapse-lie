/* SPDX-License-Identifier: MIT */
/* Prepared HTTP cohorts. No model loading or server/process control. */
#include "bench_native.h"
#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <math.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define MULTI_SCHEMA "synapse-lie.http-multi-bench.v1"
static volatile sig_atomic_t interrupted;
static void stop(int signal_number) {
  (void)signal_number;
  interrupted = 1;
}
static bool eq(json_object *o, const char *key, const char *value) {
  return !strcmp(nb_string(o, key), value);
}
static bool real_value(json_object *o, const char *key, double low, double high,
                       double *out) {
  json_object *v = nb_get(o, key);
  double x = json_object_get_double(v);
  if ((!json_object_is_type(v, json_type_int) &&
       !json_object_is_type(v, json_type_double)) ||
      !isfinite(x) || x < low || x > high)
    return false;
  if (out)
    *out = x;
  return true;
}
static bool close_value(double a, double b) {
  return isfinite(a) && isfinite(b) &&
         fabs(a - b) <= fmax(fmax(fabs(a), fabs(b)), 1) * 1e-12;
}
static bool true_value(json_object *o, const char *key) {
  json_object *v = nb_get(o, key);
  return json_object_is_type(v, json_type_boolean) &&
         json_object_get_boolean(v);
}
static bool natural(const char *text, uint64_t limit, uint64_t *out) {
  uint64_t n = 0;
  if (!*text)
    return false;
  for (; *text; ++text) {
    unsigned k = (unsigned)(*text - '0');
    if (k > 9 || k > limit || n > (limit - k) / 10)
      return false;
    n = n * 10 + k;
  }
  *out = n;
  return true;
}
static json_object *numbers(const char *text, nb_error *e) {
  json_object *a = json_object_new_array();
  char *copy = strdup(text), *at = copy;
  if (!copy) {
    json_object_put(a);
    return NULL;
  }
  for (;;) {
    char *comma = strchr(at, ',');
    if (comma)
      *comma = 0;
    uint64_t value;
    if (!natural(at, 8, &value) || !value || json_object_array_length(a) >= 8)
      goto bad;
    for (size_t i = 0; i < json_object_array_length(a); ++i)
      if (json_object_get_int64(json_object_array_get_idx(a, i)) ==
          (int64_t)value)
        goto bad;
    json_object_array_add(a, json_object_new_int64((int64_t)value));
    if (!comma)
      break;
    at = comma + 1;
  }
  free(copy);
  return a;
bad:
  free(copy);
  json_object_put(a);
  nb_fail(e, "Distinct user counts in 1..8 required");
  return NULL;
}
static json_object *payload(json_object *supplied, const char *model,
                            unsigned output, nb_error *e) {
  if (!json_object_is_type(supplied, json_type_object)) {
    nb_fail(e, "Corpus body must be an object");
    return NULL;
  }
  json_object *messages = nb_get(supplied, "messages"),
              *kwargs = nb_get(supplied, "chat_template_kwargs");
  if (!json_object_is_type(messages, json_type_array) ||
      !json_object_array_length(messages) ||
      (nb_get(supplied, "temperature") &&
       !real_value(supplied, "temperature", 0, 0, NULL)) ||
      (kwargs && !json_object_is_type(kwargs, json_type_object))) {
    nb_fail(e, "Nonempty messages and greedy sampling required");
    return NULL;
  }
  json_object *o = nb_copy(supplied), *stream = json_object_new_object();
  nb_str(o, "model", model);
  nb_num(o, "max_tokens", output);
  nb_num(o, "temperature", 0);
  nb_real(o, "top_p", 1);
  nb_num(o, "frequency_penalty", 0);
  nb_num(o, "presence_penalty", 0);
  json_object_object_add(o, "stream", json_object_new_boolean(true));
  json_object_object_add(stream, "include_usage",
                         json_object_new_boolean(true));
  json_object_object_add(o, "stream_options", stream);
  json_object *template_options =
      kwargs ? nb_copy(kwargs) : json_object_new_object();
  json_object_object_add(template_options, "enable_thinking",
                         json_object_new_boolean(false));
  json_object_object_add(o, "chat_template_kwargs", template_options);
  return o;
}
typedef struct {
  int64_t prompt, output, cached, prefill;
  double pp_ms, tg_ms, wall, ttft;
  const char *source;
} observation;
static bool observe(json_object *row, unsigned budget, observation *out,
                    nb_error *e) {
  json_object *request = nb_get(row, "request"), *usage = nb_get(row, "usage");
  int64_t begin, end;
  char hash[65];
  double seconds;
  if (!json_object_is_type(request, json_type_object) ||
      !nb_json_hash(request, hash) ||
      strcmp(hash, nb_string(row, "request_sha256")) ||
      !nb_count(request, "max_tokens", budget, budget, NULL) ||
      !true_value(row, "stream_complete") ||
      !nb_count(usage, "prompt_tokens", 1, 1048576, &out->prompt) ||
      !nb_count(usage, "completion_tokens", budget, budget, &out->output) ||
      !nb_count(usage, "total_tokens", out->prompt + out->output,
                out->prompt + out->output, NULL) ||
      !nb_count(row, "cached_tokens", 0, out->prompt, &out->cached) ||
      !true_value(row, "full_output_budget") ||
      !nb_count(row, "started_ns", 1, INT64_MAX - 1, &begin) ||
      !nb_count(row, "finished_ns", begin + 1, INT64_MAX, &end) ||
      !real_value(row, "wall_seconds", 0, 7201, &seconds) ||
      !close_value(seconds, (end - begin) / 1e9) ||
      !real_value(row, "first_output_seconds", 0, seconds, &out->ttft))
    return nb_fail(e,
                   "Incomplete HTTP cohort usage, request or timing witness");
  out->wall = seconds;
  int64_t usage_cached = 0;
  json_object *details = nb_get(usage, "prompt_tokens_details");
  if ((details &&
       !nb_count(details, "cached_tokens", 0, out->prompt, &usage_cached)) ||
      usage_cached != out->cached)
    return nb_fail(e, "HTTP usage cache count disagrees with observation");
  double declared;
  if (!real_value(row, "prompt_over_wall_tps", 0, 1e30, &declared) ||
      !close_value(declared, out->prompt / seconds) ||
      !real_value(row, "output_over_wall_tps", 0, 1e30, &declared) ||
      !close_value(declared, out->output / seconds))
    return nb_fail(e, "HTTP cohort wall-rate accounting mismatch");
  if (!json_object_is_type(nb_get(row, "assistant"), json_type_object) ||
      !json_object_is_type(nb_get(nb_get(row, "assistant"), "content"),
                           json_type_string))
    return nb_fail(e, "HTTP cohort output witness missing");
  json_object *timing = nb_get(row, "server_timings"),
              *gufo = nb_get(usage, "gufo");
  if (timing) {
    if (!nb_http_timing_contract(timing, out->prompt, out->output, out->cached,
                                 e))
      return false;
    out->source = "lie";
    out->prefill = nb_number(timing, "prefill_tokens");
  } else if (gufo) {
    timing = gufo;
    out->source = "gufo";
    if (!nb_count(timing, "prefill_tokens", 0, out->prompt, &out->prefill) ||
        out->prefill != out->prompt - out->cached)
      return nb_fail(e, "Gufo executed prefill/cache counts disagree");
  } else
    return nb_fail(e, "Qualified LIE or Gufo server phase timings required; no "
                      "wall-rate fallback");
  if (!real_value(timing, "prefill_ms", 0, seconds * 1000 + 1e-3,
                  &out->pp_ms) ||
      !real_value(timing, "decode_ms", 0, seconds * 1000 + 1e-3, &out->tg_ms) ||
      out->tg_ms <= 0 || (out->prefill && out->pp_ms <= 0) ||
      out->pp_ms + out->tg_ms > seconds * 1000 + 1e-3)
    return nb_fail(e, "Executed HTTP phases have invalid durations");
  if (!isfinite(out->output * 1000 / out->tg_ms) ||
      (out->prefill && !isfinite(out->prefill * 1000 / out->pp_ms)))
    return nb_fail(e, "HTTP cohort server phase rate overflow");
  return true;
}
/* Recompute from individual observations rather than trusting an aggregate. */
static json_object *cohort_values(json_object *row, json_object *item,
                                  unsigned users, unsigned output,
                                  unsigned context, nb_error *e) {
  json_object *prep = nb_get(row, "preparations"),
              *jobs = nb_get(row, "requests");
  if (!json_object_is_type(prep, json_type_array) ||
      json_object_array_length(prep) != users ||
      !json_object_is_type(jobs, json_type_array) ||
      json_object_array_length(jobs) != users) {
    nb_fail(e, "Missing prepared cohort participants");
    return NULL;
  }
  uint64_t prepare_begin = 0, prepare_end = 0, begin = 0, end = 0;
  double sum = 0, ttft = 0, pp = 0;
  unsigned pp_count = 0;
  int64_t total = 0, executed = 0;
  const char *source = NULL;
  json_object *hashes = json_object_new_array(),
              *prompt = json_object_new_array();
  json_object *point = json_object_new_object();
  json_object_object_add(point, "output_hashes", hashes);
  json_object_object_add(point, "prompt_tokens", prompt);
  for (unsigned i = 0; i < users; ++i) {
    json_object *p = json_object_array_get_idx(prep, i),
                *r = json_object_array_get_idx(jobs, i);
    observation a = {0}, b = {0};
    if (!observe(p, 1, &a, e) || !observe(r, output, &b, e))
      goto bad;
    if (a.prompt != b.prompt || b.cached < b.prompt - 4 || b.prefill > 4 ||
        (context && (uint64_t)b.prompt + output > context) ||
        (nb_get(item, "expected_prompt_tokens") &&
         b.prompt != nb_number(item, "expected_prompt_tokens")) ||
        !nb_same(p, r, "client_id") ||
        !json_object_is_type(nb_get(p, "client_id"), json_type_string) ||
        !strcmp(nb_string(p, "client_id"), "") || strcmp(a.source, b.source) ||
        (source && strcmp(source, b.source))) {
      nb_fail(e,
              "Prepared prefix was not reused or participant identity changed");
      goto bad;
    }
    source = b.source;
    for (unsigned j = 0; j < i; ++j)
      if (nb_same(r, json_object_array_get_idx(jobs, j), "client_id")) {
        nb_fail(e, "Duplicate cohort session ID");
        goto bad;
      }
    json_object *prepared_body = nb_copy(nb_get(p, "request")),
                *measured_body = nb_get(r, "request");
    nb_num(prepared_body, "max_tokens", output);
    bool identical = json_object_equal(prepared_body, measured_body) &&
                     json_object_equal(measured_body, nb_get(item, "body"));
    json_object_put(prepared_body);
    if (!identical) {
      nb_fail(e, "Prepared and measured HTTP payloads differ");
      goto bad;
    }
    uint64_t ps = (uint64_t)nb_number(p, "started_ns"),
             pe = (uint64_t)nb_number(p, "finished_ns"),
             rs = (uint64_t)nb_number(r, "started_ns"),
             re = (uint64_t)nb_number(r, "finished_ns");
    if (i && (ps != prepare_begin || rs != begin)) {
      nb_fail(e, "HTTP cohort did not share a client start gate");
      goto bad;
    }
    prepare_begin = ps;
    begin = rs;
    if (pe > prepare_end)
      prepare_end = pe;
    if (re > end)
      end = re;
    sum += b.output * 1000 / b.tg_ms;
    ttft += b.ttft;
    total += b.output;
    executed += a.prefill;
    if (a.prefill) {
      pp += a.prefill * 1000 / a.pp_ms;
      ++pp_count;
    }
    char hash[65];
    if (!nb_json_hash(nb_get(r, "assistant"), hash)) {
      nb_fail(e, "Output hash failed");
      goto bad;
    }
    json_object_array_add(hashes, json_object_new_string(hash));
    json_object_array_add(prompt, json_object_new_int64(b.prompt));
  }
  if (prepare_end > begin || prepare_end <= prepare_begin || end <= begin) {
    nb_fail(e, "Measured decode started before all preparations completed");
    goto bad;
  }
  nb_real(point, "sum_request_decode_tps", sum);
  nb_real(point, "aggregate_output_tps", total * 1e9 / (end - begin));
  nb_real(point, "first_output_seconds", ttft / users);
  nb_real(point, "preparation_wall_seconds",
          (prepare_end - prepare_begin) / 1e9);
  nb_real(point, "measured_wall_seconds", (end - begin) / 1e9);
  nb_real(point, "executed_preparation_pp_tps", pp_count ? pp / pp_count : NAN);
  nb_num(point, "preparation_prefill_tokens", executed);
  nb_str(point, "timing_source", source);
  return point;
bad:
  json_object_put(point);
  return NULL;
}
static const char *metrics[] = {
    "sum_request_decode_tps",    "aggregate_output_tps",
    "first_output_seconds",      "preparation_wall_seconds",
    "measured_wall_seconds",     "executed_preparation_pp_tps",
    "preparation_prefill_tokens"};
json_object *nb_http_multi_summary(json_object *rows, nb_error *e) {
  size_t n = json_object_array_length(rows);
  json_object *out = NULL, *points = NULL;
  if (n < 3) {
    nb_fail(e, "Incomplete HTTP multi evidence");
    return NULL;
  }
  json_object *id = json_object_array_get_idx(rows, 0),
              *last = json_object_array_get_idx(rows, n - 1);
  json_object *cases = nb_get(id, "cases"), *users = nb_get(id, "users");
  int64_t warm, reps, output, context;
  if (!eq(id, "event", "identity") || !eq(id, "schema", MULTI_SCHEMA) ||
      !eq(last, "event", "complete") ||
      !nb_count(last, "exit_code", 0, 0, NULL) ||
      !eq(id, "cache_policy", "on") ||
      !eq(id, "client_execution", "curl-multi-single-event-loop") ||
      !eq(id, "decode_metric", "sum of individual server decode rates") ||
      !nb_count(id, "preparation_output_tokens", 1, 1, NULL) ||
      !nb_count(id, "max_replayed_prompt_tokens", 4, 4, NULL) ||
      !nb_count(id, "warmups", 0, 10, &warm) ||
      !nb_count(id, "repetitions", 1, 100, &reps) ||
      !nb_count(id, "output_limit", 1, 4096, &output) ||
      !nb_count(id, "context_capacity_declared", 128, 1048576, &context) ||
      !json_object_is_type(cases, json_type_array) ||
      !json_object_array_length(cases) ||
      json_object_array_length(cases) > 16 ||
      !json_object_is_type(users, json_type_array) ||
      !json_object_array_length(users) || json_object_array_length(users) > 8 ||
      n - 2 != json_object_array_length(cases) *
                   json_object_array_length(users) * (size_t)(warm + reps)) {
    nb_fail(e, "Invalid HTTP multi identity or missing cohorts");
    return NULL;
  }
  out = json_object_new_object();
  points = json_object_new_array();
  nb_add(out, "identity", id);
  json_object_object_add(out, "configurations", points);
  for (size_t c = 0; c < json_object_array_length(cases); ++c) {
    json_object *item = json_object_array_get_idx(cases, c);
    const char *name = nb_string(item, "id");
    if (!*name || strlen(name) > 128 ||
        (nb_get(item, "expected_prompt_tokens") &&
         !nb_count(item, "expected_prompt_tokens", 1, context - output,
                   NULL))) {
      nb_fail(e, "Invalid HTTP corpus ID");
      goto bad;
    }
    json_object *normalized = payload(
        nb_get(item, "body"), nb_string(id, "model"), (unsigned)output, e);
    bool controls = normalized && *nb_string(id, "model") &&
                    json_object_equal(normalized, nb_get(item, "body"));
    json_object_put(normalized);
    if (!controls) {
      nb_fail(e, "HTTP corpus does not match declared greedy controls");
      goto bad;
    }
    for (size_t j = 0; j < c; ++j)
      if (eq(json_object_array_get_idx(cases, j), "id", name)) {
        nb_fail(e, "Duplicate HTTP corpus ID");
        goto bad;
      }
    for (size_t u = 0; u < json_object_array_length(users); ++u) {
      json_object *uv = json_object_array_get_idx(users, u);
      int64_t count = json_object_get_int64(uv);
      if (!json_object_is_type(uv, json_type_int) || count < 1 || count > 8) {
        nb_fail(e, "Invalid HTTP user count");
        goto bad;
      }
      for (size_t j = 0; j < u; ++j)
        if (json_object_equal(uv, json_object_array_get_idx(users, j))) {
          nb_fail(e, "Duplicate HTTP user count");
          goto bad;
        }
      json_object *point = json_object_new_object(),
                  *outputs = json_object_new_array(),
                  *prompts = json_object_new_array();
      json_object_array_add(points, point);
      nb_str(point, "case", name);
      nb_num(point, "users", count);
      nb_num(point, "samples", reps);
      json_object_object_add(point, "output_hashes", outputs);
      json_object_object_add(point, "prompt_tokens", prompts);
      double values[7][110];
      size_t sizes[7] = {0};
      bool seen[110] = {0};
      const char *timing_source = NULL;
      for (size_t i = 1; i < n - 1; ++i) {
        json_object *row = json_object_array_get_idx(rows, i);
        if (!eq(row, "event", "cohort")) {
          nb_fail(e, "Unexpected HTTP multi record");
          goto bad;
        }
        if (!eq(row, "case", name) || nb_number(row, "users") != count)
          continue;
        int64_t rep;
        if (!nb_count(row, "rep", 0, warm + reps - 1, &rep) || seen[rep] ||
            !json_object_is_type(nb_get(row, "warmup"), json_type_boolean) ||
            json_object_get_boolean(nb_get(row, "warmup")) != (rep < warm)) {
          nb_fail(e, "Duplicate HTTP cohort, invalid repetition or warmup");
          goto bad;
        }
        seen[rep] = true;
        json_object *v = cohort_values(row, item, (unsigned)count,
                                       (unsigned)output, (unsigned)context, e);
        if (!v)
          goto bad;
        if (timing_source &&
            strcmp(timing_source, nb_string(v, "timing_source"))) {
          json_object_put(v);
          nb_fail(e, "Server timing profile changed between cohorts");
          goto bad;
        }
        if (!timing_source) {
          nb_str(point, "timing_source", nb_string(v, "timing_source"));
          timing_source = nb_string(point, "timing_source");
        }
        if (rep >= warm) {
          for (size_t k = 0; k < 7; ++k)
            if (nb_get(v, metrics[k]))
              values[k][sizes[k]++] =
                  json_object_get_double(nb_get(v, metrics[k]));
          /* Canonical repetition order permits independently reordered files.
           */
          json_object_array_put_idx(
              outputs, (size_t)(rep - warm),
              json_object_get(nb_get(v, "output_hashes")));
          json_object_array_put_idx(
              prompts, (size_t)(rep - warm),
              json_object_get(nb_get(v, "prompt_tokens")));
        }
        json_object_put(v);
      }
      for (int64_t i = 0; i < warm + reps; ++i)
        if (!seen[i]) {
          nb_fail(e, "Unbound or missing prepared cohort");
          goto bad;
        }
      for (size_t k = 0; k < 7; ++k)
        json_object_object_add(point, metrics[k],
                               nb_distribution(values[k], sizes[k]));
      json_object_object_add(point, "full_output_budget",
                             json_object_new_boolean(true));
    }
  }
  return out;
bad:
  json_object_put(out);
  return NULL;
}
int nb_http_multi_main(int argc, char **argv) {
  const char *url = NULL, *model = NULL, *corpus = NULL, *output = NULL,
             *label = NULL, *graphs = NULL, *compare = NULL;
  unsigned tg = 128, reps = 3, warm = 1, context = 4096;
  double timeout = 630;
  nb_error error = {0};
  json_object *users = NULL, *cases = NULL, *id = NULL;
  FILE *file = NULL;
  int rc = 2;
  unsigned seen = 0;
  for (int i = 1; i < argc; ++i) {
    const char *key = argv[i];
    if (!strcmp(key, "--help")) {
      puts("Usage: synapse-lie-bench --suite http-multi --url HTTP-BASE/v1 "
           "--model ID\n"
           "  --requests JSONL --server-label NAME --output NEW-JSONL\n"
           "  [--users 1,2,4,6,8] [--tg 128] [--context-capacity 4096]\n"
           "  [--warmups 1] [--repetitions 3] [--timeout SECONDS]\n"
           "  [--graphs DIRECTORY --compare REFERENCE-JSONL]\n"
           "Requires a running authorized server with prefix caching enabled "
           "and enough active slots.\n"
           "Corpus cases contain id and body.messages, optionally "
           "expected_prompt_tokens.\n"
           "Greedy, thinking off. Each session prepares one output token "
           "before the measured cohort.\n"
           "At most four prompt-tail tokens may be replayed; all output "
           "budgets must complete.\n"
           "One native C event loop starts each cohort, with distinct stable "
           "X-Client-ID headers.\n"
           "Reports sum of server request decode rates separately from output "
           "over common HTTP wall.\n"
           "Qualified LIE/Gufo phase timings required; no server configuration "
           "or cache reset.");
      return 0;
    }
    if (i + 1 == argc)
      goto usage;
    const char *value = argv[++i];
    unsigned bit = 0;
    uint64_t n = 0;
    if (!strcmp(key, "--suite")) {
      if (strcmp(value, "http-multi"))
        goto usage;
      bit = 1u;
    } else if (!strcmp(key, "--url")) {
      url = value;
      bit = 2u;
    } else if (!strcmp(key, "--model")) {
      model = value;
      bit = 4u;
    } else if (!strcmp(key, "--requests")) {
      corpus = value;
      bit = 8u;
    } else if (!strcmp(key, "--output")) {
      output = value;
      bit = 16u;
    } else if (!strcmp(key, "--server-label")) {
      label = value;
      bit = 32u;
    } else if (!strcmp(key, "--graphs")) {
      graphs = value;
      bit = 64u;
    } else if (!strcmp(key, "--compare")) {
      compare = value;
      bit = 128u;
    } else if (!strcmp(key, "--users")) {
      if (seen & 256u)
        goto usage;
      users = numbers(value, &error);
      if (!users)
        goto usage;
      bit = 256u;
    } else if (!strcmp(key, "--timeout")) {
      char *end = NULL;
      errno = 0;
      timeout = strtod(value, &end);
      if (errno || end == value || *end || !isfinite(timeout) || timeout <= 0 ||
          timeout > 7200)
        goto usage;
      bit = 512u;
    } else {
      if (!natural(value, 1048576, &n))
        goto usage;
      if (!strcmp(key, "--tg")) {
        if (!n || n > 4096)
          goto usage;
        tg = (unsigned)n;
        bit = 1024u;
      } else if (!strcmp(key, "--context-capacity")) {
        if (n < 128)
          goto usage;
        context = (unsigned)n;
        bit = 2048u;
      } else if (!strcmp(key, "--warmups")) {
        if (n > 10)
          goto usage;
        warm = (unsigned)n;
        bit = 4096u;
      } else if (!strcmp(key, "--repetitions")) {
        if (!n || n > 100)
          goto usage;
        reps = (unsigned)n;
        bit = 8192u;
      } else
        goto usage;
    }
    if (seen & bit)
      goto usage;
    seen |= bit;
  }
  if (!url || !model || !*model || !corpus || !output || !label || !*label ||
      tg >= context || (compare && !graphs))
    goto usage;
  if (!nb_http_url(url, &error)) {
    rc = 1;
    goto end;
  }
  if (!users)
    users = numbers("1,2,4,6,8", &error);
  cases = nb_read(corpus, true, &error);
  if (!cases) {
    rc = 1;
    goto end;
  }
  if (!json_object_array_length(cases) || json_object_array_length(cases) > 16)
    goto usage;
  for (size_t i = 0; i < json_object_array_length(cases); ++i) {
    json_object *item = json_object_array_get_idx(cases, i);
    if (!*nb_string(item, "id") || strlen(nb_string(item, "id")) > 128 ||
        nb_get(item, "followups") ||
        (nb_get(item, "expected_prompt_tokens") &&
         !nb_count(item, "expected_prompt_tokens", 1, context - tg, NULL)))
      goto usage;
    for (size_t j = 0; j < i; ++j)
      if (nb_same(item, json_object_array_get_idx(cases, j), "id"))
        goto usage;
    json_object *body = payload(nb_get(item, "body"), model, tg, &error);
    if (!body)
      goto usage;
    json_object_object_add(item, "body", body);
  }
  file = nb_exclusive(output, &error);
  if (!file) {
    rc = 1;
    goto end;
  }
  id = nb_event("identity");
  nb_str(id, "schema", MULTI_SCHEMA);
  nb_str(id, "url", url);
  nb_str(id, "model", model);
  nb_str(id, "server_label", label);
  nb_str(id, "cache_policy", "on");
  nb_str(id, "client_execution", "curl-multi-single-event-loop");
  nb_add(id, "cases", cases);
  nb_add(id, "users", users);
  nb_num(id, "warmups", warm);
  nb_num(id, "repetitions", reps);
  nb_num(id, "output_limit", tg);
  nb_num(id, "context_capacity_declared", context);
  nb_real(id, "timeout_seconds", timeout);
  nb_num(id, "preparation_output_tokens", 1);
  nb_num(id, "max_replayed_prompt_tokens", 4);
  nb_str(id, "decode_metric", "sum of individual server decode rates");
  nb_str(id, "scope",
         "Prepared HTTP client cohorts; no model open, server control or "
         "performance claim from synthetic fixtures");
  bool ok = nb_emit(file, id);
  struct sigaction handler = {0};
  handler.sa_handler = stop;
  sigemptyset(&handler.sa_mask);
  interrupted = 0;
  if (sigaction(SIGINT, &handler, NULL) || sigaction(SIGTERM, &handler, NULL))
    ok = nb_fail(&error, "Signal handler setup failed");
  uint64_t nonce = nb_now();
  for (size_t c = 0; ok && c < json_object_array_length(cases); ++c)
    for (size_t u = 0; ok && u < json_object_array_length(users); ++u)
      for (unsigned rep = 0; ok && rep < warm + reps; ++rep) {
        unsigned count = (unsigned)json_object_get_int64(
            json_object_array_get_idx(users, u));
        json_object *item = json_object_array_get_idx(cases, c),
                    *bodies = json_object_new_array(),
                    *ids = json_object_new_array();
        for (unsigned i = 0; i < count; ++i) {
          json_object *p = nb_copy(nb_get(item, "body"));
          nb_num(p, "max_tokens", 1);
          json_object_array_add(bodies, p);
          char client[160];
          snprintf(client, sizeof(client),
                   "lie-http-%ld-%" PRIu64 "-c%zu-u%u-r%u-i%u", (long)getpid(),
                   nonce, c, count, rep, i);
          json_object_array_add(ids, json_object_new_string(client));
        }
        json_object *row = nb_event("cohort");
        nb_str(row, "case", nb_string(item, "id"));
        nb_num(row, "users", count);
        nb_num(row, "rep", rep);
        json_object_object_add(row, "warmup",
                               json_object_new_boolean(rep < warm));
        nb_http_options options = {.url = url,
                                   .model = model,
                                   .timeout = timeout,
                                   .stream = true,
                                   .interrupted = &interrupted,
                                   .client_ids = ids};
        bool complete = false;
        json_object *prepared =
            nb_http_cohort(&options, bodies, &complete, &error);
        nb_add(row, "preparations", prepared);
        if (complete)
          for (unsigned i = 0; i < count; ++i) {
            observation preparation = {0};
            if (!observe(json_object_array_get_idx(prepared, i), 1,
                         &preparation, &error)) {
              complete = false;
              break;
            }
          }
        if (complete && !interrupted) {
          for (unsigned i = 0; i < count; ++i)
            nb_num(json_object_array_get_idx(bodies, i), "max_tokens", tg);
          json_object *requests =
              nb_http_cohort(&options, bodies, &complete, &error);
          nb_add(row, "requests", requests);
          json_object_put(requests);
          if (complete) {
            json_object *v =
                cohort_values(row, item, count, tg, context, &error);
            complete = v != NULL;
            json_object_put(v);
          }
        } else
          complete = false;
        if (!complete)
          nb_str(row, "error",
                 error.message[0] ? error.message : "HTTP multi interrupted");
        ok = complete && nb_emit(file, row);
        /* Preserve incomplete participants even when the cohort cannot qualify.
         */
        if (!complete)
          (void)nb_emit(file, row);
        json_object_put(row);
        json_object_put(prepared);
        json_object_put(bodies);
        json_object_put(ids);
      }
  json_object *last = nb_event(ok ? "complete" : "failed");
  nb_num(last, "exit_code", ok ? 0 : 1);
  if (!ok)
    nb_str(last, "error",
           error.message[0] ? error.message
                            : "HTTP cohort evidence write failed");
  bool written = nb_emit(file, last);
  json_object_put(last);
  if (fclose(file))
    written = false;
  file = NULL;
  rc = ok && written ? 0 : 1;
  if (!rc && graphs)
    rc = nb_report(output, graphs, label, compare, "Gufo reference", false,
                   &error);
  goto end;
usage:
  nb_fail(&error, "Invalid HTTP multi options; use --suite http-multi --help");
end:
  if (file)
    fclose(file);
  json_object_put(id);
  json_object_put(cases);
  json_object_put(users);
  if (rc)
    fprintf(stderr, "%s\n",
            error.message[0] ? error.message : "HTTP multi failed");
  return rc;
}
static json_object *find_point(json_object *points, json_object *point) {
  for (size_t i = 0; i < json_object_array_length(points); ++i) {
    json_object *p = json_object_array_get_idx(points, i);
    if (nb_same(p, point, "case") && nb_same(p, point, "users"))
      return p;
  }
  return NULL;
}
static void csv_text(FILE *file, const char *text) {
  fputc('"', file);
  for (; *text; ++text) {
    if (*text == '"')
      fputc('"', file);
    fputc(*text, file);
  }
  fputc('"', file);
}
int nb_http_multi_export(json_object *a, json_object *b, const char *directory,
                         const char *label, const char *reference_label,
                         nb_error *e) {
  json_object *ai = nb_get(a, "identity"), *ap = nb_get(a, "configurations"),
              *bp = nb_get(b, "configurations");
  json_object *summary = json_object_new_object(),
              *checks = json_object_new_array();
  int rc = 1;
  nb_add(summary, "primary", a);
  nb_add(summary, "reference", b);
  nb_add(summary, "comparison", checks);
  if (b) {
    json_object *bi = nb_get(b, "identity");
    const char *keys[] = {"schema",
                          "model",
                          "cache_policy",
                          "output_limit",
                          "context_capacity_declared",
                          "warmups",
                          "repetitions",
                          "preparation_output_tokens",
                          "max_replayed_prompt_tokens"};
    for (size_t k = 0; k < sizeof(keys) / sizeof(*keys); ++k)
      if (!nb_same(ai, bi, keys[k])) {
        nb_fail(e, "HTTP multi comparison declarations differ");
        goto end;
      }
    if (json_object_array_length(ap) != json_object_array_length(bp)) {
      nb_fail(e, "HTTP multi comparison point count differs");
      goto end;
    }
    for (size_t i = 0; i < json_object_array_length(ap); ++i) {
      json_object *p = json_object_array_get_idx(ap, i), *q = find_point(bp, p);
      json_object *case_a = NULL, *case_b = NULL, *ca = nb_get(ai, "cases"),
                  *cb = nb_get(bi, "cases");
      for (size_t c = 0; c < json_object_array_length(ca); ++c)
        if (eq(json_object_array_get_idx(ca, c), "id", nb_string(p, "case")))
          case_a = json_object_array_get_idx(ca, c);
      for (size_t c = 0; c < json_object_array_length(cb); ++c)
        if (eq(json_object_array_get_idx(cb, c), "id", nb_string(p, "case")))
          case_b = json_object_array_get_idx(cb, c);
      if (!q || !case_a || !case_b || !nb_same(case_a, case_b, "body") ||
          !nb_same(p, q, "prompt_tokens")) {
        nb_fail(
            e,
            "HTTP multi comparison payload or physical prompt counts differ");
        goto end;
      }
      json_object *r = json_object_new_object();
      nb_str(r, "case", nb_string(p, "case"));
      nb_add(r, "users", nb_get(p, "users"));
      bool equal = nb_same(p, q, "output_hashes");
      json_object_object_add(r, "output_equal", json_object_new_boolean(equal));
      json_object_object_add(r, "eligible", json_object_new_boolean(equal));
      nb_add(r, "primary_timing_source", nb_get(p, "timing_source"));
      nb_add(r, "reference_timing_source", nb_get(q, "timing_source"));
      double denominator =
          json_object_get_double(nb_get(nb_get(q, metrics[0]), "median"));
      nb_real(r, "sum_request_decode_ratio",
              equal && denominator > 0 ? json_object_get_double(nb_get(
                                             nb_get(p, metrics[0]), "median")) /
                                             denominator
                                       : NAN);
      json_object_array_add(checks, r);
    }
  }
  if (!nb_mkdir(directory, e))
    goto end;
  char path[4096];
  if (snprintf(path, sizeof(path), "%s/summary.json", directory) >=
      (int)sizeof(path)) {
    nb_fail(e, "Report path too long");
    goto end;
  }
  if (!nb_write_json(path, summary, e))
    goto end;
  snprintf(path, sizeof(path), "%s/summary.csv", directory);
  FILE *file = nb_exclusive(path, e);
  if (!file)
    goto end;
  fputs("label,case,users,samples,timing_source,metric,n,median,min,max\n",
        file);
  json_object *datasets[] = {a, b};
  const char *labels[] = {label, reference_label};
  for (unsigned s = 0; s < (b ? 2u : 1u); ++s) {
    json_object *points = nb_get(datasets[s], "configurations");
    for (size_t i = 0; i < json_object_array_length(points); ++i) {
      json_object *point = json_object_array_get_idx(points, i);
      for (size_t k = 0; k < 7; ++k) {
        csv_text(file, labels[s]);
        fputc(',', file);
        csv_text(file, nb_string(point, "case"));
        fprintf(file, ",%" PRId64 ",%" PRId64 ",", nb_number(point, "users"),
                nb_number(point, "samples"));
        csv_text(file, nb_string(point, "timing_source"));
        fputc(',', file);
        csv_text(file, metrics[k]);
        json_object *value = nb_get(point, metrics[k]);
        const char *keys[] = {"n", "median", "min", "max"};
        for (unsigned j = 0; j < 4; ++j) {
          fputc(',', file);
          json_object *v = nb_get(value, keys[j]);
          if (v)
            fputs(nb_encoded(v), file);
        }
        fputc('\n', file);
      }
    }
  }
  bool written = !ferror(file);
  if (fclose(file))
    written = false;
  if (!written) {
    nb_fail(e, "HTTP multi CSV write failed");
    goto end;
  }
  nb_plot_panel panels[4] = {0};
  const char *titles[] = {"Executed preparation prefill (per request)",
                          "Sum of individual server decode rates",
                          "Output / common complete HTTP wall",
                          "Mean request first output"};
  const char *units[] = {"executed tokens/s; cache hits unavailable",
                         "output tokens/s", "output tokens/s", "seconds"};
  const size_t indices[] = {5, 0, 1, 2};
  json_object *cases = nb_get(ai, "cases");
  bool one_case = json_object_array_length(cases) == 1;
  bool plotted = true;
  for (unsigned p = 0; p < 4 && plotted; ++p) {
    panels[p].title = titles[p];
    panels[p].unit = units[p];
    panels[p].x_label = one_case ? "Concurrent users"
                                 : "Case index / concurrent users (see CSV)";
    panels[p].count = b ? 2 : 1;
    for (unsigned s = 0; s < panels[p].count && plotted; ++s) {
      size_t count = json_object_array_length(ap);
      nb_plot_series *series = &panels[p].series[s];
      series->label = labels[s];
      series->count = count;
      series->ticks = calloc(count, sizeof(*series->ticks));
      series->median = malloc(count * sizeof(double));
      series->low = malloc(count * sizeof(double));
      series->high = malloc(count * sizeof(double));
      if (!series->ticks || !series->median || !series->low || !series->high) {
        plotted = false;
        break;
      }
      for (size_t i = 0; i < count; ++i) {
        json_object *primary = json_object_array_get_idx(ap, i),
                    *point = s ? find_point(bp, primary) : primary;
        char tick[128];
        if (one_case)
          snprintf(tick, sizeof(tick), "C%" PRId64, nb_number(point, "users"));
        else {
          size_t case_index = 0;
          while (case_index < json_object_array_length(cases) &&
                 !eq(json_object_array_get_idx(cases, case_index), "id",
                     nb_string(point, "case")))
            ++case_index;
          snprintf(tick, sizeof(tick), "%zu / C%" PRId64, case_index + 1,
                   nb_number(point, "users"));
        }
        series->ticks[i] = strdup(tick);
        if (!series->ticks[i]) {
          plotted = false;
          break;
        }
        json_object *m = nb_get(point, metrics[indices[p]]);
        series->median[i] =
            m ? json_object_get_double(nb_get(m, "median")) : NAN;
        series->low[i] = m ? json_object_get_double(nb_get(m, "min")) : NAN;
        series->high[i] = m ? json_object_get_double(nb_get(m, "max")) : NAN;
      }
    }
  }
  if (plotted) {
    char title[160];
    if (one_case)
      snprintf(title, sizeof(title), "Prepared HTTP cohorts - %.48s",
               nb_string(json_object_array_get_idx(cases, 0), "id"));
    else
      snprintf(title, sizeof(title),
               "Prepared HTTP cohorts - recorded server timings");
    plotted = nb_plot(directory, title, panels, 4, e);
  }
  for (unsigned p = 0; p < 4; ++p)
    for (unsigned s = 0; s < panels[p].count; ++s) {
      nb_plot_series *v = &panels[p].series[s];
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
    nb_fail(e, "HTTP multi graph allocation failed");
end:
  json_object_put(summary);
  json_object_put(checks);
  return rc;
}
