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
static const char *json_end(const char *p) {
  unsigned depth = 0;
  bool string = false, escape = false;
  for (; *p; ++p) {
    if (string) {
      if (escape)
        escape = false;
      else if (*p == '\\')
        escape = true;
      else if (*p == '"')
        string = false;
      continue;
    }
    if (*p == '"')
      string = true;
    else if (*p == '{' || *p == '[')
      ++depth;
    else if (*p == '}' || *p == ']') {
      if (!depth)
        return NULL;
      if (!--depth)
        return p + 1;
    }
  }
  return NULL;
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
  bool json_answer = false;
  const char *begin = copy;
  spaces(&begin);
  if (*begin == '{') {
    oj_node *answer = oj_parse(begin, strlen(begin));
    json_answer = answer && answer->type == OJ_OBJECT;
    oj_free(answer);
    if (json_answer)
      first = NULL;
  }
  size_t prose = first ? (size_t)(first - copy) : bytes;
  if (!first) {
    if (!json_answer && marker(copy))
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
      if (*cursor == '{') {
        const char *end = json_end(cursor);
        if (!end)
          goto fail;
        parsed = oj_parse(cursor, (size_t)(end - cursor));
        const oj_node *fn_name = oj_field(parsed, "name"),
                      *arguments = oj_field(parsed, "arguments");
        if (!parsed || parsed->type != OJ_OBJECT || !fn_name ||
            fn_name->type != OJ_STRING || !name_valid(fn_name->string) ||
            !arguments || arguments->type != OJ_OBJECT)
          goto fail;
        for (const oj_node *k = parsed->child; k; k = k->next->next)
          if (strcmp(k->string, "name") && strcmp(k->string, "arguments"))
            goto fail;
        const lie_chat_tool *fn = definition(policy, fn_name->string);
        if (!fn) {
          why = "unknown_tool_call";
          goto fail;
        }
        schema = oj_parse(fn->parameters_json, strlen(fn->parameters_json));
        if (!schema || !oj_schema_accepts(schema, arguments)) {
          why = "invalid_tool_arguments";
          goto fail;
        }
        char id[160];
        int n = snprintf(id, sizeof(id), "call-%s-%zu", identity, index);
        if (n < 0 || n > 128) {
          why = "tool_identity_too_long";
          goto fail;
        }
        lie_output_call *call = &t.calls[t.count++];
        call->id = strdup(id);
        call->name = strdup(fn_name->string);
        call->arguments_json = strndup(arguments->start, arguments->bytes);
        call->arguments_bytes = arguments->bytes;
        call->index = index;
        if (!call->id || !call->name || !call->arguments_json) {
          why = "allocation_failed";
          goto fail;
        }
        oj_free(parsed);
        parsed = NULL;
        oj_free(schema);
        schema = NULL;
        cursor = end;
        spaces(&cursor);
        if (!take(&cursor, "</tool_call>"))
          goto fail;
        continue;
      }
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
      if (!parsed || !args_valid(schema, parsed) ||
          !oj_schema_accepts(schema, parsed)) {
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

/* Conservative prefix binding. Complete calls use the authoritative parser;
 * JSON arguments retain their exact source bytes. The last
 * possible closing-tag suffix and one CR/LF are held, so later normalization
 * cannot retract bytes already emitted. Nullable/untyped strings wait for the
 * parameter close because their JSON representation is ambiguous until then. */
static bool preview_call(lie_output_turn *t, const char *identity,
                         const char *name, buffer *args) {
  size_t index = t->count;
  char id[160];
  int n = snprintf(id, sizeof(id), "call-%s-%zu", identity, index);
  if (n < 0 || n > 128 || index >= LIE_CHAT_MAX_CALLS)
    return false;
  lie_output_call *call = &t->calls[t->count++];
  call->id = strdup(id);
  call->name = strdup(name);
  call->arguments_json = args->data;
  call->arguments_bytes = args->bytes;
  call->index = index;
  args->data = NULL;
  args->bytes = args->capacity = 0;
  return call->id && call->name && call->arguments_json;
}
static const char *quoted_end(const char *s) {
  if (*s++ != '"')
    return NULL;
  for (; *s; ++s) {
    if (*s == '"')
      return s + 1;
    if (*s == '\\' && !*++s)
      return NULL;
  }
  return NULL;
}
/* Inspect only the outer frame's name/arguments fields. Keys inside nested
 * arguments or quoted text cannot be mistaken for the function name. If name
 * follows arguments, publication waits until the name is complete. */
static bool json_prefix(const char *s, char name[129], const char **arguments,
                        size_t *bytes) {
  bool named = false, args = false;
  name[0] = 0;
  *arguments = NULL;
  *bytes = 0;
  if (*s++ != '{')
    return false;
  for (;;) {
    spaces(&s);
    const char *end = quoted_end(s);
    if (!end || end - s > 1024)
      break;
    oj_node *key = oj_parse(s, (size_t)(end - s));
    bool is_name = key && !strcmp(key->string, "name"),
         is_args = key && !strcmp(key->string, "arguments");
    oj_free(key);
    s = end;
    spaces(&s);
    if (*s++ != ':' || (!is_name && !is_args))
      break;
    spaces(&s);
    if (is_name) {
      if (named)
        break;
      end = quoted_end(s);
      if (!end || end - s > 1024)
        break;
      oj_node *v = oj_parse(s, (size_t)(end - s));
      bool ok = v && v->type == OJ_STRING && name_valid(v->string);
      if (ok)
        strcpy(name, v->string);
      oj_free(v);
      if (!ok)
        break;
      named = true;
    } else {
      if (args || *s != '{')
        break;
      args = true;
      *arguments = s;
      end = json_end(s);
      *bytes = end ? (size_t)(end - s) : strlen(s);
      if (!end)
        break;
    }
    s = end;
    spaces(&s);
    if (*s != ',')
      break;
    ++s;
  }
  return named;
}
bool lie_output_preview(const lie_output_policy *p, const char *text,
                        size_t bytes, const char *identity,
                        lie_output_turn *out) {
  lie_output_turn t = {0};
  buffer args = {0};
  oj_node *schema = NULL;
  char *copy = NULL;
  const char *first = NULL;
  if (!p || !text || !identity || !out || out->count || out->text ||
      bytes > LIE_CHAT_BODY_BYTES || !lie_utf8_valid(text, bytes, false))
    return false;
  copy = strndup(text, bytes);
  if (!copy)
    return false;
  const char *cursor = copy;
  spaces(&cursor);
  /* A JSON text answer can contain literal tags; it is not a function frame. */
  if (*cursor == '{' || p->choice == LIE_TOOLS_NONE)
    goto done;
  cursor = strstr(copy, "<tool_call>");
  first = cursor;
  while (cursor && *cursor && t.count < LIE_CHAT_MAX_CALLS) {
    spaces(&cursor);
    if (!*cursor || (t.count && !p->parallel) ||
        strncmp(cursor, "<tool_call>", 11))
      break;
    const char *payload = cursor + 11;
    spaces(&payload);
    const char *closed = NULL;
    if (*payload == '{') {
      const char *end = json_end(payload);
      if (end) {
        spaces(&end);
        if (!strncmp(end, "</tool_call>", 12))
          closed = end;
      }
    } else
      closed = strstr(payload, "</tool_call>");
    if (closed) {
      lie_output_turn one = {0};
      char error[256];
      if (!lie_output_parse(p, cursor, (size_t)(closed + 12 - cursor), true,
                            identity, &one, error) ||
          one.count != 1) {
        lie_output_turn_clear(&one);
        break;
      }
      args.data = (char *)one.calls[0].arguments_json;
      args.bytes = one.calls[0].arguments_bytes;
      one.calls[0].arguments_json = NULL;
      bool ok = preview_call(&t, identity, one.calls[0].name, &args);
      lie_output_turn_clear(&one);
      if (!ok)
        goto fail;
      cursor = closed + 12;
      continue;
    }
    cursor += 11;
    spaces(&cursor);
    char name[129];
    if (*cursor == '{') {
      const char *raw = NULL;
      size_t n = 0;
      if (!json_prefix(cursor, name, &raw, &n) || !definition(p, name))
        break;
      if (!append(&args, raw ? raw : "", n) ||
          !preview_call(&t, identity, name, &args))
        goto fail;
      break;
    }
    if (!tag(&cursor, "<function=", name))
      break;
    const lie_chat_tool *fn = definition(p, name);
    if (!fn)
      break;
    schema = oj_parse(fn->parameters_json, strlen(fn->parameters_json));
    if (!schema || schema->type != OJ_OBJECT)
      break;
    const oj_node *props = oj_field(schema, "properties");
    if (!append(&args, "{", 1))
      goto fail;
    char keys[LIE_CHAT_MAX_ARGUMENTS][129];
    size_t count = 0;
    while (*cursor) {
      spaces(&cursor);
      if (!strncmp(cursor, "</function>", 11)) {
        if (!append(&args, "}", 1))
          goto fail;
        break;
      }
      char key[129];
      if (count >= LIE_CHAT_MAX_ARGUMENTS || !tag(&cursor, "<parameter=", key))
        break;
      bool duplicate = false;
      for (size_t i = 0; i < count; ++i)
        duplicate |= !strcmp(keys[i], key);
      if (duplicate)
        break;
      strcpy(keys[count], key);
      char *qkey = oj_quote(key, strlen(key));
      bool ok = qkey && (!count || append(&args, ",", 1)) &&
                append(&args, qkey, strlen(qkey)) && append(&args, ":", 1);
      free(qkey);
      if (!ok)
        goto fail;
      const char *end = strstr(cursor, "</parameter>");
      size_t n = end ? (size_t)(end - cursor) : strlen(cursor);
      if (!end) {
        const char *close = "</parameter>";
        for (size_t k = 11; k; k--)
          if (n >= k && !memcmp(cursor + n - k, close, k)) {
            n -= k;
            break;
          }
      }
      if (n && cursor[n - 1] == '\n') {
        --n;
        if (n && cursor[n - 1] == '\r')
          --n;
      } else if (!end && n && cursor[n - 1] == '\r')
        --n;
      const oj_node *s = oj_field(props, key);
      bool string = oj_type_is(s, "string"), nullable = oj_type_is(s, "null");
      char *value = NULL;
      if (end) {
        char *raw = strndup(cursor, n);
        if (!raw)
          goto fail;
        if (string && !(nullable && !strcmp(raw, "null")))
          value = oj_quote(raw, n);
        else {
          oj_node *v = oj_parse(raw, n);
          if (v) {
            value = strndup(v->start, v->bytes);
            oj_free(v);
          } else if (!oj_field(s, "type") && !oj_field(s, "anyOf") &&
                     !oj_field(s, "oneOf"))
            value = oj_quote(raw, n);
        }
        free(raw);
      } else if (n && string && !nullable) {
        value = oj_quote(cursor, n);
        if (value)
          value[strlen(value) - 1] = 0; /* Keep the opening quote. */
      } else if (n && !string &&
                 (oj_field(s, "type") || oj_field(s, "anyOf") ||
                  oj_field(s, "oneOf"))) {
        const char *raw = cursor;
        size_t leading = 0;
        while (leading < n && (raw[leading] == ' ' || raw[leading] == '\t' ||
                               raw[leading] == '\r' || raw[leading] == '\n'))
          ++leading;
        while (n > leading && (raw[n - 1] == ' ' || raw[n - 1] == '\t' ||
                               raw[n - 1] == '\r' || raw[n - 1] == '\n'))
          --n;
        value = strndup(raw + leading, n - leading);
      }
      if (!value)
        break;
      ok = append(&args, value, strlen(value));
      free(value);
      if (!ok)
        goto fail;
      if (!end)
        break;
      ++count;
      cursor = end + 12;
    }
    if (!preview_call(&t, identity, name, &args))
      goto fail;
    break;
  }
done:
  if (t.count && first) {
    t.bytes = (size_t)(first - copy);
    t.text = strndup(copy, t.bytes);
    if (!t.text)
      goto fail;
  }
  free(copy);
  free(args.data);
  oj_free(schema);
  *out = t;
  return true;
fail:
  free(copy);
  free(args.data);
  oj_free(schema);
  lie_output_turn_clear(&t);
  return false;
}
