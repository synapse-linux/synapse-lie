/* SPDX-License-Identifier: MIT */
#ifndef LIE_SCHEMA_INTEGER_H
#define LIE_SCHEMA_INTEGER_H
#include "lie/schema_transform.h"
#include "lie/grammar_builder.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_SCHEMA_INTEGER_ABI 1u
#define LIE_SCHEMA_INTEGER_TEXT_CAPACITY 512u
/* Exact unsigned magnitude of a finite, integral IEEE754 binary64, including
 * values outside int64. No rounding, shortest-decimal padding, locale, heap,
 * floating-environment mutation or retained pointers. Zero and -0 spell 0.
 * Writes no NUL and preserves output bytes/length on refusal. Output spans
 * must be disjoint. Insufficient capacity returns LIE_SCHEMA_RESOURCE. */
lie_schema_status lie_schema_integer_magnitude(double, char *, size_t, size_t *);
/* Borrowed reader and work budget follow schema_transform. C17 owns ordered
 * bound lookup, ceil/floor, exact magnitude, exclusivity, empty-interval checks
 * and ordered positive/negative/-0 grammar construction. The caller supplies
 * a valid unrestricted integer symbol belonging to the same private builder.
 * Refusal preserves result; retire a builder after any failed mutation.
 * Scratch is bounded stack storage. Builder-owned allocation uses its own
 * paired allocator. No model, HTTP, RNG, thread or mutable cache ownership. */
lie_schema_status lie_schema_integer_compile(
  const lie_schema_transform_description *, lie_schema_node,
  lie_grammar_builder *, uint32_t unrestricted, uint32_t *, lie_schema_error *);
#ifdef __cplusplus
}
#endif
#endif
