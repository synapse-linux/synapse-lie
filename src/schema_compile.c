/* SPDX-License-Identifier: MIT */
/* Publication order/text follow official Gufo f783fedb; see gufo-NOTICE. */
#include "lie/schema_compile.h"
#include <stdlib.h>
#include <string.h>
static const char object_prompt[] = "Respond with a single valid JSON object.";
static const char schema_prefix[] =
  "Respond with a single JSON object matching this JSON Schema:\n";
struct lie_schema_prompt {
  lie_grammar_allocator allocator;
  char *data;
  size_t bytes, capacity, limit, heap_limit, peak, allocations;
  lie_schema_compile_status status;
};
static void *ordinary_allocate(void *p, size_t n) { (void)p; return malloc(n); }
static void ordinary_release(void *p, void *v) { (void)p; free(v); }
void lie_schema_compile_description_init(lie_schema_compile_description *d) {
  if (!d) return;
  memset(d, 0, sizeof(*d));
  d->abi_version = LIE_SCHEMA_COMPILE_ABI;
  d->struct_bytes = sizeof(*d);
  d->max_schema_bytes = 2u * 1024u * 1024u;
  d->max_owned_prompt_bytes = 8u * 1024u * 1024u;
  lie_schema_root_description_init(&d->root);
}
void lie_schema_prompt_release(lie_schema_prompt *p) {
  if (!p) return;
  const lie_grammar_allocator a = p->allocator;
  if (p->data) a.release(a.context, p->data);
  a.release(a.context, p);
}
const char *lie_schema_prompt_bytes(const lie_schema_prompt *p, size_t *bytes) {
  if (bytes) *bytes = p ? p->bytes : 0;
  return p ? p->data : "";
}
void lie_schema_prompt_describe(const lie_schema_prompt *p, lie_schema_prompt_info *out) {
  if (!out) return;
  *out = p ? (lie_schema_prompt_info){p->bytes, p->capacity,
    sizeof(*p) + p->capacity, p->peak, p->allocations}
    : (lie_schema_prompt_info){0};
}
static bool write_prompt(void *context, const char *data, size_t bytes) {
  lie_schema_prompt *p = context;
  if (p->status != LIE_COMPILE_OK) return false;
  if ((bytes && !data) || bytes > p->limit - p->bytes) {
    p->status = LIE_COMPILE_PROMPT_LIMIT;
    return false;
  }
  const size_t wanted = p->bytes + bytes + 1;
  if (wanted > p->capacity) {
    size_t capacity = p->capacity ? p->capacity : 64;
    const size_t maximum = p->limit + 1;
    if (capacity > maximum) capacity = maximum;
    while (capacity < wanted) {
      if (capacity > maximum / 2) { capacity = maximum; break; }
      capacity *= 2;
    }
    const size_t live = sizeof(*p) + p->capacity;
    if (capacity > p->heap_limit - live) {
      p->status = LIE_COMPILE_PROMPT_LIMIT;
      return false;
    }
    const size_t overlap = live + capacity;
    if (overlap > p->peak) p->peak = overlap;
    char *next = p->allocator.allocate(p->allocator.context, capacity);
    if (!next) { p->status = LIE_COMPILE_RESOURCE; return false; }
    ++p->allocations;
    if (p->bytes) memcpy(next, p->data, p->bytes);
    if (p->data) p->allocator.release(p->allocator.context, p->data);
    p->data = next;
    p->capacity = capacity;
  }
  if (bytes) memcpy(p->data + p->bytes, data, bytes);
  p->bytes += bytes;
  p->data[p->bytes] = '\0';
  return true;
}
lie_schema_compile_status lie_schema_compile(
    const lie_schema_compile_description *d, lie_schema_node schema,
    const lie_json_value *native_schema, bool object_only, lie_grammar_builder *b,
    uint32_t whitespace, lie_schema_compilation *out, lie_schema_compile_error *error) {
  lie_schema_compile_error e = {0};
  if (error) *error = e;
  if (!d || !out || !b || d->abi_version != LIE_SCHEMA_COMPILE_ABI ||
      d->struct_bytes != sizeof(*d) || !d->max_schema_bytes ||
      d->max_schema_bytes > SIZE_MAX - sizeof(schema_prefix) ||
      d->max_owned_prompt_bytes < sizeof(lie_schema_prompt) ||
      (!!d->allocator.allocate != !!d->allocator.release) ||
      !d->lexeme_count || !d->bind || (!object_only && (!schema || !native_schema)))
    return LIE_COMPILE_INVALID;
  uint32_t root = 0;
  e.schema_status = lie_schema_root_rule(&d->root, schema, object_only, b,
                                        whitespace, &root, &e.schema_error);
  if (e.schema_status) {
    if (error) *error = e;
    return LIE_COMPILE_SCHEMA;
  }
  lie_grammar_allocator a = d->allocator;
  if (!a.allocate) a = (lie_grammar_allocator){NULL, ordinary_allocate, ordinary_release};
  lie_schema_prompt *p = a.allocate(a.context, sizeof(*p));
  if (!p) return LIE_COMPILE_RESOURCE;
  *p = (lie_schema_prompt){.allocator = a, .heap_limit = d->max_owned_prompt_bytes,
    .limit = object_only ? sizeof(object_prompt) - 1
                       : d->max_schema_bytes + sizeof(schema_prefix) - 1,
    .peak = sizeof(*p), .allocations = 1};
  lie_schema_compile_status rc = LIE_COMPILE_OK;
  if (!write_prompt(p, object_only ? object_prompt : schema_prefix,
                     object_only ? sizeof(object_prompt) - 1 : sizeof(schema_prefix) - 1)) {
    rc = p->status; goto done;
  }
  if (!object_only) {
    const lie_json_value_sink sink = {p, write_prompt};
    e.json_status = lie_json_value_dump(native_schema, &sink);
    if (e.json_status) {
      rc = p->status ? p->status : LIE_COMPILE_JSON;
      goto done;
    }
  }
  lie_grammar_description program;
  e.builder_status = lie_builder_finish(b, root, d->lexeme_count(d->binding_context), &program);
  if (e.builder_status) { rc = LIE_COMPILE_BUILDER; goto done; }
  e.grammar_status = d->bind(d->binding_context, &program.predicates);
  if (e.grammar_status) { rc = LIE_COMPILE_BINDING; goto done; }
  program.allocator = a;
  lie_grammar_program *compiled = NULL;
  e.grammar_status = lie_grammar_program_create(&program, &compiled);
  if (e.grammar_status) { rc = LIE_COMPILE_PROGRAM; goto done; }
  lie_grammar_state *initial = NULL;
  e.grammar_status = lie_grammar_start(compiled, &initial);
  if (e.grammar_status) {
    lie_grammar_program_release(compiled);
    rc = LIE_COMPILE_PROGRAM; goto done;
  }
  lie_grammar_state_release(initial);
  *out = (lie_schema_compilation){compiled, p, root};
  if (error) *error = e;
  return LIE_COMPILE_OK;
done:
  if (error) *error = e;
  lie_schema_prompt_release(p);
  return rc;
}
