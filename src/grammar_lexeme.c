/* SPDX-License-Identifier: MIT */
/* C17 immutable ownership and ordered dispatch of the independently pinned
 * Gufo primitive semantics, using LIE's owned numeric/string/DFA algorithms. */
#include "lie/grammar_lexeme.h"
#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>

struct lie_grammar_lexeme {
  atomic_size_t references;
  lie_grammar_allocator allocator;
  size_t max_state_bytes;
  lie_lexeme_kind kind;
  uint8_t alphabet[32];
  union { const lie_number_policy *number; lie_string_policy string; } policy;
};
struct lie_lexeme_table {
  lie_lexeme_table_description description;
  const lie_grammar_lexeme **items;
  size_t count, capacity, live, peak, allocations;
  bool sealed;
};
typedef struct { const void *key; const lie_grammar_lexeme *value; } memo_entry;
struct lie_lexeme_memo {
  lie_lexeme_table_description description;
  memo_entry *entries;
  size_t count, capacity, live, peak, allocations;
};
static void *take(void *ctx, size_t bytes) { (void)ctx; return malloc(bytes); }
static void give(void *ctx, void *p) { (void)ctx; free(p); }
static bool allocator(lie_grammar_allocator input, lie_grammar_allocator *out) {
  if (!!input.allocate != !!input.release) return false;
  if (!input.allocate) input = (lie_grammar_allocator){NULL, take, give};
  *out = input; return true;
}
static lie_lexeme_status number_status(lie_number_status s) {
  if (s == LIE_NUMBER_OK) return LIE_LEXEME_OK;
  if (s == LIE_NUMBER_RESOURCE) return LIE_LEXEME_RESOURCE;
  if (s == LIE_NUMBER_WORK_LIMIT) return LIE_LEXEME_NUMBER_WORK;
  return LIE_LEXEME_INVALID;
}
static lie_lexeme_status string_status(lie_string_status s) {
  switch (s) {
  case LIE_STRING_OK: return LIE_LEXEME_OK;
  case LIE_STRING_RESOURCE: return LIE_LEXEME_RESOURCE;
  case LIE_STRING_WORK_LIMIT: return LIE_LEXEME_STRING_WORK;
  case LIE_STRING_STATE: return LIE_LEXEME_STRING_STATE;
  case LIE_STRING_PHASE: return LIE_LEXEME_STRING_PHASE;
  case LIE_STRING_EMPTY_LENGTH: return LIE_LEXEME_STRING_EMPTY_LENGTH;
  case LIE_STRING_EMPTY_PATTERN: return LIE_LEXEME_STRING_EMPTY_PATTERN;
  default: return LIE_LEXEME_INVALID;
  }
}
void lie_lexeme_description_init(lie_lexeme_description *d) {
  if (d) *d = (lie_lexeme_description){LIE_LEXEME_ABI, sizeof(*d), 64u * 1024u * 1024u, {0}};
}
static lie_lexeme_status create(const lie_lexeme_description *input,
                                lie_lexeme_kind kind, lie_grammar_lexeme **out) {
  lie_lexeme_description d; lie_lexeme_description_init(&d);
  if (input) d = *input;
  lie_grammar_allocator a;
  if (!out || d.abi_version != LIE_LEXEME_ABI || d.struct_bytes != sizeof(d) ||
      !d.max_state_bytes || !allocator(d.allocator, &a)) return LIE_LEXEME_INVALID;
  lie_grammar_lexeme *p = a.allocate(a.context, sizeof(*p));
  if (!p) return LIE_LEXEME_RESOURCE;
  memset(p, 0, sizeof(*p)); atomic_init(&p->references, 1);
  p->allocator = a; p->max_state_bytes = d.max_state_bytes; p->kind = kind;
  if (kind == LIE_LEXEME_STRING) memset(p->alphabet, 255, sizeof(p->alphabet));
  else {
    const char *allowed = kind == LIE_LEXEME_NUMBER ? "0123456789-." : " \t\r\n";
    for (; *allowed; ++allowed) {
      const unsigned byte = (unsigned char)*allowed;
      p->alphabet[byte / 8] |= (uint8_t)(1u << (byte % 8));
    }
  }
  *out = p; return LIE_LEXEME_OK;
}
lie_lexeme_status lie_lexeme_whitespace_create(const lie_lexeme_description *d, lie_grammar_lexeme **out) {
  return create(d, LIE_LEXEME_WHITESPACE, out);
}
lie_lexeme_status lie_lexeme_number_create(const lie_lexeme_description *d,
                                          const lie_number_policy *policy, lie_grammar_lexeme **out) {
  if (!policy || !out) return LIE_LEXEME_INVALID;
  lie_grammar_lexeme *p = NULL;
  lie_lexeme_status rc = create(d, LIE_LEXEME_NUMBER, &p);
  if (rc != LIE_LEXEME_OK) return rc;
  if (!lie_number_retain(policy)) { lie_lexeme_release(p); return LIE_LEXEME_RESOURCE; }
  p->policy.number = policy; *out = p; return LIE_LEXEME_OK;
}
lie_lexeme_status lie_lexeme_string_create(const lie_lexeme_description *d,
                                          const lie_string_policy *policy, lie_grammar_lexeme **out) {
  if (!policy || !out) return LIE_LEXEME_INVALID;
  lie_lexeme_status rc = string_status(lie_string_policy_validate(policy));
  if (rc != LIE_LEXEME_OK) return rc;
  lie_grammar_lexeme *p = NULL; rc = create(d, LIE_LEXEME_STRING, &p);
  if (rc != LIE_LEXEME_OK) return rc;
  if (!lie_regex_retain(policy->regex)) { lie_lexeme_release(p); return LIE_LEXEME_RESOURCE; }
  p->policy.string = *policy; *out = p; return LIE_LEXEME_OK;
}
bool lie_lexeme_retain(const lie_grammar_lexeme *lexeme) {
  if (!lexeme) return false;
  lie_grammar_lexeme *p = (lie_grammar_lexeme *)lexeme;
  size_t old = atomic_load_explicit(&p->references, memory_order_relaxed);
  while (old && old < SIZE_MAX) {
    if (atomic_compare_exchange_weak_explicit(&p->references, &old, old + 1,
          memory_order_relaxed, memory_order_relaxed)) return true;
  }
  return false;
}
void lie_lexeme_release(lie_grammar_lexeme *p) {
  if (!p || atomic_fetch_sub_explicit(&p->references, 1, memory_order_acq_rel) != 1) return;
  if (p->kind == LIE_LEXEME_NUMBER) lie_number_release((lie_number_policy *)p->policy.number);
  else if (p->kind == LIE_LEXEME_STRING) lie_regex_release((lie_regex_program *)p->policy.string.regex);
  p->allocator.release(p->allocator.context, p);
}
lie_lexeme_kind lie_lexeme_type(const lie_grammar_lexeme *p) { return p ? p->kind : LIE_LEXEME_WHITESPACE; }
const lie_number_policy *lie_lexeme_number_policy(const lie_grammar_lexeme *p) {
  return p && p->kind == LIE_LEXEME_NUMBER ? p->policy.number : NULL;
}
bool lie_lexeme_allows(const lie_grammar_lexeme *p, uint8_t b) {
  return p && (p->alphabet[b / 8] & (1u << (b % 8)));
}
bool lie_lexeme_cache_transitions(const lie_grammar_lexeme *p) { return p && p->kind != LIE_LEXEME_NUMBER; }
lie_lexeme_status lie_lexeme_check(const lie_grammar_lexeme *p, const uint8_t *text,
                                  size_t n, lie_lexeme_match *out) {
  if (!p || !out || (n && !text)) return LIE_LEXEME_INVALID;
  if (n > p->max_state_bytes) return LIE_LEXEME_LIMIT;
  lie_lexeme_match match = {true, false}; lie_lexeme_status rc = LIE_LEXEME_OK;
  if (p->kind == LIE_LEXEME_NUMBER) {
    lie_number_match m;
    rc = number_status(lie_number_check(p->policy.number, (lie_number_text){(const char *)text, n}, &m));
    if (rc == LIE_LEXEME_OK) match = (lie_lexeme_match){m.prefix, m.complete};
  } else if (p->kind == LIE_LEXEME_STRING) {
    lie_string_match m; rc = string_status(lie_string_check(&p->policy.string, text, n, &m));
    if (rc == LIE_LEXEME_OK) match = (lie_lexeme_match){m.prefix, m.complete};
  } else {
    uint8_t count = 0;
    for (size_t i = 0; i < n; ++i) {
      const lie_string_match m = lie_string_whitespace(&count, text[i]);
      match = (lie_lexeme_match){m.prefix, m.complete};
      if (!m.prefix && !m.complete) break;
    }
  }
  if (rc == LIE_LEXEME_OK) *out = match;
  return rc;
}
lie_lexeme_status lie_lexeme_advance(const lie_grammar_lexeme *p, const uint8_t *input,
                                    size_t n, uint8_t b, uint8_t *output, size_t cap,
                                    size_t *length, lie_lexeme_match *match) {
  if (!p || !length || !match || (n && !input) || (cap && !output)) return LIE_LEXEME_INVALID;
  if (n > p->max_state_bytes) return LIE_LEXEME_LIMIT;
  lie_lexeme_match m = {false, false}; lie_lexeme_status rc;
  if (p->kind == LIE_LEXEME_NUMBER) {
    if (n == SIZE_MAX || n + 1 > p->max_state_bytes) return LIE_LEXEME_LIMIT;
    if (cap < n + 1) return LIE_LEXEME_RESOURCE;
    if (n <= 4096) {
      uint8_t text[4097]; if (n) memcpy(text, input, n); text[n] = b;
      rc = lie_lexeme_check(p, text, n + 1, &m); if (rc != LIE_LEXEME_OK) return rc;
    } else {
      /* The numeric policy still owns its query scratch/refusal even when a
       * longer prefix is lexically impossible; it never reads such a span. */
      lie_number_match nm;
      rc = number_status(lie_number_check(p->policy.number, (lie_number_text){(const char *)input, n}, &nm));
      if (rc != LIE_LEXEME_OK) return rc;
      m = (lie_lexeme_match){nm.prefix, nm.complete};
    }
    if (n) memmove(output, input, n);
    output[n] = b; *length = n + 1; *match = m; return LIE_LEXEME_OK;
  }
  if (p->kind == LIE_LEXEME_STRING) {
    if (n && n != LIE_STRING_STATE_BYTES) return LIE_LEXEME_STRING_STATE;
    uint8_t state[LIE_STRING_STATE_BYTES] = {0}; if (n) memcpy(state, input, n);
    size_t bytes = n; lie_string_match sm;
    rc = string_status(lie_string_advance(&p->policy.string, state, &bytes, sizeof(state), b, &sm));
    if (rc != LIE_LEXEME_OK) return rc;
    if (bytes > cap) return LIE_LEXEME_RESOURCE;
    if (bytes > p->max_state_bytes) return LIE_LEXEME_LIMIT;
    if (bytes) memcpy(output, state, bytes);
    *length = bytes; *match = (lie_lexeme_match){sm.prefix, sm.complete}; return LIE_LEXEME_OK;
  }
  uint8_t count = n ? input[0] : 0;
  const lie_string_match sm = lie_string_whitespace(&count, b);
  const bool changed = sm.prefix || sm.complete;
  const size_t bytes = changed ? 1 : n;
  if (bytes > cap) return LIE_LEXEME_RESOURCE;
  if (changed) output[0] = count;
  else if (bytes) memmove(output, input, bytes);
  *length = bytes; *match = (lie_lexeme_match){sm.prefix, sm.complete}; return LIE_LEXEME_OK;
}
lie_lexeme_status lie_lexeme_canonical(const lie_grammar_lexeme *p, uint8_t *text,
                                      size_t n, size_t tokens) {
  if (!p || (n && !text)) return LIE_LEXEME_INVALID;
  if (n > p->max_state_bytes) return LIE_LEXEME_LIMIT;
  if (p->kind != LIE_LEXEME_STRING) return LIE_LEXEME_OK;
  if (n && n != LIE_STRING_STATE_BYTES) return LIE_LEXEME_STRING_STATE;
  uint8_t state[LIE_STRING_STATE_BYTES] = {0}; if (n) memcpy(state, text, n);
  lie_lexeme_status rc = string_status(lie_string_canonical(&p->policy.string, state, n, tokens));
  if (rc == LIE_LEXEME_OK && n) memcpy(text, state, n);
  return rc;
}
void lie_lexeme_table_description_init(lie_lexeme_table_description *d) {
  if (d) *d = (lie_lexeme_table_description){LIE_LEXEME_ABI, sizeof(*d), 262144,
                                          64u * 1024u * 1024u, {0}};
}
lie_lexeme_status lie_lexeme_table_create(const lie_lexeme_table_description *input,
                                        lie_lexeme_table **out) {
  lie_lexeme_table_description d; lie_lexeme_table_description_init(&d);
  if (input) d = *input;
  lie_grammar_allocator a;
  if (!out || d.abi_version != LIE_LEXEME_ABI || d.struct_bytes != sizeof(d) ||
      !d.max_items || !allocator(d.allocator, &a)) return LIE_LEXEME_INVALID;
  if (d.max_owned_bytes < sizeof(lie_lexeme_table)) return LIE_LEXEME_LIMIT;
  lie_lexeme_table *p = a.allocate(a.context, sizeof(*p)); if (!p) return LIE_LEXEME_RESOURCE;
  memset(p, 0, sizeof(*p)); d.allocator = a; p->description = d;
  p->live = p->peak = sizeof(*p); p->allocations = 1; *out = p; return LIE_LEXEME_OK;
}
void lie_lexeme_table_release(lie_lexeme_table *p) {
  if (!p) return;
  for (size_t i = 0; i < p->count; ++i) lie_lexeme_release((lie_grammar_lexeme *)p->items[i]);
  lie_grammar_allocator a = p->description.allocator;
  if (p->items) a.release(a.context, p->items);
  a.release(a.context, p);
}
lie_lexeme_status lie_lexeme_table_reserve(lie_lexeme_table *p, size_t n) {
  if (!p) return LIE_LEXEME_INVALID;
  if (p->sealed) return LIE_LEXEME_SEALED;
  if (n > p->description.max_items || n > SIZE_MAX / sizeof(*p->items)) return LIE_LEXEME_LIMIT;
  if (n <= p->capacity) return LIE_LEXEME_OK;
  const size_t bytes = n * sizeof(*p->items);
  if (bytes > p->description.max_owned_bytes - p->live) return LIE_LEXEME_LIMIT;
  const lie_grammar_lexeme **items = p->description.allocator.allocate(p->description.allocator.context, bytes);
  if (!items) return LIE_LEXEME_RESOURCE;
  if (p->count) memcpy(items, p->items, p->count * sizeof(*items));
  p->live += bytes; if (p->live > p->peak) p->peak = p->live; ++p->allocations;
  if (p->items) p->description.allocator.release(p->description.allocator.context, p->items);
  p->live -= p->capacity * sizeof(*p->items); p->capacity = n; p->items = items;
  return LIE_LEXEME_OK;
}
static lie_lexeme_status space(lie_lexeme_table *p, size_t n) {
  if (!p) return LIE_LEXEME_INVALID;
  if (p->sealed) return LIE_LEXEME_SEALED;
  if (n > p->description.max_items || n > SIZE_MAX / sizeof(*p->items)) return LIE_LEXEME_LIMIT;
  if (n <= p->capacity) return LIE_LEXEME_OK;
  size_t capacity = p->capacity ? p->capacity : 8;
  while (capacity < n && capacity <= p->description.max_items / 2) capacity *= 2;
  if (capacity < n || capacity > p->description.max_items) capacity = n;
  if (capacity > (p->description.max_owned_bytes - p->live) / sizeof(*p->items)) capacity = n;
  return lie_lexeme_table_reserve(p, capacity);
}
lie_lexeme_status lie_lexeme_table_push(lie_lexeme_table *p, const lie_grammar_lexeme *item) {
  if (!p || !item) return LIE_LEXEME_INVALID;
  if (p->count == SIZE_MAX) return LIE_LEXEME_LIMIT;
  lie_lexeme_status rc = space(p, p->count + 1); if (rc != LIE_LEXEME_OK) return rc;
  if (!lie_lexeme_retain(item)) return LIE_LEXEME_RESOURCE;
  p->items[p->count++] = item; return LIE_LEXEME_OK;
}
lie_lexeme_status lie_lexeme_table_append(lie_lexeme_table *p, const lie_lexeme_table *source,
                                        size_t first, size_t n) {
  if (!p || !source || first > source->count || n > source->count - first) return LIE_LEXEME_INVALID;
  if (n > SIZE_MAX - p->count) return LIE_LEXEME_LIMIT;
  lie_lexeme_status rc = space(p, p->count + n); if (rc != LIE_LEXEME_OK) return rc;
  size_t held = 0;
  for (; held < n; ++held) if (!lie_lexeme_retain(source->items[first + held])) break;
  if (held < n) {
    while (held) lie_lexeme_release((lie_grammar_lexeme *)source->items[first + --held]);
    return LIE_LEXEME_RESOURCE;
  }
  if (n) memmove(p->items + p->count, source->items + first, n * sizeof(*p->items));
  p->count += n; return LIE_LEXEME_OK;
}
lie_lexeme_status lie_lexeme_table_clone(const lie_lexeme_table *source,
                                       const lie_lexeme_table_description *d, lie_lexeme_table **out) {
  if (!source || !out) return LIE_LEXEME_INVALID;
  lie_lexeme_table *p = NULL; lie_lexeme_status rc = lie_lexeme_table_create(d, &p);
  if (rc == LIE_LEXEME_OK) rc = lie_lexeme_table_append(p, source, 0, source->count);
  if (rc != LIE_LEXEME_OK) { lie_lexeme_table_release(p); return rc; }
  *out = p; return LIE_LEXEME_OK;
}
size_t lie_lexeme_table_size(const lie_lexeme_table *p) { return p ? p->count : 0; }
const lie_grammar_lexeme *lie_lexeme_table_at(const lie_lexeme_table *p, size_t i) {
  return p && i < p->count ? p->items[i] : NULL;
}
lie_lexeme_status lie_lexeme_table_describe(const lie_lexeme_table *p, lie_lexeme_table_info *out) {
  if (!p || !out) return LIE_LEXEME_INVALID;
  *out = (lie_lexeme_table_info){p->count, p->capacity, p->live, p->peak, p->allocations, p->sealed};
  return LIE_LEXEME_OK;
}
lie_lexeme_status lie_lexeme_table_seal(lie_lexeme_table *p) {
  if (!p) return LIE_LEXEME_INVALID;
  if (!p->sealed) p->sealed = true;
  return LIE_LEXEME_OK;
}
static lie_grammar_status grammar_status(lie_lexeme_status rc) {
  if (rc == LIE_LEXEME_OK) return LIE_GRAMMAR_OK;
  return rc == LIE_LEXEME_RESOURCE || rc == LIE_LEXEME_LIMIT ? LIE_GRAMMAR_RESOURCE : LIE_GRAMMAR_PREDICATE;
}
static bool allows(const void *context, uint32_t id, uint8_t b) {
  return lie_lexeme_allows(lie_lexeme_table_at(context, id), b);
}
static lie_grammar_status advance(const void *context, uint32_t id, const uint8_t *input,
                                  size_t n, uint8_t b, uint8_t *output, size_t cap,
                                  size_t *length, bool *prefix, bool *complete) {
  if (!prefix || !complete) return LIE_GRAMMAR_INVALID;
  lie_lexeme_match match;
  lie_lexeme_status rc = lie_lexeme_advance(lie_lexeme_table_at(context, id), input, n, b, output, cap, length, &match);
  if (rc == LIE_LEXEME_OK) { *prefix = match.prefix; *complete = match.complete; }
  return grammar_status(rc);
}
static lie_grammar_status canonical(const void *context, uint32_t id, uint8_t *output,
                                    size_t *length, size_t cap, size_t tokens) {
  if (!length || *length > cap) return LIE_GRAMMAR_INVALID;
  return grammar_status(lie_lexeme_canonical(lie_lexeme_table_at(context, id), output, *length, tokens));
}
lie_grammar_predicates lie_lexeme_table_predicates(const lie_lexeme_table *p) {
  if (!p || !p->sealed) return (lie_grammar_predicates){0};
  return (lie_grammar_predicates){p, allows, advance, canonical};
}
bool lie_lexeme_table_cacheable(const void *context, const lie_grammar_state *state) {
  const lie_lexeme_table *p = context;
  if (!p || !p->sealed || !state) return false;
  for (size_t i = 0; i < lie_grammar_state_count(state); ++i) {
    lie_grammar_frame f;
    if (lie_grammar_state_frame(state, i, &f) != LIE_GRAMMAR_OK) return false;
    if (f.symbol_count && (f.symbols[f.symbol_count - 1] & LIE_GRAMMAR_LEXEME)) {
      const uint32_t id = f.symbols[f.symbol_count - 1] & ~LIE_GRAMMAR_LEXEME;
      if (!lie_lexeme_cache_transitions(lie_lexeme_table_at(p, id))) return false;
    }
  }
  return true;
}
static size_t memo_hash(const void *key) {
  uintptr_t x = (uintptr_t)key;
  x ^= x >> 4; x *= (uintptr_t)UINT32_C(0x9e3779b1); x ^= x >> 16;
  return (size_t)x;
}
static size_t memo_slot(const memo_entry *entries, size_t capacity, const void *key) {
  size_t slot = memo_hash(key) & (capacity - 1);
  while (entries[slot].key && entries[slot].key != key) slot = (slot + 1) & (capacity - 1);
  return slot;
}
lie_lexeme_status lie_lexeme_memo_create(const lie_lexeme_table_description *input, lie_lexeme_memo **out) {
  lie_lexeme_table_description d; lie_lexeme_table_description_init(&d);
  if (input) d = *input;
  lie_grammar_allocator a;
  if (!out || d.abi_version != LIE_LEXEME_ABI || d.struct_bytes != sizeof(d) ||
      !d.max_items || !allocator(d.allocator, &a)) return LIE_LEXEME_INVALID;
  if (d.max_owned_bytes < sizeof(lie_lexeme_memo)) return LIE_LEXEME_LIMIT;
  lie_lexeme_memo *p = a.allocate(a.context, sizeof(*p)); if (!p) return LIE_LEXEME_RESOURCE;
  memset(p, 0, sizeof(*p)); d.allocator = a; p->description = d;
  p->live = p->peak = sizeof(*p); p->allocations = 1; *out = p; return LIE_LEXEME_OK;
}
void lie_lexeme_memo_release(lie_lexeme_memo *p) {
  if (!p) return;
  for (size_t i = 0; i < p->capacity; ++i)
    if (p->entries[i].key) lie_lexeme_release((lie_grammar_lexeme *)p->entries[i].value);
  lie_grammar_allocator a = p->description.allocator;
  if (p->entries) a.release(a.context, p->entries);
  a.release(a.context, p);
}
const lie_grammar_lexeme *lie_lexeme_memo_get(const lie_lexeme_memo *p, const void *key) {
  if (!p || !key || !p->capacity) return NULL;
  return p->entries[memo_slot(p->entries, p->capacity, key)].value;
}
lie_lexeme_status lie_lexeme_memo_put(lie_lexeme_memo *p, const void *key, const lie_grammar_lexeme *value) {
  if (!p || !key || !value) return LIE_LEXEME_INVALID;
  if (lie_lexeme_memo_get(p, key)) return LIE_LEXEME_OK;
  if (p->count >= p->description.max_items) return LIE_LEXEME_LIMIT;
  if (!p->capacity || p->count >= p->capacity / 2) {
    if (p->capacity > SIZE_MAX / 2 / sizeof(memo_entry)) return LIE_LEXEME_LIMIT;
    size_t capacity = p->capacity ? p->capacity * 2 : 16;
    if (capacity > SIZE_MAX / sizeof(memo_entry)) return LIE_LEXEME_LIMIT;
    size_t bytes = capacity * sizeof(memo_entry);
    if (bytes > p->description.max_owned_bytes - p->live) return LIE_LEXEME_LIMIT;
    memo_entry *entries = p->description.allocator.allocate(p->description.allocator.context, bytes);
    if (!entries) return LIE_LEXEME_RESOURCE;
    memset(entries, 0, bytes);
    for (size_t i = 0; i < p->capacity; ++i) if (p->entries[i].key)
      entries[memo_slot(entries, capacity, p->entries[i].key)] = p->entries[i];
    p->live += bytes; if (p->live > p->peak) p->peak = p->live; ++p->allocations;
    if (p->entries) p->description.allocator.release(p->description.allocator.context, p->entries);
    p->live -= p->capacity * sizeof(memo_entry); p->capacity = capacity; p->entries = entries;
  }
  if (!lie_lexeme_retain(value)) return LIE_LEXEME_RESOURCE;
  p->entries[memo_slot(p->entries, p->capacity, key)] = (memo_entry){key, value};
  ++p->count; return LIE_LEXEME_OK;
}
lie_lexeme_status lie_lexeme_memo_describe(const lie_lexeme_memo *p, lie_lexeme_table_info *out) {
  if (!p || !out) return LIE_LEXEME_INVALID;
  *out = (lie_lexeme_table_info){p->count, p->capacity, p->live, p->peak, p->allocations, false};
  return LIE_LEXEME_OK;
}
