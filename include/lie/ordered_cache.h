/* SPDX-License-Identifier: MIT */
#ifndef LIE_ORDERED_CACHE_H
#define LIE_ORDERED_CACHE_H
#include "lie/grammar.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_ORDERED_CACHE_ABI 1u
typedef enum {
  LIE_ORDERED_CACHE_OK,
  LIE_ORDERED_CACHE_INVALID,
  LIE_ORDERED_CACHE_RESOURCE,
  LIE_ORDERED_CACHE_CALLBACK
} lie_ordered_cache_status;
typedef struct {
  void *context;
  lie_ordered_cache_status (*retain)(void *, const void *, void **);
  void (*release)(void *, void *);
  /* Compare owned left key with borrowed right key: negative/zero/positive.
   * The same strict total ordering must apply throughout the cache lifetime. */
  lie_ordered_cache_status (*compare)(void *, const void *, const void *, int *);
} lie_ordered_cache_keys;
typedef struct {
  void *context;
  lie_ordered_cache_status (*retain)(void *, const void *, void **);
  void (*release)(void *, void *);
  lie_ordered_cache_status (*copy)(void *, const void *, void *);
} lie_ordered_cache_values;
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t max_entries;
  lie_grammar_allocator allocator;
  lie_ordered_cache_keys keys;
  lie_ordered_cache_values values;
} lie_ordered_cache_description;
typedef struct lie_ordered_cache lie_ordered_cache;
typedef struct { size_t entries; } lie_ordered_cache_info;
void lie_ordered_cache_description_init(lie_ordered_cache_description *);
lie_ordered_cache_status lie_ordered_cache_create(
    const lie_ordered_cache_description *, lie_ordered_cache **);
/* Concurrent get/put/inspect serialize internally; compile outside the lock.
 * put rechecks duplicates BEFORE eviction: a duplicate returns the existing
 * value without eviction/retention. A new insertion at capacity evicts the
 * smallest existing key. Default capacity16 follows pinned composition caches.
 * Inputs are borrowed for the call. Keys and values remain opaque: hooks own
 * their storage, size budgets and resource accounting. The core owns only its
 * fixed-capacity entry array and mutex; it adds no thread or device/model call.
 * Hooks must not throw or reenter this cache. Comparison, retain and copy run
 * inside its lock. Retain publishes a non-NULL fresh owned handle only on
 * success; on refusal it must retire partial work. copy preserves output on
 * refusal. A miss leaves output unchanged; hit is published only on success.
 * Hook/allocation refusal preserves entries and outputs. Eviction/refusal
 * retirement occurs after unlock; release and allocator hooks must support
 * concurrent calls. Destruction requires all operations retired. Allocator
 * hooks are paired, return fresh aligned memory and outlive the cache; NULL
 * hooks select malloc/free. Returned value copies outlive eviction. */
lie_ordered_cache_status lie_ordered_cache_get(
    lie_ordered_cache *, const void *key, void *output, bool *hit);
lie_ordered_cache_status lie_ordered_cache_put(
    lie_ordered_cache *, const void *key, const void *value, void *output);
lie_ordered_cache_status lie_ordered_cache_inspect(
    lie_ordered_cache *, lie_ordered_cache_info *);
void lie_ordered_cache_release(lie_ordered_cache *);
#ifdef __cplusplus
}
#endif
#endif
