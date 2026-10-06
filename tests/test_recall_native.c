/* SPDX-License-Identifier: MIT */
/* Synthetic corpus and response oracles only: no server, weights or GPU. */
#include "bench_native.h"
#include <stdlib.h>
#include <string.h>

static void require(bool good, const char *why) {
  if (!good) {
    fprintf(stderr, "Recall fixture failed: %s\n", why);
    exit(1);
  }
}
static json_object *parse(const char *text) {
  nb_error error = {0};
  json_object *o = nb_parse(text, strlen(text), &error);
  require(o != NULL, error.message);
  return o;
}
static void score_text(json_object *expected, const char *text, bool wanted,
                       const char *reason) {
  json_object *row = json_object_new_object(),
              *assistant = json_object_new_object();
  nb_str(assistant, "content", text);
  nb_add(row, "assistant", assistant);
  nb_str(row, "finish_reason", "stop");
  nb_error error = {0};
  json_object *score = nb_recall_score(expected, row, &error);
  require(score != NULL, error.message);
  require((bool)json_object_get_boolean(nb_get(score, "pass")) == wanted,
          "semantic response decision");
  require(!strcmp(nb_string(score, "reason"), reason), "response diagnostic");
  json_object_put(score);
  json_object_put(assistant);
  json_object_put(row);
}
int main(void) {
  nb_error error = {0};
  json_object *o = parse("{\"kind\":\"json-object-exact\",\"value\":{\"a\":"
                         "\"one\",\"b\":\"two\"}}");
  score_text(o, " { \"b\":\"two\", \"a\":\"one\" } \n", true, "exact_match");
  score_text(o, "{\"a\":\"one\",\"b\":\"two\"}", true, "exact_match");
  score_text(o, "{\"\\u0061\":\"one\",\"b\":\"tw\\u006f\"}", true,
             "exact_match");
  score_text(o, "{\"a\":\"wrong\",\"b\":\"two\"}", false, "wrong_value");
  score_text(o, "{\"a\":\"one\"}", false, "missing_key");
  score_text(o, "{\"a\":\"one\",\"b\":\"two\",\"extra\":\"x\"}", false,
             "unexpected_key");
  score_text(o, "{\"a\":\"one\",\"b\":2}", false,
             "flat_string_object_required");
  score_text(o, "{\"a\":\"one\",\"b\":[\"two\"]}", false,
             "flat_string_object_required");
  score_text(o, "{\"a\":\"one\",\"b\":{\"x\":\"two\"}}", false,
             "flat_string_object_required");
  score_text(o, "{\"a\":\"one\",\"b\":\"two\",\"a\":\"one\"}", false,
             "invalid_json");
  score_text(o, "{\"a\":\"one\",\"b\":\"two\",\"\\u0061\":\"one\"}", false,
             "invalid_json");
  score_text(o, "{\"a\":\"one\",\"b\":\"two\"} {}", false, "invalid_json");
  score_text(o, "{\"a\":\"one\",\"b\":\"two\"} prose", false, "invalid_json");
  score_text(o, "\x60\x60\x60json\n{\"a\":\"one\",\"b\":\"two\"}\n\x60\x60\x60",
             false, "invalid_json");
  score_text(o, "", false, "invalid_json");
  score_text(o, "null", false, "flat_string_object_required");
  score_text(o, "{\"a\":\"one\\u0000\",\"b\":\"two\"}", false, "wrong_value");
  json_object *row =
      parse("{\"assistant\":{\"content\":\"{}\",\"tool_calls\":[]}}");
  json_object *s = nb_recall_score(o, row, &error);
  require(s && !strcmp(nb_string(s, "reason"), "unexpected_tool_calls"),
          "tool output refusal");
  json_object_put(s);
  json_object_put(row);
  row = parse("{}");
  s = nb_recall_score(o, row, &error);
  require(s && !strcmp(nb_string(s, "reason"), "missing_response"),
          "missing response refusal");
  json_object_put(s);
  json_object_put(row);
  json_object *oracles = json_object_new_array();
  json_object_array_add(oracles, json_object_get(o));
  require(nb_recall_oracles_valid(oracles, 1, &error),
          "prepared oracle admission");
  require(!nb_recall_oracles_valid(oracles, 2, &error), "turn count refusal");
  json_object_put(oracles);
  json_object *invalid[] = {
      parse("{\"kind\":\"unknown\",\"value\":{\"a\":\"one\"}}"),
      parse("{\"kind\":\"json-object-exact\",\"value\":{}}"),
      parse("{\"kind\":\"json-object-exact\",\"value\":{\"a\":2}}"),
      parse("{\"kind\":\"json-object-exact\",\"value\":{\"a\":\"placeholder\"}"
            "}")};
  /* The file reader already refuses decoded NUL. Construct the typed invalid
   * value directly to exercise this API's defensive admission as well. */
  json_object_object_add(nb_get(invalid[3], "value"), "a",
                         json_object_new_string_len("\0", 1));
  for (size_t i = 0; i < sizeof(invalid) / sizeof(*invalid); ++i) {
    row = parse("{}");
    require(!nb_recall_score(invalid[i], row, &error),
            "malformed oracle refusal");
    json_object_put(row);
    json_object_put(invalid[i]);
  }
  json_object *a = nb_recall_case(77, 32, 2, 128, &error),
              *b = nb_recall_case(77, 32, 2, 128, &error),
              *c = nb_recall_case(78, 32, 2, 128, &error),
              *d = nb_recall_case(77, 32, 1, 128, &error);
  require(a && b && c && d, error.message);
  require(json_object_equal(a, b) && !json_object_equal(a, c),
          "determinism and seed independence");
  require(nb_recall_oracles_valid(nb_get(a, "expected"), 2, &error) &&
              nb_recall_oracles_valid(nb_get(d, "expected"), 1, &error),
          "generated turn oracles");
  json_object *needles = nb_get(nb_get(a, "corpus"), "needles"),
              *first = nb_get(
                  json_object_array_get_idx(nb_get(a, "expected"), 0), "value"),
              *second = nb_get(
                  json_object_array_get_idx(nb_get(a, "expected"), 1), "value"),
              *single = nb_get(
                  json_object_array_get_idx(nb_get(d, "expected"), 0), "value");
  require(json_object_array_length(needles) == 3 &&
              json_object_object_length(first) == 1 &&
              json_object_object_length(second) == 2 &&
              json_object_object_length(single) == 3,
          "three independent needles");
  const char *text = nb_string(
      json_object_array_get_idx(nb_get(nb_get(a, "body"), "messages"), 0),
      "content");
  unsigned expected_rows[3] = {0, 16, 31};
  for (size_t i = 0; i < 3; ++i) {
    json_object *p = json_object_array_get_idx(needles, i);
    const char *key = nb_string(p, "key");
    json_object *value = nb_get(i == 1 ? first : second, key);
    require(value && nb_number(p, "record_index") == expected_rows[i],
            "start/middle/end physical row");
    const char *location = text + nb_number(p, "prompt_byte_offset");
    require(!strncmp(location, "binding ", 8) &&
                !strncmp(location + 8, key, strlen(key)),
            "exact byte location");
    require(strstr(location, json_object_get_string(value)) != NULL,
            "binding value");
    json_object *other = nb_get(i == 1 ? second : first, key);
    require(!other, "continuation queries previously unanswered keys");
  }
  score_text(json_object_array_get_idx(nb_get(d, "expected"), 0),
             nb_encoded(single), true, "exact_match");
  for (unsigned records = 4; records <= 512; records *= 2) {
    json_object *probe = nb_recall_case(UINT64_MAX, records, 2, 128, &error);
    require(probe &&
                nb_recall_oracles_valid(nb_get(probe, "expected"), 2, &error),
            "small calibration corpus with maximum seed");
    json_object_put(probe);
  }
  require(!nb_recall_case(77, 3, 2, 128, &error) &&
              !nb_recall_case(77, 32, 3, 128, &error) &&
              !nb_recall_case(77, 32, 2, 0, &error) &&
              !nb_recall_case(77, 1048576, 2, 128, &error),
          "bounds and admission refusal");
  json_object_put(a);
  json_object_put(b);
  json_object_put(c);
  json_object_put(d);
  json_object_put(o);
  puts("Native associative recall corpus and independent response/refusal "
       "oracles: PASS (NOT-INFERENCE)");
  return 0;
}
