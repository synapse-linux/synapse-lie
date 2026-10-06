/* SPDX-License-Identifier: MIT */
/* Copyright (c) 2026 gufo contributors. */
/* Attributed byte-runtime port from official Gufo f783fedb. See NOTICE. */
#include "lie/grammar.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>
#define LEAF (LIE_GRAMMAR_TERMINAL | LIE_GRAMMAR_LEXEME)
typedef struct {
  uint32_t *symbols;
  size_t count;
  uint8_t *lexeme;
  size_t bytes, capacity;
  void *allocation;
} frame;
struct lie_grammar_program {
  lie_grammar_description d;
  void *tables;
};
struct lie_grammar_state {
  lie_grammar_allocator allocator;
  lie_grammar_limits limits;
  frame *frames;
  size_t count, capacity;
};
static void *ordinary_allocate(void *context, size_t bytes) {
  (void)context;
  return malloc(bytes);
}
static void ordinary_release(void *context, void *p) {
  (void)context;
  free(p);
}
static bool span(const void *p, size_t n, size_t width) {
  return n <= SIZE_MAX / width && (!n || p);
}
static bool limits(const lie_grammar_limits *p) {
  return p && p->abi_version == LIE_GRAMMAR_ABI &&
         p->struct_bytes == sizeof(*p) && p->max_states &&
         p->max_states <= UINT32_MAX && p->max_stack &&
         p->max_stack <= UINT32_MAX && p->max_work && p->max_work < SIZE_MAX &&
         p->max_lexeme_bytes &&
         p->max_lexeme_bytes <= UINT32_MAX;
}
void lie_grammar_limits_init(lie_grammar_limits *p) {
  if (p)
    *p = (lie_grammar_limits){LIE_GRAMMAR_ABI, sizeof(*p), 8192, 16384,
                              2000000, 4096 + 64};
}
void lie_grammar_description_init(lie_grammar_description *p) {
  if (p) {
    *p = (lie_grammar_description){.abi_version = LIE_GRAMMAR_ABI,
                                   .struct_bytes = sizeof(*p)};
    lie_grammar_limits_init(&p->limits);
  }
}
static bool symbol(const lie_grammar_description *d, uint32_t s) {
  uint32_t kind = s & LEAF, index = s & ~LEAF;
  return kind == LIE_GRAMMAR_TERMINAL ? index < d->class_count
       : kind == LIE_GRAMMAR_LEXEME ? index < d->lexeme_count
       : kind == 0 ? index < d->rule_count : false;
}
static bool range(lie_grammar_range r, size_t count) {
  return r.offset <= count && r.count <= count - r.offset;
}
lie_grammar_status lie_grammar_program_create(const lie_grammar_description *d,
                                             lie_grammar_program **out) {
  if (!out || !d || d->abi_version != LIE_GRAMMAR_ABI ||
      d->struct_bytes != sizeof(*d) || !limits(&d->limits) || !d->rule_count ||
      d->rule_count > 262144 || d->root >= d->rule_count ||
      d->sequence_count > UINT32_MAX || d->symbol_count > UINT32_MAX ||
      d->class_count >= LIE_GRAMMAR_LEXEME ||
      d->lexeme_count >= LIE_GRAMMAR_LEXEME ||
      !span(d->rules, d->rule_count, sizeof(*d->rules)) ||
      !span(d->sequences, d->sequence_count, sizeof(*d->sequences)) ||
      !span(d->symbols, d->symbol_count, sizeof(*d->symbols)) ||
      !span(d->classes, d->class_count, 32) ||
      (!!d->allocator.allocate != !!d->allocator.release) ||
      (d->lexeme_count && (!d->predicates.allows || !d->predicates.advance)))
    return LIE_GRAMMAR_INVALID;
  for (size_t i = 0; i < d->rule_count; ++i)
    if (!range(d->rules[i], d->sequence_count))
      return LIE_GRAMMAR_INVALID;
  for (size_t i = 0; i < d->sequence_count; ++i)
    if (!range(d->sequences[i], d->symbol_count))
      return LIE_GRAMMAR_INVALID;
  for (size_t i = 0; i < d->symbol_count; ++i)
    if (!symbol(d, d->symbols[i]))
      return LIE_GRAMMAR_INVALID;
  size_t widths[] = {sizeof(*d->rules), sizeof(*d->sequences),
                     sizeof(*d->symbols), 32};
  size_t counts[] = {d->rule_count, d->sequence_count, d->symbol_count,
                     d->class_count};
  size_t total = 0;
  for (size_t i = 0; i < 4; ++i) {
    size_t bytes = counts[i] * widths[i];
    if (bytes > SIZE_MAX - total)
      return LIE_GRAMMAR_RESOURCE;
    total += bytes;
  }
  lie_grammar_allocator a = d->allocator;
  if (!a.allocate)
    a = (lie_grammar_allocator){NULL, ordinary_allocate, ordinary_release};
  lie_grammar_program *p = a.allocate(a.context, sizeof(*p));
  if (!p)
    return LIE_GRAMMAR_RESOURCE;
  p->d = *d;
  p->d.allocator = a;
  p->tables = a.allocate(a.context, total);
  if (!p->tables) {
    a.release(a.context, p);
    return LIE_GRAMMAR_RESOURCE;
  }
  unsigned char *at = p->tables;
  const void *sources[] = {d->rules, d->sequences, d->symbols, d->classes};
  void *destinations[4];
  for (size_t i = 0; i < 4; ++i) {
    destinations[i] = at;
    size_t bytes = counts[i] * widths[i];
    if (bytes)
      memcpy(at, sources[i], bytes);
    at += bytes;
  }
  p->d.rules = destinations[0];
  p->d.sequences = destinations[1];
  p->d.symbols = destinations[2];
  p->d.classes = destinations[3];
  *out = p;
  return LIE_GRAMMAR_OK;
}
void lie_grammar_program_release(lie_grammar_program *p) {
  if (!p)
    return;
  lie_grammar_allocator a = p->d.allocator;
  a.release(a.context, p->tables);
  a.release(a.context, p);
}
lie_grammar_status lie_grammar_program_describe(const lie_grammar_program *p,
                                               lie_grammar_description *out) {
  if (!p || !out)
    return LIE_GRAMMAR_INVALID;
  *out = p->d;
  return LIE_GRAMMAR_OK;
}
static lie_grammar_state *new_state(const lie_grammar_program *p) {
  lie_grammar_allocator a = p->d.allocator;
  lie_grammar_state *s = a.allocate(a.context, sizeof(*s));
  if (s)
    *s = (lie_grammar_state){.allocator = a, .limits = p->d.limits};
  return s;
}
static void release_frame(lie_grammar_state *s, frame *f) {
  if (f->allocation)
    s->allocator.release(s->allocator.context, f->allocation);
  *f = (frame){0};
}
void lie_grammar_state_release(lie_grammar_state *s) {
  if (!s)
    return;
  for (size_t i = 0; i < s->count; ++i)
    release_frame(s, s->frames + i);
  if (s->frames)
    s->allocator.release(s->allocator.context, s->frames);
  s->allocator.release(s->allocator.context, s);
}
static bool valid_frame(const lie_grammar_program *p, lie_grammar_frame f) {
  if (!span(f.symbols, f.symbol_count, sizeof(*f.symbols)) ||
      !span(f.lexeme, f.lexeme_bytes, 1) ||
      f.symbol_count > p->d.limits.max_stack ||
      f.lexeme_bytes > p->d.limits.max_lexeme_bytes)
    return false;
  for (size_t i = 0; i < f.symbol_count; ++i)
    if (!symbol(&p->d, f.symbols[i]))
      return false;
  return true;
}
static lie_grammar_frame view(const frame *f) {
  return (lie_grammar_frame){f->symbols, f->count, f->lexeme, f->bytes};
}
static lie_grammar_status copy_frame(lie_grammar_state *s,
                                     lie_grammar_frame input, size_t extra,
                                     frame *out) {
  if (input.symbol_count > s->limits.max_stack)
    return LIE_GRAMMAR_STACK_LIMIT;
  if (input.lexeme_bytes > s->limits.max_lexeme_bytes)
    return LIE_GRAMMAR_RESOURCE;
  size_t capacity = input.lexeme_bytes;
  if (extra > s->limits.max_lexeme_bytes - capacity)
    extra = s->limits.max_lexeme_bytes - capacity;
  capacity += extra;
  if (input.symbol_count > (SIZE_MAX - capacity) / sizeof(uint32_t))
    return LIE_GRAMMAR_RESOURCE;
  size_t bytes = input.symbol_count * sizeof(uint32_t) + capacity;
  void *data = bytes ? s->allocator.allocate(s->allocator.context, bytes) : NULL;
  if (bytes && !data)
    return LIE_GRAMMAR_RESOURCE;
  *out = (frame){.symbols = data, .count = input.symbol_count,
                 .lexeme = bytes ? (uint8_t *)data +
                           input.symbol_count * sizeof(uint32_t) : NULL,
                 .bytes = input.lexeme_bytes, .capacity = capacity,
                 .allocation = data};
  if (input.symbol_count)
    memcpy(out->symbols, input.symbols, input.symbol_count * sizeof(uint32_t));
  if (input.lexeme_bytes)
    memcpy(out->lexeme, input.lexeme, input.lexeme_bytes);
  return LIE_GRAMMAR_OK;
}
static lie_grammar_status push(lie_grammar_state *s, frame *f) {
  if (s->count >= s->limits.max_states)
    return LIE_GRAMMAR_STATE_LIMIT;
  if (s->count == s->capacity) {
    size_t cap = s->capacity ? (s->capacity > s->limits.max_states / 2
                                  ? s->limits.max_states : s->capacity * 2) : 8;
    if (cap > s->limits.max_states)
      cap = s->limits.max_states;
    if (cap > SIZE_MAX / sizeof(frame))
      return LIE_GRAMMAR_RESOURCE;
    frame *next = s->allocator.allocate(s->allocator.context, cap * sizeof(frame));
    if (!next)
      return LIE_GRAMMAR_RESOURCE;
    if (s->count)
      memcpy(next, s->frames, s->count * sizeof(frame));
    if (s->frames)
      s->allocator.release(s->allocator.context, s->frames);
    s->frames = next;
    s->capacity = cap;
  }
  s->frames[s->count++] = *f;
  *f = (frame){0};
  return LIE_GRAMMAR_OK;
}
lie_grammar_status lie_grammar_state_import(const lie_grammar_program *p,
                                           const lie_grammar_frame *frames,
                                           size_t count,
                                           lie_grammar_state **out) {
  if (!p || !out || !span(frames, count, sizeof(*frames)))
    return LIE_GRAMMAR_INVALID;
  if (count > p->d.limits.max_states)
    return LIE_GRAMMAR_STATE_LIMIT;
  for (size_t i = 0; i < count; ++i)
    if (!valid_frame(p, frames[i]))
      return LIE_GRAMMAR_INVALID;
  lie_grammar_state *s = new_state(p);
  if (!s)
    return LIE_GRAMMAR_RESOURCE;
  lie_grammar_status rc = LIE_GRAMMAR_OK;
  for (size_t i = 0; i < count; ++i) {
    frame f = {0};
    rc = copy_frame(s, frames[i], 0, &f);
    if (rc == LIE_GRAMMAR_OK)
      rc = push(s, &f);
    if (rc != LIE_GRAMMAR_OK) {
      release_frame(s, &f);
      lie_grammar_state_release(s);
      return rc;
    }
  }
  *out = s;
  return LIE_GRAMMAR_OK;
}
lie_grammar_status lie_grammar_state_read(const lie_grammar_program *p,
  const lie_grammar_snapshot_reader *reader, lie_grammar_state **out) {
  if (!p || !reader || !out || reader->abi_version != LIE_GRAMMAR_SNAPSHOT_ABI ||
      reader->struct_bytes != sizeof(*reader) || (reader->count && !reader->frame))
    return LIE_GRAMMAR_INVALID;
  if (reader->count > p->d.limits.max_states)
    return LIE_GRAMMAR_STATE_LIMIT;
  lie_grammar_state *s = new_state(p);
  if (!s) return LIE_GRAMMAR_RESOURCE;
  lie_grammar_status rc = LIE_GRAMMAR_OK;
  for (size_t i = 0; rc == LIE_GRAMMAR_OK && i < reader->count; ++i) {
    lie_grammar_frame input = {0};
    frame copied = {0};
    rc = reader->frame(reader->context, i, &input);
    if (rc == LIE_GRAMMAR_OK && !valid_frame(p, input)) rc = LIE_GRAMMAR_INVALID;
    if (rc == LIE_GRAMMAR_OK) rc = copy_frame(s, input, 0, &copied);
    if (rc == LIE_GRAMMAR_OK) rc = push(s, &copied);
    release_frame(s, &copied);
  }
  if (rc != LIE_GRAMMAR_OK) { lie_grammar_state_release(s); return rc; }
  *out = s;
  return LIE_GRAMMAR_OK;
}
typedef struct { uintptr_t first, end; bool writable; } snapshot_span;
static bool snapshot_overlap(snapshot_span a, snapshot_span b) {
  return a.first < b.end && b.first < a.end;
}
static bool snapshot_add_span(snapshot_span *spans, size_t *count,
  const void *p, size_t n, size_t width, bool writable) {
  if (!n) return true;
  if (!p || n > SIZE_MAX / width) return false;
  size_t bytes = n * width;
  uintptr_t first = (uintptr_t)p;
  if (first > UINTPTR_MAX - bytes) return false;
  spans[(*count)++] = (snapshot_span){first, first + bytes, writable};
  return true;
}
static bool snapshot_less(snapshot_span a, snapshot_span b) {
  return a.first < b.first || (a.first == b.first && a.end < b.end);
}
static void snapshot_swap(snapshot_span *a, snapshot_span *b) {
  snapshot_span t = *a; *a = *b; *b = t;
}
static lie_grammar_status snapshot_sink(snapshot_span *v, size_t count, size_t at,
  size_t *work, size_t maximum) {
  while (at < count / 2) {
    if (*work >= maximum) return LIE_GRAMMAR_WORK_LIMIT;
    ++*work;
    size_t child = at * 2 + 1;
    if (child + 1 < count && snapshot_less(v[child], v[child + 1])) ++child;
    if (!snapshot_less(v[at], v[child])) break;
    snapshot_swap(v + at, v + child); at = child;
  }
  return LIE_GRAMMAR_OK;
}
static lie_grammar_status snapshot_disjoint(snapshot_span *v, size_t count,
  size_t maximum) {
  size_t work = 0;
  for (size_t i = count / 2; i; --i) {
    lie_grammar_status rc = snapshot_sink(v, count, i - 1, &work, maximum);
    if (rc != LIE_GRAMMAR_OK) return rc;
  }
  for (size_t i = count; i > 1; --i) {
    snapshot_swap(v, v + i - 1);
    lie_grammar_status rc = snapshot_sink(v, i - 1, 0, &work, maximum);
    if (rc != LIE_GRAMMAR_OK) return rc;
  }
  uintptr_t source_end = 0, output_end = 0;
  for (size_t i = 0; i < count; ++i) {
    if (v[i].writable) {
      if (v[i].first < source_end || v[i].first < output_end) return LIE_GRAMMAR_INVALID;
      output_end = v[i].end;
    } else {
      if (v[i].first < output_end) return LIE_GRAMMAR_INVALID;
      if (v[i].end > source_end) source_end = v[i].end;
    }
  }
  return LIE_GRAMMAR_OK;
}
lie_grammar_status lie_grammar_state_write(const lie_grammar_state *s,
  const lie_grammar_snapshot_writer *writer) {
  if (!s || !writer || writer->abi_version != LIE_GRAMMAR_SNAPSHOT_ABI ||
      writer->struct_bytes != sizeof(*writer) || !writer->prepare ||
      (s->count && !writer->frame)) return LIE_GRAMMAR_INVALID;
  const size_t width = sizeof(lie_grammar_writable_frame) + 4 * sizeof(snapshot_span);
  if (s->count > (SIZE_MAX - 2 * sizeof(snapshot_span)) / width) return LIE_GRAMMAR_RESOURCE;
  size_t allocation_bytes = s->count * width + 2 * sizeof(snapshot_span);
  void *memory = s->count ? s->allocator.allocate(s->allocator.context, allocation_bytes) : NULL;
  if (s->count && !memory) return LIE_GRAMMAR_RESOURCE;
  lie_grammar_writable_frame *plans = memory;
  snapshot_span *spans = s->count ? (snapshot_span *)(plans + s->count) : NULL;
  size_t span_count = 0;
  lie_grammar_status rc = LIE_GRAMMAR_OK;
  if (s->count && (!snapshot_add_span(spans, &span_count, s, 1, sizeof(*s), false) ||
      !snapshot_add_span(spans, &span_count, s->frames, s->capacity, sizeof(frame), false)))
    rc = LIE_GRAMMAR_INVALID;
  if (rc == LIE_GRAMMAR_OK) rc = writer->prepare(writer->context, s->count);
  for (size_t i = 0; rc == LIE_GRAMMAR_OK && i < s->count; ++i) {
    lie_grammar_frame input = view(s->frames + i);
    plans[i] = (lie_grammar_writable_frame){0};
    rc = writer->frame(writer->context, i, input.symbol_count, input.lexeme_bytes, plans + i);
    if (rc != LIE_GRAMMAR_OK) break;
    if (plans[i].symbol_capacity < input.symbol_count || plans[i].lexeme_capacity < input.lexeme_bytes ||
        !snapshot_add_span(spans, &span_count, s->frames[i].allocation, input.symbol_count * sizeof(uint32_t) + s->frames[i].capacity, 1, false) ||
        !snapshot_add_span(spans, &span_count, plans[i].symbols, plans[i].symbol_capacity, sizeof(uint32_t), true) ||
        !snapshot_add_span(spans, &span_count, plans[i].lexeme, plans[i].lexeme_capacity, 1, true)) {
      rc = LIE_GRAMMAR_INVALID; break;
    }
    snapshot_span plan_storage = {(uintptr_t)memory, (uintptr_t)memory + allocation_bytes, false};
    for (size_t j = span_count - (plans[i].symbol_capacity != 0) - (plans[i].lexeme_capacity != 0); j < span_count; ++j)
      if (snapshot_overlap(spans[j], plan_storage)) rc = LIE_GRAMMAR_INVALID;
  }
  if (rc == LIE_GRAMMAR_OK) rc = snapshot_disjoint(spans, span_count, s->limits.max_work);
  if (rc == LIE_GRAMMAR_OK)
    for (size_t i = 0; i < s->count; ++i) {
      const frame *f = s->frames + i;
      if (f->count) memcpy(plans[i].symbols, f->symbols, f->count * sizeof(uint32_t));
      if (f->bytes) memcpy(plans[i].lexeme, f->lexeme, f->bytes);
    }
  if (memory) s->allocator.release(s->allocator.context, memory);
  return rc;
}
size_t lie_grammar_state_count(const lie_grammar_state *s) {
  return s ? s->count : 0;
}
lie_grammar_status lie_grammar_state_frame(const lie_grammar_state *s, size_t i,
                                          lie_grammar_frame *out) {
  if (!s || !out || i >= s->count)
    return LIE_GRAMMAR_INVALID;
  *out = view(s->frames + i);
  return LIE_GRAMMAR_OK;
}
static int compare(const frame *a, const frame *b) {
  size_t n = a->count < b->count ? a->count : b->count;
  for (size_t i = 0; i < n; ++i)
    if (a->symbols[i] != b->symbols[i])
      return a->symbols[i] < b->symbols[i] ? -1 : 1;
  if (a->count != b->count)
    return a->count < b->count ? -1 : 1;
  n = a->bytes < b->bytes ? a->bytes : b->bytes;
  int c = n ? memcmp(a->lexeme, b->lexeme, n) : 0;
  if (c)
    return c;
  return (a->bytes > b->bytes) - (a->bytes < b->bytes);
}
int lie_grammar_state_compare(const lie_grammar_state *a,
                               const lie_grammar_state *b) {
  if (!a || !b)
    return (a != NULL) - (b != NULL);
  size_t n = a->count < b->count ? a->count : b->count;
  for (size_t i = 0; i < n; ++i) {
    int c = compare(a->frames + i, b->frames + i);
    if (c)
      return c;
  }
  return (a->count > b->count) - (a->count < b->count);
}
static uint64_t hash_word(uint64_t h, uint64_t n) {
  for (unsigned i = 0; i < 8; ++i) {
    h = (h ^ (uint8_t)n) * UINT64_C(1099511628211);
    n >>= 8;
  }
  return h;
}
uint64_t lie_grammar_state_hash(const lie_grammar_state *s) {
  uint64_t h = UINT64_C(14695981039346656037);
  if (!s)
    return h;
  h = hash_word(h, s->count);
  for (size_t i = 0; i < s->count; ++i) {
    const frame *f = s->frames + i;
    h = hash_word(h, f->count);
    for (size_t j = 0; j < f->count; ++j)
      h = hash_word(h, f->symbols[j]);
    h = hash_word(h, f->bytes);
    for (size_t j = 0; j < f->bytes; ++j)
      h = (h ^ f->lexeme[j]) * UINT64_C(1099511628211);
  }
  return h;
}
static void swap(frame *a, frame *b) {
  frame f = *a;
  *a = *b;
  *b = f;
}
static void sift(frame *p, size_t n, size_t root) {
  while (root < n / 2) {
    size_t child = root * 2 + 1;
    if (child + 1 < n && compare(p + child, p + child + 1) < 0)
      ++child;
    if (compare(p + root, p + child) >= 0)
      return;
    swap(p + root, p + child);
    root = child;
  }
}
static void canonicalize(lie_grammar_state *s) {
  for (size_t root = s->count / 2; root;)
    sift(s->frames, s->count, --root);
  for (size_t end = s->count; end > 1;) {
    swap(s->frames, s->frames + --end);
    sift(s->frames, end, 0);
  }
  size_t used = 0;
  for (size_t i = 0; i < s->count; ++i) {
    if (used && compare(s->frames + used - 1, s->frames + i) == 0)
      release_frame(s, s->frames + i);
    else {
      if (used != i) {
        s->frames[used] = s->frames[i];
        s->frames[i] = (frame){0};
      }
      ++used;
    }
  }
  s->count = used;
}
static lie_grammar_status expand_owned(const lie_grammar_program *p,
                                       lie_grammar_state *pending,
                                       lie_grammar_state **out) {
  lie_grammar_state *s = new_state(p);
  lie_grammar_status rc = s ? LIE_GRAMMAR_OK : LIE_GRAMMAR_RESOURCE;
  size_t work = 0;
  frame active = {0};
  while (rc == LIE_GRAMMAR_OK && pending->count) {
    if (++work > p->d.limits.max_work) {
      rc = LIE_GRAMMAR_WORK_LIMIT;
      break;
    }
    if (pending->count > p->d.limits.max_states - s->count) {
      rc = LIE_GRAMMAR_STATE_LIMIT;
      break;
    }
    active = pending->frames[--pending->count];
    if (!active.count || (active.symbols[active.count - 1] & LEAF)) {
      rc = push(s, &active);
      continue;
    }
    uint32_t rule = active.symbols[--active.count];
    lie_grammar_range alternatives = p->d.rules[rule];
    for (size_t i = 0; i < alternatives.count; ++i) {
      lie_grammar_range seq = p->d.sequences[alternatives.offset + i];
      if (seq.count > p->d.limits.max_stack - active.count) {
        rc = LIE_GRAMMAR_STACK_LIMIT;
        break;
      }
      lie_grammar_frame base = view(&active);
      /* Allocate the combined stack once; prefix/lexeme remain borrowed. */
      size_t n = active.count + seq.count;
      if (n > (SIZE_MAX - active.bytes) / sizeof(uint32_t)) {
        rc = LIE_GRAMMAR_RESOURCE;
        break;
      }
      size_t bytes = n * sizeof(uint32_t) + active.bytes;
      void *data = bytes ? pending->allocator.allocate(pending->allocator.context,
                                                       bytes) : NULL;
      if (bytes && !data) {
        rc = LIE_GRAMMAR_RESOURCE;
        break;
      }
      frame f = {.symbols = data, .count = n, .bytes = active.bytes,
                  .capacity = active.bytes, .allocation = data,
                  .lexeme = bytes ? (uint8_t *)data + n * sizeof(uint32_t) : NULL};
      if (base.symbol_count)
        memcpy(f.symbols, base.symbols, base.symbol_count * sizeof(uint32_t));
      for (size_t j = 0; j < seq.count; ++j)
        f.symbols[active.count + j] = p->d.symbols[seq.offset + seq.count - 1 - j];
      if (active.bytes)
        memcpy(f.lexeme, active.lexeme, active.bytes);
      rc = push(pending, &f);
      release_frame(pending, &f);
      if (rc != LIE_GRAMMAR_OK)
        break;
    }
    release_frame(pending, &active);
  }
  release_frame(pending, &active);
  lie_grammar_state_release(pending);
  if (rc != LIE_GRAMMAR_OK) {
    lie_grammar_state_release(s);
    return rc;
  }
  canonicalize(s);
  *out = s;
  return LIE_GRAMMAR_OK;
}
static lie_grammar_status copy_state(const lie_grammar_program *p,
                                     const lie_grammar_state *input,
                                     lie_grammar_state **out) {
  if (!p || !input || !out)
    return LIE_GRAMMAR_INVALID;
  if (input->count > p->d.limits.max_states)
    return LIE_GRAMMAR_STATE_LIMIT;
  for (size_t i = 0; i < input->count; ++i)
    if (!valid_frame(p, view(input->frames + i)))
      return LIE_GRAMMAR_INVALID;
  lie_grammar_state *s = new_state(p);
  if (!s)
    return LIE_GRAMMAR_RESOURCE;
  for (size_t i = 0; i < input->count; ++i) {
    frame f = {0};
    lie_grammar_status rc = copy_frame(s, view(input->frames + i), 0, &f);
    if (rc == LIE_GRAMMAR_OK)
      rc = push(s, &f);
    if (rc != LIE_GRAMMAR_OK) {
      release_frame(s, &f);
      lie_grammar_state_release(s);
      return rc;
    }
  }
  *out = s;
  return LIE_GRAMMAR_OK;
}
lie_grammar_status lie_grammar_state_clone(const lie_grammar_program *p,
                                          const lie_grammar_state *input,
                                          lie_grammar_state **out) {
  return copy_state(p, input, out);
}
lie_grammar_status lie_grammar_expand(const lie_grammar_program *p,
                                      const lie_grammar_state *input,
                                      lie_grammar_state **out) {
  if (!out)
    return LIE_GRAMMAR_INVALID;
  lie_grammar_state *pending = NULL;
  lie_grammar_status rc = copy_state(p, input, &pending);
  return rc == LIE_GRAMMAR_OK ? expand_owned(p, pending, out) : rc;
}
lie_grammar_status lie_grammar_start(const lie_grammar_program *p,
                                     lie_grammar_state **out) {
  if (!p || !out)
    return LIE_GRAMMAR_INVALID;
  lie_grammar_frame root = {&p->d.root, 1, NULL, 0};
  lie_grammar_state *pending = NULL;
  lie_grammar_status rc = lie_grammar_state_import(p, &root, 1, &pending);
  return rc == LIE_GRAMMAR_OK ? expand_owned(p, pending, out) : rc;
}
lie_grammar_status lie_grammar_advance(const lie_grammar_program *p,
                                      const lie_grammar_state *input,
                                      uint8_t byte, lie_grammar_state **out) {
  if (!p || !input || !out)
    return LIE_GRAMMAR_INVALID;
  lie_grammar_state *next = new_state(p);
  if (!next)
    return LIE_GRAMMAR_RESOURCE;
  lie_grammar_status rc = LIE_GRAMMAR_OK;
  frame active = {0};
  if (input->count > p->d.limits.max_states)
    rc = LIE_GRAMMAR_STATE_LIMIT;
  for (size_t i = 0; rc == LIE_GRAMMAR_OK && i < input->count; ++i) {
    const frame *f = input->frames + i;
    if (!valid_frame(p, view(f))) {
      rc = LIE_GRAMMAR_INVALID;
      break;
    }
    if (!f->count)
      continue;
    uint32_t leaf = f->symbols[f->count - 1];
    if (!(leaf & LEAF)) {
      rc = LIE_GRAMMAR_INVALID;
      break;
    }
    if (leaf & LIE_GRAMMAR_LEXEME) {
      uint32_t index = leaf & ~LEAF;
      if (!p->d.predicates.allows(p->d.predicates.context, index, byte))
        continue;
      rc = copy_frame(next, view(f), 64, &active);
      if (rc != LIE_GRAMMAR_OK)
        break;
      bool prefix = false, complete = false;
      rc = p->d.predicates.advance(p->d.predicates.context, index, active.lexeme,
          active.bytes, byte, active.lexeme, active.capacity, &active.bytes,
          &prefix, &complete);
      if (rc != LIE_GRAMMAR_OK || active.bytes > active.capacity) {
        if (rc == LIE_GRAMMAR_OK)
          rc = LIE_GRAMMAR_PREDICATE;
        break;
      }
      if (prefix && complete) {
        frame keep = {0};
        rc = copy_frame(next, view(&active), 0, &keep);
        if (rc == LIE_GRAMMAR_OK)
          rc = push(next, &keep);
        release_frame(next, &keep);
      }
      if (rc == LIE_GRAMMAR_OK && complete) {
        --active.count;
        active.bytes = 0;
        rc = push(next, &active);
      } else if (rc == LIE_GRAMMAR_OK && prefix)
        rc = push(next, &active);
    } else if (p->d.classes[(size_t)(leaf & ~LEAF) * 32 + byte / 8] &
               (1u << (byte % 8))) {
      rc = copy_frame(next, view(f), 0, &active);
      if (rc == LIE_GRAMMAR_OK) {
        --active.count;
        rc = push(next, &active);
      }
    }
    release_frame(next, &active);
  }
  release_frame(next, &active);
  if (rc != LIE_GRAMMAR_OK) {
    lie_grammar_state_release(next);
    return rc;
  }
  return expand_owned(p, next, out);
}
bool lie_grammar_complete(const lie_grammar_state *s) {
  if (s)
    for (size_t i = 0; i < s->count; ++i)
      if (!s->frames[i].count)
        return true;
  return false;
}
lie_grammar_status lie_grammar_canonical(const lie_grammar_program *p,
                                        const lie_grammar_state *input,
                                        size_t token_bytes,
                                        lie_grammar_state **out) {
  if (!out)
    return LIE_GRAMMAR_INVALID;
  lie_grammar_state *s = NULL;
  lie_grammar_status rc = copy_state(p, input, &s);
  if (rc != LIE_GRAMMAR_OK)
    return rc;
  if (p->d.predicates.canonical)
    for (size_t i = 0; i < s->count; ++i) {
      frame *f = s->frames + i;
      if (f->count && (f->symbols[f->count - 1] & LIE_GRAMMAR_LEXEME)) {
        rc = p->d.predicates.canonical(p->d.predicates.context,
            f->symbols[f->count - 1] & ~LEAF, f->lexeme, &f->bytes,
            f->capacity, token_bytes);
        if (rc != LIE_GRAMMAR_OK || f->bytes > f->capacity) {
          lie_grammar_state_release(s);
          return rc == LIE_GRAMMAR_OK ? LIE_GRAMMAR_PREDICATE : rc;
        }
      }
    }
  canonicalize(s);
  *out = s;
  return LIE_GRAMMAR_OK;
}
static bool overlap(const void *a, size_t an, const void *b, size_t bn) {
  if (!an || !bn)
    return false;
  uintptr_t x = (uintptr_t)a, y = (uintptr_t)b;
  return x > UINTPTR_MAX - an || y > UINTPTR_MAX - bn ||
         (x < y + bn && y < x + an);
}
lie_grammar_status lie_grammar_mask_logits(const float *logits, size_t count,
                                          const uint32_t *ids, size_t id_count,
                                          const uint8_t *mask, size_t vocabulary,
                                          float *output, size_t capacity) {
  if (!span(logits, count, sizeof(*logits)) ||
      !span(output, capacity, sizeof(*output)) || capacity < count ||
      !span(mask, vocabulary, 1) || !span(ids, id_count, sizeof(*ids)) ||
      (ids ? id_count != count : id_count != 0 || count != vocabulary) ||
      (logits != output && overlap(logits, count * sizeof(*logits), output,
                                   count * sizeof(*output))) ||
      overlap(ids, id_count * sizeof(*ids), output, count * sizeof(*output)) ||
      overlap(mask, vocabulary, output, count * sizeof(*output)))
    return LIE_GRAMMAR_INVALID;
  for (size_t i = 0; ids && i < count; ++i)
    if (ids[i] >= vocabulary)
      return LIE_GRAMMAR_INVALID;
  for (size_t i = 0; i < count; ++i)
    if (mask[ids ? ids[i] : i]) {
      if (output != logits)
        memcpy(output + i, logits + i, sizeof(float));
    }
    else
      output[i] = -INFINITY;
  return LIE_GRAMMAR_OK;
}
