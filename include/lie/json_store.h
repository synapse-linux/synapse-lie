/* SPDX-License-Identifier: MIT */
#ifndef LIE_JSON_STORE_H
#define LIE_JSON_STORE_H
#include "lie/json_value.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_JSON_STORE_ABI 1u
typedef struct lie_json_store lie_json_store;
typedef enum {
  LIE_JSON_STORE_OK, LIE_JSON_STORE_INVALID, LIE_JSON_STORE_RESOURCE,
  LIE_JSON_STORE_LIMIT
} lie_json_store_status;
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t max_roots, max_owned_bytes;
  lie_grammar_allocator allocator;
} lie_json_store_description;
typedef struct {
  size_t live_roots, accepted_roots;
  size_t live_owned_bytes, peak_owned_bytes, allocations;
} lie_json_store_info;
void lie_json_store_description_init(lie_json_store_description *);
/* Caller-synchronized C17 root ownership collection; no model, HTTP or thread.
 * Defaults: 262144 cumulative successful adoptions, 16MiB collection heap.
 * Taking a root does not refund the cumulative admission budget. Root domains
 * retain their own allocators/budgets/views; collection accounting EXCLUDES
 * their heap and includes its context/table/growth overlap. Allocator hooks
 * are paired, max_align_t-aligned and outlive the collection. Root allocator
 * and view hooks must also outlive every taken root. Hooks cannot reenter the
 * collection or transfer/release its roots. No clone or tree mutation.
 * adopt requires a live, exclusively caller-owned ROOT (never a child or a
 * root owned by another collection). Success transfers ownership; all refusals
 * leave ownership, content and output pointers unchanged. Duplicate adoption
 * into this collection is refused. Borrowed roots/children/views remain stable
 * across collection growth and taking other roots. take transfers the exact
 * root to the caller. release retires only roots still owned by the collection.
 * Diagnostic allocation/peak counters may advance on an operation. */
lie_json_store_status lie_json_store_create(const lie_json_store_description *,
                                            lie_json_store **);
lie_json_store_status lie_json_store_adopt(lie_json_store *, lie_json_value *);
lie_json_store_status lie_json_store_take(lie_json_store *, const lie_json_value *,
                                         lie_json_value **);
void lie_json_store_describe(const lie_json_store *, lie_json_store_info *);
void lie_json_store_release(lie_json_store *);
#ifdef __cplusplus
}
#endif
#endif
