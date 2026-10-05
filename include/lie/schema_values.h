/* SPDX-License-Identifier: MIT */
#ifndef LIE_SCHEMA_VALUES_H
#define LIE_SCHEMA_VALUES_H
#include "lie/grammar_builder.h"
#include "lie/schema_transform.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_SCHEMA_VALUES_ABI 1u
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t max_depth, max_characters;
  lie_schema_transform_description transform;
  void *leaf_context;
  /* Leaf predicates and binary-double serialization retain their declared
   * owner. Callbacks are synchronous and must not throw/retain input. */
  lie_schema_status (*accept)(void *, lie_schema_node, lie_schema_node, bool *);
  lie_schema_status (*number_literal)(void *, lie_schema_node,
                                      lie_grammar_builder *, uint32_t *);
} lie_schema_values_description;
typedef struct {
  bool matched;
  lie_schema_node value;
} lie_schema_normalized;
typedef struct {
  size_t properties, characters;
} lie_schema_container_counts;
typedef struct {
  void *context;
  lie_schema_status (*visit)(void *, lie_schema_node, size_t, uint32_t *);
} lie_schema_visit;
void lie_schema_values_description_init(lie_schema_values_description *);
lie_schema_status lie_schema_matches_type(const lie_schema_values_description *,
                                          lie_schema_node, lie_schema_bytes,
                                          bool *, lie_schema_error *);
/* Successful exclusion publishes {false,NULL}; operational refusal preserves
 * the entire output. Root/schema/value and reader views remain immutable and
 * stable for the call. Canonical objects retain schema property order, followed
 * by permitted extra members in source order. Arrays retain source order.
 * Private writer staging retires on success/exclusion/refusal. */
lie_schema_status lie_schema_normalize(const lie_schema_values_description *,
                                       lie_schema_node root,
                                       lie_schema_node schema,
                                       lie_schema_node value, size_t depth,
                                       lie_schema_normalized *,
                                       lie_schema_error *);
/* Counts non-continuation bytes, preserving pinned character accounting rather
 * than validating UTF8. Result is a delta bounded by max_characters. All tree
 * traversal is iterative. Refusal preserves the result. */
lie_schema_status
lie_schema_text_characters(const lie_schema_values_description *,
                           lie_schema_bytes, size_t *, lie_schema_error *);
lie_schema_status
lie_schema_value_characters(const lie_schema_values_description *,
                            lie_schema_node, size_t *, lie_schema_error *);
/* Ordered finite JSON value -> copied builder rules. C17 owns JSON string/key
 * quoting and container traversal; only number serialization uses the hook.
 * Depth defaults to256; builder mutations are private and may remain after
 * refusal, so retire the builder on failure. Result remains unpublished. */
lie_schema_status
lie_schema_value_literal(const lie_schema_values_description *, lie_schema_node,
                         lie_grammar_builder *, uint32_t whitespace, uint32_t *,
                         lie_schema_error *);
/* Shared object/array rule construction and child visitation. Objects require
 * additionalProperties:false, validate required names/duplicates, preserve
 * property order and the two comma suffix states. strict requires all fields.
 * Counts are private construction state; earlier successful increments may
 * remain after failure. Retire counts/builder and callback staging on failure.
 * The dispatcher/reference memo cache belongs to the declared visit hook. */
lie_schema_status lie_schema_object(const lie_schema_values_description *,
                                    lie_schema_node, size_t depth, bool strict,
                                    lie_grammar_builder *, uint32_t whitespace,
                                    lie_schema_visit,
                                    lie_schema_container_counts *, uint32_t *,
                                    lie_schema_error *);
lie_schema_status lie_schema_array(const lie_schema_values_description *,
                                   lie_schema_node, size_t depth,
                                   lie_grammar_builder *, uint32_t whitespace,
                                   lie_schema_visit, uint32_t *,
                                   lie_schema_error *);
#ifdef __cplusplus
}
#endif
#endif
