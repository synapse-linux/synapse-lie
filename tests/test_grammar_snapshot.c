/* SPDX-License-Identifier: MIT */
/* Independent copied snapshot/read/write lifetimes, refusals and overlap. */
#include "lie/grammar.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define COUNT 64u
typedef struct {
  size_t calls, fail_at, live;
} memory;
static void *allocate(void *ctx, size_t bytes) {
  memory *m = ctx;
  if (++m->calls == m->fail_at)
    return NULL;
  void *p = malloc(bytes);
  if (p)
    ++m->live;
  return p;
}
static void release(void *ctx, void *ptr) {
  memory *m = ctx;
  assert(ptr && m->live);
  --m->live;
  free(ptr);
}
typedef struct {
  lie_grammar_frame views[COUNT];
  uint32_t symbols[COUNT][4];
  uint8_t bytes[COUNT][32];
  size_t count, calls, refuse_at;
} source;
typedef struct {
  uint32_t symbols[COUNT][4];
  uint8_t bytes[COUNT][32];
  size_t count, calls, refuse_at;
  bool short_capacity, missing, duplicate, cross_source;
  lie_grammar_frame alias;
} destination;
static lie_grammar_program *program(memory *m, size_t work) {
  static const lie_grammar_range rules[] = {{0, 1}}, sequences[] = {{0, 0}};
  static const uint8_t classes[96] = {0};
  lie_grammar_description d;
  lie_grammar_description_init(&d);
  d.rules = rules;
  d.rule_count = 1;
  d.sequences = sequences;
  d.sequence_count = 1;
  d.classes = classes;
  d.class_count = 3;
  d.limits.max_work = work;
  if (m)
    d.allocator = (lie_grammar_allocator){m, allocate, release};
  lie_grammar_program *p = NULL;
  assert(lie_grammar_program_create(&d, &p) == LIE_GRAMMAR_OK);
  return p;
}
static void fill(source *s, size_t n) {
  memset(s, 0, sizeof(*s));
  s->count = n;
  for (size_t i = 0; i < n; ++i) {
    size_t symbols = i % 5, bytes = i % 33;
    for (size_t j = 0; j < symbols; ++j)
      s->symbols[i][j] = LIE_GRAMMAR_TERMINAL | (uint32_t)((i + j) % 3);
    for (size_t j = 0; j < bytes; ++j)
      s->bytes[i][j] = (uint8_t)(i * 137 + j * 71);
    s->views[i] =
        (lie_grammar_frame){s->symbols[i], symbols, s->bytes[i], bytes};
  }
}
static lie_grammar_status read_frame(const void *ctx, size_t i,
                                     lie_grammar_frame *out) {
  source *s = (source *)ctx;
  assert(i < s->count);
  if (++s->calls == s->refuse_at)
    return LIE_GRAMMAR_RESOURCE;
  *out = s->views[i];
  return LIE_GRAMMAR_OK;
}
static lie_grammar_snapshot_reader reader(source *s) {
  return (lie_grammar_snapshot_reader){LIE_GRAMMAR_SNAPSHOT_ABI,
                                       sizeof(lie_grammar_snapshot_reader), s,
                                       s->count, read_frame};
}
static lie_grammar_status prepare(void *ctx, size_t n) {
  destination *d = ctx;
  assert(n <= COUNT);
  if (++d->calls == d->refuse_at)
    return LIE_GRAMMAR_RESOURCE;
  d->count = n;
  return LIE_GRAMMAR_OK;
}
static lie_grammar_status write_frame(void *ctx, size_t i, size_t symbols,
                                      size_t bytes,
                                      lie_grammar_writable_frame *out) {
  destination *d = ctx;
  assert(i < d->count && symbols <= 4 && bytes <= 32);
  if (++d->calls == d->refuse_at)
    return LIE_GRAMMAR_RESOURCE;
  *out =
      (lie_grammar_writable_frame){d->symbols[i], symbols, d->bytes[i], bytes};
  if (d->short_capacity && symbols)
    --out->symbol_capacity;
  if (d->missing && symbols)
    out->symbols = NULL;
  if (d->duplicate && i == 2)
    out->symbols = d->symbols[1];
  if (d->cross_source && i == 1) {
    out->symbols = (uint32_t *)d->alias.symbols;
    out->symbol_capacity = d->alias.symbol_count;
  }
  return LIE_GRAMMAR_OK;
}
static lie_grammar_snapshot_writer writer(destination *d) {
  return (lie_grammar_snapshot_writer){LIE_GRAMMAR_SNAPSHOT_ABI,
                                       sizeof(lie_grammar_snapshot_writer), d,
                                       prepare, write_frame};
}
static size_t roundtrips(void) {
  lie_grammar_program *p = program(NULL, 2000000);
  size_t checks = 0;
  for (size_t n = 0; n <= COUNT; ++n) {
    source src;
    fill(&src, n);
    lie_grammar_snapshot_reader r = reader(&src);
    lie_grammar_state *s = NULL;
    assert(lie_grammar_state_read(p, &r, &s) == LIE_GRAMMAR_OK);
    uint64_t hash = lie_grammar_state_hash(s);
    destination dst;
    memset(&dst, 0xa5, sizeof(dst));
    dst.calls = dst.refuse_at = 0;
    dst.short_capacity = dst.missing = dst.duplicate = dst.cross_source = false;
    lie_grammar_snapshot_writer w = writer(&dst);
    assert(lie_grammar_state_write(s, &w) == LIE_GRAMMAR_OK && dst.count == n);
    for (size_t i = 0; i < n; ++i) {
      lie_grammar_frame f;
      assert(lie_grammar_state_frame(s, i, &f) == LIE_GRAMMAR_OK);
      assert(f.symbol_count == src.views[i].symbol_count &&
             f.lexeme_bytes == src.views[i].lexeme_bytes);
      assert(!memcmp(dst.symbols[i], src.symbols[i],
                     f.symbol_count * sizeof(uint32_t)));
      assert(!memcmp(dst.bytes[i], src.bytes[i], f.lexeme_bytes));
      memset(src.symbols[i], 0, sizeof(src.symbols[i]));
      memset(src.bytes[i], 0, sizeof(src.bytes[i]));
      if (f.symbol_count)
        assert(!memcmp(dst.symbols[i], f.symbols,
                       f.symbol_count * sizeof(uint32_t)));
      if (f.lexeme_bytes)
        assert(!memcmp(dst.bytes[i], f.lexeme, f.lexeme_bytes));
      ++checks;
    }
    assert(lie_grammar_state_hash(s) == hash);
    lie_grammar_state_release(s);
  }
  lie_grammar_program_release(p);
  return checks;
}
static void refusals(void) {
  lie_grammar_program *p = program(NULL, 2000000);
  source src;
  fill(&src, 8);
  lie_grammar_snapshot_reader r = reader(&src);
  lie_grammar_state *s = (void *)(uintptr_t)1;
  r.abi_version = 0;
  assert(lie_grammar_state_read(p, &r, &s) == LIE_GRAMMAR_INVALID &&
         s == (void *)(uintptr_t)1);
  r = reader(&src);
  r.count = 8193;
  assert(lie_grammar_state_read(p, &r, &s) == LIE_GRAMMAR_STATE_LIMIT);
  r = reader(&src);
  r.frame = NULL;
  assert(lie_grammar_state_read(p, &r, &s) == LIE_GRAMMAR_INVALID);
  r = reader(&src);
  src.views[2].symbols = NULL;
  assert(lie_grammar_state_read(p, &r, &s) == LIE_GRAMMAR_INVALID &&
         s == (void *)(uintptr_t)1);
  fill(&src, 8);
  r = reader(&src);
  assert(lie_grammar_state_read(p, &r, &s) == LIE_GRAMMAR_OK);
  uint64_t hash = lie_grammar_state_hash(s);
  for (unsigned kind = 0; kind < 4; ++kind) {
    destination d = {0};
    memset(d.symbols, 0xa5, sizeof(d.symbols));
    memset(d.bytes, 0xa5, sizeof(d.bytes));
    d.short_capacity = kind == 0;
    d.missing = kind == 1;
    d.duplicate = kind == 2;
    d.cross_source = kind == 3;
    assert(lie_grammar_state_frame(s, 3, &d.alias) == LIE_GRAMMAR_OK);
    lie_grammar_snapshot_writer w = writer(&d);
    assert(lie_grammar_state_write(s, &w) == LIE_GRAMMAR_INVALID);
    for (size_t i = 0; i < sizeof(d.symbols); ++i)
      assert(((uint8_t *)d.symbols)[i] == 0xa5);
    for (size_t i = 0; i < sizeof(d.bytes); ++i)
      assert(((uint8_t *)d.bytes)[i] == 0xa5);
    assert(lie_grammar_state_hash(s) == hash);
  }
  for (size_t fail = 1; fail <= 9; ++fail) {
    destination d = {.refuse_at = fail};
    lie_grammar_snapshot_writer w = writer(&d);
    assert(lie_grammar_state_write(s, &w) == LIE_GRAMMAR_RESOURCE &&
           lie_grammar_state_hash(s) == hash);
  }
  destination d = {0};
  lie_grammar_snapshot_writer w = writer(&d);
  w.struct_bytes = 0;
  assert(lie_grammar_state_write(s, &w) == LIE_GRAMMAR_INVALID && !d.calls);
  lie_grammar_state_release(s);
  lie_grammar_program_release(p);
  p = program(NULL, 1);
  fill(&src, 8);
  r = reader(&src);
  assert(lie_grammar_state_read(p, &r, &s) == LIE_GRAMMAR_OK);
  w = writer(&d);
  assert(lie_grammar_state_write(s, &w) == LIE_GRAMMAR_WORK_LIMIT);
  lie_grammar_state_release(s);
  lie_grammar_program_release(p);
  p = program(NULL, 2000000);
  fill(&src, 8);
  for (size_t fail = 1; fail <= 8; ++fail) {
    src.calls = 0;
    src.refuse_at = fail;
    r = reader(&src);
    s = (void *)(uintptr_t)1;
    assert(lie_grammar_state_read(p, &r, &s) == LIE_GRAMMAR_RESOURCE &&
           s == (void *)(uintptr_t)1);
  }
  lie_grammar_program_release(p);
}
typedef struct {
  uint32_t *symbols;
  uint8_t *bytes;
} maximum_output;
static lie_grammar_status repeated_frame(const void *ctx, size_t i,
                                         lie_grammar_frame *out) {
  (void)i;
  *out = *(const lie_grammar_frame *)ctx;
  return LIE_GRAMMAR_OK;
}
static lie_grammar_status maximum_prepare(void *ctx, size_t n) {
  (void)ctx;
  assert(n == 8192);
  return LIE_GRAMMAR_OK;
}
static lie_grammar_status maximum_frame(void *ctx, size_t i, size_t n,
                                        size_t bytes,
                                        lie_grammar_writable_frame *out) {
  maximum_output *d = ctx;
  assert(n == 2 && bytes == 5 && i < 8192);
  *out =
      (lie_grammar_writable_frame){d->symbols + 2 * i, 2, d->bytes + 5 * i, 5};
  return LIE_GRAMMAR_OK;
}
static void maximum(void) {
  lie_grammar_program *p = program(NULL, 2000000);
  uint32_t symbols[] = {LIE_GRAMMAR_TERMINAL, LIE_GRAMMAR_TERMINAL | 2};
  uint8_t bytes[] = {0, 0xff, 0x80, 1, 0};
  lie_grammar_frame f = {symbols, 2, bytes, 5};
  lie_grammar_snapshot_reader r = {LIE_GRAMMAR_SNAPSHOT_ABI, sizeof(r), &f,
                                   8192, repeated_frame};
  lie_grammar_state *state = NULL;
  assert(lie_grammar_state_read(p, &r, &state) == LIE_GRAMMAR_OK);
  maximum_output d = {malloc(8192 * 2 * sizeof(uint32_t)), malloc(8192 * 5)};
  assert(d.symbols && d.bytes);
  lie_grammar_snapshot_writer w = {LIE_GRAMMAR_SNAPSHOT_ABI, sizeof(w), &d,
                                   maximum_prepare, maximum_frame};
  assert(lie_grammar_state_write(state, &w) == LIE_GRAMMAR_OK);
  for (size_t i = 0; i < 8192; ++i) {
    assert(!memcmp(d.symbols + 2 * i, symbols, sizeof(symbols)));
    assert(!memcmp(d.bytes + 5 * i, bytes, sizeof(bytes)));
  }
  free(d.symbols);
  free(d.bytes);
  lie_grammar_state_release(state);
  lie_grammar_program_release(p);
}
static size_t faults(void) {
  memory m = {0};
  lie_grammar_program *p = program(&m, 2000000);
  source src;
  fill(&src, 32);
  lie_grammar_snapshot_reader r = reader(&src);
  size_t baseline = m.calls;
  lie_grammar_state *s = NULL;
  assert(lie_grammar_state_read(p, &r, &s) == LIE_GRAMMAR_OK);
  size_t calls = m.calls - baseline;
  lie_grammar_state_release(s);
  for (size_t fail = 1; fail <= calls; ++fail) {
    m.fail_at = m.calls + fail;
    s = (void *)(uintptr_t)1;
    assert(lie_grammar_state_read(p, &r, &s) == LIE_GRAMMAR_RESOURCE &&
           s == (void *)(uintptr_t)1 && m.live == 2);
  }
  m.fail_at = 0;
  assert(lie_grammar_state_read(p, &r, &s) == LIE_GRAMMAR_OK);
  destination d = {0};
  lie_grammar_snapshot_writer w = writer(&d);
  m.fail_at = m.calls + 1;
  assert(lie_grammar_state_write(s, &w) == LIE_GRAMMAR_RESOURCE && !d.calls);
  ++calls;
  lie_grammar_state_release(s);
  lie_grammar_program_release(p);
  assert(!m.live);
  return calls;
}
static size_t duplicate_lifetimes(void) {
  size_t copied_frames = 0;
  for (size_t n = 0; n <= COUNT; ++n) {
    memory m = {0};
    lie_grammar_program *p = program(&m, 2000000);
    source src;
    fill(&src, n);
    lie_grammar_snapshot_reader r = reader(&src);
    lie_grammar_state *original = NULL, *copy = NULL;
    assert(lie_grammar_state_read(p, &r, &original) == LIE_GRAMMAR_OK);
    const uint64_t hash = lie_grammar_state_hash(original);
    lie_grammar_program_release(p); /* Copies require no live program. */
    assert(lie_grammar_state_duplicate(original, &copy) == LIE_GRAMMAR_OK);
    assert(copy != original && lie_grammar_state_compare(copy, original) == 0 &&
           lie_grammar_state_hash(copy) == hash);
    for (size_t i = 0; i < n; ++i) {
      lie_grammar_frame a, b;
      assert(lie_grammar_state_frame(original, i, &a) == LIE_GRAMMAR_OK);
      assert(lie_grammar_state_frame(copy, i, &b) == LIE_GRAMMAR_OK);
      assert(a.symbol_count == b.symbol_count && a.lexeme_bytes == b.lexeme_bytes);
      if (a.symbol_count) assert(a.symbols != b.symbols);
      if (a.lexeme_bytes) assert(a.lexeme != b.lexeme);
      ++copied_frames;
    }
    memset(&src, 0xa5, sizeof(src));
    lie_grammar_state_release(original);
    assert(lie_grammar_state_hash(copy) == hash);
    lie_grammar_state *third = NULL;
    assert(lie_grammar_state_duplicate(copy, &third) == LIE_GRAMMAR_OK);
    lie_grammar_state_release(copy);
    assert(lie_grammar_state_hash(third) == hash);
    lie_grammar_state_release(third);
    assert(!m.live);
  }
  return copied_frames;
}
static size_t duplicate_refusals(void) {
  memory m = {0};
  lie_grammar_program *p = program(&m, 2000000);
  source src;
  fill(&src, COUNT);
  lie_grammar_snapshot_reader r = reader(&src);
  lie_grammar_state *input = NULL, *output = NULL;
  assert(lie_grammar_state_read(p, &r, &input) == LIE_GRAMMAR_OK);
  lie_grammar_program_release(p);
  const uint64_t hash = lie_grammar_state_hash(input);
  size_t baseline = m.calls, live = m.live;
  assert(lie_grammar_state_duplicate(input, &output) == LIE_GRAMMAR_OK);
  const size_t allocations = m.calls - baseline;
  lie_grammar_state_release(output);
  assert(m.live == live);
  for (size_t fail = 1; fail <= allocations; ++fail) {
    m.fail_at = m.calls + fail;
    output = (void *)(uintptr_t)1;
    assert(lie_grammar_state_duplicate(input, &output) == LIE_GRAMMAR_RESOURCE &&
           output == (void *)(uintptr_t)1 && m.live == live &&
           lie_grammar_state_hash(input) == hash);
  }
  m.fail_at = 0;
  output = (void *)(uintptr_t)1;
  assert(lie_grammar_state_duplicate(NULL, &output) == LIE_GRAMMAR_INVALID &&
         output == (void *)(uintptr_t)1);
  assert(lie_grammar_state_duplicate(input, NULL) == LIE_GRAMMAR_INVALID &&
         m.live == live);
  lie_grammar_state_release(input);
  assert(!m.live);
  return allocations;
}
int main(void) {
  size_t count = roundtrips();
  refusals();
  maximum();
  size_t refused = faults();
  const size_t copied = duplicate_lifetimes(), copy_refusals = duplicate_refusals();
  printf("SNAPSHOT_FRAME_ORACLES=%zu OWN_ALLOCATOR_REFUSALS=%zu "
         "STAGING_REFUSALS=17 OVERLAP_CASES=4 MAX_FRAMES=8192 "
         "HOST_NOT_INFERENCE\n",
         count, refused);
  printf("C17_REQUEST_SNAPSHOT copied_frame_oracles=%zu copy_allocator_refusals=%zu "
         "PROGRAM_RETIRED_INPUT_RETIRED_OUTPUT_INDEPENDENT HOST_NOT_INFERENCE\n",
         copied, copy_refusals);
}
