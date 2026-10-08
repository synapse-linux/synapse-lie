/* SPDX-License-Identifier: MIT */
#include "bench_native.h"
#include "lie/json_parse.h"
#include <inttypes.h>
#include <stdlib.h>
#include <string.h>

#define RECALL_INPUT_LIMIT (8u * 1024u * 1024u)
#define RECALL_RESPONSE_LIMIT 131072u
#define RECALL_KEYS 8u

static bool oracle_valid(json_object *o, nb_error *e) {
  json_object *value = nb_get(o, "value"), *kind = nb_get(o, "kind");
  if (!json_object_is_type(o, json_type_object) ||
      !json_object_is_type(kind, json_type_string) ||
      json_object_get_string_len(kind) != (int)strlen("json-object-exact") ||
      strcmp(json_object_get_string(kind), "json-object-exact") ||
      !json_object_is_type(value, json_type_object) ||
      !json_object_object_length(value) ||
      (size_t)json_object_object_length(value) > RECALL_KEYS)
    return nb_fail(
        e, "Recall oracle requires a flat object with 1..8 string values");
  json_object_object_foreach(value, key, v) {
    if (!*key || strlen(key) > 64 ||
        !json_object_is_type(v, json_type_string) ||
        json_object_get_string_len(v) < 1 ||
        json_object_get_string_len(v) > 64 ||
        memchr(json_object_get_string(v), 0,
               (size_t)json_object_get_string_len(v)))
      return nb_fail(
          e, "Recall oracle keys and values must be bounded nonempty strings");
  }
  return true;
}

bool nb_recall_oracles_valid(json_object *a, size_t turns, nb_error *e) {
  if (!a)
    return true;
  if (!json_object_is_type(a, json_type_array) ||
      json_object_array_length(a) != turns || !turns || turns > 100)
    return nb_fail(e, "Recall requires exactly one oracle per turn");
  for (size_t i = 0; i < turns; ++i)
    if (!oracle_valid(json_object_array_get_idx(a, i), e))
      return false;
  return true;
}

static json_object *oracle(char keys[3][21], char values[3][19], unsigned begin,
                           unsigned end) {
  json_object *o = json_object_new_object(), *v = json_object_new_object();
  nb_str(o, "kind", "json-object-exact");
  for (unsigned i = begin; i < end; ++i)
    nb_str(v, keys[i], values[i]);
  nb_add(o, "value", v);
  json_object_put(v);
  return o;
}

