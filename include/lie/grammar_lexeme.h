/* SPDX-License-Identifier: MIT */
#ifndef LIE_GRAMMAR_LEXEME_H
#define LIE_GRAMMAR_LEXEME_H
#include "lie/grammar_number.h"
#include "lie/grammar_string.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_LEXEME_ABI 1u
typedef enum {
  LIE_LEXEME_OK, LIE_LEXEME_INVALID, LIE_LEXEME_RESOURCE, LIE_LEXEME_LIMIT,
  LIE_LEXEME_NUMBER_WORK, LIE_LEXEME_STRING_WORK, LIE_LEXEME_STRING_STATE,
  LIE_LEXEME_STRING_PHASE, LIE_LEXEME_STRING_EMPTY_LENGTH,
  LIE_LEXEME_STRING_EMPTY_PATTERN, LIE_LEXEME_SEALED
} lie_lexeme_status;
typedef enum { LIE_LEXEME_WHITESPACE, LIE_LEXEME_NUMBER, LIE_LEXEME_STRING } lie_lexeme_kind;
typedef struct lie_grammar_lexeme lie_grammar_lexeme;
typedef struct lie_lexeme_table lie_lexeme_table;
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t max_state_bytes;
  lie_grammar_allocator allocator;
} lie_lexeme_description;
typedef struct { bool prefix, complete; } lie_lexeme_match;
void lie_lexeme_description_init(lie_lexeme_description *);
lie_lexeme_status lie_lexeme_whitespace_create(const lie_lexeme_description *, lie_grammar_lexeme **);
lie_lexeme_status lie_lexeme_number_create(const lie_lexeme_description *, const lie_number_policy *, lie_grammar_lexeme **);
lie_lexeme_status lie_lexeme_string_create(const lie_lexeme_description *, const lie_string_policy *, lie_grammar_lexeme **);
bool lie_lexeme_retain(const lie_grammar_lexeme *);
void lie_lexeme_release(lie_grammar_lexeme *);
lie_lexeme_kind lie_lexeme_type(const lie_grammar_lexeme *);
const lie_number_policy *lie_lexeme_number_policy(const lie_grammar_lexeme *);
bool lie_lexeme_allows(const lie_grammar_lexeme *, uint8_t);
bool lie_lexeme_cache_transitions(const lie_grammar_lexeme *);
lie_lexeme_status lie_lexeme_check(const lie_grammar_lexeme *, const uint8_t *, size_t, lie_lexeme_match *);
lie_lexeme_status lie_lexeme_advance(const lie_grammar_lexeme *, const uint8_t *, size_t,
                                    uint8_t, uint8_t *, size_t, size_t *, lie_lexeme_match *);
lie_lexeme_status lie_lexeme_canonical(const lie_grammar_lexeme *, uint8_t *, size_t, size_t);
/* Immutable C17 tagged predicates own their alphabet/dispatch/options and retain
 * C numeric/DFA policies. Caller already owns a reference for retain; overflow
 * refuses. Final release retires dependencies. Paired aligned allocator hooks
 * outlive all retained references and support caller concurrency. No worker,
 * model, HTTP, RNG or mutable shared cache. Default text/state budget is64MiB.
 * Number advance appends even a rejected byte; string/whitespace rejection keeps
 * encoded state. Numeric prefix length4096 and whitespace length32 semantics
 * are unchanged. Input/output payloads may overlap; metadata/match must be
 * disjoint. Refusals preserve payload/length/match. Canonical changes copied mask
 * keys only. Number/string work limits remain those of the retained policies. */
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t max_items, max_owned_bytes;
  lie_grammar_allocator allocator;
} lie_lexeme_table_description;
typedef struct {
  size_t count, capacity, live_owned_bytes, peak_owned_bytes, allocations;
  bool sealed;
} lie_lexeme_table_info;
void lie_lexeme_table_description_init(lie_lexeme_table_description *);
lie_lexeme_status lie_lexeme_table_create(const lie_lexeme_table_description *, lie_lexeme_table **);
void lie_lexeme_table_release(lie_lexeme_table *);
lie_lexeme_status lie_lexeme_table_reserve(lie_lexeme_table *, size_t);
lie_lexeme_status lie_lexeme_table_push(lie_lexeme_table *, const lie_grammar_lexeme *);
lie_lexeme_status lie_lexeme_table_append(lie_lexeme_table *, const lie_lexeme_table *, size_t, size_t);
lie_lexeme_status lie_lexeme_table_clone(const lie_lexeme_table *, const lie_lexeme_table_description *, lie_lexeme_table **);
size_t lie_lexeme_table_size(const lie_lexeme_table *);
const lie_grammar_lexeme *lie_lexeme_table_at(const lie_lexeme_table *, size_t);
lie_lexeme_status lie_lexeme_table_describe(const lie_lexeme_table *, lie_lexeme_table_info *);
lie_lexeme_status lie_lexeme_table_seal(lie_lexeme_table *);
lie_grammar_predicates lie_lexeme_table_predicates(const lie_lexeme_table *);
bool lie_lexeme_table_cacheable(const void *, const lie_grammar_state *);
/* Construction-only pointer-identity memo. Keys are borrowed opaque identities,
 * never dereferenced; owners outlive the memo. First published predicate wins,
 * matching one cached primitive per immutable schema node. C17 owns bounded
 * hash storage and retained predicates; no mutex, worker, eviction or C++ handle.
 * Reads require quiescent mutations. Defaults/byte exclusions match tables.
 * Refusals preserve entries and outputs; misses publish NULL. */
typedef struct lie_lexeme_memo lie_lexeme_memo;
lie_lexeme_status lie_lexeme_memo_create(const lie_lexeme_table_description *, lie_lexeme_memo **);
void lie_lexeme_memo_release(lie_lexeme_memo *);
const lie_grammar_lexeme *lie_lexeme_memo_get(const lie_lexeme_memo *, const void *);
lie_lexeme_status lie_lexeme_memo_put(lie_lexeme_memo *, const void *, const lie_grammar_lexeme *);
lie_lexeme_status lie_lexeme_memo_describe(const lie_lexeme_memo *, lie_lexeme_table_info *);
/* C17 owns ordered retained predicate pointers, growth, range import and clone.
 * Defaults262144items/64MiB direct requested bytes, including body and overlap
 * during growth; retained predicates/policies, allocator overhead, stack, C++
 * projections and process/device costs are excluded. Refusals preserve contents
 * and published outputs; allocation/peak/capacity diagnostics may advance.
 * Child predicate identity survives growth. Mutations require caller serialization.
 * Seal irreversibly refuses mutations; immutable reads may be concurrent.
 * Clone creates an independent mutable table with retained immutable predicates.
 * Append supports self-import. Borrowed predicates/hooks/context remain valid
 * until table release, which requires retiring all calls/grammar borrowers.
 * The returned C dispatch hooks require sealing and contain no C++ callbacks. */
#ifdef __cplusplus
}
#endif
#endif
