/* SPDX-License-Identifier: MIT */
/* Independent root admission, cleanup/refusal and complete-language oracles. */
#include "lie/schema_root.h"
#include "lie/json_value.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { size_t calls, fail, live; } memory;
typedef struct {
  lie_schema_root_description d;
  lie_grammar_builder *builder;
  lie_json_value *schema;
  memory memo, build;
  size_t calls, fail, visits;
  lie_schema_status visit_status;
  bool bad_view, bad_child, literal_leaf;
} fixture;
static size_t oracles, callback_refusals, allocation_refusals;
static void *allocate(void *p, size_t bytes) {
  memory *m = p;
  if (++m->calls == m->fail) return NULL;
  void *v = malloc(bytes); assert(v); ++m->live; return v;
}
static void release(void *p, void *v) {
  memory *m = p; assert(m->live); --m->live; free(v);
}
static lie_schema_status describe(void *p, lie_schema_node n,
                                 lie_schema_value *out) {
  fixture *f = p;
  if (++f->calls == f->fail) return LIE_SCHEMA_CALLBACK;
  const lie_json_value *v = n;
  *out = (lie_schema_value){.count = lie_json_value_size(v)};
  switch (lie_json_value_type(v)) {
  case LIE_JSON_VALUE_NULL: out->kind = LIE_SCHEMA_NULL; break;
  case LIE_JSON_VALUE_BOOL: out->kind = LIE_SCHEMA_BOOL; break;
  case LIE_JSON_VALUE_NUMBER: out->kind = LIE_SCHEMA_NUMBER; break;
  case LIE_JSON_VALUE_STRING: {
    out->kind = LIE_SCHEMA_STRING;
    size_t bytes = 0;
    const char *text = lie_json_value_string(v, &bytes);
    out->text = (lie_schema_bytes){text, bytes}; break;
  }
  case LIE_JSON_VALUE_ARRAY: out->kind = LIE_SCHEMA_ARRAY; break;
  case LIE_JSON_VALUE_OBJECT: out->kind = LIE_SCHEMA_OBJECT; break;
  }
  if (f->bad_view) out->text = (lie_schema_bytes){NULL, 1};
  return LIE_SCHEMA_OK;
}
static lie_schema_status child(void *p, lie_schema_node n, size_t i,
    lie_schema_bytes *key, lie_schema_node *out) {
  fixture *f = p;
  if (++f->calls == f->fail) return LIE_SCHEMA_CALLBACK;
  bool object = lie_json_value_type(n) == LIE_JSON_VALUE_OBJECT;
  const lie_json_value *v = lie_json_value_at(n, object, i);
  assert(v);
  size_t bytes = 0;
  const char *text = object ? lie_json_value_key(v, &bytes) : NULL;
  *key = (lie_schema_bytes){text, bytes};
  *out = f->bad_child ? NULL : v;
  return LIE_SCHEMA_OK;
}
static lie_schema_status visit(void *p, lie_schema_node n, size_t depth,
    uint32_t *out, lie_schema_error *e) {
  fixture *f = p;
  /* Follow resolved-root policy but compile original identity only after the
   * temporary reference memo is completely retired. */
  assert(n == f->schema && depth == 0 && !f->memo.live);
  ++f->visits;
  if (++f->calls == f->fail) return LIE_SCHEMA_CALLBACK;
  if (f->visit_status) {
    *e = (lie_schema_error){"root visitor refusal", {NULL, 0}, ""};
    return f->visit_status;
  }
  if (f->literal_leaf) { *out = LIE_GRAMMAR_TERMINAL | 'x'; return LIE_SCHEMA_OK; }
  assert(lie_builder_literal(f->builder, (const uint8_t *)"{}", 2, out) ==
         LIE_BUILDER_OK);
  return LIE_SCHEMA_OK;
}
static void initialize(fixture *f, const char *text) {
  memset(f, 0, sizeof(*f));
  lie_schema_root_description_init(&f->d);
  f->d.reader.access.context = f;
  f->d.reader.access.describe = describe;
  f->d.reader.access.child = child;
  f->d.reader.allocator = (lie_grammar_allocator){&f->memo, allocate, release};
  f->d.visit.context = f;
  f->d.visit.body = visit;
  lie_builder_description bd;
  lie_builder_description_init(&bd);
  bd.allocator = (lie_grammar_allocator){&f->build, allocate, release};
  assert(lie_builder_create(&bd, &f->builder) == LIE_BUILDER_OK);
  /* Root fixture uses an empty whitespace rule; generic-object tests use
   * production JSON primitives and the separately qualified whitespace leaf. */
  uint32_t ws;
  assert(lie_builder_sequence_make(f->builder, NULL, 0, &ws) == LIE_BUILDER_OK);
  assert(ws == 0);
  lie_json_value_description jd;
  lie_json_value_description_init(&jd);
  lie_json_parse_description pd;
  lie_json_parse_description_init(&pd);
  assert(lie_json_value_parse(text, strlen(text), &jd, &pd, &f->schema,
                              NULL, NULL) == LIE_JSON_VALUE_OK);
}
static void retire(fixture *f) {
  lie_builder_release(f->builder);
  lie_json_value_release(f->schema);
  assert(!f->memo.live && !f->build.live);
}
static lie_schema_status run(fixture *f, uint32_t *out, lie_schema_error *e) {
  const uint64_t revision = lie_json_value_revision(f->schema);
  const lie_schema_status rc = lie_schema_root_rule(&f->d, f->schema, false,
                                                   f->builder, 0, out, e);
  assert(lie_json_value_revision(f->schema) == revision && !f->memo.live);
  if (rc) assert(*out == UINT32_MAX);
  return rc;
}
static bool accepts(const lie_grammar_program *p, const char *text) {
  lie_grammar_state *s = NULL;
  assert(lie_grammar_start(p, &s) == LIE_GRAMMAR_OK);
  for (const unsigned char *b = (const unsigned char *)text; *b; ++b) {
    lie_grammar_state *next = NULL;
    assert(lie_grammar_advance(p, s, *b, &next) == LIE_GRAMMAR_OK);
    lie_grammar_state_release(s); s = next;
  }
  const bool ok = lie_grammar_complete(s);
  lie_grammar_state_release(s); return ok;
}
static void admission(void) {
  static const struct { const char *schema, *error; } cases[] = {
    {"{\"type\":\"object\"}", NULL},
    {"{\"type\":\"object\",\"anyOf\":null}", "the root must have type object"},
    {"{\"type\":[\"object\"]}", "the root must have type object"},
    {"{\"type\":\"string\"}", "the root must have type object"},
    {"{\"type\":1}", "the root must have type object"},
    {"{}", "the root must have type object"},
    {"false", "the root must have type object"},
    {"[]", "the root must have type object"},
    {"{\"$ref\":\"#\"}", "root reference cycle"},
    {"{\"$ref\":false}", "only local JSON pointer references are supported"},
    {"{\"$ref\":\"elsewhere\"}", "only local JSON pointer references are supported"},
    {"{\"$ref\":\"#/absent\"}", "local reference does not exist"},
    {"{\"$ref\":\"#/~2\"}", "invalid JSON pointer escape"},
    {"{\"$ref\":\"#/~\"}", "invalid JSON pointer escape"},
    {"{\"$ref\":\"#/x\",\"x\":{\"type\":\"object\"}}", NULL},
    {"{\"$ref\":\"#/a~1b~0c\",\"a/b~c\":{\"type\":\"object\"}}", NULL},
    {"{\"$ref\":\"#/x/0\",\"x\":[{\"type\":\"object\"}]}", NULL},
    {"{\"$ref\":\"#/x/1\",\"x\":[{\"type\":\"object\"}]}", "local reference does not exist"},
    {"{\"$ref\":\"#/x/-1\",\"x\":[{\"type\":\"object\"}]}", "local reference does not exist"},
    {"{\"$ref\":\"#/x\",\"x\":{\"$ref\":\"#\"}}", "root reference cycle"},
    {"{\"$ref\":\"#/x\",\"x\":{\"$ref\":\"#/x\"}}", "root reference cycle"},
    {"{\"$ref\":\"#/x\",\"x\":{\"type\":\"object\",\"anyOf\":[]}}", "the root must have type object"},
  };
  for (size_t i = 0; i < sizeof(cases)/sizeof(*cases); ++i) {
    fixture f; initialize(&f, cases[i].schema);
    uint32_t out = UINT32_MAX; lie_schema_error e = {0};
    const lie_schema_status rc = run(&f, &out, &e);
    if (cases[i].error) {
      assert(rc == LIE_SCHEMA_INVALID && e.message &&
             !strcmp(e.message, cases[i].error) && !f.visits);
    } else {
      assert(rc == LIE_SCHEMA_OK && f.visits == 1);
      lie_grammar_description d;
      assert(lie_builder_finish(f.builder, out, 0, &d) == LIE_BUILDER_OK);
      lie_grammar_program *p = NULL;
      assert(lie_grammar_program_create(&d, &p) == LIE_GRAMMAR_OK);
      assert(accepts(p, "{}") && !accepts(p, "{ }") && !accepts(p, "[]") &&
             !accepts(p, "") && !accepts(p, "{}{}"));
      lie_grammar_program_release(p);
    }
    retire(&f); ++oracles;
  }
}
static void refusals(void) {
  const char *chain = "{\"$ref\":\"#/a\",\"a\":{\"$ref\":\"#/b\"},\"b\":{\"type\":\"object\"}}";
  fixture f; initialize(&f, chain);
  uint32_t out = UINT32_MAX; lie_schema_error e = {0};
  assert(run(&f, &out, &e) == LIE_SCHEMA_OK);
  const size_t calls = f.calls, allocations = f.memo.calls;
  retire(&f);
  for (size_t fail = 1; fail <= calls; ++fail) {
    initialize(&f, chain); f.fail = fail; out = UINT32_MAX;
    assert(run(&f, &out, &e) == LIE_SCHEMA_CALLBACK);
    retire(&f); ++callback_refusals;
  }
  for (size_t fail = 1; fail <= allocations; ++fail) {
    initialize(&f, chain); f.memo.fail = fail; out = UINT32_MAX;
    assert(run(&f, &out, &e) == LIE_SCHEMA_RESOURCE && !f.visits);
    retire(&f); ++allocation_refusals;
  }
  for (unsigned mode = 0; mode < 7; ++mode) {
    initialize(&f, chain); out = UINT32_MAX;
    if (mode == 0) f.d.max_references = 1;
    if (mode == 1) f.d.reader.max_work = 1;
    if (mode == 2) f.bad_view = true;
    if (mode == 3) f.bad_child = true;
    if (mode >= 4) f.visit_status = mode == 4 ? LIE_SCHEMA_EMPTY :
        mode == 5 ? LIE_SCHEMA_RESOURCE : LIE_SCHEMA_WORK_LIMIT;
    const lie_schema_status expected = mode <= 1 ? LIE_SCHEMA_WORK_LIMIT :
        mode <= 3 ? LIE_SCHEMA_INVALID : f.visit_status;
    assert(run(&f, &out, &e) == expected);
    if (mode >= 4) assert(!strcmp(e.message, "root visitor refusal"));
    retire(&f); ++oracles;
  }
  initialize(&f, "{\"type\":\"object\"}");
  lie_schema_root_description valid = f.d;
  for (unsigned bad = 0; bad < 9; ++bad) {
    f.d = valid; out = UINT32_MAX;
    if (bad == 0) ++f.d.abi_version;
    if (bad == 1) --f.d.struct_bytes;
    if (bad == 2) f.d.max_references = 0;
    if (bad == 3) f.d.max_references = 262145;
    if (bad == 4) f.d.reader.access.child = NULL;
    if (bad == 5) f.d.visit.body = NULL;
    if (bad == 6) ++f.d.visit.abi_version;
    if (bad == 7) --f.d.visit.struct_bytes;
    if (bad == 8) f.d.reader.allocator.release = NULL;
    assert(run(&f, &out, &e) == LIE_SCHEMA_INVALID && !f.calls);
    ++oracles;
  }
  retire(&f);
  lie_schema_root_description_init(NULL);
}
static void long_chains(void) {
  for (size_t count = 1; count <= 128; count *= 2) {
    char text[16384]; size_t used = (size_t)snprintf(text, sizeof(text),
        "{\"$ref\":\"#/$defs/n0\",\"$defs\":{");
    for (size_t i = 0; i < count; ++i)
      used += (size_t)snprintf(text + used, sizeof(text) - used,
          "%s\"n%zu\":{\"$ref\":\"#/$defs/n%zu\"}", i ? "," : "", i, i + 1);
    used += (size_t)snprintf(text + used, sizeof(text) - used,
        ",\"n%zu\":{\"type\":\"object\"}}}", count);
    assert(used < sizeof(text));
    fixture f; initialize(&f, text);
    uint32_t out = UINT32_MAX; lie_schema_error e = {0};
    assert(run(&f, &out, &e) == LIE_SCHEMA_OK && f.visits == 1);
    retire(&f); ++oracles;
  }
}
static void builder_refusals(void) {
  fixture f; initialize(&f, "{\"type\":\"object\"}");
  f.literal_leaf = true;
  const size_t before = f.build.calls;
  uint32_t out = UINT32_MAX; lie_schema_error e = {0};
  assert(run(&f, &out, &e) == LIE_SCHEMA_OK);
  const size_t allocations = f.build.calls - before;
  assert(allocations);
  retire(&f);
  for (size_t fail = 1; fail <= allocations; ++fail) {
    initialize(&f, "{\"type\":\"object\"}"); f.literal_leaf = true;
    f.build.fail = f.build.calls + fail; out = UINT32_MAX;
    assert(run(&f, &out, &e) == LIE_SCHEMA_RESOURCE && f.visits == 1);
    retire(&f); ++allocation_refusals;
  }
}
static void object_only(void) {
  fixture f; initialize(&f, "false");
  lie_builder_primitives p;
  assert(lie_builder_json(f.builder, LIE_GRAMMAR_LEXEME, &p) == LIE_BUILDER_OK);
  uint32_t root = UINT32_MAX; lie_schema_error e = {0};
  assert(lie_schema_root_rule(&f.d, NULL, true, f.builder, p.whitespace, &root,
      &e) == LIE_SCHEMA_OK && !f.calls && !f.visits && !f.memo.calls);
  lie_grammar_description d;
  assert(lie_builder_finish(f.builder, root, 1, &d) == LIE_BUILDER_OK);
  assert(d.root == root && d.rule_count > 100);
  retire(&f); ++oracles;
}
int main(void) {
  admission(); refusals(); long_chains(); builder_refusals(); object_only();
  printf("SCHEMA_ROOT_ORACLES=%zu CALLBACK_REFUSALS=%zu ALLOCATION_REFUSALS=%zu "
         "CHAIN_MAX=129 IDENTITIES SCRATCH_RETIRED_BEFORE_VISIT HOST_NOT_INFERENCE\n",
         oracles, callback_refusals, allocation_refusals);
}
