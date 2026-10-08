/* SPDX-License-Identifier: MIT */
#ifndef LIE_GRAMMAR_COMPOSITION_H
#define LIE_GRAMMAR_COMPOSITION_H
#include "lie/grammar.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_GRAMMAR_COMPOSITION_ABI 1u
typedef enum {
  LIE_COMPOSITION_OK, LIE_COMPOSITION_INVALID, LIE_COMPOSITION_RESOURCE,
  LIE_COMPOSITION_TABLE_LIMIT, LIE_COMPOSITION_WORK_LIMIT
} lie_composition_status;
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t max_rules, max_sequences, max_symbols, max_classes, max_lexemes;
  size_t max_work;
  lie_grammar_allocator allocator;
} lie_composition_description;
typedef struct {
  const uint8_t *name;
  size_t name_bytes;
  const lie_grammar_program *arguments;
} lie_composition_tool;
typedef struct {
  const lie_grammar_program *program;
  uint32_t index;
} lie_composition_lexeme;
typedef struct {
  lie_grammar_description grammar;
  const lie_composition_lexeme *lexemes;
  bool stop_only_when_complete;
  size_t work, owned_bytes, peak_owned_bytes;
} lie_composition_view;
typedef struct lie_grammar_composition lie_grammar_composition;
void lie_composition_description_init(lie_composition_description *);
/* Synchronous, request-independent immutable construction. C owns ordered
 * marker automata, JSON name quoting, identity-based imports, symbol remapping,
 * alternatives and stop policy. No pruning, predicate calls, threads, global
 * cache, model/device/HTTP operations or RNG. Inputs are immutable and valid
 * for the call; source programs referenced by lexeme origins remain alive until
 * those origins are consumed. All tables/names are copied. Paired allocation
 * hooks are nonthrowing and caller-synchronized. Refusal retires partial work
 * and preserves *output; success is released by the caller. */
lie_composition_status lie_composition_reasoning(
  const lie_composition_description *, const lie_grammar_program *, bool,
  lie_grammar_composition **output);
/* base is the answer, or the caller's generic object grammar when plain=true.
 * Nonempty tools are required. The base's first256 classes must be literal
 * byte singletons. Repeated argument program identities are imported once;
 * when plain=false the base is already imported. Strict/parallel/plain policy
 * is independent of a provider's model and transport. */
lie_composition_status lie_composition_tools(
  const lie_composition_description *, const lie_grammar_program *base,
  bool plain, const lie_composition_tool *, size_t tool_count,
  bool required, bool parallel, lie_grammar_composition **output);
/* The view borrows tables/origins until composition release. Its description
 * has no predicates/allocator context: the caller binds imported immutable
 * predicates then creates an independent runtime program. Output is unchanged
 * on refusal. Owned byte accounting excludes caller programs, predicates and
 * private import storage. */
lie_composition_status lie_composition_describe(const lie_grammar_composition *,
                                               lie_composition_view *);
void lie_composition_release(lie_grammar_composition *);
#ifdef __cplusplus
}
#endif
#endif
