/* SPDX-License-Identifier: MIT */
#include "bench_native.h"
#include <inttypes.h>
#include <limits.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

static bool flag(json_object *o, const char *k) {
  return json_object_get_boolean(nb_get(o, k));
}
static bool eqs(json_object *o, const char *k, const char *v) {
  return !strcmp(nb_string(o, k), v);
}
static bool nonnegative(json_object *o, const char *k) {
  return nb_count(o, k, 0, INT64_MAX, NULL);
}
static void fields(json_object *dst, json_object *src, const char *keys) {
  char *copy = strdup(keys);
  if (!copy)
    return;
  char *save = NULL;
  for (char *k = strtok_r(copy, " ", &save); k; k = strtok_r(NULL, " ", &save))
    nb_add(dst, k, nb_get(src, k));
  free(copy);
}
static json_object *select_rows(json_object *rows, const char *event) {
  json_object *out = json_object_new_array();
  for (size_t i = 0; i < json_object_array_length(rows); i++) {
    json_object *r = json_object_array_get_idx(rows, i);
    if (eqs(r, "event", event))
      json_object_array_add(out, json_object_get(r));
  }
  return out;
}
static json_object *metric(json_object *rows, const char *key, double scale,
                           bool measured) {
  size_t n = json_object_array_length(rows), count = 0;
  double *v = malloc((n + 1) * sizeof(*v));
  if (!v)
    return NULL;
  for (size_t i = 0; i < n; i++) {
    json_object *r = json_object_array_get_idx(rows, i), *x = nb_get(r, key);
    if (x && (!measured || !flag(r, "warmup")))
      v[count++] = json_object_get_double(x) * scale;
  }
  json_object *out = nb_distribution(v, count);
  free(v);
  return out;
}
static bool rate(json_object *r, const char *key, int64_t count,
                 int64_t elapsed) {
  json_object *value = nb_get(r, key);
  double v = json_object_get_double(value),
         expected = count * 1e9 / (double)elapsed;
  return elapsed > 0 &&
         (json_object_is_type(value, json_type_int) ||
          json_object_is_type(value, json_type_double)) &&
         isfinite(v) &&
         fabs(v - expected) <= fmax(fabs(v), fabs(expected)) * 1e-12;
}
static bool ids(json_object *r) {
  json_object *a = nb_get(r, "physical_ids");
  char hash[65];
  return json_object_is_type(a, json_type_array) &&
         nb_count(r, "prompt_tokens", 1, 1048576, NULL) &&
         (int64_t)json_object_array_length(a) ==
             nb_number(r, "prompt_tokens") &&
         nb_ids_hash(a, hash) &&
         !strcmp(hash, nb_string(r, "physical_ids_sha256"));
}
static bool output_ids(json_object *a, int64_t n) {
  char h[65];
  return json_object_is_type(a, json_type_array) &&
         (int64_t)json_object_array_length(a) == n && nb_ids_hash(a, h);
}
static bool repetition_config(json_object *id) {
  return nb_count(id, "warmups", 0, 10, NULL) &&
         nb_count(id, "repetitions", 1, 100, NULL) &&
         nb_count(id, "output_limit", 1, 65536, NULL) &&
         json_object_is_type(nb_get(id, "synthetic"), json_type_boolean);
}
static bool direct_phase_bounds(json_object *id, json_object *row) {
  const char *keys[] = {"sample_begin_monotonic_ns", "sample_begin_wall_time_ns",
                        "prefill_begin_monotonic_ns", "prefill_end_monotonic_ns",
                        "decode_begin_monotonic_ns", "decode_end_monotonic_ns"};
  bool present = false;
  for (size_t i = 0; i < sizeof(keys) / sizeof(*keys); ++i)
    present |= nb_get(row, keys[i]) != NULL;
  if (!present)
    return nb_get(id, "timing_clock") == NULL; /* Retained v1 evidence. */
  if (!eqs(id, "timing_clock", "CLOCK_MONOTONIC"))
    return false;
  for (size_t i = 0; i < sizeof(keys) / sizeof(*keys); ++i)
    if (!nb_count(row, keys[i], 1, INT64_MAX, NULL))
      return false;
  int64_t begin = nb_number(row, keys[0]), pp_begin = nb_number(row, keys[2]),
          pp_end = nb_number(row, keys[3]), tg_begin = nb_number(row, keys[4]),
          tg_end = nb_number(row, keys[5]);
  return begin <= pp_begin && pp_begin < pp_end && pp_end <= tg_begin &&
         tg_begin < tg_end && pp_end - pp_begin == nb_number(row, "prefill_ns") &&
         tg_end - tg_begin == nb_number(row, "decode_ns");
}
#define CHECK(test, message)                                                   \
  do {                                                                         \
    if (!(test)) {                                                             \
      nb_fail(e, message);                                                     \
      goto bad;                                                                \
    }                                                                          \
  } while (0)
