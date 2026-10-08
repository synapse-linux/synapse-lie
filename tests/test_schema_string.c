/* SPDX-License-Identifier: MIT */
/* Independent string-leaf admission/language/lifetime fixtures, written for
 * final qualification. HOST NOT-INFERENCE; no model or GPU execution. */
#include "lie/schema_string.h"
#include "lie/schema_arena.h"
#include <assert.h>
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
static lie_json_value *parse(const char *s) {
  lie_json_value *out = NULL;
  assert(lie_json_value_parse(s, strlen(s), NULL, NULL, &out, NULL, NULL) == LIE_JSON_VALUE_OK);
  return out;
}
static lie_schema_string_description description(memory *m) {
  lie_schema_string_description d; lie_schema_string_description_init(&d);
  d.transform = lie_schema_arena_transform(NULL);
  if (m) d.transform.allocator = (lie_grammar_allocator){m, allocate, release};
  return d;
}
static bool accepts(const lie_grammar_lexeme *p, const char *text) {
  lie_lexeme_match match = {0};
  assert(lie_lexeme_check(p, (const uint8_t *)text, strlen(text), &match) == LIE_LEXEME_OK);
  return match.complete;
}
static lie_grammar_lexeme *create(const char *schema) {
  lie_json_value *tree = parse(schema);
  lie_schema_string_description d = description(NULL);
  lie_schema_string_error error = {0}; lie_grammar_lexeme *out = NULL;
  assert(lie_schema_string_create(&d, tree, &out, &error) == LIE_SCHEMA_OK);
  lie_json_value_release(tree); return out;
}
typedef struct { size_t calls, fail; } callbacks;
static lie_schema_status describe_node(void *p, lie_schema_node n, lie_schema_value *out) {
  callbacks *f = p;
  if (++f->calls == f->fail) return LIE_SCHEMA_CALLBACK;
  return lie_schema_json_describe(NULL, n, out);
}
static lie_schema_status child_node(void *p, lie_schema_node n, size_t at,
    lie_schema_bytes *key, lie_schema_node *out) {
  callbacks *f = p;
  if (++f->calls == f->fail) return LIE_SCHEMA_CALLBACK;
  return lie_schema_json_child(NULL, n, at, key, out);
}
static void callback_refusals(void) {
  lie_json_value *tree = parse("{\"minLength\":1,\"maxLength\":2,\"pattern\":\"^a\",\"format\":\"hostname\"}");
  lie_schema_string_description d = description(NULL);
  callbacks f = {0};
  d.transform.access.context = &f;
  d.transform.access.describe = describe_node; d.transform.access.child = child_node;
  lie_schema_string_plan plan; lie_schema_string_error e;
  assert(lie_schema_string_prepare(&d, tree, &plan, &e) == LIE_SCHEMA_OK);
  const size_t calls = f.calls;
  unsigned char before[sizeof(plan)];
  for (size_t fail = 1; fail <= calls; ++fail) {
    f = (callbacks){.fail = fail}; memset(&plan, 0x5a, sizeof(plan));
    memcpy(before, &plan, sizeof(plan));
    assert(lie_schema_string_prepare(&d, tree, &plan, &e) == LIE_SCHEMA_CALLBACK);
    assert(!memcmp(before, &plan, sizeof(plan)));
  }
  lie_json_value_release(tree);
}
static void language(void) {
  lie_grammar_lexeme *p = create("{\"minLength\":1,\"maxLength\":2,\"pattern\":\"^[ab]+$\"}");
  /* Every word of lengths0..3 over a,b,c, independent of the regex compiler. */
  for (size_t n = 0; n <= 3; ++n) {
    size_t possibilities = 1; for (size_t i = 0; i < n; ++i) possibilities *= 3;
    for (size_t code = 0; code < possibilities; ++code) {
      char text[6] = {'"'}; size_t digits = code; bool expected = n >= 1 && n <= 2;
      for (size_t i = 0; i < n; ++i) {
        unsigned digit = digits % 3; digits /= 3;
        text[i + 1] = (char)('a' + digit); expected = expected && digit < 2;
      }
      text[n + 1] = '"'; text[n + 2] = '\0';
      assert(accepts(p, text) == expected);
    }
  }
  lie_lexeme_release(p);
  p = create("{\"minLength\":1,\"maxLength\":1}");
  assert(accepts(p, "\"A\"") && accepts(p, "\"\\u0000\"") &&
         accepts(p, "\"\\ud83d\\ude00\"") && accepts(p, "\"\xc3\xa8\""));
  assert(!accepts(p, "\"\"") && !accepts(p, "\"AA\"") && !accepts(p, "\"\\ud800\""));
  lie_lexeme_release(p);
  p = create("{\"pattern\":\"^a\\u0000b$\"}");
  assert(accepts(p, "\"a\\u0000b\"") && !accepts(p, "\"ab\"")); lie_lexeme_release(p);
  p = create("{\"pattern\":\"^\\\\p{Greek}+$\",\"maxLength\":2}");
  assert(accepts(p, "\"\xce\xb1\"") && !accepts(p, "\"a\"")); lie_lexeme_release(p);
  p = create("{\"pattern\":\"^127\\\\.\",\"format\":\"ipv4\"}");
  assert(accepts(p, "\"127.0.0.1\"") && !accepts(p, "\"128.0.0.1\"") &&
         !accepts(p, "\"127.0.0.999\"")); lie_lexeme_release(p);
}
static void admission(void) {
  const struct { const char *schema; lie_schema_status status; const char *message; } cases[] = {
    {"{\"minLength\":-1}", LIE_SCHEMA_INVALID, "string lengths must be nonnegative integers up to 1048576"},
    {"{\"maxLength\":0.5}", LIE_SCHEMA_INVALID, "string lengths must be nonnegative integers up to 1048576"},
    {"{\"minLength\":1048577}", LIE_SCHEMA_INVALID, "string lengths must be nonnegative integers up to 1048576"},
    {"{\"minLength\":2,\"maxLength\":1,\"pattern\":false}", LIE_SCHEMA_EMPTY, "minLength exceeds maxLength"},
    {"{\"pattern\":\"[\",\"format\":false}", LIE_SCHEMA_INVALID, ""},
    {"{\"pattern\":\"[\",\"format\":\"unsupported\"}", LIE_SCHEMA_INVALID, "unsupported string format"},
    {"{\"minLength\":254,\"format\":\"hostname\"}", LIE_SCHEMA_EMPTY, "string predicates and lengths have no matching value"},
    {"{\"minLength\":3,\"pattern\":\"^a{2}$\"}", LIE_SCHEMA_EMPTY, "string predicates and lengths have no matching value"}
  };
  const lie_schema_string_description d = description(NULL); max_align_t sentinel;
  for (size_t i = 0; i < sizeof(cases) / sizeof(*cases); ++i) {
    lie_json_value *tree = parse(cases[i].schema);
    lie_schema_string_error e; lie_grammar_lexeme *out = (void *)&sentinel;
    assert(lie_schema_string_create(&d, tree, &out, &e) == cases[i].status);
    assert(out == (void *)&sentinel && e.schema_error.message && !strcmp(e.schema_error.message, cases[i].message));
    if (i == 4) assert(e.schema_error.detail.size == 6 &&
      !memcmp(e.schema_error.detail.data, "format", 6) && !strcmp(e.schema_error.suffix, " must be a string"));
    if (i == 6) assert(e.string_status == LIE_STRING_EMPTY_PATTERN);
    lie_json_value_release(tree);
  }
  lie_json_value *tree = parse("{\"format\":\"ipv4\"}");
  lie_schema_string_plan plan, copied;
  lie_schema_string_error e; assert(lie_schema_string_prepare(&d, tree, &plan, &e) == LIE_SCHEMA_OK);
  copied = plan; memset(&plan, 0, sizeof(plan)); lie_json_value_release(tree);
  lie_grammar_lexeme *p = NULL;
  assert(lie_schema_string_compile(&d, &copied, NULL, &p, &e) == LIE_SCHEMA_OK);
  assert(accepts(p, "\"1.2.3.4\"")); lie_lexeme_release(p);
}
static void reuse_and_refusals(void) {
  memory baseline = {0}; lie_schema_string_description d = description(&baseline);
  lie_json_value *tree = parse("{\"pattern\":\"^[ab]{1,2}$\"}");
  lie_schema_string_error e; lie_grammar_lexeme *out = NULL;
  assert(lie_schema_string_create(&d, tree, &out, &e) == LIE_SCHEMA_OK);
  const size_t calls = baseline.calls;
  lie_lexeme_release(out); assert(!baseline.live && !baseline.bytes);
  max_align_t sentinel;
  for (size_t fail = 1; fail <= calls; ++fail) {
    memory m = {.fail = fail}; d = description(&m); out = (void *)&sentinel;
    assert(lie_schema_string_create(&d, tree, &out, &e) == LIE_SCHEMA_RESOURCE);
    assert(out == (void *)&sentinel && !m.live && !m.bytes);
  }
  lie_json_value_release(tree);
  memory m = {0}; d = description(&m);
  lie_regex_program *unrestricted = NULL;
  assert(lie_schema_string_unrestricted(&d, &unrestricted, &e) == LIE_SCHEMA_OK);
  tree = parse("{\"maxLength\":2}");
  lie_schema_string_plan plan;
  assert(lie_schema_string_prepare(&d, tree, &plan, &e) == LIE_SCHEMA_OK);
  lie_json_value_release(tree); const size_t before = m.calls;
  assert(lie_schema_string_compile(&d, &plan, unrestricted, &out, &e) == LIE_SCHEMA_OK);
  assert(m.calls == before + 1); /* Reuse creates only the immutable lexeme. */
  lie_regex_release(unrestricted);
  assert(accepts(out, "\"\"") && accepts(out, "\"a\"") && accepts(out, "\"\\ud83d\\ude00\""));
  lie_lexeme_release(out); assert(!m.live && !m.bytes);
  tree = parse("{\"minLength\":1}"); d = description(NULL); d.transform.max_work = 1;
  out = (void *)&sentinel;
  assert(lie_schema_string_create(&d, tree, &out, &e) == LIE_SCHEMA_WORK_LIMIT);
  assert(out == (void *)&sentinel); lie_json_value_release(tree);
}
int main(void) {
  language(); admission(); callback_refusals(); reuse_and_refusals();
  puts("Native schema string construction: HOST NOT-INFERENCE");
  return 0;
}
