/* SPDX-License-Identifier: MIT */
/* Independent finite-language/Unicode and allocator/budget lifetime oracles. */
/* Synthetic construction and runtime fixtures; NOT-INFERENCE. */
#include "lie/grammar_regex_compile.h"
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct {
  size_t calls, fail_at, live, bytes, peak;
} memory;
typedef union {
  size_t bytes;
  max_align_t alignment;
} allocation;
static void *allocate(void *ctx, size_t n) {
  memory *m = ctx;
  ++m->calls;
  if (m->calls == m->fail_at)
    return NULL;
  allocation *p = malloc(sizeof(*p) + n);
  if (!p)
    return NULL;
  p->bytes = n;
  ++m->live;
  m->bytes += n;
  if (m->bytes > m->peak)
    m->peak = m->bytes;
  return p + 1;
}
static void release(void *ctx, void *ptr) {
  memory *m = ctx;
  allocation *p = (allocation *)ptr - 1;
  assert(m->live && m->bytes >= p->bytes);
  --m->live;
  m->bytes -= p->bytes;
  free(p);
}
static lie_regex_compiler_description description(memory *m) {
  lie_regex_compiler_description d;
  lie_regex_compiler_description_init(&d);
  d.maximum_length = 9;
  if (m)
    d.allocator = (lie_grammar_allocator){m, allocate, release};
  return d;
}
static uint32_t chars(lie_regex_compiler *c, uint32_t first, uint32_t last) {
  lie_unicode_range r = {first, last};
  uint32_t cls, id;
  assert(lie_regex_class_add(c, &r, 1, &cls) == LIE_REGEX_COMPILE_OK);
  r.first = r.last = 'z'; /* The builder owns the supplied scalar ranges. */
  assert(lie_regex_chars(c, cls, &id) == LIE_REGEX_COMPILE_OK);
  return id;
}
static uint32_t combine(lie_regex_compiler *c, lie_regex_operation op,
                        const uint32_t *p, size_t n) {
  uint32_t id;
  assert(lie_regex_combine(c, op, p, n, &id) == LIE_REGEX_COMPILE_OK);
  return id;
}
static uint32_t two(lie_regex_compiler *c, lie_regex_operation op, uint32_t a,
                    uint32_t b) {
  uint32_t p[] = {a, b};
  return combine(c, op, p, 2);
}
static uint32_t repeat(lie_regex_compiler *c, uint32_t child, uint32_t lo,
                       uint32_t hi) {
  uint32_t id;
  assert(lie_regex_repeat(c, child, lo, hi, &id) == LIE_REGEX_COMPILE_OK);
  return id;
}
static uint32_t negate(lie_regex_compiler *c, uint32_t child) {
  uint32_t id;
  assert(lie_regex_not(c, child, &id) == LIE_REGEX_COMPILE_OK);
  return id;
}
static lie_regex_compiler *fixture(memory *m, uint32_t *root) {
  lie_regex_compiler_description d = description(m);
  lie_regex_compiler *c = NULL;
  assert(lie_regex_compiler_create(&d, &c) == LIE_REGEX_COMPILE_OK);
  uint32_t a = chars(c, 'a', 'a'), b = chars(c, 'b', 'b');
  *root = two(c, LIE_REGEX_UNION, two(c, LIE_REGEX_CONCATENATION, a, b),
              repeat(c, a, 1, 3));
  return c;
}
static bool oracle(unsigned which, const uint8_t *p, size_t n) {
  bool only_a = true, only_ab = true, alternating = true;
  for (size_t i = 0; i < n; ++i) {
    only_a &= p[i] == 'a';
    only_ab &= p[i] == 'a' || p[i] == 'b';
    alternating &= p[i] == (i % 2 ? 'b' : 'a');
  }
  switch (which) {
  case 0:
    return n == 1 && p[0] == 'a';
  case 1:
    return n == 1 && (p[0] == 'a' || p[0] == 'b');
  case 2:
    return n >= 1 && n <= 3 && only_ab;
  case 3:
    return n <= 4 && only_a;
  case 4:
    return n >= 2 && n <= 6 && n % 2 == 0 && alternating;
  case 5:
    return !(n == 1 && p[0] == 'a');
  case 6:
    return n == 1 && p[0] == 'a';
  case 7:
    return n > 0 && p[0] != '?' && p[n - 1] != '?';
  case 8:
    return !n || (p[0] == '?' && p[n - 1] == '?');
  case 9:
    return only_a && n != 2;
  case 10:
    return false;
  default:
    return true;
  }
}
static size_t finite(void) {
  uint32_t ignored;
  lie_regex_compiler *c = fixture(NULL, &ignored);
  lie_regex_bases base;
  assert(lie_regex_compiler_bases(c, &base) == LIE_REGEX_COMPILE_OK);
  uint32_t a = chars(c, 'a', 'a'), b = chars(c, 'b', 'b'), boundary, negative;
  assert(lie_regex_boundary(c, true, &boundary) == LIE_REGEX_COMPILE_OK);
  assert(lie_regex_boundary(c, false, &negative) == LIE_REGEX_COMPILE_OK);
  uint32_t empty_cls, empty_chars;
  assert(lie_regex_class_add(c, NULL, 0, &empty_cls) == LIE_REGEX_COMPILE_OK);
  assert(lie_regex_chars(c, empty_cls, &empty_chars) == LIE_REGEX_COMPILE_OK);
  uint32_t roots[] = {a,
                      two(c, LIE_REGEX_UNION, a, b),
                      repeat(c, two(c, LIE_REGEX_UNION, a, b), 1, 3),
                      repeat(c, two(c, LIE_REGEX_UNION, a, base.epsilon), 2, 4),
                      repeat(c, two(c, LIE_REGEX_CONCATENATION, a, b), 1, 3),
                      negate(c, a),
                      two(c, LIE_REGEX_CONCATENATION, base.start, a),
                      two(c, LIE_REGEX_CONCATENATION, boundary,
                          two(c, LIE_REGEX_CONCATENATION, base.all, boundary)),
                      two(c, LIE_REGEX_CONCATENATION, negative,
                          two(c, LIE_REGEX_CONCATENATION, base.all, negative)),
                      two(c, LIE_REGEX_INTERSECTION,
                          repeat(c, a, 0, UINT32_MAX),
                          negate(c, two(c, LIE_REGEX_CONCATENATION, a, a))),
                      empty_chars,
                      base.all};
  const uint8_t alphabet[] = {'a', 'b', 'c', '?'};
  size_t checks = 0;
  for (unsigned which = 0; which < sizeof(roots) / sizeof(roots[0]); ++which) {
    lie_regex_program *p = NULL;
    assert(lie_regex_seal(c, roots[which], &p) == LIE_REGEX_COMPILE_OK);
    for (size_t length = 0; length <= 6; ++length) {
      size_t count = 1;
      for (size_t i = 0; i < length; ++i)
        count *= 4;
      for (size_t word = 0; word < count; ++word) {
        uint8_t text[10];
        size_t value = word;
        uint32_t state = 0;
        for (size_t i = 0; i < length; ++i) {
          text[i] = alphabet[value % 4];
          value /= 4;
          uint32_t next;
          assert(lie_regex_advance(p, state, text[i], &next) == LIE_REGEX_OK);
          state = next;
        }
        bool accepted;
        assert(lie_regex_accepting(p, state, &accepted) == LIE_REGEX_OK);
        assert(accepted == oracle(which, text, length));
        ++checks;
        if (length <= 2)
          for (uint32_t extra = 0; extra <= 3; ++extra) {
            size_t suffixes = 1;
            for (size_t i = 0; i < extra; ++i)
              suffixes *= 4;
            bool possible = false;
            for (size_t suffix = 0; suffix < suffixes; ++suffix) {
              value = suffix;
              for (size_t i = 0; i < extra; ++i) {
                text[length + i] = alphabet[value % 4];
                value /= 4;
              }
              possible |= oracle(which, text, length + extra);
            }
            bool finish;
            assert(lie_regex_can_finish(p, state, extra, extra, &finish) ==
                   LIE_REGEX_OK);
            assert(finish == possible);
            ++checks;
          }
      }
    }
    lie_regex_release(p);
  }
  for (unsigned start = 0; start < 2; ++start)
    for (unsigned previous = 0; previous < 2; ++previous)
      for (unsigned next = 0; next < 2; ++next) {
        bool value;
        assert(lie_regex_nullable(c, boundary, start, previous, next, &value) ==
                   LIE_REGEX_COMPILE_OK &&
               value == (previous != next));
        assert(lie_regex_nullable(c, negative, start, previous, next, &value) ==
                   LIE_REGEX_COMPILE_OK &&
               value == (previous == next));
        assert(lie_regex_nullable(c, base.start, start, previous, next,
                                  &value) == LIE_REGEX_COMPILE_OK &&
               value == (start != 0));
      }
  lie_regex_compiler_release(c);
  return checks;
}
static size_t scalars(void) {
  uint32_t ignored;
  lie_regex_compiler *c = fixture(NULL, &ignored);
  uint32_t root =
      two(c, LIE_REGEX_UNION, chars(c, 0xe9, 0xe9), chars(c, 0x1f600, 0x1f600));
  lie_regex_program *p = NULL;
  assert(lie_regex_seal(c, root, &p) == LIE_REGEX_COMPILE_OK);
  lie_regex_compiler_release(c);
  size_t checks = 0;
  for (uint32_t cp = 0; cp <= 0x10ffff; ++cp) {
    if (cp >= 0xd800 && cp <= 0xdfff)
      continue;
    uint32_t next;
    bool accepted;
    assert(lie_regex_advance(p, 0, cp, &next) == LIE_REGEX_OK);
    assert(lie_regex_accepting(p, next, &accepted) == LIE_REGEX_OK);
    assert(accepted == (cp == 0xe9 || cp == 0x1f600));
    ++checks;
  }
  lie_regex_release(p);
  return checks;
}
static size_t faults(size_t *peak) {
  memory m = {0};
  lie_regex_compiler_description d = description(&m);
  lie_regex_compiler *c = NULL;
  size_t before = m.calls;
  assert(lie_regex_compiler_create(&d, &c) == LIE_REGEX_COMPILE_OK);
  size_t creation = m.calls - before;
  lie_regex_compiler_release(c);
  assert(!m.live);
  for (size_t i = 1; i <= creation; ++i) {
    m.fail_at = m.calls + i;
    c = NULL;
    assert(lie_regex_compiler_create(&d, &c) == LIE_REGEX_COMPILE_RESOURCE &&
           !c && !m.live);
    m.fail_at = 0;
  }
  size_t operations[2] = {0};
  uint32_t root;
  for (unsigned operation = 0; operation < 2; ++operation) {
    c = fixture(&m, &root);
    before = m.calls;
    uint32_t derived = UINT32_MAX;
    lie_regex_program *program = NULL;
    assert((operation ? lie_regex_seal(c, root, &program)
                      : lie_regex_derive(c, root, 'a', true, false,
                                         &derived)) == LIE_REGEX_COMPILE_OK);
    operations[operation] = m.calls - before;
    lie_regex_release(program);
    lie_regex_compiler_release(c);
    assert(!m.live);
    for (size_t i = 1; i <= operations[operation]; ++i) {
      c = fixture(&m, &root);
      m.fail_at = m.calls + i;
      derived = UINT32_MAX;
      program = NULL;
      assert((operation
                  ? lie_regex_seal(c, root, &program)
                  : lie_regex_derive(c, root, 'a', true, false, &derived)) ==
             LIE_REGEX_COMPILE_RESOURCE);
      assert(!program && derived == UINT32_MAX);
      m.fail_at = 0;
      lie_regex_compiler_release(c);
      assert(!m.live && !m.bytes);
    }
  }
  *peak = m.peak;
  return creation + operations[0] + operations[1];
}
static void limits(void) {
  lie_regex_compiler_description d = description(NULL);
  lie_regex_compiler *c = NULL;
  uint32_t out = 123;
  d.max_expressions = 5;
  assert(lie_regex_compiler_create(&d, &c) == LIE_REGEX_COMPILE_OK);
  lie_unicode_range range = {'a', 'a'};
  uint32_t cls;
  assert(lie_regex_class_add(c, &range, 1, &cls) == LIE_REGEX_COMPILE_OK);
  assert(lie_regex_chars(c, cls, &out) == LIE_REGEX_COMPILE_EXPRESSION_LIMIT &&
         out == 123);
  lie_regex_compiler_release(c);
  d = description(NULL);
  d.max_ranges = 2;
  assert(lie_regex_compiler_create(&d, &c) == LIE_REGEX_COMPILE_OK);
  assert(lie_regex_class_add(c, &range, 1, &out) ==
             LIE_REGEX_COMPILE_CLASS_LIMIT &&
         out == 123);
  lie_regex_compiler_release(c);
  d = description(NULL);
  d.max_states = 1;
  assert(lie_regex_compiler_create(&d, &c) == LIE_REGEX_COMPILE_OK);
  uint32_t root = chars(c, 'a', 'a');
  lie_regex_program *p = NULL;
  assert(lie_regex_seal(c, root, &p) == LIE_REGEX_COMPILE_STATE_LIMIT && !p);
  lie_regex_compiler_release(c);
  d = description(NULL);
  d.max_derivatives = 1;
  assert(lie_regex_compiler_create(&d, &c) == LIE_REGEX_COMPILE_OK);
  root =
      two(c, LIE_REGEX_CONCATENATION, chars(c, 'a', 'a'), chars(c, 'b', 'b'));
  assert(lie_regex_derive(c, root, 'a', true, false, &out) ==
             LIE_REGEX_COMPILE_DERIVATIVE_LIMIT &&
         out == 123);
  lie_regex_compiler_release(c);
  d = description(NULL);
  d.max_work = 3;
  c = NULL;
  assert(lie_regex_compiler_create(&d, &c) == LIE_REGEX_COMPILE_WORK_LIMIT &&
         !c);
  d = description(NULL);
  assert(lie_regex_compiler_create(&d, &c) == LIE_REGEX_COMPILE_OK);
  lie_regex_bases base;
  assert(lie_regex_compiler_bases(c, &base) == LIE_REGEX_COMPILE_OK);
  assert(lie_regex_repeat(c, base.any, 2, 1, &out) ==
             LIE_REGEX_COMPILE_REPETITION &&
         out == 123);
  assert(lie_regex_combine(c, (lie_regex_operation)-1, NULL, 0, &out) ==
             LIE_REGEX_COMPILE_INVALID &&
         out == 123);
  assert(lie_regex_derive(c, base.any, 0xd800, false, false, &out) ==
             LIE_REGEX_COMPILE_INVALID &&
         out == 123);
  range = (lie_unicode_range){0xd800, 0xdfff};
  assert(lie_regex_class_add(c, &range, 1, &out) == LIE_REGEX_COMPILE_INVALID &&
         out == 123);
  lie_regex_compiler_release(c);
  d = description(NULL);
  d.maximum_length = 0;
  assert(lie_regex_compiler_create(&d, &c) == LIE_REGEX_COMPILE_OK);
  assert(lie_regex_compiler_bases(c, &base) == LIE_REGEX_COMPILE_OK &&
         base.any == base.empty && base.all == base.epsilon);
  assert(lie_regex_seal(c, base.all, &p) == LIE_REGEX_COMPILE_OK);
  bool accepting;
  assert(lie_regex_accepting(p, 0, &accepting) == LIE_REGEX_OK && accepting);
  uint32_t next;
  assert(lie_regex_advance(p, 0, 'a', &next) == LIE_REGEX_OK &&
         next == LIE_REGEX_DEAD);
  lie_regex_release(p);
  lie_regex_compiler_release(c);
}
static void deep_derivative(void) {
  lie_regex_compiler_description d = description(NULL);
  lie_regex_compiler *c = NULL;
  assert(lie_regex_compiler_create(&d, &c) == LIE_REGEX_COMPILE_OK);
  uint32_t a = chars(c, 'a', 'a'), b = chars(c, 'b', 'b'), root = a;
  // Alternating nodes prevent flattening and create 4096 nested DAG edges.
  // The independent language is always exactly {a}: {a} union (previous & {b}).
  for (size_t i = 0; i < 2048; ++i)
    root = two(c, LIE_REGEX_UNION, a, two(c, LIE_REGEX_INTERSECTION, root, b));
  uint32_t derived;
  bool nullable;
  assert(lie_regex_derive(c, root, 'a', true, false, &derived) ==
         LIE_REGEX_COMPILE_OK);
  assert(lie_regex_nullable(c, derived, false, true, false, &nullable) ==
             LIE_REGEX_COMPILE_OK &&
         nullable);
  assert(lie_regex_derive(c, root, 'b', true, false, &derived) ==
         LIE_REGEX_COMPILE_OK);
  assert(lie_regex_nullable(c, derived, false, true, false, &nullable) ==
             LIE_REGEX_COMPILE_OK &&
         !nullable);
  lie_regex_compiler_release(c);
}
int main(void) {
  size_t finite_checks = finite(), scalar_checks = scalars(), peak = 0,
         refusals = faults(&peak);
  limits();
  deep_derivative();
  printf("REGEX_COMPILER_FINITE=%zu SCALARS=%zu ALLOCATOR_REFUSALS=%zu "
         "FIXTURE_PEAK_BYTES=%zu HOST_NOT_INFERENCE\n",
         finite_checks, scalar_checks, refusals, peak);
}
