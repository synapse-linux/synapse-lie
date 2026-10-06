/* SPDX-License-Identifier: MIT */
/* Independent lifecycle/refusal witnesses. Written for final qualification;
 * not executed during the owner's implementation-first phase. NOT-INFERENCE. */
#include "lie/schema_compiler.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef union { max_align_t alignment; size_t bytes; } header;
typedef struct { size_t calls, fail, live, bytes; } memory;
typedef struct {
  lie_schema_compiler *compiler;
  lie_lexeme_table *table;
  size_t calls, binds;
  unsigned mode;
  bool refuse_bind;
} fixture;
static void *allocate(void *p, size_t bytes) {
  memory *m = p;
  if (++m->calls == m->fail) return NULL;
  assert(bytes <= SIZE_MAX - sizeof(header));
  header *h = malloc(sizeof(*h) + bytes); assert(h);
  h->bytes = bytes; ++m->live; m->bytes += bytes;
  return h + 1;
}
static void release(void *p, void *value) {
  memory *m = p; header *h = (header *)value - 1;
  assert(m->live && m->bytes >= h->bytes);
  --m->live; m->bytes -= h->bytes; free(h);
}
static lie_schema_compiler_phase phase(const lie_schema_compiler *c) {
  lie_schema_compiler_info info; lie_schema_compiler_describe(c, &info);
  return info.phase;
}
static lie_schema_status whitespace(void *p, uint32_t *out) {
  fixture *f = p; ++f->calls;
  assert(phase(f->compiler) == LIE_COMPILER_INITIALIZING);
  if (f->mode == 1) return LIE_SCHEMA_RESOURCE;
  if (f->mode == 2) { *out = LIE_GRAMMAR_TERMINAL; return LIE_SCHEMA_OK; }
  lie_grammar_lexeme *lexeme = NULL;
  assert(lie_lexeme_whitespace_create(NULL, &lexeme) == LIE_LEXEME_OK);
  size_t id = lie_lexeme_table_size(f->table);
  assert(lie_lexeme_table_push(f->table, lexeme) == LIE_LEXEME_OK);
  lie_lexeme_release(lexeme);
  *out = LIE_GRAMMAR_LEXEME | (uint32_t)id;
  return LIE_SCHEMA_OK;
}
static lie_schema_status no_describe(void *p, lie_schema_node n, lie_schema_value *out) {
  (void)p; (void)n; (void)out;
  assert(!"Object-only compilation read a schema"); return LIE_SCHEMA_INVALID;
}
static lie_schema_status no_child(void *p, lie_schema_node n, size_t i,
    lie_schema_bytes *key, lie_schema_node *out) {
  (void)p; (void)n; (void)i; (void)key; (void)out;
  assert(!"Object-only compilation read a schema child"); return LIE_SCHEMA_INVALID;
}
static size_t count(void *p) {
  fixture *f = p; assert(phase(f->compiler) == LIE_COMPILER_PUBLISHING);
  return lie_lexeme_table_size(f->table);
}
static lie_grammar_status bind(void *p, lie_grammar_predicates *out) {
  fixture *f = p; ++f->binds;
  assert(phase(f->compiler) == LIE_COMPILER_PUBLISHING);
  if (f->refuse_bind) return LIE_GRAMMAR_PREDICATE;
  assert(lie_lexeme_table_seal(f->table) == LIE_LEXEME_OK);
  *out = lie_lexeme_table_predicates(f->table);
  return LIE_GRAMMAR_OK;
}
static lie_schema_compiler *create(memory *m, lie_schema_compiler_description *d) {
  lie_schema_compiler_description_init(d);
  d->allocator = (lie_grammar_allocator){m, allocate, release};
  lie_schema_compiler *c = NULL;
  assert(lie_schema_compiler_create(d, &c, NULL) == LIE_COMPILER_OK);
  assert(phase(c) == LIE_COMPILER_NEW);
  return c;
}
static bool accepts(const lie_grammar_program *program, const char *text) {
  lie_grammar_state *state = NULL;
  assert(lie_grammar_start(program, &state) == LIE_GRAMMAR_OK);
  for (size_t i = 0; text[i]; ++i) {
    lie_grammar_state *next = NULL;
    lie_grammar_status rc = lie_grammar_advance(program, state, (uint8_t)text[i], &next);
    lie_grammar_state_release(state);
    if (rc != LIE_GRAMMAR_OK) { assert(!next); return false; }
    state = next;
  }
  bool accepted = lie_grammar_complete(state);
  lie_grammar_state_release(state); return accepted;
}
static void publication(bool refusal) {
  memory m = {0}; lie_schema_compiler_description d;
  fixture f = {.compiler = create(&m, &d), .refuse_bind = refusal};
  assert(lie_lexeme_table_create(NULL, &f.table) == LIE_LEXEME_OK);
  const lie_builder_primitives *p = lie_schema_compiler_primitives(f.compiler);
  lie_schema_container_counts *containers = lie_schema_compiler_containers(f.compiler);
  size_t *enumeration = lie_schema_compiler_enum_values(f.compiler);
  assert(lie_schema_compiler_initialize(f.compiler, &f, whitespace, NULL) == LIE_COMPILER_OK);
  assert(phase(f.compiler) == LIE_COMPILER_READY && f.calls == 1);
  assert(lie_schema_compiler_primitives(f.compiler) == p);
  assert(lie_schema_compiler_containers(f.compiler) == containers);
  assert(lie_schema_compiler_enum_values(f.compiler) == enumeration);
  assert(lie_schema_compiler_initialize(f.compiler, &f, whitespace, NULL) == LIE_COMPILER_PHASE && f.calls == 1);
  containers->properties = 3; containers->characters = 7; *enumeration = 2;
  lie_json_value *root = NULL;
  assert(lie_json_value_create(NULL, &root) == LIE_JSON_VALUE_OK);
  assert(lie_json_store_adopt(lie_schema_compiler_store(f.compiler), root) == LIE_JSON_STORE_OK);
  assert(lie_schema_memo_assign(lie_schema_compiler_memo(f.compiler), root, 19) == LIE_SCHEMA_OK);
  bool hit = false; uint32_t id = 0;
  assert(lie_schema_memo_get(lie_schema_compiler_memo(f.compiler), root, &id, &hit) == LIE_SCHEMA_OK && hit && id == 19);
  assert(lie_lexeme_memo_put(lie_schema_compiler_checks(f.compiler), root,
                           lie_lexeme_table_at(f.table, 0)) == LIE_LEXEME_OK);
  assert(lie_lexeme_memo_get(lie_schema_compiler_checks(f.compiler), root) == lie_lexeme_table_at(f.table, 0));
  lie_schema_compiler_info info; lie_schema_compiler_describe(f.compiler, &info);
  assert(info.memo.entries == 1 && info.store.live_roots == 1 && info.checks.count == 1);
  assert(info.containers.properties == 3 && info.containers.characters == 7 && info.enum_values == 2);
  lie_schema_compile_description cd; lie_schema_compile_description_init(&cd);
  cd.allocator = d.allocator;
  cd.root.reader.access.describe = no_describe; cd.root.reader.access.child = no_child;
  cd.binding_context = &f; cd.lexeme_count = count; cd.bind = bind;
  max_align_t sentinel;
  lie_schema_compilation result = {(void *)&sentinel, (void *)&sentinel, 777};
  lie_schema_compiler_error error = {0};
  lie_schema_compiler_status rc = lie_schema_compiler_publish(f.compiler, &cd,
    NULL, NULL, true, &result, &error);
  if (refusal) {
    assert(rc == LIE_COMPILER_PUBLICATION && error.compile_status == LIE_COMPILE_BINDING);
    assert(error.compile_error.grammar_status == LIE_GRAMMAR_PREDICATE);
    assert(phase(f.compiler) == LIE_COMPILER_FAILED);
    assert(result.program == (void *)&sentinel && result.prompt == (void *)&sentinel && result.root == 777);
  } else {
    assert(rc == LIE_COMPILER_OK && phase(f.compiler) == LIE_COMPILER_PUBLISHED);
  }
  lie_schema_compilation before = result;
  assert(lie_schema_compiler_publish(f.compiler, &cd, NULL, NULL, true,
                                    &result, NULL) == LIE_COMPILER_PHASE);
  assert(result.program == before.program && result.prompt == before.prompt && result.root == before.root);
  assert(f.binds == 1);
  lie_schema_compiler_release(f.compiler); f.compiler = NULL;
  if (!refusal) {
    assert(m.live); /* Independent program/prompt still own their allocations. */
    size_t bytes = 0;
    const char *prompt = lie_schema_prompt_bytes(result.prompt, &bytes);
    assert(bytes == strlen("Respond with a single valid JSON object."));
    assert(!memcmp(prompt, "Respond with a single valid JSON object.", bytes));
    const char *valid[] = {"{}", " {\"a\":[1,null,true,\"hello\"]} ", "{\"s\":\"\\ud83d\\ude00\"}"};
    const char *invalid[] = {"[]", "1", "{", "{\"a\":01}", "{\"s\":\"\\ud800\"}"};
    for (size_t i = 0; i < sizeof(valid) / sizeof(*valid); ++i) assert(accepts(result.program, valid[i]));
    for (size_t i = 0; i < sizeof(invalid) / sizeof(*invalid); ++i) assert(!accepts(result.program, invalid[i]));
    lie_grammar_program_release(result.program); lie_schema_prompt_release(result.prompt);
  }
  lie_lexeme_table_release(f.table);
  assert(!m.live && !m.bytes);
}
static void initialization_refusals(void) {
  for (unsigned mode = 1; mode <= 2; ++mode) {
    memory m = {0}; lie_schema_compiler_description d;
    fixture f = {.compiler = create(&m, &d), .mode = mode};
    lie_schema_compiler_error e = {0};
    const lie_builder_primitives *p = lie_schema_compiler_primitives(f.compiler);
    lie_builder_primitives before = *p;
    assert(lie_schema_compiler_initialize(f.compiler, &f, NULL, NULL) == LIE_COMPILER_INVALID);
    assert(phase(f.compiler) == LIE_COMPILER_NEW && !f.calls);
    lie_schema_compiler_status rc = lie_schema_compiler_initialize(f.compiler, &f, whitespace, &e);
    assert(rc == (mode == 1 ? LIE_COMPILER_CALLBACK : LIE_COMPILER_BUILDER));
    assert(mode == 1 ? e.schema_status == LIE_SCHEMA_RESOURCE : e.builder_status == LIE_BUILDER_INVALID);
    assert(phase(f.compiler) == LIE_COMPILER_FAILED && f.calls == 1);
    assert(!memcmp(&before, p, sizeof(before)));
    assert(lie_schema_compiler_initialize(f.compiler, &f, whitespace, NULL) == LIE_COMPILER_PHASE && f.calls == 1);
    lie_schema_compiler_release(f.compiler); assert(!m.live && !m.bytes);
  }
}
static void allocator_refusals(void) {
  memory baseline = {0}; lie_schema_compiler_description d;
  lie_schema_compiler *c = create(&baseline, &d);
  size_t creations = baseline.calls;
  lie_schema_compiler_release(c); assert(!baseline.live && !baseline.bytes);
  max_align_t sentinel;
  for (size_t fail = 1; fail <= creations; ++fail) {
    memory m = {.fail = fail}; d.allocator = (lie_grammar_allocator){&m, allocate, release};
    c = (void *)&sentinel;
    lie_schema_compiler_error e = {0};
    assert(lie_schema_compiler_create(&d, &c, &e) != LIE_COMPILER_OK);
    assert(c == (void *)&sentinel && !m.live && !m.bytes);
  }
  memory m = {0}; fixture f = {.compiler = create(&m, &d)};
  assert(lie_lexeme_table_create(NULL, &f.table) == LIE_LEXEME_OK);
  size_t start = m.calls;
  assert(lie_schema_compiler_initialize(f.compiler, &f, whitespace, NULL) == LIE_COMPILER_OK);
  size_t bootstrap = m.calls - start;
  lie_schema_compiler_release(f.compiler); lie_lexeme_table_release(f.table);
  assert(!m.live && !m.bytes);
  for (size_t offset = 1; offset <= bootstrap; ++offset) {
    memory fail = {0}; fixture trial = {.compiler = create(&fail, &d)};
    fail.fail = fail.calls + offset;
    assert(lie_lexeme_table_create(NULL, &trial.table) == LIE_LEXEME_OK);
    lie_schema_compiler_error e = {0};
    assert(lie_schema_compiler_initialize(trial.compiler, &trial, whitespace, &e) == LIE_COMPILER_BUILDER);
    assert(e.builder_status == LIE_BUILDER_RESOURCE && phase(trial.compiler) == LIE_COMPILER_FAILED);
    lie_schema_compiler_release(trial.compiler); lie_lexeme_table_release(trial.table);
    assert(!fail.live && !fail.bytes);
  }
}
int main(void) {
  publication(false); publication(true); initialization_refusals(); allocator_refusals();
  puts("C17 compiler lifecycle/refusals: HOST NOT-INFERENCE");
  return 0;
}
