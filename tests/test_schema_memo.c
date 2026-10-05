/* SPDX-License-Identifier: MIT */
#include "lie/schema_memo.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
enum { N = 4096 };
static unsigned char nodes[N + 1];
static size_t checks, refusals;
typedef struct {
  size_t calls, fail, live, bytes;
} allocator;
typedef union {
  max_align_t alignment;
  size_t bytes;
} allocation;
static void *alloc(void *p, size_t bytes) {
  allocator *a = p;
  if (++a->calls == a->fail)
    return NULL;
  allocation *h = malloc(sizeof(*h) + bytes);
  assert(h);
  h->bytes = bytes;
  ++a->live;
  a->bytes += bytes;
  return h + 1;
}
static void free_block(void *p, void *v) {
  allocator *a = p;
  allocation *h = (allocation *)v - 1;
  assert(a->live && a->bytes >= h->bytes);
  --a->live;
  a->bytes -= h->bytes;
  free(h);
}
static void compare(lie_schema_memo *m, const bool *present,
                    const uint32_t *values, size_t count) {
  for (size_t i = 0; i <= N; ++i) {
    uint32_t value = UINT32_C(0x12345678);
    bool hit = true;
    assert(lie_schema_memo_get(m, nodes + i, &value, &hit) == LIE_SCHEMA_OK);
    assert(hit == present[i]);
    assert(value == (hit ? values[i] : UINT32_C(0x12345678)));
    ++checks;
  }
  lie_schema_memo_info info;
  assert(lie_schema_memo_inspect(m, &info) == LIE_SCHEMA_OK);
  assert(info.entries == count && (count == 0 || info.slots >= 2 * count));
}
static size_t scenario(size_t fail) {
  allocator a = {.fail = fail};
  lie_schema_memo_description d;
  lie_schema_memo_description_init(&d);
  d.max_entries = N;
  d.allocator = (lie_grammar_allocator){&a, alloc, free_block};
  lie_schema_memo *m = (void *)&nodes;
  lie_schema_status rc = lie_schema_memo_create(&d, &m);
  if (rc) {
    assert(rc == LIE_SCHEMA_RESOURCE && m == (void *)&nodes);
    ++refusals;
  } else {
    bool present[N + 1] = {false};
    uint32_t values[N + 1] = {0};
    size_t count = 0;
    compare(m, present, values, count);
    for (size_t j = 0; j < N; j++) {
      /* Odd multiplication permutes this power-of-two domain; no hash oracle.
       */
      size_t i = (j * 2053 + 73) % N;
      uint32_t value = (uint32_t)(j * 7927);
      lie_schema_memo_info before, after;
      assert(lie_schema_memo_inspect(m, &before) == LIE_SCHEMA_OK);
      rc = lie_schema_memo_assign(m, nodes + i, value);
      if (rc) {
        assert(rc == LIE_SCHEMA_RESOURCE);
        assert(lie_schema_memo_inspect(m, &after) == LIE_SCHEMA_OK);
        assert(before.entries == after.entries && before.slots == after.slots &&
               before.allocated_bytes == after.allocated_bytes);
        compare(m, present, values, count);
        ++refusals;
        rc = lie_schema_memo_assign(m, nodes + i, value);
        assert(rc == LIE_SCHEMA_OK);
      }
      present[i] = true;
      values[i] = value;
      ++count;
      assert(lie_schema_memo_inspect(m, &after) == LIE_SCHEMA_OK);
      assert(after.allocated_bytes == a.bytes);
      if (j % 256 == 0)
        compare(m, present, values, count);
    }
    size_t calls = a.calls;
    assert(lie_schema_memo_assign(m, nodes + N, 0) == LIE_SCHEMA_WORK_LIMIT);
    ++refusals;
    assert(a.calls == calls);
    for (size_t i = 0; i < N; i++) {
      values[i] = i % 2 ? UINT32_MAX : 0;
      assert(lie_schema_memo_assign(m, nodes + i, values[i]) == LIE_SCHEMA_OK);
    }
    assert(a.calls == calls);
    compare(m, present, values, count);
    uint32_t v = 19;
    bool hit = true;
    assert(lie_schema_memo_get(m, NULL, &v, &hit) == LIE_SCHEMA_INVALID &&
           v == 19 && hit);
    assert(lie_schema_memo_assign(m, NULL, 0) == LIE_SCHEMA_INVALID);
    lie_schema_memo_release(m);
  }
  assert(a.live == 0 && a.bytes == 0);
  return a.calls;
}
int main(void) {
  lie_schema_memo_description d;
  lie_schema_memo_description_init(&d);
  assert(d.max_entries == 262144);
  lie_schema_memo *m = (void *)&nodes;
  d.abi_version++;
  assert(lie_schema_memo_create(&d, &m) == LIE_SCHEMA_INVALID &&
         m == (void *)&nodes);
  lie_schema_memo_description_init(&d);
  d.max_entries = SIZE_MAX;
  assert(lie_schema_memo_create(&d, &m) == LIE_SCHEMA_INVALID &&
         m == (void *)&nodes);
  d.max_entries = 0;
  assert(lie_schema_memo_create(&d, &m) == LIE_SCHEMA_INVALID);
  lie_schema_memo_description_init(&d);
  d.allocator.allocate = alloc;
  assert(lie_schema_memo_create(&d, &m) == LIE_SCHEMA_INVALID);
  lie_schema_memo_release(NULL);
  const size_t allocations = scenario(0);
  for (size_t fail = 1; fail <= allocations; fail++)
    scenario(fail);
  lie_schema_memo_description_init(&d);
  d.max_entries = 1;
  assert(lie_schema_memo_create(&d, &m) == LIE_SCHEMA_OK);
  assert(lie_schema_memo_assign(m, nodes, UINT32_MAX) == LIE_SCHEMA_OK);
  assert(lie_schema_memo_assign(m, nodes + 1, 1) == LIE_SCHEMA_WORK_LIMIT);
  assert(lie_schema_memo_assign(m, nodes, 0) == LIE_SCHEMA_OK);
  uint32_t value = 1;
  bool hit = false;
  assert(lie_schema_memo_get(m, nodes, &value, &hit) == LIE_SCHEMA_OK && hit &&
         value == 0);
  lie_schema_memo_release(m);
  printf("C17 schema memo: %zu independent identity/value checks, %zu "
         "refusals, %zu allocation sites\n",
         checks, refusals, allocations);
}
