/* SPDX-License-Identifier: MIT */
/* Ordered bounded cache policy follows the independently pinned Gufo schema
 * compiler; third_party/gufo-NOTICE records attribution and opaque-value glue.
 */
#include "lie/grammar_cache.h"
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
typedef struct {
  uint8_t *key;
  size_t bytes;
  void *value;
} entry;
struct lie_grammar_cache {
  lie_grammar_cache_description description;
  pthread_mutex_t mutex;
  entry *entries;
  size_t count, key_bytes;
};
static void *allocate(const lie_grammar_cache_description *d, size_t n) {
  return d->allocator.allocate ? d->allocator.allocate(d->allocator.context, n)
                               : malloc(n);
}
static void release(const lie_grammar_cache_description *d, void *p) {
  if (!p)
    return;
  if (d->allocator.release)
    d->allocator.release(d->allocator.context, p);
  else
    free(p);
}
static int compare(const entry *e, const uint8_t *key, size_t bytes) {
  const size_t n = e->bytes < bytes ? e->bytes : bytes;
  const int cmp = n ? memcmp(e->key, key, n) : 0;
  return cmp ? cmp : (e->bytes > bytes) - (e->bytes < bytes);
}
static size_t find(const lie_grammar_cache *c, const uint8_t *key, size_t bytes,
                   size_t first, bool *found) {
  size_t last = c->count;
  while (first < last) {
    const size_t mid = first + (last - first) / 2;
    if (compare(&c->entries[mid], key, bytes) < 0)
      first = mid + 1;
    else
      last = mid;
  }
  *found = first < c->count && compare(&c->entries[first], key, bytes) == 0;
  return first;
}
static lie_grammar_cache_status input(lie_grammar_cache *c, const uint8_t *key,
                                      size_t bytes, void *output) {
  if (!c || (bytes && !key) || !output)
    return LIE_GRAMMAR_CACHE_INVALID;
  return bytes > c->description.max_key_bytes ? LIE_GRAMMAR_CACHE_KEY_LIMIT
                                              : LIE_GRAMMAR_CACHE_OK;
}
static void retire(lie_grammar_cache *c, entry e) {
  release(&c->description, e.key);
  if (e.value)
    c->description.values.release(c->description.values.context, e.value);
}
void lie_grammar_cache_description_init(lie_grammar_cache_description *d) {
  if (!d)
    return;
  memset(d, 0, sizeof(*d));
  d->abi_version = LIE_GRAMMAR_CACHE_ABI;
  d->struct_bytes = sizeof(*d);
  d->max_entries = 16;
  d->max_key_bytes = 2u * 1024u * 1024u;
}
lie_grammar_cache_status
lie_grammar_cache_create(const lie_grammar_cache_description *d,
                         lie_grammar_cache **out) {
  if (!d || !out || d->abi_version != LIE_GRAMMAR_CACHE_ABI ||
      d->struct_bytes != sizeof(*d) || !d->max_entries ||
      d->max_entries > SIZE_MAX / sizeof(entry) ||
      d->max_key_bytes > SIZE_MAX / d->max_entries ||
      (!!d->allocator.allocate != !!d->allocator.release) ||
      !d->values.retain || !d->values.release || !d->values.copy)
    return LIE_GRAMMAR_CACHE_INVALID;
  lie_grammar_cache *c = allocate(d, sizeof(*c));
  if (!c)
    return LIE_GRAMMAR_CACHE_RESOURCE;
  memset(c, 0, sizeof(*c));
  c->description = *d;
  c->entries = allocate(d, d->max_entries * sizeof(*c->entries));
  if (!c->entries) {
    release(d, c);
    return LIE_GRAMMAR_CACHE_RESOURCE;
  }
  if (pthread_mutex_init(&c->mutex, NULL)) {
    release(d, c->entries);
    release(d, c);
    return LIE_GRAMMAR_CACHE_RESOURCE;
  }
  *out = c;
  return LIE_GRAMMAR_CACHE_OK;
}
lie_grammar_cache_status lie_grammar_cache_get(lie_grammar_cache *c,
                                               const uint8_t *key, size_t bytes,
                                               void *output, bool *hit) {
  lie_grammar_cache_status rc = input(c, key, bytes, output);
  if (rc || !hit)
    return rc ? rc : LIE_GRAMMAR_CACHE_INVALID;
  if (pthread_mutex_lock(&c->mutex))
    return LIE_GRAMMAR_CACHE_RESOURCE;
  bool found = false;
  const size_t i = find(c, key, bytes, 0, &found);
  if (found)
    rc = c->description.values.copy(c->description.values.context,
                                    c->entries[i].value, output);
  if (!rc)
    *hit = found;
  (void)pthread_mutex_unlock(&c->mutex);
  return rc;
}
lie_grammar_cache_status lie_grammar_cache_put(lie_grammar_cache *c,
                                               const uint8_t *key, size_t bytes,
                                               const void *value,
                                               void *output) {
  lie_grammar_cache_status rc = input(c, key, bytes, output);
  if (rc || !value)
    return rc ? rc : LIE_GRAMMAR_CACHE_INVALID;
  if (pthread_mutex_lock(&c->mutex))
    return LIE_GRAMMAR_CACHE_RESOURCE;
  const size_t skip = c->count == c->description.max_entries ? 1 : 0;
  bool found = false;
  const size_t i = find(c, key, bytes, skip, &found);
  entry added = {0}, evicted = {0};
  if (!found) {
    added.bytes = bytes;
    if (bytes) {
      added.key = allocate(&c->description, bytes);
      if (!added.key)
        rc = LIE_GRAMMAR_CACHE_RESOURCE;
      else
        memcpy(added.key, key, bytes);
    }
    if (!rc)
      rc = c->description.values.retain(c->description.values.context, value,
                                        &added.value);
    if (!rc && !added.value)
      rc = LIE_GRAMMAR_CACHE_CALLBACK;
  }
  if (!rc)
    rc = c->description.values.copy(c->description.values.context,
                                    found ? c->entries[i].value : added.value,
                                    output);
  if (!rc) {
    if (skip) {
      evicted = c->entries[0];
      --c->count;
      c->key_bytes -= evicted.bytes;
      memmove(c->entries, c->entries + 1, c->count * sizeof(*c->entries));
    }
    if (!found) {
      const size_t at = i - skip;
      memmove(c->entries + at + 1, c->entries + at,
              (c->count - at) * sizeof(*c->entries));
      c->entries[at] = added;
      ++c->count;
      c->key_bytes += bytes;
      added = (entry){0};
    }
  }
  (void)pthread_mutex_unlock(&c->mutex);
  retire(c, added);
  retire(c, evicted);
  return rc;
}
lie_grammar_cache_status
lie_grammar_cache_inspect(lie_grammar_cache *c, lie_grammar_cache_info *out) {
  if (!c || !out)
    return LIE_GRAMMAR_CACHE_INVALID;
  if (pthread_mutex_lock(&c->mutex))
    return LIE_GRAMMAR_CACHE_RESOURCE;
  *out = (lie_grammar_cache_info){c->count, c->key_bytes};
  (void)pthread_mutex_unlock(&c->mutex);
  return LIE_GRAMMAR_CACHE_OK;
}
void lie_grammar_cache_release(lie_grammar_cache *c) {
  if (!c)
    return;
  for (size_t i = 0; i < c->count; ++i)
    retire(c, c->entries[i]);
  (void)pthread_mutex_destroy(&c->mutex);
  const lie_grammar_cache_description d = c->description;
  release(&d, c->entries);
  release(&d, c);
}
