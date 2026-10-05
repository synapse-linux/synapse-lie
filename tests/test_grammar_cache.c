/* SPDX-License-Identifier: MIT */
/* Independent ordered-policy, ownership, refusal and concurrent-use oracles. */
#include "lie/grammar_cache.h"
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef union {
  max_align_t alignment;
  size_t bytes;
} header;
typedef struct {
  atomic_size_t allocation_calls, live_allocations, live_bytes;
  atomic_size_t retain_calls, copy_calls, live_values, released_values;
  size_t fail_allocation, fail_retain, fail_copy;
  bool null_retain;
} fixture;
static size_t policy_oracles, refusals;
static void *allocate(void *p, size_t bytes) {
  fixture *f = p;
  if (atomic_fetch_add(&f->allocation_calls, 1) + 1 == f->fail_allocation)
    return NULL;
  header *h = malloc(sizeof(*h) + bytes);
  assert(h);
  h->bytes = bytes;
  atomic_fetch_add(&f->live_allocations, 1);
  atomic_fetch_add(&f->live_bytes, bytes);
  return h + 1;
}
static void release(void *p, void *v) {
  fixture *f = p;
  header *h = (header *)v - 1;
  assert(atomic_fetch_sub(&f->live_allocations, 1) > 0);
  assert(atomic_fetch_sub(&f->live_bytes, h->bytes) >= h->bytes);
  free(h);
}
static lie_grammar_cache_status retain(void *p, const void *v, void **out) {
  fixture *f = p;
  if (atomic_fetch_add(&f->retain_calls, 1) + 1 == f->fail_retain)
    return LIE_GRAMMAR_CACHE_CALLBACK;
  if (f->null_retain) {
    *out = NULL;
    return LIE_GRAMMAR_CACHE_OK;
  }
  int *owned = malloc(sizeof(*owned));
  assert(owned);
  *owned = *(const int *)v;
  atomic_fetch_add(&f->live_values, 1);
  *out = owned;
  return LIE_GRAMMAR_CACHE_OK;
}
static void retire(void *p, void *v) {
  fixture *f = p;
  assert(atomic_fetch_sub(&f->live_values, 1) > 0);
  atomic_fetch_add(&f->released_values, 1);
  free(v);
}
static lie_grammar_cache_status copy(void *p, const void *v, void *out) {
  fixture *f = p;
  if (atomic_fetch_add(&f->copy_calls, 1) + 1 == f->fail_copy)
    return LIE_GRAMMAR_CACHE_CALLBACK;
  *(int *)out = *(const int *)v;
  return LIE_GRAMMAR_CACHE_OK;
}
static lie_grammar_cache_description description(fixture *f, size_t capacity) {
  lie_grammar_cache_description d;
  lie_grammar_cache_description_init(&d);
  assert(d.max_entries == 16 && d.max_key_bytes == 2u * 1024u * 1024u);
  d.max_entries = capacity;
  d.max_key_bytes = 8;
  d.allocator = (lie_grammar_allocator){f, allocate, release};
  d.values = (lie_grammar_cache_values){f, retain, retire, copy};
  return d;
}
static lie_grammar_cache *make(fixture *f, size_t capacity) {
  lie_grammar_cache_description d = description(f, capacity);
  lie_grammar_cache *c = NULL;
  assert(lie_grammar_cache_create(&d, &c) == LIE_GRAMMAR_CACHE_OK && c);
  return c;
}
static void finished(fixture *f, lie_grammar_cache *c) {
  lie_grammar_cache_release(c);
  assert(!atomic_load(&f->live_values) && !atomic_load(&f->live_allocations) &&
         !atomic_load(&f->live_bytes));
}
static void expect(lie_grammar_cache *c, const uint8_t *key, size_t bytes,
                   bool expected, int wanted) {
  int out = -999;
  bool hit = !expected;
  assert(lie_grammar_cache_get(c, key, bytes, &out, &hit) ==
             LIE_GRAMMAR_CACHE_OK &&
         hit == expected);
  assert(out == (expected ? wanted : -999));
  ++policy_oracles;
}
static int put(lie_grammar_cache *c, const uint8_t *key, size_t bytes,
               int value) {
  int out = -999;
  assert(lie_grammar_cache_put(c, key, bytes, &value, &out) ==
         LIE_GRAMMAR_CACHE_OK);
  return out;
}
static void policy(size_t capacity) {
  fixture f = {0};
  lie_grammar_cache *c = make(&f, capacity);
  bool present[32] = {0};
  int values[32] = {0};
  size_t count = 0;
  /* Unsorted independent oracle: full puts evict the minimum before looking
   * for duplicates. Includes replacing that minimum and retaining others. */
  for (size_t step = 0; step < 300; ++step) {
    uint8_t key = (uint8_t)((step * 13 + step / 7) % 32);
    int value = (int)step + 100;
    if (count == capacity) {
      size_t smallest = 0;
      while (!present[smallest])
        ++smallest;
      present[smallest] = false;
      --count;
    }
    if (!present[key]) {
      present[key] = true;
      values[key] = value;
      ++count;
    }
    assert(put(c, &key, 1, value) == values[key]);
    lie_grammar_cache_info info = {999, 999};
    assert(lie_grammar_cache_inspect(c, &info) == LIE_GRAMMAR_CACHE_OK &&
           info.entries == count && info.key_bytes == count);
    for (uint8_t k = 0; k < 32; ++k)
      expect(c, &k, 1, present[k], values[k]);
  }
  finished(&f, c);
}
static void binary_keys(void) {
  fixture f = {0};
  lie_grammar_cache *c = make(&f, 3);
  uint8_t key[] = {0, 'b'}, first[] = {0, 'a'}, prefix[] = {0};
  assert(put(c, key, 2, 2) == 2);
  key[1] = 'z';
  const uint8_t original[] = {0, 'b'};
  expect(c, original, 2, true, 2);
  expect(c, key, 2, false, 0);
  assert(put(c, prefix, 1, 1) == 1);
  assert(put(c, NULL, 0, 0) == 0);
  assert(put(c, first, 2, 3) == 3);
  expect(c, NULL, 0, false, 0);
  expect(c, prefix, 1, true, 1);
  expect(c, first, 2, true, 3);
  expect(c, original, 2, true, 2);
  int copied = put(c, original, 2, 88);
  assert(copied == 2);
  expect(c, prefix, 1, false, 0);
  lie_grammar_cache_info info;
  assert(lie_grammar_cache_inspect(c, &info) == 0 && info.entries == 2 &&
         info.key_bytes == 4);
  finished(&f, c);
  assert(copied == 2);
  fixture empty = {0};
  lie_grammar_cache_description d = description(&empty, 1);
  d.max_key_bytes = 0;
  assert(lie_grammar_cache_create(&d, &c) == 0);
  assert(put(c, NULL, 0, 71) == 71);
  int out = 13;
  bool hit = true;
  assert(lie_grammar_cache_get(c, prefix, 1, &out, &hit) ==
             LIE_GRAMMAR_CACHE_KEY_LIMIT &&
         out == 13 && hit);
  ++refusals;
  finished(&empty, c);
}
static void failures(void) {
  for (size_t failure = 1; failure <= 2; ++failure) {
    fixture f = {0};
    f.fail_allocation = failure;
    lie_grammar_cache_description d = description(&f, 2);
    lie_grammar_cache *sentinel = (lie_grammar_cache *)(uintptr_t)1;
    assert(lie_grammar_cache_create(&d, &sentinel) ==
               LIE_GRAMMAR_CACHE_RESOURCE &&
           sentinel == (void *)(uintptr_t)1);
    assert(!atomic_load(&f.live_allocations) && !atomic_load(&f.live_bytes));
    ++refusals;
  }
  for (unsigned failure = 0; failure < 5; ++failure) {
    fixture f = {0};
    lie_grammar_cache *c = make(&f, 2);
    const uint8_t a = 'a', b = 'b', k = 'c';
    assert(put(c, &a, 1, 11) == 11 && put(c, &b, 1, 22) == 22);
    if (failure == 0)
      f.fail_allocation = atomic_load(&f.allocation_calls) + 1;
    if (failure == 1)
      f.fail_retain = atomic_load(&f.retain_calls) + 1;
    if (failure == 2)
      f.fail_copy = atomic_load(&f.copy_calls) + 1;
    if (failure == 3)
      f.null_retain = true;
    if (failure == 4)
      f.fail_copy = atomic_load(&f.copy_calls) + 1;
    int out = 777, value = 33;
    bool hit = true;
    lie_grammar_cache_status rc =
        failure == 4 ? lie_grammar_cache_get(c, &a, 1, &out, &hit)
                     : lie_grammar_cache_put(c, &k, 1, &value, &out);
    assert(rc == (failure == 0 ? LIE_GRAMMAR_CACHE_RESOURCE
                               : LIE_GRAMMAR_CACHE_CALLBACK));
    assert(out == 777 && hit);
    ++refusals;
    f.fail_allocation = f.fail_retain = f.fail_copy = 0;
    f.null_retain = false;
    expect(c, &a, 1, true, 11);
    expect(c, &b, 1, true, 22);
    expect(c, &k, 1, false, 0);
    lie_grammar_cache_info info;
    assert(lie_grammar_cache_inspect(c, &info) == 0 && info.entries == 2 &&
           info.key_bytes == 2);
    finished(&f, c);
  }
}
static void invalid(void) {
  fixture f = {0};
  lie_grammar_cache_description base = description(&f, 2);
  for (unsigned i = 0; i < 8; ++i) {
    lie_grammar_cache_description d = base;
    if (i == 0)
      ++d.abi_version;
    if (i == 1)
      --d.struct_bytes;
    if (i == 2)
      d.max_entries = 0;
    if (i == 3)
      d.max_entries = SIZE_MAX;
    if (i == 4)
      d.max_key_bytes = SIZE_MAX;
    if (i == 5)
      d.allocator.release = NULL;
    if (i == 6)
      d.values.copy = NULL;
    if (i == 7)
      d.values.retain = NULL;
    lie_grammar_cache *out = (lie_grammar_cache *)(uintptr_t)1;
    assert(lie_grammar_cache_create(&d, &out) == LIE_GRAMMAR_CACHE_INVALID &&
           out == (void *)(uintptr_t)1);
    ++refusals;
  }
  assert(lie_grammar_cache_create(NULL, NULL) == LIE_GRAMMAR_CACHE_INVALID);
  ++refusals;
  lie_grammar_cache *c = make(&f, 2);
  const uint8_t key = 'a';
  int out = 77, value = 7;
  bool hit = true;
  assert(lie_grammar_cache_get(NULL, &key, 1, &out, &hit) ==
         LIE_GRAMMAR_CACHE_INVALID);
  assert(lie_grammar_cache_get(c, NULL, 1, &out, &hit) ==
         LIE_GRAMMAR_CACHE_INVALID);
  assert(lie_grammar_cache_get(c, &key, 1, &out, NULL) ==
         LIE_GRAMMAR_CACHE_INVALID);
  assert(lie_grammar_cache_put(c, &key, 1, NULL, &out) ==
         LIE_GRAMMAR_CACHE_INVALID);
  assert(lie_grammar_cache_put(c, &key, 1, &value, NULL) ==
         LIE_GRAMMAR_CACHE_INVALID);
  assert(lie_grammar_cache_get(c, &key, 9, &out, &hit) ==
         LIE_GRAMMAR_CACHE_KEY_LIMIT);
  assert(out == 77 && hit);
  refusals += 6;
  finished(&f, c);
  lie_grammar_cache_release(NULL);
  lie_grammar_cache_description_init(NULL);
}
typedef struct {
  lie_grammar_cache *cache;
  unsigned id;
} worker;
static void *concurrent(void *p) {
  worker *w = p;
  for (unsigned i = 0; i < 1000; ++i) {
    uint8_t key[] = {0, (uint8_t)((i * 3 + w->id) % 8)};
    int value = key[1] + 100, out = -1;
    assert(lie_grammar_cache_put(w->cache, key, 2, &value, &out) == 0 &&
           out == value);
    bool hit = false;
    out = -1;
    assert(lie_grammar_cache_get(w->cache, key, 2, &out, &hit) == 0 &&
           (hit ? out == value : out == -1));
    lie_grammar_cache_info info;
    assert(lie_grammar_cache_inspect(w->cache, &info) == 0 &&
           info.entries <= 4 && info.key_bytes == 2 * info.entries);
  }
  return NULL;
}
int main(void) {
  policy(1);
  policy(2);
  policy(16);
  binary_keys();
  failures();
  invalid();
  fixture defaults = {0};
  lie_grammar_cache_description d = description(&defaults, 1);
  d.allocator = (lie_grammar_allocator){0};
  lie_grammar_cache *default_cache = NULL;
  assert(lie_grammar_cache_create(&d, &default_cache) == 0);
  assert(put(default_cache, NULL, 0, 93) == 93);
  finished(&defaults, default_cache);
  fixture f = {0};
  lie_grammar_cache *c = make(&f, 4);
  pthread_t threads[8];
  worker workers[8];
  for (unsigned i = 0; i < 8; ++i) {
    workers[i] = (worker){c, i};
    assert(!pthread_create(&threads[i], NULL, concurrent, &workers[i]));
  }
  for (unsigned i = 0; i < 8; ++i)
    assert(!pthread_join(threads[i], NULL));
  finished(&f, c);
  printf("C17 compiled-schema cache: PASS; policy_oracles=%zu refusals=%zu "
         "concurrent_operations=24000 HOST NOT-INFERENCE\n",
         policy_oracles, refusals);
  return 0;
}
