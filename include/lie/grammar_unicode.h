/* SPDX-License-Identifier: MIT */
#ifndef LIE_GRAMMAR_UNICODE_H
#define LIE_GRAMMAR_UNICODE_H
#include "lie/grammar_regex_parse.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_GRAMMAR_UNICODE_ABI 1u
typedef struct lie_grammar_unicode lie_grammar_unicode;
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t max_classes;
  lie_regex_compiler_description compiler;
} lie_grammar_unicode_description;
void lie_grammar_unicode_description_init(lie_grammar_unicode_description *);
lie_regex_compile_status
lie_grammar_unicode_create(const lie_grammar_unicode_description *,
                           lie_grammar_unicode **);
void lie_grammar_unicode_release(lie_grammar_unicode *);
/* Borrowed compiler and synchronous hooks. No ICU type crosses this header.
 * The context owns compiler/class registry, scalar-range translations and
 * decode storage. ICU remains the dependency providing set/property/string
 * semantics and conversion. Published sets are private immutable copies;
 * scalar-identical sets with different string members remain distinct.
 * Paired aligned allocator hooks are the compiler hooks and outlive context
 * and sealed runtime programs. ICU's internal allocations use its allocator;
 * these hooks do not establish fault coverage of ICU itself. Caller serializes
 * construction. Only this context may add compiler classes; the borrowed
 * compiler allows expression construction, queries and sealing. Successful
 * class/expression entries may remain after refusal.
 */
lie_regex_compiler *lie_grammar_unicode_compiler(lie_grammar_unicode *);
lie_regex_compile_status lie_grammar_unicode_sets(lie_grammar_unicode *,
                                                  lie_regex_unicode_sets *);
/* Replacement decoding agrees with ICU UnicodeString::fromUTF8. Input <=16384
 * bytes; explicit lengths preserve NUL. Buffers and length may not overlap.
 * Refused input
 * or capacity preserves destination and length; no retained input pointer. */
lie_regex_compile_status
lie_grammar_utf8_to_utf16(const char *, size_t, uint16_t *, size_t, size_t *);
lie_regex_parse_status
lie_grammar_unicode_parse(lie_grammar_unicode *, const char *, size_t,
                          const lie_regex_parser_description *, uint32_t *,
                          lie_regex_parse_error *);
/* Diagnostic version strings are ICU/data identities, not model/cache IDs. */
lie_regex_compile_status lie_grammar_unicode_versions(char *, size_t, char *,
                                                      size_t);
#ifdef __cplusplus
}
#endif
#endif
