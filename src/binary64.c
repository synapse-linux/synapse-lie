/* SPDX-License-Identifier: MIT */
/* First-party format policy and exact long-decimal parser. */
/* Ryu shortest/short parsing code below retains its upstream dual license;
 * LIE selects BSL-1.0. See third_party/ryu-source.json and upstream notices. */
#include "lie/binary64.h"
#include <float.h>
#include <stdbool.h>
#include <string.h>
#define d2s_buffered_n lie_ryu_d2s_buffered_n
#define d2s_buffered lie_ryu_d2s_buffered
#define d2s lie_ryu_d2s
#define s2d_n lie_ryu_s2d_n
#define s2d lie_ryu_s2d
#include "../third_party/ryu/ryu/d2s.c"
#include "../third_party/ryu/ryu/s2d.c"
_Static_assert(sizeof(double) == 8 && DBL_MANT_DIG == 53 && DBL_MAX_EXP == 1024,
               "binary64 codec requires IEEE754 binary64");
#define SIGN (UINT64_C(1) << 63)
#define FRACTION ((UINT64_C(1) << 52) - 1)
#define EXPONENT (UINT64_C(0x7ff) << 52)
#define DIGITS 800u
#define WORDS 128u
typedef struct { uint32_t v[WORDS]; size_t n; } integer;
typedef struct { size_t used, limit; } budget;
static bool tick(budget *b, size_t n) {
  if (n > b->limit - b->used) return false;
  b->used += n; return true;
}
static uint64_t bits(double value) { uint64_t u; memcpy(&u, &value, 8); return u; }
static double value(uint64_t u) { double d; memcpy(&d, &u, 8); return d; }
static bool overlap(const void *a, size_t na, const void *b, size_t nb) {
  uintptr_t x = (uintptr_t)a, y = (uintptr_t)b;
  return na && nb && (x > UINTPTR_MAX - na || y > UINTPTR_MAX - nb ||
                     (x < y + nb && y < x + na));
}
void lie_binary64_limits_init(lie_binary64_limits *p) {
  if (p) *p = (lie_binary64_limits){LIE_BINARY64_ABI, sizeof(*p), UINT32_MAX, 64000000};
}
static size_t decimal_integer(uint64_t u, char *out) {
  uint32_t words[3] = {0};
  uint64_t mantissa = (u & FRACTION) | (UINT64_C(1) << 52);
  int exponent = (int)((u & EXPONENT) >> 52) - 1023 - 52;
  if (exponent < 0) { mantissa >>= (unsigned)-exponent; exponent = 0; }
  words[0] = (uint32_t)mantissa; words[1] = (uint32_t)(mantissa >> 32);
  while (exponent--) {
    uint32_t carry = 0;
    for (size_t i = 0; i < 3; ++i) {
      uint32_t next = words[i] >> 31; words[i] = (words[i] << 1) | carry; carry = next;
    }
  }
  char reversed[32]; size_t n = 0;
  do {
    uint64_t rem = 0;
    for (size_t i = 3; i--;) {
      uint64_t word = (rem << 32) | words[i];
      words[i] = (uint32_t)(word / 10); rem = word % 10;
    }
    reversed[n++] = (char)('0' + rem);
  } while (words[0] || words[1] || words[2]);
  for (size_t i = 0; i < n; ++i) out[i] = reversed[n - i - 1];
  return n;
}
lie_binary64_status lie_binary64_format(double input, char *out, size_t capacity,
                                       size_t *length) {
  uint64_t u = bits(input);
  if (!out || !length || (u & EXPONENT) == EXPONENT ||
      overlap(out, capacity, length, sizeof(*length))) return LIE_BINARY64_INVALID;
  char scientific[32], digits[24], staged[64];
  int raw = lie_ryu_d2s_buffered_n(input, scientific);
  bool negative = (u & SIGN) != 0; size_t at = negative ? 1 : 0, count = 0;
  while (at < (size_t)raw && scientific[at] != 'E') {
    if (scientific[at] != '.') digits[count++] = scientific[at];
    ++at;
  }
  ++at; bool exponent_negative = scientific[at] == '-';
  if (exponent_negative) ++at;
  int exponent = 0;
  while (at < (size_t)raw) exponent = exponent * 10 + scientific[at++] - '0';
  if (exponent_negative) exponent = -exponent;
  size_t exp_digits = exponent >= 100 || exponent <= -100 ? 3 : 2;
  size_t scientific_size = count + (count > 1) + 2 + exp_digits;
  size_t fixed_size = exponent < 0 ? count + 1 + (size_t)-exponent
      : (size_t)exponent + 1 >= count ? (size_t)exponent + 1 : count + 1;
  size_t n = 0;
  if (negative) staged[n++] = '-';
  if (fixed_size <= scientific_size) {
    if (exponent >= (int)count) n += decimal_integer(u, staged + n);
    else if (exponent < 0) {
      staged[n++] = '0'; staged[n++] = '.';
      for (int i = -1; i > exponent; --i) staged[n++] = '0';
      memcpy(staged + n, digits, count); n += count;
    } else {
      for (size_t i = 0; i < count; ++i) {
        if (i == (size_t)exponent + 1) staged[n++] = '.';
        staged[n++] = digits[i];
      }
    }
  } else {
    staged[n++] = digits[0];
    if (count > 1) { staged[n++] = '.'; memcpy(staged + n, digits + 1, count - 1); n += count - 1; }
    staged[n++] = 'e'; staged[n++] = exponent < 0 ? '-' : '+';
    unsigned e = (unsigned)(exponent < 0 ? -exponent : exponent);
    if (exp_digits == 3) staged[n++] = (char)('0' + e / 100);
    staged[n++] = (char)('0' + e / 10 % 10); staged[n++] = (char)('0' + e % 10);
  }
  if (n > capacity) return LIE_BINARY64_CAPACITY;
  memcpy(out, staged, n); *length = n; return LIE_BINARY64_OK;
}
static bool digit(char c) { return c >= '0' && c <= '9'; }
static bool whitespace(char c) { return c == ' ' || c == '\t' || c == '\n' || c == '\r'; }
static void trim(integer *a) { while (a->n && !a->v[a->n - 1]) --a->n; }
static bool multiply(integer *a, unsigned factor, unsigned add, budget *b) {
  if (!tick(b, a->n + 1)) return false;
  uint64_t carry = add;
  for (size_t i = 0; i < a->n; ++i) {
    uint64_t v = (uint64_t)a->v[i] * factor + carry;
    a->v[i] = (uint32_t)v; carry = v >> 32;
  }
  if (carry) { if (a->n == WORDS) return false; a->v[a->n++] = (uint32_t)carry; }
  return true;
}
static size_t bit_length(const integer *a) {
  if (!a->n) return 0;
  uint32_t v = a->v[a->n - 1]; unsigned n = 0;
  while (v) { v >>= 1; ++n; }
  return (a->n - 1) * 32 + n;
}
static uint32_t shifted_word(const integer *a, size_t at, size_t shift) {
  size_t offset = shift / 32; unsigned bit = (unsigned)(shift % 32);
  if (at < offset) return 0;
  size_t index = at - offset;
  uint32_t word = index < a->n ? a->v[index] << bit : 0;
  if (bit && index && index - 1 < a->n) word |= a->v[index - 1] >> (32 - bit);
  return word;
}
static bool compare(const integer *a, size_t sa, const integer *b, size_t sb,
                    budget *work, int *out) {
  size_t abits = bit_length(a) + sa, bbits = bit_length(b) + sb;
  if (!a->n) abits = 0;
  if (!b->n) bbits = 0;
  if (abits != bbits) { *out = abits < bbits ? -1 : 1; return tick(work, 1); }
  size_t n = (abits + 31) / 32;
  if (!tick(work, n + 1)) return false;
  for (size_t i = n; i--;) {
    uint32_t x = shifted_word(a, i, sa), y = shifted_word(b, i, sb);
    if (x != y) { *out = x < y ? -1 : 1; return true; }
  }
  *out = 0; return true;
}
static bool shift(integer *a, size_t bits, budget *b) {
  if (!a->n || !bits) return true;
  size_t length = bit_length(a) + bits, n = (length + 31) / 32;
  if (n > WORDS || !tick(b, n)) return false;
  for (size_t i = n; i--;) a->v[i] = shifted_word(a, i, bits);
  a->n = n; return true;
}
static bool subtract(integer *a, const integer *d, size_t bits, budget *b) {
  if (!tick(b, a->n)) return false;
  uint64_t borrow = 0;
  for (size_t i = 0; i < a->n; ++i) {
    uint64_t sub = (uint64_t)shifted_word(d, i, bits) + borrow;
    uint32_t x = a->v[i]; a->v[i] = (uint32_t)((uint64_t)x - sub);
    borrow = (uint64_t)x < sub;
  }
  trim(a); return !borrow;
}
static lie_binary64_status exact(const char *digits, size_t count, int exponent,
    bool sticky, bool negative, budget *work, double *out) {
  integer numerator = {{0}, 0}, denominator = {{1}, 1};
  for (size_t i = 0; i < count; ++i)
    if (!multiply(&numerator, 10, (unsigned)(digits[i] - '0'), work)) return LIE_BINARY64_WORK_LIMIT;
  integer *powered = exponent >= 0 ? &numerator : &denominator;
  unsigned power = (unsigned)(exponent >= 0 ? exponent : -exponent);
  for (unsigned i = 0; i < power; ++i)
    if (!multiply(powered, 5, 0, work)) return LIE_BINARY64_WORK_LIMIT;
  int ratio = (int)bit_length(&numerator) - (int)bit_length(&denominator), order;
  int cmp = 0;
  if (!compare(&numerator, ratio < 0 ? (size_t)-ratio : 0,
               &denominator, ratio > 0 ? (size_t)ratio : 0, work, &cmp)) return LIE_BINARY64_WORK_LIMIT;
  if (cmp < 0) --ratio;
  order = ratio + exponent;
  if (order > 1023) return LIE_BINARY64_RANGE;
  int scale = order < -1022 ? 1074 : 52 - order, move = exponent + scale;
  if (!shift(move >= 0 ? &numerator : &denominator,
             (size_t)(move >= 0 ? move : -move), work)) return LIE_BINARY64_WORK_LIMIT;
  int delta = (int)bit_length(&numerator) - (int)bit_length(&denominator);
  uint64_t mantissa = 0;
  for (int bit = delta; bit >= 0; --bit) {
    if (bit >= 64) return LIE_BINARY64_INVALID;
    if (!compare(&numerator, 0, &denominator, (size_t)bit, work, &cmp)) return LIE_BINARY64_WORK_LIMIT;
    if (cmp >= 0) {
      if (!subtract(&numerator, &denominator, (size_t)bit, work)) return LIE_BINARY64_WORK_LIMIT;
      mantissa |= UINT64_C(1) << bit;
    }
  }
  if (!compare(&numerator, 1, &denominator, 0, work, &cmp)) return LIE_BINARY64_WORK_LIMIT;
  if (cmp > 0 || (cmp == 0 && (sticky || (mantissa & 1)))) ++mantissa;
  uint64_t u;
  if (order < -1022) u = mantissa;
  else {
    if (mantissa == (UINT64_C(1) << 53)) { mantissa >>= 1; ++order; }
    if (order > 1023) return LIE_BINARY64_RANGE;
    u = ((uint64_t)(order + 1023) << 52) | (mantissa & FRACTION);
  }
  if (!u) return LIE_BINARY64_RANGE;
  *out = value(u | (negative ? SIGN : 0)); return LIE_BINARY64_OK;
}
lie_binary64_status lie_binary64_parse(const char *text, size_t bytes,
    const lie_binary64_limits *limits, double *out) {
  lie_binary64_limits defaults; lie_binary64_limits_init(&defaults);
  const lie_binary64_limits *l = limits ? limits : &defaults;
  if (!text || !bytes || !out || l->abi_version != LIE_BINARY64_ABI ||
      l->struct_bytes != sizeof(*l) || !l->max_work || !l->max_text_bytes ||
      l->max_text_bytes > UINT32_MAX ||
      overlap(text, bytes, out, sizeof(*out)) ||
      overlap(l, sizeof(*l), out, sizeof(*out))) return LIE_BINARY64_INVALID;
  if (bytes > l->max_text_bytes) return LIE_BINARY64_TEXT_LIMIT;
  if (bytes > l->max_work) return LIE_BINARY64_WORK_LIMIT;
  budget work = {bytes, l->max_work};
  size_t first = 0, end = bytes;
  while (first < end && whitespace(text[first])) ++first;
  while (end > first && whitespace(text[end - 1])) --end;
  bool negative = first < end && text[first] == '-';
  size_t at = first + negative, begin = at;
  if (at == end) return LIE_BINARY64_INVALID;
  if (text[at] == '0') { ++at; if (at < end && digit(text[at])) return LIE_BINARY64_INVALID; }
  else if (text[at] >= '1' && text[at] <= '9') { do { ++at; } while (at < end && digit(text[at])); }
  else return LIE_BINARY64_INVALID;
  size_t fraction = 0;
  if (at < end && text[at] == '.') {
    size_t start = ++at;
    while (at < end && digit(text[at])) ++at;
    fraction = at - start; if (!fraction) return LIE_BINARY64_INVALID;
  }
  size_t digits_end = at; int64_t explicit_exponent = 0;
  if (at < end && (text[at] == 'e' || text[at] == 'E')) {
    ++at; bool minus = at < end && text[at] == '-';
    if (at < end && (minus || text[at] == '+')) ++at;
    size_t start = at;
    while (at < end && digit(text[at])) {
      if (explicit_exponent <= INT64_MAX / 10 - 10)
        explicit_exponent = explicit_exponent * 10 + text[at] - '0';
      else explicit_exponent = INT64_MAX / 4;
      ++at;
    }
    if (at == start) return LIE_BINARY64_INVALID;
    if (minus) explicit_exponent = -explicit_exponent;
  }
  if (at != end) return LIE_BINARY64_INVALID;
  char significant[DIGITS]; size_t count = 0, total = 0; bool started = false, sticky = false;
  if (!tick(&work, digits_end - begin)) return LIE_BINARY64_WORK_LIMIT;
  for (size_t i = begin; i < digits_end; ++i) {
    if (text[i] == '.') continue;
    if (!started && text[i] == '0') continue;
    started = true; ++total;
    if (count < DIGITS) significant[count++] = text[i]; else sticky |= text[i] != '0';
  }
  if (!started) { *out = value(negative ? SIGN : 0); return LIE_BINARY64_OK; }
  int64_t decimal = explicit_exponent - (int64_t)fraction + (int64_t)total - 1;
  if (decimal > 308 || decimal < -324) return LIE_BINARY64_RANGE;
  int exponent = (int)decimal - (int)count + 1;
  while (count > 1 && significant[count - 1] == '0') { --count; ++exponent; }
  double result = 0;
  if (count <= 17 && !sticky) {
    char compact[32]; size_t n = 0;
    if (negative) compact[n++] = '-';
    memcpy(compact + n, significant, count); n += count; compact[n++] = 'e';
    unsigned e = (unsigned)(exponent < 0 ? -exponent : exponent);
    if (exponent < 0) compact[n++] = '-';
    char reversed[8]; size_t k = 0;
    do { reversed[k++] = (char)('0' + e % 10); e /= 10; } while (e);
    while (k) compact[n++] = reversed[--k];
    if (lie_ryu_s2d_n(compact, (int)n, &result) != SUCCESS) return LIE_BINARY64_INVALID;
    uint64_t u = bits(result);
    if ((u & EXPONENT) == EXPONENT || !(u & ~SIGN)) return LIE_BINARY64_RANGE;
  } else {
    lie_binary64_status rc = exact(significant, count, exponent, sticky, negative, &work, &result);
    if (rc != LIE_BINARY64_OK) return rc;
  }
  *out = result; return LIE_BINARY64_OK;
}
