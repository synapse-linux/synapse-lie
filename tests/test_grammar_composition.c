/* SPDX-License-Identifier: MIT */
/* Independent C language/identity/lifetime/accounting/refusal oracles. */
#include "lie/grammar_composition.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { size_t calls, fail_at, live, bytes, peak; } memory;
typedef union { max_align_t alignment; size_t bytes; } block;
static void *allocate(void *ctx, size_t bytes) {
  memory *m = ctx;
  if (++m->calls == m->fail_at) return NULL;
  block *p = malloc(sizeof(*p) + bytes);
  if (!p) return NULL;
  p->bytes = bytes; ++m->live; m->bytes += bytes;
  if (m->bytes > m->peak) m->peak = m->bytes;
  return p + 1;
}
static void release(void *ctx, void *ptr) {
  memory *m = ctx; block *p = (block *)ptr - 1;
  assert(m->live && m->bytes >= p->bytes);
  --m->live; m->bytes -= p->bytes; free(p);
}
static bool allows(const void *ctx, uint32_t id, uint8_t b) {
  (void)ctx; assert(id == 0); return b == 'B';
}
static lie_grammar_status advance(const void *ctx, uint32_t id,
  const uint8_t *in, size_t bytes, uint8_t byte, uint8_t *out, size_t capacity,
  size_t *length, bool *prefix, bool *complete) {
  (void)ctx; (void)in; (void)bytes; (void)out; (void)capacity;
  assert(id == 0); *length = 0; *prefix = false; *complete = byte == 'B';
  return LIE_GRAMMAR_OK;
}
static lie_grammar_program *make(bool lexeme) {
  uint8_t classes[256 * 32] = {0};
  for (unsigned i = 0; i < 256; ++i) classes[i * 32 + i / 8] = (uint8_t)(1u << (i % 8));
  lie_grammar_range rule = {0, 1}, seq = {0, 1};
  uint32_t symbol = lexeme ? LIE_GRAMMAR_LEXEME : LIE_GRAMMAR_TERMINAL | 'A';
  lie_grammar_description d; lie_grammar_description_init(&d);
  d.rules = &rule; d.rule_count = 1; d.sequences = &seq; d.sequence_count = 1;
  d.symbols = &symbol; d.symbol_count = 1; d.classes = classes; d.class_count = 256;
  if (lexeme) { d.lexeme_count = 1; d.predicates = (lie_grammar_predicates){NULL, allows, advance, NULL}; }
  lie_grammar_program *p = NULL; assert(lie_grammar_program_create(&d, &p) == LIE_GRAMMAR_OK);
  memset(classes, 0, sizeof(classes)); symbol = 0;
  return p;
}
static lie_grammar_program *runtime(lie_grammar_composition *c, memory *m) {
  lie_composition_view v; assert(lie_composition_describe(c, &v) == LIE_COMPOSITION_OK);
  if (m) assert(v.owned_bytes == m->bytes && v.peak_owned_bytes == m->peak);
  if (v.grammar.lexeme_count) v.grammar.predicates = (lie_grammar_predicates){NULL, allows, advance, NULL};
  lie_grammar_program *p = NULL; assert(lie_grammar_program_create(&v.grammar, &p) == LIE_GRAMMAR_OK);
  return p;
}
static bool accepts(const lie_grammar_program *p, const uint8_t *s, size_t bytes) {
  lie_grammar_state *state = NULL; assert(lie_grammar_start(p, &state) == LIE_GRAMMAR_OK);
  for (size_t i = 0; i < bytes; ++i) {
    lie_grammar_state *next = NULL;
    assert(lie_grammar_advance(p, state, s[i], &next) == LIE_GRAMMAR_OK);
    lie_grammar_state_release(state); state = next;
  }
  bool complete = lie_grammar_complete(state); lie_grammar_state_release(state); return complete;
}
static bool text(const lie_grammar_program *p, const char *s) {
  return accepts(p, (const uint8_t *)s, strlen(s));
}
int main(void) {
  size_t oracles = 0, refusals = 0;
  lie_grammar_program *base = make(false), *arg = make(true);
  lie_composition_description d; lie_composition_description_init(&d);
  lie_grammar_composition *c = NULL;
  assert(lie_composition_reasoning(&d, base, true, &c) == LIE_COMPOSITION_OK);
  lie_grammar_program *p = runtime(c, NULL); lie_composition_release(c);
  for (unsigned byte = 0; byte < 256; ++byte) {
    uint8_t value[] = {(uint8_t)byte, '<','/','t','h','i','n','k','>','A'};
    assert(accepts(p, value, sizeof(value))); ++oracles;
  }
  assert(text(p, "<</thi</think>A") && !text(p, "</think>B") && !text(p, "thinking")); oracles += 3;
  lie_grammar_program_release(p);
  const lie_composition_tool tools[] = {{(const uint8_t *)"run", 3, arg}, {(const uint8_t *)"same", 4, arg}};
  const char *call = "<tool_call>{\"name\":\"run\",\"arguments\":B}</tool_call>";
  char twice[256]; (void)snprintf(twice, sizeof(twice), "%s%s", call, call);
  for (unsigned mode = 0; mode < 8; ++mode) {
    bool plain = mode & 1, required = mode & 2, parallel = mode & 4;
    assert(lie_composition_tools(&d, base, plain, tools, 2, required, parallel, &c) == LIE_COMPOSITION_OK);
    lie_composition_view v; assert(lie_composition_describe(c, &v) == LIE_COMPOSITION_OK);
    assert(v.stop_only_when_complete == (!plain && !parallel));
    assert(v.grammar.lexeme_count == 1 && v.lexemes[0].program == arg && v.lexemes[0].index == 0);
    assert(v.grammar.class_count >= 512);
    p = runtime(c, NULL); lie_composition_release(c);
    assert(text(p, call) && text(p, twice) == parallel);
    assert(text(p, "A") == !required);
    assert(text(p, "ordinary text") == (plain && !required));
    assert(!text(p, "<tool_call>{\"name\":\"run\",\"arguments\":A}</tool_call>"));
    assert(text(p, "<tool_call>{\"name\":\"same\",\"arguments\":B}</tool_call>"));
    lie_grammar_program_release(p); oracles += 8;
  }
  /* Base identity is reused rather than imported a second time. */
  lie_composition_tool same = {(const uint8_t *)"base", 4, base};
  assert(lie_composition_tools(&d, base, false, &same, 1, true, false, &c) == LIE_COMPOSITION_OK);
  lie_composition_view v; assert(lie_composition_describe(c, &v) == LIE_COMPOSITION_OK);
  assert(v.grammar.class_count == 256 && !v.grammar.lexeme_count); ++oracles;
  lie_composition_release(c);
  /* Every control byte, NUL, quote, slash and high byte is copied/quoted exactly. */
  for (unsigned b = 0; b < 256; ++b) {
    uint8_t name = (uint8_t)b; lie_composition_tool t = {&name, 1, arg};
    assert(lie_composition_tools(&d, base, false, &t, 1, true, false, &c) == LIE_COMPOSITION_OK);
    p = runtime(c, NULL); name = 0; lie_composition_release(c);
    char quoted[16];
    switch (b) {
    case '"': strcpy(quoted, "\\\""); break; case '\\': strcpy(quoted, "\\\\"); break;
    case '\b': strcpy(quoted, "\\b"); break; case '\f': strcpy(quoted, "\\f"); break;
    case '\n': strcpy(quoted, "\\n"); break; case '\r': strcpy(quoted, "\\r"); break;
    case '\t': strcpy(quoted, "\\t"); break;
    default: if (b < 32) (void)snprintf(quoted, sizeof(quoted), "\\u%04x", b);
             else { quoted[0] = (char)b; quoted[1] = 0; }
    }
    char value[128]; (void)snprintf(value, sizeof(value), "<tool_call>{\"name\":\"%s\",\"arguments\":B}</tool_call>", quoted);
    assert(text(p, value)); ++oracles; lie_grammar_program_release(p);
  }
  for (unsigned kind = 0; kind < 2; ++kind) {
    size_t calls = 0;
    for (size_t n = 0; !n || n <= calls; ++n) {
      memory m = {.fail_at = n}; d.allocator = (lie_grammar_allocator){&m, allocate, release};
      lie_grammar_composition *sentinel = (lie_grammar_composition *)&m; c = sentinel;
      lie_composition_status rc = kind ? lie_composition_tools(&d, base, true, tools, 2, true, false, &c)
                                      : lie_composition_reasoning(&d, base, false, &c);
      if (!n) {
        assert(rc == LIE_COMPOSITION_OK); calls = m.calls;
        p = runtime(c, &m); lie_grammar_program_release(p); lie_composition_release(c);
        assert(calls > 5); ++oracles;
      } else { assert(rc == LIE_COMPOSITION_RESOURCE && c == sentinel); ++refusals; }
      assert(!m.live && !m.bytes);
    }
  }
  lie_composition_description_init(&d);
  for (unsigned kind = 0; kind < 6; ++kind) {
    lie_composition_description limited = d;
    switch (kind) {
    case 0: limited.max_rules = 1; break; case 1: limited.max_classes = 256; break;
    case 2: limited.max_lexemes = 0; break; case 3: limited.max_sequences = 1; break;
    case 4: limited.max_symbols = 1; break; default: limited.max_work = 10;
    }
    c = (lie_grammar_composition *)&d;
    lie_composition_status rc = lie_composition_tools(&limited, base, true, tools, 1, true, false, &c);
    assert(rc == (kind == 5 ? LIE_COMPOSITION_WORK_LIMIT : LIE_COMPOSITION_TABLE_LIMIT));
    assert(c == (lie_grammar_composition *)&d); ++refusals;
  }
  v.owned_bytes = 987; assert(lie_composition_describe(NULL, &v) == LIE_COMPOSITION_INVALID && v.owned_bytes == 987);
  c = (lie_grammar_composition *)&d;
  d.abi_version = 0;
  assert(lie_composition_reasoning(&d, base, true, &c) == LIE_COMPOSITION_INVALID && c == (lie_grammar_composition *)&d);
  lie_grammar_description before; memset(&before, 0xa5, sizeof(before));
  lie_grammar_description after = before;
  assert(lie_grammar_program_describe(NULL, &after) == LIE_GRAMMAR_INVALID && !memcmp(&before, &after, sizeof(after)));
  refusals += 3;
  lie_grammar_program_release(base); lie_grammar_program_release(arg);
  printf("C17 composition: %zu independent oracles, %zu refusals; HOST_NOT_INFERENCE\n", oracles, refusals);
}
