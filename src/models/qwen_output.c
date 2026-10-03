/* SPDX-License-Identifier: MIT */
/* Qwen tag grammar moved out of HTTP. Neutral result, no executable callbacks.
 */
#include "../output_json.h"
#include "lie/output.h"
#include "lie/text.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void lie_output_turn_clear(lie_output_turn *t) {
  if (!t)
    return;
  free(t->text);
  for (size_t i = 0; i < t->count; ++i) {
    free((void *)t->calls[i].id);
    free((void *)t->calls[i].name);
    free((void *)t->calls[i].arguments_json);
  }
  memset(t, 0, sizeof(*t));
}
static void spaces(const char **s) {
  while (**s == ' ' || **s == '\t' || **s == '\r' || **s == '\n')
    ++*s;
}
static bool take(const char **s, const char *lit) {
  size_t n = strlen(lit);
  if (strncmp(*s, lit, n))
    return false;
  *s += n;
  return true;
}
static bool name_valid(const char *s) {
  if (!*s || strlen(s) > 128)
    return false;
  for (size_t i = 0; s[i]; ++i) {
    unsigned char c = (unsigned char)s[i];
    if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_' ||
          (i && ((c >= '0' && c <= '9') || c == '.' || c == '-'))))
      return false;
  }
  return true;
}
static bool tag(const char **s, const char *prefix, char out[129]) {
  if (!take(s, prefix))
    return false;
  const char *e = strchr(*s, '>');
  if (!e || e == *s || e - *s > 128)
    return false;
  size_t n = (size_t)(e - *s);
  memcpy(out, *s, n);
  out[n] = 0;
  if (!name_valid(out))
    return false;
  *s = e + 1;
  if (**s == '\r' && (*s)[1] == '\n')
    *s += 2;
  else if (**s == '\n')
    ++*s;
  return true;
}
static bool marker(const char *s) {
  return strstr(s, "<tool_call") || strstr(s, "</tool_call") ||
         strstr(s, "<function=") || strstr(s, "</function") ||
         strstr(s, "<parameter=") || strstr(s, "</parameter");
}
static const lie_chat_tool *definition(const lie_output_policy *p,
                                       const char *name) {
  if (p->choice == LIE_TOOLS_NONE ||
      (p->choice == LIE_TOOLS_NAMED && (!p->named || strcmp(p->named, name))))
    return NULL;
  for (size_t i = 0; i < p->tool_count; ++i)
    if (!strcmp(p->tools[i].name, name))
      return &p->tools[i];
  return NULL;
}
typedef struct {
  char *data;
  size_t bytes, capacity;
} buffer;
static bool append(buffer *b, const char *s, size_t n) {
  if (n > LIE_CHAT_BODY_BYTES - b->bytes)
    return false;
  size_t want = b->bytes + n + 1;
  if (want > b->capacity) {
    size_t c = b->capacity ? b->capacity : 256;
    while (c < want)
      c *= 2;
    if (c > LIE_CHAT_BODY_BYTES + 1u)
      c = LIE_CHAT_BODY_BYTES + 1u;
    char *p = realloc(b->data, c);
    if (!p)
      return false;
    b->data = p;
    b->capacity = c;
  }
  memcpy(b->data + b->bytes, s, n);
  b->bytes += n;
  b->data[b->bytes] = 0;
  return true;
}
static bool args_valid(const oj_node *schema, const oj_node *args) {
  const oj_node *req = oj_field(schema, "required"),
                *props = oj_field(schema, "properties");
  if (req) {
    if (req->type != OJ_ARRAY)
      return false;
    for (const oj_node *k = req->child; k; k = k->next)
      if (k->type != OJ_STRING || !oj_field(args, k->string))
        return false;
  }
  for (const oj_node *k = args->child; k; k = k->next->next) {
    const oj_node *v = k->next, *s = oj_field(props, k->string),
                  *extra = oj_field(schema, "additionalProperties");
    if (!s) {
      if (extra && extra->type == OJ_BOOL && !extra->boolean)
        return false;
      continue;
    }
    /* Enforce the same basic type/required gate for union schemas too. */
    if (!oj_field(s, "type") && !oj_field(s, "anyOf") && !oj_field(s, "oneOf"))
      continue;
    const char *types[] = {"null",   "boolean", "number",
                           "string", "array",   "object"};
    if (!oj_type_is(s, types[v->type]) &&
        !(v->type == OJ_NUMBER && oj_type_is(s, "integer") &&
          floor(v->number) == v->number))
      return false;
  }
  return true;
}
bool lie_output_parse(const lie_output_policy *policy, const char *text,
                      size_t bytes, bool complete, const char *identity,
                      lie_output_turn *out, char error[256]) {
  const char *why = "malformed_tool_output";
  lie_output_turn t = {0};
  char *copy = NULL;
  oj_node *schema = NULL, *parsed = NULL;
  buffer args = {0};
  if (!policy || !out || out->text || out->count || !text || !identity ||
      !error ||
      bytes > (size_t)LIE_CORE_MAX_OUTPUT * LIE_CORE_TOKEN_BYTES * 3 + 8 ||
      !lie_utf8_valid(text, bytes, false))
    goto fail;
  if (policy->tool_count > LIE_CHAT_MAX_TOOLS ||
      (policy->tool_count && !policy->tools) ||
      policy->choice < LIE_TOOLS_AUTO || policy->choice > LIE_TOOLS_NAMED) {
    why = "invalid_tool_schema";
    goto fail;
  }
  for (size_t i = 0; i < policy->tool_count; ++i) {
    if (!policy->tools[i].name || !name_valid(policy->tools[i].name) ||
        !policy->tools[i].parameters_json) {
      why = "invalid_tool_schema";
      goto fail;
    }
  }
  copy = malloc(bytes + 1);
  if (!copy) {
    why = "allocation_failed";
    goto fail;
  }
  memcpy(copy, text, bytes);
  copy[bytes] = 0;
  const char *first = strstr(copy, "<tool_call>");
  size_t prose = first ? (size_t)(first - copy) : bytes;
  if (!first) {
    if (marker(copy))
      goto fail;
    if (policy->choice >= LIE_TOOLS_REQUIRED) {
      why = "required_tool_call_missing";
      goto fail;
    }
  } else {
    if (!complete) {
      why = "truncated_tool_output";
      goto fail;
    }
    if (policy->choice == LIE_TOOLS_NONE) {
      why = "tool_call_disabled";
      goto fail;
    }
    char save = copy[prose];
    copy[prose] = 0;
    bool bad = marker(copy);
    copy[prose] = save;
    if (bad)
      goto fail;
    const char *cursor = first;
    for (;;) {
      spaces(&cursor);
      if (!*cursor)
        break;
      size_t index = t.count;
      if (index >= LIE_CHAT_MAX_CALLS || (index && !policy->parallel)) {
        why = "too_many_tool_calls";
        goto fail;
      }
      if (!take(&cursor, "<tool_call>"))
        goto fail;
      spaces(&cursor);
      char name[129];
      if (!tag(&cursor, "<function=", name))
        goto fail;
      const lie_chat_tool *fn = definition(policy, name);
      if (!fn) {
        why = "unknown_tool_call";
        goto fail;
      }
      schema = oj_parse(fn->parameters_json, strlen(fn->parameters_json));
      if (!schema || schema->type != OJ_OBJECT) {
        why = "invalid_tool_schema";
        goto fail;
      }
      const oj_node *props = oj_field(schema, "properties");
      if (!append(&args, "{", 1)) {
        why = "allocation_failed";
        goto fail;
      }
      char keys[LIE_CHAT_MAX_ARGUMENTS][129];
      size_t count = 0;
      for (;;) {
        spaces(&cursor);
        if (strncmp(cursor, "<parameter=", 11))
          break;
        char key[129];
        if (count >= LIE_CHAT_MAX_ARGUMENTS ||
            !tag(&cursor, "<parameter=", key))
          goto fail;
        for (size_t i = 0; i < count; ++i)
          if (!strcmp(keys[i], key))
            goto fail;
        strcpy(keys[count], key);
        const char *end = strstr(cursor, "</parameter>");
        if (!end)
          goto fail;
        size_t n = (size_t)(end - cursor);
        if (n && cursor[n - 1] == '\n') {
          --n;
          if (n && cursor[n - 1] == '\r')
            --n;
        }
        char *raw = strndup(cursor, n);
        if (!raw) {
          why = "allocation_failed";
          goto fail;
        }
        if (marker(raw)) {
          free(raw);
          goto fail;
        }
        const oj_node *s = oj_field(props, key);
        char *value = NULL;
        if (oj_type_is(s, "string") &&
            !(oj_type_is(s, "null") && !strcmp(raw, "null")))
          value = oj_quote(raw, n);
        else {
          parsed = oj_parse(raw, n);
          if (parsed) {
            value = strndup(parsed->start, parsed->bytes);
            oj_free(parsed);
            parsed = NULL;
          } else if (!oj_field(s, "type") && !oj_field(s, "anyOf") &&
                     !oj_field(s, "oneOf"))
            value = oj_quote(raw, n);
        }
        free(raw);
        if (!value) {
          why = "invalid_tool_arguments";
          goto fail;
        }
        char *qkey = oj_quote(key, strlen(key));
        bool ok = qkey && (!count || append(&args, ",", 1)) &&
                  append(&args, qkey, strlen(qkey)) && append(&args, ":", 1) &&
                  append(&args, value, strlen(value));
        free(qkey);
        free(value);
        if (!ok) {
          why = "allocation_failed";
          goto fail;
        }
        ++count;
        cursor = end + 12;
      }
      if (!take(&cursor, "</function>"))
        goto fail;
      spaces(&cursor);
      if (!take(&cursor, "</tool_call>"))
        goto fail;
      if (!append(&args, "}", 1)) {
        why = "allocation_failed";
        goto fail;
      }
      parsed = oj_parse(args.data, args.bytes);
      if (!parsed || !args_valid(schema, parsed)) {
        why = "invalid_tool_arguments";
        goto fail;
      }
      oj_free(parsed);
      parsed = NULL;
      oj_free(schema);
      schema = NULL;
      char id[160];
      int n = snprintf(id, sizeof(id), "call-%s-%zu", identity, index);
      if (n < 0 || n > 128) {
        why = "tool_identity_too_long";
        goto fail;
      }
      lie_output_call *call = &t.calls[t.count++];
      call->id = strdup(id);
      call->name = strdup(name);
      call->arguments_json = args.data;
      call->arguments_bytes = args.bytes;
      call->index = index;
      args = (buffer){0};
      if (!call->id || !call->name) {
        why = "allocation_failed";
        goto fail;
      }
    }
  }
  t.text = strndup(copy, prose);
  t.bytes = prose;
  if (!t.text) {
    why = "allocation_failed";
    goto fail;
  }
  free(copy);
  *out = t;
  error[0] = 0;
  return true;
fail:
  free(copy);
  free(args.data);
  oj_free(schema);
  oj_free(parsed);
  lie_output_turn_clear(&t);
  if (error)
    snprintf(error, 256, "%s", why);
  return false;
}
