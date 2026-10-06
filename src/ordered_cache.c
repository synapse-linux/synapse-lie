/* SPDX-License-Identifier: MIT */
/* Composition-cache ordering/duplicate/eviction policy follows independently
 * pinned Gufo; opaque storage stays caller-owned. See third_party/gufo-NOTICE. */
#include "lie/ordered_cache.h"
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
typedef struct { void *key, *value; } entry;
struct lie_ordered_cache {
  lie_ordered_cache_description d;
  pthread_mutex_t mutex;
  entry *entries;
  size_t count;
};
static void *allocate(const lie_ordered_cache_description *d, size_t bytes) {
  return d->allocator.allocate ? d->allocator.allocate(d->allocator.context, bytes) : malloc(bytes);
}
static void deallocate(const lie_ordered_cache_description *d, void *p) {
  if (!p) return;
  if (d->allocator.release) d->allocator.release(d->allocator.context, p);
  else free(p);
}
static void retire(lie_ordered_cache *c, entry e) {
  if (e.key) c->d.keys.release(c->d.keys.context, e.key);
  if (e.value) c->d.values.release(c->d.values.context, e.value);
}
static lie_ordered_cache_status find(lie_ordered_cache *c, const void *key,
    size_t *at, bool *hit) {
  size_t first = 0, last = c->count;
  while (first < last) {
    const size_t mid = first + (last - first) / 2;
    int comparison = 0;
    const lie_ordered_cache_status rc = c->d.keys.compare(
        c->d.keys.context, c->entries[mid].key, key, &comparison);
    if (rc) return rc;
    if (!comparison) { *at = mid; *hit = true; return LIE_ORDERED_CACHE_OK; }
    if (comparison < 0) first = mid + 1;
    else last = mid;
  }
  *at = first;
  *hit = false;
  return LIE_ORDERED_CACHE_OK;
}
void lie_ordered_cache_description_init(lie_ordered_cache_description *d) {
  if (!d) return;
  memset(d, 0, sizeof(*d));
  d->abi_version = LIE_ORDERED_CACHE_ABI;
  d->struct_bytes = sizeof(*d);
  d->max_entries = 16;
}
lie_ordered_cache_status lie_ordered_cache_create(
    const lie_ordered_cache_description *d, lie_ordered_cache **out) {
  if (!d || !out || d->abi_version != LIE_ORDERED_CACHE_ABI ||
      d->struct_bytes != sizeof(*d) || !d->max_entries ||
      d->max_entries > SIZE_MAX / sizeof(entry) ||
      (!!d->allocator.allocate != !!d->allocator.release) ||
      !d->keys.retain || !d->keys.release || !d->keys.compare ||
      !d->values.retain || !d->values.release || !d->values.copy)
    return LIE_ORDERED_CACHE_INVALID;
  lie_ordered_cache *c = allocate(d, sizeof(*c));
  if (!c) return LIE_ORDERED_CACHE_RESOURCE;
  memset(c, 0, sizeof(*c));
  c->d = *d;
  c->entries = allocate(d, d->max_entries * sizeof(entry));
  if (!c->entries || pthread_mutex_init(&c->mutex, NULL)) {
    deallocate(d, c->entries);
    deallocate(d, c);
    return LIE_ORDERED_CACHE_RESOURCE;
  }
  *out = c;
  return LIE_ORDERED_CACHE_OK;
}
lie_ordered_cache_status lie_ordered_cache_get(lie_ordered_cache *c,
    const void *key, void *out, bool *hit) {
  if (!c || !key || !out || !hit) return LIE_ORDERED_CACHE_INVALID;
  if (pthread_mutex_lock(&c->mutex)) return LIE_ORDERED_CACHE_RESOURCE;
  size_t at = 0;
  bool found = false;
  lie_ordered_cache_status rc = find(c, key, &at, &found);
  if (!rc && found) rc = c->d.values.copy(c->d.values.context, c->entries[at].value, out);
  if (!rc) *hit = found;
  (void)pthread_mutex_unlock(&c->mutex);
  return rc;
}
lie_ordered_cache_status lie_ordered_cache_put(lie_ordered_cache *c,
    const void *key, const void *value, void *out) {
  if (!c || !key || !value || !out) return LIE_ORDERED_CACHE_INVALID;
  if (pthread_mutex_lock(&c->mutex)) return LIE_ORDERED_CACHE_RESOURCE;
  size_t at = 0;
  bool found = false;
  entry added = {0}, evicted = {0};
  lie_ordered_cache_status rc = find(c, key, &at, &found);
  if (!rc && !found) {
    rc = c->d.keys.retain(c->d.keys.context, key, &added.key);
    if (!rc && !added.key) rc = LIE_ORDERED_CACHE_CALLBACK;
    if (!rc) rc = c->d.values.retain(c->d.values.context, value, &added.value);
    if (!rc && !added.value) rc = LIE_ORDERED_CACHE_CALLBACK;
  }
  if (!rc) rc = c->d.values.copy(c->d.values.context,
      found ? c->entries[at].value : added.value, out);
  if (!rc && !found) {
    if (c->count == c->d.max_entries) {
      evicted = c->entries[0];
      --c->count;
      memmove(c->entries, c->entries + 1, c->count * sizeof(entry));
      if (at) --at;
    }
    memmove(c->entries + at + 1, c->entries + at, (c->count - at) * sizeof(entry));
    c->entries[at] = added;
    ++c->count;
    added = (entry){0};
  }
  (void)pthread_mutex_unlock(&c->mutex);
  retire(c, added);
  retire(c, evicted);
  return rc;
}
lie_ordered_cache_status lie_ordered_cache_inspect(lie_ordered_cache *c,
    lie_ordered_cache_info *out) {
  if (!c || !out) return LIE_ORDERED_CACHE_INVALID;
  if (pthread_mutex_lock(&c->mutex)) return LIE_ORDERED_CACHE_RESOURCE;
  out->entries = c->count;
  (void)pthread_mutex_unlock(&c->mutex);
  return LIE_ORDERED_CACHE_OK;
}
void lie_ordered_cache_release(lie_ordered_cache *c) {
  if (!c) return;
  for (size_t i = 0; i < c->count; ++i) retire(c, c->entries[i]);
  (void)pthread_mutex_destroy(&c->mutex);
  const lie_ordered_cache_description d = c->d;
  deallocate(&d, c->entries);
  deallocate(&d, c);
}
