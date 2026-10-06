/* SPDX-License-Identifier: MIT */
/* Independent libc decimal and mathematical interval oracles. Synthetic
 * grammar construction only; no model, GPU or performance qualification. */
#include "lie/schema_integer.h"
#include <assert.h>
#include <float.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct node node;
struct node { lie_schema_value value; const char *keys[4]; const node *children[4]; };
typedef struct {
  size_t callbacks, fail_callback, allocations, fail_allocation, live;
} fixture;
static size_t format_oracles, language_oracles, callback_refusals, allocation_refusals;
static lie_schema_status describe(void *p, lie_schema_node n, lie_schema_value *out) {
  fixture *f = p;
  if (++f->callbacks == f->fail_callback) return LIE_SCHEMA_CALLBACK;
  *out = ((const node *)n)->value;
  return LIE_SCHEMA_OK;
}
static lie_schema_status child(void *p, lie_schema_node n, size_t i,
    lie_schema_bytes *key, lie_schema_node *out) {
  fixture *f = p;
  if (++f->callbacks == f->fail_callback) return LIE_SCHEMA_CALLBACK;
  const node *v = n;
  assert(i < v->value.count);
  *key = (lie_schema_bytes){v->keys[i], strlen(v->keys[i])};
  *out = v->children[i];
  return LIE_SCHEMA_OK;
}
static void *allocate(void *p, size_t bytes) {
  fixture *f = p;
  if (++f->allocations == f->fail_allocation) return NULL;
  void *out = malloc(bytes); assert(out); ++f->live; return out;
}
static void release(void *p, void *out) {
  fixture *f = p; assert(f->live && out); --f->live; free(out);
}
static lie_schema_transform_description reader(fixture *f) {
  lie_schema_transform_description d; lie_schema_transform_description_init(&d);
  d.access.context = f; d.access.describe = describe; d.access.child = child;
  d.allocator = (lie_grammar_allocator){f, allocate, release};
  return d;
}
static lie_grammar_builder *builder(fixture *f, uint32_t *integer) {
  lie_builder_description d; lie_builder_description_init(&d);
  d.allocator = (lie_grammar_allocator){f, allocate, release};
  lie_grammar_builder *out = NULL;
  assert(lie_builder_create(&d, &out) == LIE_BUILDER_OK);
  uint32_t digits = 0, nonzero = 0, repeat = 0, positive = 0, sign = 0;
  assert(lie_builder_range(out, '0', '9', &digits) == LIE_BUILDER_OK);
  assert(lie_builder_range(out, '1', '9', &nonzero) == LIE_BUILDER_OK);
  assert(lie_builder_repeat(out, digits, &repeat) == LIE_BUILDER_OK);
  uint32_t sequence[] = {nonzero, repeat};
  assert(lie_builder_sequence_make(out, sequence, 2, &positive) == LIE_BUILDER_OK);
  uint32_t alternatives[] = {LIE_GRAMMAR_TERMINAL | '0', positive};
  assert(lie_builder_alternatives(out, alternatives, 2, &positive) == LIE_BUILDER_OK);
  assert(lie_builder_optional(out, LIE_GRAMMAR_TERMINAL | '-', &sign) == LIE_BUILDER_OK);
  sequence[0] = sign; sequence[1] = positive;
  assert(lie_builder_sequence_make(out, sequence, 2, integer) == LIE_BUILDER_OK);
  f->allocations = 0;
  return out;
}
static void field(node *schema, const char *key, const node *value) {
  size_t i = schema->value.count++;
  assert(i < 4); schema->keys[i] = key; schema->children[i] = value;
}
static node number(double value) {
  node n = {0}; n.value.kind = LIE_SCHEMA_NUMBER; n.value.number = value; return n;
}
static node object(void) { node n = {0}; n.value.kind = LIE_SCHEMA_OBJECT; return n; }
static bool accepts(const lie_grammar_program *p, const char *text) {
  lie_grammar_state *state = NULL;
  assert(lie_grammar_start(p, &state) == LIE_GRAMMAR_OK);
  for (const unsigned char *b = (const unsigned char *)text; *b; ++b) {
    lie_grammar_state *next = NULL;
    assert(lie_grammar_advance(p, state, *b, &next) == LIE_GRAMMAR_OK);
    lie_grammar_state_release(state); state = next;
  }
  bool result = lie_grammar_complete(state);
  lie_grammar_state_release(state); return result;
}
static void formatting(void) {
  /* libc's fixed decimal formatter is independent of production's binary
   * word division. Cover every exponent, signs and several significands. */
  for (unsigned exponent = 0; exponent < 2047; ++exponent)
    for (unsigned choice = 0; choice < 4; ++choice) {
      uint64_t fraction = choice == 0 ? 0 : choice == 1 ? 1 : choice == 2
          ? (UINT64_C(1) << 52) - 1 : UINT64_C(0x7a26e185ca94b);
      uint64_t bits = ((uint64_t)exponent << 52) | fraction;
      double input; memcpy(&input, &bits, sizeof(input)); input = floor(input);
      for (unsigned sign = 0; sign < 2; ++sign) {
        double value = sign ? -input : input;
        char expected[512], actual[512]; memset(actual, 'X', sizeof(actual));
        int n = snprintf(expected, sizeof(expected), "%.0f", fabs(value));
        size_t bytes = SIZE_MAX;
        assert(n > 0 && (size_t)n < sizeof(expected));
        assert(lie_schema_integer_magnitude(value, actual, sizeof(actual), &bytes) == LIE_SCHEMA_OK);
        assert(bytes == (size_t)n && !memcmp(actual, expected, bytes));
        assert(actual[bytes] == 'X'); ++format_oracles;
      }
    }
  char output[512], original[512]; memset(output, 'X', sizeof(output));
  memcpy(original, output, sizeof(output)); size_t bytes = 999;
  const double invalid[] = {0.5, -0.5, DBL_MIN, DBL_TRUE_MIN, NAN, INFINITY, -INFINITY};
  for (size_t i = 0; i < sizeof(invalid) / sizeof(*invalid); ++i) {
    assert(lie_schema_integer_magnitude(invalid[i], output, sizeof(output), &bytes) == LIE_SCHEMA_INVALID);
    assert(bytes == 999 && !memcmp(output, original, sizeof(output))); ++format_oracles;
  }
  assert(lie_schema_integer_magnitude(DBL_MAX, output, 308, &bytes) == LIE_SCHEMA_RESOURCE);
  assert(bytes == 999 && !memcmp(output, original, sizeof(output)));
  union { size_t bytes; char text[512]; } alias;
  memset(&alias, 'X', sizeof(alias)); unsigned char before[sizeof(alias)];
  memcpy(before, &alias, sizeof(alias));
  assert(lie_schema_integer_magnitude(123, alias.text, sizeof(alias.text), &alias.bytes) == LIE_SCHEMA_INVALID);
  assert(!memcmp(before, &alias, sizeof(alias)));
  assert(lie_schema_integer_magnitude(1000000000000000128.0, output, sizeof(output), &bytes) == LIE_SCHEMA_OK);
  assert(bytes == 19 && !memcmp(output, "1000000000000000128", bytes));
}
static void language(void) {
  for (int lo = -7; lo <= 7; ++lo) for (int hi = -7; hi <= 7; ++hi)
    for (unsigned flags = 0; flags < 4; ++flags) {
      fixture f = {0}; uint32_t integer = 0; lie_grammar_builder *b = builder(&f, &integer);
      lie_schema_transform_description d = reader(&f);
      node schema = object(), low = number(lo / 2.0), high = number(hi / 2.0);
      bool exclusive_low = flags & 1, exclusive_high = flags & 2;
      /* Deliberately reverse member order; failure policy keeps keyword order. */
      field(&schema, exclusive_high ? "exclusiveMaximum" : "maximum", &high);
      field(&schema, exclusive_low ? "exclusiveMinimum" : "minimum", &low);
      uint32_t result = UINT32_MAX; lie_schema_error e = {0};
      lie_schema_status rc = lie_schema_integer_compile(&d, &schema, b, integer, &result, &e);
      bool any = false;
      for (int n = -5; n <= 5; ++n)
        any |= (exclusive_low ? n > low.value.number : n >= low.value.number) &&
               (exclusive_high ? n < high.value.number : n <= high.value.number);
      assert(any ? rc == LIE_SCHEMA_OK : rc == LIE_SCHEMA_EMPTY);
      if (!any) assert(result == UINT32_MAX);
      else {
        lie_grammar_description gd;
        assert(lie_builder_finish(b, result, 0, &gd) == LIE_BUILDER_OK);
        lie_grammar_program *p = NULL;
        assert(lie_grammar_program_create(&gd, &p) == LIE_GRAMMAR_OK);
        for (int n = -5; n <= 5; ++n) {
          char text[32]; snprintf(text, sizeof(text), "%d", n);
          bool expected = (exclusive_low ? n > low.value.number : n >= low.value.number) &&
                          (exclusive_high ? n < high.value.number : n <= high.value.number);
          assert(accepts(p, text) == expected); ++language_oracles;
          if (!n) { assert(accepts(p, "-0") == expected); ++language_oracles; }
        }
        assert(!accepts(p, "01") && !accepts(p, "1.0") && !accepts(p, "1e0"));
        lie_grammar_program_release(p);
      }
      lie_builder_release(b); assert(!f.live);
    }
}
static void refusals(void) {
  node schema = object(), low = number(-31.5), high = number(29.5);
  field(&schema, "exclusiveMaximum", &high); field(&schema, "exclusiveMinimum", &low);
  fixture baseline = {0}; uint32_t integer = 0;
  lie_grammar_builder *b = builder(&baseline, &integer);
  lie_schema_transform_description d = reader(&baseline);
  uint32_t result = UINT32_MAX; lie_schema_error e = {0};
  assert(lie_schema_integer_compile(&d, &schema, b, integer, &result, &e) == LIE_SCHEMA_OK);
  size_t calls = baseline.callbacks, allocations = baseline.allocations;
  lie_builder_release(b); assert(!baseline.live && calls && allocations);
  for (size_t i = 1; i <= calls; ++i) {
    fixture f = {0}; b = builder(&f, &integer); d = reader(&f); f.fail_callback = i;
    result = UINT32_MAX;
    assert(lie_schema_integer_compile(&d, &schema, b, integer, &result, &e) == LIE_SCHEMA_CALLBACK);
    assert(result == UINT32_MAX); lie_builder_release(b); assert(!f.live); ++callback_refusals;
  }
  for (size_t i = 1; i <= allocations; ++i) {
    fixture f = {0}; b = builder(&f, &integer); d = reader(&f); f.fail_allocation = i;
    result = UINT32_MAX;
    assert(lie_schema_integer_compile(&d, &schema, b, integer, &result, &e) == LIE_SCHEMA_RESOURCE);
    assert(result == UINT32_MAX); lie_builder_release(b); assert(!f.live); ++allocation_refusals;
  }
  for (unsigned key = 0; key < 4; ++key) for (unsigned kind = 0; kind < 3; ++kind) {
    const char *keys[] = {"minimum", "exclusiveMinimum", "maximum", "exclusiveMaximum"};
    node malformed = object(), value = number(kind == 0 ? NAN : kind == 1 ? INFINITY : 0);
    if (kind == 2) value.value.kind = LIE_SCHEMA_STRING;
    field(&malformed, keys[key], &value);
    fixture f = {0}; b = builder(&f, &integer); d = reader(&f); result = UINT32_MAX;
    assert(lie_schema_integer_compile(&d, &malformed, b, integer, &result, &e) == LIE_SCHEMA_INVALID);
    assert(result == UINT32_MAX && !strcmp(e.suffix, " must be finite"));
    assert(e.detail.size == strlen(keys[key]) && !memcmp(e.detail.data, keys[key], e.detail.size));
    lie_builder_release(b); assert(!f.live);
  }
  fixture f = {0}; b = builder(&f, &integer); d = reader(&f); d.max_work = 1; result = UINT32_MAX;
  assert(lie_schema_integer_compile(&d, &schema, b, integer, &result, &e) == LIE_SCHEMA_WORK_LIMIT);
  assert(result == UINT32_MAX); lie_builder_release(b); assert(!f.live);
}
int main(void) {
  formatting(); language(); refusals();
  printf("C17 signed integer: %zu format, %zu language oracles, %zu callback and %zu allocator refusals; HOST NOT-INFERENCE\n",
         format_oracles, language_oracles, callback_refusals, allocation_refusals);
  return 0;
}
