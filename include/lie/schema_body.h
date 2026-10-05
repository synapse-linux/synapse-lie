/* SPDX-License-Identifier: MIT */
#ifndef LIE_SCHEMA_BODY_H
#define LIE_SCHEMA_BODY_H
#include "lie/schema_dispatch.h"
#include "lie/schema_values.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_SCHEMA_BODY_ABI 1u
typedef struct {
  void *context;
  lie_schema_status (*visit)(void *, lie_schema_node, size_t, uint32_t *);
  lie_schema_status (*keep_schema)(void *, lie_schema_node, lie_schema_node *);
  lie_schema_status (*normalize)(void *, lie_schema_node, lie_schema_node,
                                 lie_schema_normalized *);
} lie_schema_compile_access;
typedef struct {
  uint32_t abi_version, struct_bytes;
  lie_schema_transform_description transform;
  lie_schema_values_description values;
  /* Uses transform.access.context; copies a member without replacing earlier
   * equal keys, preserving borrowed source order for schema copies. */
  lie_schema_status (*append_member)(void *, lie_schema_node, lie_schema_bytes,
                                     lie_schema_node);
  lie_schema_compile_access compile;
  lie_schema_rule_access rules;
} lie_schema_body_description;
void lie_schema_body_description_init(lie_schema_body_description *);
/* Model-neutral synchronous schema-body policy: validate keys/depth, visit
 * definitions, resolve/distribute references and anyOf, validate the base of
 * enum/const, filter/count/canonicalize choices and compose ordered rules.
 * Input/reader views are immutable and stable. Writer staging is private and
 * retires after this call. keep_schema copies into per-compilation storage
 * whose identities outlive the memo/builder pair; visit never sees temporary
 * writer nodes. normalize adapts the separately owned C17 value normalizer,
 * publishing a canonical node stable until this call retires, or exclusion.
 * Hooks do not throw or reenter this call; child visitors may compile bodies
 * in separate staging. Leaf routes belong to the declared rule callback.
 * Counters are caller-owned per-compilation state shared with container rules.
 * They and builder/storage mutations can remain after refusal: destroy the
 * entire failed compilation rather than reusing it. Only successful calls
 * publish the result. EMPTY is a semantic empty body for Visit to consume.
 * Budgets retain schema depth16, enum1000, global characters120000 and large
 * string enums (>250 entries)15000 characters. Transform work/allocator
 * limits also apply. No model, worker, HTTP, RNG or persisted-state ownership.
 * Caller serializes calls and retires callbacks before destroying state. */
lie_schema_status
lie_schema_compile_body(const lie_schema_body_description *,
                        lie_schema_node root, lie_schema_node schema,
                        size_t depth, lie_grammar_builder *,
                        uint32_t whitespace, lie_schema_container_counts *,
                        size_t *enum_values, uint32_t *, lie_schema_error *);
#ifdef __cplusplus
}
#endif
#endif
