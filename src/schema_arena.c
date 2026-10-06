/* SPDX-License-Identifier: MIT */
/* Native construction/ownership binding to the separately owned C17 schema
 * transform, format, numeric and JSON tree contracts; no provider types. */
#include "lie/schema_arena.h"
#include "lie/schema_format.h"
#include "lie/schema_number.h"
#include <stdlib.h>
#include <string.h>
struct lie_schema_arena {
  lie_schema_arena_description description;
  lie_json_store *store;
  lie_schema_arena_error error;
};
static void *allocate(void *p, size_t bytes) { (void)p; return malloc(bytes); }
static void release(void *p, void *value) { (void)p; free(value); }
static void inherit(lie_grammar_allocator *a, lie_grammar_allocator parent) {
  if (!a->allocate && !a->release) *a = parent;
}
void lie_schema_arena_description_init(lie_schema_arena_description *d) {
  if (!d) return;
  memset(d, 0, sizeof(*d));
  d->abi_version = LIE_SCHEMA_ARENA_ABI; d->struct_bytes = sizeof(*d);
  lie_json_value_description_init(&d->values);
  lie_json_store_description_init(&d->store);
  lie_schema_transform_description_init(&d->transform);
}
static void reset(lie_schema_arena *a) { if (a) a->error = (lie_schema_arena_error){0}; }
static lie_schema_status value_status(lie_schema_arena *a, lie_json_value_status rc) {
  a->error.value_status = rc;
  return rc == LIE_JSON_VALUE_OK ? LIE_SCHEMA_OK :
    rc == LIE_JSON_VALUE_RESOURCE ? LIE_SCHEMA_RESOURCE : LIE_SCHEMA_CALLBACK;
}
static lie_schema_status store_status(lie_schema_arena *a, lie_json_store_status rc) {
  a->error.store_status = rc;
  return rc == LIE_JSON_STORE_OK ? LIE_SCHEMA_OK :
    rc == LIE_JSON_STORE_RESOURCE ? LIE_SCHEMA_RESOURCE : LIE_SCHEMA_CALLBACK;
}
lie_schema_status lie_schema_arena_create(const lie_schema_arena_description *input,
    lie_schema_arena **out) {
  lie_schema_arena_description d; lie_schema_arena_description_init(&d);
  if (input) d = *input;
  if (!out || d.abi_version != LIE_SCHEMA_ARENA_ABI || d.struct_bytes != sizeof(d) ||
      (!!d.allocator.allocate != !!d.allocator.release) ||
      (!!d.values.allocator.allocate != !!d.values.allocator.release) ||
      (!!d.store.allocator.allocate != !!d.store.allocator.release) ||
      (!!d.transform.allocator.allocate != !!d.transform.allocator.release))
    return LIE_SCHEMA_INVALID;
  if (!d.allocator.allocate) d.allocator = (lie_grammar_allocator){NULL, allocate, release};
  inherit(&d.values.allocator, d.allocator); inherit(&d.store.allocator, d.allocator);
  inherit(&d.transform.allocator, d.allocator);
  lie_schema_arena *a = d.allocator.allocate(d.allocator.context, sizeof(*a));
  if (!a) return LIE_SCHEMA_RESOURCE;
  *a = (lie_schema_arena){.description = d};
  lie_json_store_status rc = lie_json_store_create(&d.store, &a->store);
  if (rc) {
    d.allocator.release(d.allocator.context, a);
    return rc == LIE_JSON_STORE_RESOURCE ? LIE_SCHEMA_RESOURCE : LIE_SCHEMA_INVALID;
  }
  *out = a; return LIE_SCHEMA_OK;
}
void lie_schema_arena_release(lie_schema_arena *a) {
  if (!a) return;
  const lie_grammar_allocator allocator = a->description.allocator;
  lie_json_store_release(a->store);
  allocator.release(allocator.context, a);
}
static lie_schema_status adopt(lie_schema_arena *a, lie_json_value *root, lie_json_value **out) {
  lie_schema_status rc = store_status(a, lie_json_store_adopt(a->store, root));
  if (rc) lie_json_value_release(root);
  else *out = root;
  return rc;
}
lie_schema_status lie_schema_arena_clone(lie_schema_arena *a, const lie_json_value *value,
    lie_json_value **out) {
  reset(a);
  if (!a || !value || !out) return LIE_SCHEMA_INVALID;
  lie_json_value *root = NULL;
  lie_schema_status rc = value_status(a, lie_json_value_clone(value, &a->description.values, &root));
  return rc ? rc : adopt(a, root, out);
}
lie_schema_status lie_schema_arena_make(lie_schema_arena *a, const lie_schema_value *v,
    lie_json_value **out) {
  reset(a);
  if (!a || !v || !out) return LIE_SCHEMA_INVALID;
  lie_json_value_kind kind;
  switch (v->kind) {
  case LIE_SCHEMA_NULL: kind = LIE_JSON_VALUE_NULL; break;
  case LIE_SCHEMA_BOOL: kind = LIE_JSON_VALUE_BOOL; break;
  case LIE_SCHEMA_NUMBER: kind = LIE_JSON_VALUE_NUMBER; break;
  case LIE_SCHEMA_STRING: kind = LIE_JSON_VALUE_STRING; break;
  case LIE_SCHEMA_ARRAY: kind = LIE_JSON_VALUE_ARRAY; break;
  case LIE_SCHEMA_OBJECT: kind = LIE_JSON_VALUE_OBJECT; break;
  default: return LIE_SCHEMA_INVALID;
  }
  lie_json_value *root = NULL;
  lie_schema_status rc = value_status(a, lie_json_value_create(&a->description.values, &root));
  if (rc) return rc;
  rc = value_status(a, lie_json_value_set(root, kind, v->boolean, v->number,
                                       v->text.data, v->text.size));
  if (rc) { lie_json_value_release(root); return rc; }
  return adopt(a, root, out);
}
lie_schema_status lie_schema_arena_put(lie_schema_arena *a, lie_json_value *target,
    lie_schema_bytes key, const lie_json_value *value) {
  reset(a);
  if (!a || !target || !value) return LIE_SCHEMA_INVALID;
  lie_json_value *member = NULL;
  lie_schema_status rc = value_status(a, lie_json_value_member(target, key.data, key.size, &member));
  return rc ? rc : value_status(a, lie_json_value_assign(member, value));
}
lie_schema_status lie_schema_arena_append_member(lie_schema_arena *a, lie_json_value *target,
    lie_schema_bytes key, const lie_json_value *value) {
  reset(a);
  if (!a || !target || !value) return LIE_SCHEMA_INVALID;
  lie_json_value *member = NULL;
  return value_status(a, lie_json_value_append_member(target, key.data, key.size, value, &member));
}
lie_schema_status lie_schema_arena_append(lie_schema_arena *a, lie_json_value *target,
    const lie_json_value *value) {
  reset(a);
  if (!a || !target || !value) return LIE_SCHEMA_INVALID;
  lie_json_value *member = NULL;
  return value_status(a, lie_json_value_append(target, value, &member));
}
lie_schema_status lie_schema_arena_take(lie_schema_arena *a, const lie_json_value *value,
    lie_json_value **out) {
  reset(a);
  if (!a || !value || !out) return LIE_SCHEMA_INVALID;
  return store_status(a, lie_json_store_take(a->store, value, out));
}
lie_schema_status lie_schema_json_describe(void *p, lie_schema_node n, lie_schema_value *out) {
  (void)p;
  if (!n || !out) return LIE_SCHEMA_INVALID;
  lie_schema_value value = {.count = lie_json_value_size(n),
    .number = lie_json_value_number(n, 0), .boolean = lie_json_value_boolean(n, false)};
  switch (lie_json_value_type(n)) {
  case LIE_JSON_VALUE_NULL: value.kind = LIE_SCHEMA_NULL; break;
  case LIE_JSON_VALUE_BOOL: value.kind = LIE_SCHEMA_BOOL; break;
  case LIE_JSON_VALUE_NUMBER: value.kind = LIE_SCHEMA_NUMBER; break;
  case LIE_JSON_VALUE_STRING:
    value.kind = LIE_SCHEMA_STRING;
    value.text.data = lie_json_value_string(n, &value.text.size); break;
  case LIE_JSON_VALUE_ARRAY: value.kind = LIE_SCHEMA_ARRAY; break;
  case LIE_JSON_VALUE_OBJECT: value.kind = LIE_SCHEMA_OBJECT; break;
  }
  *out = value; return LIE_SCHEMA_OK;
}
lie_schema_status lie_schema_json_child(void *p, lie_schema_node n, size_t i,
    lie_schema_bytes *key, lie_schema_node *out) {
  (void)p;
  if (!n || !key || !out) return LIE_SCHEMA_INVALID;
  const lie_json_value_kind kind = lie_json_value_type(n);
  if (kind != LIE_JSON_VALUE_ARRAY && kind != LIE_JSON_VALUE_OBJECT) return LIE_SCHEMA_INVALID;
  const lie_json_value *child = lie_json_value_at(n, kind == LIE_JSON_VALUE_OBJECT, i);
  if (!child) return LIE_SCHEMA_INVALID;
  lie_schema_bytes k = {0};
  if (kind == LIE_JSON_VALUE_OBJECT) k.data = lie_json_value_key(child, &k.size);
  *key = k; *out = child; return LIE_SCHEMA_OK;
}
static lie_schema_status clone(void *p, lie_schema_node n, lie_schema_node *out) {
  if (!out) return LIE_SCHEMA_INVALID;
  lie_json_value *v = NULL; lie_schema_status rc = lie_schema_arena_clone(p, n, &v);
  if (!rc) *out = v;
  return rc;
}
static lie_schema_status make(void *p, const lie_schema_value *value, lie_schema_node *out) {
  if (!out) return LIE_SCHEMA_INVALID;
  lie_json_value *v = NULL; lie_schema_status rc = lie_schema_arena_make(p, value, &v);
  if (!rc) *out = v;
  return rc;
}
static lie_schema_status put(void *p, lie_schema_node n, lie_schema_bytes key, lie_schema_node value) {
  return lie_schema_arena_put(p, (lie_json_value *)n, key, value);
}
static lie_schema_status append(void *p, lie_schema_node n, lie_schema_node value) {
  return lie_schema_arena_append(p, (lie_json_value *)n, value);
}
static lie_schema_status format(void *p, lie_schema_bytes text, lie_schema_node *out) {
  if (!out) return LIE_SCHEMA_INVALID;
  lie_json_value *v = NULL; lie_schema_status rc = lie_schema_arena_format(p, text, &v);
  if (!rc) *out = v;
  return rc;
}
static lie_schema_status multiple(void *p, lie_schema_node left, lie_schema_node right,
    lie_schema_node *out) {
  if (!out) return LIE_SCHEMA_INVALID;
  lie_json_value *v = NULL; lie_schema_status rc = lie_schema_arena_multiple(p, left, right, &v);
  if (!rc) *out = v;
  return rc;
}
lie_schema_transform_description lie_schema_arena_transform(lie_schema_arena *a) {
  lie_schema_transform_description d;
  if (a) d = a->description.transform;
  else lie_schema_transform_description_init(&d);
  d.access = (lie_schema_access){.context = a, .describe = lie_schema_json_describe,
    .child = lie_schema_json_child, .clone = clone, .create = make, .put = put,
    .append = append, .format = format, .multiple = multiple};
  return d;
}
lie_schema_status lie_schema_arena_format(lie_schema_arena *a, lie_schema_bytes text,
    lie_json_value **out) {
  reset(a);
  if (!a || !out) return LIE_SCHEMA_INVALID;
  const lie_schema_transform_description d = lie_schema_arena_transform(a);
  lie_schema_node result = NULL; lie_schema_error e = {0};
  lie_schema_status rc = lie_schema_format_expand(&d, text, &result, &e);
  a->error.schema_error = e;
  if (!rc) *out = (lie_json_value *)result;
  return rc;
}
lie_schema_status lie_schema_arena_multiple(lie_schema_arena *a, const lie_json_value *left,
    const lie_json_value *right, lie_json_value **out) {
  reset(a);
  if (!a || !out) return LIE_SCHEMA_INVALID;
  lie_schema_number_description d; lie_schema_number_description_init(&d);
  d.transform = lie_schema_arena_transform(a); d.number_work = a->description.number_work;
  double result = 0; lie_schema_error e = {0};
  lie_schema_status rc = lie_schema_number_intersect(&d, left, right, &result, &e);
  if (rc) { a->error.schema_error = e; return rc; }
  const lie_schema_value number = {.kind = LIE_SCHEMA_NUMBER, .number = result};
  return lie_schema_arena_make(a, &number, out);
}
void lie_schema_arena_error_describe(const lie_schema_arena *a, lie_schema_arena_error *out) {
  if (out) *out = a ? a->error : (lie_schema_arena_error){0};
}
void lie_schema_arena_store_describe(const lie_schema_arena *a, lie_json_store_info *out) {
  lie_json_store_describe(a ? a->store : NULL, out);
}