static json_object *direct(json_object *rows, nb_error *e) {
  json_object *id = json_object_array_get_idx(rows, 0),
              *out = json_object_new_object(),
              *points = json_object_new_array(),
              *input = select_rows(rows, "input"),
              *samples = select_rows(rows, "sample");
  nb_add(out, "identity", id);
  json_object_object_add(out, "configurations", points);
  json_object_object_add(out, "loading", select_rows(rows, "model_loaded"));
  CHECK(repetition_config(id), "Invalid direct benchmark identity");
  size_t reps =
      (size_t)(nb_number(id, "warmups") + nb_number(id, "repetitions"));
  CHECK(json_object_array_length(samples) ==
            json_object_array_length(input) * reps,
        "Unbound or missing direct samples");
  CHECK(json_object_array_length(input) || eqs(id, "suite", "loading"),
        "No direct workload inputs");
  for (size_t p = 0; p < json_object_array_length(input); p++) {
    json_object *in = json_object_array_get_idx(input, p);
    CHECK(ids(in) && nb_count(in, "users", 1, 8, NULL) &&
              nb_count(in, "depth", 0, 1048576, NULL) &&
              nb_count(in, "context_capacity", 1, 2097152, NULL) &&
              nb_count(in, "point", 0, 65535, NULL),
          "Invalid physical workload");
    CHECK(nb_number(in, "depth") < nb_number(in, "prompt_tokens") &&
              nb_number(in, "prompt_tokens") + nb_number(id, "output_limit") <=
                  nb_number(in, "context_capacity"),
          "Invalid direct context accounting");
    for (size_t j = 0; j < p; j++)
      CHECK(!nb_same(in, json_object_array_get_idx(input, j), "point"),
            "Duplicate direct input point");
    json_object *point = json_object_new_object();
    json_object_array_add(points, point);
    fields(
        point, in,
        "point depth users context_capacity prompt_tokens physical_ids_sha256");
    nb_num(point, "repetitions", nb_number(id, "repetitions"));
    json_object *group = json_object_new_array();
    json_object_object_add(point, "_rows", group);
    for (size_t j = 0; j < json_object_array_length(samples); j++) {
      json_object *r = json_object_array_get_idx(samples, j);
      if (nb_same(r, in, "point"))
        json_object_array_add(group, json_object_get(r));
    }
    CHECK(json_object_array_length(group) == reps,
          "Missing direct repetitions");
    bool full = true;
    json_object *first = json_object_array_get_idx(group, 0);
    for (size_t j = 0; j < reps; j++) {
      json_object *r = json_object_array_get_idx(group, j);
      int64_t users = nb_number(in, "users"),
              pp = nb_number(in, "prompt_tokens") - nb_number(in, "depth"),
              tg = nb_number(r, "output_tokens_per_user");
      CHECK(nb_count(r, "rep", (int64_t)j, (int64_t)j, NULL) &&
                flag(r, "warmup") == ((int64_t)j < nb_number(id, "warmups")) &&
                nb_same(r, in, "depth") && nb_same(r, in, "users") &&
                nb_same(r, in, "prompt_tokens"),
            "Direct workload or warmup drift");
      CHECK(nb_number(r, "cache_tokens") == nb_number(in, "depth") &&
                nb_number(r, "prefill_tokens_per_user") == pp,
            "Fresh/reused prefill accounting");
      CHECK(nb_count(r, "output_tokens_per_user", 0,
                     nb_number(id, "output_limit"), NULL) &&
                nb_number(r, "output_tokens") == users * tg &&
                output_ids(nb_get(r, "output_ids"), tg),
            "Invalid confirmed output count");
      CHECK(flag(r, "full_output_budget") ==
                    (tg == nb_number(id, "output_limit")) &&
                (flag(r, "full_output_budget") || flag(r, "stop")),
            "Short output without EOS");
      CHECK(flag(r, "finite_frontiers") &&
                flag(r, "identical_input_peers_verified"),
            "Unverified numerical frontier or peers");
      CHECK(
          nonnegative(r, "prefill_ns") && nonnegative(r, "decode_ns") &&
              rate(r, "prefill_tps", pp * users, nb_number(r, "prefill_ns")) &&
              rate(r, "decode_tps", tg * users, nb_number(r, "decode_ns")),
          "Invalid direct timing or rate");
      CHECK(direct_phase_bounds(id, r), "Invalid direct monotonic phase bounds");
      if (eqs(id, "execution", "LIE-reactive-ready-batch")) {
        int64_t singles = nb_number(r, "decode_single_calls"),
                batches = nb_number(r, "decode_batches"),
                batch_rows = nb_number(r, "decode_batch_rows");
        CHECK(nonnegative(r, "decode_single_calls") &&
                  nonnegative(r, "decode_batches") &&
                  nonnegative(r, "decode_batch_rows") &&
                  (singles + batches == tg ||
                   singles + batches == tg + flag(r, "stop")) &&
                  (users == 1 ? (!batches && !batch_rows)
                              : (!singles && batch_rows == batches * users)),
              "Invalid confirmed reactive dispatch counts");
      }
      const char *same[] = {"prefill_logits_sha256", "decode_logits_sha256",
                            "output_ids", "output_tokens_per_user", "stop"};
      for (size_t k = 0; k < 5; k++)
        CHECK(nb_same(r, first, same[k]), "Direct repeatability mismatch");
      if (!flag(r, "warmup") && !flag(r, "full_output_budget"))
        full = false;
    }
    json_object_object_add(point, "full_output_budget",
                           json_object_new_boolean(full));
    fields(point, first,
           "output_ids prefill_logits_sha256 decode_logits_sha256");
    json_object_object_add(point, "prefill_tps",
                           metric(group, "prefill_tps", 1, true));
    json_object_object_add(point, "decode_tps",
                           metric(group, "decode_tps", 1, true));
    json_object_object_add(point, "prefill_seconds",
                           metric(group, "prefill_ns", 1e-9, true));
    json_object_object_add(point, "decode_seconds",
                           metric(group, "decode_ns", 1e-9, true));
    json_object_object_del(point, "_rows");
  }
  json_object_put(input);
  json_object_put(samples);
  return out;
bad:
  json_object_put(out);
  json_object_put(input);
  json_object_put(samples);
  return NULL;
}
static const char *policy_keys[] = {"cache_min_tokens", "cache_cold_max_tokens",
                                    "cache_continued_tokens",
                                    "cache_trim_tokens", "cache_align_tokens"};
