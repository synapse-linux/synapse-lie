/* SPDX-License-Identifier: MIT */
/* Signed interval policy adapted from independently pinned MIT Gufo
 * JsonConstraintCompiler::Integer. Exact represented-integer formatting is
 * owned C17; see third_party/gufo-NOTICE for the compiler provenance. */
#include "lie/schema_integer.h"
#include "schema_internal.h"
#include <float.h>
#include <math.h>
#include <string.h>

_Static_assert(sizeof(double) == 8 && DBL_MANT_DIG == 53 && DBL_MAX_EXP == 1024,
               "integer magnitude requires IEEE754 binary64");
#define TRY(call) do { lie_schema_status rc_ = (call); if (rc_) return rc_; } while (0)
typedef struct {
  bool present, negative;
  double rounded;
  char digits[LIE_SCHEMA_INTEGER_TEXT_CAPACITY];
  size_t bytes;
} bound;
static bool overlap(const void *a, size_t na, const void *b, size_t nb) {
  uintptr_t x = (uintptr_t)a, y = (uintptr_t)b;
  return na && nb && (x > UINTPTR_MAX - na || y > UINTPTR_MAX - nb ||
                     (x < y + nb && y < x + na));
}
static lie_schema_status magnitude(double value, char *text, size_t *bytes,
                                   lie_schema_context *context) {
  uint64_t bits;
  memcpy(&bits, &value, sizeof(bits));
  unsigned encoded = (unsigned)((bits >> 52) & 0x7ff);
  uint64_t significand = bits & ((UINT64_C(1) << 52) - 1);
  if (encoded == 0x7ff || (!encoded && significand)) return LIE_SCHEMA_INVALID;
  int exponent = (int)encoded - 1023 - 52;
  if (encoded) significand |= UINT64_C(1) << 52;
  if (significand && exponent < 0) {
    unsigned shift = (unsigned)-exponent;
    if (shift >= 64 || (significand & ((UINT64_C(1) << shift) - 1)))
      return LIE_SCHEMA_INVALID;
    significand >>= shift;
    exponent = 0;
  }
  uint32_t words[32] = {0};
  if (significand) {
    for (unsigned bit = 0; bit < 53; ++bit) {
      unsigned at = bit + (unsigned)exponent;
      if ((significand >> bit) & 1u)
        words[at / 32] |= UINT32_C(1) << (at % 32);
    }
  }
  size_t used = 32, n = 0;
  while (used && !words[used - 1]) --used;
  char reversed[LIE_SCHEMA_INTEGER_TEXT_CAPACITY];
  do {
    if (context) TRY(lie_schema_internal_tick(context, used + 1));
    uint64_t remainder = 0;
    for (size_t i = used; i--;) {
      uint64_t word = (remainder << 32) | words[i];
      words[i] = (uint32_t)(word / 10);
      remainder = word % 10;
    }
    reversed[n++] = (char)('0' + remainder);
    while (used && !words[used - 1]) --used;
  } while (used);
  for (size_t i = 0; i < n; ++i) text[i] = reversed[n - i - 1];
  *bytes = n;
  return LIE_SCHEMA_OK;
}
lie_schema_status lie_schema_integer_magnitude(double value, char *out,
    size_t capacity, size_t *bytes) {
  if (!out || !bytes || overlap(out, capacity, bytes, sizeof(*bytes)))
    return LIE_SCHEMA_INVALID;
  char staged[LIE_SCHEMA_INTEGER_TEXT_CAPACITY];
  size_t n = 0;
  TRY(magnitude(value, staged, &n, NULL));
  if (capacity < n) return LIE_SCHEMA_RESOURCE;
  memcpy(out, staged, n);
  *bytes = n;
  return LIE_SCHEMA_OK;
}
static lie_schema_status finite(lie_schema_context *c, lie_schema_node node,
    const char *key, double *out) {
  lie_schema_value v;
  TRY(lie_schema_internal_describe(c, node, &v));
  if (v.kind != LIE_SCHEMA_NUMBER || !isfinite(v.number)) {
    if (c->error) *c->error = (lie_schema_error){"", {key, strlen(key)}, " must be finite"};
    return LIE_SCHEMA_INVALID;
  }
  *out = v.number;
  return LIE_SCHEMA_OK;
}
static bool zero(const bound *b) { return b->bytes == 1 && b->digits[0] == '0'; }
static lie_schema_status prepare(lie_schema_context *c, lie_schema_node schema,
    const char *exclusive, bool lower, bound *b) {
  if (!b->present) return LIE_SCHEMA_OK;
  b->negative = b->rounded < 0;
  TRY(magnitude(b->rounded, b->digits, &b->bytes, c));
  lie_schema_node excluded = NULL;
  TRY(lie_schema_internal_field(c, schema, exclusive, &excluded));
  if (!excluded) return LIE_SCHEMA_OK;
  double number = 0;
  TRY(finite(c, excluded, exclusive, &number));
  if (number != b->rounded) return LIE_SCHEMA_OK;
  TRY(lie_schema_internal_tick(c, b->bytes));
  if (zero(b)) {
    b->negative = !lower;
    b->digits[0] = '1';
  } else if (lower == b->negative) {
    for (size_t i = b->bytes; i--;) {
      if (b->digits[i] != '0') { --b->digits[i]; break; }
      b->digits[i] = '9';
    }
    if (b->bytes > 1 && b->digits[0] == '0') {
      --b->bytes;
      memmove(b->digits, b->digits + 1, b->bytes);
    }
    if (zero(b)) b->negative = false;
  } else {
    size_t i = b->bytes;
    while (i && b->digits[i - 1] == '9') b->digits[--i] = '0';
    if (i) ++b->digits[i - 1];
    else {
      if (b->bytes == sizeof(b->digits))
        return lie_schema_internal_fail(c, LIE_SCHEMA_INVALID,
                                       "numeric bound cannot be represented");
      memmove(b->digits + 1, b->digits, b->bytes);
      ++b->bytes;
      b->digits[0] = '1';
    }
  }
  return LIE_SCHEMA_OK;
}
static int compare(const bound *a, const bound *b) {
  return a->bytes != b->bytes ? (a->bytes < b->bytes ? -1 : 1)
                              : memcmp(a->digits, b->digits, a->bytes);
}
lie_schema_status lie_schema_integer_compile(
    const lie_schema_transform_description *d, lie_schema_node schema,
    lie_grammar_builder *builder, uint32_t unrestricted, uint32_t *out,
    lie_schema_error *error) {
  if (!lie_schema_internal_valid(d) || !schema || !builder || !out)
    return LIE_SCHEMA_INVALID;
  lie_schema_context c = {d, 0, error};
  bound low = {0}, high = {0};
  const char *keys[] = {"minimum", "exclusiveMinimum", "maximum", "exclusiveMaximum"};
  for (size_t i = 0; i < 4; ++i) {
    lie_schema_node node = NULL;
    TRY(lie_schema_internal_field(&c, schema, keys[i], &node));
    if (!node) continue;
    double value = 0;
    TRY(finite(&c, node, keys[i], &value));
    bool lower = i < 2;
    double rounded = lower ? ceil(value) : floor(value);
    bound *b = lower ? &low : &high;
    if (!b->present || (lower ? rounded > b->rounded : rounded < b->rounded)) {
      b->present = true;
      b->rounded = rounded;
    }
  }
  if (!low.present && !high.present) { *out = unrestricted; return LIE_SCHEMA_OK; }
  TRY(prepare(&c, schema, "exclusiveMinimum", true, &low));
  TRY(prepare(&c, schema, "exclusiveMaximum", false, &high));
  if (low.present && high.present &&
      (low.negative != high.negative ? !low.negative
       : low.negative ? compare(&low, &high) < 0 : compare(&low, &high) > 0))
    return lie_schema_internal_fail(&c, LIE_SCHEMA_EMPTY,
                                   "numeric bounds describe an empty interval");
  uint32_t choices[3], n = 0;
#define BUILD(call) TRY(lie_schema_internal_builder_error((call), error))
  if (!high.present || !high.negative) {
    const bool positive = low.present && !low.negative;
    BUILD(lie_builder_unsigned(builder, positive ? low.digits : "0",
      positive ? low.bytes : 1, high.present ? high.digits : NULL,
      high.present ? high.bytes : 0, &choices[n++]));
  }
  if (!low.present || low.negative) {
    const bool negative = high.present && high.negative;
    uint32_t sequence[] = {LIE_GRAMMAR_TERMINAL | '-', 0};
    BUILD(lie_builder_unsigned(builder, negative ? high.digits : "1",
      negative ? high.bytes : 1, low.present ? low.digits : NULL,
      low.present ? low.bytes : 0, &sequence[1]));
    BUILD(lie_builder_sequence_make(builder, sequence, 2, &choices[n++]));
  }
  if ((!low.present || low.negative || zero(&low)) &&
      (!high.present || !high.negative))
    BUILD(lie_builder_literal(builder, (const uint8_t *)"-0", 2, &choices[n++]));
  uint32_t result = 0;
  BUILD(lie_builder_alternatives(builder, choices, n, &result));
  *out = result;
  return LIE_SCHEMA_OK;
#undef BUILD
}
