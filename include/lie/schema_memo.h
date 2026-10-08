/* SPDX-License-Identifier: MIT */
#ifndef LIE_SCHEMA_MEMO_H
#define LIE_SCHEMA_MEMO_H
#include "lie/schema_transform.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_SCHEMA_MEMO_ABI 1u
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t max_entries;
  lie_grammar_allocator allocator;
} lie_schema_memo_description;
typedef struct lie_schema_memo lie_schema_memo;
typedef struct {
  size_t entries, slots, allocated_bytes;
} lie_schema_memo_info;
void lie_schema_memo_description_init(lie_schema_memo_description *);
lie_schema_status lie_schema_memo_create(const lie_schema_memo_description *,
                                         lie_schema_memo **);
/* Per-compilation, caller-serialized identity memo. Keys are nonnull opaque
 * node addresses, compared for equality and never dereferenced. Addresses
 * remain unique/stable until destruction, including recursively pending nodes.
 * Values are rule IDs; publish a placeholder before visiting its children.
 * This contract owns no grammar, JSON node, worker, model, HTTP or persistent
 * cache. Default maximum entries: 262144. Storage grows geometrically with a
 * load factor at most 1/2; inspect reports all live C allocations. Allocator
 * callbacks must be paired, return fresh aligned storage, and outlive the memo.
 * NULL callbacks select malloc/free. Allocation/bound/argument refusal leaves
 * existing entries and outputs unchanged. Miss sets hit=false without writing
 * value. Assigning an existing key replaces its value, including at capacity,
 * without allocation. Caller-owned output and allocator state are disjoint
 * from the memo. No callback reentry; destroy only after operations retire. */
lie_schema_status lie_schema_memo_get(const lie_schema_memo *, lie_schema_node,
                                      uint32_t *value, bool *hit);
lie_schema_status lie_schema_memo_assign(lie_schema_memo *, lie_schema_node,
                                         uint32_t value);
lie_schema_status lie_schema_memo_inspect(const lie_schema_memo *,
                                          lie_schema_memo_info *);
void lie_schema_memo_release(lie_schema_memo *);
#ifdef __cplusplus
}
#endif
#endif
