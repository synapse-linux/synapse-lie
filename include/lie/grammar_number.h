/* SPDX-License-Identifier: MIT */
#ifndef LIE_GRAMMAR_NUMBER_H
#define LIE_GRAMMAR_NUMBER_H
#include "lie/grammar.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_GRAMMAR_NUMBER_ABI 1u
typedef enum {
  LIE_NUMBER_OK, LIE_NUMBER_INVALID, LIE_NUMBER_RESOURCE,
  LIE_NUMBER_EMPTY_INTERVAL, LIE_NUMBER_EMPTY_GRID, LIE_NUMBER_WORK_LIMIT
} lie_number_status;
typedef struct { const char *data; size_t bytes; } lie_number_text;
typedef struct {
  uint32_t abi_version, struct_bytes;
  bool integer;
  /* A NULL data pointer means absent; present spans are copied at creation. */
  lie_number_text minimum, maximum, exclusive_minimum, exclusive_maximum, multiple;
  size_t max_work;
  lie_grammar_allocator allocator;
} lie_number_description;
typedef struct lie_number_policy lie_number_policy;
typedef struct { bool prefix, complete; } lie_number_match;
void lie_number_description_init(lie_number_description *);
lie_number_status lie_number_create(const lie_number_description *, lie_number_policy **);
void lie_number_release(lie_number_policy *);
/* Add one immutable ownership reference. Caller already holds a live reference;
 * false on NULL/overflow. Paired release retires the final reference only. */
bool lie_number_retain(const lie_number_policy *);
/* Immutable, model-neutral exact decimal predicates. Runtime prefixes use
 * plain JSON decimal spelling, <=4096 bytes, and <=1024 integer shifts.
 * Complete values additionally allow JSON exponent spelling. Schema/value
 * spans are <=4096 bytes, exponents <=4096 in magnitude; internal natural
 * numbers are <=8192 digits. Oversize arithmetic refuses explicitly.
 * Default work budget is 32000000 digit operations per call. Allocator hooks
 * have the same lifetime/alignment/thread rules as lie_grammar_allocator.
 * No floating-point remainder, RNG, device, thread or mutable shared cache.
 * Refusals preserve outputs; a rejected lexical prefix is OK with false flags.
 * Each call owns/retires a bounded workspace; policy is safe to share with
 * caller-synchronized allocator hooks. Output spans must not alias inputs. */
lie_number_status lie_number_check(const lie_number_policy *, lie_number_text, lie_number_match *);
lie_number_status lie_number_accept(const lie_number_policy *, lie_number_text, bool *);
/* Exact positive-decimal LCM, canonical scientific JSON spelling; output has
 * no trailing NUL. JSON library representability is an adapter responsibility.
 * NULL allocator selects malloc/free. max_work=0 selects the default budget. */
lie_number_status lie_number_intersect(lie_number_text, lie_number_text,
  const lie_grammar_allocator *, size_t max_work, char *, size_t, size_t *);
lie_number_status lie_number_equal(lie_number_text, lie_number_text, bool *);
/* Same exact comparison with a caller-owned paired workspace allocator.
 * NULL selects malloc/free. Refusals preserve the result argument. */
lie_number_status lie_number_equal_with_allocator(lie_number_text, lie_number_text,
  const lie_grammar_allocator *, bool *);
/* Compare complete JSON decimal spans exactly, returning -1, 0 or 1. The
 * same 4096-byte/exponent bounds apply. Borrowed spans may alias each other,
 * but must be disjoint from the result. Constant bounded stack storage, no
 * heap, floating point, mutable state or retained pointers. Refusal preserves
 * the result. Equality treats signed zero and equivalent exponents alike. */
lie_number_status lie_number_compare(lie_number_text, lie_number_text, int *);
/* Exact divisibility by a strictly positive decimal step. Negative values
 * and signed zero are allowed; zero is a multiple of every positive step.
 * Reuses bounded decimal division with the declared paired workspace
 * allocator and max_work (0 selects the default). No policy is constructed
 * or retained. Invalid/nonpositive step, aliasing, allocation/work/resource
 * refusal preserves the result and retires the temporary workspace. */
lie_number_status lie_number_multiple_with_allocator(lie_number_text value,
  lie_number_text step, const lie_grammar_allocator *, size_t max_work, bool *);
lie_number_status lie_number_multiple(lie_number_text value,
  lie_number_text step, bool *);
#ifdef __cplusplus
}
#endif
#endif
