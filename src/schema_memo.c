/* SPDX-License-Identifier: MIT */
#include "lie/schema_memo.h"
#include <stdlib.h>
#include <string.h>
typedef struct {
  lie_schema_node key;
  uint32_t value;
} memo_entry;
struct lie_schema_memo {
  lie_schema_memo_description description;
  memo_entry *table;
  size_t count, slots;
};
static void *allocate(const lie_schema_memo_description *d, size_t bytes) {
  return d->allocator.allocate
             ? d->allocator.allocate(d->allocator.context, bytes)
             : malloc(bytes);
}
static void release(const lie_schema_memo_description *d, void *p) {
  if (!p)
    return;
  if (d->allocator.release)
    d->allocator.release(d->allocator.context, p);
  else
    free(p);
}
static size_t hash(lie_schema_node key) {
  /* Unsigned mixing also supports tightly packed nodes and 32-bit hosts. */
  uint64_t x = (uint64_t)(uintptr_t)key;
  x ^= x >> 30;
  x *= UINT64_C(0xbf58476d1ce4e5b9);
  x ^= x >> 27;
  x *= UINT64_C(0x94d049bb133111eb);
  x ^= x >> 31;
  return (size_t)x;
}
static size_t find(const memo_entry *table, size_t slots, lie_schema_node key) {
  size_t i = hash(key) & (slots - 1);
  /* Empty slots always exist: live count is at most half of capacity. */
  while (table[i].key && table[i].key != key)
    i = (i + 1) & (slots - 1);
  return i;
}
void lie_schema_memo_description_init(lie_schema_memo_description *d) {
  if (!d)
    return;
  memset(d, 0, sizeof(*d));
  d->abi_version = LIE_SCHEMA_MEMO_ABI;
  d->struct_bytes = sizeof(*d);
  d->max_entries = 262144;
}
lie_schema_status lie_schema_memo_create(const lie_schema_memo_description *d,
                                         lie_schema_memo **out) {
  if (!d || !out || d->abi_version != LIE_SCHEMA_MEMO_ABI ||
      d->struct_bytes != sizeof(*d) || !d->max_entries ||
      d->max_entries >
          (SIZE_MAX - sizeof(lie_schema_memo)) / sizeof(memo_entry) / 4 ||
      (!!d->allocator.allocate != !!d->allocator.release))
    return LIE_SCHEMA_INVALID;
  lie_schema_memo *m = allocate(d, sizeof(*m));
  if (!m)
    return LIE_SCHEMA_RESOURCE;
  memset(m, 0, sizeof(*m));
  m->description = *d;
  *out = m;
  return LIE_SCHEMA_OK;
}
lie_schema_status lie_schema_memo_get(const lie_schema_memo *m,
                                      lie_schema_node key, uint32_t *out,
                                      bool *hit) {
  if (!m || !key || !out || !hit)
    return LIE_SCHEMA_INVALID;
  if (!m->slots) {
    *hit = false;
    return LIE_SCHEMA_OK;
  }
  const size_t i = find(m->table, m->slots, key);
  const bool found = m->table[i].key != NULL;
  if (found)
    *out = m->table[i].value;
  *hit = found;
  return LIE_SCHEMA_OK;
}
lie_schema_status lie_schema_memo_assign(lie_schema_memo *m,
                                         lie_schema_node key, uint32_t value) {
  if (!m || !key)
    return LIE_SCHEMA_INVALID;
  size_t i = 0;
  if (m->slots) {
    i = find(m->table, m->slots, key);
    if (m->table[i].key) {
      m->table[i].value = value;
      return LIE_SCHEMA_OK;
    }
  }
  if (m->count == m->description.max_entries)
    return LIE_SCHEMA_WORK_LIMIT;
  if (!m->slots || m->count == m->slots / 2) {
    const size_t slots = m->slots ? m->slots * 2 : 2;
    memo_entry *table = allocate(&m->description, slots * sizeof(*table));
    if (!table)
      return LIE_SCHEMA_RESOURCE;
    memset(table, 0, slots * sizeof(*table));
    for (size_t j = 0; j < m->slots; ++j)
      if (m->table[j].key)
        table[find(table, slots, m->table[j].key)] = m->table[j];
    memo_entry *old = m->table;
    m->table = table;
    m->slots = slots;
    release(&m->description, old);
    i = find(m->table, slots, key);
  }
  m->table[i] = (memo_entry){key, value};
  ++m->count;
  return LIE_SCHEMA_OK;
}
lie_schema_status lie_schema_memo_inspect(const lie_schema_memo *m,
                                          lie_schema_memo_info *out) {
  if (!m || !out)
    return LIE_SCHEMA_INVALID;
  *out = (lie_schema_memo_info){m->count, m->slots,
                                sizeof(*m) + m->slots * sizeof(*m->table)};
  return LIE_SCHEMA_OK;
}
void lie_schema_memo_release(lie_schema_memo *m) {
  if (!m)
    return;
  const lie_schema_memo_description d = m->description;
  release(&d, m->table);
  release(&d, m);
}
