/* SPDX-License-Identifier: MIT */
/* Finite-value and container algorithms follow independently pinned Gufo;
 * third_party/gufo-NOTICE records scope, license and retained leaf policies. */
#include "lie/schema_values.h"
#include "schema_internal.h"
#include <limits.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>
#define TRY(call)                                                              \
  do {                                                                         \
    lie_schema_status rc_ = (call);                                            \
    if (rc_)                                                                   \
      return rc_;                                                              \
  } while (0)
#define BYTE(c) (LIE_GRAMMAR_TERMINAL | (uint8_t)(c))
typedef struct {
  lie_schema_context shared;
  const lie_schema_values_description *d;
} values_context;
static bool valid(const lie_schema_values_description *d) {
  return d && d->abi_version == LIE_SCHEMA_VALUES_ABI &&
         d->struct_bytes == sizeof(*d) && d->max_depth <= 256 &&
         lie_schema_internal_valid(&d->transform);
}
static lie_schema_status fail(values_context *c, lie_schema_status rc,
                              const char *s) {
  return lie_schema_internal_fail(&c->shared, rc, s);
}
static bool text_is(lie_schema_bytes text, const char *s) {
  const size_t n = strlen(s);
  return text.size == n && (!n || !memcmp(text.data, s, n));
}
static bool matches(lie_schema_value v, lie_schema_bytes type) {
  if (text_is(type, "object"))
    return v.kind == LIE_SCHEMA_OBJECT;
  if (text_is(type, "array"))
    return v.kind == LIE_SCHEMA_ARRAY;
  if (text_is(type, "string"))
    return v.kind == LIE_SCHEMA_STRING;
  if (text_is(type, "boolean"))
    return v.kind == LIE_SCHEMA_BOOL;
  if (text_is(type, "null"))
    return v.kind == LIE_SCHEMA_NULL;
  if (text_is(type, "number"))
    return v.kind == LIE_SCHEMA_NUMBER;
  return text_is(type, "integer") && v.kind == LIE_SCHEMA_NUMBER &&
         floor(v.number) == v.number;
}
static size_t size_value(lie_schema_value v) {
  if (v.kind != LIE_SCHEMA_NUMBER || !isfinite(v.number) || v.number < 0 ||
      floor(v.number) != v.number ||
      v.number >= ldexp(1.0, (int)(CHAR_BIT * sizeof(size_t))))
    return 0;
  return (size_t)v.number;
}
static lie_schema_status normalize(values_context *c, lie_schema_node root,
                                   lie_schema_node schema,
                                   lie_schema_node value, size_t depth,
                                   lie_schema_normalized *out) {
  lie_schema_context *s = &c->shared;
  if (depth > c->d->max_depth)
    return fail(c, LIE_SCHEMA_INVALID,
                "enum/const reference expansion exceeds its resource budget");
  lie_schema_node result;
  TRY(lie_schema_internal_clone(s, value, &result));
  lie_schema_node ref;
  TRY(lie_schema_internal_field(s, schema, "$ref", &ref));
  if (ref) {
    lie_schema_node target;
    TRY(lie_schema_internal_reference(s, root, ref, &target));
    lie_schema_normalized n;
    TRY(normalize(c, root, target, value, depth + 1, &n));
    if (!n.matched) {
      *out = (lie_schema_normalized){false, NULL};
      return LIE_SCHEMA_OK;
    }
    result = n.value;
  }
  lie_schema_node any;
  TRY(lie_schema_internal_field(s, schema, "anyOf", &any));
  if (any) {
    lie_schema_value av;
    TRY(lie_schema_internal_describe(s, any, &av));
    bool matched = false;
    if (av.kind == LIE_SCHEMA_ARRAY)
      for (size_t i = 0; i < av.count; ++i) {
        lie_schema_bytes ignored;
        lie_schema_node branch;
        TRY(lie_schema_internal_child(s, any, i, &ignored, &branch));
        lie_schema_normalized n;
        const lie_schema_status rc =
            normalize(c, root, branch, value, depth + 1, &n);
        if (rc == LIE_SCHEMA_EMPTY)
          continue;
        if (rc)
          return rc;
        if (n.matched) {
          result = n.value;
          matched = true;
          break;
        }
      }
    if (!matched) {
      *out = (lie_schema_normalized){false, NULL};
      return LIE_SCHEMA_OK;
    }
  }
  lie_schema_value vv;
  TRY(lie_schema_internal_describe(s, value, &vv));
  lie_schema_node type;
  TRY(lie_schema_internal_field(s, schema, "type", &type));
  if (type) {
    lie_schema_value tv;
    TRY(lie_schema_internal_describe(s, type, &tv));
    bool matched = false;
    if (tv.kind == LIE_SCHEMA_STRING)
      matched = matches(vv, tv.text);
    else if (tv.kind == LIE_SCHEMA_ARRAY)
      for (size_t i = 0; i < tv.count; ++i) {
        lie_schema_bytes ignored;
        lie_schema_node child;
        TRY(lie_schema_internal_child(s, type, i, &ignored, &child));
        lie_schema_value v;
        TRY(lie_schema_internal_describe(s, child, &v));
        if (matches(vv, v.kind == LIE_SCHEMA_STRING
                            ? v.text
                            : (lie_schema_bytes){NULL, 0})) {
          matched = true;
          break;
        }
      }
    if (!matched) {
      *out = (lie_schema_normalized){false, NULL};
      return LIE_SCHEMA_OK;
    }
  }
  lie_schema_node enumeration;
  TRY(lie_schema_internal_field(s, schema, "enum", &enumeration));
  if (enumeration) {
    lie_schema_value ev;
    TRY(lie_schema_internal_describe(s, enumeration, &ev));
    bool matched = false;
    if (ev.kind == LIE_SCHEMA_ARRAY)
      for (size_t i = 0; i < ev.count; ++i) {
        lie_schema_bytes ignored;
        lie_schema_node n;
        TRY(lie_schema_internal_child(s, enumeration, i, &ignored, &n));
        TRY(lie_schema_internal_equal(s, value, n, &matched));
        if (matched)
          break;
      }
    if (!matched) {
      *out = (lie_schema_normalized){false, NULL};
      return LIE_SCHEMA_OK;
    }
  }
  lie_schema_node constant;
  TRY(lie_schema_internal_field(s, schema, "const", &constant));
  if (constant) {
    bool same;
    TRY(lie_schema_internal_equal(s, value, constant, &same));
    if (!same) {
      *out = (lie_schema_normalized){false, NULL};
      return LIE_SCHEMA_OK;
    }
  }
  if (vv.kind == LIE_SCHEMA_STRING || vv.kind == LIE_SCHEMA_NUMBER) {
    bool accepted = false;
    TRY(lie_schema_internal_tick(s, 1));
    const lie_schema_status rc =
        c->d->accept(c->d->leaf_context, schema, value, &accepted);
    if (rc) {
      if (rc == LIE_SCHEMA_EMPTY && s->error)
        *s->error = (lie_schema_error){0};
      return rc;
    }
    if (!accepted) {
      *out = (lie_schema_normalized){false, NULL};
      return LIE_SCHEMA_OK;
    }
  } else if (vv.kind == LIE_SCHEMA_ARRAY) {
    const char *names[] = {"minItems", "maxItems"};
    for (size_t i = 0; i < 2; ++i) {
      lie_schema_node bound;
      TRY(lie_schema_internal_field(s, schema, names[i], &bound));
      if (bound) {
        lie_schema_value bv;
        TRY(lie_schema_internal_describe(s, bound, &bv));
        const size_t n = size_value(bv);
        if (i ? vv.count > n : vv.count < n) {
          *out = (lie_schema_normalized){false, NULL};
          return LIE_SCHEMA_OK;
        }
      }
    }
    lie_schema_node items;
    TRY(lie_schema_internal_field(s, schema, "items", &items));
    if (items) {
      TRY(lie_schema_internal_create(
          s, (lie_schema_value){.kind = LIE_SCHEMA_ARRAY}, &result));
      for (size_t i = 0; i < vv.count; ++i) {
        lie_schema_bytes ignored;
        lie_schema_node n;
        TRY(lie_schema_internal_child(s, value, i, &ignored, &n));
        lie_schema_normalized child;
        TRY(normalize(c, root, items, n, depth + 1, &child));
        if (!child.matched) {
          *out = (lie_schema_normalized){false, NULL};
          return LIE_SCHEMA_OK;
        }
        TRY(lie_schema_internal_append(s, result, child.value));
      }
    }
  } else if (vv.kind == LIE_SCHEMA_OBJECT) {
    lie_schema_node required;
    TRY(lie_schema_internal_field(s, schema, "required", &required));
    if (required) {
      lie_schema_value rv;
      TRY(lie_schema_internal_describe(s, required, &rv));
      if (rv.kind == LIE_SCHEMA_ARRAY)
        for (size_t i = 0; i < rv.count; ++i) {
          lie_schema_bytes ignored;
          lie_schema_node n, found;
          TRY(lie_schema_internal_child(s, required, i, &ignored, &n));
          lie_schema_value nv;
          TRY(lie_schema_internal_describe(s, n, &nv));
          TRY(lie_schema_internal_find(s, value,
                                       nv.kind == LIE_SCHEMA_STRING
                                           ? nv.text
                                           : (lie_schema_bytes){NULL, 0},
                                       &found));
          if (!found) {
            *out = (lie_schema_normalized){false, NULL};
            return LIE_SCHEMA_OK;
          }
        }
    }
    lie_schema_node properties, additional;
    TRY(lie_schema_internal_field(s, schema, "properties", &properties));
    TRY(lie_schema_internal_field(s, schema, "additionalProperties",
                                  &additional));
    bool closed = false;
    if (additional) {
      lie_schema_value av;
      TRY(lie_schema_internal_describe(s, additional, &av));
      closed = !(av.kind == LIE_SCHEMA_BOOL && av.boolean);
    }
    if (properties || closed) {
      TRY(lie_schema_internal_create(
          s, (lie_schema_value){.kind = LIE_SCHEMA_OBJECT}, &result));
      if (properties) {
        lie_schema_value pv;
        TRY(lie_schema_internal_describe(s, properties, &pv));
        if (pv.kind == LIE_SCHEMA_OBJECT)
          for (size_t i = 0; i < pv.count; ++i) {
            lie_schema_bytes name;
            lie_schema_node child, item;
            TRY(lie_schema_internal_child(s, properties, i, &name, &child));
            TRY(lie_schema_internal_find(s, value, name, &item));
            if (item) {
              lie_schema_normalized n;
              TRY(normalize(c, root, child, item, depth + 1, &n));
              if (!n.matched) {
                *out = (lie_schema_normalized){false, NULL};
                return LIE_SCHEMA_OK;
              }
              TRY(lie_schema_internal_put(s, result, name, n.value));
            }
          }
      }
      for (size_t i = 0; i < vv.count; ++i) {
        lie_schema_bytes name;
        lie_schema_node item, known = NULL;
        TRY(lie_schema_internal_child(s, value, i, &name, &item));
        if (properties)
          TRY(lie_schema_internal_find(s, properties, name, &known));
        if (!known) {
          if (closed) {
            *out = (lie_schema_normalized){false, NULL};
            return LIE_SCHEMA_OK;
          }
          TRY(lie_schema_internal_put(s, result, name, item));
        }
      }
    }
  }
  *out = (lie_schema_normalized){true, result};
  return LIE_SCHEMA_OK;
}
static lie_schema_status characters(values_context *c, lie_schema_bytes text,
                                    size_t *total) {
  if (text.size && !text.data)
    return fail(c, LIE_SCHEMA_INVALID, "invalid string view");
  TRY(lie_schema_internal_tick(&c->shared, text.size));
  size_t count = 0;
  for (size_t i = 0; i < text.size; ++i)
    if (((unsigned char)text.data[i] & 0xc0) != 0x80)
      ++count;
  if (count > c->d->max_characters - *total)
    return fail(c, LIE_SCHEMA_INVALID,
                "property/definition names and enum/const strings exceed "
                "120000 characters");
  *total += count;
  return LIE_SCHEMA_OK;
}
typedef struct {
  lie_schema_node n;
  size_t next;
  lie_schema_value value;
} count_frame;
static lie_schema_status count_value(values_context *c, lie_schema_node n,
                                     size_t *out) {
  lie_schema_context *s = &c->shared;
  const size_t limit = c->d->max_depth + 1;
  count_frame local[16], *stack = local;
  size_t capacity = limit < 16 ? limit : 16;
  size_t depth = 1, total = 0;
  stack[0] = (count_frame){.n = n};
  lie_schema_status rc = lie_schema_internal_describe(s, n, &stack[0].value);
  while (!rc && depth) {
    count_frame *f = &stack[depth - 1];
    if (f->value.kind == LIE_SCHEMA_STRING) {
      rc = characters(c, f->value.text, &total);
      --depth;
    } else if ((f->value.kind != LIE_SCHEMA_OBJECT &&
                f->value.kind != LIE_SCHEMA_ARRAY) ||
               f->next == f->value.count)
      --depth;
    else {
      lie_schema_bytes key;
      lie_schema_node child;
      rc = lie_schema_internal_child(s, f->n, f->next++, &key, &child);
      if (rc)
        break;
      if (f->value.kind == LIE_SCHEMA_OBJECT) {
        rc = characters(c, key, &total);
        if (rc)
          break;
      }
      if (depth == limit) {
        rc = fail(c, LIE_SCHEMA_INVALID,
                  "enum/const value nesting exceeds its resource budget");
        break;
      }
      if (depth == capacity) {
        const size_t next = capacity * 2 < limit ? capacity * 2 : limit;
        count_frame *grown =
            lie_schema_internal_allocate(s, next * sizeof(*grown));
        if (!grown) {
          rc = fail(c, LIE_SCHEMA_RESOURCE,
                    "value character stack allocation failed");
          break;
        }
        memcpy(grown, stack, depth * sizeof(*grown));
        if (stack != local)
          lie_schema_internal_release(s, stack);
        stack = grown;
        capacity = next;
      }
      stack[depth] = (count_frame){.n = child};
      rc = lie_schema_internal_describe(s, child, &stack[depth].value);
      ++depth;
    }
  }
  if (stack != local)
    lie_schema_internal_release(s, stack);
  if (!rc)
    *out = total;
  return rc;
}
static lie_schema_status builder_status(values_context *c,
                                        lie_builder_status rc) {
  switch (rc) {
  case LIE_BUILDER_OK:
    return LIE_SCHEMA_OK;
  case LIE_BUILDER_RESOURCE:
    return fail(c, LIE_SCHEMA_RESOURCE,
                "grammar construction allocation failed");
  case LIE_BUILDER_RULE_LIMIT:
    return fail(c, LIE_SCHEMA_INVALID,
                "compiled grammar exceeds the rule limit");
  case LIE_BUILDER_WORK_LIMIT:
    return fail(c, LIE_SCHEMA_WORK_LIMIT, "construction work limit exceeded");
  case LIE_BUILDER_EMPTY:
    return fail(c, LIE_SCHEMA_EMPTY, "schema has no finite value");
  case LIE_BUILDER_CYCLE:
    return fail(c, LIE_SCHEMA_INVALID,
                "reference cycle does not consume input");
  default:
    return fail(c, LIE_SCHEMA_INVALID, "invalid C17 grammar construction");
  }
}
static lie_schema_status quote(values_context *c, lie_grammar_builder *b,
                               lie_schema_bytes text, uint32_t *out) {
  if (text.size && !text.data)
    return fail(c, LIE_SCHEMA_INVALID, "invalid string view");
  TRY(lie_schema_internal_tick(&c->shared, text.size));
  size_t bytes = 2;
  for (size_t i = 0; i < text.size; ++i) {
    const unsigned char ch = (unsigned char)text.data[i];
    const size_t n = (ch == '"' || ch == '\\' || ch == '\b' || ch == '\f' ||
                      ch == '\n' || ch == '\r' || ch == '\t')
                         ? 2
                     : ch < 32 ? 6
                               : 1;
    if (n > SIZE_MAX - bytes)
      return fail(c, LIE_SCHEMA_RESOURCE, "quoted value storage overflow");
    bytes += n;
  }
  char local[128], *p = bytes <= sizeof(local)
                            ? local
                            : lie_schema_internal_allocate(&c->shared, bytes);
  if (!p)
    return fail(c, LIE_SCHEMA_RESOURCE, "quoted value allocation failed");
  static const char hex[] = "0123456789abcdef";
  size_t at = 0;
  p[at++] = '"';
  for (size_t i = 0; i < text.size; ++i) {
    const unsigned char ch = (unsigned char)text.data[i];
    char escaped = 0;
    switch (ch) {
    case '"':
      escaped = '"';
      break;
    case '\\':
      escaped = '\\';
      break;
    case '\b':
      escaped = 'b';
      break;
    case '\f':
      escaped = 'f';
      break;
    case '\n':
      escaped = 'n';
      break;
    case '\r':
      escaped = 'r';
      break;
    case '\t':
      escaped = 't';
      break;
    default:
      break;
    }
    if (escaped) {
      p[at++] = '\\';
      p[at++] = escaped;
    } else if (ch < 32) {
      p[at++] = '\\';
      p[at++] = 'u';
      p[at++] = '0';
      p[at++] = '0';
      p[at++] = hex[ch >> 4];
      p[at++] = hex[ch & 15];
    } else
      p[at++] = (char)ch;
  }
  p[at++] = '"';
  const lie_builder_status rc =
      lie_builder_literal(b, (const uint8_t *)p, at, out);
  if (p != local)
    lie_schema_internal_release(&c->shared, p);
  return builder_status(c, rc);
}
static lie_schema_status literal(values_context *c, lie_schema_node n,
                                 lie_grammar_builder *b, uint32_t ws,
                                 size_t depth, uint32_t *out) {
  if (depth > c->d->max_depth)
    return fail(c, LIE_SCHEMA_INVALID,
                "finite value nesting exceeds its resource budget");
  lie_schema_value v;
  TRY(lie_schema_internal_describe(&c->shared, n, &v));
  if (v.kind == LIE_SCHEMA_STRING)
    return quote(c, b, v.text, out);
  if (v.kind == LIE_SCHEMA_NUMBER) {
    if (!c->d->number_literal)
      return fail(c, LIE_SCHEMA_INVALID,
                  "number serialization callback missing");
    return c->d->number_literal(c->d->leaf_context, n, b, out);
  }
  if (v.kind == LIE_SCHEMA_NULL || v.kind == LIE_SCHEMA_BOOL) {
    const char *text = v.kind == LIE_SCHEMA_NULL ? "null"
                       : v.boolean               ? "true"
                                                 : "false";
    return builder_status(
        c, lie_builder_literal(b, (const uint8_t *)text, strlen(text), out));
  }
  const bool object = v.kind == LIE_SCHEMA_OBJECT;
  const size_t per = object ? 8 : 4;
  if (v.count > (SIZE_MAX - 4) / per ||
      (4 + v.count * per) > SIZE_MAX / sizeof(uint32_t))
    return fail(c, LIE_SCHEMA_RESOURCE, "finite value symbol storage overflow");
  TRY(lie_schema_internal_tick(&c->shared, v.count));
  const size_t capacity = 4 + v.count * per;
  uint32_t local[32], *parts = capacity <= 32
                                   ? local
                                   : lie_schema_internal_allocate(
                                         &c->shared, capacity * sizeof(*parts));
  if (!parts)
    return fail(c, LIE_SCHEMA_RESOURCE,
                "finite value symbol allocation failed");
  size_t at = 0;
  parts[at++] = BYTE(object ? '{' : '[');
  parts[at++] = ws;
  lie_schema_status rc = LIE_SCHEMA_OK;
  for (size_t i = 0; i < v.count; ++i) {
    lie_schema_bytes key;
    lie_schema_node child;
    rc = lie_schema_internal_child(&c->shared, n, i, &key, &child);
    if (rc)
      break;
    if (i) {
      parts[at++] = ws;
      parts[at++] = BYTE(',');
      parts[at++] = ws;
    }
    if (object) {
      uint32_t id;
      rc = quote(c, b, key, &id);
      if (rc)
        break;
      parts[at++] = id;
      parts[at++] = ws;
      parts[at++] = BYTE(':');
      parts[at++] = ws;
    }
    rc = literal(c, child, b, ws, depth + 1, &parts[at]);
    if (rc)
      break;
    ++at;
  }
  if (!rc) {
    parts[at++] = ws;
    parts[at++] = BYTE(object ? '}' : ']');
    rc = builder_status(c, lie_builder_sequence_make(b, parts, at, out));
  }
  if (parts != local)
    lie_schema_internal_release(&c->shared, parts);
  return rc;
}
static int compare_bytes(const void *a, const void *b) {
  const lie_schema_bytes x = *(const lie_schema_bytes *)a,
                         y = *(const lie_schema_bytes *)b;
  const size_t common = x.size < y.size ? x.size : y.size;
  const int cmp = common ? memcmp(x.data, y.data, common) : 0;
  return cmp ? cmp : (x.size > y.size) - (x.size < y.size);
}
static bool contains(const lie_schema_bytes *keys, size_t count,
                     lie_schema_bytes key) {
  size_t first = 0;
  while (first < count) {
    const size_t mid = first + (count - first) / 2;
    const int cmp = compare_bytes(&keys[mid], &key);
    if (cmp == 0)
      return true;
    if (cmp < 0)
      first = mid + 1;
    else
      count = mid;
  }
  return false;
}
static lie_schema_status
object(values_context *c, lie_schema_node schema, size_t depth, bool strict,
       lie_grammar_builder *b, uint32_t ws, lie_schema_visit visit,
       lie_schema_container_counts *counts, uint32_t *out) {
  lie_schema_context *s = &c->shared;
  lie_schema_node properties, additional, required;
  TRY(lie_schema_internal_field(s, schema, "properties", &properties));
  TRY(lie_schema_internal_field(s, schema, "additionalProperties",
                                &additional));
  lie_schema_value pv = {.kind = LIE_SCHEMA_OBJECT}, av = {0};
  if (properties)
    TRY(lie_schema_internal_describe(s, properties, &pv));
  if (additional)
    TRY(lie_schema_internal_describe(s, additional, &av));
  if (pv.kind != LIE_SCHEMA_OBJECT || !additional ||
      av.kind != LIE_SCHEMA_BOOL || av.boolean)
    return fail(c, LIE_SCHEMA_INVALID,
                "objects require properties and additionalProperties: false");
  if (counts->properties > 5000 || pv.count > 5000 - counts->properties)
    return fail(c, LIE_SCHEMA_INVALID, "maximum property count is 5000");
  counts->properties += pv.count;
  TRY(lie_schema_internal_field(s, schema, "required", &required));
  lie_schema_value rv = {.kind = LIE_SCHEMA_ARRAY};
  if (required)
    TRY(lie_schema_internal_describe(s, required, &rv));
  if (rv.kind != LIE_SCHEMA_ARRAY)
    return fail(c, LIE_SCHEMA_INVALID, "required must be an array");
  if (rv.count > pv.count)
    return fail(c, LIE_SCHEMA_INVALID,
                "required contains an unknown or duplicate property");
  lie_schema_bytes local[16],
      *keys = rv.count <= 16
                  ? local
                  : lie_schema_internal_allocate(s, rv.count * sizeof(*keys));
  if (!keys)
    return fail(c, LIE_SCHEMA_RESOURCE, "required name allocation failed");
  lie_schema_status rc = LIE_SCHEMA_OK;
  for (size_t i = 0; i < rv.count; ++i) {
    lie_schema_bytes ignored;
    lie_schema_node n, known = NULL;
    lie_schema_value v;
    rc = lie_schema_internal_child(s, required, i, &ignored, &n);
    if (rc)
      break;
    rc = lie_schema_internal_describe(s, n, &v);
    if (rc)
      break;
    if (v.kind == LIE_SCHEMA_STRING && properties)
      rc = lie_schema_internal_find(s, properties, v.text, &known);
    if (rc)
      break;
    if (v.kind != LIE_SCHEMA_STRING || !known) {
      rc = fail(c, LIE_SCHEMA_INVALID,
                "required contains an unknown or duplicate property");
      break;
    }
    keys[i] = v.text;
  }
  if (!rc && rv.count) {
    qsort(keys, rv.count, sizeof(*keys), compare_bytes);
    for (size_t i = 1; i < rv.count; ++i)
      if (!compare_bytes(&keys[i - 1], &keys[i])) {
        rc = fail(c, LIE_SCHEMA_INVALID,
                  "required contains an unknown or duplicate property");
        break;
      }
  }
  if (!rc && strict && rv.count != pv.count)
    rc = fail(
        c, LIE_SCHEMA_INVALID,
        "strict schemas require every property (use null for optional values)");
  uint32_t suffix[2] = {0};
  for (size_t i = 0; !rc && i < 2; ++i)
    rc = builder_status(c, lie_builder_sequence_make(b, NULL, 0, &suffix[i]));
  for (size_t i = pv.count; !rc && i > 0; --i) {
    lie_schema_bytes name;
    lie_schema_node child;
    rc = lie_schema_internal_child(s, properties, i - 1, &name, &child);
    if (rc)
      break;
    size_t delta = 0;
    const size_t max_chars = c->d->max_characters;
    if (counts->characters > max_chars) {
      rc = fail(c, LIE_SCHEMA_INVALID,
                "property/definition names and enum/const strings exceed "
                "120000 characters");
      break;
    }
    rc = characters(c, name, &delta);
    if (rc)
      break;
    if (delta > max_chars - counts->characters) {
      rc = fail(c, LIE_SCHEMA_INVALID,
                "property/definition names and enum/const strings exceed "
                "120000 characters");
      break;
    }
    counts->characters += delta;
    uint32_t key, child_id, member, next[2];
    rc = quote(c, b, name, &key);
    if (rc)
      break;
    rc = visit.visit(visit.context, child, depth + 1, &child_id);
    if (rc)
      break;
    const uint32_t member_parts[] = {key, ws, BYTE(':'), ws, child_id};
    rc = builder_status(c,
                        lie_builder_sequence_make(b, member_parts, 5, &member));
    if (rc)
      break;
    for (unsigned comma = 0; comma < 2; ++comma) {
      uint32_t parts[5];
      size_t at = 0;
      if (comma) {
        parts[at++] = ws;
        parts[at++] = BYTE(',');
        parts[at++] = ws;
      }
      parts[at++] = member;
      parts[at++] = suffix[1];
      const lie_builder_sequence alternatives[] = {{parts, at},
                                                   {&suffix[comma], 1}};
      rc = builder_status(
          c, lie_builder_new(b, alternatives,
                             contains(keys, rv.count, name) ? 1 : 2,
                             &next[comma]));
      if (rc)
        break;
    }
    if (!rc) {
      suffix[0] = next[0];
      suffix[1] = next[1];
    }
  }
  if (!rc) {
    const uint32_t parts[] = {BYTE('{'), ws, suffix[0], ws, BYTE('}')};
    rc = builder_status(c, lie_builder_sequence_make(b, parts, 5, out));
  }
  if (keys != local)
    lie_schema_internal_release(s, keys);
  return rc;
}
static lie_schema_status array(values_context *c, lie_schema_node schema,
                               size_t depth, lie_grammar_builder *b,
                               uint32_t ws, lie_schema_visit visit,
                               uint32_t *out) {
  lie_schema_context *s = &c->shared;
  lie_schema_node items;
  TRY(lie_schema_internal_field(s, schema, "items", &items));
  if (!items)
    return fail(c, LIE_SCHEMA_INVALID, "arrays require an items schema");
  const char *names[] = {"minItems", "maxItems"};
  size_t bounds[] = {0, UINT32_MAX};
  bool maximum = false;
  for (size_t i = 0; i < 2; ++i) {
    lie_schema_node n;
    TRY(lie_schema_internal_field(s, schema, names[i], &n));
    if (n) {
      lie_schema_value v;
      TRY(lie_schema_internal_describe(s, n, &v));
      if (v.kind != LIE_SCHEMA_NUMBER || v.number < 0 ||
          v.number > UINT32_MAX || floor(v.number) != v.number)
        return fail(c, LIE_SCHEMA_INVALID,
                    "array bounds must be nonnegative 32-bit integers");
      bounds[i] = size_value(v);
      if (i)
        maximum = true;
    }
  }
  if (bounds[0] > bounds[1])
    return fail(c, LIE_SCHEMA_EMPTY, "minItems exceeds maxItems");
  uint32_t item;
  TRY(visit.visit(visit.context, items, depth + 1, &item));
  if (!bounds[1]) {
    const uint32_t parts[] = {BYTE('['), ws, BYTE(']')};
    return builder_status(c, lie_builder_sequence_make(b, parts, 3, out));
  }
  const uint32_t addition[] = {ws, BYTE(','), ws, item};
  uint32_t additional, tail, exact, members;
  TRY(builder_status(c,
                     lie_builder_sequence_make(b, addition, 4, &additional)));
  const size_t required = bounds[0] ? bounds[0] - 1 : 0;
  TRY(builder_status(c, maximum ? lie_builder_at_most(b, additional,
                                                      bounds[1] - required - 1,
                                                      &tail)
                                : lie_builder_repeat(b, additional, &tail)));
  TRY(builder_status(c, lie_builder_exact(b, additional, required, &exact)));
  const uint32_t member_parts[] = {item, exact, tail};
  TRY(builder_status(c,
                     lie_builder_sequence_make(b, member_parts, 3, &members)));
  if (!bounds[0])
    TRY(builder_status(c, lie_builder_optional(b, members, &members)));
  const uint32_t parts[] = {BYTE('['), ws, members, ws, BYTE(']')};
  return builder_status(c, lie_builder_sequence_make(b, parts, 5, out));
}
void lie_schema_values_description_init(lie_schema_values_description *d) {
  if (!d)
    return;
  memset(d, 0, sizeof(*d));
  d->abi_version = LIE_SCHEMA_VALUES_ABI;
  d->struct_bytes = sizeof(*d);
  d->max_depth = 256;
  d->max_characters = 120000;
  lie_schema_transform_description_init(&d->transform);
}
lie_schema_status
lie_schema_matches_type(const lie_schema_values_description *d,
                        lie_schema_node n, lie_schema_bytes type, bool *out,
                        lie_schema_error *e) {
  if (!valid(d) || !n || !out || (type.size && !type.data))
    return LIE_SCHEMA_INVALID;
  values_context c = {{&d->transform, 0, e}, d};
  lie_schema_value v;
  TRY(lie_schema_internal_describe(&c.shared, n, &v));
  *out = matches(v, type);
  return LIE_SCHEMA_OK;
}
lie_schema_status lie_schema_normalize(const lie_schema_values_description *d,
                                       lie_schema_node root,
                                       lie_schema_node schema,
                                       lie_schema_node value, size_t depth,
                                       lie_schema_normalized *out,
                                       lie_schema_error *e) {
  if (!valid(d) || !root || !schema || !value || !out || !d->accept ||
      !d->transform.access.clone || !d->transform.access.create ||
      !d->transform.access.put || !d->transform.access.append)
    return LIE_SCHEMA_INVALID;
  values_context c = {{&d->transform, 0, e}, d};
  lie_schema_normalized n;
  const lie_schema_status rc = normalize(&c, root, schema, value, depth, &n);
  if (!rc)
    *out = n;
  return rc;
}
lie_schema_status
lie_schema_text_characters(const lie_schema_values_description *d,
                           lie_schema_bytes text, size_t *out,
                           lie_schema_error *e) {
  if (!valid(d) || !out)
    return LIE_SCHEMA_INVALID;
  values_context c = {{&d->transform, 0, e}, d};
  size_t n = 0;
  TRY(characters(&c, text, &n));
  *out = n;
  return LIE_SCHEMA_OK;
}
lie_schema_status
lie_schema_value_characters(const lie_schema_values_description *d,
                            lie_schema_node n, size_t *out,
                            lie_schema_error *e) {
  if (!valid(d) || !n || !out)
    return LIE_SCHEMA_INVALID;
  values_context c = {{&d->transform, 0, e}, d};
  return count_value(&c, n, out);
}
lie_schema_status
lie_schema_value_literal(const lie_schema_values_description *d,
                         lie_schema_node n, lie_grammar_builder *b, uint32_t ws,
                         uint32_t *out, lie_schema_error *e) {
  if (!valid(d) || !n || !b || !out)
    return LIE_SCHEMA_INVALID;
  values_context c = {{&d->transform, 0, e}, d};
  uint32_t id;
  TRY(literal(&c, n, b, ws, 0, &id));
  *out = id;
  return LIE_SCHEMA_OK;
}
lie_schema_status lie_schema_object(const lie_schema_values_description *d,
                                    lie_schema_node n, size_t depth,
                                    bool strict, lie_grammar_builder *b,
                                    uint32_t ws, lie_schema_visit visit,
                                    lie_schema_container_counts *counts,
                                    uint32_t *out, lie_schema_error *e) {
  if (!valid(d) || !n || !b || !visit.visit || !counts || !out ||
      depth == SIZE_MAX)
    return LIE_SCHEMA_INVALID;
  values_context c = {{&d->transform, 0, e}, d};
  uint32_t id;
  TRY(object(&c, n, depth, strict, b, ws, visit, counts, &id));
  *out = id;
  return LIE_SCHEMA_OK;
}
lie_schema_status lie_schema_array(const lie_schema_values_description *d,
                                   lie_schema_node n, size_t depth,
                                   lie_grammar_builder *b, uint32_t ws,
                                   lie_schema_visit visit, uint32_t *out,
                                   lie_schema_error *e) {
  if (!valid(d) || !n || !b || !visit.visit || !out || depth == SIZE_MAX)
    return LIE_SCHEMA_INVALID;
  values_context c = {{&d->transform, 0, e}, d};
  uint32_t id;
  TRY(array(&c, n, depth, b, ws, visit, &id));
  *out = id;
  return LIE_SCHEMA_OK;
}
