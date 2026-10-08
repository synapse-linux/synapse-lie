/* SPDX-License-Identifier: MIT */
/* Native construction/ownership oracles for final qualification. These fixtures
 * are written, not run, during implementation-first work. HOST NOT-INFERENCE. */
#include "lie/schema_arena.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef union { max_align_t alignment; size_t bytes; } header;
typedef struct { size_t calls, fail, live, bytes; } memory;
static void *allocate(void *p, size_t bytes) {
  memory *m = p;
  if (++m->calls == m->fail) return NULL;
  assert(bytes <= SIZE_MAX - sizeof(header));
  header *h = malloc(sizeof(*h) + bytes); assert(h);
  h->bytes = bytes; ++m->live; m->bytes += bytes; return h + 1;
}
static void release(void *p, void *value) {
  memory *m = p; header *h = (header *)value - 1;
  assert(m->live && m->bytes >= h->bytes);
  --m->live; m->bytes -= h->bytes; free(h);
}
static lie_schema_bytes text(const char *s) { return (lie_schema_bytes){s, strlen(s)}; }
static lie_json_value *parse(const char *s) {
  lie_json_value *value = NULL;
  assert(lie_json_value_parse(s, strlen(s), NULL, NULL, &value, NULL, NULL) == LIE_JSON_VALUE_OK);
  return value;
}
static lie_schema_arena *create(memory *m, lie_schema_arena_description *d) {
  lie_schema_arena_description_init(d);
  d->allocator = (lie_grammar_allocator){m, allocate, release};
  lie_schema_arena *a = NULL;
  assert(lie_schema_arena_create(d, &a) == LIE_SCHEMA_OK); return a;
}
static lie_json_value *make(lie_schema_arena *a, lie_schema_kind kind,
    double number, const char *s, size_t bytes) {
  const lie_schema_value value = {.kind = kind, .number = number, .text = {s, bytes}};
  lie_json_value *out = NULL;
  assert(lie_schema_arena_make(a, &value, &out) == LIE_SCHEMA_OK); return out;
}
static void ownership(void) {
  memory m = {0}; lie_schema_arena_description d;
  lie_schema_arena *a = create(&m, &d);
  lie_json_value *null = make(a, LIE_SCHEMA_NULL, 0, NULL, 0);
  const lie_schema_value boolean = {.kind = LIE_SCHEMA_BOOL, .boolean = true};
  lie_json_value *truth = NULL;
  assert(lie_schema_arena_make(a, &boolean, &truth) == LIE_SCHEMA_OK);
  assert(lie_json_value_type(null) == LIE_JSON_VALUE_NULL);
  assert(lie_json_value_type(truth) == LIE_JSON_VALUE_BOOL && lie_json_value_boolean(truth, false));
  lie_json_value *object = make(a, LIE_SCHEMA_OBJECT, 0, NULL, 0);
  lie_json_value *one = make(a, LIE_SCHEMA_NUMBER, 1, NULL, 0);
  lie_json_value *two = make(a, LIE_SCHEMA_NUMBER, 2, NULL, 0);
  lie_json_value *zero = make(a, LIE_SCHEMA_NUMBER, -0.0, NULL, 0);
  assert(signbit(lie_json_value_number(zero, 1)));
  const char string[] = {'A', '\0', 'B', (char)0xc3, (char)0xa8};
  lie_json_value *value = make(a, LIE_SCHEMA_STRING, 0, string, sizeof(string));
  size_t bytes = 0;
  const char *p = lie_json_value_string(value, &bytes);
  assert(bytes == sizeof(string) && !memcmp(p, string, bytes));
  const char key[] = {'k', '\0', 'x'};
  assert(lie_schema_arena_append_member(a, object, (lie_schema_bytes){key, sizeof(key)}, one) == LIE_SCHEMA_OK);
  assert(lie_schema_arena_append_member(a, object, (lie_schema_bytes){key, sizeof(key)}, two) == LIE_SCHEMA_OK);
  assert(lie_json_value_object_size(object) == 2);
  const lie_json_value *first = lie_json_value_at(object, true, 0);
  const lie_json_value *second = lie_json_value_at(object, true, 1);
  assert(first != second && lie_json_value_number(first, 0) == 1 && lie_json_value_number(second, 0) == 2);
  assert(lie_schema_arena_put(a, object, (lie_schema_bytes){key, sizeof(key)}, zero) == LIE_SCHEMA_OK);
  assert(lie_json_value_at(object, true, 0) == first && signbit(lie_json_value_number(first, 1)));
  assert(lie_json_value_number(second, 0) == 2);
  lie_schema_value read = {0};
  assert(lie_schema_json_describe(NULL, value, &read) == LIE_SCHEMA_OK && read.kind == LIE_SCHEMA_STRING);
  assert(read.text.size == sizeof(string) && !memcmp(read.text.data, string, sizeof(string)));
  lie_schema_bytes name = {0}; lie_schema_node child = NULL;
  assert(lie_schema_json_child(NULL, object, 1, &name, &child) == LIE_SCHEMA_OK);
  assert(child == second && name.size == sizeof(key) && !memcmp(name.data, key, sizeof(key)));
  const lie_schema_bytes unchanged_name = name;
  const lie_schema_node unchanged_child = child;
  assert(lie_schema_json_child(NULL, object, 2, &name, &child) == LIE_SCHEMA_INVALID);
  assert(name.data == unchanged_name.data && name.size == unchanged_name.size && child == unchanged_child);
  lie_json_value *array = make(a, LIE_SCHEMA_ARRAY, 0, NULL, 0);
  assert(lie_schema_arena_append(a, array, value) == LIE_SCHEMA_OK);
  assert(lie_schema_arena_put(a, object, text("array"), array) == LIE_SCHEMA_OK);
  max_align_t sentinel; lie_json_value *out = (void *)&sentinel;
  assert(lie_schema_arena_take(a, first, &out) == LIE_SCHEMA_CALLBACK && out == (void *)&sentinel);
  lie_schema_arena_error e; lie_schema_arena_error_describe(a, &e);
  assert(e.store_status == LIE_JSON_STORE_INVALID);
  assert(lie_schema_arena_take(a, object, &out) == LIE_SCHEMA_OK && out == object);
  lie_schema_arena_release(a);
  assert(m.live && lie_json_value_object_size(out) == 3);
  const lie_json_value *retained_array = lie_json_value_find(out, "array", 5);
  const lie_json_value *retained_string = lie_json_value_at(retained_array, false, 0);
  p = lie_json_value_string(retained_string, &bytes);
  assert(bytes == sizeof(string) && !memcmp(p, string, bytes));
  lie_json_value_release(out); assert(!m.live && !m.bytes);
}
static void lazy_null_sources(void) {
  memory m = {0}; lie_schema_arena_description d;
  lie_schema_arena *a = create(&m, &d);
  lie_json_value *null = NULL;
  assert(lie_schema_arena_clone(a, NULL, &null) == LIE_SCHEMA_OK);
  assert(null && lie_json_value_is_root(null));
  lie_schema_value described = {.kind = LIE_SCHEMA_BOOL, .boolean = true};
  assert(lie_schema_json_describe(NULL, null, &described) == LIE_SCHEMA_OK);
  assert(described.kind == LIE_SCHEMA_NULL);
  described = (lie_schema_value){.kind = LIE_SCHEMA_BOOL, .boolean = true};
  assert(lie_schema_json_describe(NULL, NULL, &described) == LIE_SCHEMA_INVALID);
  assert(described.kind == LIE_SCHEMA_BOOL && described.boolean);

  lie_json_value *object = make(a, LIE_SCHEMA_OBJECT, 0, NULL, 0);
  lie_json_value *one = make(a, LIE_SCHEMA_NUMBER, 1, NULL, 0);
  assert(lie_schema_arena_put(a, object, text("existing"), one) == LIE_SCHEMA_OK);
  const lie_json_value *existing = lie_json_value_find(object, "existing", 8);
  assert(existing && lie_json_value_number(existing, 0) == 1);
  assert(lie_schema_arena_put(a, object, text("existing"), NULL) == LIE_SCHEMA_OK);
  assert(lie_json_value_find(object, "existing", 8) == existing);
  assert(lie_json_value_type(existing) == LIE_JSON_VALUE_NULL);
  assert(lie_schema_arena_put(a, object, text("created"), NULL) == LIE_SCHEMA_OK);
  const char key[] = {'k', '\0', 'x'};
  const lie_schema_bytes name = {key, sizeof(key)};
  assert(lie_schema_arena_append_member(a, object, name, NULL) == LIE_SCHEMA_OK);
  assert(lie_schema_arena_append_member(a, object, name, NULL) == LIE_SCHEMA_OK);
  assert(lie_json_value_object_size(object) == 4);
  const lie_json_value *first = lie_json_value_at(object, true, 2);
  const lie_json_value *second = lie_json_value_at(object, true, 3);
  assert(first && second && first != second);
  assert(lie_json_value_type(first) == LIE_JSON_VALUE_NULL);
  assert(lie_json_value_type(second) == LIE_JSON_VALUE_NULL);
  size_t bytes = 0; const char *stored_key = lie_json_value_key(second, &bytes);
  assert(bytes == sizeof(key) && !memcmp(stored_key, key, bytes));
  lie_json_value *array = make(a, LIE_SCHEMA_ARRAY, 0, NULL, 0);
  assert(lie_schema_arena_append(a, array, NULL) == LIE_SCHEMA_OK);
  const lie_json_value *element = lie_json_value_at(array, false, 0);
  assert(element && lie_json_value_type(element) == LIE_JSON_VALUE_NULL);
  assert(lie_schema_arena_put(a, object, text("array"), array) == LIE_SCHEMA_OK);

  max_align_t sentinel; lie_json_value *untouched = (void *)&sentinel;
  assert(lie_schema_arena_clone(NULL, NULL, &untouched) == LIE_SCHEMA_INVALID);
  assert(untouched == (void *)&sentinel);
  assert(lie_schema_arena_clone(a, NULL, NULL) == LIE_SCHEMA_INVALID);
  assert(lie_schema_arena_put(a, NULL, text("x"), NULL) == LIE_SCHEMA_INVALID);
  assert(lie_schema_arena_append_member(a, NULL, name, NULL) == LIE_SCHEMA_INVALID);
  assert(lie_schema_arena_append(a, NULL, NULL) == LIE_SCHEMA_INVALID);
  assert(lie_schema_arena_take(a, NULL, &untouched) == LIE_SCHEMA_INVALID);
  assert(untouched == (void *)&sentinel);
  const lie_schema_transform_description binding = lie_schema_arena_transform(a);
  lie_schema_node output = &sentinel;
  assert(binding.access.clone(a, NULL, &output) == LIE_SCHEMA_INVALID);
  assert(output == &sentinel);
  assert(binding.access.put(a, object, text("refused"), NULL) == LIE_SCHEMA_INVALID);
  assert(lie_json_value_object_size(object) == 5 && !lie_json_value_find(object, "refused", 7));
  assert(binding.access.append(a, array, NULL) == LIE_SCHEMA_INVALID);
  assert(lie_json_value_array_size(array) == 1);
  assert(binding.access.clone(a, null, &output) == LIE_SCHEMA_OK);
  assert(output && lie_json_value_type(output) == LIE_JSON_VALUE_NULL);

  lie_json_value *taken_null = NULL, *taken_object = NULL;
  assert(lie_schema_arena_take(a, null, &taken_null) == LIE_SCHEMA_OK && taken_null == null);
  assert(lie_schema_arena_take(a, object, &taken_object) == LIE_SCHEMA_OK && taken_object == object);
  lie_schema_arena_release(a);
  assert(m.live && lie_json_value_is_root(taken_null));
  assert(lie_json_value_type(taken_null) == LIE_JSON_VALUE_NULL);
  assert(lie_json_value_object_size(taken_object) == 5);
  assert(lie_json_value_find(taken_object, "existing", 8) == existing);
  const lie_json_value *retained_array = lie_json_value_find(taken_object, "array", 5);
  assert(retained_array && lie_json_value_array_size(retained_array) == 1);
  element = lie_json_value_at(retained_array, false, 0);
  assert(element && lie_json_value_type(element) == LIE_JSON_VALUE_NULL);
  lie_json_value_release(taken_null); lie_json_value_release(taken_object);
  assert(!m.live && !m.bytes);
}
static void lazy_null_refusals(void) {
  memory baseline = {0}; lie_schema_arena_description d;
  lie_schema_arena *a = create(&baseline, &d);
  lie_json_value *root = NULL;
  assert(lie_schema_arena_clone(a, NULL, &root) == LIE_SCHEMA_OK);
  const size_t calls = baseline.calls;
  lie_schema_arena_release(a); assert(!baseline.live && !baseline.bytes);
  max_align_t sentinel;
  for (size_t fail = 1; fail <= calls; ++fail) {
    memory m = {.fail = fail};
    d.allocator = (lie_grammar_allocator){&m, allocate, release};
    a = (void *)&sentinel;
    const lie_schema_status rc = lie_schema_arena_create(&d, &a);
    if (rc == LIE_SCHEMA_OK) {
      root = (void *)&sentinel;
      assert(lie_schema_arena_clone(a, NULL, &root) == LIE_SCHEMA_RESOURCE);
      assert(root == (void *)&sentinel);
      lie_schema_arena_release(a);
    } else assert(rc == LIE_SCHEMA_RESOURCE && a == (void *)&sentinel);
    assert(!m.live && !m.bytes);
  }
  memory m = {0}; lie_schema_arena_description_init(&d);
  d.allocator = (lie_grammar_allocator){&m, allocate, release}; d.store.max_roots = 1;
  assert(lie_schema_arena_create(&d, &a) == LIE_SCHEMA_OK);
  assert(lie_schema_arena_clone(a, NULL, &root) == LIE_SCHEMA_OK);
  lie_json_value *taken = NULL;
  assert(lie_schema_arena_take(a, root, &taken) == LIE_SCHEMA_OK);
  root = (void *)&sentinel;
  assert(lie_schema_arena_clone(a, NULL, &root) == LIE_SCHEMA_CALLBACK);
  assert(root == (void *)&sentinel && lie_json_value_type(taken) == LIE_JSON_VALUE_NULL);
  lie_schema_arena_error error; lie_schema_arena_error_describe(a, &error);
  assert(error.store_status == LIE_JSON_STORE_LIMIT);
  lie_json_store_info info; lie_schema_arena_store_describe(a, &info);
  assert(!info.live_roots && info.accepted_roots == 1);
  lie_schema_arena_release(a); lie_json_value_release(taken);
  assert(!m.live && !m.bytes);
}
static void native_transforms(void) {
  lie_json_value *left = parse("{\"type\":\"number\",\"multipleOf\":0.3,\"minimum\":0.3}");
  lie_json_value *right = parse("{\"type\":\"number\",\"multipleOf\":0.2,\"maximum\":1.2}");
  memory m = {0}; lie_schema_arena_description description;
  lie_schema_arena *a = create(&m, &description);
  const lie_schema_transform_description d = lie_schema_arena_transform(a);
  lie_schema_node merged = NULL; lie_schema_error e = {0};
  assert(lie_schema_conjoin(&d, left, left, right, 0, &merged, &e) == LIE_SCHEMA_OK);
  assert(lie_json_value_number(lie_json_value_find(merged, "multipleOf", 10), 0) == 0.6);
  assert(lie_json_value_number(lie_json_value_find(merged, "minimum", 7), 0) == 0.3);
  assert(lie_json_value_number(lie_json_value_find(merged, "maximum", 7), 0) == 1.2);
  assert(lie_json_value_number(lie_json_value_find(left, "multipleOf", 10), 0) == 0.3);
  assert(lie_json_value_number(lie_json_value_find(right, "multipleOf", 10), 0) == 0.2);
  lie_json_value *format = NULL;
  assert(lie_schema_arena_format(a, text("ipv4"), &format) == LIE_SCHEMA_OK);
  size_t bytes = 0; const char *pattern = lie_json_value_string(lie_json_value_find(format, "pattern", 7), &bytes);
  assert(pattern && bytes && pattern[0] == '^' && pattern[bytes - 1] == '$');
  max_align_t sentinel; lie_json_value *untouched = (void *)&sentinel;
  assert(lie_schema_arena_format(a, text("unsupported-format"), &untouched) == LIE_SCHEMA_INVALID);
  assert(untouched == (void *)&sentinel);
  lie_schema_arena_error error; lie_schema_arena_error_describe(a, &error);
  assert(error.schema_error.message);
  lie_schema_transform_description reader = lie_schema_arena_transform(NULL);
  bool equal = false;
  assert(lie_schema_equal(&reader, merged, merged, &equal, &e) == LIE_SCHEMA_OK && equal);
  lie_schema_node output = &sentinel;
  assert(reader.access.clone(NULL, left, &output) == LIE_SCHEMA_INVALID && output == &sentinel);
  lie_schema_arena_release(a); assert(!m.live && !m.bytes);
  lie_json_value_release(left); lie_json_value_release(right);
}
static void allocation_and_admission(void) {
  lie_json_value *source = parse("{\"a\":[1,2,3],\"s\":\"copied\"}");
  memory baseline = {0}; lie_schema_arena_description d;
  lie_schema_arena *a = create(&baseline, &d);
  lie_json_value *copy = NULL;
  assert(lie_schema_arena_clone(a, source, &copy) == LIE_SCHEMA_OK);
  size_t calls = baseline.calls;
  lie_schema_arena_release(a); assert(!baseline.live && !baseline.bytes);
  max_align_t sentinel;
  for (size_t fail = 1; fail <= calls; ++fail) {
    memory m = {.fail = fail}; d.allocator = (lie_grammar_allocator){&m, allocate, release};
    a = (void *)&sentinel;
    lie_schema_status rc = lie_schema_arena_create(&d, &a);
    if (rc == LIE_SCHEMA_OK) {
      copy = (void *)&sentinel;
      assert(lie_schema_arena_clone(a, source, &copy) == LIE_SCHEMA_RESOURCE);
      assert(copy == (void *)&sentinel);
      lie_schema_arena_release(a);
    } else assert(rc == LIE_SCHEMA_RESOURCE && a == (void *)&sentinel);
    assert(!m.live && !m.bytes);
  }
  memory m = {0}; lie_schema_arena_description_init(&d);
  d.allocator = (lie_grammar_allocator){&m, allocate, release}; d.store.max_roots = 1;
  assert(lie_schema_arena_create(&d, &a) == LIE_SCHEMA_OK);
  assert(lie_schema_arena_clone(a, source, &copy) == LIE_SCHEMA_OK);
  lie_json_value *taken = NULL;
  assert(lie_schema_arena_take(a, copy, &taken) == LIE_SCHEMA_OK);
  copy = (void *)&sentinel;
  assert(lie_schema_arena_clone(a, source, &copy) == LIE_SCHEMA_CALLBACK && copy == (void *)&sentinel);
  lie_schema_arena_error error; lie_schema_arena_error_describe(a, &error);
  assert(error.store_status == LIE_JSON_STORE_LIMIT);
  lie_json_store_info info; lie_schema_arena_store_describe(a, &info);
  assert(info.live_roots == 0 && info.accepted_roots == 1);
  lie_schema_arena_release(a); lie_json_value_release(taken);
  assert(!m.live && !m.bytes); lie_json_value_release(source);
}
int main(void) {
  ownership(); lazy_null_sources(); lazy_null_refusals();
  native_transforms(); allocation_and_admission();
  puts("Native schema arena construction/ownership: HOST NOT-INFERENCE");
  return 0;
}