json_object *nb_recall_case(uint64_t seed, unsigned records, unsigned turns,
                            unsigned budget, nb_error *e) {
  static const char head[] =
      "Reference ledger. Numeric rows are unrelated distractors. Each named "
      "key "
      "has exactly one value. Retrieve only the requested keys and return one "
      "JSON object with string values. Do not infer, explain or add keys.\n";
  if (records < 4 || records > 1048576 || (turns != 1 && turns != 2) ||
      !budget || budget > 65536) {
    nb_fail(e, "Recall requires 4..1048576 records, one or two turns and a "
               "bounded output budget");
    return NULL;
  }
  size_t bytes = sizeof(head) + (size_t)records * 32 + 3 * 96 + 512;
  if (bytes > RECALL_INPUT_LIMIT) {
    nb_fail(e, "Recall prompt exceeds HTTP body budget");
    return NULL;
  }
  char *text = malloc(bytes);
  if (!text) {
    nb_fail(e, "Recall prompt allocation failed");
    return NULL;
  }
  char keys[3][21], values[3][19];
  unsigned rows[3] = {0, records / 2, records - 1};
  for (unsigned i = 0; i < 3; ++i) {
    char source[128], hash[65];
    snprintf(source, sizeof(source),
             "lie-associative-recall-v1:key:%" PRIu64 ":%u", seed, i);
    if (!nb_hash(source, strlen(source), hash))
      goto hash_failed;
    snprintf(keys[i], sizeof(keys[i]), "key_%.16s", hash);
    snprintf(source, sizeof(source),
             "lie-associative-recall-v1:value:%" PRIu64 ":%u", seed, i);
    if (!nb_hash(source, strlen(source), hash))
      goto hash_failed;
    snprintf(values[i], sizeof(values[i]), "v_%.16s", hash);
    for (unsigned j = 0; j < i; ++j)
      if (!strcmp(keys[i], keys[j]) || !strcmp(values[i], values[j]))
        goto hash_failed;
  }
  json_object *item = json_object_new_object(),
              *body = json_object_new_object(),
              *messages = json_object_new_array(),
              *message = json_object_new_object(),
              *corpus = json_object_new_object(),
              *positions = json_object_new_array(),
              *expected = json_object_new_array();
  size_t at = strlen(head);
  memcpy(text, head, at);
  for (unsigned row = 0; row < records; ++row) {
    int needle = -1;
    for (unsigned i = 0; i < 3; ++i)
      if (row == rows[i])
        needle = (int)i;
    if (needle >= 0) {
      unsigned i = (unsigned)needle;
      json_object *position = json_object_new_object();
      nb_str(position, "key", keys[i]);
      nb_num(position, "record_index", row);
      nb_num(position, "prompt_byte_offset", (int64_t)at);
      nb_str(position, "region", i == 0 ? "start" : i == 1 ? "middle" : "end");
      json_object_array_add(positions, position);
      int n = snprintf(text + at, bytes - at, "binding %s = %s\n", keys[i],
                       values[i]);
      if (n < 0 || (size_t)n >= bytes - at)
        goto failed;
      at += (size_t)n;
    } else {
      char source[128], hash[65];
      snprintf(source, sizeof(source), "lie-long-context-v1:%" PRIu64 ":%u",
               seed, row);
      if (!nb_hash(source, strlen(source), hash))
        goto failed;
      for (unsigned i = 0; i < 8; ++i) {
        char part[7];
        memcpy(part, hash + 6 * i, 6);
        part[6] = 0;
        unsigned n = (unsigned)strtoul(part, NULL, 16) % 1000;
        snprintf(text + at, 5, "%03u%c", n, i == 7 ? '\n' : ' ');
        at += 4;
      }
    }
  }
  char query[256];
  if (turns == 2)
    snprintf(query, sizeof(query),
             "\nQuery keys: %s. Return only the JSON object.", keys[1]);
  else
    snprintf(query, sizeof(query),
             "\nQuery keys: %s, %s, %s. Return only the JSON object.", keys[0],
             keys[1], keys[2]);
  memcpy(text + at, query, strlen(query) + 1);
  nb_str(message, "role", "user");
  nb_str(message, "content", text);
  json_object_array_add(messages, message);
  message = NULL;
  nb_add(body, "messages", messages);
  nb_num(body, "max_tokens", budget);
  nb_add(item, "body", body);
  nb_str(item, "id", "recall");
  nb_str(corpus, "generator", "lie-associative-recall-v1");
  json_object_object_add(corpus, "seed", json_object_new_uint64(seed));
  nb_num(corpus, "records", records);
  nb_num(corpus, "prompt_bytes", (int64_t)(at + strlen(query)));
  nb_str(
      corpus, "kind",
      "synthetic associative recall; not natural-language or vendor quality");
  nb_str(corpus, "position_units",
         "zero-based record index and UTF-8 byte offset; not token offsets");
  nb_add(corpus, "needles", positions);
  nb_add(item, "corpus", corpus);
  if (turns == 2) {
    json_object *follow = json_object_new_array();
    snprintf(query, sizeof(query),
             "Using the original ledger, retrieve the two other keys: %s, %s. "
             "Return only their JSON object; omit the key answered previously.",
             keys[0], keys[2]);
    json_object_array_add(follow, json_object_new_string(query));
    nb_add(item, "followups", follow);
    json_object_put(follow);
    json_object_array_add(expected, oracle(keys, values, 1, 2));
    json_object *second = oracle(keys, values, 0, 1);
    nb_str(nb_get(second, "value"), keys[2], values[2]);
    json_object_array_add(expected, second);
  } else {
    json_object_array_add(expected, oracle(keys, values, 0, 3));
  }
  nb_add(item, "expected", expected);
  json_object_put(body);
  json_object_put(messages);
  json_object_put(corpus);
  json_object_put(positions);
  json_object_put(expected);
  free(text);
  return item;
failed:
  nb_fail(e, "Recall corpus construction failed");
  json_object_put(item);
  json_object_put(body);
  json_object_put(messages);
  json_object_put(message);
  json_object_put(corpus);
  json_object_put(positions);
  json_object_put(expected);
  free(text);
  return NULL;
hash_failed:
  nb_fail(e, "Recall corpus hashing failed");
  free(text);
  return NULL;
}

