/* SPDX-License-Identifier: MIT */
#ifndef LIE_SCHEMA_STRING_H
#define LIE_SCHEMA_STRING_H
#include "lie/schema_transform.h"
#include "lie/schema_format.h"
#include "lie/grammar_unicode.h"
#include "lie/grammar_lexeme.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_SCHEMA_STRING_ABI 1u
typedef struct {
  uint32_t abi_version, struct_bytes;
  lie_schema_transform_description transform;
  lie_grammar_unicode_description unicode;
  lie_regex_parser_description parser;
  lie_lexeme_description lexeme;
} lie_schema_string_description;
typedef struct {
  uint32_t abi_version, struct_bytes, minimum, maximum;
  bool has_pattern;
  lie_schema_bytes pattern;
  size_t format_bytes;
  char format[LIE_SCHEMA_FORMAT_PATTERN_CAPACITY];
} lie_schema_string_plan;
typedef struct {
  lie_schema_error schema_error;
  lie_regex_compile_status compiler_status;
  lie_regex_parse_error parse_error;
  lie_string_status string_status;
  lie_lexeme_status lexeme_status;
} lie_schema_string_error;
void lie_schema_string_description_init(lie_schema_string_description *);
/* Ordered C17 string policy admission: lengths first, then pattern/format,
 * hostname narrowing and copied format expansion. No heap allocation. Pattern
 * bytes borrow immutable input; format bytes belong to the plan and plans may
 * be copied by value. Refusal preserves the plan. Reader and transform counted
 * work bounds apply. Input/output/error and callback storage are disjoint. */
lie_schema_status lie_schema_string_prepare(const lie_schema_string_description *,
  lie_schema_node, lie_schema_string_plan *, lie_schema_string_error *);
/* Consume an unchanged plan produced by prepare. Compile pattern followed by
 * format, intersect their languages, seal C17 Unicode DFA, validate lengths and
 * publish an independently owned immutable lexeme. No C++ regex/schema types.
 * Original minLength/maxLength ordering precedes format narrowing; a hostname
 * narrowing conflict is EMPTY_PATTERN, after regex compilation, not EMPTY_LENGTH.
 * Child allocator hooks inherit the paired transform hooks unless explicitly
 * overridden. All hooks outlive independently published lexemes/programs.
 * Unicode/property conversion remains ICU through its C API; its allocations
 * are outside these hooks. Refusals preserve *output and retire all staging.
 * A non-NULL unrestricted program must be the immutable full scalar language
 * produced below; it is borrowed for this call and retained by the new lexeme.
 * Use it only for plans with neither pattern nor format; never bypass a pattern.
 * This optional caller-owned reuse has no global cache, thread, model or HTTP. */
lie_schema_status lie_schema_string_compile(const lie_schema_string_description *,
  const lie_schema_string_plan *, const lie_regex_program *unrestricted,
  lie_grammar_lexeme **, lie_schema_string_error *);
/* Build the reusable full scalar language with unlimited maximum. Owner may
 * retain one per compilation/client; this call publishes no process-global state. */
lie_schema_status lie_schema_string_unrestricted(const lie_schema_string_description *,
  lie_regex_program **, lie_schema_string_error *);
/* Convenience prepare + compile without a retained unrestricted program. */
lie_schema_status lie_schema_string_create(const lie_schema_string_description *,
  lie_schema_node, lie_grammar_lexeme **, lie_schema_string_error *);
#ifdef __cplusplus
}
#endif
#endif
