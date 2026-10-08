/* SPDX-License-Identifier: MIT */
#ifndef LIE_GRAMMAR_REGEX_H
#define LIE_GRAMMAR_REGEX_H
#include "lie/grammar.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_REGEX_ABI 1u
#define LIE_REGEX_DEAD UINT32_MAX
typedef enum { LIE_REGEX_OK, LIE_REGEX_INVALID, LIE_REGEX_RESOURCE, LIE_REGEX_WORK_LIMIT } lie_regex_status;
typedef struct { uint32_t first, last; } lie_unicode_range;
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t max_states, max_transitions, max_ranges, max_work;
} lie_regex_limits;
typedef struct {
  uint32_t abi_version, struct_bytes;
  const lie_grammar_range *classes;
  size_t class_count;
  const lie_unicode_range *ranges;
  size_t range_count;
  const uint8_t *accepting;
  size_t state_count;
  /* Row-major state_count * class_count targets, or LIE_REGEX_DEAD. */
  const uint32_t *transitions;
  lie_grammar_allocator allocator;
  lie_regex_limits limits;
} lie_regex_description;
typedef struct lie_regex_program lie_regex_program;
void lie_regex_description_init(lie_regex_description *);
lie_regex_status lie_regex_create(const lie_regex_description *, lie_regex_program **);
void lie_regex_release(lie_regex_program *);
/* Add one immutable ownership reference; caller already holds a live reference.
 * false on NULL/overflow. Existing release retires the final reference only. */
bool lie_regex_retain(const lie_regex_program *);
size_t lie_regex_state_count(const lie_regex_program *);
uint32_t lie_regex_maximum_suffix(const lie_regex_program *);
lie_regex_status lie_regex_accepting(const lie_regex_program *, uint32_t, bool *);
lie_regex_status lie_regex_advance(const lie_regex_program *, uint32_t, uint32_t, uint32_t *);
lie_regex_status lie_regex_can_finish(const lie_regex_program *, uint32_t, uint32_t, uint32_t, bool *);
lie_regex_status lie_regex_can_advance(const lie_regex_program *, uint32_t,
  uint32_t first, uint32_t last, uint32_t minimum, uint32_t maximum, bool *);
/* Model-neutral copied immutable Unicode DFA tables, not a regex compiler.
 * Create owns unique successor/predecessor construction, shortest accepting
 * distances, unreachable-edge pruning and maximum suffix. Runtime owns range
 * lookup, bounded reachability and Brent cycle skipping for length constraints.
 * State zero is the start. Ranges within a class are sorted/disjoint/scalar;
 * overlapping classes preserve first-class priority for single-codepoint advance.
 * Default budgets:4096 states,262144 transitions/ranges,256000000 counted work
 * units. Paired fresh aligned allocator hooks have grammar allocator lifetimes.
 * Queries allocate scratch lazily only when minimum-length reachability needs
 * it, and release on all paths. Refusals preserve outputs. No model, device,
 * thread, RNG, mutable global cache or transport operation. */
#ifdef __cplusplus
}
#endif
#endif
