/* SPDX-License-Identifier: MIT */
/* Independent typed-tree, finite-language and complete refusal oracles. */
#include "lie/schema_values.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct node node;
typedef struct {
  char key[128];
  size_t bytes;
  node *value;
} edge;
struct node {
  node *next;
  lie_schema_value value;
  char text[1024];
  edge edges[32];
};
typedef struct {
  node *nodes;
  size_t calls, fail_at;
} arena;
typedef union {
  max_align_t align;
  size_t bytes;
} header;
typedef struct {
  size_t calls, fail_at, live, bytes, peak;
} memory;
static size_t oracles, callback_refusals, allocation_refusals;
static void *alloc(void *p, size_t n) {
  memory *m = p;
  if (++m->calls == m->fail_at)
    return NULL;
  header *h = malloc(sizeof(*h) + n);
  assert(h);
  h->bytes = n;
  ++m->live;
  m->bytes += n;
  if (m->bytes > m->peak)
    m->peak = m->bytes;
  return h + 1;
}
static void dealloc(void *p, void *n) {
  memory *m = p;
  header *h = (header *)n - 1;
  assert(m->live && m->bytes >= h->bytes);
  --m->live;
  m->bytes -= h->bytes;
  free(h);
}
static bool refusal(arena *a) { return ++a->calls == a->fail_at; }
static node *make(arena *a, lie_schema_kind kind, const char *text,
                  size_t bytes, double number) {
  node *n = calloc(1, sizeof(*n));
  assert(n && bytes < sizeof(n->text));
  n->next = a->nodes;
  a->nodes = n;
  n->value.kind = kind;
  n->value.number = number;
  if (bytes)
    memcpy(n->text, text, bytes);
  n->value.text = (lie_schema_bytes){n->text, bytes};
  return n;
}
static node *str(arena *a, const char *s) {
  return make(a, LIE_SCHEMA_STRING, s, strlen(s), 0);
}
static node *num(arena *a, double n) {
  return make(a, LIE_SCHEMA_NUMBER, NULL, 0, n);
}
static node *obj(arena *a) { return make(a, LIE_SCHEMA_OBJECT, NULL, 0, 0); }
static node *arr(arena *a) { return make(a, LIE_SCHEMA_ARRAY, NULL, 0, 0); }
static void add(node *n, const char *key, size_t bytes, node *value) {
  assert(n->value.count < 32 && bytes < 128);
  edge *e = &n->edges[n->value.count++];
  if (bytes)
    memcpy(e->key, key, bytes);
  e->bytes = bytes;
  e->value = value;
}
static void field(node *n, const char *key, node *value) {
  for (size_t i = 0; i < n->value.count; ++i)
    if (n->edges[i].bytes == strlen(key) &&
        !memcmp(n->edges[i].key, key, strlen(key))) {
      n->edges[i].value = value;
      return;
    }
  add(n, key, strlen(key), value);
}
static node *get(node *n, const char *key) {
  for (size_t i = 0; i < n->value.count; ++i)
    if (n->edges[i].bytes == strlen(key) &&
        !memcmp(n->edges[i].key, key, strlen(key)))
      return n->edges[i].value;
  return NULL;
}
static void clear(arena *a) {
  while (a->nodes) {
    node *n = a->nodes;
    a->nodes = n->next;
    free(n);
  }
}
static node *copy(arena *a, const node *n) {
  node *out = make(a, n->value.kind, n->value.text.data, n->value.text.size,
                   n->value.number);
  out->value.boolean = n->value.boolean;
  for (size_t i = 0; i < n->value.count; ++i)
    add(out, n->edges[i].key, n->edges[i].bytes, copy(a, n->edges[i].value));
  return out;
}
static lie_schema_status describe(void *p, lie_schema_node n,
                                  lie_schema_value *v) {
  if (refusal(p))
    return LIE_SCHEMA_CALLBACK;
  *v = ((const node *)n)->value;
  return LIE_SCHEMA_OK;
}
static lie_schema_status invalid_describe(void *p, lie_schema_node n,
                                          lie_schema_value *v) {
  lie_schema_status rc = describe(p, n, v);
  if (!rc)
    v->kind = (lie_schema_kind)-1;
  return rc;
}
static lie_schema_status child(void *p, lie_schema_node n, size_t i,
                               lie_schema_bytes *key, lie_schema_node *out) {
  if (refusal(p))
    return LIE_SCHEMA_CALLBACK;
  const node *v = n;
  assert(i < v->value.count);
  *key = (lie_schema_bytes){v->edges[i].key, v->edges[i].bytes};
  *out = v->edges[i].value;
  return LIE_SCHEMA_OK;
}
static lie_schema_status clone(void *p, lie_schema_node n,
                               lie_schema_node *out) {
  if (refusal(p))
    return LIE_SCHEMA_CALLBACK;
  *out = copy(p, n);
  return LIE_SCHEMA_OK;
}
static lie_schema_status create(void *p, const lie_schema_value *v,
                                lie_schema_node *out) {
  if (refusal(p))
    return LIE_SCHEMA_CALLBACK;
  node *n = make(p, v->kind, v->text.data, v->text.size, v->number);
  n->value.boolean = v->boolean;
  *out = n;
  return LIE_SCHEMA_OK;
}
static lie_schema_status put(void *p, lie_schema_node n, lie_schema_bytes key,
                             lie_schema_node value) {
  if (refusal(p))
    return LIE_SCHEMA_CALLBACK;
  node *target = (node *)n;
  node *v = copy(p, value);
  for (size_t i = 0; i < target->value.count; ++i)
    if (target->edges[i].bytes == key.size &&
        !memcmp(target->edges[i].key, key.data, key.size)) {
      target->edges[i].value = v;
      return LIE_SCHEMA_OK;
    }
  add(target, key.data, key.size, v);
  return LIE_SCHEMA_OK;
}
static lie_schema_status append(void *p, lie_schema_node n,
                                lie_schema_node value) {
  if (refusal(p))
    return LIE_SCHEMA_CALLBACK;
  add((node *)n, NULL, 0, copy(p, value));
  return LIE_SCHEMA_OK;
}
static lie_schema_status format(void *p, lie_schema_bytes name,
                                lie_schema_node *out) {
  if (refusal(p))
    return LIE_SCHEMA_CALLBACK;
  node *n = obj(p);
  field(n, "pattern", make(p, LIE_SCHEMA_STRING, name.data, name.size, 0));
  *out = n;
  return LIE_SCHEMA_OK;
}
static lie_schema_status multiple(void *p, lie_schema_node l, lie_schema_node r,
                                  lie_schema_node *out) {
  if (refusal(p))
    return LIE_SCHEMA_CALLBACK;
  unsigned a = (unsigned)((const node *)l)->value.number,
           b = (unsigned)((const node *)r)->value.number;
  if (!a || !b)
    return LIE_SCHEMA_EMPTY;
  unsigned n = a;
  while (n % b)
    n += a;
  *out = num(p, n);
  return LIE_SCHEMA_OK;
}
static lie_schema_transform_description description(arena *a, memory *m) {
  lie_schema_transform_description d;
  lie_schema_transform_description_init(&d);
  d.access = (lie_schema_access){a,   describe, child,  clone,   create,
                                 put, append,   format, multiple};
  if (m)
    d.allocator = (lie_grammar_allocator){m, alloc, dealloc};
  return d;
}
static node *schema(arena *a, const char *type) {
  node *n = obj(a);
  field(n, "type", str(a, type));
  return n;
}
static lie_schema_status accept(void *p, lie_schema_node schema_node,
                                lie_schema_node value, bool *out) {
  arena *a = p;
  if (refusal(a))
    return LIE_SCHEMA_CALLBACK;
  (void)value;
  node *policy = get((node *)schema_node, "accept");
  if (policy && policy->value.number == 2)
    return LIE_SCHEMA_EMPTY;
  *out = !policy || policy->value.number != 0;
  return LIE_SCHEMA_OK;
}
static lie_schema_status number_literal(void *p, lie_schema_node value,
                                        lie_grammar_builder *b, uint32_t *out) {
  if (refusal(p))
    return LIE_SCHEMA_CALLBACK;
  char text[32];
  const int n =
      snprintf(text, sizeof(text), "%.0f", ((const node *)value)->value.number);
  assert(n > 0 && (size_t)n < sizeof(text));
  const lie_builder_status rc =
      lie_builder_literal(b, (const uint8_t *)text, (size_t)n, out);
  return rc == LIE_BUILDER_OK         ? LIE_SCHEMA_OK
         : rc == LIE_BUILDER_RESOURCE ? LIE_SCHEMA_RESOURCE
                                      : LIE_SCHEMA_INVALID;
}
static lie_schema_values_description values(arena *a, memory *m) {
  lie_schema_values_description d;
  lie_schema_values_description_init(&d);
  d.transform = description(a, m);
  d.leaf_context = a;
  d.accept = accept;
  d.number_literal = number_literal;
  return d;
}
static void type_and_normalization(void) {
  arena a = {0};
  lie_schema_values_description d = values(&a, NULL);
  lie_schema_error e = {0};
  node *nodes[] = {make(&a, LIE_SCHEMA_NULL, NULL, 0, 0),
                   make(&a, LIE_SCHEMA_BOOL, NULL, 0, 0),
                   num(&a, 2),
                   str(&a, "x"),
                   arr(&a),
                   obj(&a),
                   num(&a, 1.5)};
  const char *types[] = {"null",  "boolean", "number",  "string",
                         "array", "object",  "integer", "invalid"};
  for (size_t i = 0; i < 7; ++i)
    for (size_t j = 0; j < 8; ++j) {
      const bool expected =
          (i == j && i < 6) || (i == 6 && j == 2) || (i == 2 && j == 6);
      bool result = !expected;
      assert(lie_schema_matches_type(
                 &d, nodes[i], (lie_schema_bytes){types[j], strlen(types[j])},
                 &result, &e) == LIE_SCHEMA_OK &&
             result == expected);
      ++oracles;
    }
  node *root = obj(&a), *s = schema(&a, "object"), *props = obj(&a),
       *input = obj(&a), *required = arr(&a);
  field(props, "a", schema(&a, "number"));
  field(props, "b", schema(&a, "string"));
  field(s, "properties", props);
  field(s, "required", required);
  add(required, NULL, 0, str(&a, "a"));
  field(input, "b", str(&a, "x"));
  field(input, "extra", num(&a, 3));
  field(input, "a", num(&a, 2));
  lie_schema_normalized n = {0};
  assert(lie_schema_normalize(&d, root, s, input, 0, &n, &e) == LIE_SCHEMA_OK &&
         n.matched);
  const node *canonical = n.value;
  assert(canonical->value.count == 3 && !strcmp(canonical->edges[0].key, "a") &&
         !strcmp(canonical->edges[1].key, "b") &&
         !strcmp(canonical->edges[2].key, "extra"));
  ++oracles;
  assert(!strcmp(input->edges[0].key, "b") &&
         !strcmp(input->edges[1].key, "extra"));
  field(s, "additionalProperties", make(&a, LIE_SCHEMA_BOOL, NULL, 0, 0));
  assert(lie_schema_normalize(&d, root, s, input, 0, &n, &e) == LIE_SCHEMA_OK &&
         !n.matched && !n.value);
  ++oracles;
  node *number = schema(&a, "number"), *enumeration = arr(&a);
  add(enumeration, NULL, 0, num(&a, 2));
  field(number, "enum", enumeration);
  for (unsigned i = 0; i < 5; ++i) {
    assert(lie_schema_normalize(&d, root, number, num(&a, i), 0, &n, &e) ==
               LIE_SCHEMA_OK &&
           n.matched == (i == 2));
    ++oracles;
  }
  field(number, "const", num(&a, 3));
  assert(lie_schema_normalize(&d, root, number, num(&a, 2), 0, &n, &e) ==
             LIE_SCHEMA_OK &&
         !n.matched);
  ++oracles;
  node *branches = arr(&a), *choice = obj(&a), *empty = schema(&a, "number"),
       *yes = schema(&a, "number");
  field(empty, "accept", num(&a, 2));
  add(branches, NULL, 0, empty);
  add(branches, NULL, 0, yes);
  field(choice, "anyOf", branches);
  assert(lie_schema_normalize(&d, root, choice, num(&a, 1), 0, &n, &e) ==
             LIE_SCHEMA_OK &&
         n.matched);
  ++oracles;
  node *defs = obj(&a), *reference = obj(&a);
  field(defs, "value", yes);
  field(root, "$defs", defs);
  field(reference, "$ref", str(&a, "#/$defs/value"));
  assert(lie_schema_normalize(&d, root, reference, num(&a, 1), 0, &n, &e) ==
             LIE_SCHEMA_OK &&
         n.matched);
  ++oracles;
  field(reference, "$ref", str(&a, "#"));
  field(root, "$ref", str(&a, "#"));
  n = (lie_schema_normalized){true, input};
  assert(lie_schema_normalize(&d, root, reference, input, 0, &n, &e) ==
             LIE_SCHEMA_INVALID &&
         n.matched && n.value == input);
  ++oracles;
  node *array = schema(&a, "array"), *items = arr(&a);
  field(array, "items", yes);
  field(array, "minItems", num(&a, 1));
  field(array, "maxItems", num(&a, 2));
  add(items, NULL, 0, num(&a, 1));
  add(items, NULL, 0, num(&a, 2));
  assert(lie_schema_normalize(&d, array, array, items, 0, &n, &e) ==
             LIE_SCHEMA_OK &&
         n.matched);
  ++oracles;
  add(items, NULL, 0, num(&a, 3));
  assert(lie_schema_normalize(&d, array, array, items, 0, &n, &e) ==
             LIE_SCHEMA_OK &&
         !n.matched);
  ++oracles;
  bool matched = true;
  d.transform.access.describe = invalid_describe;
  assert(lie_schema_matches_type(&d, input, (lie_schema_bytes){"object", 6},
                                 &matched, &e) == LIE_SCHEMA_INVALID &&
         matched);
  ++oracles;
  clear(&a);
}
static void character_and_refusal_oracles(void) {
  arena a = {0};
  memory m = {0};
  lie_schema_values_description d = values(&a, &m);
  lie_schema_error e = {0};
  node *root = obj(&a), *array = arr(&a);
  field(root, "é", array);
  add(array, NULL, 0, str(&a, "😀x"));
  add(array, NULL, 0, num(&a, 12));
  size_t count = 999;
  assert(lie_schema_value_characters(&d, root, &count, &e) == LIE_SCHEMA_OK &&
         count == 3 && !m.calls);
  ++oracles;
  const size_t calls = a.calls;
  for (size_t i = 1; i <= calls; ++i) {
    a.calls = 0;
    a.fail_at = i;
    count = 999;
    assert(lie_schema_value_characters(&d, root, &count, &e) ==
               LIE_SCHEMA_CALLBACK &&
           count == 999 && !m.live);
    ++callback_refusals;
  }
  a.fail_at = 0;
  d.max_characters = 2;
  count = 999;
  assert(lie_schema_value_characters(&d, root, &count, &e) ==
             LIE_SCHEMA_INVALID &&
         count == 999);
  ++oracles;
  d.max_characters = 120000;
  node *deep = str(&a, "x");
  for (size_t i = 0; i < 200; ++i) {
    node *next = arr(&a);
    add(next, NULL, 0, deep);
    deep = next;
  }
  m.calls = 0;
  assert(lie_schema_value_characters(&d, deep, &count, &e) == LIE_SCHEMA_OK &&
         count == 1 && !m.live);
  ++oracles;
  const size_t allocations = m.calls;
  assert(allocations > 0);
  for (size_t i = 1; i <= allocations; ++i) {
    m.calls = 0;
    m.fail_at = i;
    count = 999;
    assert(lie_schema_value_characters(&d, deep, &count, &e) ==
               LIE_SCHEMA_RESOURCE &&
           count == 999 && !m.live && !m.bytes);
    ++allocation_refusals;
  }
  m.fail_at = 0;
  d.max_depth = 10;
  count = 999;
  assert(lie_schema_value_characters(&d, deep, &count, &e) ==
             LIE_SCHEMA_INVALID &&
         count == 999 && !m.live);
  ++oracles;
  d.max_depth = 256;
  d.transform.max_work = 1;
  count = 999;
  assert(lie_schema_value_characters(&d, root, &count, &e) ==
             LIE_SCHEMA_WORK_LIMIT &&
         count == 999 && !m.live);
  ++oracles;
  clear(&a);
}
static lie_grammar_builder *builder(memory *m) {
  lie_builder_description d;
  lie_builder_description_init(&d);
  if (m)
    d.allocator = (lie_grammar_allocator){m, alloc, dealloc};
  lie_grammar_builder *b = NULL;
  assert(lie_builder_create(&d, &b) == LIE_BUILDER_OK);
  return b;
}
static lie_grammar_program *program(lie_grammar_builder *b, uint32_t root) {
  lie_grammar_description d;
  assert(lie_builder_finish(b, root, 0, &d) == LIE_BUILDER_OK);
  lie_grammar_program *p = NULL;
  assert(lie_grammar_program_create(&d, &p) == LIE_GRAMMAR_OK);
  lie_builder_release(b);
  return p;
}
static bool text(const lie_grammar_program *p, const char *input) {
  lie_grammar_state *s = NULL;
  assert(lie_grammar_start(p, &s) == LIE_GRAMMAR_OK);
  for (size_t i = 0; input[i]; ++i) {
    lie_grammar_state *next = NULL;
    assert(lie_grammar_advance(p, s, (uint8_t)input[i], &next) ==
           LIE_GRAMMAR_OK);
    lie_grammar_state_release(s);
    s = next;
  }
  bool result = lie_grammar_complete(s);
  lie_grammar_state_release(s);
  return result;
}
typedef struct {
  arena *a;
  lie_grammar_builder *b;
  size_t calls, fail_at;
} visitor;
static lie_schema_status visit(void *p, lie_schema_node n, size_t depth,
                               uint32_t *out) {
  visitor *v = p;
  (void)n;
  assert(depth == 1);
  if (++v->calls == v->fail_at)
    return LIE_SCHEMA_CALLBACK;
  return number_literal(v->a, num(v->a, 1), v->b, out);
}
static void literals_and_containers(void) {
  arena a = {0};
  lie_schema_values_description d = values(&a, NULL);
  lie_schema_error e = {0};
  node *value = obj(&a), *array = arr(&a);
  add(array, NULL, 0, str(&a, "a\n\"\\"));
  add(array, NULL, 0, num(&a, 2));
  field(value, "k\t", array);
  lie_grammar_builder *b = builder(NULL);
  uint32_t ws, root;
  assert(lie_builder_sequence_make(b, NULL, 0, &ws) == LIE_BUILDER_OK);
  assert(lie_schema_value_literal(&d, value, b, ws, &root, &e) ==
         LIE_SCHEMA_OK);
  lie_grammar_program *p = program(b, root);
  assert(text(p, "{\"k\\t\":[\"a\\n\\\"\\\\\",2]}") && !text(p, "{}") &&
         !text(p, "{\"k\\t\":[2]}"));
  oracles += 3;
  lie_grammar_program_release(p);
  for (unsigned mask = 0; mask < 8; ++mask) {
    node *s = schema(&a, "object"), *props = obj(&a), *required = arr(&a);
    const char *keys[] = {"a", "b", "c"};
    for (unsigned i = 0; i < 3; ++i) {
      field(props, keys[i], obj(&a));
      if (mask & (1u << i))
        add(required, NULL, 0, str(&a, keys[i]));
    }
    field(s, "properties", props);
    field(s, "required", required);
    field(s, "additionalProperties", make(&a, LIE_SCHEMA_BOOL, NULL, 0, 0));
    b = builder(NULL);
    assert(lie_builder_sequence_make(b, NULL, 0, &ws) == LIE_BUILDER_OK);
    visitor v = {&a, b, 0, 0};
    lie_schema_container_counts counts = {0};
    assert(lie_schema_object(&d, s, 0, false, b, ws,
                             (lie_schema_visit){&v, visit}, &counts, &root,
                             &e) == LIE_SCHEMA_OK &&
           counts.properties == 3 && counts.characters == 3 && v.calls == 3);
    p = program(b, root);
    for (unsigned selected = 0; selected < 8; ++selected) {
      char sample[64] = "{";
      size_t at = 1;
      for (unsigned i = 0; i < 3; ++i)
        if (selected & (1u << i))
          at += (size_t)snprintf(sample + at, sizeof(sample) - at, "%s\"%s\":1",
                                 at > 1 ? "," : "", keys[i]);
      sample[at++] = '}';
      sample[at] = '\0';
      assert(text(p, sample) == ((selected & mask) == mask));
      ++oracles;
    }
    assert(!text(p, "{\"c\":1,\"a\":1}") && !text(p, "{\"a\":1,\"a\":1}"));
    oracles += 2;
    lie_grammar_program_release(p);
    b = builder(NULL);
    assert(lie_builder_sequence_make(b, NULL, 0, &ws) == LIE_BUILDER_OK);
    v = (visitor){&a, b, 0, 1};
    counts = (lie_schema_container_counts){0};
    root = UINT32_MAX;
    assert(lie_schema_object(&d, s, 0, false, b, ws,
                             (lie_schema_visit){&v, visit}, &counts, &root,
                             &e) == LIE_SCHEMA_CALLBACK &&
           root == UINT32_MAX);
    ++callback_refusals;
    lie_builder_release(b);
  }
  for (unsigned low = 0; low < 4; ++low)
    for (unsigned high = low; high < 5; ++high) {
      node *s = schema(&a, "array");
      field(s, "items", obj(&a));
      field(s, "minItems", num(&a, low));
      field(s, "maxItems", num(&a, high));
      b = builder(NULL);
      assert(lie_builder_sequence_make(b, NULL, 0, &ws) == LIE_BUILDER_OK);
      visitor v = {&a, b, 0, 0};
      assert(lie_schema_array(&d, s, 0, b, ws, (lie_schema_visit){&v, visit},
                              &root, &e) == LIE_SCHEMA_OK &&
             v.calls == 1);
      p = program(b, root);
      for (unsigned n = 0; n < 7; ++n) {
        char sample[64] = "[";
        size_t at = 1;
        for (unsigned i = 0; i < n; ++i)
          at += (size_t)snprintf(sample + at, sizeof(sample) - at, "%s1",
                                 i ? "," : "");
        sample[at++] = ']';
        sample[at] = '\0';
        assert(text(p, sample) == (n >= low && n <= high));
        ++oracles;
      }
      lie_grammar_program_release(p);
    }
  clear(&a);
}
static void normalization_callback_refusals(void) {
  arena a = {0};
  memory m = {0};
  lie_schema_values_description d = values(&a, &m);
  lie_schema_error e = {0};
  node *s = schema(&a, "object"), *props = obj(&a), *input = obj(&a),
       *items = schema(&a, "array"), *array = arr(&a);
  field(items, "items", schema(&a, "string"));
  field(props, "a", items);
  field(s, "properties", props);
  field(input, "a", array);
  add(array, NULL, 0, str(&a, "x"));
  lie_schema_normalized out = {0};
  a.calls = 0;
  assert(lie_schema_normalize(&d, s, s, input, 0, &out, &e) == LIE_SCHEMA_OK &&
         out.matched);
  const size_t calls = a.calls;
  for (size_t i = 1; i <= calls; ++i) {
    a.calls = 0;
    a.fail_at = i;
    out = (lie_schema_normalized){true, input};
    assert(lie_schema_normalize(&d, s, s, input, 0, &out, &e) ==
               LIE_SCHEMA_CALLBACK &&
           out.matched && out.value == input && !m.live);
    ++callback_refusals;
  }
  clear(&a);
}
static void literal_and_required_refusals(void) {
  arena a = {0};
  memory m = {0};
  lie_schema_values_description d = values(&a, &m);
  lie_schema_error e = {0};
  char long_text[512];
  memset(long_text, 'x', sizeof(long_text) - 1);
  long_text[sizeof(long_text) - 1] = '\0';
  node *value = obj(&a);
  for (unsigned i = 0; i < 10; ++i) {
    char key[16];
    snprintf(key, sizeof(key), "k%u", i);
    field(value, key, str(&a, long_text));
  }
  uint32_t ws, root;
  lie_grammar_builder *b = builder(NULL);
  assert(lie_builder_sequence_make(b, NULL, 0, &ws) == LIE_BUILDER_OK);
  m.calls = 0;
  a.calls = 0;
  assert(lie_schema_value_literal(&d, value, b, ws, &root, &e) ==
         LIE_SCHEMA_OK);
  const size_t allocations = m.calls, calls = a.calls;
  assert(allocations > 1 && !m.live);
  lie_builder_release(b);
  for (size_t i = 1; i <= allocations; ++i) {
    b = builder(NULL);
    assert(lie_builder_sequence_make(b, NULL, 0, &ws) == LIE_BUILDER_OK);
    m.calls = 0;
    m.fail_at = i;
    root = UINT32_MAX;
    assert(lie_schema_value_literal(&d, value, b, ws, &root, &e) ==
               LIE_SCHEMA_RESOURCE &&
           root == UINT32_MAX && !m.live && !m.bytes);
    ++allocation_refusals;
    lie_builder_release(b);
  }
  m.fail_at = 0;
  for (size_t i = 1; i <= calls; ++i) {
    b = builder(NULL);
    assert(lie_builder_sequence_make(b, NULL, 0, &ws) == LIE_BUILDER_OK);
    a.calls = 0;
    a.fail_at = i;
    root = UINT32_MAX;
    assert(lie_schema_value_literal(&d, value, b, ws, &root, &e) ==
               LIE_SCHEMA_CALLBACK &&
           root == UINT32_MAX && !m.live);
    ++callback_refusals;
    lie_builder_release(b);
  }
  a.fail_at = 0;
  node *s = schema(&a, "object"), *props = obj(&a), *required = arr(&a);
  for (unsigned i = 0; i < 20; ++i) {
    char key[16];
    snprintf(key, sizeof(key), "p%u", i);
    field(props, key, obj(&a));
    add(required, NULL, 0, str(&a, key));
  }
  field(s, "properties", props);
  field(s, "required", required);
  field(s, "additionalProperties", make(&a, LIE_SCHEMA_BOOL, NULL, 0, 0));
  b = builder(NULL);
  assert(lie_builder_sequence_make(b, NULL, 0, &ws) == LIE_BUILDER_OK);
  visitor v = {&a, b, 0, 0};
  lie_schema_container_counts counts = {0};
  m.calls = 0;
  assert(lie_schema_object(&d, s, 0, true, b, ws, (lie_schema_visit){&v, visit},
                           &counts, &root, &e) == LIE_SCHEMA_OK &&
         !m.live);
  const size_t required_allocations = m.calls;
  assert(required_allocations == 1);
  ++oracles;
  lie_builder_release(b);
  b = builder(NULL);
  assert(lie_builder_sequence_make(b, NULL, 0, &ws) == LIE_BUILDER_OK);
  v = (visitor){&a, b, 0, 0};
  counts = (lie_schema_container_counts){0};
  m.calls = 0;
  m.fail_at = 1;
  root = UINT32_MAX;
  assert(lie_schema_object(&d, s, 0, true, b, ws, (lie_schema_visit){&v, visit},
                           &counts, &root, &e) == LIE_SCHEMA_RESOURCE &&
         root == UINT32_MAX && !m.live);
  ++allocation_refusals;
  lie_builder_release(b);
  m.fail_at = 0;
  b = builder(NULL);
  assert(lie_builder_sequence_make(b, NULL, 0, &ws) == LIE_BUILDER_OK);
  v = (visitor){&a, b, 0, 1};
  counts = (lie_schema_container_counts){0};
  root = UINT32_MAX;
  assert(lie_schema_object(&d, s, 0, true, b, ws, (lie_schema_visit){&v, visit},
                           &counts, &root, &e) == LIE_SCHEMA_CALLBACK &&
         root == UINT32_MAX && !m.live);
  ++callback_refusals;
  lie_builder_release(b);
  b = builder(NULL);
  assert(lie_builder_sequence_make(b, NULL, 0, &ws) == LIE_BUILDER_OK);
  v = (visitor){&a, b, 0, 0};
  counts = (lie_schema_container_counts){4990, 0};
  root = UINT32_MAX;
  assert(lie_schema_object(&d, s, 0, false, b, ws,
                           (lie_schema_visit){&v, visit}, &counts, &root,
                           &e) == LIE_SCHEMA_INVALID &&
         root == UINT32_MAX && !m.live);
  ++oracles;
  lie_builder_release(b);
  clear(&a);
}
int main(void) {
  type_and_normalization();
  character_and_refusal_oracles();
  literals_and_containers();
  normalization_callback_refusals();
  literal_and_required_refusals();
  printf("C17 schema values: %zu independent oracles, %zu callback refusals, "
         "%zu allocation refusals; HOST_NOT_INFERENCE\n",
         oracles, callback_refusals, allocation_refusals);
  return 0;
}
