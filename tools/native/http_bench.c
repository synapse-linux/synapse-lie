/* SPDX-License-Identifier: MIT */
#include "bench_native.h"
#include <errno.h>
#include <inttypes.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

static const char pad[] = "The maintenance team documented the inspection and "
                          "scheduled additional measurements.\n";
static const struct {
  const char *id, *prompt;
} shapes[] = {
    {"prose",
     "Write a long account of a lighthouse keeper recording a winter storm."},
    {"code", "Implement a bounded FIFO queue in C17 and explain ownership and "
             "error handling."},
    {"proof", "Prove by induction the formula for the sum of the first n "
              "squares, explaining every step."},
    {"chat", "Help a volunteer team plan a community garden; discuss choices "
             "and responsibilities."},
    {"analysis", "Compare centralized and distributed inventory systems with "
                 "concrete failure examples."},
    {"structured", "Produce a JSON array of 30 fictional weather station "
                   "readings with name, temperature and notes."},
    {"translation", "Translate and explain this sentence in ten languages: The "
                    "train reaches the mountain village before noon."},
    {"debug", "Diagnose a C program that retains pointers into a reallocating "
              "array; give a corrected implementation."},
    {"review", "Review a design that retries every failed database transaction "
               "forever; propose bounded recovery."},
    {"tool-dialogue",
     "After reading a configuration with timeout=20 and retries=3, explain a "
     "careful change to timeout=30 and its verification."}};
