/* SPDX-License-Identifier: MIT */
/* Copyright (c) 2026 gufo contributors. */
/* Attributed construction/fixed-point port from official Gufo f783fedb. */
#include "lie/grammar_builder.h"
#include <stdlib.h>
#include <string.h>
#define LEAF (LIE_GRAMMAR_TERMINAL | LIE_GRAMMAR_LEXEME)
#define DIGITS 512u
typedef struct { lie_builder_sequence *sequences; size_t count, symbols; } rule;
struct lie_grammar_builder {
  lie_builder_description d;
  lie_builder_status status;
  rule *rules;
  size_t count, capacity, sequences, symbols, classes, class_capacity, work;
  uint8_t *bits;
  void *tables;
  bool sealed, json;
  lie_builder_primitives primitives;
  uint32_t generic[17];
  char zeros[DIGITS], nines[DIGITS];
};
static void *ordinary_allocate(void *ctx, size_t bytes) { (void)ctx; return malloc(bytes); }
static void ordinary_release(void *ctx, void *p) { (void)ctx; free(p); }
void lie_builder_description_init(lie_builder_description *d) {
  if (d) *d = (lie_builder_description){LIE_GRAMMAR_BUILDER_ABI, sizeof(*d),
    262144, UINT32_MAX, UINT32_MAX, LIE_GRAMMAR_LEXEME - 1, 64000000, {0}};
}
static lie_builder_status refuse(lie_grammar_builder *b, lie_builder_status rc) {
  if (b && b->status == LIE_BUILDER_OK && !b->sealed) b->status = rc;
  return rc;
}
static bool spend(lie_grammar_builder *b, size_t n) {
  if (b->status != LIE_BUILDER_OK) return false;
  if (n > b->d.max_work - b->work) { refuse(b, LIE_BUILDER_WORK_LIMIT); return false; }
  b->work += n; return true;
}
static bool mutable(lie_grammar_builder *b) {
  return b && !b->sealed && b->status == LIE_BUILDER_OK;
}
static lie_builder_status unavailable(lie_grammar_builder *b) {
  return b && !b->sealed ? b->status : LIE_BUILDER_INVALID;
}
static void retire(lie_grammar_builder *b, void *p) {
  if (p) b->d.allocator.release(b->d.allocator.context, p);
}
lie_builder_status lie_builder_create(const lie_builder_description *d, lie_grammar_builder **out) {
  if (!d || !out || d->abi_version != LIE_GRAMMAR_BUILDER_ABI ||
      d->struct_bytes != sizeof(*d) || !d->max_rules || d->max_rules > 262144 ||
      !d->max_sequences || d->max_sequences > UINT32_MAX ||
      !d->max_symbols || d->max_symbols > UINT32_MAX ||
      d->max_classes < 256 || d->max_classes >= LIE_GRAMMAR_LEXEME ||
      !d->max_work || (!!d->allocator.allocate != !!d->allocator.release)) return LIE_BUILDER_INVALID;
  lie_grammar_allocator a = d->allocator;
  if (!a.allocate) a = (lie_grammar_allocator){NULL, ordinary_allocate, ordinary_release};
  lie_grammar_builder *b = a.allocate(a.context, sizeof(*b));
  if (!b) return LIE_BUILDER_RESOURCE;
  *b = (lie_grammar_builder){.d = *d}; b->d.allocator = a;
  b->bits = a.allocate(a.context, 256 * 32);
  if (!b->bits) { a.release(a.context, b); return LIE_BUILDER_RESOURCE; }
  memset(b->bits, 0, 256 * 32);
  for (unsigned i = 0; i < 256; ++i) b->bits[i * 32 + i / 8] = (uint8_t)(1u << (i % 8));
  b->classes = b->class_capacity = 256;
  for (size_t i = 0; i < 17; ++i) b->generic[i] = UINT32_MAX;
  memset(b->zeros, '0', sizeof(b->zeros)); memset(b->nines, '9', sizeof(b->nines));
  *out = b; return LIE_BUILDER_OK;
}
void lie_builder_release(lie_grammar_builder *b) {
  if (!b) return;
  for (size_t i = 0; i < b->count; ++i) retire(b, b->rules[i].sequences);
  retire(b, b->rules); retire(b, b->bits); retire(b, b->tables);
  b->d.allocator.release(b->d.allocator.context, b);
}
static bool reserve_rules(lie_grammar_builder *b) {
  if (b->count < b->capacity) return true;
  size_t capacity = b->capacity ? b->capacity * 2 : 16;
  if (capacity > b->d.max_rules) capacity = b->d.max_rules;
  rule *p = b->d.allocator.allocate(b->d.allocator.context, capacity * sizeof(*p));
  if (!p) { refuse(b, LIE_BUILDER_RESOURCE); return false; }
  if (b->count) memcpy(p, b->rules, b->count * sizeof(*p));
  retire(b, b->rules); b->rules = p; b->capacity = capacity; return true;
}
static bool store_rule(lie_grammar_builder *b, uint32_t id,
  const lie_builder_sequence *source, size_t count, bool fresh) {
  if (!mutable(b)) return false;
  if ((count && !source) || count > b->d.max_sequences) { refuse(b, LIE_BUILDER_INVALID); return false; }
  if (fresh && b->count == b->d.max_rules) { refuse(b, LIE_BUILDER_RULE_LIMIT); return false; }
  size_t symbols = 0;
  for (size_t i = 0; i < count; ++i) {
    if ((source[i].count && !source[i].symbols) || source[i].count > b->d.max_symbols - symbols) {
      refuse(b, LIE_BUILDER_TABLE_LIMIT); return false;
    }
    symbols += source[i].count;
  }
  rule old = fresh ? (rule){0} : b->rules[id];
  if (count > b->d.max_sequences - (b->sequences - old.count) ||
      symbols > b->d.max_symbols - (b->symbols - old.symbols)) {
    refuse(b, LIE_BUILDER_TABLE_LIMIT); return false;
  }
  if (count > SIZE_MAX / sizeof(lie_builder_sequence) ||
      symbols > (SIZE_MAX - count * sizeof(lie_builder_sequence)) / sizeof(uint32_t)) {
    refuse(b, LIE_BUILDER_RESOURCE); return false;
  }
  if (!spend(b, count + symbols + 1)) return false;
  size_t bytes = count * sizeof(lie_builder_sequence) + symbols * sizeof(uint32_t);
  lie_builder_sequence *copy = bytes ? b->d.allocator.allocate(b->d.allocator.context, bytes) : NULL;
  if (bytes && !copy) { refuse(b, LIE_BUILDER_RESOURCE); return false; }
  uint32_t *at = count ? (uint32_t *)(copy + count) : NULL;
  for (size_t i = 0; i < count; ++i) {
    copy[i] = (lie_builder_sequence){at, source[i].count};
    if (source[i].count) memcpy(at, source[i].symbols, source[i].count * sizeof(*at));
    at += source[i].count;
  }
  if (fresh && !reserve_rules(b)) { retire(b, copy); return false; }
  b->rules[id] = (rule){copy, count, symbols};
  if (fresh) ++b->count;
  b->sequences = b->sequences - old.count + count;
  b->symbols = b->symbols - old.symbols + symbols;
  retire(b, old.sequences); return true;
}
static uint32_t new_rule(lie_grammar_builder *b, const lie_builder_sequence *v, size_t n) {
  uint32_t id = (uint32_t)b->count;
  return store_rule(b, id, v, n, true) ? id : 0;
}
static uint32_t sequence(lie_grammar_builder *b, const uint32_t *v, size_t n) {
  lie_builder_sequence s = {v, n}; return new_rule(b, &s, 1);
}
static uint32_t alternatives(lie_grammar_builder *b, const uint32_t *v, size_t n) {
  if (!mutable(b)) return 0;
  if ((n && !v) || n > b->d.max_sequences || n > SIZE_MAX / sizeof(lie_builder_sequence)) {
    refuse(b, LIE_BUILDER_INVALID); return 0;
  }
  lie_builder_sequence *views = n ? b->d.allocator.allocate(b->d.allocator.context, n * sizeof(*views)) : NULL;
  if (n && !views) { refuse(b, LIE_BUILDER_RESOURCE); return 0; }
  for (size_t i = 0; i < n; ++i) views[i] = (lie_builder_sequence){v + i, 1};
  uint32_t id = new_rule(b, views, n); retire(b, views); return id;
}
static uint32_t character_class(lie_grammar_builder *b, const uint8_t *v, size_t n) {
  if (!mutable(b)) return 0;
  if ((n && !v) || n > b->d.max_symbols || n == SIZE_MAX) { refuse(b, LIE_BUILDER_INVALID); return 0; }
  if (b->classes == b->d.max_classes) { refuse(b, LIE_BUILDER_TABLE_LIMIT); return 0; }
  if (!spend(b, n + 1)) return 0;
  if (b->classes == b->class_capacity) {
    size_t capacity = b->class_capacity * 2;
    if (capacity > b->d.max_classes) capacity = b->d.max_classes;
    if (capacity > SIZE_MAX / 32) { refuse(b, LIE_BUILDER_RESOURCE); return 0; }
    uint8_t *p = b->d.allocator.allocate(b->d.allocator.context, capacity * 32);
    if (!p) { refuse(b, LIE_BUILDER_RESOURCE); return 0; }
    memcpy(p, b->bits, b->classes * 32); retire(b, b->bits); b->bits = p; b->class_capacity = capacity;
  }
  uint8_t *bits = b->bits + b->classes * 32;
  memset(bits, 0, 32);
  for (size_t i = 0; i < n; ++i) bits[v[i] / 8] |= (uint8_t)(1u << (v[i] % 8));
  return LIE_GRAMMAR_TERMINAL | (uint32_t)b->classes++;
}
static uint32_t range_class(lie_grammar_builder *b, unsigned first, unsigned last) {
  if (first > last || last > 255) { refuse(b, LIE_BUILDER_INVALID); return 0; }
  uint8_t bytes[256]; for (unsigned i = first; i <= last; ++i) bytes[i - first] = (uint8_t)i;
  return character_class(b, bytes, last - first + 1);
}
static uint32_t optional(lie_grammar_builder *b, uint32_t item) {
  const lie_builder_sequence v[] = {{NULL, 0}, {&item, 1}}; return new_rule(b, v, 2);
}
static uint32_t repeat(lie_grammar_builder *b, uint32_t item) {
  uint32_t id = new_rule(b, NULL, 0), values[] = {item, id};
  const lie_builder_sequence v[] = {{NULL, 0}, {values, 2}};
  if (mutable(b)) store_rule(b, id, v, 2, false);
  return id;
}
static uint32_t exact(lie_grammar_builder *b, uint32_t item, size_t count) {
  uint32_t parts[sizeof(size_t) * 8]; size_t n = 0;
  while (count && mutable(b)) {
    if (count & 1) parts[n++] = item;
    count >>= 1;
    if (count) { uint32_t pair[] = {item, item}; item = sequence(b, pair, 2); }
  }
  return sequence(b, parts, n);
}
static uint32_t at_most(lie_grammar_builder *b, uint32_t item, size_t count) {
  if (!mutable(b)) return 0;
  if (!count) return sequence(b, NULL, 0);
  if (count == 1) return optional(b, item);
  if (count & 1) {
    uint32_t pair[] = {item, item};
    uint32_t combined = sequence(b, pair, 2);
    uint32_t parts[] = {at_most(b, combined, count / 2), 0};
    parts[1] = optional(b, item); return sequence(b, parts, 2);
  }
  uint32_t parts[] = {at_most(b, item, count - 1), 0};
  parts[1] = exact(b, item, count); return alternatives(b, parts, 2);
}
static uint32_t literal(lie_grammar_builder *b, const uint8_t *v, size_t n) {
  if (!mutable(b)) return 0;
  if ((n && !v) || n > b->d.max_symbols) { refuse(b, LIE_BUILDER_INVALID); return 0; }
  size_t count = n / 64 + (n % 64 != 0);
  if (count > SIZE_MAX / sizeof(uint32_t)) { refuse(b, LIE_BUILDER_RESOURCE); return 0; }
  uint32_t *chunks = count ? b->d.allocator.allocate(b->d.allocator.context, count * sizeof(*chunks)) : NULL;
  if (count && !chunks) { refuse(b, LIE_BUILDER_RESOURCE); return 0; }
  for (size_t offset = 0; offset < n && mutable(b); offset += 64) {
    size_t bytes = n - offset < 64 ? n - offset : 64;
    uint32_t symbols[64];
    for (size_t j = 0; j < bytes; ++j) symbols[j] = LIE_GRAMMAR_TERMINAL | v[offset + j];
    chunks[offset / 64] = sequence(b, symbols, bytes);
  }
  uint32_t id = sequence(b, chunks, count); retire(b, chunks); return id;
}
#define BYTE(x) (LIE_GRAMMAR_TERMINAL | (uint8_t)(x))
#define SEQ(b, ...) sequence(b, (uint32_t[]){__VA_ARGS__}, sizeof((uint32_t[]){__VA_ARGS__}) / sizeof(uint32_t))
#define ALT(b, ...) alternatives(b, (uint32_t[]){__VA_ARGS__}, sizeof((uint32_t[]){__VA_ARGS__}) / sizeof(uint32_t))
#define CLASS(b, s) character_class(b, (const uint8_t *)(s), sizeof(s) - 1)
static lie_builder_primitives json_primitives(lie_grammar_builder *b, uint32_t whitespace) {
  lie_builder_primitives p = {0};
  p.whitespace = optional(b, whitespace);
  uint32_t digits = CLASS(b, "0123456789"), hex = CLASS(b, "0123456789abcdefABCDEF");
  uint32_t hex_tail = SEQ(b, hex, hex), u[3];
  uint32_t c = CLASS(b, "0123456789abcefABCEF");
  u[0] = SEQ(b, c, hex, hex, hex);
  uint32_t d = CLASS(b, "dD"), h = CLASS(b, "01234567");
  u[1] = SEQ(b, d, h, hex_tail);
  d = CLASS(b, "dD"); h = CLASS(b, "89abAB");
  uint32_t escape = literal(b, (const uint8_t *)"\\u", 2);
  uint32_t low_d = CLASS(b, "dD"), low_h = CLASS(b, "cdefCDEF");
  u[2] = SEQ(b, d, h, hex_tail, escape, low_d, low_h, hex_tail);
  uint32_t unicode = alternatives(b, u, 3), continuation = range_class(b, 0x80, 0xbf), characters[13];
  characters[0] = range_class(b, 0x20, 0x21);
  characters[1] = range_class(b, 0x23, 0x5b);
  characters[2] = range_class(b, 0x5d, 0x7f);
  c = range_class(b, 0xc2, 0xdf); characters[3] = SEQ(b, c, continuation);
  c = range_class(b, 0xa0, 0xbf); characters[4] = SEQ(b, BYTE(0xe0), c, continuation);
  c = range_class(b, 0xe1, 0xec); characters[5] = SEQ(b, c, continuation, continuation);
  c = range_class(b, 0x80, 0x9f); characters[6] = SEQ(b, BYTE(0xed), c, continuation);
  c = range_class(b, 0xee, 0xef); characters[7] = SEQ(b, c, continuation, continuation);
  c = range_class(b, 0x90, 0xbf); characters[8] = SEQ(b, BYTE(0xf0), c, continuation, continuation);
  c = range_class(b, 0xf1, 0xf3); characters[9] = SEQ(b, c, continuation, continuation, continuation);
  c = range_class(b, 0x80, 0x8f); characters[10] = SEQ(b, BYTE(0xf4), c, continuation, continuation);
  c = CLASS(b, "\"\\/bfnrt"); characters[11] = SEQ(b, BYTE('\\'), c);
  escape = literal(b, (const uint8_t *)"\\u", 2); characters[12] = SEQ(b, escape, unicode);
  uint32_t character = alternatives(b, characters, 13), repeated = repeat(b, character);
  p.string = SEQ(b, BYTE('"'), repeated, BYTE('"'));
  c = range_class(b, '1', '9'); repeated = repeat(b, digits);
  uint32_t tail = SEQ(b, c, repeated), positive = ALT(b, BYTE('0'), tail);
  uint32_t sign = optional(b, BYTE('-')); p.integer = SEQ(b, sign, positive);
  repeated = repeat(b, digits); uint32_t fraction = SEQ(b, BYTE('.'), digits, repeated);
  c = CLASS(b, "eE"); d = CLASS(b, "+-"); sign = optional(b, d); repeated = repeat(b, digits);
  uint32_t exponent = SEQ(b, c, sign, digits, repeated);
  fraction = optional(b, fraction); exponent = optional(b, exponent);
  p.number = SEQ(b, p.integer, fraction, exponent);
  uint32_t yes = literal(b, (const uint8_t *)"true", 4), no = literal(b, (const uint8_t *)"false", 5);
  p.boolean = ALT(b, yes, no); p.null_value = literal(b, (const uint8_t *)"null", 4);
  return p;
}
static uint32_t generic_object(lie_grammar_builder *, size_t);
static uint32_t generic_value(lie_grammar_builder *b, size_t depth) {
  if (!mutable(b)) return 0;
  if (b->generic[depth] != UINT32_MAX) return b->generic[depth];
  uint32_t choices[6] = {b->primitives.string, b->primitives.number,
    b->primitives.boolean, b->primitives.null_value};
  size_t n = 4;
  if (depth) {
    uint32_t value = generic_value(b, depth - 1), ws = b->primitives.whitespace;
    uint32_t additional = SEQ(b, ws, BYTE(','), ws, value), tail = repeat(b, additional);
    uint32_t members = SEQ(b, value, tail); members = optional(b, members);
    choices[n++] = SEQ(b, BYTE('['), ws, members, ws, BYTE(']'));
    choices[n++] = generic_object(b, depth);
  }
  uint32_t id = alternatives(b, choices, n);
  if (mutable(b)) b->generic[depth] = id;
  return id;
}
static uint32_t generic_object(lie_grammar_builder *b, size_t depth) {
  uint32_t value = generic_value(b, depth - 1), ws = b->primitives.whitespace;
  uint32_t member = SEQ(b, b->primitives.string, ws, BYTE(':'), ws, value);
  uint32_t additional = SEQ(b, ws, BYTE(','), ws, member), tail = repeat(b, additional);
  uint32_t members = SEQ(b, member, tail); members = optional(b, members);
  return SEQ(b, BYTE('{'), ws, members, ws, BYTE('}'));
}
static uint32_t digits_between(lie_grammar_builder *b, const char *low, const char *high, size_t n) {
  if (!mutable(b)) return 0;
  if (!n) return sequence(b, NULL, 0);
  bool whole = true;
  for (size_t i = 0; i < n; ++i) whole &= low[i] == '0' && high[i] == '9';
  uint32_t parts[DIGITS + 1];
  if (whole) {
    uint32_t digit = range_class(b, '0', '9');
    for (size_t i = 0; i < n; ++i) parts[i] = digit;
    return sequence(b, parts, n);
  }
  if (low[0] == high[0]) {
    uint32_t suffix = digits_between(b, low + 1, high + 1, n - 1);
    return SEQ(b, BYTE(low[0]), suffix);
  }
  uint32_t choices[3]; size_t count = 0;
  uint32_t suffix = digits_between(b, low + 1, b->nines, n - 1);
  choices[count++] = SEQ(b, BYTE(low[0]), suffix);
  if (low[0] + 1 < high[0]) {
    parts[0] = range_class(b, (unsigned char)low[0] + 1, (unsigned char)high[0] - 1);
    /* Match the original call even for an empty middle suffix. */
    uint32_t digit = range_class(b, '0', '9');
    for (size_t i = 1; i < n; ++i) parts[i] = digit;
    choices[count++] = sequence(b, parts, n);
  }
  suffix = digits_between(b, b->zeros, high + 1, n - 1);
  choices[count++] = SEQ(b, BYTE(high[0]), suffix);
  return alternatives(b, choices, count);
}
static uint32_t unsigned_interval(lie_grammar_builder *b, const char *low, size_t nl,
  const char *high, size_t nh) {
  uint32_t choices[DIGITS + 2]; size_t count = 0, last = high ? nh : nl;
  for (size_t n = nl; n <= last && mutable(b); ++n) {
    char first[DIGITS], end[DIGITS];
    if (n == nl) memcpy(first, low, n);
    else { memcpy(first, b->zeros, n); first[0] = '1'; }
    if (high && n == nh) memcpy(end, high, n); else memcpy(end, b->nines, n);
    if (memcmp(first, end, n) <= 0) choices[count++] = digits_between(b, first, end, n);
  }
  if (!high) {
    uint32_t longer[DIGITS + 2]; longer[0] = range_class(b, '1', '9');
    uint32_t digit = range_class(b, '0', '9');
    for (size_t i = 1; i <= nl; ++i) longer[i] = digit;
    digit = range_class(b, '0', '9'); longer[nl + 1] = repeat(b, digit);
    choices[count++] = sequence(b, longer, nl + 2);
  }
  if (!count) { refuse(b, LIE_BUILDER_EMPTY); return 0; }
  return alternatives(b, choices, count);
}
static bool decimal(const char *p, size_t n, bool canonical) {
  if (!p || !n || n > DIGITS || (canonical && n > 1 && p[0] == '0')) return false;
  for (size_t i = 0; i < n; ++i) if (p[i] < '0' || p[i] > '9') return false;
  return true;
}
static lie_builder_status publish(lie_grammar_builder *b, uint32_t value, uint32_t *out) {
  if (b->status == LIE_BUILDER_OK) *out = value;
  return b->status;
}
lie_builder_status lie_builder_new(lie_grammar_builder *b, const lie_builder_sequence *v, size_t n, uint32_t *out) {
  if (!out) return LIE_BUILDER_INVALID;
  if (!mutable(b)) return unavailable(b);
  return publish(b, new_rule(b, v, n), out);
}
lie_builder_status lie_builder_set(lie_grammar_builder *b, uint32_t id, const lie_builder_sequence *v, size_t n) {
  if (!mutable(b)) return unavailable(b);
  if (id >= b->count) return refuse(b, LIE_BUILDER_INVALID);
  store_rule(b, id, v, n, false); return b->status;
}
#define WRAPPER(name, expression) \
  lie_builder_status name(lie_grammar_builder *b, uint32_t item, uint32_t *out) { \
    if (!out) return LIE_BUILDER_INVALID; \
    if (!mutable(b)) return unavailable(b); \
    return publish(b, expression, out); }
