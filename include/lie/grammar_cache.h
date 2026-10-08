/* SPDX-License-Identifier: MIT */
#ifndef LIE_GRAMMAR_CACHE_H
#define LIE_GRAMMAR_CACHE_H
#include "lie/grammar.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_GRAMMAR_CACHE_ABI 1u
typedef enum {
  LIE_GRAMMAR_CACHE_OK,
  LIE_GRAMMAR_CACHE_INVALID,
  LIE_GRAMMAR_CACHE_RESOURCE,
  LIE_GRAMMAR_CACHE_KEY_LIMIT,
  LIE_GRAMMAR_CACHE_CALLBACK
} lie_grammar_cache_status;
typedef struct {
  void *context;
  /* Copy borrowed value into a private owned handle, without publishing on
   * failure. release retires that handle. copy writes caller-owned output
   * transactionally; it does not retain input. Hooks must not throw or reenter
   * this cache. They execute synchronously; copy runs inside the cache lock. */
  lie_grammar_cache_status (*retain)(void *, const void *, void **);
  void (*release)(void *, void *);
  lie_grammar_cache_status (*copy)(void *, const void *, void *);
} lie_grammar_cache_values;
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t max_entries, max_key_bytes;
  lie_grammar_allocator allocator;
  lie_grammar_cache_values values;
} lie_grammar_cache_description;
typedef struct lie_grammar_cache lie_grammar_cache;
typedef struct {
  size_t entries, key_bytes;
} lie_grammar_cache_info;
void lie_grammar_cache_description_init(lie_grammar_cache_description *);
lie_grammar_cache_status
lie_grammar_cache_create(const lie_grammar_cache_description *,
                         lie_grammar_cache **);
/* Concurrent get/put/info operations are serialized internally. Caller output
 * and hook/allocator contexts remain private, disjoint and alive for the call.
 * Keys are copied byte spans, ordered lexicographically, including embedded
 * NUL. Defaults retain at most 16 entries and 2 MiB per key. Values remain
 * opaque; their allocations belong to the declared hooks, not key accounting.
 * No compiler/model/HTTP/device/worker ownership: compile outside the lock,
 * then put the result. Hook/allocation refusal preserves the cache and outputs.
 * get publishes hit only on success; a miss does not write value_output.
 * When full, successful put evicts the lexicographically smallest key BEFORE
 * resolving a duplicate, matching the pinned compilation cache. A duplicate
 * remaining after that eviction returns the existing value, leaving one fewer
 * entry. Evicted values retire after unlock; returned copies outlive eviction.
 * Cache destruction requires all operations retired, and releases every key
 * and opaque owned value. Paired allocators outlive the entire cache;
 * allocation returns fresh aligned memory. Release hooks/allocators must
 * support concurrent calls, since eviction and failed insertion retire after
 * unlocking. Retain and copy run under the lock. NULL allocator hooks select
 * malloc/free. */
lie_grammar_cache_status lie_grammar_cache_get(lie_grammar_cache *,
                                               const uint8_t *key,
                                               size_t key_bytes,
                                               void *value_output, bool *hit);
lie_grammar_cache_status
lie_grammar_cache_put(lie_grammar_cache *, const uint8_t *key, size_t key_bytes,
                      const void *value, void *value_output);
lie_grammar_cache_status lie_grammar_cache_inspect(lie_grammar_cache *,
                                                   lie_grammar_cache_info *);
void lie_grammar_cache_release(lie_grammar_cache *);
#ifdef __cplusplus
}
#endif
#endif
