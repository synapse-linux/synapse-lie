/* SPDX-License-Identifier: MIT */
/* Complete native frontend fixtures prepared for final qualification.
 * HOST NOT-INFERENCE: independent language, ownership and refusal witnesses. */
#include "lie/schema_frontend.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef union { max_align_t alignment; size_t bytes; } header;
typedef struct { size_t calls, fail, live, bytes; } memory;
static void *allocate(void *p, size_t bytes) {
  memory *m = p; if (++m->calls == m->fail) return NULL;
  assert(bytes <= SIZE_MAX - sizeof(header));
  header *h = malloc(sizeof(*h) + bytes); assert(h);
  h->bytes = bytes; ++m->live; m->bytes += bytes; return h + 1;
}
static void release(void *p, void *value) {
  memory *m = p; header *h = (header *)value - 1;
  assert(m->live && m->bytes >= h->bytes);
  --m->live; m->bytes -= h->bytes; free(h);
}
static lie_json_value *parse(const char *text) {
  lie_json_value *out = NULL;
  assert(lie_json_value_parse(text, strlen(text), NULL, NULL, &out, NULL, NULL) == LIE_JSON_VALUE_OK);
  return out;
}
static bool accepts(const lie_grammar_program *program, const char *text) {
  lie_grammar_state *state = NULL;
  assert(lie_grammar_start(program, &state) == LIE_GRAMMAR_OK);
  for (size_t i = 0; i < strlen(text); ++i) {
    lie_grammar_state *next = NULL;
    assert(lie_grammar_advance(program, state, (uint8_t)text[i], &next) == LIE_GRAMMAR_OK);
    lie_grammar_state_release(state); state = next;
  }
  bool complete = lie_grammar_complete(state); lie_grammar_state_release(state); return complete;
}
static lie_schema_frontend_output compile(const char *text, bool strict) {
  lie_json_value *tree = parse(text); lie_schema_frontend *f = NULL;
  lie_schema_frontend_error e = {0}; lie_schema_frontend_output out = {0};
  assert(lie_schema_frontend_create(NULL, &f, &e) == LIE_FRONTEND_OK);
  assert(lie_schema_frontend_compile(f, tree, strict, false, &out, &e) == LIE_FRONTEND_OK);
  lie_schema_frontend_info info; lie_schema_frontend_describe(f, &info);
  assert(info.phase == LIE_FRONTEND_PUBLISHED && info.compiler.phase == LIE_COMPILER_PUBLISHED);
  lie_schema_frontend_release(f); lie_json_value_release(tree); return out;
}
static void language(void) {
  lie_schema_frontend_output out = compile(
    "{\"type\":\"object\",\"additionalProperties\":false,\"properties\":{"
    "\"name\":{\"type\":\"string\",\"pattern\":\"^[ab]+$\",\"maxLength\":2},"
    "\"value\":{\"type\":\"integer\",\"minimum\":-2,\"maximum\":2},"
    "\"items\":{\"type\":\"array\",\"items\":{\"type\":\"boolean\"},\"minItems\":1,\"maxItems\":2}},"
    "\"required\":[\"name\",\"value\",\"items\"]}", true);
  assert(accepts(out.compilation.program, "{\"name\":\"ab\",\"value\":-2,\"items\":[true,false]}"));
  assert(accepts(out.compilation.program, " { \"name\":\"a\", \"value\":2, \"items\":[false] } "));
  const char *rejected[] = {
    "{\"name\":\"c\",\"value\":0,\"items\":[true]}",
    "{\"name\":\"aba\",\"value\":0,\"items\":[true]}",
    "{\"name\":\"a\",\"value\":3,\"items\":[true]}",
    "{\"name\":\"a\",\"value\":1.5,\"items\":[true]}",
    "{\"name\":\"a\",\"value\":0,\"items\":[]}",
    "{\"name\":\"a\",\"value\":0,\"items\":[true,false,true]}",
    "{\"value\":0,\"name\":\"a\",\"items\":[true]}",
    "{\"name\":\"a\",\"items\":[true]}"
  };
  for (size_t i = 0; i < sizeof(rejected) / sizeof(*rejected); ++i)
    assert(!accepts(out.compilation.program, rejected[i]));
  size_t bytes = 0; const char *prompt = lie_schema_prompt_bytes(out.compilation.prompt, &bytes);
  assert(bytes > 58 && strstr(prompt, "matching this JSON Schema:") && strstr(prompt, "\"name\""));
  lie_schema_frontend_output_release(&out); assert(!out.compilation.program && !out.lexemes);
  out = compile("{\"type\":\"object\",\"additionalProperties\":false,\"properties\":{"
    "\"x\":{\"type\":\"string\",\"pattern\":\"^a\",\"enum\":[\"b\",\"ab\",\"ac\"]}},\"required\":[\"x\"]}", true);
  assert(accepts(out.compilation.program, "{\"x\":\"ab\"}") && accepts(out.compilation.program, "{\"x\":\"ac\"}"));
  assert(!accepts(out.compilation.program, "{\"x\":\"b\"}") && !accepts(out.compilation.program, "{\"x\":\"a\"}"));
  lie_schema_frontend_output_release(&out);
  out = compile("{\"type\":\"object\",\"additionalProperties\":false,\"$defs\":{\"v\":{\"type\":\"number\",\"multipleOf\":0.3}},"
    "\"properties\":{\"x\":{\"$ref\":\"#/$defs/v\",\"minimum\":0.3,\"maximum\":0.9}},\"required\":[\"x\"]}", true);
  assert(accepts(out.compilation.program, "{\"x\":0.6}") && !accepts(out.compilation.program, "{\"x\":0.5}"));
  lie_schema_frontend_output_release(&out);
}
static void diagnostic_lifetime(void) {
  lie_json_value *tree = parse("{\"type\":\"object\",\"additionalProperties\":false,\"properties\":{"
    "\"x\":{\"type\":\"string\",\"unexpected\\u0000key\":1}},\"required\":[\"x\"]}");
  lie_schema_frontend *f = NULL; lie_schema_frontend_error e;
  assert(lie_schema_frontend_create(NULL, &f, &e) == LIE_FRONTEND_OK);
  lie_schema_frontend_output out; memset(&out, 0x5a, sizeof(out));
  unsigned char saved[sizeof(out)]; memcpy(saved, &out, sizeof(out));
  assert(lie_schema_frontend_compile(f, tree, true, false, &out, &e) == LIE_FRONTEND_PUBLICATION);
  assert(!memcmp(saved, &out, sizeof(out)) && e.schema_status == LIE_SCHEMA_INVALID);
  lie_json_value_release(tree);
  const char expected[] = "unexpected\0key";
  assert(e.schema_error.detail.size == sizeof(expected) - 1 &&
    !memcmp(e.schema_error.detail.data, expected, sizeof(expected) - 1));
  lie_schema_frontend_info info; lie_schema_frontend_describe(f, &info);
  assert(info.phase == LIE_FRONTEND_FAILED && info.retained_error_bytes > sizeof(expected));
  assert(lie_schema_frontend_compile(f, NULL, false, true, &out, NULL) == LIE_FRONTEND_PHASE);
  assert(!memcmp(saved, &out, sizeof(out))); lie_schema_frontend_release(f);
  lie_schema_frontend_description d; lie_schema_frontend_description_init(&d);
  d.max_error_bytes = 1;
  tree = parse("{\"type\":\"object\",\"unexpected\":1}");
  assert(lie_schema_frontend_create(&d, &f, &e) == LIE_FRONTEND_OK);
  assert(lie_schema_frontend_compile(f, tree, false, false, &out, &e) == LIE_FRONTEND_PUBLICATION);
  assert(e.schema_status == LIE_SCHEMA_RESOURCE && !memcmp(saved, &out, sizeof(out)));
  lie_json_value_release(tree); lie_schema_frontend_release(f);
}
static void allocation_and_object(void) {
  memory baseline = {0}; lie_schema_frontend_description d;
  lie_schema_frontend_description_init(&d); d.allocator = (lie_grammar_allocator){&baseline, allocate, release};
  lie_schema_frontend *f = NULL; lie_schema_frontend_error e; lie_schema_frontend_output out = {0};
  assert(lie_schema_frontend_create(&d, &f, &e) == LIE_FRONTEND_OK);
  assert(lie_schema_frontend_compile(f, NULL, false, true, &out, &e) == LIE_FRONTEND_OK);
  const size_t calls = baseline.calls;
  lie_schema_frontend_release(f);
  assert(accepts(out.compilation.program, "{\"nested\":[1,true,null,{\"s\":\"x\"}]}"));
  assert(!accepts(out.compilation.program, "[1]"));
  lie_schema_frontend_output_release(&out); assert(!baseline.live && !baseline.bytes);
  max_align_t sentinel;
  for (size_t fail = 1; fail <= calls; ++fail) {
    memory m = {.fail = fail}; d.allocator = (lie_grammar_allocator){&m, allocate, release};
    f = (void *)&sentinel; lie_schema_frontend_status rc = lie_schema_frontend_create(&d, &f, &e);
    if (rc == LIE_FRONTEND_OK) {
      memset(&out, 0x5a, sizeof(out)); unsigned char saved[sizeof(out)]; memcpy(saved, &out, sizeof(out));
      assert(lie_schema_frontend_compile(f, NULL, false, true, &out, &e) != LIE_FRONTEND_OK);
      assert(!memcmp(saved, &out, sizeof(out))); lie_schema_frontend_release(f);
    } else assert(f == (void *)&sentinel);
    assert(!m.live && !m.bytes);
  }
}
int main(void) {
  language(); diagnostic_lifetime(); allocation_and_object();
  puts("Native complete schema frontend: HOST NOT-INFERENCE"); return 0;
}