WRAPPER(lie_builder_optional, optional(b, item))
WRAPPER(lie_builder_repeat, repeat(b, item))
#undef WRAPPER
#define WRAPPER(name, expression) \
  lie_builder_status name(lie_grammar_builder *b, const uint32_t *v, size_t n, uint32_t *out) { \
    if (!out) return LIE_BUILDER_INVALID; \
    if (!mutable(b)) return unavailable(b); \
    return publish(b, expression, out); }
WRAPPER(lie_builder_sequence_make, sequence(b, v, n))
WRAPPER(lie_builder_alternatives, alternatives(b, v, n))
#undef WRAPPER
#define WRAPPER(name, expression) \
  lie_builder_status name(lie_grammar_builder *b, uint32_t item, size_t n, uint32_t *out) { \
    if (!out) return LIE_BUILDER_INVALID; \
    if (!mutable(b)) return unavailable(b); \
    return publish(b, expression, out); }
WRAPPER(lie_builder_exact, exact(b, item, n))
WRAPPER(lie_builder_at_most, at_most(b, item, n))
#undef WRAPPER
lie_builder_status lie_builder_class(lie_grammar_builder *b, const uint8_t *p, size_t n, uint32_t *out) {
  if (!out) return LIE_BUILDER_INVALID;
  if (!mutable(b)) return unavailable(b);
  return publish(b, character_class(b, p, n), out);
}
lie_builder_status lie_builder_range(lie_grammar_builder *b, unsigned first, unsigned last, uint32_t *out) {
  if (!out) return LIE_BUILDER_INVALID;
  if (!mutable(b)) return unavailable(b);
  return publish(b, range_class(b, first, last), out);
}
lie_builder_status lie_builder_literal(lie_grammar_builder *b, const uint8_t *p, size_t n, uint32_t *out) {
  if (!out) return LIE_BUILDER_INVALID;
  if (!mutable(b)) return unavailable(b);
  return publish(b, literal(b, p, n), out);
}
lie_builder_status lie_builder_json(lie_grammar_builder *b, uint32_t whitespace, lie_builder_primitives *out) {
  if (!out) return LIE_BUILDER_INVALID;
  if (!mutable(b)) return unavailable(b);
  if (b->json || (whitespace & LEAF) != LIE_GRAMMAR_LEXEME) return refuse(b, LIE_BUILDER_INVALID);
  lie_builder_primitives p = json_primitives(b, whitespace);
  if (mutable(b)) { b->json = true; b->primitives = p; *out = p; }
  return b->status;
}
lie_builder_status lie_builder_generic_value(lie_grammar_builder *b, size_t depth, uint32_t *out) {
  if (!out) return LIE_BUILDER_INVALID;
  if (!mutable(b)) return unavailable(b);
  if (!b->json || depth > 16) return refuse(b, LIE_BUILDER_INVALID);
  return publish(b, generic_value(b, depth), out);
}
lie_builder_status lie_builder_generic_object(lie_grammar_builder *b, size_t depth, uint32_t *out) {
  if (!out) return LIE_BUILDER_INVALID;
  if (!mutable(b)) return unavailable(b);
  if (!b->json || !depth || depth > 16) return refuse(b, LIE_BUILDER_INVALID);
  return publish(b, generic_object(b, depth), out);
}
lie_builder_status lie_builder_digits(lie_grammar_builder *b, const char *low, const char *high, size_t n, uint32_t *out) {
  if (!out) return LIE_BUILDER_INVALID;
  if (!mutable(b)) return unavailable(b);
  if (n && (!decimal(low, n, false) || !decimal(high, n, false) || memcmp(low, high, n) > 0)) return refuse(b, LIE_BUILDER_INVALID);
  return publish(b, digits_between(b, low, high, n), out);
}
lie_builder_status lie_builder_unsigned(lie_grammar_builder *b, const char *low, size_t nl, const char *high, size_t nh, uint32_t *out) {
  if (!out) return LIE_BUILDER_INVALID;
  if (!mutable(b)) return unavailable(b);
  if (!decimal(low, nl, true) || (high ? !decimal(high, nh, true) : nh != 0)) return refuse(b, LIE_BUILDER_INVALID);
  return publish(b, unsigned_interval(b, low, nl, high, nh), out);
}
static bool valid_symbol(const lie_grammar_builder *b, uint32_t value, size_t lexemes) {
  uint32_t kind = value & LEAF, index = value & ~LEAF;
  return kind == LIE_GRAMMAR_TERMINAL ? index < b->classes
       : kind == LIE_GRAMMAR_LEXEME ? index < lexemes
       : kind == 0 && index < b->count;
}
static bool productive_sequence(lie_builder_sequence s, const uint8_t *productive) {
  for (size_t i = 0; i < s.count; ++i)
    if (!(s.symbols[i] & LEAF) && !productive[s.symbols[i]]) return false;
  return true;
}
typedef struct { uint32_t rule; size_t sequence, symbol; } cursor;
static bool no_cycles(lie_grammar_builder *b, const uint8_t *nullable,
  uint8_t *visited, cursor *stack) {
  for (size_t id = 0; id < b->count; ++id) {
    if (visited[id]) continue;
    size_t depth = 1; stack[0] = (cursor){(uint32_t)id, 0, 0}; visited[id] = 1;
    while (depth) {
      if (!spend(b, 1)) return false;
      cursor *at = stack + depth - 1;
      const rule *r = b->rules + at->rule;
      if (at->sequence == r->count) { visited[at->rule] = 2; --depth; continue; }
      lie_builder_sequence s = r->sequences[at->sequence];
      if (at->symbol == s.count) { ++at->sequence; at->symbol = 0; continue; }
      uint32_t symbol = s.symbols[at->symbol++];
      if (symbol & LEAF) { ++at->sequence; at->symbol = 0; continue; }
      if (!nullable[symbol]) { ++at->sequence; at->symbol = 0; }
      if (visited[symbol] == 1) { refuse(b, LIE_BUILDER_CYCLE); return false; }
      if (visited[symbol] == 2) continue;
      visited[symbol] = 1; stack[depth++] = (cursor){symbol, 0, 0};
    }
  }
  return true;
}
lie_builder_status lie_builder_finish(lie_grammar_builder *b, uint32_t root,
  size_t lexemes, lie_grammar_description *out) {
  if (!out) return LIE_BUILDER_INVALID;
  if (!mutable(b)) return unavailable(b);
  if (!b->count || root >= b->count || lexemes >= LIE_GRAMMAR_LEXEME) return refuse(b, LIE_BUILDER_INVALID);
  for (size_t id = 0; id < b->count; ++id)
    for (size_t j = 0; j < b->rules[id].count; ++j) {
      lie_builder_sequence s = b->rules[id].sequences[j];
      if (!spend(b, s.count + 1)) return b->status;
      for (size_t k = 0; k < s.count; ++k)
        if (!valid_symbol(b, s.symbols[k], lexemes)) return refuse(b, LIE_BUILDER_INVALID);
    }
  uint8_t *flags = b->d.allocator.allocate(b->d.allocator.context, b->count * 3);
  cursor *stack = b->d.allocator.allocate(b->d.allocator.context, b->count * sizeof(*stack));
  if (!flags || !stack) {
    retire(b, flags); retire(b, stack); return refuse(b, LIE_BUILDER_RESOURCE);
  }
  memset(flags, 0, b->count * 3);
  uint8_t *productive = flags, *nullable = flags + b->count, *visited = flags + b->count * 2;
  bool changed = true;
  while (changed && mutable(b)) {
    changed = false;
    for (size_t id = 0; id < b->count && mutable(b); ++id) {
      for (size_t j = 0; j < b->rules[id].count && mutable(b); ++j) {
        lie_builder_sequence s = b->rules[id].sequences[j]; bool p = true, n = true;
        if (!spend(b, s.count + 1)) break;
        for (size_t k = 0; k < s.count; ++k) {
          uint32_t value = s.symbols[k];
          if (value & LEAF) n = false;
          else { p &= productive[value] != 0; n &= nullable[value] != 0; }
        }
        changed |= (p && !productive[id]) || (n && !nullable[id]);
        productive[id] |= p; nullable[id] |= n;
      }
    }
  }
  if (mutable(b)) no_cycles(b, nullable, visited, stack);
  if (mutable(b) && !productive[root]) refuse(b, LIE_BUILDER_EMPTY);
  size_t sequences = 0, symbols = 0;
  if (mutable(b))
    for (size_t id = 0; id < b->count && mutable(b); ++id)
      for (size_t j = 0; j < b->rules[id].count && mutable(b); ++j) {
        lie_builder_sequence s = b->rules[id].sequences[j];
        if (!spend(b, s.count + 1)) break;
        if (productive_sequence(s, productive)) { ++sequences; symbols += s.count; }
      }
  size_t bytes = 0;
  const size_t counts[] = {b->count, sequences, symbols, b->classes};
  const size_t widths[] = {sizeof(lie_grammar_range), sizeof(lie_grammar_range), sizeof(uint32_t), 32};
  if (mutable(b))
    for (size_t i = 0; i < 4; ++i) {
      if (counts[i] > (SIZE_MAX - bytes) / widths[i]) { refuse(b, LIE_BUILDER_RESOURCE); break; }
      bytes += counts[i] * widths[i];
    }
  void *tables = mutable(b) ? b->d.allocator.allocate(b->d.allocator.context, bytes) : NULL;
  if (mutable(b) && !tables) refuse(b, LIE_BUILDER_RESOURCE);
  if (mutable(b)) {
    lie_grammar_description d; lie_grammar_description_init(&d);
    lie_grammar_range *rules = tables, *ranges = rules + b->count;
    uint32_t *values = (uint32_t *)(ranges + sequences);
    uint8_t *classes = (uint8_t *)(values + symbols);
    size_t seq = 0, sym = 0;
    for (size_t id = 0; id < b->count; ++id) {
      rules[id] = (lie_grammar_range){(uint32_t)seq, 0};
      for (size_t j = 0; j < b->rules[id].count; ++j) {
        lie_builder_sequence s = b->rules[id].sequences[j];
        if (!productive_sequence(s, productive)) continue;
        ranges[seq++] = (lie_grammar_range){(uint32_t)sym, (uint32_t)s.count};
        if (s.count) memcpy(values + sym, s.symbols, s.count * sizeof(*values));
        sym += s.count; ++rules[id].count;
      }
    }
    memcpy(classes, b->bits, b->classes * 32);
    d.root = root; d.rules = rules; d.rule_count = b->count;
    d.sequences = ranges; d.sequence_count = sequences; d.symbols = values; d.symbol_count = symbols;
    d.classes = classes; d.class_count = b->classes; d.lexeme_count = lexemes;
    d.allocator = b->d.allocator;
    b->tables = tables; b->sealed = true; *out = d;
  }
  retire(b, flags); retire(b, stack); return b->status;
}
