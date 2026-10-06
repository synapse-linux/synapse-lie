/* SPDX-License-Identifier: MIT */
/* Native publication/order/lifetime/refusal oracles; no model or timing. */
#include "lie/schema_compile.h"
#include "lie/grammar_lexeme.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef union { max_align_t alignment; size_t bytes; } header;
typedef struct { size_t calls, fail, live, bytes; } memory;
typedef struct {
  lie_schema_compile_description d;
  lie_json_value *schema;
  lie_grammar_builder *builder;
  lie_lexeme_table *table;
  uint32_t whitespace;
  memory mem;
  size_t visits, counts, binds;
  unsigned mode;
  bool refuse_visit, refuse_bind, bad_binding, excess_count;
} fixture;
static size_t successes, refusals, allocation_refusals;
static max_align_t sentinel;
static lie_schema_compilation untouched(void) {
  return (lie_schema_compilation){(void *)&sentinel, (void *)&sentinel, 777};
}
static void unchanged(lie_schema_compilation a) {
  assert(a.program == (void *)&sentinel && a.prompt == (void *)&sentinel && a.root == 777);
}
static void *allocate(void *context, size_t bytes) {
  memory *m = context;
  if (++m->calls == m->fail) return NULL;
  assert(bytes <= SIZE_MAX - sizeof(header));
  header *h = malloc(sizeof(*h) + bytes); assert(h);
  h->bytes = bytes; ++m->live; m->bytes += bytes;
  return h + 1;
}
static void release(void *context, void *v) {
  memory *m = context; header *h = (header *)v - 1;
  assert(m->live && m->bytes >= h->bytes);
  --m->live; m->bytes -= h->bytes; free(h);
}
static lie_schema_status describe(void *context, lie_schema_node n, lie_schema_value *out) {
  (void)context;
  const lie_json_value *v = n;
  *out = (lie_schema_value){.count = lie_json_value_size(v)};
  switch (lie_json_value_type(v)) {
  case LIE_JSON_VALUE_NULL: out->kind = LIE_SCHEMA_NULL; break;
  case LIE_JSON_VALUE_BOOL: out->kind = LIE_SCHEMA_BOOL; out->boolean = lie_json_value_boolean(v, false); break;
  case LIE_JSON_VALUE_NUMBER: out->kind = LIE_SCHEMA_NUMBER; out->number = lie_json_value_number(v, 0); break;
  case LIE_JSON_VALUE_STRING:
    out->kind = LIE_SCHEMA_STRING;
    out->text.data = lie_json_value_string(v, &out->text.size); break;
  case LIE_JSON_VALUE_ARRAY: out->kind = LIE_SCHEMA_ARRAY; break;
  case LIE_JSON_VALUE_OBJECT: out->kind = LIE_SCHEMA_OBJECT; break;
  }
  return LIE_SCHEMA_OK;
}
static lie_schema_status child(void *context, lie_schema_node n, size_t i,
    lie_schema_bytes *key, lie_schema_node *out) {
  (void)context;
  const bool object = lie_json_value_type(n) == LIE_JSON_VALUE_OBJECT;
  const lie_json_value *v = lie_json_value_at(n, object, i);
  assert(v); *key = (lie_schema_bytes){0};
  if (object) key->data = lie_json_value_key(v, &key->size);
  *out = v; return LIE_SCHEMA_OK;
}
static lie_schema_status visit(void *context, lie_schema_node n, size_t depth,
    uint32_t *out, lie_schema_error *error) {
  fixture *f = context; assert(n == f->schema && depth == 0);
  ++f->visits; assert(!f->counts && !f->binds);
  if (f->refuse_visit) {
    *error = (lie_schema_error){"visitor refused", {0}, ""};
    return LIE_SCHEMA_CALLBACK;
  }
  if (f->mode == 0)
    assert(lie_builder_literal(f->builder, (const uint8_t *)"{}", 2, out) == LIE_BUILDER_OK);
  else {
    assert(lie_builder_new(f->builder, NULL, 0, out) == LIE_BUILDER_OK);
    if (f->mode == 2) {
      const lie_builder_sequence s = {out, 1};
      assert(lie_builder_set(f->builder, *out, &s, 1) == LIE_BUILDER_OK);
    }
  }
  return LIE_SCHEMA_OK;
}
static size_t count(void *context) {
  fixture *f = context; assert(!f->counts && !f->binds); ++f->counts;
  if (f->excess_count) return SIZE_MAX;
  return f->table ? lie_lexeme_table_size(f->table) : 0;
}
static lie_grammar_status bind(void *context, lie_grammar_predicates *out) {
  fixture *f = context; assert(f->counts == 1 && !f->binds); ++f->binds;
  uint32_t ignored = 0;
  assert(lie_builder_new(f->builder, NULL, 0, &ignored) == LIE_BUILDER_INVALID);
  if (f->refuse_bind) return LIE_GRAMMAR_PREDICATE;
  *out = (lie_grammar_predicates){0};
  if (f->table) {
    assert(lie_lexeme_table_seal(f->table) == LIE_LEXEME_OK);
    *out = lie_lexeme_table_predicates(f->table);
  }
  if (f->bad_binding) *out = (lie_grammar_predicates){0};
  return LIE_GRAMMAR_OK;
}
static void initialize(fixture *f, size_t large, bool object_only) {
  memset(f, 0, sizeof(*f));
  lie_schema_compile_description_init(&f->d);
  f->d.allocator = (lie_grammar_allocator){&f->mem, allocate, release};
  f->d.root.reader.access = (lie_schema_access){.context = f, .describe = describe, .child = child};
  f->d.root.visit.context = f; f->d.root.visit.body = visit;
  f->d.binding_context = f; f->d.lexeme_count = count; f->d.bind = bind;
  lie_builder_description bd; lie_builder_description_init(&bd);
  assert(lie_builder_create(&bd, &f->builder) == LIE_BUILDER_OK);
  if (object_only) {
    lie_lexeme_description ld; lie_lexeme_description_init(&ld);
    lie_grammar_lexeme *p = NULL;
    assert(lie_lexeme_whitespace_create(&ld, &p) == LIE_LEXEME_OK);
    lie_lexeme_table_description td; lie_lexeme_table_description_init(&td);
    assert(lie_lexeme_table_create(&td, &f->table) == LIE_LEXEME_OK);
    assert(lie_lexeme_table_push(f->table, p) == LIE_LEXEME_OK);
    assert(lie_lexeme_table_size(f->table) == 1);
    lie_lexeme_release(p);
    lie_builder_primitives primitives;
    assert(lie_builder_json(f->builder, LIE_GRAMMAR_LEXEME, &primitives) == LIE_BUILDER_OK);
    f->whitespace = primitives.whitespace;
  } else {
    const char *source = "{\"type\":\"object\",\"description\":\"A\\u0000B\\n\\\"\\\\Z\"}";
    lie_json_parse_error error;
    assert(lie_json_value_parse(source, strlen(source), NULL, NULL, &f->schema,
                                 &error, NULL) == LIE_JSON_VALUE_OK);
    if (large) {
      char *bytes = malloc(large); assert(bytes); memset(bytes, 'x', large);
      lie_json_value *v = NULL;
      assert(lie_json_value_member(f->schema, "description", 11, &v) == LIE_JSON_VALUE_OK);
      assert(lie_json_value_set(v, LIE_JSON_VALUE_STRING, false, 0, bytes, large) == LIE_JSON_VALUE_OK);
      free(bytes);
    }
    const lie_builder_sequence epsilon = {NULL, 0};
    assert(lie_builder_new(f->builder, &epsilon, 1, &f->whitespace) == LIE_BUILDER_OK);
  }
}
static void finish(fixture *f) {
  lie_builder_release(f->builder); lie_json_value_release(f->schema);
  lie_lexeme_table_release(f->table);
  assert(!f->mem.live && !f->mem.bytes);
}
static bool accepts(const lie_grammar_program *p, const char *text) {
  lie_grammar_state *s = NULL;
  assert(lie_grammar_start(p, &s) == LIE_GRAMMAR_OK);
  for (const unsigned char *c = (const unsigned char *)text; *c; ++c) {
    lie_grammar_state *next = NULL;
    assert(lie_grammar_advance(p, s, *c, &next) == LIE_GRAMMAR_OK);
    lie_grammar_state_release(s); s = next;
  }
  const bool result = lie_grammar_complete(s); lie_grammar_state_release(s);
  return result;
}
static lie_schema_compile_status compile(fixture *f, bool object_only,
    lie_schema_compilation *out, lie_schema_compile_error *e) {
  return lie_schema_compile(&f->d, f->schema, f->schema, object_only,
                            f->builder, f->whitespace, out, e);
}
int main(void) {
  fixture f; lie_schema_compilation out; lie_schema_compile_error e;
  initialize(&f, 0, false); out = untouched();
  assert(compile(&f, false, &out, &e) == LIE_COMPILE_OK); ++successes;
  size_t bytes = 0;
  const char *prompt = lie_schema_prompt_bytes(out.prompt, &bytes);
  const char *expected = "Respond with a single JSON object matching this JSON Schema:\n"
                         "{\"type\":\"object\",\"description\":\"A\\u0000B\\n\\\"\\\\Z\"}";
  assert(bytes == strlen(expected) && memcmp(prompt, expected, bytes + 1) == 0);
  assert(f.visits == 1 && f.counts == 1 && f.binds == 1);
  lie_builder_release(f.builder); f.builder = NULL;
  lie_json_value_release(f.schema); f.schema = NULL;
  assert(memcmp(prompt, expected, bytes + 1) == 0);
  assert(accepts(out.program, "{}") && !accepts(out.program, "[]"));
  lie_schema_prompt_release(out.prompt);
  assert(accepts(out.program, "{}"));
  lie_grammar_program_release(out.program); finish(&f);
  initialize(&f, 0, true);
  assert(compile(&f, true, &out, &e) == LIE_COMPILE_OK); ++successes;
  assert(!f.visits && f.counts == 1 && f.binds == 1);
  assert(strcmp(lie_schema_prompt_bytes(out.prompt, NULL),
                "Respond with a single valid JSON object.") == 0);
  assert(accepts(out.program, " \t{\"v\":[1,true,null]}\n") && !accepts(out.program, "[]"));
  lie_grammar_program_release(out.program); lie_schema_prompt_release(out.prompt); finish(&f);
  initialize(&f, 100000, false);
  assert(compile(&f, false, &out, &e) == LIE_COMPILE_OK); ++successes;
  const size_t allocations = f.mem.calls;
  lie_schema_prompt_info info; lie_schema_prompt_describe(out.prompt, &info);
  assert(info.bytes > 100000 && info.peak_owned_bytes > info.live_owned_bytes);
  lie_grammar_program_release(out.program); lie_schema_prompt_release(out.prompt); finish(&f);
  for (size_t fail = 1; fail <= allocations; ++fail) {
    initialize(&f, 100000, false); f.mem.fail = fail; out = untouched();
    const lie_schema_compile_status rc = compile(&f, false, &out, &e);
    assert(rc == LIE_COMPILE_RESOURCE ||
          (rc == LIE_COMPILE_PROGRAM && e.grammar_status == LIE_GRAMMAR_RESOURCE));
    unchanged(out); assert(!f.mem.live && !f.mem.bytes); finish(&f); ++allocation_refusals;
  }
  initialize(&f, 100000, false); f.d.max_owned_prompt_bytes = info.live_owned_bytes;
  out = untouched(); assert(compile(&f, false, &out, &e) == LIE_COMPILE_PROMPT_LIMIT);
  unchanged(out); assert(!f.counts && !f.binds); finish(&f); ++refusals;
  initialize(&f, 100000, false); f.d.max_owned_prompt_bytes = info.peak_owned_bytes;
  assert(compile(&f, false, &out, &e) == LIE_COMPILE_OK); ++successes;
  lie_grammar_program_release(out.program); lie_schema_prompt_release(out.prompt); finish(&f);
  for (unsigned mode = 0; mode < 5; ++mode) {
    initialize(&f, 0, false); out = untouched();
    if (mode == 0) { f.refuse_visit = true;
      assert(compile(&f, false, &out, &e) == LIE_COMPILE_SCHEMA && e.schema_status == LIE_SCHEMA_CALLBACK);
      assert(!f.mem.calls && !f.counts && !f.binds);
    } else if (mode == 1) { f.refuse_bind = true;
      assert(compile(&f, false, &out, &e) == LIE_COMPILE_BINDING && e.grammar_status == LIE_GRAMMAR_PREDICATE);
    } else if (mode == 2) { f.d.max_schema_bytes = 1;
      assert(compile(&f, false, &out, &e) == LIE_COMPILE_PROMPT_LIMIT && !f.counts && !f.binds);
    } else { f.mode = mode == 3 ? 1 : 2;
      assert(compile(&f, false, &out, &e) == LIE_COMPILE_BUILDER);
      assert(e.builder_status == (mode == 3 ? LIE_BUILDER_EMPTY : LIE_BUILDER_CYCLE));
      assert(f.counts == 1 && !f.binds);
    }
    unchanged(out); finish(&f); ++refusals;
  }
  for (unsigned invalid = 0; invalid < 6; ++invalid) {
    initialize(&f, 0, false); out = untouched();
    if (invalid == 0) ++f.d.abi_version;
    if (invalid == 1) --f.d.struct_bytes;
    if (invalid == 2) f.d.max_schema_bytes = 0;
    if (invalid == 3) f.d.allocator.release = NULL;
    if (invalid == 4) f.d.lexeme_count = NULL;
    if (invalid == 5) f.d.bind = NULL;
    assert(compile(&f, false, &out, &e) == LIE_COMPILE_INVALID);
    unchanged(out); assert(!f.visits && !f.mem.calls); finish(&f); ++refusals;
  }
  initialize(&f, 0, false); out = untouched();
  lie_json_value *value = NULL;
  assert(lie_json_value_member(f.schema, "description", 11, &value) == LIE_JSON_VALUE_OK);
  assert(lie_json_value_set(value, LIE_JSON_VALUE_NUMBER, false, INFINITY, NULL, 0) == LIE_JSON_VALUE_OK);
  assert(compile(&f, false, &out, &e) == LIE_COMPILE_JSON && e.json_status == LIE_JSON_VALUE_NONFINITE);
  unchanged(out); assert(!f.counts && !f.binds); finish(&f); ++refusals;
  initialize(&f, 0, true); f.bad_binding = true; out = untouched();
  assert(compile(&f, true, &out, &e) == LIE_COMPILE_PROGRAM && e.grammar_status == LIE_GRAMMAR_INVALID);
  unchanged(out); finish(&f); ++refusals;
  initialize(&f, 0, false); f.excess_count = true; out = untouched();
  assert(compile(&f, false, &out, &e) == LIE_COMPILE_BUILDER && e.builder_status != LIE_BUILDER_OK);
  unchanged(out); assert(f.counts == 1 && !f.binds); finish(&f); ++refusals;
  printf("schema compile: %zu publications, %zu refusals, %zu allocator faults; exact prompt/language/order/lifetimes\n",
          successes, refusals, allocation_refusals);
}