typedef struct {
  json_object *expected, *current;
  const char *reason;
  size_t members;
  bool opened, closed;
} score;
static bool value_event(void *context, const lie_json_event *event) {
  score *s = context;
  if (event->kind == LIE_JSON_BEGIN_OBJECT && !s->opened) {
    s->opened = true;
    return true;
  }
  if (event->kind == LIE_JSON_KEY && s->opened && !s->closed && !s->current) {
    json_object_object_foreach(s->expected, key, value) {
      if (strlen(key) == event->text_bytes &&
          !memcmp(key, event->text, event->text_bytes)) {
        s->current = value;
        return true;
      }
    }
    s->reason = "unexpected_key";
    return false;
  }
  if (event->kind == LIE_JSON_STRING && s->current) {
    if ((size_t)json_object_get_string_len(s->current) != event->text_bytes ||
        memcmp(json_object_get_string(s->current), event->text,
               event->text_bytes)) {
      s->reason = "wrong_value";
      return false;
    }
    s->current = NULL;
    ++s->members;
    return true;
  }
  if (event->kind == LIE_JSON_END_OBJECT && s->opened && !s->closed &&
      !s->current) {
    s->closed = true;
    if (s->members == (size_t)json_object_object_length(s->expected))
      return true;
    s->reason = "missing_key";
    return false;
  }
  s->reason = "flat_string_object_required";
  return false;
}

json_object *nb_recall_score(json_object *oracle_value, json_object *row,
                             nb_error *e) {
  if (!oracle_valid(oracle_value, e))
    return NULL;
  json_object *content = nb_get(nb_get(row, "assistant"), "content");
  const char *reason = "missing_response";
  bool pass = false;
  if (nb_get(nb_get(row, "assistant"), "tool_calls"))
    reason = "unexpected_tool_calls";
  else if (json_object_is_type(content, json_type_string)) {
    size_t bytes = (size_t)json_object_get_string_len(content);
    if (bytes > RECALL_RESPONSE_LIMIT)
      reason = "response_too_large";
    else {
      lie_json_parse_description description;
      lie_json_parse_description_init(&description);
      description.max_input_bytes = RECALL_RESPONSE_LIMIT;
      description.max_owned_bytes = 2 * RECALL_RESPONSE_LIMIT;
      description.max_work = 8 * RECALL_RESPONSE_LIMIT;
      description.max_depth = 8;
      score state = {.expected = nb_get(oracle_value, "value")};
      lie_json_sink sink = {&state, value_event};
      lie_json_parse_status rc =
          lie_json_parse_events(json_object_get_string(content), bytes,
                                &description, &sink, NULL, NULL);
      if (rc == LIE_JSON_PARSE_RESOURCE) {
        nb_fail(e, "Recall oracle allocation refused");
        return NULL;
      }
      pass = rc == LIE_JSON_PARSE_OK && state.closed;
      reason = pass           ? "exact_match"
               : state.reason ? state.reason
                              : "invalid_json";
    }
  }
  json_object *result = json_object_new_object();
  if (!result) {
    nb_fail(e, "Recall result allocation failed");
    return NULL;
  }
  nb_str(result, "kind", "json-object-exact");
  nb_str(result, "status", pass ? "PASS" : "FAIL");
  nb_str(result, "reason", reason);
  json_object_object_add(result, "pass", json_object_new_boolean(pass));
  nb_add(result, "expected", nb_get(oracle_value, "value"));
  json_object_object_add(result, "output_budget_reached",
                         json_object_new_boolean(!strcmp(
                             nb_string(row, "finish_reason"), "length")));
  return result;
}
