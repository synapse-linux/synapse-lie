/* SPDX-License-Identifier: MIT */
#ifndef LIE_GRAMMAR_REGEX_COMPILE_H
#define LIE_GRAMMAR_REGEX_COMPILE_H
#include "lie/grammar_regex.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_REGEX_COMPILER_ABI 1u
typedef enum {
  LIE_REGEX_COMPILE_OK,
  LIE_REGEX_COMPILE_INVALID,
  LIE_REGEX_COMPILE_RESOURCE,
  LIE_REGEX_COMPILE_EXPRESSION_LIMIT,
  LIE_REGEX_COMPILE_DERIVATIVE_LIMIT,
  LIE_REGEX_COMPILE_STATE_LIMIT,
  LIE_REGEX_COMPILE_CLASS_LIMIT,
  LIE_REGEX_COMPILE_WORK_LIMIT,
  LIE_REGEX_COMPILE_REPETITION
} lie_regex_compile_status;
typedef enum {
  LIE_REGEX_UNION,
  LIE_REGEX_INTERSECTION,
  LIE_REGEX_CONCATENATION
} lie_regex_operation;
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t max_expressions, max_derivatives, max_states, max_transitions,
      max_ranges, max_work;
  uint32_t maximum_length;
  lie_grammar_allocator allocator;
} lie_regex_compiler_description;
typedef struct {
  uint32_t empty, epsilon, start, any, all;
} lie_regex_bases;
typedef struct lie_regex_compiler lie_regex_compiler;
void lie_regex_compiler_description_init(lie_regex_compiler_description *);
lie_regex_compile_status
lie_regex_compiler_create(const lie_regex_compiler_description *,
                          lie_regex_compiler **);
void lie_regex_compiler_release(lie_regex_compiler *);
lie_regex_compile_status lie_regex_compiler_bases(const lie_regex_compiler *,
                                                  lie_regex_bases *);
/* Class IDs retain insertion order and semantic identity supplied by the
 * parser. Equal scalar ranges with different external Unicode metadata may be
 * separate classes. Ranges are copied, sorted/disjoint and exclude UTF16
 * surrogates; an empty range list remains a structural character-class
 * expression. */
lie_regex_compile_status lie_regex_class_add(lie_regex_compiler *,
                                             const lie_unicode_range *, size_t,
                                             uint32_t *);
lie_regex_compile_status lie_regex_chars(lie_regex_compiler *, uint32_t,
                                         uint32_t *);
lie_regex_compile_status lie_regex_boundary(lie_regex_compiler *, bool,
                                            uint32_t *);
lie_regex_compile_status lie_regex_not(lie_regex_compiler *, uint32_t,
                                       uint32_t *);
lie_regex_compile_status lie_regex_combine(lie_regex_compiler *,
                                           lie_regex_operation,
                                           const uint32_t *, size_t,
                                           uint32_t *);
lie_regex_compile_status lie_regex_repeat(lie_regex_compiler *, uint32_t,
                                          uint32_t, uint32_t, uint32_t *);
lie_regex_compile_status lie_regex_nullable(const lie_regex_compiler *,
                                            uint32_t, bool, bool, bool, bool *);
lie_regex_compile_status lie_regex_derive(lie_regex_compiler *, uint32_t,
                                          uint32_t, bool, bool, uint32_t *);
lie_regex_compile_status lie_regex_seal(lie_regex_compiler *, uint32_t,
                                        lie_regex_program **);
/* Model-neutral mutable construction context, immutable published programs.
 * C17 owns normalized expression DAG/minimum widths/nullable context bits,
 * iterative memoized derivatives, Unicode membership partitioning and BFS
 * state interning. No parser, Unicode property database or model/device/thread
 * dependency. Parser-supplied expressions compose a complete scalar language.
 * Boundary compilation adds word membership to the partition even when the
 * parser supplies no explicit word class. Source budgets default to32768
 * expressions,1048576derivatives,4096states,262144transitions/ranges and256M
 * counted work units. UINT32_MAX is infinite maximum/repetition.
 * Paired fresh aligned allocator hooks/default malloc/free outlive construction
 * and published programs. Caller synchronizes construction. Refusals preserve
 * outputs; successful internal memo entries may remain after a refused
 * operation. Seal owns and retires its temporary graph and copies into the
 * runtime program. Previously published programs never change. No mutable
 * global cache/RNG/HTTP. */
#ifdef __cplusplus
}
#endif
#endif
