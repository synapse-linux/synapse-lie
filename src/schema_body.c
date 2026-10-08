/* SPDX-License-Identifier: MIT */
/* Body policy follows independently pinned Gufo; see gufo-NOTICE. */
#include "lie/schema_body.h"
#include "schema_internal.h"
#include <string.h>
#define TRY(call)                                                              \
  do {                                                                         \
    lie_schema_status rc_ = (call);                                            \
    if (rc_)                                                                   \
      return rc_;                                                              \
  } while (0)
typedef struct {
  lie_schema_context shared;
  const lie_schema_body_description *d;
  lie_schema_node root;
  lie_grammar_builder *builder;
  uint32_t whitespace;
  lie_schema_container_counts *counts;
  size_t *enum_values;
} body_context;
static bool key_is(lie_schema_bytes k, const char *s) {
  size_t n = strlen(s);
  return k.size == n && (!n || !memcmp(k.data, s, n));
}
static lie_schema_status fail(body_context *c, lie_schema_status rc,
                              const char *s) {
  return lie_schema_internal_fail(&c->shared, rc, s);
}
static void clear_error(body_context *c) {
  if (c->shared.error)
    *c->shared.error = (lie_schema_error){0};
}
static lie_schema_status without(body_context *c, lie_schema_node node,
                                 const char *const *keys, size_t key_count,
                                 lie_schema_node *out) {
  lie_schema_context *s = &c->shared;
  lie_schema_node result;
  TRY(lie_schema_internal_create(
      s, (lie_schema_value){.kind = LIE_SCHEMA_OBJECT}, &result));
  lie_schema_value v;
  TRY(lie_schema_internal_describe(s, node, &v));
  for (size_t i = 0; i < v.count; ++i) {
    lie_schema_bytes key;
    lie_schema_node value;
    TRY(lie_schema_internal_child(s, node, i, &key, &value));
    bool excluded = false;
    for (size_t j = 0; j < key_count; ++j)
      if (key_is(key, keys[j])) {
        excluded = true;
        break;
      }
    if (!excluded) {
      TRY(lie_schema_internal_tick(s, 1));
      TRY(c->d->append_member(s->d->access.context, result, key, value));
    }
  }
  *out = result;
  return LIE_SCHEMA_OK;
}
static lie_schema_status keep(body_context *c, lie_schema_node node,
                              lie_schema_node *out) {
  lie_schema_node result = NULL;
  TRY(c->d->compile.keep_schema(c->d->compile.context, node, &result));
  if (!result)
    return fail(c, LIE_SCHEMA_INVALID, "invalid retained schema node");
  *out = result;
  return LIE_SCHEMA_OK;
}
static lie_schema_status count_name(body_context *c, lie_schema_bytes text) {
  lie_schema_values_description values = c->d->values;
  values.max_characters = 120000 - c->counts->characters;
  size_t n = 0;
  TRY(lie_schema_text_characters(&values, text, &n, c->shared.error));
  c->counts->characters += n;
  return LIE_SCHEMA_OK;
}
static lie_schema_status definitions(body_context *c, lie_schema_node schema,
                                     size_t depth) {
  lie_schema_node defs;
  TRY(lie_schema_internal_field(&c->shared, schema, "$defs", &defs));
  if (!defs)
    return LIE_SCHEMA_OK;
  lie_schema_value v;
  TRY(lie_schema_internal_describe(&c->shared, defs, &v));
  if (v.kind != LIE_SCHEMA_OBJECT)
    return fail(c, LIE_SCHEMA_INVALID, "$defs must be an object");
  for (size_t i = 0; i < v.count; ++i) {
    lie_schema_bytes name;
    lie_schema_node child;
    uint32_t ignored = 0;
    TRY(lie_schema_internal_child(&c->shared, defs, i, &name, &child));
    TRY(count_name(c, name));
    TRY(c->d->compile.visit(c->d->compile.context, child, depth, &ignored));
  }
  return LIE_SCHEMA_OK;
}
static lie_schema_status reference(body_context *c, lie_schema_node schema,
                                   lie_schema_node ref, size_t depth,
                                   uint32_t *out) {
  static const char *const keys[] = {"$ref", "$defs", "title", "description"};
  lie_schema_node siblings, target;
  TRY(without(c, schema, keys, 4, &siblings));
  lie_schema_value v;
  TRY(lie_schema_internal_describe(&c->shared, siblings, &v));
  TRY(lie_schema_internal_reference(&c->shared, c->root, ref, &target));
  if (v.count) {
    lie_schema_node merged;
    TRY(lie_schema_conjoin(&c->d->transform, c->root, target, siblings, 0,
                           &merged, c->shared.error));
    TRY(keep(c, merged, &target));
  }
  return c->d->compile.visit(c->d->compile.context, target, depth, out);
}
static lie_schema_status any_of(body_context *c, lie_schema_node schema,
                                lie_schema_node any, size_t depth,
                                uint32_t *out) {
  lie_schema_context *s = &c->shared;
  lie_schema_value av;
  TRY(lie_schema_internal_describe(s, any, &av));
  if (av.kind != LIE_SCHEMA_ARRAY || !av.count)
    return fail(c, LIE_SCHEMA_INVALID, "anyOf needs at least one branch");
  static const char *const keys[] = {"anyOf", "$defs", "title", "description"};
  lie_schema_node siblings;
  TRY(without(c, schema, keys, 4, &siblings));
  lie_schema_value sv;
  TRY(lie_schema_internal_describe(s, siblings, &sv));
  TRY(lie_schema_internal_tick(s, av.count));
  if (av.count > SIZE_MAX / sizeof(uint32_t))
    return LIE_SCHEMA_RESOURCE;
  uint32_t local[16],
      *rules = av.count <= 16
                   ? local
                   : lie_schema_internal_allocate(s, av.count * sizeof(*rules));
  if (!rules)
    return LIE_SCHEMA_RESOURCE;
  size_t count = 0;
  lie_schema_status rc = LIE_SCHEMA_OK;
  for (size_t i = 0; i < av.count; ++i) {
    lie_schema_bytes ignored;
    lie_schema_node child;
    rc = lie_schema_internal_child(s, any, i, &ignored, &child);
    if (rc)
      break;
    if (sv.count) {
      lie_schema_node merged;
      rc = lie_schema_conjoin(&c->d->transform, c->root, child, siblings, 0,
                              &merged, s->error);
      if (!rc)
        rc = keep(c, merged, &child);
    }
    if (!rc)
      rc = c->d->compile.visit(c->d->compile.context, child, depth + 1,
                               &rules[count]);
    if (rc == LIE_SCHEMA_EMPTY) {
      clear_error(c);
      rc = LIE_SCHEMA_OK;
      continue;
    }
    if (rc)
      break;
    ++count;
  }
  if (!rc)
    rc = lie_schema_internal_builder_error(
        lie_builder_alternatives(c->builder, rules, count, out), s->error);
  if (rules != local)
    lie_schema_internal_release(s, rules);
  return rc;
}
static lie_schema_status finite(body_context *c, lie_schema_node schema,
                                lie_schema_node enumeration,
                                lie_schema_node constant, size_t depth,
                                const lie_schema_dispatch_plan *plan,
                                uint32_t *out) {
  lie_schema_context *s = &c->shared;
  static const char *const keys[] = {"enum", "const", "$defs"};
  lie_schema_node base = NULL, temporary = NULL;
  uint32_t ignored = 0;
  TRY(without(c, schema, keys, 3, &temporary));
  TRY(keep(c, temporary, &base));
  TRY(c->d->compile.visit(c->d->compile.context, base, depth, &ignored));
  lie_schema_value ev = {.count = 1};
  if (enumeration) {
    TRY(lie_schema_internal_describe(s, enumeration, &ev));
    if (ev.kind != LIE_SCHEMA_ARRAY || !ev.count)
      return fail(c, LIE_SCHEMA_INVALID, "enum must be a nonempty array");
  }
  if (ev.count > 1000 - *c->enum_values)
    return fail(c, LIE_SCHEMA_INVALID,
                "maximum enum/const value count is 1000");
  *c->enum_values += ev.count;
  uint32_t local[16],
      *rules = ev.count <= 16
                   ? local
                   : lie_schema_internal_allocate(s, ev.count * sizeof(*rules));
  if (!rules)
    return LIE_SCHEMA_RESOURCE;
  size_t count = 0, enum_characters = 0;
  lie_schema_status rc = LIE_SCHEMA_OK;
  for (size_t i = 0; i < ev.count; ++i) {
    lie_schema_node value = constant;
    if (enumeration) {
      lie_schema_bytes key;
      rc = lie_schema_internal_child(s, enumeration, i, &key, &value);
    }
    if (rc)
      break;
    lie_schema_values_description values = c->d->values;
    size_t delta = 0;
    values.max_characters = 120000 - c->counts->characters;
    rc = lie_schema_value_characters(&values, value, &delta, s->error);
    if (rc)
      break;
    c->counts->characters += delta;
    bool matched = false;
    for (size_t j = 0; j < plan->count && !matched; ++j) {
      rc = lie_schema_matches_type(&c->d->values, value, plan->names[j],
                                   &matched, s->error);
      if (rc)
        break;
    }
    if (rc)
      break;
    if (!matched) {
      rc = fail(c, LIE_SCHEMA_INVALID,
                "enum/const value does not match its type");
      break;
    }
    lie_schema_value v;
    rc = lie_schema_internal_describe(s, value, &v);
    if (rc)
      break;
    if (v.kind == LIE_SCHEMA_STRING) {
      enum_characters += delta;
      if (ev.count > 250 && enum_characters > 15000) {
        rc = fail(c, LIE_SCHEMA_INVALID,
                  "an enum with more than 250 entries is limited to 15000 "
                  "string characters");
        break;
      }
    }
    if (constant) {
      bool equal = false;
      rc = lie_schema_internal_equal(s, value, constant, &equal);
      if (rc)
        break;
      if (!equal)
        continue;
    }
    lie_schema_normalized normalized = {0};
    rc = c->d->compile.normalize(c->d->compile.context, base, value,
                                 &normalized);
    if (!rc && normalized.matched) {
      if (!normalized.value) {
        rc = fail(c, LIE_SCHEMA_INVALID, "invalid canonical value node");
        break;
      }
      rc = lie_schema_value_literal(&c->d->values, normalized.value, c->builder,
                                    c->whitespace, &rules[count], s->error);
      if (!rc)
        ++count;
    }
    if (rc == LIE_SCHEMA_EMPTY) {
      clear_error(c);
      rc = LIE_SCHEMA_OK;
      continue;
    }
    if (rc)
      break;
  }
  if (!rc && !count)
    rc = fail(c, LIE_SCHEMA_EMPTY,
              "enum/const has no value satisfying its constraints");
  if (!rc)
    rc = lie_schema_internal_builder_error(
        lie_builder_alternatives(c->builder, rules, count, out), s->error);
  if (rules != local)
    lie_schema_internal_release(s, rules);
  return rc;
}
void lie_schema_body_description_init(lie_schema_body_description *d) {
  if (!d)
    return;
  memset(d, 0, sizeof(*d));
  d->abi_version = LIE_SCHEMA_BODY_ABI;
  d->struct_bytes = sizeof(*d);
  lie_schema_transform_description_init(&d->transform);
  lie_schema_values_description_init(&d->values);
}
lie_schema_status lie_schema_compile_body(
    const lie_schema_body_description *d, lie_schema_node root,
    lie_schema_node schema, size_t depth, lie_grammar_builder *builder,
    uint32_t whitespace, lie_schema_container_counts *counts,
    size_t *enum_values, uint32_t *out, lie_schema_error *error) {
  if (!d || d->abi_version != LIE_SCHEMA_BODY_ABI ||
      d->struct_bytes != sizeof(*d) ||
      !lie_schema_internal_valid(&d->transform) ||
      !lie_schema_internal_valid(&d->values.transform) ||
      d->values.abi_version != LIE_SCHEMA_VALUES_ABI ||
      d->values.struct_bytes != sizeof(d->values) ||
      d->values.max_depth > 256 || !d->transform.access.create ||
      !d->transform.access.put || !d->transform.access.clone ||
      !d->transform.access.append || !d->append_member || !d->compile.visit ||
      !d->compile.keep_schema || !d->compile.normalize || !d->rules.rule ||
      !root || !schema || !builder || !counts || !enum_values || !out ||
      counts->characters > 120000 || *enum_values > 1000)
    return LIE_SCHEMA_INVALID;
  body_context c = {{&d->transform, 0, error},
                    d,
                    root,
                    builder,
                    whitespace,
                    counts,
                    enum_values};
  lie_schema_value v;
  TRY(lie_schema_internal_describe(&c.shared, schema, &v));
  if (v.kind != LIE_SCHEMA_OBJECT)
    return fail(&c, LIE_SCHEMA_INVALID, "each schema must be an object");
  if (depth > 16)
    return fail(&c, LIE_SCHEMA_INVALID, "maximum schema depth is 16");
  TRY(lie_schema_keys(&d->transform, schema, error));
  TRY(definitions(&c, schema, depth));
  lie_schema_node ref, any;
  uint32_t result = 0;
  lie_schema_status rc;
  TRY(lie_schema_internal_field(&c.shared, schema, "$ref", &ref));
  if (ref)
    rc = reference(&c, schema, ref, depth, &result);
  else {
    TRY(lie_schema_internal_field(&c.shared, schema, "anyOf", &any));
    if (any)
      rc = any_of(&c, schema, any, depth, &result);
    else {
      lie_schema_dispatch_plan plan;
      TRY(lie_schema_dispatch_types(&d->transform, schema, &plan, error));
      lie_schema_node enumeration, constant;
      TRY(lie_schema_internal_field(&c.shared, schema, "enum", &enumeration));
      TRY(lie_schema_internal_field(&c.shared, schema, "const", &constant));
      if (enumeration || constant)
        rc = finite(&c, schema, enumeration, constant, depth, &plan, &result);
      else
        rc = lie_schema_dispatch_rules(&plan, schema, depth, builder, d->rules,
                                       &result, error);
    }
  }
  if (!rc)
    *out = result;
  return rc;
}
