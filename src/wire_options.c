/* SPDX-License-Identifier: MIT */
#include "lie/wire.h"
#include <json-c/json.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static json_object *probability(const lie_token_probability *p) {
  lie_utf8_decoder decoder = {0};
  char text[LIE_CORE_TOKEN_BYTES * 3 + 8];
  size_t bytes = 0;
  if (p->bytes > sizeof(p->text) ||
      !lie_utf8_feed(&decoder, p->text, p->bytes, true, text, sizeof(text),
                     &bytes))
    return NULL;
  json_object *o = json_object_new_object(), *raw = json_object_new_array();
  json_object_object_add(o, "token",
                         json_object_new_string_len(text, (int)bytes));
  json_object_object_add(o, "logprob", json_object_new_double(p->logprob));
  for (size_t i = 0; i < p->bytes; ++i)
    json_object_array_add(raw, json_object_new_int((unsigned char)p->text[i]));
  json_object_object_add(o, "bytes", raw);
  return o;
}
json_object *lie_wire_logprobs(lie_job *job, size_t offset, size_t count) {
  lie_token_logprobs score;
  if (count && lie_job_logprob(job, offset, &score) != LIE_OK)
    return NULL;
  json_object *array = json_object_new_array();
  for (size_t i = 0; i < count; ++i) {
    if (lie_job_logprob(job, offset + i, &score) != LIE_OK) {
      json_object_put(array);
      return NULL;
    }
    if(!score.token.bytes)continue;
    json_object *token = probability(&score.token),
                *top = json_object_new_array();
    if (!token) {
      json_object_put(array);
      json_object_put(top);
      return NULL;
    }
    for (unsigned k = 0; k < score.top_count; ++k) {
      json_object *p = probability(&score.top[k]);
      if (!p) {
        json_object_put(token);
        json_object_put(top);
        json_object_put(array);
        return NULL;
      }
      json_object_array_add(top, p);
    }
    json_object_object_add(token, "top_logprobs", top);
    json_object_array_add(array, token);
  }
  return array;
}
char *lie_wire_reindex(char *owned, unsigned index, bool keep_done) {
  if (!owned)
    return NULL;
  bool stream = !strncmp(owned, "data: ", 6);
  size_t capacity = strlen(owned) + 256, length = 0;
  char *out = malloc(capacity);
  if (!out) {
    free(owned);
    return NULL;
  }
  const char *p = owned;
  do {
    const char *end = stream ? strstr(p, "\n\n") : p + strlen(p);
    if (!end) {
      free(out);
      free(owned);
      return NULL;
    }
    size_t bytes = (size_t)(end - p);
    if (stream && bytes == 12 && !memcmp(p, "data: [DONE]", 12)) {
      if (keep_done) {
        memcpy(out + length, "data: [DONE]\n\n", 14);
        length += 14;
      }
    } else {
      char *text = strndup(p + (stream ? 6 : 0), bytes - (stream ? 6 : 0));
      json_object *object = text ? json_tokener_parse(text) : NULL;
      free(text);
      if (!object) {
        free(out);
        free(owned);
        return NULL;
      }
      json_object *choices = NULL;
      if (json_object_object_get_ex(object, "choices", &choices))
        for (size_t i = 0; i < json_object_array_length(choices); ++i)
          json_object_object_add(json_object_array_get_idx(choices, i), "index",
                                 json_object_new_int64(index));
      const char *json =
          json_object_to_json_string_ext(object, JSON_C_TO_STRING_PLAIN);
      size_t n = strlen(json) + (stream ? 8 : 0);
      if (length + n + 1 > capacity) {
        capacity = length + n + 256;
        char *next = realloc(out, capacity);
        if (!next) {
          json_object_put(object);
          free(out);
          free(owned);
          return NULL;
        }
        out = next;
      }
      if (stream) {
        memcpy(out + length, "data: ", 6);
        length += 6;
      }
      memcpy(out + length, json, strlen(json));
      length += strlen(json);
      if (stream) {
        memcpy(out + length, "\n\n", 2);
        length += 2;
      }
      json_object_put(object);
    }
    p = stream ? end + 2 : end;
  } while (*p);
  out[length] = 0;
  free(owned);
  return out;
}
