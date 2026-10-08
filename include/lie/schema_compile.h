/* SPDX-License-Identifier: MIT */
#ifndef LIE_SCHEMA_COMPILE_H
#define LIE_SCHEMA_COMPILE_H
#include "lie/schema_root.h"
#include "lie/json_value.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_SCHEMA_COMPILE_ABI 1u
typedef struct lie_schema_prompt lie_schema_prompt;
typedef enum {
  LIE_COMPILE_OK, LIE_COMPILE_INVALID, LIE_COMPILE_SCHEMA, LIE_COMPILE_JSON,
  LIE_COMPILE_RESOURCE, LIE_COMPILE_PROMPT_LIMIT, LIE_COMPILE_BUILDER,
  LIE_COMPILE_BINDING, LIE_COMPILE_PROGRAM
} lie_schema_compile_status;
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t max_schema_bytes, max_owned_prompt_bytes;
  lie_grammar_allocator allocator;
  lie_schema_root_description root;
  void *binding_context;
  size_t (*lexeme_count)(void *);
  lie_grammar_status (*bind)(void *, lie_grammar_predicates *);
} lie_schema_compile_description;
typedef struct {
  lie_schema_status schema_status;
  lie_schema_error schema_error;
  lie_json_value_status json_status;
  lie_builder_status builder_status;
  lie_grammar_status grammar_status;
} lie_schema_compile_error;
typedef struct {
  lie_grammar_program *program;
  lie_schema_prompt *prompt;
  uint32_t root;
} lie_schema_compilation;
typedef struct {
  size_t bytes, capacity, live_owned_bytes, peak_owned_bytes, allocations;
} lie_schema_prompt_info;
void lie_schema_compile_description_init(lie_schema_compile_description *);
/* Complete synchronous publication workflow: root admission/visit, exact
 * native JSON prompt serialization, builder finalization, predicate binding,
 * immutable program creation and initial-state validation. Original schema is visited, not its resolved
 * root. object_only skips schema reads/dump and uses the existing fixed text.
 * Opaque schema and native_schema describe the SAME stable immutable input;
 * object_only permits both NULL. Reader/visitor and binding hooks cannot throw,
 * reenter this call or retain staging spans. lexeme_count runs after visit and
 * serialization; bind runs after successful builder finalization. Predicate
 * contexts outlive the published program/states. Callers serialize builder and
 * callbacks, and retire the entire failed compilation; earlier builder/visitor
 * mutations may remain. No model, device, HTTP, thread, RNG or mutable cache.
 * Output changes only on full success. Program and prompt have independent
 * ownership and both require release; builder/input may retire after success.
 * Default serialized-schema bound2MiB; prompt heap bound8MiB includes context,
 * terminating NUL, capacity and growth overlap, excludes input/builder/program
 * heap and allocator overhead. Paired max_align_t-aligned allocator hooks
 * outlive BOTH outputs. The program inherits builder limits, uses these hooks
 * for its own copied tables, and retains existing program accounting. Prompt
 * text is immutable exact bytes and stays valid until its separate release.
 * Error fields are meaningful on refusal; schema error spans borrow input.
 * All caller outputs and allocator/callback state are disjoint from input. */
lie_schema_compile_status lie_schema_compile(
  const lie_schema_compile_description *, lie_schema_node schema,
  const lie_json_value *native_schema, bool object_only, lie_grammar_builder *,
  uint32_t whitespace, lie_schema_compilation *, lie_schema_compile_error *);
const char *lie_schema_prompt_bytes(const lie_schema_prompt *, size_t *);
void lie_schema_prompt_describe(const lie_schema_prompt *, lie_schema_prompt_info *);
void lie_schema_prompt_release(lie_schema_prompt *);
#ifdef __cplusplus
}
#endif
#endif
