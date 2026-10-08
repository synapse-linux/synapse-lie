/* SPDX-License-Identifier: MIT */
/* Owned compilation lifecycle. JSON primitive/publication algorithms retain
 * their separately recorded pinned Gufo provenance and C17 implementations. */
#include "lie/schema_compiler.h"
#include <stdlib.h>
#include <string.h>
struct lie_schema_compiler {
  lie_grammar_allocator allocator;
  lie_grammar_builder *builder;
  lie_schema_memo *memo;
  lie_json_store *store;
  lie_lexeme_memo *checks;
  lie_builder_primitives primitives;
  lie_schema_container_counts containers;
  size_t enum_values;
  lie_schema_compiler_phase phase;
};
static void *allocate(void *p, size_t bytes) { (void)p; return malloc(bytes); }
static void release(void *p, void *value) { (void)p; free(value); }
void lie_schema_compiler_description_init(lie_schema_compiler_description *d) {
  if (!d) return;
  memset(d, 0, sizeof(*d));
  d->abi_version = LIE_SCHEMA_COMPILER_ABI;
  d->struct_bytes = sizeof(*d);
  lie_builder_description_init(&d->builder);
  lie_schema_memo_description_init(&d->memo);
  lie_json_store_description_init(&d->store);
  lie_lexeme_table_description_init(&d->checks);
}
void lie_schema_compiler_release(lie_schema_compiler *c) {
  if (!c) return;
  lie_grammar_allocator a = c->allocator;
  /* Memos borrow derived identities; destroy them before releasing the roots. */
  lie_lexeme_memo_release(c->checks);
  lie_schema_memo_release(c->memo);
  lie_builder_release(c->builder);
  lie_json_store_release(c->store);
  a.release(a.context, c);
}
static void inherit(lie_grammar_allocator *child, lie_grammar_allocator parent) {
  if (!child->allocate && !child->release) *child = parent;
}
lie_schema_compiler_status lie_schema_compiler_create(
    const lie_schema_compiler_description *d, lie_schema_compiler **out,
    lie_schema_compiler_error *error) {
  lie_schema_compiler_description defaults;
  if (!d) { lie_schema_compiler_description_init(&defaults); d = &defaults; }
  lie_schema_compiler_error e = {0};
  if (error) *error = e;
  if (!out || d->abi_version != LIE_SCHEMA_COMPILER_ABI ||
      d->struct_bytes != sizeof(*d) ||
      (!!d->allocator.allocate != !!d->allocator.release)) return LIE_COMPILER_INVALID;
  lie_grammar_allocator a = d->allocator;
  if (!a.allocate) a = (lie_grammar_allocator){NULL, allocate, release};
  lie_schema_compiler *c = a.allocate(a.context, sizeof(*c));
  if (!c) return LIE_COMPILER_RESOURCE;
  *c = (lie_schema_compiler){.allocator = a, .phase = LIE_COMPILER_NEW};
  lie_schema_memo_description memo = d->memo;
  lie_json_store_description store = d->store;
  lie_lexeme_table_description checks = d->checks;
  lie_builder_description builder = d->builder;
  inherit(&memo.allocator, a); inherit(&store.allocator, a);
  inherit(&checks.allocator, a); inherit(&builder.allocator, a);
  lie_schema_compiler_status status;
  e.schema_status = lie_schema_memo_create(&memo, &c->memo);
  if (e.schema_status) { status = LIE_COMPILER_MEMO; goto refused; }
  e.store_status = lie_json_store_create(&store, &c->store);
  if (e.store_status) { status = LIE_COMPILER_STORE; goto refused; }
  e.lexeme_status = lie_lexeme_memo_create(&checks, &c->checks);
  if (e.lexeme_status) { status = LIE_COMPILER_CHECKS; goto refused; }
  e.builder_status = lie_builder_create(&builder, &c->builder);
  if (e.builder_status) { status = LIE_COMPILER_BUILDER; goto refused; }
  if (error) *error = e;
  *out = c;
  return LIE_COMPILER_OK;
refused:
  if (error) *error = e;
  lie_schema_compiler_release(c);
  return status;
}
lie_schema_compiler_status lie_schema_compiler_initialize(lie_schema_compiler *c,
    void *context, lie_schema_status (*whitespace)(void *, uint32_t *),
    lie_schema_compiler_error *error) {
  lie_schema_compiler_error e = {0};
  if (error) *error = e;
  if (!c || !whitespace) return LIE_COMPILER_INVALID;
  if (c->phase != LIE_COMPILER_NEW) return LIE_COMPILER_PHASE;
  c->phase = LIE_COMPILER_INITIALIZING;
  uint32_t symbol = 0;
  e.schema_status = whitespace(context, &symbol);
  if (e.schema_status) {
    c->phase = LIE_COMPILER_FAILED;
    if (error) *error = e;
    return LIE_COMPILER_CALLBACK;
  }
  lie_builder_primitives primitives;
  e.builder_status = lie_builder_json(c->builder, symbol, &primitives);
  if (error) *error = e;
  if (e.builder_status) {
    c->phase = LIE_COMPILER_FAILED;
    return LIE_COMPILER_BUILDER;
  }
  c->primitives = primitives;
  c->phase = LIE_COMPILER_READY;
  return LIE_COMPILER_OK;
}
lie_schema_compiler_status lie_schema_compiler_publish(lie_schema_compiler *c,
    const lie_schema_compile_description *d, lie_schema_node schema,
    const lie_json_value *native, bool object_only, lie_schema_compilation *out,
    lie_schema_compiler_error *error) {
  lie_schema_compiler_error e = {0};
  if (error) *error = e;
  if (!c || !d || !out) return LIE_COMPILER_INVALID;
  if (c->phase != LIE_COMPILER_READY) return LIE_COMPILER_PHASE;
  c->phase = LIE_COMPILER_PUBLISHING;
  e.compile_status = lie_schema_compile(d, schema, native, object_only,
    c->builder, c->primitives.whitespace, out, &e.compile_error);
  if (error) *error = e;
  c->phase = e.compile_status ? LIE_COMPILER_FAILED : LIE_COMPILER_PUBLISHED;
  return e.compile_status ? LIE_COMPILER_PUBLICATION : LIE_COMPILER_OK;
}
lie_grammar_builder *lie_schema_compiler_builder(lie_schema_compiler *c) { return c ? c->builder : NULL; }
lie_schema_memo *lie_schema_compiler_memo(lie_schema_compiler *c) { return c ? c->memo : NULL; }
lie_json_store *lie_schema_compiler_store(lie_schema_compiler *c) { return c ? c->store : NULL; }
lie_lexeme_memo *lie_schema_compiler_checks(lie_schema_compiler *c) { return c ? c->checks : NULL; }
const lie_builder_primitives *lie_schema_compiler_primitives(const lie_schema_compiler *c) { return c ? &c->primitives : NULL; }
lie_schema_container_counts *lie_schema_compiler_containers(lie_schema_compiler *c) { return c ? &c->containers : NULL; }
size_t *lie_schema_compiler_enum_values(lie_schema_compiler *c) { return c ? &c->enum_values : NULL; }
void lie_schema_compiler_describe(const lie_schema_compiler *c, lie_schema_compiler_info *out) {
  if (!out) return;
  *out = (lie_schema_compiler_info){0};
  if (!c) return;
  out->phase = c->phase;
  out->context_bytes = sizeof(*c);
  out->enum_values = c->enum_values;
  out->containers = c->containers;
  (void)lie_schema_memo_inspect(c->memo, &out->memo);
  lie_json_store_describe(c->store, &out->store);
  (void)lie_lexeme_memo_describe(c->checks, &out->checks);
}
