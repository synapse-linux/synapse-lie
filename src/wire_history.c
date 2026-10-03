/* SPDX-License-Identifier: MIT */
#include "lie/responses.h"
#include "lie/tools.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static json_object *get(json_object *o, const char *k) {
  json_object *v = NULL;
  json_object_object_get_ex(o, k, &v);
  return v;
}
json_object *lie_response_input_items(const lie_core_request *r, size_t skip) {
  json_object *messages = lie_chat_history_json(r),
              *items = json_object_new_array();
  if (!messages) {
    json_object_put(items);
    return NULL;
  }
  for (size_t i = skip; i < json_object_array_length(messages); ++i) {
    json_object *m = json_object_array_get_idx(messages, i),
                *content = get(m, "content"), *calls = get(m, "tool_calls");
    if (lie_json_literal(get(m, "role"), "tool")) {
      json_object *item = json_object_new_object();
      json_object_object_add(item, "type",
                             json_object_new_string("function_call_output"));
      json_object_object_add(item, "call_id",
                             json_object_get(get(m, "tool_call_id")));
      json_object_object_add(item, "output", json_object_get(content));
      json_object_array_add(items, item);
      continue;
    }
    if (!calls || json_object_get_string_len(content)) {
      json_object *item = json_object_new_object(),
                  *parts = json_object_new_array();
      json_object_object_add(item, "type", json_object_new_string("message"));
      json_object_object_add(item, "role", json_object_get(get(m, "role")));
      json_object_object_add(item, "content", parts);
      if (json_object_is_type(content, json_type_string)) {
        json_object *part = json_object_new_object();
        json_object_object_add(part, "type",
                               json_object_new_string("input_text"));
        json_object_object_add(part, "text", json_object_get(content));
        json_object_array_add(parts, part);
      } else
        for (size_t k = 0; k < json_object_array_length(content); ++k) {
          json_object *part = json_object_array_get_idx(content, k),
                      *p = json_object_new_object();
          if (lie_json_literal(get(part, "type"), "text")) {
            json_object_object_add(p, "type",
                                   json_object_new_string("input_text"));
            json_object_object_add(p, "text",
                                   json_object_get(get(part, "text")));
          } else {
            json_object *image = get(part, "image_url");
            json_object_object_add(p, "type",
                                   json_object_new_string("input_image"));
            json_object_object_add(p, "image_url",
                                   json_object_get(get(image, "url")));
            if (get(image, "detail"))
              json_object_object_add(p, "detail",
                                     json_object_get(get(image, "detail")));
          }
          json_object_array_add(parts, p);
        }
      json_object_array_add(items, item);
    }
    for (size_t k = 0; calls && k < json_object_array_length(calls); ++k) {
      json_object *call = json_object_array_get_idx(calls, k),
                  *fn = get(call, "function"), *item = json_object_new_object();
      json_object_object_add(item, "type",
                             json_object_new_string("function_call"));
      json_object_object_add(item, "call_id", json_object_get(get(call, "id")));
      json_object_object_add(item, "name", json_object_get(get(fn, "name")));
      json_object_object_add(item, "arguments",
                             json_object_get(get(fn, "arguments")));
      json_object_object_add(item, "status",
                             json_object_new_string("completed"));
      json_object_array_add(items, item);
    }
  }
  json_object_put(messages);
  return items;
}
static int hex(char c) {
  if (c >= '0' && c <= '9')
    return c - '0';
  if (c >= 'A' && c <= 'F')
    return c - 'A' + 10;
  if (c >= 'a' && c <= 'f')
    return c - 'a' + 10;
  return -1;
}
static bool decode(char *s) {
  char *out = s;
  for (char *p = s; *p; ++p) {
    if (*p == '%') {
      if (!p[1] || !p[2] || hex(p[1]) < 0 || hex(p[2]) < 0)
        return false;
      char c = (char)(hex(p[1]) * 16 + hex(p[2]));
      if (!c || c < ' ')
        return false;
      *out++ = c;
      p += 2;
    } else
      *out++ = *p == '+' ? ' ' : *p;
  }
  *out = 0;
  return lie_utf8_valid(s, strlen(s), false);
}
bool lie_response_retrieve_query(const char *query, bool *stream,
                                 int64_t *after) {
  if (!stream || !after)
    return false;
  *stream = false;
  *after = -1;
  bool seen_stream = false, seen_after = false, ok = true;
  char *copy = query ? strdup(query) : NULL, *save = NULL;
  if (query && !copy)
    return false;
  for (char *part = copy ? strtok_r(copy, "&", &save) : NULL; part;
       part = strtok_r(NULL, "&", &save)) {
    char *v = strchr(part, '=');
    if (!v) {
      ok = false;
      break;
    }
    *v++ = 0;
    if (!decode(part) || !decode(v)) {
      ok = false;
      break;
    }
    if (!strcmp(part, "stream")) {
      if (seen_stream || (strcmp(v, "true") && strcmp(v, "false"))) {
        ok = false;
        break;
      }
      seen_stream = true;
      *stream = !strcmp(v, "true");
    } else if (!strcmp(part, "starting_after")) {
      if (seen_after || !*v) {
        ok = false;
        break;
      }
      seen_after = true;
      uint64_t n = 0;
      for (char *p = v; *p; ++p) {
        if (*p < '0' || *p > '9' ||
            n > ((uint64_t)INT64_MAX - (unsigned)(*p - '0')) / 10) {
          ok = false;
          break;
        }
        n = n * 10 + (unsigned)(*p - '0');
      }
      if (!ok)
        break;
      *after = (int64_t)n;
    } else {
      ok = false;
      break;
    }
  }
  free(copy);
  return ok && (!seen_after || *stream);
}
char *lie_response_since(char *owned, int64_t after) {
  if (!owned || after < 0)
    return owned;
  size_t written = 0;
  for (char *p = owned; *p;) {
    char *end = strstr(p, "\n\n"), *data = strstr(p, "data: ");
    if (!end || !data || data >= end) {
      free(owned);
      return NULL;
    }
    char *raw = strndup(data + 6, (size_t)(end - data - 6));
    json_object *o = raw ? json_tokener_parse(raw) : NULL;
    free(raw);
    json_object *sequence = get(o, "sequence_number");
    if (!o || !json_object_is_type(sequence, json_type_int)) {
      json_object_put(o);
      free(owned);
      return NULL;
    }
    size_t n = (size_t)(end + 2 - p);
    if (json_object_get_int64(sequence) > after) {
      memmove(owned + written, p, n);
      written += n;
    }
    json_object_put(o);
    p = end + 2;
  }
  owned[written] = 0;
  return owned;
}
json_object *lie_wire_page(json_object *items, const char *query,
                           bool completions, char error[256]) {
  char *copy = query ? strdup(query) : NULL, *save = NULL, *after = NULL;
  unsigned limit = 20;
  const char *model = NULL, *metadata_key[16], *metadata_value[16];
  size_t metadata_count = 0;
  json_object *filtered = NULL;
  bool descending = !completions, seen_limit = false, seen_order = false;
  if (query && !copy)
    return NULL;
  for (char *part = copy ? strtok_r(copy, "&", &save) : NULL; part;
       part = strtok_r(NULL, "&", &save)) {
    char *value = strchr(part, '=');
    if (!value)
      goto invalid;
    *value++ = 0;
    if (!decode(part) || !decode(value))
      goto invalid;
    if (!strcmp(part, "limit")) {
      if (seen_limit || !*value)
        goto invalid;
      seen_limit = true;
      unsigned n = 0;
      for (char *p = value; *p; ++p) {
        if (*p < '0' || *p > '9' || n > 100)
          goto invalid;
        n = n * 10 + (unsigned)(*p - '0');
      }
      if (!n || n > 100)
        goto invalid;
      limit = n;
    } else if (!strcmp(part, "order")) {
      if (seen_order)
        goto invalid;
      seen_order = true;
      if (!strcmp(value, "desc"))
        descending = true;
      else if (strcmp(value, "asc"))
        goto invalid;
    } else if (!strcmp(part, "after")) {
      if (after || !*value)
        goto invalid;
      after = value;
    } else if (completions && !strcmp(part, "model")) {
      if (model || !*value || strlen(value) > 256)
        goto invalid;
      model = value;
    } else if (completions && !strncmp(part, "metadata[", 9)) {
      size_t n = strlen(part);
      if (n < 11 || part[n - 1] != ']' || n - 10 > 64 || strlen(value) > 512 ||
          metadata_count >= 16)
        goto invalid;
      part[n - 1] = 0;
      const char *key = part + 9;
      for (size_t i = 0; i < metadata_count; ++i)
        if (!strcmp(metadata_key[i], key))
          goto invalid;
      metadata_key[metadata_count] = key;
      metadata_value[metadata_count++] = value;
    } else
      goto invalid;
  }
  if (model || metadata_count) {
    filtered = json_object_new_array();
    if (!filtered)
      goto invalid;
    for (size_t i = 0; i < json_object_array_length(items); ++i) {
      json_object *item = json_object_array_get_idx(items, i);
      if (!lie_json_literal(get(item, "object"), "chat.completion"))
        goto invalid;
      bool match = !model || lie_json_literal(get(item, "model"), model);
      for (size_t k = 0; k < metadata_count && match; ++k)
        match = lie_json_literal(get(get(item, "metadata"), metadata_key[k]),
                                 metadata_value[k]);
      if (match)
        json_object_array_add(filtered, json_object_get(item));
    }
    items = filtered;
  }
  size_t count = json_object_array_length(items), start = 0;
  if (after) {
    bool found = false;
    for (size_t k = 0; k < count; ++k) {
      size_t i = descending ? count - 1 - k : k;
      json_object *id = get(json_object_array_get_idx(items, i), "id");
      if (lie_json_literal(id, after)) {
        start = k + 1;
        found = true;
        break;
      }
    }
    if (!found)
      goto invalid;
  }
  json_object *out = json_object_new_object(), *page = json_object_new_array();
  size_t n = count - start;
  if (n > limit)
    n = limit;
  for (size_t k = 0; k < n; ++k) {
    size_t i = descending ? count - 1 - start - k : start + k;
    json_object_array_add(page,
                          json_object_get(json_object_array_get_idx(items, i)));
  }
  json_object_object_add(out, "object", json_object_new_string("list"));
  json_object_object_add(out, "data", page);
  json_object_object_add(out, "has_more",
                         json_object_new_boolean(start + n < count));
  json_object_object_add(
      out, "first_id",
      n ? json_object_get(get(json_object_array_get_idx(page, 0), "id"))
        : NULL);
  json_object_object_add(
      out, "last_id",
      n ? json_object_get(get(json_object_array_get_idx(page, n - 1), "id"))
        : NULL);
  json_object_put(filtered);
  free(copy);
  error[0] = 0;
  return out;
invalid:
  json_object_put(filtered);
  free(copy);
  snprintf(error, 256, "invalid_pagination");
  return NULL;
}
