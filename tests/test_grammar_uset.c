/* SPDX-License-Identifier: MIT */
/* Real ICU C API, copied registry/input lifetimes and own allocation refusals.
 * Synthetic host checks only; ICU internal allocation faults are not injected.
 */
#include "lie/grammar_unicode.h"
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
  if (++m->calls == m->fail_at)
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
static lie_grammar_unicode_description description(memory *m) {
  lie_grammar_unicode_description d;
  lie_grammar_unicode_description_init(&d);
  d.compiler.allocator = (lie_grammar_allocator){m, allocate, release};
  return d;
}
static bool accepts(lie_regex_program *p, const uint32_t *text, size_t n) {
  uint32_t state = 0;
  for (size_t i = 0; i < n; ++i) {
    uint32_t next;
    assert(lie_regex_advance(p, state, text[i], &next) == LIE_REGEX_OK);
    state = next;
  }
  bool result;
  assert(lie_regex_accepting(p, state, &result) == LIE_REGEX_OK);
  return result;
}
static void decoding(void) {
  const char text[] = {'a',        0,          (char)0xf0, (char)0x9f,
                       (char)0x98, (char)0x80, (char)0xc0, (char)0x80};
  uint16_t dst[16] = {0};
  size_t n = 999;
  assert(lie_grammar_utf8_to_utf16(text, sizeof(text), dst, 16, &n) ==
         LIE_REGEX_COMPILE_OK);
  const uint16_t expected[] = {'a', 0, 0xd83d, 0xde00, 0xfffd, 0xfffd};
  assert(n == 6 && !memcmp(dst, expected, sizeof(expected)));
  memset(dst, 0x55, sizeof(dst));
  n = 999;
  uint16_t saved[16];
  memcpy(saved, dst, sizeof(dst));
  assert(lie_grammar_utf8_to_utf16(text, sizeof(text), dst, 1, &n) ==
         LIE_REGEX_COMPILE_RESOURCE);
  assert(n == 999 && !memcmp(dst, saved, sizeof(dst)));
  assert(lie_grammar_utf8_to_utf16(NULL, 1, dst, 16, &n) ==
         LIE_REGEX_COMPILE_INVALID);
  assert(lie_grammar_utf8_to_utf16(text, 16385, dst, 16, &n) ==
         LIE_REGEX_COMPILE_INVALID);
  assert(lie_grammar_utf8_to_utf16(text, sizeof(text), dst, 16386, &n) ==
         LIE_REGEX_COMPILE_INVALID);
  assert(lie_grammar_utf8_to_utf16((char *)dst, 1, dst, 16, &n) ==
         LIE_REGEX_COMPILE_INVALID);
  union {
    size_t length;
    uint16_t units[16];
  } alias;
  alias.length = 999;
  assert(lie_grammar_utf8_to_utf16("x", 1, alias.units, 16, &alias.length) ==
         LIE_REGEX_COMPILE_INVALID);
  assert(alias.length == 999);
  assert(lie_grammar_utf8_to_utf16(NULL, 0, NULL, 0, &n) ==
             LIE_REGEX_COMPILE_OK &&
         n == 0);
  assert(lie_grammar_utf8_to_utf16("x", 1, dst, 1, &n) ==
             LIE_REGEX_COMPILE_OK &&
         n == 1 && dst[0] == 'x');
  char *limit = malloc(16384);
  uint16_t *units = malloc(16384 * sizeof(*units));
  assert(limit && units);
  memset(limit, 'a', 16384);
  assert(lie_grammar_utf8_to_utf16(limit, 16384, units, 16384, &n) ==
             LIE_REGEX_COMPILE_OK &&
         n == 16384);
  for (size_t i = 0; i < n; ++i)
    assert(units[i] == 'a');
  free(limit);
  free(units);
}
static void identity(void) {
  memory m = {0};
  lie_grammar_unicode_description d = description(&m);
  lie_grammar_unicode *c = NULL;
  assert(lie_grammar_unicode_create(&d, &c) == LIE_REGEX_COMPILE_OK);
  lie_regex_unicode_sets h;
  assert(lie_grammar_unicode_sets(c, &h) == LIE_REGEX_COMPILE_OK);
  lie_regex_compiler *compiler = lie_grammar_unicode_compiler(c);
  lie_regex_bases b;
  assert(lie_regex_compiler_bases(compiler, &b) == LIE_REGEX_COMPILE_OK);
  void *a = NULL, *ab = NULL, *abc = NULL, *surrogate = NULL;
  assert(h.range(h.context, 'a', 'a', &a) == LIE_REGEX_COMPILE_OK);
  uint32_t plain, copy, with_string, another;
  assert(h.publish(h.context, a, &plain) == LIE_REGEX_COMPILE_OK);
  assert(h.add_range(h.context, a, 'b', 'b') == LIE_REGEX_COMPILE_OK);
  assert(h.property(h.context, "[a{bc}]", 7, &ab) == LIE_REGEX_COMPILE_OK);
  assert(h.property(h.context, "[a{bd}]", 7, &abc) == LIE_REGEX_COMPILE_OK);
  assert(h.publish(h.context, ab, &with_string) == LIE_REGEX_COMPILE_OK);
  assert(h.publish(h.context, abc, &another) == LIE_REGEX_COMPILE_OK);
  assert(plain != with_string && plain != another && with_string != another);
  assert(h.remove_range(h.context, a, 'b', 'b') == LIE_REGEX_COMPILE_OK);
  assert(h.publish(h.context, a, &copy) == LIE_REGEX_COMPILE_OK &&
         copy == plain);
  assert(h.range(h.context, 0xd800, 0xdfff, &surrogate) ==
         LIE_REGEX_COMPILE_OK);
  assert(h.publish(h.context, surrogate, &copy) == LIE_REGEX_COMPILE_OK &&
         copy == b.empty);
  assert(h.property(h.context, "[{xy}]", 6, &surrogate) ==
         LIE_REGEX_COMPILE_OK);
  assert(h.publish(h.context, surrogate, &copy) == LIE_REGEX_COMPILE_OK &&
         copy != b.empty);
  uint64_t size;
  int32_t first;
  assert(h.info(h.context, surrogate, &size, &first) == LIE_REGEX_COMPILE_OK &&
         size == 1 && first == -1);
  lie_regex_program *p = NULL;
  assert(lie_regex_seal(compiler, plain, &p) == LIE_REGEX_COMPILE_OK);
  /* Release intentionally leaves outstanding handles for context cleanup. */
  lie_grammar_unicode_release(c);
  uint32_t aa = 'a', bb = 'b';
  assert(accepts(p, &aa, 1) && !accepts(p, &bb, 1));
  lie_regex_release(p);
  assert(!m.live && !m.bytes);
}
static size_t languages(void) {
  const char *patterns[] = {"^\\p{L}$",
                            "^\\P{L}$",
                            "^.$",
                            "^é😀$",
                            "^[\\u{d800}-\\u{dfff}]$",
                            "^\\b[a-z]{1,3}\\b$"};
  uint32_t scalars[] = {0,    10,    'a',    'Z',    '0',    '_',
                        0xe9, 0x391, 0x2028, 0xd800, 0xe000, 0x1f600};
  size_t checks = 0;
  for (size_t i = 0; i < sizeof(patterns) / sizeof(*patterns); ++i) {
    memory m = {0};
    lie_grammar_unicode_description d = description(&m);
    lie_grammar_unicode *c = NULL;
    assert(lie_grammar_unicode_create(&d, &c) == LIE_REGEX_COMPILE_OK);
    lie_regex_parser_description pd;
    lie_regex_parser_description_init(&pd);
    uint32_t root;
    lie_regex_parse_error error;
    assert(lie_grammar_unicode_parse(c, patterns[i], strlen(patterns[i]), &pd,
                                     &root, &error) == LIE_REGEX_PARSE_OK);
    lie_regex_program *p = NULL;
    assert(lie_regex_seal(lie_grammar_unicode_compiler(c), root, &p) ==
           LIE_REGEX_COMPILE_OK);
    lie_grammar_unicode_release(c);
    for (size_t j = 0; j < sizeof(scalars) / sizeof(*scalars); ++j) {
      uint32_t cp = scalars[j];
      bool letter = cp == 'a' || cp == 'Z' || cp == 0xe9 || cp == 0x391;
      bool scalar = cp < 0xd800 || cp > 0xdfff;
      bool expected = i == 0   ? letter
                      : i == 1 ? scalar && !letter
                      : i == 2 ? scalar && cp != 10 && cp != 0x2028
                      : i == 5 ? cp == 'a'
                               : false;
      assert(accepts(p, &cp, 1) == expected);
      ++checks;
    }
    uint32_t pair[] = {0xe9, 0x1f600};
    assert(accepts(p, pair, 2) == (i == 3));
    ++checks;
    uint32_t word[] = {'a', 'b'};
    assert(accepts(p, word, 2) == (i == 5));
    ++checks;
    lie_regex_release(p);
    assert(!m.live && !m.bytes);
  }
  return checks;
}
static size_t fault_pass(size_t fail_at, size_t *peak) {
  memory m = {.fail_at = fail_at};
  lie_grammar_unicode_description d = description(&m);
  lie_grammar_unicode *c = (lie_grammar_unicode *)(uintptr_t)1;
  lie_regex_compile_status rc = lie_grammar_unicode_create(&d, &c);
  if (rc == LIE_REGEX_COMPILE_OK) {
    lie_regex_parser_description pd;
    lie_regex_parser_description_init(&pd);
    pd.allocator = d.compiler.allocator;
    for (int32_t cp = 'A'; rc == LIE_REGEX_COMPILE_OK && cp < 'M'; ++cp) {
      lie_regex_unicode_sets h;
      assert(lie_grammar_unicode_sets(c, &h) == LIE_REGEX_COMPILE_OK);
      void *s = NULL;
      rc = h.range(h.context, cp, cp, &s);
      uint32_t published = UINT32_MAX;
      if (rc == LIE_REGEX_COMPILE_OK)
        rc = h.publish(h.context, s, &published);
      if (s)
        h.release(h.context, s);
      if (rc != LIE_REGEX_COMPILE_OK)
        assert(rc == LIE_REGEX_COMPILE_RESOURCE && published == UINT32_MAX);
    }
    const char *pattern = "^(?:\\p{L}|[a-z0-9_]){1,3}\\b(?=é|a).*$";
    uint32_t root = UINT32_MAX;
    lie_regex_parse_error error;
    lie_regex_parse_status parsed =
        rc == LIE_REGEX_COMPILE_OK
            ? lie_grammar_unicode_parse(c, pattern, strlen(pattern), &pd, &root,
                                        &error)
            : LIE_REGEX_PARSE_RESOURCE;
    if (parsed == LIE_REGEX_PARSE_OK) {
      assert(root != UINT32_MAX);
      assert(!fail_at);
    } else {
      assert(parsed == LIE_REGEX_PARSE_RESOURCE ||
             (parsed == LIE_REGEX_PARSE_COMPILER &&
              error.compiler_status == LIE_REGEX_COMPILE_RESOURCE));
      assert(root == UINT32_MAX);
    }
    lie_grammar_unicode_release(c);
  } else {
    assert(rc == LIE_REGEX_COMPILE_RESOURCE &&
           c == (lie_grammar_unicode *)(uintptr_t)1);
  }
  assert(!m.live && !m.bytes);
  if (peak)
    *peak = m.peak;
  return m.calls;
}
static void refusals(void) {
  lie_grammar_unicode_description d;
  lie_grammar_unicode_description_init(&d);
  lie_grammar_unicode *c = (lie_grammar_unicode *)(uintptr_t)1;
  d.abi_version = 0;
  assert(lie_grammar_unicode_create(&d, &c) == LIE_REGEX_COMPILE_INVALID &&
         c == (lie_grammar_unicode *)(uintptr_t)1);
  lie_grammar_unicode_description_init(&d);
  d.max_classes = 0;
  assert(lie_grammar_unicode_create(&d, &c) == LIE_REGEX_COMPILE_INVALID);
  lie_grammar_unicode_description_init(&d);
  d.compiler.allocator.allocate = allocate;
  assert(lie_grammar_unicode_create(&d, &c) == LIE_REGEX_COMPILE_INVALID);
  lie_grammar_unicode_description_init(&d);
  d.max_classes = 1;
  assert(lie_grammar_unicode_create(&d, &c) == LIE_REGEX_COMPILE_OK);
  lie_regex_unicode_sets h;
  assert(lie_grammar_unicode_sets(c, &h) == LIE_REGEX_COMPILE_OK);
  void *a = NULL;
  assert(h.range(h.context, 'a', 'a', &a) == LIE_REGEX_COMPILE_OK);
  uint32_t root = UINT32_MAX;
  assert(h.publish(h.context, a, &root) == LIE_REGEX_COMPILE_CLASS_LIMIT &&
         root == UINT32_MAX);
  h.release(h.context, a);
  lie_regex_parser_description pd;
  lie_regex_parser_description_init(&pd);
  lie_regex_parse_error error;
  assert(lie_grammar_unicode_parse(c, "x", 16385, &pd, &root, &error) ==
             LIE_REGEX_PARSE_BYTES &&
         root == UINT32_MAX);
  assert(lie_grammar_unicode_parse(NULL, "x", 1, &pd, &root, &error) ==
         LIE_REGEX_PARSE_INVALID);
  assert(h.property(h.context, "[:NoSuchProperty:]", 18, &a) ==
         LIE_REGEX_COMPILE_INVALID);
  lie_grammar_unicode_release(c);
  lie_grammar_unicode_description_init(&d);
  assert(lie_grammar_unicode_create(&d, &c) == LIE_REGEX_COMPILE_OK);
  const char *unpaired = "^[\\uD800-\\uDFFF]$";
  root = UINT32_MAX;
  assert(lie_grammar_unicode_parse(c, unpaired, strlen(unpaired), &pd, &root,
                                   &error) == LIE_REGEX_PARSE_SURROGATE &&
         root == UINT32_MAX);
  lie_grammar_unicode_release(c);
  char icu[32], unicode[32];
  assert(lie_grammar_unicode_versions(icu, sizeof(icu), unicode,
                                      sizeof(unicode)) == LIE_REGEX_COMPILE_OK);
  assert(*icu && *unicode);
  assert(lie_grammar_unicode_versions(icu, 1, unicode, sizeof(unicode)) ==
         LIE_REGEX_COMPILE_INVALID);
  assert(lie_grammar_unicode_versions(icu, sizeof(icu), icu, sizeof(icu)) ==
         LIE_REGEX_COMPILE_INVALID);
}
int main(void) {
  decoding();
  identity();
  refusals();
  size_t count = languages(), peak;
  size_t calls = fault_pass(0, &peak);
  for (size_t i = 1; i <= calls; ++i)
    fault_pass(i, NULL);
  printf("UNICODE_SET_LANGUAGES=%zu OWN_ALLOCATOR_REFUSALS=%zu "
         "OWN_FIXTURE_PEAK_BYTES=%zu ICU_INTERNAL_FAULTS_UNQUALIFIED "
         "HOST_NOT_INFERENCE\n",
         count, calls, peak);
}
