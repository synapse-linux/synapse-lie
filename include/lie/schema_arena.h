/* SPDX-License-Identifier: MIT */
#ifndef LIE_SCHEMA_ARENA_H
#define LIE_SCHEMA_ARENA_H
#include "lie/schema_transform.h"
#include "lie/json_store.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_SCHEMA_ARENA_ABI 1u
typedef struct lie_schema_arena lie_schema_arena;
typedef struct {
  uint32_t abi_version, struct_bytes;
  lie_grammar_allocator allocator;
  lie_json_value_description values;
  lie_json_store_description store;
  lie_schema_transform_description transform;
  size_t number_work;
} lie_schema_arena_description;
typedef struct {
  lie_json_value_status value_status;
  lie_json_store_status store_status;
  lie_schema_error schema_error;
} lie_schema_arena_error;
void lie_schema_arena_description_init(lie_schema_arena_description *);
/* Native, caller-serialized staging trees for schema transformation and value
 * normalization. C17 owns allocation, copied roots, scalar/container creation,
 * mutation and retirement. Child allocator hooks inherit the paired parent
 * hooks unless explicitly overridden. Child bounds/view hooks remain unchanged.
 * Store configuration is validated during create. Value/transform descriptions
 * are validated by their existing modules when the corresponding operation runs.
 * The arena owns successful copied/created roots until take or release. Original
 * inputs are borrowed and immutable; create/clone/take publish only on success.
 * Direct clone/put/append_member/append calls accept a NULL copied source as JSON
 * null, matching the JSON-value contract. Mutation targets and taken roots must
 * be actual non-NULL nodes; taking a NULL pointer is invalid.
 * Mutation targets belong to this arena's writable staging trees. Mutations may
 * remain after refusal: retire the whole failed staging operation.
 * No model, transport, thread, RNG or mutable global cache. Caller keeps all
 * allocator/view hooks and input/error spans alive through their required scope.
 * Inputs/outputs/errors are disjoint; hooks cannot reenter or release the arena. */
lie_schema_status lie_schema_arena_create(const lie_schema_arena_description *,
  lie_schema_arena **);
void lie_schema_arena_release(lie_schema_arena *);
lie_schema_status lie_schema_arena_clone(lie_schema_arena *, const lie_json_value *,
  lie_json_value **);
lie_schema_status lie_schema_arena_make(lie_schema_arena *, const lie_schema_value *,
  lie_json_value **);
lie_schema_status lie_schema_arena_put(lie_schema_arena *, lie_json_value *,
  lie_schema_bytes, const lie_json_value *);
lie_schema_status lie_schema_arena_append_member(lie_schema_arena *, lie_json_value *,
  lie_schema_bytes, const lie_json_value *);
lie_schema_status lie_schema_arena_append(lie_schema_arena *, lie_json_value *,
  const lie_json_value *);
lie_schema_status lie_schema_arena_take(lie_schema_arena *, const lie_json_value *,
  lie_json_value **);
/* Native readers and writer binding use lie_json_value pointers as opaque
 * schema nodes. Ordered members/duplicates, exact string/key spans and stored
 * binary64 values retain JSON-value semantics. No typed C++ projection is made.
 * Reader/writer callbacks require non-NULL schema-node handles, including nodes
 * representing JSON null; the direct copied-source convention does not apply.
 * Reader output spans borrow their source tree. A NULL arena selects read-only
 * default binding; create/clone/mutation then refuse. */
lie_schema_transform_description lie_schema_arena_transform(lie_schema_arena *);
lie_schema_status lie_schema_json_describe(void *, lie_schema_node, lie_schema_value *);
lie_schema_status lie_schema_json_child(void *, lie_schema_node, size_t,
  lie_schema_bytes *, lie_schema_node *);
/* Native format expansion and exact combined multipleOf use existing C17
 * policy/codec modules, with errors recorded before typed projection. */
lie_schema_status lie_schema_arena_format(lie_schema_arena *, lie_schema_bytes,
  lie_json_value **);
lie_schema_status lie_schema_arena_multiple(lie_schema_arena *, const lie_json_value *,
  const lie_json_value *, lie_json_value **);
/* Diagnostic snapshot for the immediately refused operation. Value/store
 * RESOURCE maps to schema RESOURCE; other underlying refusals map to CALLBACK
 * with their original reason retained. Transform/number statuses pass through.
 * Schema-error detail spans borrow input/staging and expire with those trees.
 * Roots retain their own accounting; this snapshot is not aggregate cost. */
void lie_schema_arena_error_describe(const lie_schema_arena *, lie_schema_arena_error *);
void lie_schema_arena_store_describe(const lie_schema_arena *, lie_json_store_info *);
#ifdef __cplusplus
}
#endif
#endif
