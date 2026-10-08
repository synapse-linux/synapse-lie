/* SPDX-License-Identifier: MIT */
/* Independent finite-language parser and allocator/callback lifetime oracles.
 */
/* Synthetic Unicode-set fixture, not a property database or model inference. */
#include "lie/grammar_regex_parse.h"
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define RANGES 64u
typedef struct {
  lie_unicode_range r[RANGES];
  size_t n;
} set;
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
typedef struct {
  memory mem;
  lie_regex_compiler *compiler;
  set classes[128];
  size_t count;
} fixture;
static lie_regex_compile_status add_range(void *ctx, void *dst, int32_t lo,
                                          int32_t hi) {
  (void)ctx;
  set *s = dst;
  if (lo < 0 || hi < lo)
    return LIE_REGEX_COMPILE_OK;
  set result = {0};
  lie_unicode_range added = {(uint32_t)lo, (uint32_t)hi};
  bool inserted = false;
  for (size_t i = 0; i < s->n + 1; ++i) {
    lie_unicode_range r;
    if (!inserted && (i == s->n || added.first < s->r[i].first)) {
      r = added;
      inserted = true;
    } else {
      size_t index = i - (inserted ? 1 : 0);
      r = s->r[index];
    }
    if (result.n && r.first <= result.r[result.n - 1].last + 1) {
      if (r.last > result.r[result.n - 1].last)
        result.r[result.n - 1].last = r.last;
    } else {
      if (result.n == RANGES)
        return LIE_REGEX_COMPILE_RESOURCE;
      result.r[result.n++] = r;
    }
  }
  *s = result;
  return LIE_REGEX_COMPILE_OK;
}
static lie_regex_compile_status make_range(void *ctx, int32_t lo, int32_t hi,
                                           void **out) {
  fixture *f = ctx;
  set *s = allocate(&f->mem, sizeof(*s));
  if (!s)
    return LIE_REGEX_COMPILE_RESOURCE;
  *s = (set){0};
  lie_regex_compile_status rc = add_range(ctx, s, lo, hi);
  if (rc != LIE_REGEX_COMPILE_OK) {
    release(&f->mem, s);
    return rc;
  }
  *out = s;
  return LIE_REGEX_COMPILE_OK;
}
static lie_regex_compile_status add(void *ctx, void *dst, const void *src) {
  set result = *(set *)dst;
  const set *s = src;
  for (size_t i = 0; i < s->n; ++i) {
    lie_regex_compile_status rc =
        add_range(ctx, &result, (int32_t)s->r[i].first, (int32_t)s->r[i].last);
    if (rc != LIE_REGEX_COMPILE_OK)
      return rc;
  }
  *(set *)dst = result;
  return LIE_REGEX_COMPILE_OK;
}
static lie_regex_compile_status remove_range(void *ctx, void *dst, int32_t lo,
                                             int32_t hi) {
  (void)ctx;
  const set *s = dst;
  set result = {0};
  for (size_t i = 0; i < s->n; ++i) {
    lie_unicode_range r = s->r[i];
    if (r.last < (uint32_t)lo || r.first > (uint32_t)hi) {
      if (result.n == RANGES)
        return LIE_REGEX_COMPILE_RESOURCE;
      result.r[result.n++] = r;
    } else {
      if (r.first < (uint32_t)lo) {
        if (result.n == RANGES)
          return LIE_REGEX_COMPILE_RESOURCE;
        result.r[result.n++] = (lie_unicode_range){r.first, (uint32_t)lo - 1};
      }
      if (r.last > (uint32_t)hi) {
        if (result.n == RANGES)
          return LIE_REGEX_COMPILE_RESOURCE;
        result.r[result.n++] = (lie_unicode_range){(uint32_t)hi + 1, r.last};
      }
    }
  }
  *(set *)dst = result;
  return LIE_REGEX_COMPILE_OK;
}
static lie_regex_compile_status complement(void *ctx, void *dst) {
  (void)ctx;
  set result = {0};
  const set *s = dst;
  uint32_t next = 0;
  for (size_t i = 0; i < s->n; ++i) {
    if (s->r[i].first > next) {
      if (result.n == RANGES)
        return LIE_REGEX_COMPILE_RESOURCE;
      result.r[result.n++] = (lie_unicode_range){next, s->r[i].first - 1};
    }
    next = s->r[i].last + 1;
  }
  if (next <= 0x10ffff) {
    if (result.n == RANGES)
      return LIE_REGEX_COMPILE_RESOURCE;
    result.r[result.n++] = (lie_unicode_range){next, 0x10ffff};
  }
  *(set *)dst = result;
  return LIE_REGEX_COMPILE_OK;
}
static lie_regex_compile_status property(void *ctx, const char *p, size_t n,
                                         void **out) {
  set *s = NULL;
  lie_regex_compile_status rc = make_range(ctx, 1, 0, (void **)&s);
  if (rc != LIE_REGEX_COMPILE_OK)
    return rc;
  if (n == 5 && !memcmp(p, "[0-9]", 5))
    rc = add_range(ctx, s, '0', '9');
  else if (n == 12 && !memcmp(p, "[a-zA-Z0-9_]", 12)) {
    rc = add_range(ctx, s, 'a', 'z');
    if (rc == LIE_REGEX_COMPILE_OK)
      rc = add_range(ctx, s, 'A', 'Z');
    if (rc == LIE_REGEX_COMPILE_OK)
      rc = add_range(ctx, s, '0', '9');
    if (rc == LIE_REGEX_COMPILE_OK)
      rc = add_range(ctx, s, '_', '_');
  } else
    rc = LIE_REGEX_COMPILE_INVALID;
  if (rc != LIE_REGEX_COMPILE_OK) {
    release(&((fixture *)ctx)->mem, s);
    return rc;
  }
  *out = s;
  return LIE_REGEX_COMPILE_OK;
}
static lie_regex_compile_status info(void *ctx, const void *src, uint64_t *size,
                                     int32_t *first) {
  (void)ctx;
  const set *s = src;
  uint64_t n = 0;
  for (size_t i = 0; i < s->n; ++i)
    n += s->r[i].last - s->r[i].first + 1;
  *size = n;
  *first = s->n ? (int32_t)s->r[0].first : -1;
  return LIE_REGEX_COMPILE_OK;
}
static lie_regex_compile_status publish(void *ctx, const void *src,
                                        uint32_t *out) {
  fixture *f = ctx;
  set s = *(const set *)src;
  lie_regex_compile_status rc = remove_range(ctx, &s, 0xd800, 0xdfff);
  if (rc != LIE_REGEX_COMPILE_OK)
    return rc;
  lie_regex_bases b;
  assert(lie_regex_compiler_bases(f->compiler, &b) == LIE_REGEX_COMPILE_OK);
  if (!s.n) {
    *out = b.empty;
    return LIE_REGEX_COMPILE_OK;
  }
  size_t index = 0;
  for (; index < f->count; ++index)
    if (s.n == f->classes[index].n &&
        !memcmp(s.r, f->classes[index].r, s.n * sizeof(*s.r)))
      break;
  if (index == f->count) {
    if (f->count == 128)
      return LIE_REGEX_COMPILE_RESOURCE;
    uint32_t copied;
    rc = lie_regex_class_add(f->compiler, s.r, s.n, &copied);
    if (rc != LIE_REGEX_COMPILE_OK)
      return rc;
    assert(copied == index);
    f->classes[f->count++] = s;
  }
  return lie_regex_chars(f->compiler, (uint32_t)index, out);
}
static lie_regex_compile_status boundary(void *ctx, bool positive,
                                         uint32_t *out) {
  set words = {0};
  assert(add_range(ctx, &words, 'a', 'z') == LIE_REGEX_COMPILE_OK);
  assert(add_range(ctx, &words, 'A', 'Z') == LIE_REGEX_COMPILE_OK);
  assert(add_range(ctx, &words, '0', '9') == LIE_REGEX_COMPILE_OK);
  assert(add_range(ctx, &words, '_', '_') == LIE_REGEX_COMPILE_OK);
  uint32_t ignored;
  lie_regex_compile_status rc = publish(ctx, &words, &ignored);
  return rc == LIE_REGEX_COMPILE_OK
             ? lie_regex_boundary(((fixture *)ctx)->compiler, positive, out)
             : rc;
}
static void set_release(void *ctx, void *p) {
  release(&((fixture *)ctx)->mem, p);
}
static lie_regex_unicode_sets hooks(fixture *f) {
  return (lie_regex_unicode_sets){f,         make_range,   property,   add,
                                  add_range, remove_range, complement, info,
                                  publish,   boundary,     set_release};
}
static void start(fixture *f) {
  lie_regex_compiler_description d;
  lie_regex_compiler_description_init(&d);
  d.maximum_length = 16;
  d.allocator = (lie_grammar_allocator){&f->mem, allocate, release};
  assert(lie_regex_compiler_create(&d, &f->compiler) == LIE_REGEX_COMPILE_OK);
  f->count = 1;
  f->classes[0] = (set){.r = {{0, 0xd7ff}, {0xe000, 0x10ffff}}, .n = 2};
}
static void stop(fixture *f) {
  lie_regex_compiler_release(f->compiler);
  f->compiler = NULL;
  assert(!f->mem.live && !f->mem.bytes);
}
static lie_regex_parse_status parse(fixture *f, const char *text,
                                    const lie_regex_parser_description *d,
                                    uint32_t *out) {
  size_t n = strlen(text);
  assert(n <= 16384);
  uint16_t units[16384];
  for (size_t i = 0; i < n; ++i)
    units[i] = (uint8_t)text[i];
  lie_regex_unicode_sets sets = hooks(f);
  lie_regex_parse_error error;
  return lie_regex_parse_utf16(f->compiler, units, n, n, &sets, d, out, &error);
}
static bool oracle(unsigned which, const uint8_t *p, size_t n) {
  bool a = true, ab = true;
  for (size_t i = 0; i < n; ++i) {
    a &= p[i] == 'a';
    ab &= p[i] == 'a' || p[i] == 'b';
  }
  switch (which) {
  case 0:
    return n >= 1 && n <= 3 && ab;
  case 1:
    return n <= 4 && a;
  case 2:
    return n >= 2 && p[0] == 'a' && p[1] == 'b';
  case 3:
    return !(n == 2 && p[0] == 'a' && p[1] == 'a');
  case 4:
    return n > 0 && p[0] != '?' && p[n - 1] != '?';
  case 5:
    return !n || (p[0] == '?' && p[n - 1] == '?');
  case 6:
    return n == 1 && p[0] == 'a';
  case 7:
    return n == 1 && p[0] == '?';
  case 8:
    return n == 1 && (p[0] == 'a' || p[0] == 'b');
  default:
    return !n;
  }
}
static size_t languages(void) {
  const char *patterns[] = {
      "^[ab]{1,3}$", "^(a?){2,4}$", "^(?=ab)a.*$",         "^(?!aa$).*$",
      "^\\b.*\\b$",  "^\\B.*\\B$",  "^(?:\\b|\\B){1,3}a$", "^[^a-b]$",
      "^\\w$",       "^[]*$"};
  const uint8_t alphabet[] = {'a', 'b', '?'};
  size_t checks = 0;
  for (unsigned which = 0; which < sizeof(patterns) / sizeof(*patterns);
       ++which) {
    fixture f = {0};
    start(&f);
    lie_regex_parser_description d;
    lie_regex_parser_description_init(&d);
    uint32_t root;
    assert(parse(&f, patterns[which], &d, &root) == LIE_REGEX_PARSE_OK);
    lie_regex_program *p = NULL;
    assert(lie_regex_seal(f.compiler, root, &p) == LIE_REGEX_COMPILE_OK);
    lie_regex_compiler_release(f.compiler);
    f.compiler = NULL;
    for (size_t n = 0; n <= 6; ++n) {
      size_t count = 1;
      for (size_t i = 0; i < n; ++i)
        count *= 3;
      for (size_t value = 0; value < count; ++value) {
        uint8_t text[6];
        size_t v = value;
        uint32_t state = 0;
        for (size_t i = 0; i < n; ++i) {
          text[i] = alphabet[v % 3];
          v /= 3;
          uint32_t next;
          assert(lie_regex_advance(p, state, text[i], &next) == LIE_REGEX_OK);
          state = next;
        }
        bool result;
        assert(lie_regex_accepting(p, state, &result) == LIE_REGEX_OK);
        assert(result == oracle(which, text, n));
        ++checks;
      }
    }
    lie_regex_release(p);
    assert(!f.mem.live && !f.mem.bytes);
  }
  return checks;
}
static size_t faults(size_t *peak) {
  fixture f = {0};
  start(&f);
  lie_regex_parser_description d;
  lie_regex_parser_description_init(&d);
  d.allocator = (lie_grammar_allocator){&f.mem, allocate, release};
  const char *pattern = "^(?=a|b)[a-b\\w]{1,3}(?!c)$";
  uint32_t out = 123;
  size_t before = f.mem.calls;
  assert(parse(&f, pattern, &d, &out) == LIE_REGEX_PARSE_OK);
  size_t points = f.mem.calls - before;
  *peak = f.mem.peak;
  stop(&f);
  for (size_t i = 1; i <= points; ++i) {
    fixture q = {0};
    start(&q);
    d.allocator = (lie_grammar_allocator){&q.mem, allocate, release};
    q.mem.fail_at = q.mem.calls + i;
    out = 123;
    assert(parse(&q, pattern, &d, &out) == LIE_REGEX_PARSE_RESOURCE &&
           out == 123);
    q.mem.fail_at = 0;
    stop(&q);
  }
  return points;
}
static void refusals(void) {
  const struct {
    const char *text;
    lie_regex_parse_status status;
  } cases[] = {{"[", LIE_REGEX_PARSE_TRUNCATED},
               {"(", LIE_REGEX_PARSE_TRUNCATED},
               {")", LIE_REGEX_PARSE_PARENTHESES},
               {"(?<=a)b", LIE_REGEX_PARSE_GROUP},
               {"\\1", LIE_REGEX_PARSE_ESCAPE},
               {"\\01", LIE_REGEX_PARSE_OCTAL},
               {"\\c0", LIE_REGEX_PARSE_CONTROL},
               {"\\uZZZZ", LIE_REGEX_PARSE_HEX},
               {"\\u{}", LIE_REGEX_PARSE_EMPTY_CODEPOINT},
               {"\\u{110000}", LIE_REGEX_PARSE_CODEPOINT},
               {"\\uD800a", LIE_REGEX_PARSE_SURROGATE},
               {"\\pL", LIE_REGEX_PARSE_PROPERTY_BRACES},
               {"\\p{bad}", LIE_REGEX_PARSE_PROPERTY},
               {"[b-a]", LIE_REGEX_PARSE_RANGE},
               {"[\\w-a]", LIE_REGEX_PARSE_RANGE},
               {"*a", LIE_REGEX_PARSE_NO_ATOM},
               {"a{4,2}", LIE_REGEX_PARSE_REPETITION},
               {"a{4294967295}", LIE_REGEX_PARSE_REPETITION_LARGE},
               {"(?:\\b)*", LIE_REGEX_PARSE_ASSERTION_REPEAT}};
  fixture f = {0};
  start(&f);
  lie_regex_parser_description d;
  lie_regex_parser_description_init(&d);
  for (size_t i = 0; i < sizeof(cases) / sizeof(*cases); ++i) {
    uint32_t out = 123;
    assert(parse(&f, cases[i].text, &d, &out) == cases[i].status && out == 123);
  }
  uint32_t out = 123;
  d.max_work = 1;
  assert(parse(&f, "ab", &d, &out) == LIE_REGEX_PARSE_WORK_LIMIT && out == 123);
  lie_regex_parser_description_init(&d);
  d.max_nodes = 1;
  assert(parse(&f, "a", &d, &out) == LIE_REGEX_PARSE_NODE_LIMIT && out == 123);
  lie_regex_parser_description_init(&d);
  d.abi_version = 99;
  assert(parse(&f, "a", &d, &out) == LIE_REGEX_PARSE_INVALID && out == 123);
  lie_regex_parser_description_init(&d);
  lie_regex_unicode_sets sets = hooks(&f);
  lie_regex_parse_error error;
  assert(lie_regex_parse_utf16(f.compiler, NULL, 0, 16385, &sets, &d, &out,
                               &error) == LIE_REGEX_PARSE_BYTES &&
         out == 123);
  uint16_t nul[] = {0};
  assert(lie_regex_parse_utf16(f.compiler, nul, 1, 1, &sets, &d, &out,
                               &error) == LIE_REGEX_PARSE_OK);
  uint16_t escaped_nul[] = {'\\', 0};
  out = 123;
  assert(lie_regex_parse_utf16(f.compiler, escaped_nul, 2, 2, &sets, &d, &out,
                               &error) == LIE_REGEX_PARSE_ESCAPE &&
         out == 123);
  uint16_t supplementary[] = {'^', 0xd83d, 0xde00, '$'};
  assert(lie_regex_parse_utf16(f.compiler, supplementary, 4, 6, &sets, &d, &out,
                               &error) == LIE_REGEX_PARSE_OK);
  lie_regex_program *program = NULL;
  assert(lie_regex_seal(f.compiler, out, &program) == LIE_REGEX_COMPILE_OK);
  uint32_t next;
  bool accepted;
  assert(lie_regex_advance(program, 0, 0x1f600, &next) == LIE_REGEX_OK);
  assert(lie_regex_accepting(program, next, &accepted) == LIE_REGEX_OK &&
         accepted);
  lie_regex_release(program);
  stop(&f);
}
int main(void) {
  size_t checks = languages(), peak = 0, points = faults(&peak);
  refusals();
  printf("REGEX_PARSER_LANGUAGES=%zu ALLOCATOR_REFUSALS=%zu "
         "FIXTURE_PEAK_BYTES=%zu HOST_NOT_INFERENCE\n",
         checks, points, peak);
}
