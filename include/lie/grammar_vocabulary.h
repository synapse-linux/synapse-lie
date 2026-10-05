/* SPDX-License-Identifier: MIT */
#ifndef LIE_GRAMMAR_VOCABULARY_H
#define LIE_GRAMMAR_VOCABULARY_H
#include "lie/grammar.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_VOCABULARY_ABI 1u
typedef struct { const uint8_t *bytes; size_t length; bool stop; } lie_token_piece;
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t max_tokens, max_bytes, max_token_bytes, max_nodes;
} lie_vocabulary_limits;
typedef struct {
  uint32_t abi_version, struct_bytes;
  const lie_token_piece *pieces;
  size_t count;
  lie_grammar_allocator allocator;
  lie_vocabulary_limits limits;
} lie_vocabulary_description;
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t max_work, max_interned_states;
  const void *context;
  bool (*cache_transitions)(const void *, const lie_grammar_state *);
} lie_vocabulary_query;
typedef struct {
  size_t visited_nodes, advances, interned_states, direct_nodes, cache_hits, peak_depth;
} lie_vocabulary_stats;
typedef struct lie_grammar_vocabulary lie_grammar_vocabulary;
void lie_vocabulary_description_init(lie_vocabulary_description *);
void lie_vocabulary_query_init(lie_vocabulary_query *);
lie_grammar_status lie_vocabulary_create(const lie_vocabulary_description *,
                                         lie_grammar_vocabulary **);
void lie_vocabulary_release(lie_grammar_vocabulary *);
size_t lie_vocabulary_size(const lie_grammar_vocabulary *);
size_t lie_vocabulary_max_token_bytes(const lie_grammar_vocabulary *);
lie_grammar_status lie_vocabulary_allowed(const lie_grammar_vocabulary *,
  const lie_grammar_program *, const lie_grammar_state *, bool stop_only_when_complete,
  const lie_vocabulary_query *, uint8_t *, size_t, lie_vocabulary_stats *);
lie_grammar_status lie_vocabulary_accept(const lie_grammar_vocabulary *,
  const lie_grammar_program *, const lie_grammar_state *, uint32_t,
  lie_grammar_state **);
/* Copied immutable byte pieces and insertion-ordered trie. Default limits:
 * 1,048,576 tokens,64MiB total text,4096 bytes per nonempty non-stop piece,
 * 4,000,000 nodes. Stop/empty pieces never enter the trie. Mask traversal is
 * iterative with depth-bounded scratch; exact state interning and lazily
 * allocated 256-entry transition tables stop growing at8192 states by default.
 * Numeric/noncacheable predicates and full interning use direct traversal,
 * preserving the language. A zero interning limit selects direct traversal.
 * Work budget defaults to2,000,000 visited trie nodes. Query outputs/stats are
 * unchanged on refusal. NO_TOKEN is language rejection, not allocation failure.
 * Input states must belong to the borrowed immutable grammar program. Runtime
 * cache predicate and paired allocator hooks are nonthrowing/caller-synchronized.
 * No model, device, RNG, thread, HTTP or mutable global state. */

typedef struct lie_grammar_mask_cache lie_grammar_mask_cache;
typedef void (*lie_grammar_payload_release)(void *, void *);
lie_grammar_status lie_mask_cache_create(const lie_grammar_program *, size_t,
  lie_grammar_allocator, lie_grammar_payload_release, void *, lie_grammar_mask_cache **);
void lie_mask_cache_release(lie_grammar_mask_cache *);
size_t lie_mask_cache_size(const lie_grammar_mask_cache *);
lie_grammar_status lie_mask_cache_find(const lie_grammar_mask_cache *,
  const lie_grammar_state *, void **);
lie_grammar_status lie_mask_cache_publish(lie_grammar_mask_cache *,
  const lie_grammar_state *, void *, void **);
/* Shared bounded cache owns copied canonical C state keys and opaque snapshot
 * payloads. Caller serializes find/publish/release; returned payloads are borrowed
 * under that synchronization. On OK publish consumes incoming payload, possibly
 * releasing a raced duplicate. On refusal it consumes nothing and leaves cache
 * and output unchanged. At capacity the smallest lexical key is retired before
 * publishing, matching the reference policy even for duplicate races. Cache
 * capacity1..1024; provider uses16. Borrowed program/allocator/release contexts
 * outlive the cache. Snapshot retain/copy belongs to payload glue; compilation
 * and mask computation can run outside the caller's cache lock. */
#ifdef __cplusplus
}
#endif
#endif
