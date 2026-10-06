/* SPDX-License-Identifier: MIT */
#include "lie/grammar_lexeme.h"
#include <assert.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static size_t checks, failures;
#define CHECK(x) do { assert(x); ++checks; } while (0)
typedef struct { void *ptr[128]; size_t bytes[128], count, live, calls, fail; } heap;
static void *take(void *context, size_t bytes) {
  heap *h = context; if (++h->calls == h->fail) return NULL;
  void *p = malloc(bytes); assert(p && h->count < 128);
  h->ptr[h->count] = p; h->bytes[h->count++] = bytes; h->live += bytes; return p;
}
static void give(void *context, void *p) {
  heap *h = context; size_t i = 0; while (i < h->count && h->ptr[i] != p) ++i;
  CHECK(i < h->count); h->live -= h->bytes[i]; --h->count;
  h->ptr[i] = h->ptr[h->count]; h->bytes[i] = h->bytes[h->count]; free(p);
}
static lie_grammar_allocator allocator(heap *h) { return (lie_grammar_allocator){h, take, give}; }
static lie_number_policy *number(heap *h) {
  lie_number_description d; lie_number_description_init(&d);
  d.allocator = h ? allocator(h) : (lie_grammar_allocator){0};
  lie_number_policy *p = NULL; CHECK(lie_number_create(&d, &p) == LIE_NUMBER_OK); return p;
}
static lie_regex_program *regex(heap *h) {
  const lie_grammar_range classes[] = {{0, 1}, {1, 1}};
  const lie_unicode_range ranges[] = {{0, 0xd7ff}, {0xe000, 0x10ffff}};
  const uint8_t accepts[] = {1}; const uint32_t next[] = {0, 0};
  lie_regex_description d; lie_regex_description_init(&d);
  d.classes = classes; d.class_count = 2; d.ranges = ranges; d.range_count = 2;
  d.accepting = accepts; d.state_count = 1; d.transitions = next;
  d.allocator = h ? allocator(h) : (lie_grammar_allocator){0};
  lie_regex_program *p = NULL; CHECK(lie_regex_create(&d, &p) == LIE_REGEX_OK); return p;
}
static void primitive_ownership(void) {
  heap h = {0}; lie_lexeme_description d; lie_lexeme_description_init(&d); d.allocator = allocator(&h);
  lie_number_policy *n = number(&h); lie_grammar_lexeme *numeric = NULL, *space = NULL, *string = NULL;
  CHECK(lie_lexeme_number_create(&d, n, &numeric) == LIE_LEXEME_OK);
  lie_number_release(n); /* The C predicate independently retains its policy. */
  CHECK(lie_lexeme_whitespace_create(&d, &space) == LIE_LEXEME_OK);
  lie_regex_program *r = regex(&h); lie_string_policy p; lie_string_policy_init(&p);
  p.regex = r; p.scalar_only = true; p.minimum = 1; p.maximum = 128;
  CHECK(lie_lexeme_string_create(&d, &p, &string) == LIE_LEXEME_OK); lie_regex_release(r);
  p.minimum = 99; p.maximum = 99; p.regex = NULL; /* copied options, no borrowed C++ owner */
  lie_lexeme_match m;
  CHECK(lie_lexeme_check(numeric, (const uint8_t *)"1.25", 4, &m) == LIE_LEXEME_OK && m.complete);
  CHECK(lie_lexeme_check(string, (const uint8_t *)"\"a\\u0000b\"", 10, &m) == LIE_LEXEME_OK && m.complete);
  for (unsigned b = 0; b < 256; ++b) {
    CHECK(lie_lexeme_allows(string, (uint8_t)b));
    CHECK(lie_lexeme_allows(numeric, (uint8_t)b) == (strchr("0123456789-.", (int)b) != NULL && b != 0));
    CHECK(lie_lexeme_allows(space, (uint8_t)b) == (strchr(" \t\r\n", (int)b) != NULL && b != 0));
  }
  uint8_t output[64]; size_t bytes = 0;
  memset(output, 0x5c, sizeof(output)); m = (lie_lexeme_match){true, true}; bytes = 77;
  h.fail = h.calls + 1;
  CHECK(lie_lexeme_advance(numeric, (const uint8_t *)"2", 1, '.', output, sizeof(output), &bytes, &m) == LIE_LEXEME_RESOURCE);
  CHECK(bytes == 77 && m.prefix && m.complete && output[0] == 0x5c); h.fail = 0;
  uint8_t longer[5000], long_output[5001]; memset(longer, '1', sizeof(longer));
  memset(long_output, 0x5c, sizeof(long_output)); h.fail = h.calls + 1;
  CHECK(lie_lexeme_advance(numeric, longer, sizeof(longer), '2', long_output, sizeof(long_output), &bytes, &m) == LIE_LEXEME_RESOURCE);
  CHECK(bytes == 77 && m.prefix && m.complete && long_output[0] == 0x5c); h.fail = 0;
  CHECK(lie_lexeme_advance(numeric, (const uint8_t *)"1", 1, 'x', output, sizeof(output), &bytes, &m) == LIE_LEXEME_OK);
  CHECK(bytes == 2 && !memcmp(output, "1x", 2) && !m.prefix && !m.complete);
  memcpy(output, "123", 3);
  CHECK(lie_lexeme_advance(numeric, output, 3, '4', output + 1, 63, &bytes, &m) == LIE_LEXEME_OK);
  CHECK(bytes == 4 && !memcmp(output + 1, "1234", 4) && m.complete);
  uint8_t encoded[32] = {0}; bytes = 0;
  for (size_t i = 0; i < 32; ++i) {
    CHECK(lie_lexeme_advance(space, encoded, bytes, ' ', encoded, sizeof(encoded), &bytes, &m) == LIE_LEXEME_OK);
    CHECK(bytes == 1 && encoded[0] == i + 1 && m.complete && m.prefix == (i < 31));
  }
  CHECK(lie_lexeme_advance(space, encoded, bytes, ' ', encoded, sizeof(encoded), &bytes, &m) == LIE_LEXEME_OK);
  CHECK(bytes == 1 && encoded[0] == 32 && !m.complete && !m.prefix);
  bytes = 0;
  const char *text = "\"a\\u0000b\"";
  for (size_t i = 0; i < strlen(text); ++i)
    CHECK(lie_lexeme_advance(string, encoded, bytes, (uint8_t)text[i], encoded, sizeof(encoded), &bytes, &m) == LIE_LEXEME_OK);
  CHECK(m.complete && bytes == LIE_STRING_STATE_BYTES);
  uint8_t original[32]; memcpy(original, encoded, bytes);
  CHECK(lie_lexeme_canonical(string, encoded, bytes, 7) == LIE_LEXEME_OK);
  CHECK(!memcmp(original, encoded, 4)); /* DFA identity is unchanged. */
  lie_lexeme_release(string); lie_lexeme_release(space); lie_lexeme_release(numeric);
  CHECK(!h.count && !h.live);
}
static void tables(void) {
  heap h = {0}; lie_lexeme_table_description d; lie_lexeme_table_description_init(&d); d.allocator = allocator(&h);
  lie_lexeme_table *p = NULL; CHECK(lie_lexeme_table_create(&d, &p) == LIE_LEXEME_OK);
  lie_grammar_lexeme *ws = NULL; CHECK(lie_lexeme_whitespace_create(NULL, &ws) == LIE_LEXEME_OK);
  for (size_t i = 0; i < 65; ++i) CHECK(lie_lexeme_table_push(p, ws) == LIE_LEXEME_OK);
  lie_lexeme_release(ws);
  CHECK(lie_lexeme_table_size(p) == 65 && !lie_lexeme_table_at(p, 65));
  const lie_grammar_lexeme *identity = lie_lexeme_table_at(p, 0);
  CHECK(lie_lexeme_table_append(p, p, 1, 64) == LIE_LEXEME_OK && lie_lexeme_table_size(p) == 129);
  for (size_t i = 0; i < 129; ++i) CHECK(lie_lexeme_table_at(p, i) == identity);
  lie_lexeme_table_info info; CHECK(lie_lexeme_table_describe(p, &info) == LIE_LEXEME_OK);
  CHECK(info.live_owned_bytes == h.live && info.peak_owned_bytes > info.live_owned_bytes);
  CHECK(lie_lexeme_table_seal(p) == LIE_LEXEME_OK);
  CHECK(lie_lexeme_table_reserve(p, 0) == LIE_LEXEME_SEALED);
  CHECK(lie_lexeme_table_push(p, identity) == LIE_LEXEME_SEALED);
  lie_lexeme_table *clone = NULL; CHECK(lie_lexeme_table_clone(p, &d, &clone) == LIE_LEXEME_OK);
  CHECK(lie_lexeme_table_push(clone, identity) == LIE_LEXEME_OK);
  lie_lexeme_table_release(p); /* clone retains all predicate identities */
  CHECK(lie_lexeme_table_size(clone) == 130 && lie_lexeme_table_at(clone, 0) == identity);
  CHECK(lie_lexeme_table_seal(clone) == LIE_LEXEME_OK);
  const lie_grammar_range rules[] = {{0, 1}}, sequences[] = {{0, 1}};
  const uint32_t symbols[] = {LIE_GRAMMAR_LEXEME};
  lie_grammar_description g; lie_grammar_description_init(&g);
  g.rules = rules; g.rule_count = 1; g.sequences = sequences; g.sequence_count = 1;
  g.symbols = symbols; g.symbol_count = 1; g.lexeme_count = lie_lexeme_table_size(clone);
  g.predicates = lie_lexeme_table_predicates(clone);
  lie_grammar_program *program = NULL; CHECK(lie_grammar_program_create(&g, &program) == LIE_GRAMMAR_OK);
  lie_grammar_state *state = NULL, *next = NULL; CHECK(lie_grammar_start(program, &state) == LIE_GRAMMAR_OK);
  CHECK(lie_lexeme_table_cacheable(clone, state));
  CHECK(lie_grammar_advance(program, state, ' ', &next) == LIE_GRAMMAR_OK && lie_grammar_complete(next));
  lie_grammar_state_release(next); lie_grammar_state_release(state); lie_grammar_program_release(program);
  for (size_t fail = 1; fail <= 2; ++fail) {
    h.fail = h.calls + fail; lie_lexeme_table *sentinel = (lie_lexeme_table *)(uintptr_t)1;
    CHECK(lie_lexeme_table_clone(clone, &d, &sentinel) == LIE_LEXEME_RESOURCE);
    CHECK(sentinel == (lie_lexeme_table *)(uintptr_t)1 && lie_lexeme_table_size(clone) == 130);
    ++failures; h.fail = 0;
  }
  lie_lexeme_table_release(clone); CHECK(!h.count && !h.live);
  d.max_items = 1; CHECK(lie_lexeme_table_create(&d, &p) == LIE_LEXEME_OK);
  CHECK(lie_lexeme_whitespace_create(NULL, &ws) == LIE_LEXEME_OK);
  CHECK(lie_lexeme_table_push(p, ws) == LIE_LEXEME_OK);
  CHECK(lie_lexeme_table_push(p, ws) == LIE_LEXEME_LIMIT && lie_lexeme_table_size(p) == 1);
  lie_lexeme_release(ws); lie_lexeme_table_release(p); CHECK(!h.count && !h.live);
}
static void *reader(void *context) {
  const lie_grammar_lexeme *p = context;
  for (size_t i = 0; i < 64; ++i) {
    assert(lie_lexeme_retain(p)); lie_lexeme_match m;
    assert(lie_lexeme_check(p, (const uint8_t *)"1.25", 4, &m) == LIE_LEXEME_OK && m.complete);
    lie_lexeme_release((lie_grammar_lexeme *)p);
  }
  return NULL;
}
static void memo(void) {
  heap h = {0}; lie_lexeme_table_description d; lie_lexeme_table_description_init(&d);
  d.allocator = allocator(&h); d.max_items = 257;
  lie_lexeme_memo *p = (lie_lexeme_memo *)(uintptr_t)1;
  h.fail = 1; CHECK(lie_lexeme_memo_create(&d, &p) == LIE_LEXEME_RESOURCE);
  CHECK(p == (lie_lexeme_memo *)(uintptr_t)1 && !h.count); ++failures; h.fail = 0;
  CHECK(lie_lexeme_memo_create(&d, &p) == LIE_LEXEME_OK);
  unsigned keys[258] = {0}; lie_grammar_lexeme *ws = NULL;
  CHECK(lie_lexeme_whitespace_create(NULL, &ws) == LIE_LEXEME_OK);
  for (size_t i = 0; i < 257; ++i) {
    CHECK(!lie_lexeme_memo_get(p, keys + i));
    if (i == 8) {
      h.fail = h.calls + 1;
      CHECK(lie_lexeme_memo_put(p, keys + i, ws) == LIE_LEXEME_RESOURCE);
      CHECK(!lie_lexeme_memo_get(p, keys + i)); ++failures; h.fail = 0;
    }
    CHECK(lie_lexeme_memo_put(p, keys + i, ws) == LIE_LEXEME_OK);
    for (size_t j = 0; j <= i; ++j) CHECK(lie_lexeme_memo_get(p, keys + j) == ws);
  }
  lie_lexeme_release(ws); /* memo independently retains every publication */
  CHECK(lie_lexeme_memo_put(p, keys + 257, lie_lexeme_memo_get(p, keys)) == LIE_LEXEME_LIMIT);
  lie_number_policy *number_policy = number(NULL); lie_grammar_lexeme *numeric = NULL;
  CHECK(lie_lexeme_number_create(NULL, number_policy, &numeric) == LIE_LEXEME_OK);
  lie_number_release(number_policy);
  CHECK(lie_lexeme_memo_put(p, keys, numeric) == LIE_LEXEME_OK);
  CHECK(lie_lexeme_type(lie_lexeme_memo_get(p, keys)) == LIE_LEXEME_WHITESPACE);
  lie_lexeme_release(numeric);
  lie_lexeme_table_info info; CHECK(lie_lexeme_memo_describe(p, &info) == LIE_LEXEME_OK);
  CHECK(info.count == 257 && info.live_owned_bytes == h.live && info.peak_owned_bytes > h.live);
  lie_lexeme_memo_release(p); CHECK(!h.count && !h.live);
}
static void refusals(void) {
  heap h = {0}; lie_lexeme_description d; lie_lexeme_description_init(&d);
  d.allocator = allocator(&h);
  lie_grammar_lexeme *sentinel = (lie_grammar_lexeme *)(uintptr_t)1;
  d.abi_version++;
  CHECK(lie_lexeme_whitespace_create(&d, &sentinel) == LIE_LEXEME_INVALID);
  CHECK(sentinel == (lie_grammar_lexeme *)(uintptr_t)1 && !h.calls);
  lie_lexeme_description_init(&d); d.allocator = allocator(&h); d.allocator.release = NULL;
  CHECK(lie_lexeme_whitespace_create(&d, &sentinel) == LIE_LEXEME_INVALID);
  d.allocator = allocator(&h); h.fail = h.calls + 1;
  CHECK(lie_lexeme_whitespace_create(&d, &sentinel) == LIE_LEXEME_RESOURCE);
  CHECK(sentinel == (lie_grammar_lexeme *)(uintptr_t)1 && !h.live); ++failures; h.fail = 0;
  lie_number_policy *n = number(&h);
  h.fail = h.calls + 1;
  CHECK(lie_lexeme_number_create(&d, n, &sentinel) == LIE_LEXEME_RESOURCE);
  CHECK(sentinel == (lie_grammar_lexeme *)(uintptr_t)1); ++failures; h.fail = 0;
  lie_number_match nm; CHECK(lie_number_check(n, (lie_number_text){"2", 1}, &nm) == LIE_NUMBER_OK && nm.complete);
  lie_number_release(n);
  lie_regex_program *r = regex(&h); lie_string_policy sp; lie_string_policy_init(&sp); sp.regex = r;
  h.fail = h.calls + 1;
  CHECK(lie_lexeme_string_create(&d, &sp, &sentinel) == LIE_LEXEME_RESOURCE);
  CHECK(sentinel == (lie_grammar_lexeme *)(uintptr_t)1); ++failures; h.fail = 0;
  sp.minimum = 2; sp.maximum = 1;
  CHECK(lie_lexeme_string_create(&d, &sp, &sentinel) == LIE_LEXEME_STRING_EMPTY_LENGTH);
  lie_regex_release(r); CHECK(!h.count && !h.live);

  d.max_state_bytes = 1; lie_grammar_lexeme *ws = NULL;
  CHECK(lie_lexeme_whitespace_create(&d, &ws) == LIE_LEXEME_OK);
  uint8_t output[2] = {0x5c, 0x5c}; size_t bytes = 77; lie_lexeme_match match = {true, true};
  CHECK(lie_lexeme_advance(ws, NULL, 0, ' ', output, 0, &bytes, &match) == LIE_LEXEME_RESOURCE);
  CHECK(bytes == 77 && match.prefix && match.complete && output[0] == 0x5c);
  CHECK(lie_lexeme_check(ws, (const uint8_t *)"  ", 2, &match) == LIE_LEXEME_LIMIT);
  CHECK(lie_lexeme_check(ws, NULL, 1, &match) == LIE_LEXEME_INVALID);
  CHECK(match.prefix && match.complete);
  lie_lexeme_table_description td; lie_lexeme_table_description_init(&td); td.allocator = allocator(&h);
  lie_lexeme_table *table = NULL;
  CHECK(lie_lexeme_table_create(&td, &table) == LIE_LEXEME_OK);
  CHECK(!lie_lexeme_table_predicates(table).advance);
  CHECK(lie_lexeme_table_push(table, ws) == LIE_LEXEME_OK);
  lie_lexeme_table_info before, after;
  CHECK(lie_lexeme_table_describe(table, &before) == LIE_LEXEME_OK);
  h.fail = h.calls + 1;
  CHECK(lie_lexeme_table_reserve(table, before.capacity + 1) == LIE_LEXEME_RESOURCE); ++failures; h.fail = 0;
  CHECK(lie_lexeme_table_describe(table, &after) == LIE_LEXEME_OK);
  CHECK(before.count == after.count && before.capacity == after.capacity && before.live_owned_bytes == after.live_owned_bytes &&
        before.peak_owned_bytes == after.peak_owned_bytes && before.allocations == after.allocations && before.sealed == after.sealed);
  CHECK(lie_lexeme_table_append(table, table, 1, 1) == LIE_LEXEME_INVALID && lie_lexeme_table_size(table) == 1);
  CHECK(lie_lexeme_table_seal(table) == LIE_LEXEME_OK);
  lie_grammar_predicates hooks = lie_lexeme_table_predicates(table);
  bool prefix = true, complete = true;
  CHECK(hooks.advance(hooks.context, 1, NULL, 0, ' ', output, 2, &bytes, &prefix, &complete) == LIE_GRAMMAR_PREDICATE);
  CHECK(bytes == 77 && prefix && complete && output[0] == 0x5c);
  CHECK(hooks.advance(hooks.context, 0, NULL, 0, ' ', output, 0, &bytes, &prefix, &complete) == LIE_GRAMMAR_RESOURCE);
  CHECK(bytes == 77 && prefix && complete && output[0] == 0x5c);
  CHECK(lie_lexeme_table_append(table, table, 0, 0) == LIE_LEXEME_SEALED);
  lie_lexeme_table_release(table);
  /* Budgets include body and overlapping growth buffers, without leaf costs. */
  td.max_owned_bytes = before.live_owned_bytes;
  CHECK(lie_lexeme_table_create(&td, &table) == LIE_LEXEME_OK);
  CHECK(lie_lexeme_table_reserve(table, before.capacity) == LIE_LEXEME_OK);
  CHECK(lie_lexeme_table_push(table, ws) == LIE_LEXEME_OK);
  CHECK(lie_lexeme_table_reserve(table, before.capacity + 1) == LIE_LEXEME_LIMIT && lie_lexeme_table_size(table) == 1);
  CHECK(lie_lexeme_table_at(table, 0) == ws);
  lie_lexeme_table_release(table); lie_lexeme_release(ws); CHECK(!h.count && !h.live);
  CHECK(!lie_lexeme_retain(NULL) && !lie_number_retain(NULL) && !lie_regex_retain(NULL));
}
typedef struct { const lie_lexeme_table *table; const lie_lexeme_memo *memo; const void *key; } shared_tables;
static void *table_reader(void *context) {
  const shared_tables *shared = context;
  const lie_grammar_lexeme *p = lie_lexeme_table_at(shared->table, 0);
  const lie_grammar_predicates hooks = lie_lexeme_table_predicates(shared->table);
  for (size_t i = 0; i < 64; ++i) {
    assert(lie_lexeme_memo_get(shared->memo, shared->key) == p);
    assert(hooks.allows(hooks.context, 0, ' '));
    uint8_t output[1]; size_t length = 0; bool prefix = false, complete = false;
    assert(hooks.advance(hooks.context, 0, NULL, 0, ' ', output, 1, &length, &prefix, &complete) == LIE_GRAMMAR_OK);
    assert(length == 1 && output[0] == 1 && prefix && complete);
  }
  return NULL;
}
static void table_readers(void) {
  lie_lexeme_table *table = NULL; lie_lexeme_memo *memo = NULL; lie_grammar_lexeme *ws = NULL;
  CHECK(lie_lexeme_table_create(NULL, &table) == LIE_LEXEME_OK);
  CHECK(lie_lexeme_memo_create(NULL, &memo) == LIE_LEXEME_OK);
  CHECK(lie_lexeme_whitespace_create(NULL, &ws) == LIE_LEXEME_OK);
  unsigned key = 0;
  CHECK(lie_lexeme_table_push(table, ws) == LIE_LEXEME_OK);
  CHECK(lie_lexeme_memo_put(memo, &key, ws) == LIE_LEXEME_OK);
  lie_lexeme_release(ws); CHECK(lie_lexeme_table_seal(table) == LIE_LEXEME_OK);
  shared_tables shared = {table, memo, &key}; pthread_t threads[8];
  for (size_t i = 0; i < 8; ++i) CHECK(!pthread_create(threads + i, NULL, table_reader, &shared));
  for (size_t i = 0; i < 8; ++i) CHECK(!pthread_join(threads[i], NULL));
  lie_lexeme_table_release(table); lie_lexeme_memo_release(memo);
}
int main(void) {
  primitive_ownership(); tables(); memo(); refusals(); table_readers();
  lie_number_policy *n = number(NULL); lie_grammar_lexeme *p = NULL;
  CHECK(lie_lexeme_number_create(NULL, n, &p) == LIE_LEXEME_OK); lie_number_release(n);
  pthread_t threads[8]; for (size_t i = 0; i < 8; ++i) CHECK(!pthread_create(threads + i, NULL, reader, p));
  for (size_t i = 0; i < 8; ++i) CHECK(!pthread_join(threads[i], NULL));
  lie_lexeme_release(p);
  printf("C17 LEXEMES checks=%zu ownership_allocator_refusals=%zu numeric_query_refusals=2 joined_readers=16 read_iterations=1024 HOST_NOT_INFERENCE\n", checks, failures);
  return 0;
}