typedef struct {
  const char *url, *model, *output, *label, *requests, *preset, *sizes, *cache,
      *rope, *options_path, *export_path, *graphs, *compare;
  unsigned tg, context, reps, warmups, turns;
  uint64_t seed;
  double timeout;
  bool long_context;
  json_object *options, *targets;
  FILE *file;
  nb_error error;
} config;
static bool integer(const char *s, uint64_t max, uint64_t *out) {
  if (!*s)
    return false;
  uint64_t n = 0;
  for (; *s; s++) {
    if (*s < '0' || *s > '9' || n > (max - (unsigned)(*s - '0')) / 10)
      return false;
    n = n * 10 + (unsigned)(*s - '0');
  }
  *out = n;
  return true;
}
static json_object *message(const char *role, const char *text) {
  json_object *o = json_object_new_object();
  nb_str(o, "role", role);
  nb_str(o, "content", text);
  return o;
}
static json_object *single_message(const char *text) {
  json_object *a = json_object_new_array();
  json_object_array_add(a, message("user", text));
  return a;
}
static void merge(json_object *a, json_object *b) {
  json_object_object_foreach(b, k, v) {
    json_object_object_add(a, k, nb_copy(v));
  }
}
static json_object *body(config *c, json_object *supplied) {
  if (!json_object_is_type(supplied, json_type_object)) {
    nb_fail(&c->error, "Request body must be an object");
    return NULL;
  }
  json_object *o = json_object_new_object();
  nb_str(o, "model", c->model);
  nb_num(o, "temperature", 0);
  nb_num(o, "max_tokens", c->tg);
  merge(o, c->options);
  merge(o, supplied);
  nb_str(o, "model", c->model);
  json_object_object_add(o, "stream", json_object_new_boolean(true));
  json_object *stream = json_object_new_object();
  json_object_object_add(stream, "include_usage",
                         json_object_new_boolean(true));
  json_object_object_add(o, "stream_options", stream);
  json_object *messages = nb_get(o, "messages");
  if (!json_object_is_type(messages, json_type_array) ||
      !json_object_array_length(messages) ||
      !nb_count(o, "max_tokens", 1, 65536, NULL)) {
    json_object_put(o);
    nb_fail(&c->error, "Nonempty messages and bounded output budget required");
    return NULL;
  }
  return o;
}
static bool emit(config *c, json_object *o) {
  bool ok = nb_emit(c->file, o);
  if (!ok)
    nb_fail(&c->error, "Evidence write failed");
  return ok;
}
static json_object *request(config *c, json_object *o) {
  nb_http_options options = {
      .url = c->url, .model = c->model, .timeout = c->timeout, .stream = true};
  return nb_http_request(&options, o, &c->error);
}
static char *notes(config *c, unsigned count) {
  const char
      *head = c->long_context ? "Read the following numeric records.\n"
                              : "Read these maintenance notes.\n",
      *tail = c->long_context
                  ? "\nExplain a detailed validation procedure for these "
                    "records, including duplicate detection and range checks."
                  : "\nReply with exactly READY.";
  size_t unit = c->long_context ? 32 : strlen(pad),
         bytes = strlen(head) + unit * count + strlen(tail);
  if (bytes > 8 * 1024 * 1024) {
    nb_fail(&c->error, "Generated prompt exceeds HTTP body budget");
    return NULL;
  }
  char *text = malloc(bytes + 1);
  if (!text)
    return NULL;
  strcpy(text, head);
  char *at = text + strlen(head);
  for (unsigned i = 0; i < count; i++) {
    if (!c->long_context) {
      memcpy(at, pad, unit);
      at += unit;
    } else {
      char input[128], hash[65];
      snprintf(input, sizeof(input), "lie-long-context-v1:%" PRIu64 ":%u",
               c->seed, i);
      if (!nb_hash(input, strlen(input), hash)) {
        free(text);
        return NULL;
      }
      for (unsigned k = 0; k < 8; k++) {
        char part[7];
        memcpy(part, hash + 6 * k, 6);
        part[6] = 0;
        unsigned n = (unsigned)strtoul(part, NULL, 16) % 1000;
        snprintf(at, 5, "%03u%c", n, k == 7 ? '\n' : ' ');
        at += 4;
      }
    }
  }
  strcpy(at, tail);
  return text;
}
static json_object *with_messages(config *c, unsigned count, unsigned budget) {
  char *text = notes(c, count);
  if (!text)
    return NULL;
  json_object *o = json_object_new_object();
  json_object_object_add(o, "messages", single_message(text));
  nb_num(o, "max_tokens", budget);
  free(text);
  return o;
}
static json_object *cases(config *c) {
  if (c->requests) {
    json_object *a = nb_read(c->requests, true, &c->error);
    if (a &&
        (!json_object_array_length(a) || json_object_array_length(a) > 256)) {
      json_object_put(a);
      a = NULL;
      nb_fail(&c->error, "Expected 1..256 request cases");
    }
    return a;
  }
  json_object *a = json_object_new_array();
  if (!strcmp(c->preset, "decode")) {
    for (size_t i = 0; i < sizeof(shapes) / sizeof(shapes[0]); i++) {
      char text[512];
      snprintf(text, sizeof(text), "%s Give a substantial detailed answer.",
               shapes[i].prompt);
      json_object *item = json_object_new_object(),
                  *o = json_object_new_object();
      nb_str(item, "id", shapes[i].id);
      json_object_object_add(o, "messages", single_message(text));
      nb_num(o, "max_tokens", c->tg);
      json_object_object_add(item, "body", o);
      json_object_array_add(a, item);
    }
    return a;
  }
  int64_t counts[3];
  unsigned probes[3] = {c->long_context ? 8 : 0, c->long_context ? 16 : 8,
                        c->long_context ? 32 : 16};
  for (unsigned i = 0; i < 3; i++) {
    json_object *supplied = with_messages(c, probes[i], 1),
                *o = supplied ? body(c, supplied) : NULL;
    json_object_put(supplied);
    if (!o)
      goto fail;
    json_object *r = request(c, o);
    json_object_put(o);
    if (!r)
      goto fail;
    nb_str(r, "event", "calibration");
    nb_num(r, "lines", probes[i]);
    bool ok = emit(c, r);
    counts[i] = nb_number(nb_get(r, "usage"), "prompt_tokens");
    json_object_put(r);
    if (!ok)
      goto fail;
  }
  int64_t step = counts[1] - counts[0], unit = step / 8,
          p0 = counts[0] - (int64_t)probes[0] * unit;
  if (step <= 0 || step % 8 || counts[2] != p0 + probes[2] * unit) {
    nb_fail(&c->error,
            "Nonlinear prompt calibration; supply explicit --requests");
    goto fail;
  }
  size_t targets = !strcmp(c->preset, "conversation")
                       ? 1
                       : json_object_array_length(c->targets);
  for (size_t i = 0; i < targets; i++) {
    int64_t target =
        !strcmp(c->preset, "conversation")
            ? 100000
            : json_object_get_int64(json_object_array_get_idx(c->targets, i));
    if (target <= p0 || (target - p0) / unit > 1048576) {
      nb_fail(&c->error, "Target below rendered template size or too large");
      goto fail;
    }
    unsigned count = (unsigned)((target - p0) / unit);
    json_object *item = json_object_new_object();
    char id[80];
    snprintf(id, sizeof(id), "%s-%" PRId64, c->preset, target);
    nb_str(item, "id", id);
    nb_num(item, "target_prompt_tokens", target);
    nb_num(item, "expected_prompt_tokens", p0 + count * unit);
    json_object *o = with_messages(c, count,
                                   c->long_context                 ? c->tg
                                   : !strcmp(c->preset, "prefill") ? 1
                                                                   : 32);
    if (!o) {
      json_object_put(item);
      goto fail;
    }
    json_object_object_add(item, "body", o);
    json_object_array_add(a, item);
    if (c->long_context) {
      json_object *corpus = json_object_new_object();
      nb_str(corpus, "generator", "lie-long-context-v1");
      json_object_object_add(corpus, "seed", json_object_new_uint64(c->seed));
      nb_num(corpus, "records", count);
      nb_str(corpus, "kind",
             "varied numeric text; not a retrieval or quality test");
      json_object_object_add(item, "corpus", corpus);
    }
    if (!strcmp(c->preset, "conversation")) {
      json_object *follow = json_object_new_array();
      unsigned n = 400 / unit ? 400 / unit : 1;
      size_t size = 100 + n * strlen(pad);
      char *s = malloc(size);
      if (!s)
        goto fail;
      for (unsigned turn = 1; turn < c->turns; turn++) {
        strcpy(s, "Additional maintenance notes:\n");
        for (unsigned k = 0; k < n; k++)
          strcat(s, pad);
        snprintf(s + strlen(s), size - strlen(s),
                 "\nConfirm update %u with exactly READY.", turn);
        json_object_array_add(follow, json_object_new_string(s));
      }
      free(s);
      json_object_object_add(item, "followups", follow);
    }
  }
  return a;
fail:
  json_object_put(a);
  return NULL;
}
static bool run(config *c) {
  json_object *a = cases(c);
  if (!a)
    return false;
  bool ok = false;
  for (size_t i = 0; i < json_object_array_length(a); i++) {
    json_object *item = json_object_array_get_idx(a, i);
    const char *id = nb_string(item, "id");
    json_object *follow = nb_get(item, "followups");
    if (!*id || strlen(id) > 256 ||
        (follow && (!json_object_is_type(follow, json_type_array) ||
                    json_object_array_length(follow) > 99))) {
      nb_fail(&c->error, "Invalid case ID or followups");
      goto end;
    }
    for (size_t j = 0; j < i; j++)
      if (!strcmp(id, nb_string(json_object_array_get_idx(a, j), "id"))) {
        nb_fail(&c->error, "Duplicate case IDs");
        goto end;
      }
    json_object *o = body(c, nb_get(item, "body"));
    if (!o)
      goto end;
    json_object_put(o);
    if (follow)
      for (size_t j = 0; j < json_object_array_length(follow); j++)
        if (!json_object_is_type(json_object_array_get_idx(follow, j),
                                 json_type_string)) {
          nb_fail(&c->error, "Followups must be strings");
          goto end;
        }
  }
  if (c->export_path) {
    FILE *f = nb_exclusive(c->export_path, &c->error);
    if (!f)
      goto end;
    bool written = true;
    for (size_t i = 0; written && i < json_object_array_length(a); i++)
      written = nb_emit(f, json_object_array_get_idx(a, i));
    if (fclose(f))
      written = false;
    if (!written) {
      nb_fail(&c->error, "Corpus export failed");
      goto end;
    }
  }
  for (size_t i = 0; i < json_object_array_length(a); i++) {
    json_object *item = json_object_array_get_idx(a, i),
                *follow = nb_get(item, "followups");
    size_t turns = follow ? json_object_array_length(follow) + 1 : 1;
    for (unsigned rep = 0; rep < c->warmups + c->reps; rep++) {
      json_object *o = body(c, nb_get(item, "body"));
      if (!o)
        goto end;
      for (size_t turn = 0; turn < turns; turn++) {
        json_object *r = request(c, o);
        if (!r) {
          json_object_put(o);
          goto end;
        }
        nb_str(r, "event", "sample");
        nb_str(r, "case", nb_string(item, "id"));
        nb_num(r, "turn", (int64_t)turn);
        nb_num(r, "rep", rep);
        json_object_object_add(r, "warmup",
                               json_object_new_boolean(rep < c->warmups));
        nb_add(r, "target_prompt_tokens",
               turn ? NULL : nb_get(item, "target_prompt_tokens"));
        nb_add(r, "corpus", nb_get(item, "corpus"));
        bool valid = emit(c, r);
        int64_t pp = nb_number(nb_get(r, "usage"), "prompt_tokens");
        if (!turn && nb_get(item, "expected_prompt_tokens") &&
            pp != nb_number(item, "expected_prompt_tokens"))
          valid = nb_fail(&c->error, "Physical prompt calibration changed");
        if (c->context &&
            (uint64_t)pp + nb_number(o, "max_tokens") > c->context)
          valid = nb_fail(&c->error, "Actual prompt plus output budget exceeds "
                                     "declared context capacity");
        if (valid && turn + 1 < turns) {
          json_object *assistant = nb_get(r, "assistant");
          if (nb_get(assistant, "tool_calls"))
            valid = nb_fail(&c->error, "Automatic tool execution unsupported; "
                                       "supply a static dialogue corpus");
          else {
            json_object *next = nb_copy(o);
            json_object_put(o);
            o = next;
            json_object *messages = nb_get(o, "messages");
            json_object_array_add(messages, nb_copy(assistant));
            json_object_array_add(
                messages,
                message("user", json_object_get_string(
                                    json_object_array_get_idx(follow, turn))));
          }
        }
        json_object_put(r);
        if (!valid) {
          json_object_put(o);
          goto end;
        }
      }
      json_object_put(o);
    }
  }
  ok = true;
end:
  json_object_put(a);
  return ok;
}
int nb_http_main(int argc, char **argv) {
  config c = {.rope = "unknown", .reps = 3, .turns = 20};
  int rc = 2;
  for (int i = 1; i < argc; i++) {
    const char *k = argv[i];
    if (!strcmp(k, "--help")) {
      puts("Usage: synapse-lie-bench --suite http --url HTTP-BASE/v1 --model "
           "ID --output NEW-JSONL\n  --server-label ID --server-kv-cache "
           "off|on|unknown (--preset prefill|decode|conversation|long-context "
           "| --requests JSONL)\n  [--sizes TOKENS,...] [--tg N] [--warmups 0] "
           "[--repetitions 3] [--turns 20]\n  [--context-capacity N "
           "--rope-scaling native|yarn2|yarn4] [--corpus-seed N]\n  "
           "[--request-options JSON] [--export-requests NEW-JSONL] [--timeout "
           "SECONDS]\n  [--graphs DIRECTORY --compare REFERENCE-JSONL]\nNative "
           "C HTTP client; requires a running server. Actual usage and "
           "complete SSE evidence.\nCache/context/RoPE values are operator "
           "declarations, not server configuration.\n--cache-policy is a "
           "legacy alias of --server-kv-cache. No model, tool execution or "
           "implicit cache reset.");
      return 0;
    }
    if (i + 1 == argc)
      goto usage;
    const char *v = argv[++i];
    uint64_t n = 0;
    if (!strcmp(k, "--suite")) {
      if (strcmp(v, "http"))
        goto usage;
    }
#define OPT(name, member) else if (!strcmp(k, name)) c.member = v
    OPT("--url", url);
    OPT("--model", model);
    OPT("--output", output);
    OPT("--server-label", label);
    OPT("--requests", requests);
    OPT("--preset", preset);
    OPT("--sizes", sizes);
    OPT("--server-kv-cache", cache);
    OPT("--cache-policy", cache);
    OPT("--rope-scaling", rope);
    OPT("--request-options", options_path);
    OPT("--export-requests", export_path);
    OPT("--graphs", graphs);
    OPT("--compare", compare);
#undef OPT
    else if (!strcmp(k, "--timeout")) {
      char *end = NULL;
      errno = 0;
      c.timeout = strtod(v, &end);
      if (errno || end == v || *end || !isfinite(c.timeout) || c.timeout <= 0 ||
          c.timeout > 7200)
        goto usage;
    }
    else if (!strcmp(k, "--corpus-seed")) {
      if (!integer(v, UINT64_MAX, &c.seed))
        goto usage;
    }
    else {
      if (!integer(v, 1048576, &n))
        goto usage;
      if (!strcmp(k, "--tg")) {
        if (!n || n > 65536)
          goto usage;
        c.tg = (unsigned)n;
      } else if (!strcmp(k, "--context-capacity")) {
        if (n < 128)
          goto usage;
        c.context = (unsigned)n;
      } else if (!strcmp(k, "--repetitions")) {
        if (!n || n > 100)
          goto usage;
        c.reps = (unsigned)n;
      } else if (!strcmp(k, "--warmups")) {
        if (n > 10)
          goto usage;
        c.warmups = (unsigned)n;
      } else if (!strcmp(k, "--turns")) {
        if (!n || n > 100)
          goto usage;
        c.turns = (unsigned)n;
      } else
        goto usage;
    }
  }
  if (!c.url || !c.model || !*c.model || !c.output || !c.label || !*c.label ||
      !c.cache || ((c.requests != NULL) == (c.preset != NULL)) ||
      (strcmp(c.cache, "off") && strcmp(c.cache, "on") &&
       strcmp(c.cache, "unknown")) ||
      (strcmp(c.rope, "unknown") && strcmp(c.rope, "native") &&
       strcmp(c.rope, "yarn2") && strcmp(c.rope, "yarn4")) ||
      (c.compare && !c.graphs))
    goto usage;
  if (c.preset && strcmp(c.preset, "prefill") && strcmp(c.preset, "decode") &&
      strcmp(c.preset, "conversation") && strcmp(c.preset, "long-context"))
    goto usage;
  c.long_context = c.preset && !strcmp(c.preset, "long-context");
  if (!c.tg)
    c.tg = c.long_context ? 64 : 256;
  if (!c.timeout)
    c.timeout = c.long_context ? 3600 : 630;
  if (c.long_context &&
      (!c.context || !strcmp(c.rope, "unknown") || strcmp(c.cache, "off")))
    goto usage;
  if (!nb_http_url(c.url, &c.error))
    goto end;
  c.targets = json_object_new_array();
  char *sizes = strdup(c.sizes          ? c.sizes
                       : c.long_context ? "258794,524288,786432,1004581"
                                        : "8192,32768,131072,258794");
  if (!sizes)
    goto end;
  char *at = sizes;
  bool sizes_ok = true;
  for (;;) {
    char *next = strchr(at, ',');
    if (next)
      *next = 0;
    uint64_t n;
    if (!integer(at, 1048576, &n) || n < 128 ||
        json_object_array_length(c.targets) >= 32 ||
        (c.long_context && n + c.tg > c.context)) {
      sizes_ok = false;
      break;
    }
    json_object_array_add(c.targets, json_object_new_int64((int64_t)n));
    if (!next)
      break;
    at = next + 1;
  }
  free(sizes);
  if (!sizes_ok)
    goto usage;
  c.options = c.options_path ? nb_read(c.options_path, false, &c.error)
                             : json_object_new_object();
  if (!json_object_is_type(c.options, json_type_object))
    goto usage;
  c.file = nb_exclusive(c.output, &c.error);
  if (!c.file) {
    rc = 1;
    goto end;
  }
  json_object *id = nb_event("identity");
  nb_str(id, "schema", "synapse-lie.http-bench.v1");
  nb_str(id, "url", c.url);
  nb_str(id, "model", c.model);
  nb_str(id, "server_label", c.label);
  nb_str(id, "cache_policy", c.cache);
  nb_num(id, "warmups", c.warmups);
  nb_num(id, "repetitions", c.reps);
  nb_str(id, "preset", c.preset);
  nb_add(id, "request_options", c.options);
  json_object_object_add(id, "context_capacity_declared",
                         c.context ? json_object_new_int64(c.context) : NULL);
  nb_str(id, "rope_scaling_declared", c.rope);
  nb_real(id, "timeout_seconds", c.timeout);
  nb_add(id, "target_prompt_tokens", c.requests ? NULL : c.targets);
  json_object_object_add(id, "corpus_seed",
                         c.long_context ? json_object_new_uint64(c.seed)
                                        : NULL);
  nb_str(id, "scope",
         "Native C HTTP client; no model open, server control, tool execution "
         "or implicit cache reset");
  bool ok = emit(&c, id);
  json_object_put(id);
  if (ok)
    ok = run(&c);
  json_object *complete = nb_event(ok ? "complete" : "failed");
  nb_num(complete, "exit_code", ok ? 0 : 1);
  if (!ok)
    nb_str(complete, "error", c.error.message);
  bool complete_ok = emit(&c, complete);
  json_object_put(complete);
  if (fclose(c.file))
    complete_ok = false;
  c.file = NULL;
  rc = ok && complete_ok ? 0 : 1;
  if (!rc && c.graphs)
    rc = nb_report(c.output, c.graphs, c.label, c.compare, "Reference", false,
                   &c.error);
  goto end;
usage:
  nb_fail(&c.error, "Invalid HTTP workload options; use --suite http --help");
end:
  if (c.file)
    fclose(c.file);
  json_object_put(c.options);
  json_object_put(c.targets);
  if (rc && c.error.message[0])
    fprintf(stderr, "%s\n", c.error.message);
  return rc;
}
