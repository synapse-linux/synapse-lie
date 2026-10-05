/* SPDX-License-Identifier: MIT */
/* Independent byte-language, refusal/lifetime and bit-preserving mask fixtures. */
#include "lie/grammar.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { size_t calls, fail_at, live; } memory;
static void *allocate(void *ctx, size_t bytes) {
  memory *m = ctx;
  ++m->calls;
  if (m->calls == m->fail_at)
    return NULL;
  void *p = malloc(bytes);
  if (p)
    ++m->live;
  return p;
}
static void release(void *ctx, void *p) {
  memory *m = ctx;
  assert(p && m->live);
  --m->live;
  free(p);
}
static lie_grammar_description language(memory *m) {
  static const lie_grammar_range rules[] = {{0, 1}, {1, 4}};
  static const lie_grammar_range sequences[] = {{0, 2}, {2, 0}, {2, 2},
                                               {4, 2}, {6, 2}};
  static const uint32_t symbols[] = {1, LIE_GRAMMAR_TERMINAL | 2,
      LIE_GRAMMAR_TERMINAL | 0, 1, LIE_GRAMMAR_TERMINAL | 1, 1,
      LIE_GRAMMAR_TERMINAL | 0, 1};
  static uint8_t classes[96];
  memset(classes, 0, sizeof(classes));
  for (unsigned i = 0; i < 3; ++i) {
    unsigned byte = 'a' + i;
    classes[i * 32 + byte / 8] |= 1u << (byte % 8);
  }
  lie_grammar_description d;
  lie_grammar_description_init(&d);
  d.rules = rules; d.rule_count = 2;
  d.sequences = sequences; d.sequence_count = 5;
  d.symbols = symbols; d.symbol_count = 8;
  d.classes = classes; d.class_count = 3;
  if (m)
    d.allocator = (lie_grammar_allocator){m, allocate, release};
  return d;
}
static unsigned words(void) {
  lie_grammar_description d = language(NULL);
  lie_grammar_program *p = NULL;
  assert(lie_grammar_program_create(&d, &p) == LIE_GRAMMAR_OK);
  unsigned transitions = 0;
  for (unsigned length = 0; length <= 8; ++length)
    for (unsigned bits = 0; bits < (1u << length); ++bits) {
      lie_grammar_state *state = NULL;
      assert(lie_grammar_start(p, &state) == LIE_GRAMMAR_OK);
      assert(lie_grammar_state_count(state) == 3 && !lie_grammar_complete(state));
      for (unsigned i = 0; i < length; ++i) {
        lie_grammar_state *next = NULL;
        assert(lie_grammar_advance(p, state, (bits >> i) & 1 ? 'a' : 'b', &next) ==
               LIE_GRAMMAR_OK);
        assert(lie_grammar_state_count(next) == 3 && !lie_grammar_complete(next));
        lie_grammar_state_release(state);
        state = next;
        ++transitions;
      }
      /* Every byte is independently classified for every binary prefix. */
      for (unsigned byte = 0; byte < 256; ++byte) {
        lie_grammar_state *next = NULL;
        assert(lie_grammar_advance(p, state, (uint8_t)byte, &next) == LIE_GRAMMAR_OK);
        assert(lie_grammar_complete(next) == (byte == 'c'));
        assert(lie_grammar_state_count(next) ==
               (byte == 'a' || byte == 'b' ? 3u : byte == 'c' ? 1u : 0u));
        if (byte == 'c') {
          lie_grammar_state *dead = NULL;
          assert(lie_grammar_advance(p, next, 'a', &dead) == LIE_GRAMMAR_OK);
          assert(!lie_grammar_state_count(dead) && !lie_grammar_complete(dead));
          lie_grammar_state_release(dead);
        }
        lie_grammar_state_release(next);
        ++transitions;
      }
      lie_grammar_state_release(state);
    }
  lie_grammar_program_release(p);
  return transitions;
}
static void lifetime_refusals(void) {
  memory m = {0};
  lie_grammar_description d = language(&m);
  lie_grammar_program *p = NULL;
  assert(lie_grammar_program_create(&d, &p) == LIE_GRAMMAR_OK);
  lie_grammar_state *base = NULL, *next = NULL;
  size_t before = m.calls;
  assert(lie_grammar_start(p, &base) == LIE_GRAMMAR_OK);
  size_t start_calls = m.calls - before;
  before = m.calls;
  assert(lie_grammar_advance(p, base, 'a', &next) == LIE_GRAMMAR_OK);
  size_t advance_calls = m.calls - before;
  lie_grammar_state_release(next);
  size_t live = m.live;
  for (unsigned op = 0; op < 2; ++op) {
    size_t count = op ? advance_calls : start_calls;
    for (size_t i = 1; i <= count; ++i) {
      m.fail_at = m.calls + i;
      next = base;
      assert((op ? lie_grammar_advance(p, base, 'a', &next)
                  : lie_grammar_start(p, &next)) == LIE_GRAMMAR_RESOURCE);
      assert(next == base && m.live == live && lie_grammar_state_count(base) == 3);
      m.fail_at = 0;
    }
  }
  lie_grammar_state_release(base);
  lie_grammar_program_release(p);
  assert(!m.live);
  /* Program creation owns copies; every construction allocation may refuse. */
  for (size_t i = 1; i <= 2; ++i) {
    m.fail_at = m.calls + i;
    p = NULL;
    assert(lie_grammar_program_create(&d, &p) == LIE_GRAMMAR_RESOURCE);
    assert(!p && !m.live);
    m.fail_at = 0;
  }
  d.root = 2;
  assert(lie_grammar_program_create(&d, &p) == LIE_GRAMMAR_INVALID && !p);
  d.root = 0;
  ++d.abi_version;
  assert(lie_grammar_program_create(&d, &p) == LIE_GRAMMAR_INVALID && !p);
}
static void budgets(void) {
  lie_grammar_description d = language(NULL);
  d.limits.max_states = 2;
  lie_grammar_program *p = NULL;
  assert(lie_grammar_program_create(&d, &p) == LIE_GRAMMAR_OK);
  lie_grammar_state *s = NULL;
  assert(lie_grammar_start(p, &s) == LIE_GRAMMAR_STATE_LIMIT && !s);
  lie_grammar_program_release(p);
  const lie_grammar_range rule = {0, 1}, seq = {0, 1};
  const uint32_t cycle = 0;
  d = language(NULL);
  d.rules = &rule; d.rule_count = 1;
  d.sequences = &seq; d.sequence_count = 1;
  d.symbols = &cycle; d.symbol_count = 1;
  d.limits.max_work = 17;
  assert(lie_grammar_program_create(&d, &p) == LIE_GRAMMAR_OK);
  assert(lie_grammar_start(p, &s) == LIE_GRAMMAR_WORK_LIMIT && !s);
  lie_grammar_program_release(p);
  lie_grammar_range long_seq = {0, 3};
  const uint32_t long_symbols[] = {LIE_GRAMMAR_TERMINAL,
                                  LIE_GRAMMAR_TERMINAL, LIE_GRAMMAR_TERMINAL};
  d.sequences = &long_seq; d.symbols = long_symbols; d.symbol_count = 3;
  d.limits.max_stack = 2;
  assert(lie_grammar_program_create(&d, &p) == LIE_GRAMMAR_OK);
  assert(lie_grammar_start(p, &s) == LIE_GRAMMAR_STACK_LIMIT && !s);
  lie_grammar_program_release(p);
}
static bool digit(const void *ctx, uint32_t id, uint8_t byte) {
  (void)ctx;
  assert(id == 0);
  return byte >= '0' && byte <= '9';
}
static lie_grammar_status predicate(const void *ctx, uint32_t id,
    const uint8_t *input, size_t n, uint8_t byte, uint8_t *out, size_t capacity,
    size_t *length, bool *prefix, bool *complete) {
  (void)input;
  assert(id == 0 && digit(ctx, id, byte));
  if (ctx)
    return LIE_GRAMMAR_PREDICATE;
  if (n >= capacity)
    return LIE_GRAMMAR_RESOURCE;
  out[n] = byte;
  *length = n + 1;
  *prefix = *complete = true;
  return LIE_GRAMMAR_OK;
}
static lie_grammar_status canonical(const void *ctx, uint32_t id, uint8_t *out,
                                    size_t *n, size_t capacity, size_t window) {
  (void)ctx;
  assert(id == 0 && *n <= capacity);
  if (*n > window && *n) {
    out[0] = 0;
    *n = 1;
  }
  return LIE_GRAMMAR_OK;
}
static void lexemes(void) {
  lie_grammar_description d;
  lie_grammar_description_init(&d);
  const lie_grammar_range rule = {0, 1}, seq = {0, 2};
  const uint32_t symbols[] = {LIE_GRAMMAR_LEXEME, LIE_GRAMMAR_TERMINAL};
  uint8_t classes[32] = {0};
  classes[';' / 8] |= 1u << (';' % 8);
  d.rules = &rule; d.rule_count = 1;
  d.sequences = &seq; d.sequence_count = 1;
  d.symbols = symbols; d.symbol_count = 2;
  d.classes = classes; d.class_count = 1; d.lexeme_count = 1;
  d.predicates = (lie_grammar_predicates){NULL, digit, predicate, canonical};
  lie_grammar_program *p = NULL;
  assert(lie_grammar_program_create(&d, &p) == LIE_GRAMMAR_OK);
  memset(classes, 0, sizeof(classes)); /* Immutable tables are independently owned. */
  lie_grammar_state *s = NULL;
  assert(lie_grammar_start(p, &s) == LIE_GRAMMAR_OK);
  for (unsigned byte = '1'; byte <= '3'; ++byte) {
    lie_grammar_state *next = NULL;
    assert(lie_grammar_advance(p, s, (uint8_t)byte, &next) == LIE_GRAMMAR_OK);
    lie_grammar_state_release(s);
    s = next;
    assert(lie_grammar_state_count(s) == 2 && !lie_grammar_complete(s));
  }
  lie_grammar_frame frame;
  assert(lie_grammar_state_frame(s, 1, &frame) == LIE_GRAMMAR_OK);
  assert(frame.lexeme_bytes == 3 && !memcmp(frame.lexeme, "123", 3));
  lie_grammar_state *c = NULL;
  assert(lie_grammar_canonical(p, s, 1, &c) == LIE_GRAMMAR_OK);
  assert(lie_grammar_state_frame(c, 1, &frame) == LIE_GRAMMAR_OK);
  assert(frame.lexeme_bytes == 1 && frame.lexeme[0] == 0);
  assert(lie_grammar_state_frame(s, 1, &frame) == LIE_GRAMMAR_OK);
  assert(frame.lexeme_bytes == 3 && !memcmp(frame.lexeme, "123", 3));
  lie_grammar_state_release(c);
  assert(lie_grammar_advance(p, s, ';', &c) == LIE_GRAMMAR_OK);
  assert(lie_grammar_complete(c));
  lie_grammar_state_release(c);
  lie_grammar_state_release(s);
  lie_grammar_program_release(p);
  d.predicates.context = &d;
  assert(lie_grammar_program_create(&d, &p) == LIE_GRAMMAR_OK);
  assert(lie_grammar_start(p, &s) == LIE_GRAMMAR_OK);
  c = s;
  assert(lie_grammar_advance(p, s, '1', &c) == LIE_GRAMMAR_PREDICATE && c == s);
  lie_grammar_state_release(s);
  lie_grammar_program_release(p);
}
static void masks(void) {
  const uint32_t bit_patterns[] = {0x3f800000, 0x7fc01234, 0x7f800000, 0xbf800000};
  float logits[4], out[4], before[4];
  memcpy(logits, bit_patterns, sizeof(logits));
  const uint8_t mask[] = {0, 2, 1, 0};
  assert(lie_grammar_mask_logits(logits, 4, NULL, 0, mask, 4, out, 4) == LIE_GRAMMAR_OK);
  assert(isinf(out[0]) && out[0] < 0 && isinf(out[3]) && out[3] < 0);
  assert(!memcmp(out + 1, logits + 1, 2 * sizeof(float)));
  assert(lie_grammar_mask_logits(logits, 4, NULL, 0, mask, 4, logits, 4) == LIE_GRAMMAR_OK);
  assert(!memcmp(out, logits, sizeof(out)));
  const uint32_t ids[] = {3, 1, 0, 2};
  assert(lie_grammar_mask_logits(logits, 4, ids, 4, mask, 4, out, 4) == LIE_GRAMMAR_OK);
  memcpy(before, out, sizeof(out));
  const uint32_t bad[] = {0, 1, 2, 4};
  assert(lie_grammar_mask_logits(logits, 4, bad, 4, mask, 4, out, 4) == LIE_GRAMMAR_INVALID);
  assert(!memcmp(out, before, sizeof(out)));
  assert(lie_grammar_mask_logits(logits, 3, NULL, 0, mask, 4, out, 4) == LIE_GRAMMAR_INVALID);
  assert(lie_grammar_mask_logits(logits, 3, ids, 3, mask, 4, logits + 1, 3) == LIE_GRAMMAR_INVALID);
}
int main(void) {
  unsigned count = words();
  lifetime_refusals();
  budgets();
  lexemes();
  masks();
  printf("Byte grammar/state/refusal/mask contracts PASS: %u independent transitions; NOT-INFERENCE\n", count);
}
