/* SPDX-License-Identifier: MIT */
/* Independent finite languages, deep graph safety and owned allocation refusal. */
#include "lie/grammar_builder.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define BYTE(c) (LIE_GRAMMAR_TERMINAL | (uint8_t)(c))
typedef union { max_align_t alignment; size_t bytes; } allocation_header;
typedef struct { size_t calls, fail_at, live, bytes, peak; } memory;
static void *allocate(void *ctx, size_t n) {
  memory *m = ctx;
  if (++m->calls == m->fail_at) return NULL;
  assert(n <= SIZE_MAX - sizeof(allocation_header));
  allocation_header *h = malloc(sizeof(*h) + n);
  if (!h) return NULL;
  h->bytes = n; ++m->live; m->bytes += n;
  if (m->bytes > m->peak) m->peak = m->bytes;
  return h + 1;
}
static void release(void *ctx, void *p) {
  memory *m = ctx; allocation_header *h = (allocation_header *)p - 1;
  assert(p && m->live && m->bytes >= h->bytes);
  --m->live; m->bytes -= h->bytes; free(h);
}
static lie_grammar_builder *builder(void) {
  lie_builder_description d; lie_builder_description_init(&d);
  lie_grammar_builder *b = NULL; assert(lie_builder_create(&d, &b) == LIE_BUILDER_OK); return b;
}
static bool whitespace(const void *ctx, uint32_t id, uint8_t byte) {
  (void)ctx; assert(id == 0); return byte == ' ' || byte == '\t' || byte == '\n' || byte == '\r';
}
static lie_grammar_status advance(const void *ctx, uint32_t id, const uint8_t *input,
  size_t n, uint8_t byte, uint8_t *out, size_t capacity, size_t *bytes, bool *prefix, bool *complete) {
  assert(whitespace(ctx, id, byte) && n < capacity);
  if (n && input != out) memcpy(out, input, n);
  out[n] = byte; *bytes = n + 1; *prefix = *complete = true; return LIE_GRAMMAR_OK;
}
static lie_grammar_program *program(lie_grammar_builder *b, uint32_t root, size_t lexemes) {
  lie_grammar_description d; assert(lie_builder_finish(b, root, lexemes, &d) == LIE_BUILDER_OK);
  if (lexemes) d.predicates = (lie_grammar_predicates){NULL, whitespace, advance, NULL};
  lie_grammar_program *p = NULL; assert(lie_grammar_program_create(&d, &p) == LIE_GRAMMAR_OK);
  uint32_t marker = UINT32_MAX;
  assert(lie_builder_sequence_make(b, NULL, 0, &marker) == LIE_BUILDER_INVALID && marker == UINT32_MAX);
  lie_builder_release(b); return p;
}
static bool accepts(const lie_grammar_program *p, const uint8_t *bytes, size_t n) {
  lie_grammar_state *s = NULL; assert(lie_grammar_start(p, &s) == LIE_GRAMMAR_OK);
  for (size_t i = 0; i < n; ++i) {
    lie_grammar_state *next = NULL;
    assert(lie_grammar_advance(p, s, bytes[i], &next) == LIE_GRAMMAR_OK);
    lie_grammar_state_release(s); s = next;
  }
  bool result = lie_grammar_complete(s); lie_grammar_state_release(s); return result;
}
static bool text(const lie_grammar_program *p, const char *s) {
  return accepts(p, (const uint8_t *)s, strlen(s));
}
static size_t intervals(void) {
  size_t checks = 0;
  for (unsigned low = 0; low < 20; ++low)
    for (unsigned width = 0; width < 10; ++width) {
      char first[16], last[16]; unsigned high = low + width;
      snprintf(first, sizeof(first), "%u", low); snprintf(last, sizeof(last), "%u", high);
      lie_grammar_builder *b = builder(); uint32_t root;
      assert(lie_builder_unsigned(b, first, strlen(first), last, strlen(last), &root) == LIE_BUILDER_OK);
      lie_grammar_program *p = program(b, root, 0);
      for (unsigned value = 0; value < 40; ++value) {
        char number[16]; snprintf(number, sizeof(number), "%u", value);
        assert(text(p, number) == (value >= low && value <= high)); ++checks;
      }
      assert(!text(p, "00") && !text(p, "+1") && !text(p, "1.0")); checks += 3;
      lie_grammar_program_release(p);
    }
  lie_grammar_builder *b = builder(); uint32_t root;
  assert(lie_builder_unsigned(b, "97", 2, NULL, 0, &root) == LIE_BUILDER_OK);
  lie_grammar_program *p = program(b, root, 0);
  for (unsigned i = 90; i < 110; ++i) { char n[16]; snprintf(n, sizeof(n), "%u", i); assert(text(p, n) == (i >= 97)); ++checks; }
  assert(text(p, "10000000000000000000000000000000000000000")); ++checks;
  lie_grammar_program_release(p);
  char maximum[512]; memset(maximum, '1', sizeof(maximum)); b = builder();
  assert(lie_builder_unsigned(b, maximum, sizeof(maximum), maximum, sizeof(maximum), &root) == LIE_BUILDER_OK);
  p = program(b, root, 0); assert(accepts(p, (const uint8_t *)maximum, sizeof(maximum))); ++checks;
  lie_grammar_program_release(p);
  char oversized[513]; memset(oversized, '1', sizeof(oversized)); b = builder(); root = UINT32_MAX;
  assert(lie_builder_unsigned(b, oversized, sizeof(oversized), NULL, 0, &root) == LIE_BUILDER_INVALID && root == UINT32_MAX); ++checks;
  lie_builder_release(b); return checks;
}
static size_t counts_and_literals(void) {
  size_t checks = 0;
  for (unsigned count = 0; count < 34; ++count)
    for (unsigned kind = 0; kind < 2; ++kind) {
      lie_grammar_builder *b = builder(); uint32_t root;
      assert((kind ? lie_builder_exact(b, BYTE('x'), count, &root)
                   : lie_builder_at_most(b, BYTE('x'), count, &root)) == LIE_BUILDER_OK);
      lie_grammar_program *p = program(b, root, 0); uint8_t x[36]; memset(x, 'x', sizeof(x));
      for (size_t n = 0; n <= sizeof(x); ++n) { assert(accepts(p, x, n) == (kind ? n == count : n <= count)); ++checks; }
      lie_grammar_program_release(p);
    }
  uint8_t bytes[137], copied[137]; for (size_t i = 0; i < sizeof(bytes); ++i) bytes[i] = (uint8_t)(i * 71);
  memcpy(copied, bytes, sizeof(bytes)); lie_grammar_builder *b = builder(); uint32_t root;
  assert(lie_builder_literal(b, bytes, sizeof(bytes), &root) == LIE_BUILDER_OK);
  memset(bytes, 0, sizeof(bytes)); lie_grammar_program *p = program(b, root, 0);
  assert(accepts(p, copied, sizeof(copied)) && !accepts(p, copied, sizeof(copied) - 1)); checks += 2;
  copied[100] ^= 1; assert(!accepts(p, copied, sizeof(copied))); ++checks;
  lie_grammar_program_release(p); return checks;
}
static size_t json_languages(void) {
  static const char *valid[] = {"null", "true", "false", "0", "-0", "-12.5e+3", "\"\"", "\"abc\"", "\"\\uD83D\\uDE00\"", "\"\xc3\xa8\"", "[]", "{}", "[null, 2]", "{\"a\":false}"};
  static const char *invalid[] = {"", "01", "+1", "1.", "1e", "-.2", "\"\\uD800\"", "\"\\uDC00\"", "\"\\q\"", "\"\xc0\x80\"", "[[]]", "{\"a\":{}}", "[true,]"};
  lie_grammar_builder *b = builder(); lie_builder_primitives primitives; uint32_t root;
  assert(lie_builder_json(b, LIE_GRAMMAR_LEXEME, &primitives) == LIE_BUILDER_OK);
  assert(lie_builder_generic_value(b, 1, &root) == LIE_BUILDER_OK);
  lie_grammar_program *p = program(b, root, 1);
  size_t checks = 0;
  for (size_t i = 0; i < sizeof(valid) / sizeof(*valid); ++i) { assert(text(p, valid[i])); ++checks; }
  for (size_t i = 0; i < sizeof(invalid) / sizeof(*invalid); ++i) { assert(!text(p, invalid[i])); ++checks; }
  lie_grammar_program_release(p); return checks;
}
static void graphs(void) {
  lie_grammar_builder *b = builder(); uint32_t dead, root;
  assert(lie_builder_new(b, NULL, 0, &dead) == LIE_BUILDER_OK);
  uint32_t infinite[] = {BYTE('x'), dead}; lie_builder_sequence s = {infinite, 2};
  assert(lie_builder_set(b, dead, &s, 1) == LIE_BUILDER_OK);
  uint32_t choices[] = {BYTE('a'), dead}; assert(lie_builder_alternatives(b, choices, 2, &root) == LIE_BUILDER_OK);
  lie_grammar_program *p = program(b, root, 0); assert(text(p, "a") && !text(p, "x") && !text(p, "xa")); lie_grammar_program_release(p);
  b = builder(); assert(lie_builder_new(b, NULL, 0, &root) == LIE_BUILDER_OK);
  lie_builder_sequence cycle[] = {{NULL, 0}, {&root, 1}};
  assert(lie_builder_set(b, root, cycle, 2) == LIE_BUILDER_OK);
  lie_grammar_description out, saved; memset(&out, 0xa5, sizeof(out)); memcpy(&saved, &out, sizeof(out));
  assert(lie_builder_finish(b, root, 0, &out) == LIE_BUILDER_CYCLE && !memcmp(&out, &saved, sizeof(out))); lie_builder_release(b);
  b = builder(); assert(lie_builder_new(b, NULL, 0, &root) == LIE_BUILDER_OK);
  assert(lie_builder_finish(b, root, 0, &out) == LIE_BUILDER_EMPTY && !memcmp(&out, &saved, sizeof(out))); lie_builder_release(b);
  b = builder(); assert(lie_builder_repeat(b, BYTE('x'), &root) == LIE_BUILDER_OK); p = program(b, root, 0);
  assert(text(p, "") && text(p, "xxxxx") && !text(p, "xxa")); lie_grammar_program_release(p);
  b = builder();
  for (size_t i = 0; i < 4096; ++i) { uint32_t id; assert(lie_builder_new(b, NULL, 0, &id) == LIE_BUILDER_OK && id == i); }
  for (uint32_t i = 0; i < 4096; ++i) { uint32_t child = i + 1; s = (lie_builder_sequence){&child, i == 4095 ? 0 : 1}; assert(lie_builder_set(b, i, &s, 1) == LIE_BUILDER_OK); }
  p = program(b, 0, 0); assert(text(p, "") && !text(p, "a")); lie_grammar_program_release(p);
}
static lie_builder_status fixture(memory *m) {
  lie_builder_description d; lie_builder_description_init(&d);
  d.allocator = (lie_grammar_allocator){m, allocate, release};
  lie_grammar_builder *b = (void *)(uintptr_t)1;
  lie_builder_status rc = lie_builder_create(&d, &b);
  if (rc != LIE_BUILDER_OK) { assert(b == (void *)(uintptr_t)1); return rc; }
  lie_builder_primitives primitives; memset(&primitives, 0xa5, sizeof(primitives));
  rc = lie_builder_json(b, LIE_GRAMMAR_LEXEME, &primitives);
  uint32_t generic = UINT32_MAX, interval = UINT32_MAX, root = UINT32_MAX;
  if (rc == LIE_BUILDER_OK) {
    rc = lie_builder_generic_value(b, 2, &generic);
    if (rc != LIE_BUILDER_OK) assert(generic == UINT32_MAX);
  }
  if (rc == LIE_BUILDER_OK) {
    rc = lie_builder_unsigned(b, "12", 2, "37", 2, &interval);
    if (rc != LIE_BUILDER_OK) assert(interval == UINT32_MAX);
  }
  if (rc == LIE_BUILDER_OK) {
    uint32_t choices[] = {generic, interval};
    rc = lie_builder_alternatives(b, choices, 2, &root);
    if (rc != LIE_BUILDER_OK) assert(root == UINT32_MAX);
  }
  if (rc == LIE_BUILDER_OK) {
    lie_grammar_description out, saved; memset(&out, 0xa5, sizeof(out)); memcpy(&saved, &out, sizeof(out));
    rc = lie_builder_finish(b, root, 1, &out);
    if (rc != LIE_BUILDER_OK) assert(!memcmp(&out, &saved, sizeof(out)));
  }
  if (rc != LIE_BUILDER_OK) {
    uint32_t marker = UINT32_MAX;
    assert(lie_builder_sequence_make(b, NULL, 0, &marker) == rc && marker == UINT32_MAX);
  }
  lie_builder_release(b); assert(!m->live && !m->bytes); return rc;
}
static size_t faults(size_t *peak) {
  memory ordinary = {0}; assert(fixture(&ordinary) == LIE_BUILDER_OK);
  size_t points = ordinary.calls; *peak = ordinary.peak;
  for (size_t point = 1; point <= points; ++point) {
    memory m = {.fail_at = point}; assert(fixture(&m) == LIE_BUILDER_RESOURCE);
    assert(!m.live && !m.bytes);
  }
  return points;
}
static void limits(void) {
  lie_builder_description d; lie_builder_description_init(&d);
  lie_grammar_builder *b = (void *)(uintptr_t)1;
  d.abi_version = 0;
  assert(lie_builder_create(&d, &b) == LIE_BUILDER_INVALID && b == (void *)(uintptr_t)1);
  lie_builder_description_init(&d); d.allocator.allocate = allocate;
  assert(lie_builder_create(&d, &b) == LIE_BUILDER_INVALID && b == (void *)(uintptr_t)1);
  lie_builder_description_init(&d); d.max_rules = 1;
  assert(lie_builder_create(&d, &b) == LIE_BUILDER_OK);
  uint32_t root; assert(lie_builder_new(b, NULL, 0, &root) == LIE_BUILDER_OK);
  uint32_t marker = UINT32_MAX;
  assert(lie_builder_new(b, NULL, 0, &marker) == LIE_BUILDER_RULE_LIMIT && marker == UINT32_MAX); lie_builder_release(b);
  lie_builder_description_init(&d); d.max_classes = 256;
  assert(lie_builder_create(&d, &b) == LIE_BUILDER_OK);
  assert(lie_builder_range(b, 'a', 'z', &marker) == LIE_BUILDER_TABLE_LIMIT && marker == UINT32_MAX); lie_builder_release(b);
  lie_builder_description_init(&d); d.max_work = 1;
  assert(lie_builder_create(&d, &b) == LIE_BUILDER_OK);
  assert(lie_builder_exact(b, BYTE('a'), 2, &marker) == LIE_BUILDER_WORK_LIMIT && marker == UINT32_MAX); lie_builder_release(b);
  b = builder(); assert(lie_builder_range(b, 256, 257, &marker) == LIE_BUILDER_INVALID && marker == UINT32_MAX); lie_builder_release(b);
  b = builder(); assert(lie_builder_unsigned(b, "00", 2, NULL, 0, &marker) == LIE_BUILDER_INVALID && marker == UINT32_MAX); lie_builder_release(b);
  b = builder(); assert(lie_builder_unsigned(b, "9", 1, "2", 1, &marker) == LIE_BUILDER_EMPTY && marker == UINT32_MAX); lie_builder_release(b);
  b = builder(); uint32_t invalid = LIE_GRAMMAR_TERMINAL | LIE_GRAMMAR_LEXEME;
  assert(lie_builder_sequence_make(b, &invalid, 1, &root) == LIE_BUILDER_OK);
  lie_grammar_description out;
  assert(lie_builder_finish(b, root, 0, &out) == LIE_BUILDER_INVALID); lie_builder_release(b);
}
int main(void) {
  size_t checks = intervals() + counts_and_literals() + json_languages(), peak = 0;
  graphs(); limits(); size_t allocation_points = faults(&peak);
  printf("BUILDER_LANGUAGE_ORACLES=%zu OWN_ALLOCATOR_REFUSALS=%zu OWN_FIXTURE_PEAK_BYTES=%zu ITERATIVE_CHAIN_RULES=4096 HOST_NOT_INFERENCE\n", checks, allocation_points, peak);
}
