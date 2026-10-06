/* SPDX-License-Identifier: MIT */
/* Native orchestration of independently owned C17 schema/grammar modules.
 * Policy/order follows pinned MIT Gufo; no provider types or model forward. */
#include "lie/schema_frontend.h"
#include "lie/schema_body.h"
#include "lie/schema_number.h"
#include "lie/schema_integer.h"
#include "schema_internal.h"
#include <stdlib.h>
#include <string.h>
typedef struct diagnostic { struct diagnostic *next; size_t bytes; char text[]; } diagnostic;
struct lie_schema_frontend {
  lie_schema_frontend_description d;
  lie_schema_frontend_phase phase;
  lie_schema_compiler *compiler;
  lie_lexeme_table *lexemes;
  lie_regex_program *unrestricted;
  const lie_json_value *root;
  bool strict;
  diagnostic *diagnostics;
  size_t error_bytes;
  lie_schema_frontend_error error;
};
typedef struct { lie_schema_frontend *f; lie_schema_arena *staging, *values; } body;
static void *allocate(void *p, size_t n) { (void)p; return malloc(n); }
static void release(void *p, void *v) { (void)p; free(v); }
static void inherit(lie_grammar_allocator *a, lie_grammar_allocator parent) {
  if (!a->allocate && !a->release) *a = parent;
}
void lie_schema_frontend_description_init(lie_schema_frontend_description *d) {
  if (!d) return;
  memset(d, 0, sizeof(*d)); d->abi_version = LIE_SCHEMA_FRONTEND_ABI;
  d->struct_bytes = sizeof(*d); d->max_error_bytes = 2u * 1024u * 1024u;
  lie_schema_compiler_description_init(&d->compiler);
  lie_schema_arena_description_init(&d->arena);
  lie_schema_string_description_init(&d->strings);
  lie_lexeme_table_description_init(&d->lexemes);
  lie_schema_compile_description_init(&d->publication);
}
static lie_schema_transform_description reader(lie_schema_frontend *f) {
  lie_schema_transform_description d = f->d.arena.transform;
  d.access = (lie_schema_access){.describe = lie_schema_json_describe, .child = lie_schema_json_child};
  return d;
}
static lie_schema_status remember(lie_schema_frontend *f, lie_schema_status rc, lie_schema_error e) {
  if (!rc) return rc;
  if (f->error.schema_status != rc || f->error.schema_error.message != e.message ||
      f->error.schema_error.detail.data != e.detail.data || f->error.schema_error.detail.size != e.detail.size ||
      f->error.schema_error.suffix != e.suffix)
    f->error.origin = LIE_FRONTEND_ERROR_SCHEMA;
  if (e.detail.size) {
    for (diagnostic *kept = f->diagnostics; kept; kept = kept->next)
      if (e.detail.data == kept->text && e.detail.size <= kept->bytes - sizeof(*kept)) goto retained;
    if (!e.detail.data || e.detail.size > SIZE_MAX - sizeof(diagnostic) ||
        sizeof(diagnostic) + e.detail.size > f->d.max_error_bytes - f->error_bytes)
      goto resource;
    const size_t bytes = sizeof(diagnostic) + e.detail.size;
    diagnostic *copy = f->d.allocator.allocate(f->d.allocator.context, bytes);
    if (!copy) goto resource;
    *copy = (diagnostic){f->diagnostics, bytes};
    memcpy(copy->text, e.detail.data, e.detail.size); f->diagnostics = copy;
    f->error_bytes += bytes; e.detail.data = copy->text;
  }
retained:
  f->error.schema_status = rc; f->error.schema_error = e; return rc;
resource:
  f->error.origin = LIE_FRONTEND_ERROR_SCHEMA;
  f->error.schema_status = LIE_SCHEMA_RESOURCE;
  f->error.schema_error = (lie_schema_error){.message = "schema diagnostic allocation failed"};
  return LIE_SCHEMA_RESOURCE;
}
static lie_schema_status predicate_status(lie_schema_frontend *f, lie_lexeme_status rc) {
  if (!rc) return LIE_SCHEMA_OK;
  const lie_schema_status status = rc == LIE_LEXEME_RESOURCE ? LIE_SCHEMA_RESOURCE : LIE_SCHEMA_CALLBACK;
  f->error.origin = LIE_FRONTEND_ERROR_LEXEME;
  f->error.lexeme_status = rc; f->error.schema_status = status;
  f->error.schema_error = (lie_schema_error){0}; return status;
}
static lie_schema_status register_predicate(lie_schema_frontend *f,
    lie_grammar_lexeme *p, uint32_t *out) {
  const size_t index = lie_lexeme_table_size(f->lexemes);
  lie_schema_status rc = index >= LIE_GRAMMAR_LEXEME
    ? predicate_status(f, LIE_LEXEME_LIMIT)
    : predicate_status(f, lie_lexeme_table_push(f->lexemes, p));
  if (!rc) *out = LIE_GRAMMAR_LEXEME | (uint32_t)index;
  lie_lexeme_release(p); return rc;
}
static lie_schema_status whitespace(void *p, uint32_t *out) {
  lie_schema_frontend *f = p; lie_grammar_lexeme *lexeme = NULL;
  lie_schema_status rc = predicate_status(f, lie_lexeme_whitespace_create(&f->d.strings.lexeme, &lexeme));
  return rc ? rc : register_predicate(f, lexeme, out);
}
static lie_schema_status string_predicate(lie_schema_frontend *f, lie_schema_node schema,
    lie_grammar_lexeme **out) {
  lie_schema_string_description d = f->d.strings; d.transform.access = reader(f).access;
  lie_schema_string_plan plan; lie_schema_string_error e = {0};
  lie_schema_status rc = lie_schema_string_prepare(&d, schema, &plan, &e);
  const lie_regex_program *unrestricted = f->d.unrestricted ? f->d.unrestricted : f->unrestricted;
  if (!rc && !plan.has_pattern && !plan.format_bytes && !unrestricted) {
    rc = lie_schema_string_unrestricted(&d, &f->unrestricted, &e);
    unrestricted = f->unrestricted;
  }
  if (!rc) rc = lie_schema_string_compile(&d, &plan, unrestricted, out, &e);
  if (rc) {
    f->error.origin = LIE_FRONTEND_ERROR_STRING;
    f->error.string_error = e; f->error.schema_status = rc; f->error.schema_error = e.schema_error;
    rc = remember(f, rc, e.schema_error);
    f->error.string_error.schema_error = f->error.schema_error;
  }
  return rc;
}
static lie_schema_number_description numbers(lie_schema_frontend *f) {
  lie_schema_number_description d; lie_schema_number_description_init(&d);
  d.transform = reader(f); d.number_work = f->d.number_work; return d;
}
static lie_schema_status number_predicate(lie_schema_frontend *f, lie_schema_node schema,
    bool integer, lie_grammar_lexeme **out) {
  const lie_schema_number_description d = numbers(f);
  lie_number_policy *policy = NULL; lie_schema_error e = {0};
  lie_schema_status rc = lie_schema_number_create(&d, schema, integer, &policy, &e);
  if (rc) return remember(f, rc, e);
  rc = predicate_status(f, lie_lexeme_number_create(&f->d.strings.lexeme, policy, out));
  lie_number_release(policy); return rc;
}
typedef struct {
  const lie_grammar_lexeme *predicate;
  uint8_t state[LIE_STRING_STATE_BYTES];
  size_t bytes;
  lie_lexeme_status status;
  bool prefix, complete, rejected;
} string_sink;
static bool check_bytes(void *p, const char *text, size_t bytes) {
  string_sink *s = p;
  if (s->status || s->rejected) return true;
  for (size_t i = 0; i < bytes; ++i) {
    if (!s->prefix) { s->complete = false; s->rejected = true; return true; }
    lie_lexeme_match match = {0};
    s->status = lie_lexeme_advance(s->predicate, s->state, s->bytes, (uint8_t)text[i],
      s->state, sizeof(s->state), &s->bytes, &match);
    if (s->status) return true;
    s->prefix = match.prefix; s->complete = match.complete;
    if (!s->prefix && !s->complete) { s->rejected = true; return true; }
  }
  return true;
}
static lie_schema_status accept(void *p, lie_schema_node schema, lie_schema_node value, bool *out) {
  lie_schema_frontend *f = p;
  const lie_grammar_lexeme *predicate = lie_lexeme_memo_get(lie_schema_compiler_checks(f->compiler), schema);
  const bool string = lie_json_value_type(value) == LIE_JSON_VALUE_STRING;
  if (!predicate) {
    lie_grammar_lexeme *created = NULL;
    lie_schema_status rc = string ? string_predicate(f, schema, &created) : number_predicate(f, schema, false, &created);
    if (rc) return rc;
    rc = predicate_status(f, lie_lexeme_memo_put(lie_schema_compiler_checks(f->compiler), schema, created));
    lie_lexeme_release(created); if (rc) return rc;
    predicate = lie_lexeme_memo_get(lie_schema_compiler_checks(f->compiler), schema);
  }
  /* Numeric acceptance keeps the existing shortest-binary64 value domain.
   * String acceptance uses decoded raw bytes through the same JSON quoting. */
  if (lie_lexeme_number_policy(predicate)) {
    const lie_schema_number_description d = numbers(f); lie_schema_error e = {0};
    lie_schema_status rc = lie_schema_number_accept(&d, lie_lexeme_number_policy(predicate), value, out, &e);
    return rc ? remember(f, rc, e) : rc;
  }
  string_sink state = {.predicate = predicate, .prefix = true};
  const lie_json_value_sink sink = {&state, check_bytes};
  const lie_json_value_status serialized = lie_json_value_dump(value, &sink);
  /* Complete serialization even after a semantic/predicate refusal, preserving
   * Value::dump-before-Check diagnostic precedence and output-work admission. */
  if (serialized) {
    const lie_schema_status rc = serialized == LIE_JSON_VALUE_RESOURCE ? LIE_SCHEMA_RESOURCE : LIE_SCHEMA_CALLBACK;
    f->error = (lie_schema_frontend_error){.origin = LIE_FRONTEND_ERROR_ARENA,
      .schema_status = rc, .arena_error = {.value_status = serialized}};
    return rc;
  }
  if (state.status) return predicate_status(f, state.status);
  *out = !state.rejected && state.complete; return LIE_SCHEMA_OK;
}
static lie_schema_status number_literal(void *p, lie_schema_node value, lie_grammar_builder *b, uint32_t *out) {
  lie_schema_frontend *f = p; const lie_schema_number_description d = numbers(f);
  lie_schema_error e = {0}; lie_schema_status rc = lie_schema_number_literal(&d, value, b, out, &e);
  return rc ? remember(f, rc, e) : rc;
}
static lie_schema_status append_member(void *p, lie_schema_node n, lie_schema_bytes key, lie_schema_node value) {
  return lie_schema_arena_append_member(p, (lie_json_value *)n, key, value);
}
static lie_schema_values_description values(lie_schema_frontend *f, lie_schema_arena *arena) {
  lie_schema_values_description d; lie_schema_values_description_init(&d);
  d.transform = arena ? lie_schema_arena_transform(arena) : reader(f);
  if (arena) d.transform.access.put = append_member;
  d.leaf_context = f; d.accept = accept; d.number_literal = number_literal; return d;
}
static lie_schema_status visit(void *, lie_schema_node, size_t, uint32_t *);
static lie_schema_status keep(void *p, lie_schema_node n, lie_schema_node *out) {
  body *b = p; lie_json_value *copy = NULL;
  lie_json_value_status v = lie_json_value_clone(n, &b->f->d.arena.values, &copy);
  if (v) {
    const lie_schema_status rc = v == LIE_JSON_VALUE_RESOURCE ? LIE_SCHEMA_RESOURCE : LIE_SCHEMA_CALLBACK;
    b->f->error = (lie_schema_frontend_error){.origin = LIE_FRONTEND_ERROR_ARENA,
      .schema_status = rc, .arena_error = {.value_status = v}};
    return rc;
  }
  lie_json_store_status s = lie_json_store_adopt(lie_schema_compiler_store(b->f->compiler), copy);
  if (s) {
    lie_json_value_release(copy);
    const lie_schema_status rc = s == LIE_JSON_STORE_RESOURCE ? LIE_SCHEMA_RESOURCE : LIE_SCHEMA_CALLBACK;
    b->f->error = (lie_schema_frontend_error){.origin = LIE_FRONTEND_ERROR_ARENA,
      .schema_status = rc, .arena_error = {.store_status = s}};
    return rc;
  }
  *out = copy; return LIE_SCHEMA_OK;
}
static lie_schema_status child_visit(void *p, lie_schema_node n, size_t depth, uint32_t *out) {
  return visit(((body *)p)->f, n, depth, out);
}
static lie_schema_status normalize(void *p, lie_schema_node schema, lie_schema_node value, lie_schema_normalized *out) {
  body *b = p; const lie_schema_values_description d = values(b->f, b->values);
  lie_schema_error e = {0};
  lie_schema_status rc = lie_schema_normalize(&d, b->f->root, schema, value, 0, out, &e);
  return rc ? remember(b->f, rc, e.message ? e : b->f->error.schema_error) : rc;
}
static lie_schema_status rule(void *p, lie_schema_node n, size_t depth,
    lie_schema_route route, lie_schema_bytes name, uint32_t *out) {
  body *b = p; lie_schema_frontend *f = b->f;
  const lie_schema_values_description d = values(f, b->values);
  lie_grammar_builder *builder = lie_schema_compiler_builder(f->compiler);
  const lie_builder_primitives *primitives = lie_schema_compiler_primitives(f->compiler);
  lie_schema_error e = {0}; lie_schema_status rc;
  lie_grammar_lexeme *predicate = NULL;
  switch (route) {
  case LIE_SCHEMA_ROUTE_OBJECT:
    rc = lie_schema_object(&d, n, depth, f->strict, builder, primitives->whitespace,
      (lie_schema_visit){b, child_visit}, lie_schema_compiler_containers(f->compiler), out, &e); break;
  case LIE_SCHEMA_ROUTE_ARRAY:
    rc = lie_schema_array(&d, n, depth, builder, primitives->whitespace,
      (lie_schema_visit){b, child_visit}, out, &e); break;
  case LIE_SCHEMA_ROUTE_INTEGER:
    rc = lie_schema_integer_compile(&d.transform, n, builder, primitives->integer, out, &e); break;
  case LIE_SCHEMA_ROUTE_INTEGER_LEXEME: case LIE_SCHEMA_ROUTE_NUMBER_LEXEME:
    rc = number_predicate(f, n, route == LIE_SCHEMA_ROUTE_INTEGER_LEXEME, &predicate);
    return rc ? rc : register_predicate(f, predicate, out);
  case LIE_SCHEMA_ROUTE_STRING_LEXEME:
    rc = string_predicate(f, n, &predicate); return rc ? rc : register_predicate(f, predicate, out);
  case LIE_SCHEMA_ROUTE_PRIMITIVE: {
    const char *names[] = {"string", "integer", "number", "boolean", "null"};
    const uint32_t ids[] = {primitives->string, primitives->integer, primitives->number, primitives->boolean, primitives->null_value};
    for (size_t i = 0; i < 5; ++i)
      if (name.size == strlen(names[i]) && !memcmp(name.data, names[i], name.size)) { *out = ids[i]; return LIE_SCHEMA_OK; }
    return remember(f, LIE_SCHEMA_INVALID, (lie_schema_error){.message = "unsupported or missing type"});
  }
  default: return LIE_SCHEMA_INVALID;
  }
  return rc ? remember(f, rc, e.message ? e : f->error.schema_error) : rc;
}
static lie_schema_status compile_body(void *p, lie_schema_node n, size_t depth, uint32_t *out, lie_schema_error *error) {
  lie_schema_frontend *f = p; body b = {.f = f};
  lie_schema_status rc = lie_schema_arena_create(&f->d.arena, &b.staging);
  if (!rc) rc = lie_schema_arena_create(&f->d.arena, &b.values);
  lie_schema_error e = {0};
  if (rc) f->error = (lie_schema_frontend_error){.schema_status = rc,
    .schema_error = {.message = "schema arena creation failed"}};
  if (!rc) {
    lie_schema_body_description d; lie_schema_body_description_init(&d);
    d.transform = lie_schema_arena_transform(b.staging); d.values = values(f, b.values);
    d.append_member = append_member;
    d.compile = (lie_schema_compile_access){&b, child_visit, keep, normalize};
    d.rules = (lie_schema_rule_access){&b, rule};
    rc = lie_schema_compile_body(&d, f->root, n, depth, lie_schema_compiler_builder(f->compiler),
      lie_schema_compiler_primitives(f->compiler)->whitespace, lie_schema_compiler_containers(f->compiler),
      lie_schema_compiler_enum_values(f->compiler), out, &e);
    if (rc) {
      lie_schema_arena_error a; lie_schema_arena_error_describe(b.staging, &a);
      if (!a.value_status && !a.store_status) lie_schema_arena_error_describe(b.values, &a);
      if (a.value_status || a.store_status) {
        a.schema_error = (lie_schema_error){0};
        f->error.origin = LIE_FRONTEND_ERROR_ARENA; f->error.arena_error = a;
        f->error.schema_status = rc; f->error.schema_error = e;
      }
    }
  }
  if (rc) rc = remember(f, rc, e.message ? e : f->error.schema_error);
  if (error) *error = rc ? f->error.schema_error : (lie_schema_error){0};
  lie_schema_arena_release(b.values); lie_schema_arena_release(b.staging); return rc;
}
static lie_schema_status visit(void *p, lie_schema_node n, size_t depth, uint32_t *out) {
  lie_schema_frontend *f = p; lie_schema_body_access access;
  lie_schema_body_access_init(&access); access.context = f; access.body = compile_body;
  lie_schema_error e = {0};
  lie_schema_status rc = lie_schema_visit_rule(lie_schema_compiler_memo(f->compiler),
    lie_schema_compiler_builder(f->compiler), n, depth, access, out, &e);
  return rc ? remember(f, rc, e) : rc;
}
static lie_schema_status root_visit(void *p, lie_schema_node n, size_t depth, uint32_t *out, lie_schema_error *e) {
  lie_schema_status rc = visit(p, n, depth, out);
  if (e) *e = rc ? ((lie_schema_frontend *)p)->error.schema_error : (lie_schema_error){0};
  return rc;
}
static size_t count(void *p) { return lie_lexeme_table_size(((lie_schema_frontend *)p)->lexemes); }
static lie_grammar_status bind(void *p, lie_grammar_predicates *out) {
  lie_schema_frontend *f = p;
  lie_lexeme_status rc = lie_lexeme_table_seal(f->lexemes);
  if (rc) { (void)predicate_status(f, rc); return LIE_GRAMMAR_PREDICATE; }
  *out = lie_lexeme_table_predicates(f->lexemes); return LIE_GRAMMAR_OK;
}
void lie_schema_frontend_release(lie_schema_frontend *f) {
  if (!f) return;
  lie_schema_compiler_release(f->compiler); lie_lexeme_table_release(f->lexemes);
  lie_regex_release(f->unrestricted);
  while (f->diagnostics) {
    diagnostic *next = f->diagnostics->next;
    f->d.allocator.release(f->d.allocator.context, f->diagnostics); f->diagnostics = next;
  }
  f->d.allocator.release(f->d.allocator.context, f);
}
lie_schema_frontend_status lie_schema_frontend_create(const lie_schema_frontend_description *input,
    lie_schema_frontend **out, lie_schema_frontend_error *error) {
  lie_schema_frontend_description d; lie_schema_frontend_description_init(&d);
  if (input) d = *input;
  if (error) *error = (lie_schema_frontend_error){0};
  if (!out || d.abi_version != LIE_SCHEMA_FRONTEND_ABI || d.struct_bytes != sizeof(d) ||
      !d.max_error_bytes || (!!d.allocator.allocate != !!d.allocator.release)) return LIE_FRONTEND_INVALID;
  if (!d.allocator.allocate) d.allocator = (lie_grammar_allocator){NULL, allocate, release};
  inherit(&d.compiler.allocator, d.allocator); inherit(&d.arena.allocator, d.allocator);
  inherit(&d.arena.values.allocator, d.arena.allocator); inherit(&d.arena.transform.allocator, d.arena.allocator);
  inherit(&d.lexemes.allocator, d.allocator); inherit(&d.publication.allocator, d.allocator);
  inherit(&d.strings.lexeme.allocator, d.allocator);
  inherit(&d.strings.transform.allocator, d.allocator);
  lie_schema_frontend *f = d.allocator.allocate(d.allocator.context, sizeof(*f));
  if (!f) return LIE_FRONTEND_RESOURCE;
  *f = (lie_schema_frontend){.d = d, .phase = LIE_FRONTEND_NEW};
  lie_schema_frontend_status rc = LIE_FRONTEND_COMPILER;
  f->error.compiler_status = lie_schema_compiler_create(&d.compiler, &f->compiler, &f->error.compiler_error);
  if (f->error.compiler_status) goto refused;
  f->error.lexeme_status = lie_lexeme_table_create(&d.lexemes, &f->lexemes);
  if (f->error.lexeme_status) { rc = LIE_FRONTEND_LEXEME; goto refused; }
  f->error.compiler_status = lie_schema_compiler_initialize(f->compiler, f, whitespace, &f->error.compiler_error);
  if (f->error.compiler_status) goto refused;
  *out = f; return LIE_FRONTEND_OK;
refused:
  if (error) *error = f->error;
  lie_schema_frontend_release(f); return rc;
}
lie_schema_frontend_status lie_schema_frontend_compile(lie_schema_frontend *f,
    const lie_json_value *schema, bool strict, bool object_only,
    lie_schema_frontend_output *out, lie_schema_frontend_error *error) {
  if (error) *error = (lie_schema_frontend_error){0};
  if (!f || !out || (!object_only && !schema)) return LIE_FRONTEND_INVALID;
  if (f->phase != LIE_FRONTEND_NEW) return LIE_FRONTEND_PHASE;
  f->phase = LIE_FRONTEND_COMPILING; f->root = schema; f->strict = strict;
  lie_schema_compile_description d = f->d.publication;
  d.root.reader.access = reader(f).access; inherit(&d.root.reader.allocator, f->d.allocator);
  d.root.visit.context = f; d.root.visit.body = root_visit;
  d.binding_context = f; d.lexeme_count = count; d.bind = bind;
  lie_schema_compilation compiled = {0}; lie_schema_compiler_error e = {0};
  lie_schema_compiler_status rc = lie_schema_compiler_publish(f->compiler, &d, schema, schema, object_only, &compiled, &e);
  if (rc) {
    f->phase = LIE_FRONTEND_FAILED;
    if (e.compile_error.schema_status)
      (void)remember(f, e.compile_error.schema_status, e.compile_error.schema_error);
    f->error.compiler_status = rc; f->error.compiler_error = e;
    f->error.compiler_error.compile_error.schema_error = f->error.schema_error;
    if (e.compile_error.schema_status)
      f->error.compiler_error.compile_error.schema_status = f->error.schema_status;
    if (error) *error = f->error;
    return rc == LIE_COMPILER_PUBLICATION ? LIE_FRONTEND_PUBLICATION : LIE_FRONTEND_COMPILER;
  }
  *out = (lie_schema_frontend_output){compiled, f->lexemes}; f->lexemes = NULL;
  f->phase = LIE_FRONTEND_PUBLISHED;
  if (error) *error = (lie_schema_frontend_error){0};
  return LIE_FRONTEND_OK;
}
void lie_schema_frontend_describe(const lie_schema_frontend *f, lie_schema_frontend_info *out) {
  if (!out) return;
  *out = (lie_schema_frontend_info){0}; if (!f) return;
  out->phase = f->phase; out->context_bytes = sizeof(*f); out->retained_error_bytes = f->error_bytes;
  lie_schema_compiler_describe(f->compiler, &out->compiler);
  (void)lie_lexeme_table_describe(f->lexemes, &out->lexemes);
}
void lie_schema_frontend_output_release(lie_schema_frontend_output *out) {
  if (!out) return;
  lie_grammar_program_release(out->compilation.program);
  lie_schema_prompt_release(out->compilation.prompt); lie_lexeme_table_release(out->lexemes);
  *out = (lie_schema_frontend_output){0};
}
