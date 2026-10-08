/* SPDX-License-Identifier: MIT */
#ifndef LIE_GRAMMAR_REGEX_PARSE_H
#define LIE_GRAMMAR_REGEX_PARSE_H
#include "lie/grammar_regex_compile.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_REGEX_PARSER_ABI 1u
typedef enum {
  LIE_REGEX_PARSE_OK,
  LIE_REGEX_PARSE_INVALID,
  LIE_REGEX_PARSE_RESOURCE,
  LIE_REGEX_PARSE_WORK_LIMIT,
  LIE_REGEX_PARSE_NODE_LIMIT,
  LIE_REGEX_PARSE_COMPILER,
  LIE_REGEX_PARSE_BYTES,
  LIE_REGEX_PARSE_PARENTHESES,
  LIE_REGEX_PARSE_TRUNCATED,
  LIE_REGEX_PARSE_REPETITION,
  LIE_REGEX_PARSE_REPETITION_LARGE,
  LIE_REGEX_PARSE_HEX,
  LIE_REGEX_PARSE_BOUNDARY_ESCAPE,
  LIE_REGEX_PARSE_OCTAL,
  LIE_REGEX_PARSE_CONTROL,
  LIE_REGEX_PARSE_CODEPOINT,
  LIE_REGEX_PARSE_EMPTY_CODEPOINT,
  LIE_REGEX_PARSE_SURROGATE,
  LIE_REGEX_PARSE_ESCAPE,
  LIE_REGEX_PARSE_PROPERTY_BRACES,
  LIE_REGEX_PARSE_PROPERTY_NAME,
  LIE_REGEX_PARSE_PROPERTY,
  LIE_REGEX_PARSE_RANGE,
  LIE_REGEX_PARSE_NESTING,
  LIE_REGEX_PARSE_GROUP,
  LIE_REGEX_PARSE_NO_ATOM,
  LIE_REGEX_PARSE_ASSERTION_REPEAT
} lie_regex_parse_status;
typedef struct {
  lie_regex_parse_status status;
  lie_regex_compile_status compiler_status;
} lie_regex_parse_error;
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t max_nodes, max_work;
  lie_grammar_allocator allocator;
} lie_regex_parser_description;
/* Unicode-set storage/property/full-set identity is supplied by a separate
 * implementation. Fresh owned sets are released exactly once. All callbacks
 * preserve caller output on refusal; no exception may cross this C contract.
 * range/add/remove use signed codepoints to preserve external set semantics
 * for a singleton string's first=-1. Publish returns an expression in the
 * supplied compiler. Boundary registers the word class before creating its
 * expression. Property receives an ASCII UnicodeSet pattern, not executable
 * text. Callback context is borrowed for this call only. */
typedef struct {
  void *context;
  lie_regex_compile_status (*range)(void *, int32_t, int32_t, void **);
  lie_regex_compile_status (*property)(void *, const char *, size_t, void **);
  lie_regex_compile_status (*add)(void *, void *, const void *);
  lie_regex_compile_status (*add_range)(void *, void *, int32_t, int32_t);
  lie_regex_compile_status (*remove_range)(void *, void *, int32_t, int32_t);
  lie_regex_compile_status (*complement)(void *, void *);
  lie_regex_compile_status (*info)(void *, const void *, uint64_t *, int32_t *);
  lie_regex_compile_status (*publish)(void *, const void *, uint32_t *);
  lie_regex_compile_status (*boundary)(void *, bool, uint32_t *);
  void (*release)(void *, void *);
} lie_regex_unicode_sets;
void lie_regex_parser_description_init(lie_regex_parser_description *);
const char *lie_regex_parse_reason(lie_regex_parse_status);
/* C17 owns syntax parsing, bounded AST storage and iterative assertion
 * expansion into the supplied model-neutral expression compiler. Input UTF16
 * is borrowed; UTF8 decoding/property resolution/full-set identity are
 * external. Original input bytes and UTF16 units must each be <=16384; group
 * depth <=32. Default node/work budgets:65536/32M. No AST or input pointer is
 * retained. Refusal preserves root and previously published programs.
 * Successful compiler memo/expression entries can remain after a refused parse.
 * Error is diagnostic and may change on refusal. Allocator context outlives
 * this synchronous call. No model, device, RNG, inference thread or HTTP
 * dependency. */
lie_regex_parse_status
lie_regex_parse_utf16(lie_regex_compiler *, const uint16_t *, size_t, size_t,
                      const lie_regex_unicode_sets *,
                      const lie_regex_parser_description *, uint32_t *,
                      lie_regex_parse_error *);
#ifdef __cplusplus
}
#endif
#endif
