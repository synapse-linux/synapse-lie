/* SPDX-License-Identifier: MIT */
#ifndef LIE_SCHEMA_DISPATCH_H
#define LIE_SCHEMA_DISPATCH_H
#include "lie/grammar_builder.h"
#include "lie/schema_transform.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_SCHEMA_DISPATCH_ABI 1u
typedef enum {
  LIE_SCHEMA_ROUTE_PRIMITIVE, LIE_SCHEMA_ROUTE_OBJECT, LIE_SCHEMA_ROUTE_ARRAY,
  LIE_SCHEMA_ROUTE_INTEGER, LIE_SCHEMA_ROUTE_INTEGER_LEXEME,
  LIE_SCHEMA_ROUTE_NUMBER_LEXEME, LIE_SCHEMA_ROUTE_STRING_LEXEME
} lie_schema_route;
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t count;
  lie_schema_bytes names[2];
  lie_schema_route routes[2];
} lie_schema_dispatch_plan;
typedef struct {
  void *context;
  lie_schema_status (*rule)(void *, lie_schema_node, size_t, lie_schema_route,
                           lie_schema_bytes, uint32_t *);
} lie_schema_rule_access;
/* Validate one type or a nullable pair, keyword/type compatibility and select
 * ordered object/array/integer/lexeme/primitive routes. Unknown type names are
 * retained for the existing primitive/finite-value policy, preserving refusal
 * order. Schema keys/depth/definitions/references/finite values have their own
 * contracts. No allocation, recursion, node mutation or inference ownership.
 * Read hooks and immutable spans remain stable for the whole call; outputs
 * are disjoint from node/callback state. Refusal preserves the entire plan. */
lie_schema_status lie_schema_dispatch_types(
    const lie_schema_transform_description *, lie_schema_node,
    lie_schema_dispatch_plan *, lie_schema_error *);
/* Consume an unmodified plan produced above for this same immutable schema.
 * Invoke rule hooks in type order and compose their IDs through the C builder.
 * Hooks are synchronous, do not throw/reenter this call or retain input, and
 * may invoke child visitors. Operations are caller-serialized. Refusal leaves
 * output untouched; successful earlier hook/builder mutations remain private
 * and must be retired with staging after refusal. The borrowed plan and hook
 * state outlive the call. No shared cache/model/worker/RNG/persisted ABI change. */
lie_schema_status lie_schema_dispatch_rules(
    const lie_schema_dispatch_plan *, lie_schema_node, size_t depth,
    lie_grammar_builder *, lie_schema_rule_access, uint32_t *,
    lie_schema_error *);
#ifdef __cplusplus
}
#endif
#endif
