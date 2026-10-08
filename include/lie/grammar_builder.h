/* SPDX-License-Identifier: MIT */
/* Shared, model-neutral grammar construction; JSON tree traversal is separate. */
#ifndef LIE_GRAMMAR_BUILDER_H
#define LIE_GRAMMAR_BUILDER_H
#include "lie/grammar.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_GRAMMAR_BUILDER_ABI 1u
typedef enum {
  LIE_BUILDER_OK, LIE_BUILDER_INVALID, LIE_BUILDER_RESOURCE,
  LIE_BUILDER_RULE_LIMIT, LIE_BUILDER_TABLE_LIMIT, LIE_BUILDER_WORK_LIMIT,
  LIE_BUILDER_CYCLE, LIE_BUILDER_EMPTY
} lie_builder_status;
typedef struct { const uint32_t *symbols; size_t count; } lie_builder_sequence;
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t max_rules, max_sequences, max_symbols, max_classes, max_work;
  lie_grammar_allocator allocator;
} lie_builder_description;
typedef struct lie_grammar_builder lie_grammar_builder;
typedef struct { uint32_t whitespace, string, integer, number, boolean, null_value; }
  lie_builder_primitives;
void lie_builder_description_init(lie_builder_description *);
lie_builder_status lie_builder_create(const lie_builder_description *, lie_grammar_builder **);
void lie_builder_release(lie_grammar_builder *);
/* The builder owns all tables and copies input spans. Literal byte classes
 * occupy indices 0..255. Hooks follow lie_grammar_allocator's lifetime rules.
 * Construction is synchronous and caller-serialized, with no model/device,
 * thread, RNG, HTTP or mutable global cache. Refusal preserves output arguments;
 * a failed mutation latches its status and the caller must retire the builder.
 * Earlier successful primitives may remain after failure. Finalization seals
 * the builder, which then rejects further mutation. Default construction work
 * is 64 million counted units; it is neither timing nor a speedup metric. */
lie_builder_status lie_builder_new(lie_grammar_builder *, const lie_builder_sequence *, size_t, uint32_t *);
lie_builder_status lie_builder_set(lie_grammar_builder *, uint32_t, const lie_builder_sequence *, size_t);
lie_builder_status lie_builder_sequence_make(lie_grammar_builder *, const uint32_t *, size_t, uint32_t *);
lie_builder_status lie_builder_alternatives(lie_grammar_builder *, const uint32_t *, size_t, uint32_t *);
lie_builder_status lie_builder_class(lie_grammar_builder *, const uint8_t *, size_t, uint32_t *);
lie_builder_status lie_builder_range(lie_grammar_builder *, unsigned, unsigned, uint32_t *);
lie_builder_status lie_builder_literal(lie_grammar_builder *, const uint8_t *, size_t, uint32_t *);
lie_builder_status lie_builder_optional(lie_grammar_builder *, uint32_t, uint32_t *);
lie_builder_status lie_builder_repeat(lie_grammar_builder *, uint32_t, uint32_t *);
lie_builder_status lie_builder_exact(lie_grammar_builder *, uint32_t, size_t, uint32_t *);
lie_builder_status lie_builder_at_most(lie_grammar_builder *, uint32_t, size_t, uint32_t *);
/* Bootstrap keeps the pinned JSON byte grammar, including UTF8 and surrogate
 * pair escapes. whitespace is a caller-owned lexeme symbol, not a predicate. */
lie_builder_status lie_builder_json(lie_grammar_builder *, uint32_t whitespace, lie_builder_primitives *);
lie_builder_status lie_builder_generic_value(lie_grammar_builder *, size_t depth, uint32_t *);
lie_builder_status lie_builder_generic_object(lie_grammar_builder *, size_t depth, uint32_t *);
/* Canonical unsigned decimal bounds, at most 512 digits. NULL high means no
 * upper bound. Digit-prefix construction is independent of interval width. */
lie_builder_status lie_builder_unsigned(lie_grammar_builder *, const char *, size_t, const char *, size_t, uint32_t *);
lie_builder_status lie_builder_digits(lie_grammar_builder *, const char *, const char *, size_t, uint32_t *);
/* Compute productive/nullable fixed points, reject every non-consuming cycle,
 * then discard impossible alternatives and publish dense immutable tables.
 * Predicate/allocator contexts remain caller-owned. The returned description
 * borrows tables until builder release; program_create copies them. Set its
 * predicates before creating a program with lexemes. Refusal publishes nothing. */
lie_builder_status lie_builder_finish(lie_grammar_builder *, uint32_t root, size_t lexemes, lie_grammar_description *);
#ifdef __cplusplus
}
#endif
#endif