static json_object *core_generation(json_object *id) {
  const char *keys[] = {"temperature", "top_p", "frequency_penalty", "presence_penalty"};
  const double lower[] = {0, 0, -2, -2}, upper[] = {2, 1, 2, 2};
  double values[] = {0, 1, 0, 0};
  int64_t seed = -1;
  json_object *declared = NULL;
  if (json_object_object_get_ex(id, "generation", &declared)) {
    if (!json_object_is_type(declared, json_type_object) ||
        json_object_object_length(declared) != 5)
      return NULL;
    for (size_t k = 0; k < 4; ++k) {
      json_object *v = nb_get(declared, keys[k]);
      if (!json_object_is_type(v, json_type_int) && !json_object_is_type(v, json_type_double))
        return NULL;
      values[k] = json_object_get_double(v);
      if (!isfinite(values[k]) || values[k] < lower[k] || values[k] > upper[k] ||
          (k == 1 && values[k] == 0))
        return NULL;
    }
    json_object *v = nb_get(declared, "seed");
    if (!json_object_is_type(v, json_type_int))
      return NULL;
    seed = json_object_get_int64(v);
    if (seed < -1 || (seed >= 0 && json_object_get_uint64(v) > INT64_MAX) ||
        (values[0] > 0 && seed < 0))
      return NULL;
  }
  /* Historical core streams predate configurable sampling and are greedy. */
  json_object *out = json_object_new_object();
  for (size_t k = 0; k < 4; ++k)
    nb_real(out, keys[k], values[k]);
  nb_num(out, "seed", seed);
  return out;
}
static json_object *core(json_object *rows, nb_error *e) {
  json_object *id = json_object_array_get_idx(rows, 0),
              *out = json_object_new_object(),
              *points = json_object_new_array(),
              *input = select_rows(rows, "input"),
              *samples = select_rows(rows, "sample"),
              *jobs = select_rows(rows, "job"), *generation = NULL;
  nb_add(out, "identity", id);
  json_object_object_add(out, "configurations", points);
  nb_add(out, "samples", samples);
  nb_add(out, "jobs", jobs);
  json_object_object_add(out, "loading", select_rows(rows, "core_ready"));
  CHECK(repetition_config(id) && eqs(id, "suite", "core") &&
            eqs(id, "execution", "shared-reactive-core") &&
            nb_count(id, "users", 1, 8, NULL) &&
            nb_count(id, "prefill_chunk", 1, 2048, NULL),
        "Invalid core identity");
  generation = core_generation(id);
  CHECK(generation, "Invalid core sampling controls or missing reproducible seed");
  size_t users = (size_t)nb_number(id, "users"),
         reps =
             (size_t)(nb_number(id, "warmups") + nb_number(id, "repetitions"));
  CHECK(json_object_array_length(input) == 1 &&
            json_object_array_length(samples) == reps &&
            json_object_array_length(jobs) == reps * users,
        "Missing or duplicate core samples");
  const char *cache = nb_get(id, "cache_policy") ? nb_string(id, "cache_policy")
                                                 : "off",
             *format = nb_string(id, "state_format");
  bool ram = !strcmp(cache, "ram") || !strcmp(cache, "ram+ssd"),
       disk = !strcmp(cache, "ssd") || !strcmp(cache, "ram+ssd");
  CHECK(ram || disk || !strcmp(cache, "off"), "Invalid cache declaration");
  CHECK((!nb_get(id, "prefix_cache_bytes") ||
         nonnegative(id, "prefix_cache_bytes")) &&
            ram == (nb_number(id, "prefix_cache_bytes") > 0),
        "Invalid RAM budget declaration");
  for (unsigned i = 0; i < 2; i++) {
    const char *k = i ? "ssd_staging_bytes" : "ssd_quota_bytes";
    CHECK((!nb_get(id, k) || nonnegative(id, k)) &&
              disk == (nb_number(id, k) > 0),
          "Invalid KV disk budget declaration");
  }
  CHECK(!*format || !strcmp(format, "none") ||
            !strcmp(format, "lie-aligned-components") ||
            !strcmp(format, "ds4-kvc-payload") ||
            !strcmp(format, "synthetic-aligned-components") ||
            !strcmp(format, "synthetic-kvc-payload"),
        "Invalid state format");
  CHECK(strncmp(format, "synthetic-", 10) || flag(id, "synthetic"),
        "Synthetic state in model evidence");
  CHECK(!nb_get(id, "checkpoint_policy") ||
            eqs(id, "checkpoint_policy", "legacy") ||
            eqs(id, "checkpoint_policy", "ds4"),
        "Invalid checkpoint policy");
  for (size_t k = 0; k < 5; k++)
    CHECK(!nb_get(id, policy_keys[k]) ||
              nb_count(id, policy_keys[k], 0, UINT32_MAX, NULL),
          "Invalid checkpoint bounds");
  CHECK(
      !nb_get(id, "cache_retention_policy") ||
          eqs(id, "cache_retention_policy", "lru") ||
          eqs(id, "cache_retention_policy", "decaying-token-byte-utility-v1") ||
          eqs(id, "cache_retention_policy", "ds4-time-token-byte-utility-v1"),
      "Invalid retention policy");
  const char *flags[] = {"checkpoint_compression", "cache_text_prefix",
                         "cache_capture_finish"};
  for (unsigned i = 0; i < 3; i++)
    CHECK(!nb_get(id, flags[i]) ||
              json_object_is_type(nb_get(id, flags[i]), json_type_boolean),
          "Invalid checkpoint flag");
  const char *codec = nb_get(id, "checkpoint_codec")
                          ? nb_string(id, "checkpoint_codec")
                      : flag(id, "checkpoint_compression") ? "lz4-blocks-v1"
                                                           : "none";
  CHECK((!strcmp(codec, "none") || !strcmp(codec, "lz4-blocks-v1") ||
         !strcmp(codec, "byte-plane4-zstd1-v1")) &&
            (strcmp(codec, "none") != 0) == flag(id, "checkpoint_compression"),
        "Invalid checkpoint codec declaration");
  json_object *in = json_object_array_get_idx(input, 0);
  int64_t pp = nb_number(in, "prompt_tokens");
  CHECK(ids(in) && nb_count(id, "context_capacity", 1, 2097152, NULL) &&
            pp + nb_number(id, "output_limit") <=
                nb_number(id, "context_capacity"),
        "Invalid core physical inputs or capacity");
  json_object *first = json_object_array_get_idx(jobs, 0);
  bool full = true;
  for (size_t rep = 0; rep < reps; rep++) {
    json_object *s = json_object_array_get_idx(samples, rep);
    CHECK(nb_count(s, "rep", (int64_t)rep, (int64_t)rep, NULL) &&
              nb_number(s, "users") == (int64_t)users &&
              flag(s, "warmup") == ((int64_t)rep < nb_number(id, "warmups")),
          "Core sample ordering or warmup drift");
    int64_t tokens = 0, hits = 0;
    for (size_t u = 0; u < users; u++) {
      json_object *r = json_object_array_get_idx(jobs, rep * users + u);
      CHECK(nb_number(r, "rep") == (int64_t)rep &&
                nb_number(r, "user") == (int64_t)u &&
                flag(r, "warmup") == flag(s, "warmup"),
            "Core peer ordering");
      int64_t cached = nb_number(r, "cached_tokens"),
              ssd = nb_number(r, "ssd_cached_tokens"),
              tg = nb_number(r, "output_tokens"),
              total = nb_number(r, "total_ns");
      CHECK((!nb_get(r, "cached_tokens") ||
             nb_count(r, "cached_tokens", 0, pp, NULL)) &&
                (!nb_get(r, "ssd_cached_tokens") ||
                 nb_count(r, "ssd_cached_tokens", 0, cached, NULL)) &&
                (!cached || ram || disk) && (!ssd || disk) &&
                (ram || cached == ssd),
            "Core cached token accounting");
      CHECK((!nb_get(r, "ssd_read_ns") || nonnegative(r, "ssd_read_ns")) &&
                (disk || !nb_number(r, "ssd_read_ns")),
            "Core disk timing");
      CHECK(!eqs(id, "checkpoint_policy", "legacy") || cached == pp ||
                cached % nb_number(id, "prefill_chunk") == 0,
            "Unaligned legacy cache reuse");
      CHECK(nb_number(r, "prompt_tokens") == pp &&
                nb_count(r, "prefill_tokens", 0, pp, NULL) &&
                nb_number(r, "prefill_tokens") + cached == pp,
            "Core prefill accounting");
      const char *counts[] = {
          "output_tokens", "output_bytes",     "prefill_ns",
          "decode_ns",     "prefill_calls",    "decode_calls",
          "total_ns",      "cache_capture_ns", "cache_restore_ns"};
      for (unsigned k = 0; k < 9; k++)
        CHECK((k >= 7 && !nb_get(r, counts[k])) || nonnegative(r, counts[k]),
              "Invalid core timing or count");
      CHECK(ram || disk ||
                (!nb_number(r, "cache_capture_ns") &&
                 !nb_number(r, "cache_restore_ns")),
            "Cache timing with retention disabled");
      CHECK(nb_number(r, "prefill_tokens") ||
                (!nb_number(r, "prefill_ns") && !nb_number(r, "prefill_calls")),
            "Cached prefill double counting");
      CHECK(total > 0 && tg <= nb_number(id, "output_limit") &&
                output_ids(nb_get(r, "output_ids"), tg) &&
                nb_same(r, first, "output_ids"),
            "Core output count or reproducible drift");
      CHECK(eqs(r, "finish", "stop") || (eqs(r, "finish", "length") &&
                                         tg == nb_number(id, "output_limit")),
            "Core completion reason");
      CHECK(tg ? nb_count(r, "first_token_ns", 0, total, NULL)
               : !nb_get(r, "first_token_ns"),
            "Core first token timing");
      if (!flag(r, "warmup") && tg != nb_number(id, "output_limit"))
        full = false;
      tokens += tg;
      hits += cached && !ssd;
    }
    CHECK(!ram || (nb_number(s, "cache_hits") == hits &&
                   nb_number(s, "cache_misses") == (int64_t)users - hits),
          "Core cache cohort accounting");
    if (ram)
      CHECK(nb_number(s, "cache_budget_bytes") ==
                    nb_number(id, "prefix_cache_bytes") &&
                nb_count(s, "cache_retained_bytes", 0,
                         nb_number(id, "prefix_cache_bytes"), NULL),
            "Core retained RAM budget");
    const char *optional[] = {
        "cache_expanded_bytes", "cache_compressed_captures",
        "cache_skipped",        "ssd_evictions",
        "ssd_skipped",          "ssd_errors"};
    for (unsigned k = 0; k < 6; k++)
      CHECK(!nb_get(s, optional[k]) || nonnegative(s, optional[k]),
            "Invalid core cache admission counter");
    CHECK(!nb_get(s, "cache_expanded_bytes") ||
              nb_number(s, "cache_expanded_bytes") >=
                  nb_number(s, "cache_retained_bytes"),
          "Core expanded state accounting");
    CHECK(flag(id, "checkpoint_compression") ||
              !nb_number(s, "cache_compressed_captures"),
          "Disabled compression counter");
    CHECK(nb_number(s, "output_tokens") == tokens &&
              nb_count(s, "wall_ns", 1, INT64_MAX, NULL) &&
              rate(s, "output_per_total_wall_tps", tokens,
                   nb_number(s, "wall_ns")),
          "Invalid common-window rate");
    CHECK(nonnegative(s, "decode_batches") &&
              nonnegative(s, "decode_batch_rows") &&
              nonnegative(s, "decode_single_calls") &&
              nb_number(s, "decode_batches") <= INT64_MAX / 8 &&
              2 * nb_number(s, "decode_batches") <=
                  nb_number(s, "decode_batch_rows") &&
              nb_number(s, "decode_batch_rows") <=
                  (int64_t)users * nb_number(s, "decode_batches"),
          "Core batch width accounting");
  }
  json_object *point = json_object_new_object();
  json_object_array_add(points, point);
  nb_add(point, "generation", generation);
  fields(point, id,
         "mode mtp_model mtp_draft_tokens_requested vision_model image_sha256 image_bytes users context_capacity prefill_chunk input_kind output_limit "
         "repetitions cache_policy prefix_cache_bytes cache_retention_policy "
         "checkpoint_compression checkpoint_codec checkpoint_policy "
         "state_format ssd_quota_bytes ssd_staging_bytes");
  nb_str(point, "cache_policy", cache);
  nb_num(point, "prefix_cache_bytes", nb_number(id, "prefix_cache_bytes"));
  nb_num(point, "ssd_quota_bytes", nb_number(id, "ssd_quota_bytes"));
  nb_num(point, "ssd_staging_bytes", nb_number(id, "ssd_staging_bytes"));
  nb_str(point, "checkpoint_codec", codec);
  nb_str(point, "checkpoint_policy",
         nb_get(id, "checkpoint_policy") ? nb_string(id, "checkpoint_policy")
                                         : "legacy");
  nb_str(point, "cache_retention_policy",
         nb_get(id, "cache_retention_policy")
             ? nb_string(id, "cache_retention_policy")
             : "lru");
  nb_str(point, "state_format",
         *format                 ? format
         : flag(id, "synthetic") ? "synthetic-aligned-components"
                                 : "lie-aligned-components");
  json_object_object_add(
      point, "checkpoint_compression",
      json_object_new_boolean(flag(id, "checkpoint_compression")));
  fields(point, in, "prompt_tokens physical_ids_sha256");
  nb_add(point, "output_ids", nb_get(first, "output_ids"));
  json_object_object_add(point, "full_output_budget",
                         json_object_new_boolean(full));
  json_object *params = json_object_new_object(),
              *pflags = json_object_new_object();
  for (size_t k = 0; k < 5; k++)
    nb_num(params, policy_keys[k], nb_number(id, policy_keys[k]));
  for (size_t k = 1; k < 3; k++)
    json_object_object_add(pflags, flags[k],
                           json_object_new_boolean(flag(id, flags[k])));
  json_object_object_add(point, "checkpoint_parameters", params);
  json_object_object_add(point, "checkpoint_flags", pflags);
  const char *jm[] = {"ssd_cached_tokens", "ssd_read_ns",      "cached_tokens",
                      "cache_capture_ns",  "cache_restore_ns", "first_token_ns",
                      "total_ns"};
  for (unsigned k = 0; k < 7; k++)
    json_object_object_add(point, jm[k], metric(jobs, jm[k], 1, true));
  const char *sm[] = {"cache_retained_bytes", "cache_expanded_bytes",
                      "output_per_total_wall_tps"};
  for (unsigned k = 0; k < 3; k++)
    json_object_object_add(point, sm[k], metric(samples, sm[k], 1, true));
  double pp_rates[880], tg_rates[880];
  size_t pp_count = 0, tg_count = 0;
  for (size_t i = 0; i < json_object_array_length(jobs); i++) {
    json_object *r = json_object_array_get_idx(jobs, i);
    if (!flag(r, "warmup") && nb_number(r, "prefill_ns"))
      pp_rates[pp_count++] =
          nb_number(r, "prefill_tokens") * 1e9 / nb_number(r, "prefill_ns");
    if (!flag(r, "warmup") && nb_number(r, "decode_ns"))
      tg_rates[tg_count++] =
          nb_number(r, "output_tokens") * 1e9 / nb_number(r, "decode_ns");
  }
  json_object_object_add(point, "job_prefill_tps",
                         nb_distribution(pp_rates, pp_count));
  json_object_object_add(point, "job_decode_tps",
                         nb_distribution(tg_rates, tg_count));
  json_object_put(input);
  json_object_put(samples);
  json_object_put(jobs);
  json_object_put(generation);
  return out;
bad:
  json_object_put(generation);
  json_object_put(out);
  json_object_put(input);
  json_object_put(samples);
  json_object_put(jobs);
  return NULL;
}
static json_object *http_summary(json_object *rows, nb_error *e) {
  json_object *out = json_object_new_object(),
              *id = json_object_array_get_idx(rows, 0),
              *samples = select_rows(rows, "sample"),
              *cases = json_object_new_array();
  nb_add(out, "identity", id);
  json_object_object_add(out, "cases", cases);
  CHECK(nb_count(id, "warmups", 0, 10, NULL) &&
            nb_count(id, "repetitions", 1, 100, NULL) &&
            json_object_array_length(samples),
        "Invalid HTTP benchmark identity or missing samples");
  size_t reps =
      (size_t)(nb_number(id, "warmups") + nb_number(id, "repetitions"));
  for (size_t i = 0; i < json_object_array_length(samples); i++) {
    json_object *r = json_object_array_get_idx(samples, i);
    char hash[65];
    json_object *request = nb_get(r, "request"), *usage = nb_get(r, "usage"),
                *wall = nb_get(r, "wall_seconds"),
                *ttft = nb_get(r, "first_output_seconds");
    double seconds = json_object_get_double(wall),
           first = json_object_get_double(ttft);
    int64_t pp = nb_number(usage, "prompt_tokens"),
            tg = nb_number(usage, "completion_tokens");
    CHECK(*nb_string(r, "case") && nb_count(r, "turn", 0, 99, NULL) &&
              nb_count(r, "rep", 0, (int64_t)reps - 1, NULL) &&
              flag(r, "warmup") ==
                  (nb_number(r, "rep") < nb_number(id, "warmups")),
          "Invalid HTTP sample identity or warmup");
    CHECK(json_object_is_type(request, json_type_object) &&
              nb_json_hash(request, hash) &&
              !strcmp(hash, nb_string(r, "request_sha256")),
          "HTTP request witness mismatch");
    CHECK(nb_count(request, "max_tokens", 1, 65536, NULL) &&
              nb_count(usage, "prompt_tokens", 1, INT64_MAX - 65536, NULL) &&
              nb_count(usage, "completion_tokens", 0,
                       nb_number(request, "max_tokens"), NULL),
          "Invalid actual HTTP token usage");
    CHECK(flag(r, "full_output_budget") ==
              (tg == nb_number(request, "max_tokens")),
          "HTTP output budget declaration");
    CHECK((json_object_is_type(wall, json_type_int) ||
           json_object_is_type(wall, json_type_double)) &&
              isfinite(seconds) && seconds > 0 &&
              (!ttft || (isfinite(first) && first >= 0 && first <= seconds)),
          "Invalid HTTP wall or first-output timing");
    CHECK(fabs(json_object_get_double(nb_get(r, "prompt_over_wall_tps")) -
               pp / seconds) <= pp / seconds * 1e-12 &&
              fabs(json_object_get_double(nb_get(r, "output_over_wall_tps")) -
                   tg / seconds) <= fmax(tg / seconds, 1) * 1e-12,
          "HTTP rate accounting");
  }
  for (size_t i = 0; i < json_object_array_length(samples); i++) {
    json_object *r = json_object_array_get_idx(samples, i);
    bool known = false;
    for (size_t j = 0; j < json_object_array_length(cases); j++) {
      json_object *c = json_object_array_get_idx(cases, j);
      if (nb_same(c, r, "case") && nb_same(c, r, "turn"))
        known = true;
    }
    if (known)
      continue;
    json_object *point = json_object_new_object(),
                *group = json_object_new_array();
    json_object_array_add(cases, point);
    fields(point, r, "case turn");
    json_object_object_add(point, "_rows", group);
    for (size_t j = 0; j < json_object_array_length(samples); j++) {
      json_object *x = json_object_array_get_idx(samples, j);
      if (nb_same(x, r, "case") && nb_same(x, r, "turn"))
        json_object_array_add(group, json_object_get(x));
    }
    CHECK(json_object_array_length(group) == reps, "Missing HTTP repetitions");
    json_object *prompt = json_object_new_array(),
                *output = json_object_new_array(),
                *requests = json_object_new_array(),
                *hashes = json_object_new_array();
    json_object_object_add(point, "prompt_tokens", prompt);
    json_object_object_add(point, "output_tokens", output);
    json_object_object_add(point, "request_hashes", requests);
    json_object_object_add(point, "output_hashes", hashes);
    bool full = true;
    for (size_t j = 0; j < reps; j++) {
      json_object *x = json_object_array_get_idx(group, j);
      CHECK(nb_number(x, "rep") == (int64_t)j,
            "Missing or reordered HTTP repetition");
      if (flag(x, "warmup"))
        continue;
      json_object_array_add(
          prompt, json_object_get(nb_get(nb_get(x, "usage"), "prompt_tokens")));
      json_object_array_add(
          output,
          json_object_get(nb_get(nb_get(x, "usage"), "completion_tokens")));
      json_object_array_add(requests,
                            json_object_get(nb_get(x, "request_sha256")));
      char h[65];
      CHECK(nb_json_hash(nb_get(x, "assistant"), h), "Output witness failed");
      json_object_array_add(hashes, json_object_new_string(h));
      full = full && flag(x, "full_output_budget");
    }
    nb_num(point, "samples", nb_number(id, "repetitions"));
    json_object_object_add(point, "full_output_budget",
                           json_object_new_boolean(full));
    const char *metrics[] = {"wall_seconds", "first_output_seconds",
                             "prompt_over_wall_tps", "output_over_wall_tps"};
    for (unsigned k = 0; k < 4; k++)
      json_object_object_add(point, metrics[k],
                             metric(group, metrics[k], 1, true));
    json_object_object_del(point, "_rows");
  }
  json_object_put(samples);
  return out;
bad:
  json_object_put(samples);
  json_object_put(out);
  return NULL;
}
json_object *nb_ssd_summary(json_object *result, nb_error *e) {
  json_object *stats = json_object_new_array(),
              *samples = nb_get(result, "samples");
  CHECK(json_object_is_type(samples, json_type_array) &&
            json_object_array_length(samples),
        "Missing KV disk HTTP samples");
  for (size_t i = 0; i < json_object_array_length(samples); i++) {
    json_object *row = json_object_array_get_idx(samples, i);
    int64_t users =
        !strncmp(nb_string(row, "label"), "concurrent-", 11) ? 2 : 1;
    bool known = false;
    for (size_t j = 0; j < json_object_array_length(stats); j++) {
      json_object *s = json_object_array_get_idx(stats, j);
      if (nb_same(s, row, "case") && nb_same(s, row, "api") &&
          flag(s, "stream") == flag(row, "stream") &&
          nb_number(s, "users") == users)
        known = true;
    }
    if (known)
      continue;
    json_object *s = json_object_new_object(), *group = json_object_new_array();
    json_object_array_add(stats, s);
    fields(s, row, "case api stream");
    nb_num(s, "users", users);
    json_object_object_add(s, "_rows", group);
    json_object *gaps = json_object_new_array(), *pp = json_object_new_array(),
                *tg = json_object_new_array();
    json_object_object_add(s, "_gaps", gaps);
    json_object_object_add(s, "_pp", pp);
    json_object_object_add(s, "_tg", tg);
    bool full = true;
    for (size_t j = 0; j < json_object_array_length(samples); j++) {
      json_object *x = json_object_array_get_idx(samples, j);
      int64_t u = !strncmp(nb_string(x, "label"), "concurrent-", 11) ? 2 : 1;
      if (!nb_same(row, x, "case") || !nb_same(row, x, "api") ||
          flag(row, "stream") != flag(x, "stream") || u != users)
        continue;
      json_object_array_add(group, json_object_get(x));
      full = full && flag(x, "full_output_budget");
      json_object *v = nb_get(x, "inter_output_ms");
      if (v)
        for (size_t k = 0; k < json_object_array_length(v); k++) {
          json_object *item = json_object_new_object();
          nb_add(item, "value", json_object_array_get_idx(v, k));
          json_object_array_add(gaps, item);
        }
      const char *keys[] = {"prefill_tokens_per_second",
                            "decode_tokens_per_second"};
      json_object *arrays[] = {pp, tg};
      for (unsigned k = 0; k < 2; k++) {
        json_object *value = nb_get(nb_get(x, "timings"), keys[k]);
        if (value) {
          json_object *item = json_object_new_object();
          nb_add(item, "value", value);
          json_object_array_add(arrays[k], item);
        }
      }
    }
    nb_num(s, "samples", (int64_t)json_object_array_length(group));
    json_object_object_add(s, "full_output_budget",
                           json_object_new_boolean(full));
    json_object_object_add(s, "wall_ms", metric(group, "wall_ms", 1, false));
    json_object_object_add(s, "first_output_ms",
                           metric(group, "first_output_ms", 1, false));
    json_object_object_add(s, "inter_output_ms",
                           metric(gaps, "value", 1, false));
    json_object_object_add(s, "executed_pp_tps", metric(pp, "value", 1, false));
    json_object_object_add(s, "executor_tg_tps", metric(tg, "value", 1, false));
    json_object_object_del(s, "_rows");
    json_object_object_del(s, "_gaps");
    json_object_object_del(s, "_pp");
    json_object_object_del(s, "_tg");
  }
  return stats;
bad:
  json_object_put(stats);
  return NULL;
}
static json_object *read_result(const char *path, nb_error *e) {
  json_object *rows = nb_read(path, true, e), *out = NULL;
  if (!rows)
    return NULL;
  size_t n = json_object_array_length(rows);
  CHECK(n >= 2, "Incomplete benchmark evidence");
  json_object *id = json_object_array_get_idx(rows, 0),
              *last = json_object_array_get_idx(rows, n - 1);
  CHECK(eqs(id, "event", "identity") && eqs(last, "event", "complete"),
        "Failed or incomplete benchmark; no partial averaging");
  if (eqs(id, "schema", "synapse-lie.http-ssd-bench.v1")) {
    CHECK(eqs(last, "state", "PASS"), "KV disk benchmark did not pass");
    for (size_t i = 1; i < n - 1; i++) {
      json_object *r = json_object_array_get_idx(rows, i);
      CHECK(!eqs(r, "event", "failed"), "Failed KV disk observation");
      if (eqs(r, "event", "phase_complete")) {
        CHECK(!out, "Duplicate KV disk phase");
        out = nb_copy(nb_get(r, "result"));
      }
    }
    CHECK(out && eqs(out, "state", "PASS"), "Missing KV disk phase result");
    json_object *stats = nb_ssd_summary(out, e);
    if (!stats)
      goto bad;
    json_object_object_add(out, "distributions", stats);
  } else {
    CHECK(nb_count(last, "exit_code", 0, 0, NULL), "Failed benchmark evidence");
    if (eqs(id, "schema", "synapse-lie.bench.v1"))
      out = direct(rows, e);
    else if (eqs(id, "schema", "synapse-lie.core-bench.v1"))
      out = core(rows, e);
    else if (eqs(id, "schema", "synapse-lie.http-bench.v1"))
      out = http_summary(rows, e);
    else {
      nb_fail(e, "Unsupported benchmark report schema");
      goto bad;
    }
    if (!out)
      goto bad;
  }
  char hash[65];
  CHECK(nb_file_hash(path, hash), "Cannot hash benchmark input");
  nb_str(out, "source", path);
  nb_str(out, "source_sha256", hash);
  json_object_put(rows);
  return out;
bad:
  json_object_put(rows);
  json_object_put(out);
  return NULL;
}
static json_object *comparison(json_object *a, json_object *b, bool cache_build,
                               nb_error *e) {
  json_object *out = json_object_new_array(), *ai = nb_get(a, "identity"),
              *bi = nb_get(b, "identity"), *ap = nb_get(a, "configurations"),
              *bp = nb_get(b, "configurations");
  CHECK(nb_same(ai, bi, "schema") && nb_same(ai, bi, "synthetic") &&
            nb_same(ai, bi, "suite"),
        "Comparison scope or provider-kind mismatch");
  bool iscore = eqs(ai, "suite", "core"),
       http = eqs(ai, "schema", "synapse-lie.http-bench.v1");
  CHECK(!cache_build || iscore, "Cache build comparison requires core results");
  if (http) {
    ap = nb_get(a, "cases");
    bp = nb_get(b, "cases");
    CHECK(nb_same(ai, bi, "cache_policy") &&
              nb_same(ai, bi, "context_capacity_declared") &&
              nb_same(ai, bi, "rope_scaling_declared"),
          "HTTP comparison declarations differ");
  } else
    CHECK(nb_same(ai, bi, "output_limit"), "Comparison output budgets differ");
  CHECK(ap && bp &&
            json_object_array_length(ap) == json_object_array_length(bp),
        "Comparison point count mismatch");
  for (size_t i = 0; i < json_object_array_length(ap); i++) {
    json_object *p = json_object_array_get_idx(ap, i), *q = NULL;
    for (size_t j = 0; j < json_object_array_length(bp); j++) {
      json_object *candidate = json_object_array_get_idx(bp, j);
      bool match = http     ? (nb_same(p, candidate, "case") &&
                               nb_same(p, candidate, "turn"))
                   : iscore ? true
                            : (nb_same(p, candidate, "depth") &&
                               nb_same(p, candidate, "users") &&
                               nb_same(p, candidate, "prompt_tokens"));
      if (match) {
        CHECK(!q, "Duplicate comparison point");
        q = candidate;
      }
    }
    CHECK(q, "Missing comparison point");
    const char *samecore[] = {"users",           "context_capacity",
                              "prefill_chunk",   "input_kind",
                              "output_limit",    "physical_ids_sha256",
                              "cache_policy",    "prefix_cache_bytes",
                              "ssd_quota_bytes", "ssd_staging_bytes", "image_sha256", "vision_model", "generation"};
    if (iscore) {
      for (size_t k = 0; k < sizeof(samecore) / sizeof(*samecore); k++)
        CHECK(nb_same(p, q, samecore[k]),
              "Core comparison input/settings mismatch");
    } else if (http)
      CHECK(nb_same(p, q, "request_hashes") && nb_same(p, q, "prompt_tokens"),
            "HTTP comparison request or physical counts differ");
    else
      CHECK(nb_same(p, q, "context_capacity") &&
                nb_same(p, q, "physical_ids_sha256"),
            "Comparison capacity or physical input mismatch");
    json_object *r = json_object_new_object();
    json_object_array_add(out, r);
    bool equal = nb_same(p, q, http ? "output_hashes" : "output_ids"),
         full = flag(p, "full_output_budget") && flag(q, "full_output_budget"),
         eligible = equal && full;
    json_object_object_add(r, http ? "output_equal" : "tokens_equal",
                           json_object_new_boolean(equal));
    json_object_object_add(r, "full_output_budget",
                           json_object_new_boolean(full));
    json_object_object_add(r, "eligible", json_object_new_boolean(eligible));
    if (http) {
      fields(r, p, "case turn");
      continue;
    }
    if (iscore) {
      json_object *diff = json_object_new_object();
      json_object_object_add(r, "build_setting_differences", diff);
      const char *keys[] = {"cache_retention_policy",
                            "checkpoint_compression",
                            "checkpoint_codec",
                            "checkpoint_policy",
                            "checkpoint_parameters",
                            "checkpoint_flags",
                            "state_format"};
      for (unsigned k = 0; k < 7; k++)
        if (!nb_same(p, q, keys[k])) {
          CHECK(cache_build, "Core cache build mismatch; select "
                             "--compare-cache-build explicitly");
          json_object *v = json_object_new_object();
          nb_add(v, "primary", nb_get(p, keys[k]));
          nb_add(v, "reference", nb_get(q, keys[k]));
          json_object_object_add(diff, keys[k], v);
        }
      json_object_object_add(r, "cache_build_comparison",
                             json_object_new_boolean(cache_build));
    } else {
      fields(r, p, "depth users");
      json_object_object_add(
          r, "pp_frontier_equal",
          json_object_new_boolean(nb_same(p, q, "prefill_logits_sha256")));
      json_object_object_add(
          r, "tg_frontier_equal",
          json_object_new_boolean(nb_same(p, q, "decode_logits_sha256")));
    }
    const char *ratekey = iscore ? "output_per_total_wall_tps" : "decode_tps";
    double denominator =
        json_object_get_double(nb_get(nb_get(q, ratekey), "median"));
    nb_real(r, iscore ? "output_per_total_wall_ratio" : "decode_ratio",
            eligible && denominator > 0
                ? json_object_get_double(nb_get(nb_get(p, ratekey), "median")) /
                      denominator
                : NAN);
  }
  return out;
bad:
  json_object_put(out);
  return NULL;
}
static void csv_string(FILE *f, const char *s) {
  fputc('"', f);
  for (; *s; s++) {
    if (*s == '"')
      fputc('"', f);
    fputc(*s, f);
  }
  fputc('"', f);
}
static void csv_value(FILE *f, json_object *v) {
  if (!v)
    return;
  if (json_object_is_type(v, json_type_string))
    csv_string(f, json_object_get_string(v));
  else if (json_object_is_type(v, json_type_array) ||
           json_object_is_type(v, json_type_object))
    csv_string(f, nb_encoded(v));
  else
    fputs(nb_encoded(v), f);
}
static void csv_fields(FILE *f, json_object *r, const char *keys) {
  char *copy = strdup(keys), *save = NULL;
  if (!copy)
    return;
  for (char *k = strtok_r(copy, " ", &save); k;
       k = strtok_r(NULL, " ", &save)) {
    fputc(',', f);
    csv_value(f, nb_get(r, k));
  }
  free(copy);
}
static void csv_stat(FILE *f, json_object *r, const char *key, const char *stat,
                     double scale) {
  fputc(',', f);
  json_object *v = nb_get(nb_get(r, key), stat);
  if (v)
    fprintf(f, "%.17g", json_object_get_double(v) * scale);
}
static bool export_csv(const char *dir, json_object *a, json_object *b,
                       const char *label, const char *ref, nb_error *e) {
  char path[4096];
  if (snprintf(path, sizeof(path), "%s/summary.csv", dir) >= (int)sizeof(path))
    return nb_fail(e, "Report path too long");
  FILE *f = nb_exclusive(path, e);
  if (!f)
    return false;
  bool iscore = eqs(nb_get(a, "identity"), "suite", "core"),
       http = nb_get(a, "cases") != NULL,
       ssd = eqs(a, "schema", "synapse-lie.http-ssd-bench.v1"),
       loading = eqs(nb_get(a, "identity"), "suite", "loading");
  if (ssd)
    fputs("case,api,stream,users,samples,metric,n,p50,p95,p99,min,max\n", f);
  else if (http)
    fputs("label,case,turn,prompt_tokens,output_tokens,full_output_budget,wall_"
          "median_s,ttft_median_s,pp_wall_mean_tps,tg_wall_mean_tps\n",
          f);
  else if (iscore)
    fputs("label,users,prompt_tokens,repetitions,job_prefill_median_tps,job_"
          "decode_median_tps,output_"
          "per_total_wall_median_tps,first_token_median_ms,total_median_ms,"
          "cache_policy,cached_tokens_median,cache_capture_median_ms,cache_"
          "restore_median_ms,ssd_cached_tokens_median,ssd_read_median_ms,cache_"
          "retention_policy,checkpoint_compression,cache_retained_bytes_median,"
          "cache_expanded_bytes_median,checkpoint_codec,state_format\n",
          f);
  else if (loading)
    fputs("label,context_capacity,users,model_load_seconds\n", f);
  else
    fputs("label,depth,users,context_capacity,prompt_tokens,repetitions,full_"
          "output_budget,pp_median_tps,pp_min_tps,pp_max_tps,tg_median_tps,tg_"
          "min_tps,tg_max_tps,pp_median_s,pp_min_s,pp_max_s,tg_median_s,tg_min_s,tg_max_s\n",
          f);
  json_object *series[] = {a, b};
  const char *labels[] = {label, ref};
  for (unsigned s = 0; s < (b ? 2u : 1u); s++) {
    json_object *points = nb_get(series[s], ssd       ? "distributions"
                                            : http    ? "cases"
                                            : loading ? "loading"
                                                      : "configurations");
    for (size_t i = 0; i < json_object_array_length(points); i++) {
      json_object *r = json_object_array_get_idx(points, i);
      if (ssd) {
        const char *keys[] = {"wall_ms", "first_output_ms", "inter_output_ms",
                              "executed_pp_tps", "executor_tg_tps"};
        for (unsigned k = 0; k < 5; k++) {
          csv_value(f, nb_get(r, "case"));
          csv_fields(f, r, "api stream users samples");
          fputc(',', f);
          csv_string(f, keys[k]);
          json_object *v = nb_get(r, keys[k]);
          csv_fields(f, v, "n p50 p95 p99 min max");
          fputc('\n', f);
        }
        continue;
      }
      csv_string(f, labels[s]);
      if (http) {
        csv_fields(f, r,
                   "case turn prompt_tokens output_tokens full_output_budget");
        csv_stat(f, r, "wall_seconds", "median", 1);
        csv_stat(f, r, "first_output_seconds", "median", 1);
        csv_stat(f, r, "prompt_over_wall_tps", "mean", 1);
        csv_stat(f, r, "output_over_wall_tps", "mean", 1);
      } else if (iscore) {
        csv_fields(f, r, "users prompt_tokens repetitions");
        csv_stat(f, r, "job_prefill_tps", "median", 1);
        csv_stat(f, r, "job_decode_tps", "median", 1);
        csv_stat(f, r, "output_per_total_wall_tps", "median", 1);
        csv_stat(f, r, "first_token_ns", "median", 1e-6);
        csv_stat(f, r, "total_ns", "median", 1e-6);
        csv_fields(f, r, "cache_policy");
        csv_stat(f, r, "cached_tokens", "median", 1);
        csv_stat(f, r, "cache_capture_ns", "median", 1e-6);
        csv_stat(f, r, "cache_restore_ns", "median", 1e-6);
        csv_stat(f, r, "ssd_cached_tokens", "median", 1);
        csv_stat(f, r, "ssd_read_ns", "median", 1e-6);
        csv_fields(f, r, "cache_retention_policy checkpoint_compression");
        csv_stat(f, r, "cache_retained_bytes", "median", 1);
        csv_stat(f, r, "cache_expanded_bytes", "median", 1);
        csv_fields(f, r, "checkpoint_codec state_format");
      } else if (loading) {
        csv_fields(f, r, "context_capacity users");
        fprintf(f, ",%.17g", nb_number(r, "model_load_ns") / 1e9);
      } else {
        csv_fields(f, r,
                   "depth users context_capacity prompt_tokens repetitions "
                   "full_output_budget");
        const char *stats[] = {"median", "min", "max"};
        for (unsigned k = 0; k < 2; k++)
          for (unsigned j = 0; j < 3; j++)
            csv_stat(f, r, k ? "decode_tps" : "prefill_tps", stats[j], 1);
        for (unsigned k = 0; k < 2; k++)
          for (unsigned j = 0; j < 3; j++)
            csv_stat(f, r, k ? "decode_seconds" : "prefill_seconds", stats[j], 1);
      }
      fputc('\n', f);
    }
  }
  bool ok = !ferror(f);
  if (fclose(f))
    ok = false;
  return ok ? true : nb_fail(e, "CSV output failed");
}
static bool export_graph(const char *dir, json_object *a, json_object *b,
                         const char *label, const char *ref, nb_error *e) {
  bool iscore = eqs(nb_get(a, "identity"), "suite", "core"),
       http = nb_get(a, "cases") != NULL,
       ssd = eqs(a, "schema", "synapse-lie.http-ssd-bench.v1"),
       loading = eqs(nb_get(a, "identity"), "suite", "loading");
  nb_plot_panel panels[3] = {0};
  const char *keys[3] = {"prefill_tps", "decode_tps", NULL};
  const char *titles[3] = {"Executed prefill", "Confirmed generation", NULL},
             *units[3] = {"new tokens/s", "output tokens/s", NULL};
  double scale[3] = {1, 1, 1};
  size_t np = 2;
  char title[180];
  snprintf(title, sizeof(title), "%s - %s benchmark",
           flag(nb_get(a, "identity"), "synthetic") || flag(a, "synthetic")
               ? "CPU fixture: NOT-INFERENCE"
               : "LIE",
           http     ? "HTTP client"
           : iscore ? "shared core"
           : ssd    ? "KV disk HTTP"
                    : "direct executor");
  if (iscore) {
    keys[0] = "job_prefill_tps";
    keys[1] = "output_per_total_wall_tps";
    keys[2] = "job_decode_tps";
    titles[0] = "Per-job executor prefill";
    titles[1] = "Aggregate output / complete client wall";
    titles[2] = "Per-job confirmed decode";
    units[2] = "output tokens/s";
    np = 3;
  } else if (http) {
    keys[0] = "first_output_seconds";
    keys[1] = "prompt_over_wall_tps";
    keys[2] = "output_over_wall_tps";
    titles[0] = "First output";
    titles[1] = "Prompt tokens / complete HTTP wall";
    titles[2] = "Output tokens / complete HTTP wall";
    units[0] = "seconds";
    units[1] = units[2] = "tokens/s";
    np = 3;
  } else if (ssd) {
    keys[0] = "first_output_ms";
    keys[1] = "inter_output_ms";
    keys[2] = "wall_ms";
    titles[0] = "First text output";
    titles[1] = "Gap between SSE text events (not individual model tokens)";
    titles[2] = "Complete HTTP wall";
    units[0] = units[1] = units[2] =
        "ms; nearest-rank percentiles, see sample counts in CSV";
    np = 3;
  } else if (loading) {
    keys[0] = "model_load_ns";
    titles[0] = "Model load (existing OS cache; excludes HTTP readiness)";
    units[0] = "seconds";
    scale[0] = 1e-9;
    np = 1;
  }
  bool ok = true;
  json_object *datasets[] = {a, b};
  const char *labels[] = {label, ref};
  for (size_t p = 0; ok && p < np; p++) {
    panels[p].title = titles[p];
    panels[p].unit = units[p];
    panels[p].x_label = ssd       ? "Case / API / concurrent users"
                        : http    ? "Workload / turn"
                        : loading ? "OS file cache uncontrolled"
                        : iscore || eqs(nb_get(a, "identity"), "suite", "multi")
                            ? "Concurrent users"
                        : eqs(nb_get(a, "identity"), "suite", "fresh")
                            ? "Full prompt tokens"
                            : "Reused prefix tokens";
    panels[p].count = ssd ? 3 : b ? 2 : 1;
    for (size_t s = 0; s < panels[p].count; s++) {
      json_object *data = datasets[ssd ? 0 : s],
                  *points = nb_get(data, ssd       ? "distributions"
                                         : http    ? "cases"
                                         : loading ? "loading"
                                                   : "configurations");
      size_t count = loading ? 1 : json_object_array_length(points);
      if (!count || count > 10000) {
        ok = nb_fail(e, "No report points or too many to plot");
        break;
      }
      nb_plot_series *v = &panels[p].series[s];
      v->count = count;
      v->label = ssd ? (s == 0 ? "p50" : s == 1 ? "p95" : "p99") : labels[s];
      v->ticks = calloc(count, sizeof(*v->ticks));
      v->median = malloc(count * sizeof(double));
      v->low = malloc(count * sizeof(double));
      v->high = malloc(count * sizeof(double));
      if (!v->ticks || !v->median || !v->low || !v->high) {
        ok = nb_fail(e, "Graph allocation failed");
        break;
      }
      json_object *load =
          loading ? metric(points, "model_load_ns", 1, false) : NULL;
      for (size_t i = 0; i < count; i++) {
        json_object *r = json_object_array_get_idx(points, i);
        /* Comparison accepts reordered point sets. Plot each reference point
         * against the matching physical workload, not its file position. */
        if (s && !ssd && !loading && !iscore) {
          json_object *primary = json_object_array_get_idx(
              nb_get(a, http ? "cases" : "configurations"), i);
          for (size_t j = 0; j < json_object_array_length(points); j++) {
            json_object *candidate = json_object_array_get_idx(points, j);
            bool match = http
                             ? nb_same(primary, candidate, "case") &&
                                   nb_same(primary, candidate, "turn")
                             : nb_same(primary, candidate, "depth") &&
                                   nb_same(primary, candidate, "users") &&
                                   nb_same(primary, candidate, "prompt_tokens");
            if (match) {
              r = candidate;
              break;
            }
          }
        }
        json_object *m = loading ? load : nb_get(r, keys[p]);
        char tick[128];
        if (http)
          snprintf(tick, sizeof(tick), "%.64s:%" PRId64, nb_string(r, "case"),
                   nb_number(r, "turn"));
        else if (ssd)
          snprintf(tick, sizeof(tick), "%.40s %.16s C%" PRId64,
                   nb_string(r, "case"), nb_string(r, "api"),
                   nb_number(r, "users"));
        else if (iscore || eqs(nb_get(data, "identity"), "suite", "multi"))
          snprintf(tick, sizeof(tick), "C%" PRId64, nb_number(r, "users"));
        else if (loading)
          snprintf(tick, sizeof(tick), "model load");
        else
          snprintf(tick, sizeof(tick), "%" PRId64 " tokens",
                   nb_number(r, eqs(nb_get(data, "identity"), "suite", "fresh")
                                    ? "prompt_tokens"
                                    : "depth"));
        v->ticks[i] = strdup(tick);
        if (!v->ticks[i]) {
          ok = false;
          break;
        }
        v->median[i] =
            m ? json_object_get_double(nb_get(m, ssd ? v->label : "median")) *
                    scale[p]
              : NAN;
        v->low[i] =
            m ? json_object_get_double(nb_get(m, ssd ? v->label : "min")) *
                    scale[p]
              : NAN;
        v->high[i] =
            m ? json_object_get_double(nb_get(m, ssd ? v->label : "max")) *
                    scale[p]
              : NAN;
      }
      json_object_put(load);
    }
  }
  if (ok)
    ok = nb_plot(dir, title, panels, np, e);
  for (size_t p = 0; p < np; p++)
    for (size_t s = 0; s < panels[p].count; s++) {
      nb_plot_series *v = &panels[p].series[s];
      if (v->ticks)
        for (size_t i = 0; i < v->count; i++)
          free((void *)v->ticks[i]);
      free(v->ticks);
      free(v->median);
      free(v->low);
      free(v->high);
    }
  return ok;
}
int nb_report(const char *input, const char *directory, const char *label,
              const char *reference, const char *ref_label, bool cache_build,
              nb_error *e) {
  json_object *a = read_result(input, e), *b = NULL, *checks = NULL,
              *summary = NULL;
  int rc = 1;
  if (!a)
    goto end;
  if (cache_build && !reference) {
    nb_fail(e, "--compare-cache-build requires --compare");
    goto end;
  }
  bool ssd = eqs(a, "schema", "synapse-lie.http-ssd-bench.v1"),
       http = nb_get(a, "cases") != NULL;
  if (reference) {
    if (ssd) {
      nb_fail(e, "KV disk reports compare fresh/restored samples within their "
                 "phase protocol");
      goto end;
    }
    b = read_result(reference, e);
    if (!b)
      goto end;
    checks = comparison(a, b, cache_build, e);
    if (!checks)
      goto end;
  }
  if (ssd)
    summary = json_object_get(nb_get(a, "distributions"));
  else if (http) {
    summary = nb_copy(a);
    if (b) {
      nb_add(summary, "reference", b);
      nb_add(summary, "comparison", checks);
    }
  } else {
    summary = json_object_new_object();
    nb_add(summary, "primary", a);
    nb_add(summary, "reference", b);
    nb_add(summary, "comparison", checks);
  }
  if (!nb_mkdir(directory, e))
    goto end;
  char path[4096];
  if (snprintf(path, sizeof(path), "%s/summary.json", directory) >=
      (int)sizeof(path)) {
    nb_fail(e, "Report path too long");
    goto end;
  }
  if (!nb_write_json(path, summary, e) ||
      !export_csv(directory, a, b, label, ref_label, e) ||
      !export_graph(directory, a, b, label, ref_label, e))
    goto end;
  rc = 0;
end:
  json_object_put(summary);
  json_object_put(checks);
  json_object_put(a);
  json_object_put(b);
  return rc;
}
int lie_bench_graphs(const char *input, const char *directory,
                     const char *reference) {
  nb_error error = {0};
  int rc = nb_report(input, directory, "LIE", reference, "Gufo reference",
                     false, &error);
  if (rc)
    fprintf(stderr, "Graph export failed: %s; benchmark JSONL is preserved\n",
            error.message);
  return rc ? 3 : 0;
}
int nb_report_main(int argc, char **argv) {
  const char *input = NULL, *out = NULL, *label = "LIE", *reference = NULL,
             *ref_label = "Gufo reference";
  bool cache = false;
  for (int i = 1; i < argc; i++) {
    const char *k = argv[i];
    if (!strcmp(k, "--help")) {
      puts("Usage: synapse-lie-bench --suite report INPUT-JSONL --output "
           "DIRECTORY\n  [--label LIE] [--compare REFERENCE-JSONL "
           "--reference-label NAME]\n  [--compare-cache-build]\nValidates "
           "complete evidence, then exports summary.json, summary.csv, "
           "benchmark.svg and benchmark.png.\nAll report generation is native "
           "C. Output files must not already exist. Failed evidence is never "
           "averaged.");
      return 0;
    }
    if (!strcmp(k, "--compare-cache-build")) {
      cache = true;
      continue;
    }
    if (k[0] != '-') {
      if (input)
        goto usage;
      input = k;
      continue;
    }
    if (i + 1 == argc)
      goto usage;
    const char *v = argv[++i];
    if (!strcmp(k, "--suite")) {
      if (strcmp(v, "report"))
        goto usage;
    } else if (!strcmp(k, "--input")) {
      if (input)
        goto usage;
      input = v;
    } else if (!strcmp(k, "--output"))
      out = v;
    else if (!strcmp(k, "--label"))
      label = v;
    else if (!strcmp(k, "--compare"))
      reference = v;
    else if (!strcmp(k, "--reference-label"))
      ref_label = v;
    else
      goto usage;
  }
  if (!input || !out)
    goto usage;
  nb_error error = {0};
  int rc = nb_report(input, out, label, reference, ref_label, cache, &error);
  if (rc)
    fprintf(stderr, "Report failed: %s\n", error.message);
  return rc;
usage:
  fputs("Invalid report options; use --suite report --help\n", stderr);
  return 2;
}
#undef CHECK
