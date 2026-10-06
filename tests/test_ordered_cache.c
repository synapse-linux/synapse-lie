/* SPDX-License-Identifier: MIT */
/* Independent duplicate-before-eviction, transaction, ownership and race tests. */
#include "lie/ordered_cache.h"
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
typedef struct {
  atomic_size_t allocations, live, compares, copies, retained_keys, retained_values;
  size_t fail_allocate, fail_compare, fail_copy;
  bool refuse_key, refuse_value, null_key, null_value;
} fixture;
static size_t oracles, refusals;
static void *allocate(void *p, size_t bytes) {
  fixture *f = p;
  if (atomic_fetch_add(&f->allocations, 1) + 1 == f->fail_allocate) return NULL;
  void *out = malloc(bytes);
  assert(out);
  atomic_fetch_add(&f->live, 1);
  return out;
}
static void release(void *p, void *v) {
  fixture *f = p;
  assert(atomic_fetch_sub(&f->live, 1) > 0);
  free(v);
}
static lie_ordered_cache_status retain_key(void *p, const void *v, void **out) {
  fixture *f = p;
  if (f->refuse_key) return LIE_ORDERED_CACHE_CALLBACK;
  if (f->null_key) { *out = NULL; return LIE_ORDERED_CACHE_OK; }
  int *key = allocate(p, sizeof(*key));
  if (!key) return LIE_ORDERED_CACHE_RESOURCE;
  *key = *(const int *)v;
  atomic_fetch_add(&f->retained_keys, 1);
  *out = key;
  return LIE_ORDERED_CACHE_OK;
}
static lie_ordered_cache_status retain_value(void *p, const void *v, void **out) {
  fixture *f = p;
  if (f->refuse_value) return LIE_ORDERED_CACHE_CALLBACK;
  if (f->null_value) { *out = NULL; return LIE_ORDERED_CACHE_OK; }
  int *value = allocate(p, sizeof(*value));
  if (!value) return LIE_ORDERED_CACHE_RESOURCE;
  *value = *(const int *)v;
  atomic_fetch_add(&f->retained_values, 1);
  *out = value;
  return LIE_ORDERED_CACHE_OK;
}
static lie_ordered_cache_status compare(void *p, const void *a, const void *b, int *out) {
  fixture *f = p;
  if (atomic_fetch_add(&f->compares, 1) + 1 == f->fail_compare) return LIE_ORDERED_CACHE_CALLBACK;
  const int x = *(const int *)a, y = *(const int *)b;
  *out = (x > y) - (x < y);
  return LIE_ORDERED_CACHE_OK;
}
static lie_ordered_cache_status copy(void *p, const void *v, void *out) {
  fixture *f = p;
  if (atomic_fetch_add(&f->copies, 1) + 1 == f->fail_copy) return LIE_ORDERED_CACHE_CALLBACK;
  *(int *)out = *(const int *)v;
  return LIE_ORDERED_CACHE_OK;
}
static lie_ordered_cache_description description(fixture *f, size_t capacity) {
  lie_ordered_cache_description d;
  lie_ordered_cache_description_init(&d);
  assert(d.abi_version == 1 && d.max_entries == 16);
  d.max_entries = capacity;
  d.allocator = (lie_grammar_allocator){f, allocate, release};
  d.keys = (lie_ordered_cache_keys){f, retain_key, release, compare};
  d.values = (lie_ordered_cache_values){f, retain_value, release, copy};
  return d;
}
static lie_ordered_cache *make(fixture *f, size_t capacity) {
  const lie_ordered_cache_description d = description(f, capacity);
  lie_ordered_cache *c = NULL;
  assert(lie_ordered_cache_create(&d, &c) == LIE_ORDERED_CACHE_OK);
  return c;
}
static void finish(fixture *f, lie_ordered_cache *c) {
  lie_ordered_cache_release(c);
  assert(!atomic_load(&f->live));
}
static int put(lie_ordered_cache *c, int key, int value) {
  int out = -777;
  assert(lie_ordered_cache_put(c, &key, &value, &out) == LIE_ORDERED_CACHE_OK);
  return out;
}
static void expect(lie_ordered_cache *c, int key, bool present, int value) {
  int out = -777;
  bool hit = !present;
  assert(lie_ordered_cache_get(c, &key, &out, &hit) == LIE_ORDERED_CACHE_OK);
  assert(hit == present && out == (present ? value : -777));
  ++oracles;
}
static void policies(void) {
  fixture f = {0};
  lie_ordered_cache *c = make(&f, 4);
  bool present[29] = {0};
  int values[29] = {0};
  size_t count = 0;
  for (unsigned step = 0; step < 400; ++step) {
    const int key = (int)((step * 11 + step / 7) % 29), value = (int)step + 100;
    const bool duplicate = present[key];
    if (!duplicate) {
      if (count == 4) {
        int first = 0;
        while (!present[first]) ++first;
        present[first] = false;
        --count;
      }
      present[key] = true;
      values[key] = value;
      ++count;
    }
    const size_t allocations = atomic_load(&f.allocations);
    assert(put(c, key, value) == values[key]);
    if (duplicate) assert(atomic_load(&f.allocations) == allocations);
    for (int i = 0; i < 29; ++i) expect(c, i, present[i], values[i]);
    lie_ordered_cache_info info = {99};
    assert(lie_ordered_cache_inspect(c, &info) == LIE_ORDERED_CACHE_OK && info.entries == count);
    ++oracles;
  }
  finish(&f, c);
  // The minimum key survives a duplicate at capacity, including capacity1.
  c = make(&f, 1);
  assert(put(c, 3, 30) == 30 && put(c, 3, 99) == 30);
  expect(c, 3, true, 30);
  assert(put(c, 1, 10) == 10);
  expect(c, 3, false, 0); expect(c, 1, true, 10);
  finish(&f, c);
}
static void faults(void) {
  for (unsigned which = 0; which < 8; ++which) {
    fixture f = {0};
    lie_ordered_cache *c = make(&f, 2);
    assert(put(c, 10, 100) == 100 && put(c, 20, 200) == 200);
    const size_t live = atomic_load(&f.live);
    if (which < 2) f.fail_allocate = atomic_load(&f.allocations) + which + 1;
    if (which == 2) f.fail_compare = atomic_load(&f.compares) + 1;
    if (which == 3) f.fail_copy = atomic_load(&f.copies) + 1;
    f.refuse_key = which == 4; f.refuse_value = which == 5;
    f.null_key = which == 6; f.null_value = which == 7;
    int key = 30, value = 300, out = -777;
    const lie_ordered_cache_status rc = lie_ordered_cache_put(c, &key, &value, &out);
    assert(rc == (which < 2 ? LIE_ORDERED_CACHE_RESOURCE : LIE_ORDERED_CACHE_CALLBACK));
    assert(out == -777 && atomic_load(&f.live) == live);
    ++refusals;
    f.fail_allocate = f.fail_compare = f.fail_copy = 0;
    f.refuse_key = f.refuse_value = f.null_key = f.null_value = false;
    expect(c, 10, true, 100); expect(c, 20, true, 200); expect(c, 30, false, 0);
    finish(&f, c);
  }
  fixture f = {0};
  lie_ordered_cache *c = make(&f, 2);
  assert(put(c, 10, 100) == 100 && put(c, 20, 200) == 200);
  int key = 10, out = -777;
  bool hit = false;
  f.fail_compare = atomic_load(&f.compares) + 1;
  assert(lie_ordered_cache_get(c, &key, &out, &hit) == LIE_ORDERED_CACHE_CALLBACK && out == -777 && !hit);
  ++refusals;
  f.fail_compare = 0; f.fail_copy = atomic_load(&f.copies) + 1;
  assert(lie_ordered_cache_get(c, &key, &out, &hit) == LIE_ORDERED_CACHE_CALLBACK && out == -777 && !hit);
  ++refusals;
  f.fail_copy = atomic_load(&f.copies) + 1;
  assert(lie_ordered_cache_put(c, &key, &key, &out) == LIE_ORDERED_CACHE_CALLBACK && out == -777);
  ++refusals;
  f.fail_copy = 0;
  expect(c, 10, true, 100); expect(c, 20, true, 200);
  finish(&f, c);
  for (size_t at = 1; at <= 2; ++at) {
    fixture broken = {0}; broken.fail_allocate = at;
    lie_ordered_cache_description d = description(&broken, 2);
    lie_ordered_cache *sentinel = (lie_ordered_cache *)&broken;
    assert(lie_ordered_cache_create(&d, &sentinel) == LIE_ORDERED_CACHE_RESOURCE && sentinel == (lie_ordered_cache *)&broken);
    assert(!atomic_load(&broken.live)); ++refusals;
  }
}
typedef struct { lie_ordered_cache *cache; int value, winner; } task;
static void *race(void *p) {
  task *t = p;
  for (unsigned n = 0; n < 200; ++n) {
    const int key = 9;
    assert(lie_ordered_cache_put(t->cache, &key, &t->value, &t->winner) == LIE_ORDERED_CACHE_OK);
    int out = -1; bool hit = false;
    assert(lie_ordered_cache_get(t->cache, &key, &out, &hit) == LIE_ORDERED_CACHE_OK && hit && out == t->winner);
  }
  return NULL;
}
static void concurrent(void) {
  fixture f = {0}; lie_ordered_cache *c = make(&f, 1);
  pthread_t threads[8]; task tasks[8];
  for (size_t i = 0; i < 8; ++i) {
    tasks[i] = (task){c, (int)i + 100, 0};
    assert(!pthread_create(&threads[i], NULL, race, &tasks[i]));
  }
  for (size_t i = 0; i < 8; ++i) assert(!pthread_join(threads[i], NULL));
  for (size_t i = 0; i < 8; ++i) assert(tasks[i].winner == tasks[0].winner);
  assert(atomic_load(&f.retained_keys) == 1 && atomic_load(&f.retained_values) == 1);
  finish(&f, c);
}
static void invalid(void) {
  fixture f = {0}; const lie_ordered_cache_description valid = description(&f, 2);
  for (unsigned which = 0; which < 11; ++which) {
    lie_ordered_cache_description d = valid;
    if (which == 0) d.abi_version = 99;
    if (which == 1) --d.struct_bytes;
    if (which == 2) d.max_entries = 0;
    if (which == 3) d.max_entries = SIZE_MAX;
    if (which == 4) d.allocator.release = NULL;
    if (which == 5) d.keys.retain = NULL;
    if (which == 6) d.keys.release = NULL;
    if (which == 7) d.keys.compare = NULL;
    if (which == 8) d.values.retain = NULL;
    if (which == 9) d.values.release = NULL;
    if (which == 10) d.values.copy = NULL;
    lie_ordered_cache *sentinel = (lie_ordered_cache *)&f;
    assert(lie_ordered_cache_create(&d, &sentinel) == LIE_ORDERED_CACHE_INVALID && sentinel == (lie_ordered_cache *)&f);
    ++refusals;
  }
  lie_ordered_cache *c = make(&f, 2); int key = 1, out = -777; bool hit = false;
  assert(lie_ordered_cache_get(NULL, &key, &out, &hit) == LIE_ORDERED_CACHE_INVALID);
  assert(lie_ordered_cache_get(c, NULL, &out, &hit) == LIE_ORDERED_CACHE_INVALID);
  assert(lie_ordered_cache_get(c, &key, NULL, &hit) == LIE_ORDERED_CACHE_INVALID);
  assert(lie_ordered_cache_get(c, &key, &out, NULL) == LIE_ORDERED_CACHE_INVALID);
  assert(lie_ordered_cache_put(c, NULL, &key, &out) == LIE_ORDERED_CACHE_INVALID);
  assert(lie_ordered_cache_put(c, &key, NULL, &out) == LIE_ORDERED_CACHE_INVALID);
  assert(lie_ordered_cache_put(c, &key, &key, NULL) == LIE_ORDERED_CACHE_INVALID);
  assert(lie_ordered_cache_inspect(c, NULL) == LIE_ORDERED_CACHE_INVALID);
  assert(out == -777 && !hit); refusals += 8;
  finish(&f, c); lie_ordered_cache_release(NULL);
}
int main(void) {
  policies(); faults(); concurrent(); invalid();
  printf("C17 ordered cache: %zu independent oracles, %zu refusals, 1600 concurrent put/get pairs; HOST_NOT_INFERENCE\n", oracles, refusals);
}
