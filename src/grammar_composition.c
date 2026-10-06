/* SPDX-License-Identifier: MIT */
/* Copyright (c) 2026 gufo contributors. */
/* Attributed reasoning/tool composition port from official Gufo f783fedb. */
#include "lie/grammar_composition.h"
#include <stdlib.h>
#include <string.h>
#define LEAF (LIE_GRAMMAR_TERMINAL | LIE_GRAMMAR_LEXEME)
#define NONE UINT32_MAX
typedef struct { void *data; size_t count, capacity, width; } array;
typedef struct { uint32_t first, last, count; } rule;
typedef struct { uint32_t next, offset, count; } sequence;
typedef struct { const lie_grammar_program *program; uint32_t root; } imported;
struct lie_grammar_composition {
  lie_composition_description d;
  lie_composition_status status;
  array rules, sequences, symbols, classes, lexemes, imports;
  lie_composition_view view;
  void *tables;
  size_t tables_bytes, work, live, peak;
};
static void *ordinary_allocate(void *ctx, size_t bytes) {
  (void)ctx; return malloc(bytes);
}
static void ordinary_release(void *ctx, void *p) { (void)ctx; free(p); }
void lie_composition_description_init(lie_composition_description *d) {
  if (d) *d = (lie_composition_description){LIE_GRAMMAR_COMPOSITION_ABI,
    sizeof(*d), 262144, UINT32_MAX, UINT32_MAX, 262144, 262144, 64000000, {0}};
}
static bool fail(lie_grammar_composition *c, lie_composition_status rc) {
  if (c->status == LIE_COMPOSITION_OK) c->status = rc;
  return false;
}
static bool spend(lie_grammar_composition *c, size_t n) {
  if (c->status != LIE_COMPOSITION_OK) return false;
  if (n > c->d.max_work - c->work)
    return fail(c, LIE_COMPOSITION_WORK_LIMIT);
  c->work += n; return true;
}
static void *allocate(lie_grammar_composition *c, size_t bytes) {
  if (!bytes || bytes > SIZE_MAX - c->live) {
    fail(c, LIE_COMPOSITION_RESOURCE); return NULL;
  }
  void *p = c->d.allocator.allocate(c->d.allocator.context, bytes);
  if (!p) { fail(c, LIE_COMPOSITION_RESOURCE); return NULL; }
  c->live += bytes;
  if (c->live > c->peak) c->peak = c->live;
  return p;
}
static void retire(lie_grammar_composition *c, void *p, size_t bytes) {
  if (p) { c->d.allocator.release(c->d.allocator.context, p); c->live -= bytes; }
}
static void retire_array(lie_grammar_composition *c, array *a) {
  retire(c, a->data, a->capacity * a->width);
  a->data = NULL; a->capacity = a->count = 0;
}
void lie_composition_release(lie_grammar_composition *c) {
  if (!c) return;
  retire_array(c, &c->rules); retire_array(c, &c->sequences);
  retire_array(c, &c->symbols); retire_array(c, &c->classes);
  retire_array(c, &c->lexemes); retire_array(c, &c->imports);
  retire(c, c->tables, c->tables_bytes);
  c->d.allocator.release(c->d.allocator.context, c);
}
static bool reserve(lie_grammar_composition *c, array *a, size_t extra,
                    size_t limit) {
  if (a->count > limit || extra > limit - a->count)
    return fail(c, LIE_COMPOSITION_TABLE_LIMIT);
  size_t need = a->count + extra;
  if (need <= a->capacity) return true;
  size_t cap = a->capacity ? a->capacity : 16;
  if (cap > limit) cap = limit;
  while (cap < need) cap = cap > limit / 2 ? limit : cap * 2;
  if (cap > SIZE_MAX / a->width) return fail(c, LIE_COMPOSITION_RESOURCE);
  void *p = allocate(c, cap * a->width);
  if (!p) return false;
  if (a->count) memcpy(p, a->data, a->count * a->width);
  retire(c, a->data, a->capacity * a->width);
  a->data = p; a->capacity = cap; return true;
}
static bool capacity(lie_grammar_composition *c, size_t rules, size_t classes,
                     size_t lexemes) {
  if (rules > c->d.max_rules - c->rules.count ||
      classes > c->d.max_classes - c->classes.count ||
      lexemes > c->d.max_lexemes - c->lexemes.count)
    return fail(c, LIE_COMPOSITION_TABLE_LIMIT);
  return true;
}
static uint32_t new_rule(lie_grammar_composition *c) {
  if (!spend(c, 1) || !reserve(c, &c->rules, 1, c->d.max_rules)) return NONE;
  uint32_t id = (uint32_t)c->rules.count++;
  ((rule *)c->rules.data)[id] = (rule){NONE, NONE, 0}; return id;
}
static bool append(lie_grammar_composition *c, uint32_t id,
                   const uint32_t *symbols, size_t count) {
  if (id >= c->rules.count || !spend(c, count) || !spend(c, 1) ||
      !reserve(c, &c->sequences, 1, c->d.max_sequences) ||
      !reserve(c, &c->symbols, count, c->d.max_symbols)) return false;
  uint32_t n = (uint32_t)c->sequences.count++;
  sequence *seq = c->sequences.data;
  seq[n] = (sequence){NONE, (uint32_t)c->symbols.count, (uint32_t)count};
  if (count) memcpy((uint32_t *)c->symbols.data + c->symbols.count,
                    symbols, count * sizeof(*symbols));
  c->symbols.count += count;
  rule *r = (rule *)c->rules.data + id;
  if (r->last == NONE) r->first = n; else seq[r->last].next = n;
  r->last = n; ++r->count; return true;
}
static bool class_bits(lie_grammar_composition *c, const uint8_t bits[32],
                       uint32_t *out) {
  if (!spend(c, 32) || !reserve(c, &c->classes, 1, c->d.max_classes)) return false;
  *out = LIE_GRAMMAR_TERMINAL | (uint32_t)c->classes.count;
  memcpy((uint8_t *)c->classes.data + c->classes.count++ * 32, bits, 32);
  return true;
}
static bool import(lie_grammar_composition *c, const lie_grammar_program *p,
                   uint32_t *root) {
  lie_grammar_description d;
  if (lie_grammar_program_describe(p, &d) != LIE_GRAMMAR_OK)
    return fail(c, LIE_COMPOSITION_INVALID);
  if (!capacity(c, d.rule_count, d.class_count, d.lexeme_count) ||
      d.class_count > SIZE_MAX / 32 ||
      !spend(c, d.class_count * 32) || !spend(c, d.lexeme_count) ||
      !reserve(c, &c->classes, d.class_count, c->d.max_classes) ||
      !reserve(c, &c->lexemes, d.lexeme_count, c->d.max_lexemes)) return false;
  uint32_t ro = (uint32_t)c->rules.count, co = (uint32_t)c->classes.count,
           lo = (uint32_t)c->lexemes.count;
  if (d.class_count) memcpy((uint8_t *)c->classes.data + c->classes.count * 32,
                            d.classes, d.class_count * 32);
  c->classes.count += d.class_count;
  lie_composition_lexeme *lex = c->lexemes.data;
  for (size_t i = 0; i < d.lexeme_count; ++i)
    lex[c->lexemes.count++] = (lie_composition_lexeme){p, (uint32_t)i};
  for (size_t i = 0; i < d.rule_count; ++i)
    if (new_rule(c) == NONE) return false;
  for (size_t i = 0; i < d.rule_count; ++i) {
    lie_grammar_range r = d.rules[i];
    for (size_t j = 0; j < r.count; ++j) {
      lie_grammar_range s = d.sequences[r.offset + j];
      /* Copy first, then remap our private symbols in place. */
      size_t start = c->symbols.count;
      if (!append(c, ro + (uint32_t)i,
                  s.count ? d.symbols + s.offset : NULL, s.count)) return false;
      uint32_t *v = s.count ? (uint32_t *)c->symbols.data + start : NULL;
      for (size_t k = 0; k < s.count; ++k) {
        uint32_t symbol = v[k], kind = symbol & LEAF;
        v[k] = kind == LIE_GRAMMAR_TERMINAL ? kind | ((symbol & ~LEAF) + co)
             : kind == LIE_GRAMMAR_LEXEME ? kind | ((symbol & ~LEAF) + lo)
             : symbol + ro;
      }
    }
  }
  *root = ro + d.root; return true;
}
static bool literal(lie_grammar_composition *c, const uint8_t *bytes, size_t count,
                    uint32_t *out) {
  uint32_t id = new_rule(c);
  if (count > c->d.max_symbols) return fail(c, LIE_COMPOSITION_TABLE_LIMIT);
  if (id == NONE ||
      !reserve(c, &c->symbols, count, c->d.max_symbols)) return false;
  /* append copies into the same reserved array; use a separate temporary. */
  if (count > SIZE_MAX / sizeof(uint32_t)) return fail(c, LIE_COMPOSITION_RESOURCE);
  uint32_t *v = count ? allocate(c, count * sizeof(*v)) : NULL;
  if (count && !v) return false;
  for (size_t i = 0; i < count; ++i) v[i] = LIE_GRAMMAR_TERMINAL | bytes[i];
  bool ok = append(c, id, v, count);
  retire(c, v, count * sizeof(*v));
  if (ok) *out = id;
  return ok;
}
static bool marker(lie_grammar_composition *c, const char *text, size_t n,
                   uint32_t target, bool nullable, uint32_t *out) {
  if (!capacity(c, n, nullable ? n * 256 : 0, 0)) return false;
  uint32_t base = (uint32_t)c->rules.count;
  for (size_t i = 0; i < n; ++i) if (new_rule(c) == NONE) return false;
  for (size_t prefix = 0; prefix < n; ++prefix) {
    if (nullable && !append(c, base + (uint32_t)prefix, NULL, 0)) return false;
    uint8_t transitions[12][32] = {{0}};
    for (unsigned byte = 0; byte < 256; ++byte) {
      uint8_t candidate[11];
      memcpy(candidate, text, prefix); candidate[prefix] = (uint8_t)byte;
      size_t matched = prefix + 1;
      while (matched) {
        if (!spend(c, matched)) return false;
        if (!memcmp(candidate + prefix + 1 - matched, text, matched)) break;
        --matched;
      }
      transitions[matched][byte / 8] |= (uint8_t)(1u << (byte % 8));
    }
    for (size_t matched = 0; matched <= n; ++matched) {
      bool any = false;
      for (size_t b = 0; b < 32; ++b) any |= transitions[matched][b] != 0;
      if (!any || (matched == n && target == NONE)) continue;
      uint32_t v[2];
      if (!class_bits(c, transitions[matched], v)) return false;
      v[1] = matched == n ? target : base + (uint32_t)matched;
      if (!append(c, base + (uint32_t)prefix, v, 2)) return false;
    }
  }
  *out = base; return true;
}
static bool name_literal(lie_grammar_composition *c, const lie_composition_tool *t,
                         uint32_t *out) {
  static const char begin[] = "{\"name\":\"", end[] = "\",\"arguments\":";
  size_t size = sizeof(begin) - 1 + sizeof(end) - 1;
  if (!spend(c, t->name_bytes)) return false;
  for (size_t i = 0; i < t->name_bytes; ++i) {
    uint8_t b = t->name[i];
    size_t extra = b == '"' || b == '\\' || b == '\b' || b == '\f' ||
      b == '\n' || b == '\r' || b == '\t' ? 2 : b < 0x20 ? 6 : 1;
    if (extra > SIZE_MAX - size) return fail(c, LIE_COMPOSITION_RESOURCE);
    size += extra;
  }
  if (size > c->d.max_symbols) return fail(c, LIE_COMPOSITION_TABLE_LIMIT);
  uint8_t *bytes = allocate(c, size);
  if (!bytes) return false;
  size_t at = sizeof(begin) - 1; memcpy(bytes, begin, at);
  static const char hex[] = "0123456789abcdef";
  for (size_t i = 0; i < t->name_bytes; ++i) {
    uint8_t b = t->name[i], escaped = 0;
    switch (b) {
    case '"': case '\\': escaped = b; break;
    case '\b': escaped = 'b'; break; case '\f': escaped = 'f'; break;
    case '\n': escaped = 'n'; break; case '\r': escaped = 'r'; break;
    case '\t': escaped = 't'; break; default: break;
    }
    if (escaped) { bytes[at++] = '\\'; bytes[at++] = escaped; }
    else if (b < 0x20) {
      memcpy(bytes + at, "\\u00", 4); at += 4;
      bytes[at++] = (uint8_t)hex[b / 16]; bytes[at++] = (uint8_t)hex[b % 16];
    } else bytes[at++] = b;
  }
  memcpy(bytes + at, end, sizeof(end) - 1);
  bool ok = literal(c, bytes, size, out); retire(c, bytes, size); return ok;
}
static lie_grammar_composition *create(const lie_composition_description *d) {
  lie_grammar_allocator a = d->allocator;
  if (!a.allocate) a = (lie_grammar_allocator){NULL, ordinary_allocate, ordinary_release};
  lie_grammar_composition *c = a.allocate(a.context, sizeof(*c));
  if (!c) return NULL;
  *c = (lie_grammar_composition){.d = *d, .live = sizeof(*c), .peak = sizeof(*c)};
  c->d.allocator = a;
  c->rules.width = sizeof(rule); c->sequences.width = sizeof(sequence);
  c->symbols.width = sizeof(uint32_t); c->classes.width = 32;
  c->lexemes.width = sizeof(lie_composition_lexeme); c->imports.width = sizeof(imported);
  return c;
}
static bool valid(const lie_composition_description *d) {
  return d && d->abi_version == LIE_GRAMMAR_COMPOSITION_ABI &&
    d->struct_bytes == sizeof(*d) && d->max_rules && d->max_rules <= 262144 &&
    d->max_sequences && d->max_sequences <= UINT32_MAX &&
    d->max_symbols && d->max_symbols <= UINT32_MAX && d->max_classes &&
    d->max_classes < LIE_GRAMMAR_LEXEME && d->max_lexemes < LIE_GRAMMAR_LEXEME &&
    d->max_work && (!!d->allocator.allocate == !!d->allocator.release);
}
static lie_composition_status seal(lie_grammar_composition *c, uint32_t root,
  bool stop, const lie_grammar_program *base, lie_grammar_composition **out) {
  size_t counts[] = {c->rules.count, c->sequences.count, c->symbols.count, c->classes.count};
  size_t widths[] = {sizeof(lie_grammar_range), sizeof(lie_grammar_range), sizeof(uint32_t), 32};
  size_t total = 0;
  for (size_t i = 0; i < 4; ++i) {
    if (counts[i] > (SIZE_MAX - total) / widths[i]) {
      fail(c, LIE_COMPOSITION_RESOURCE); break;
    }
    total += counts[i] * widths[i];
  }
  if (c->status == LIE_COMPOSITION_OK && spend(c, c->rules.count) &&
      spend(c, c->sequences.count) && spend(c, c->symbols.count)) {
    c->tables = allocate(c, total); if (c->tables) c->tables_bytes = total;
  }
  if (c->status != LIE_COMPOSITION_OK) {
    lie_composition_status rc = c->status; lie_composition_release(c); return rc;
  }
  lie_grammar_description d;
  (void)lie_grammar_program_describe(base, &d);
  d.root = root; d.predicates = (lie_grammar_predicates){0}; d.allocator = (lie_grammar_allocator){0};
  uint8_t *at = c->tables;
  d.rules = (lie_grammar_range *)at; at += counts[0] * widths[0]; d.rule_count = counts[0];
  d.sequences = (lie_grammar_range *)at; at += counts[1] * widths[1]; d.sequence_count = counts[1];
  d.symbols = (uint32_t *)at; at += counts[2] * widths[2]; d.symbol_count = counts[2];
  d.classes = at; d.class_count = counts[3]; d.lexeme_count = c->lexemes.count;
  size_t si = 0, sy = 0;
  for (size_t i = 0; i < c->rules.count; ++i) {
    rule r = ((rule *)c->rules.data)[i];
    ((lie_grammar_range *)d.rules)[i] = (lie_grammar_range){(uint32_t)si, r.count};
    for (uint32_t n = r.first; n != NONE; n = ((sequence *)c->sequences.data)[n].next) {
      sequence s = ((sequence *)c->sequences.data)[n];
      ((lie_grammar_range *)d.sequences)[si++] = (lie_grammar_range){(uint32_t)sy, s.count};
      if (s.count) memcpy((uint32_t *)d.symbols + sy,
        (uint32_t *)c->symbols.data + s.offset, s.count * sizeof(uint32_t));
      sy += s.count;
    }
  }
  if (c->classes.count) memcpy((uint8_t *)d.classes, c->classes.data, c->classes.count * 32);
  retire_array(c, &c->rules); retire_array(c, &c->sequences);
  retire_array(c, &c->symbols); retire_array(c, &c->classes); retire_array(c, &c->imports);
  c->view = (lie_composition_view){d, c->lexemes.data, stop, c->work, c->live, c->peak};
  *out = c; return LIE_COMPOSITION_OK;
}
lie_composition_status lie_composition_reasoning(const lie_composition_description *d,
  const lie_grammar_program *base, bool stop, lie_grammar_composition **out) {
  if (!valid(d) || !base || !out) return LIE_COMPOSITION_INVALID;
  lie_grammar_composition *c = create(d);
  if (!c) return LIE_COMPOSITION_RESOURCE;
  uint32_t answer = 0, root = 0;
  if (!import(c, base, &answer) || !marker(c, "</think>", 8, answer, false, &root)) {
    lie_composition_status rc = c->status; lie_composition_release(c); return rc;
  }
  return seal(c, root, stop, base, out);
}
lie_composition_status lie_composition_tools(const lie_composition_description *d,
  const lie_grammar_program *base, bool plain, const lie_composition_tool *tools,
  size_t count, bool required, bool parallel, lie_grammar_composition **out) {
  if (!valid(d) || !base || !tools || !count || !out || count > d->max_sequences ||
      count > SIZE_MAX / sizeof(*tools)) return LIE_COMPOSITION_INVALID;
  if (count > d->max_work) return LIE_COMPOSITION_WORK_LIMIT;
  for (size_t i = 0; i < count; ++i)
    if (!tools[i].arguments || (tools[i].name_bytes && !tools[i].name)) return LIE_COMPOSITION_INVALID;
  lie_grammar_description bd;
  if (lie_grammar_program_describe(base, &bd) != LIE_GRAMMAR_OK || bd.class_count < 256)
    return LIE_COMPOSITION_INVALID;
  for (size_t i = 0; i < 256; ++i)
    for (size_t j = 0; j < 32; ++j)
      if (bd.classes[i * 32 + j] != (j == i / 8 ? (uint8_t)(1u << (i % 8)) : 0))
        return LIE_COMPOSITION_INVALID;
  lie_grammar_composition *c = create(d);
  if (!c) return LIE_COMPOSITION_RESOURCE;
  if (!spend(c, count)) goto refused;
  uint32_t answer = 0, end = 0, prose = NONE, after = NONE, begin = 0;
  if (!import(c, base, &answer) || !literal(c, (const uint8_t *)"}</tool_call>", 13, &end)) goto refused;
  uint32_t calls = new_rule(c);
  if (calls == NONE) goto refused;
  if (plain) {
    if (!marker(c, "<tool_call>", 11, calls, true, &prose)) goto refused;
    after = prose;
    if (!parallel && !marker(c, "<tool_call>", 11, NONE, true, &after)) goto refused;
  } else {
    after = new_rule(c);
    if (after == NONE || !append(c, after, NULL, 0)) goto refused;
    if (parallel) {
      if (!literal(c, (const uint8_t *)"<tool_call>", 11, &begin)) goto refused;
      uint32_t v[] = {begin, calls};
      if (!append(c, after, v, 2)) goto refused;
    }
    if (!reserve(c, &c->imports, 1, d->max_rules)) goto refused;
    ((imported *)c->imports.data)[c->imports.count++] = (imported){base, answer};
  }
  for (size_t i = 0; i < count; ++i) {
    if (!name_literal(c, tools + i, &begin)) goto refused;
    uint32_t arguments = NONE;
    imported *entries = c->imports.data;
    for (size_t j = 0; j < c->imports.count; ++j) {
      if (!spend(c, 1)) goto refused;
      if (entries[j].program == tools[i].arguments) { arguments = entries[j].root; break; }
    }
    if (arguments == NONE) {
      if (!import(c, tools[i].arguments, &arguments) ||
          !reserve(c, &c->imports, 1, d->max_rules)) goto refused;
      ((imported *)c->imports.data)[c->imports.count++] = (imported){tools[i].arguments, arguments};
    }
    uint32_t v[] = {begin, arguments, end, after};
    if (!append(c, calls, v, 4)) goto refused;
  }
  uint32_t root;
  if (plain && !required) begin = prose;
  else if (!literal(c, (const uint8_t *)"<tool_call>", 11, &begin)) goto refused;
  root = new_rule(c);
  if (root == NONE) goto refused;
  if (!required && !plain && !append(c, root, &answer, 1)) goto refused;
  uint32_t v[] = {begin, calls};
  if (!append(c, root, v, plain && !required ? 1 : 2)) goto refused;
  return seal(c, root, !plain && !parallel, base, out);
refused: {
  lie_composition_status rc = c->status; lie_composition_release(c); return rc;
}}
lie_composition_status lie_composition_describe(const lie_grammar_composition *c,
                                               lie_composition_view *out) {
  if (!c || !out || !c->tables) return LIE_COMPOSITION_INVALID;
  *out = c->view; return LIE_COMPOSITION_OK;
}
