/* SPDX-License-Identifier: MIT */
#ifndef LIE_GRAMMAR_STRING_H
#define LIE_GRAMMAR_STRING_H
#include "lie/grammar_regex.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_STRING_ABI 1u
#define LIE_STRING_STATE_BYTES 20u
typedef enum {
  LIE_STRING_OK, LIE_STRING_INVALID, LIE_STRING_STATE, LIE_STRING_PHASE,
  LIE_STRING_RESOURCE, LIE_STRING_WORK_LIMIT, LIE_STRING_EMPTY_LENGTH, LIE_STRING_EMPTY_PATTERN
} lie_string_status;
typedef struct {
  uint32_t abi_version, struct_bytes, minimum, maximum;
  bool scalar_only;
  const lie_regex_program *regex;
} lie_string_policy;
typedef struct { bool prefix, complete; } lie_string_match;
void lie_string_policy_init(lie_string_policy *);
lie_string_status lie_string_policy_validate(const lie_string_policy *);
lie_string_status lie_string_advance(const lie_string_policy *, uint8_t *, size_t *,
  size_t capacity, uint8_t byte, lie_string_match *);
lie_string_status lie_string_check(const lie_string_policy *, const uint8_t *, size_t, lie_string_match *);
lie_string_status lie_string_canonical(const lie_string_policy *, uint8_t *, size_t, size_t token_bytes);
lie_string_match lie_string_whitespace(uint8_t *count, uint8_t byte);
/* Model-neutral immutable caller-owned policy borrows a sealed regex program,
 * which must outlive all calls. scalar_only is a compiler assertion that the
 * regex accepts every scalar sequence; it must never bypass a restrictive DFA.
 * Init selects unconstrained bounds but requires
 * a regex before validation. State encoding is exactly five native uint32_t
 * fields (DFA/count/value/extra/mode), 20 bytes; no persisted/wire endian format.
 * Length0 is unstarted; length20 is started. Advance accepts exact in-place
 * storage; refusals preserve state, length and match. Rejected lexical bytes
 * return OK with false flags and unchanged state; closing quote changes only
 * the match, as in the pinned runtime. Canonical changes only a copied mask key,
 * never the live count. Check parses a full JSON-quoted spelling incrementally.
 * UTF8, JSON escapes, surrogate pairs, pending ranges and length counts belong
 * to C17. Regex scratch is caller-program allocated only for length queries.
 * No thread, device, model, RNG, transport or mutable global cache. */
#ifdef __cplusplus
}
#endif
#endif
