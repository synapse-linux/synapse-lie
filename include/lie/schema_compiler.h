/* SPDX-License-Identifier: MIT */
#ifndef LIE_SCHEMA_COMPILER_H
#define LIE_SCHEMA_COMPILER_H
#include "lie/schema_compile.h"
#include "lie/schema_memo.h"
#include "lie/schema_values.h"
#include "lie/json_store.h"
#include "lie/grammar_lexeme.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_SCHEMA_COMPILER_ABI 1u
typedef struct lie_schema_compiler lie_schema_compiler;
typedef enum {
  LIE_COMPILER_NEW, LIE_COMPILER_INITIALIZING, LIE_COMPILER_READY,
  LIE_COMPILER_PUBLISHING, LIE_COMPILER_PUBLISHED, LIE_COMPILER_FAILED
} lie_schema_compiler_phase;
typedef enum {
  LIE_COMPILER_OK, LIE_COMPILER_INVALID, LIE_COMPILER_RESOURCE,
  LIE_COMPILER_BUILDER, LIE_COMPILER_MEMO, LIE_COMPILER_STORE,
  LIE_COMPILER_CHECKS, LIE_COMPILER_CALLBACK, LIE_COMPILER_PUBLICATION,
  LIE_COMPILER_PHASE
} lie_schema_compiler_status;
typedef struct {
  uint32_t abi_version, struct_bytes;
  lie_grammar_allocator allocator;
  lie_builder_description builder;
  lie_schema_memo_description memo;
  lie_json_store_description store;
  lie_lexeme_table_description checks;
} lie_schema_compiler_description;
typedef struct {
  lie_builder_status builder_status;
  lie_schema_status schema_status;
  lie_json_store_status store_status;
  lie_lexeme_status lexeme_status;
  lie_schema_compile_status compile_status;
  lie_schema_compile_error compile_error;
} lie_schema_compiler_error;
typedef struct {
  lie_schema_compiler_phase phase;
  size_t context_bytes, enum_values;
  lie_schema_container_counts containers;
  lie_schema_memo_info memo;
  lie_json_store_info store;
  lie_lexeme_table_info checks;
} lie_schema_compiler_info;
void lie_schema_compiler_description_init(lie_schema_compiler_description *);
/* Per-compilation C17 owner of builder, reference memo, derived-root collection,
 * predicate memo, primitive IDs and counters. All hooks are paired/aligned and
 * outlive their objects. Child hooks inherit allocator when both are NULL;
 * explicit paired child hooks keep their own allocation domains. Existing
 * child limits/accounting apply; context_bytes counts only this fixed body.
 * Create publishes only on full success and retires every partial child.
 * No implicit original-input tree, model, HTTP, device, thread, RNG or global
 * cache ownership; the collection owns only explicitly adopted derived roots.
 * Caller serializes the context, keeps opaque memo keys/root view hooks alive,
 * and retires all borrowed views/calls before release. Inputs, outputs, errors
 * and callback/allocator state are disjoint; hooks cannot reenter/release it. */
lie_schema_compiler_status lie_schema_compiler_create(
  const lie_schema_compiler_description *, lie_schema_compiler **,
  lie_schema_compiler_error *);
/* Ordered bootstrap: invoke whitespace registration once, then create the
 * original JSON byte primitives in the owned builder. Registration returns an
 * encoded lexeme symbol and retains its own predicate/table lifetime. A hook
 * must not throw. READY and primitive IDs publish only after full success;
 * callback/builder refusal enters FAILED and requires context retirement, with
 * no hook replay. Argument/phase refusals before initialization have no side
 * effects. Native error records retain no spans. */
lie_schema_compiler_status lie_schema_compiler_initialize(lie_schema_compiler *,
  void *, lie_schema_status (*whitespace)(void *, uint32_t *),
  lie_schema_compiler_error *);
/* One-shot publication through schema_compile. Its contracts/ownership remain
 * unchanged. READY -> PUBLISHING -> PUBLISHED on success, or FAILED on refusal
 * after publication begins. Invalid arguments/phase before it have no effects.
 * Repeated/reentrant publication refuses without changing existing outputs.
 * Published program/prompt are independently owned; this context does not
 * retain them and may retire after all schema callbacks/views retire. Their
 * allocator/predicate hooks must still outlive the independent outputs. */
lie_schema_compiler_status lie_schema_compiler_publish(lie_schema_compiler *,
  const lie_schema_compile_description *, lie_schema_node,
  const lie_json_value *, bool object_only, lie_schema_compilation *,
  lie_schema_compiler_error *);
/* Stable borrowed handles/storage, never ownership transfers. Primitive and
 * counter addresses remain stable from NEW through release. Primitive IDs are
 * meaningful only after successful initialization. Mutation uses existing
 * child contracts during compilation and is forbidden after failure/publication.
 * Diagnostics are not aggregate process/model or allocation-exact cost. */
lie_grammar_builder *lie_schema_compiler_builder(lie_schema_compiler *);
lie_schema_memo *lie_schema_compiler_memo(lie_schema_compiler *);
lie_json_store *lie_schema_compiler_store(lie_schema_compiler *);
lie_lexeme_memo *lie_schema_compiler_checks(lie_schema_compiler *);
const lie_builder_primitives *lie_schema_compiler_primitives(const lie_schema_compiler *);
lie_schema_container_counts *lie_schema_compiler_containers(lie_schema_compiler *);
size_t *lie_schema_compiler_enum_values(lie_schema_compiler *);
void lie_schema_compiler_describe(const lie_schema_compiler *, lie_schema_compiler_info *);
void lie_schema_compiler_release(lie_schema_compiler *);
#ifdef __cplusplus
}
#endif
#endif
