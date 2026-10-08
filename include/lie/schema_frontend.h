/* SPDX-License-Identifier: MIT */
#ifndef LIE_SCHEMA_FRONTEND_H
#define LIE_SCHEMA_FRONTEND_H
#include "lie/schema_compiler.h"
#include "lie/schema_arena.h"
#include "lie/schema_string.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_SCHEMA_FRONTEND_ABI 1u
typedef struct lie_schema_frontend lie_schema_frontend;
typedef enum { LIE_FRONTEND_OK, LIE_FRONTEND_INVALID, LIE_FRONTEND_RESOURCE,
  LIE_FRONTEND_COMPILER, LIE_FRONTEND_LEXEME, LIE_FRONTEND_SCHEMA,
  LIE_FRONTEND_PUBLICATION, LIE_FRONTEND_PHASE } lie_schema_frontend_status;
typedef enum { LIE_FRONTEND_NEW, LIE_FRONTEND_COMPILING,
  LIE_FRONTEND_PUBLISHED, LIE_FRONTEND_FAILED } lie_schema_frontend_phase;
typedef enum { LIE_FRONTEND_ERROR_SCHEMA, LIE_FRONTEND_ERROR_STRING,
  LIE_FRONTEND_ERROR_LEXEME, LIE_FRONTEND_ERROR_ARENA } lie_schema_frontend_origin;
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t max_error_bytes, number_work;
  lie_grammar_allocator allocator;
  lie_schema_compiler_description compiler;
  lie_schema_arena_description arena;
  lie_schema_string_description strings;
  lie_lexeme_table_description lexemes;
  lie_schema_compile_description publication;
  /* Optional caller-owned full scalar language from schema_string_unrestricted.
   * NULL enables lazy per-compilation creation/reuse. Borrow until release. */
  const lie_regex_program *unrestricted;
} lie_schema_frontend_description;
typedef struct {
  lie_schema_frontend_origin origin;
  lie_schema_status schema_status;
  lie_schema_error schema_error;
  lie_schema_string_error string_error;
  lie_schema_arena_error arena_error;
  lie_lexeme_status lexeme_status;
  lie_schema_compiler_status compiler_status;
  lie_schema_compiler_error compiler_error;
} lie_schema_frontend_error;
typedef struct {
  lie_schema_compilation compilation;
  lie_lexeme_table *lexemes;
} lie_schema_frontend_output;
typedef struct {
  lie_schema_frontend_phase phase;
  size_t context_bytes, retained_error_bytes;
  lie_schema_compiler_info compiler;
  lie_lexeme_table_info lexemes;
} lie_schema_frontend_info;
void lie_schema_frontend_description_init(lie_schema_frontend_description *);
/* Complete native C17 frontend, no typed schema/regex factory callbacks.
 * Owns compilation state, copied derived roots, predicate registration/memos,
 * temporary body/normalization arenas, leaf policies and diagnostics. Uses
 * existing body/visit/container/numeric/string/root/publication contracts.
 * Create initializes whitespace/JSON primitives; partial creation retires.
 * Parent paired allocator inherits into unspecified child hooks. Requested
 * error-detail storage defaults to2MiB, excludes context/child heaps/overhead.
 * Reader/writer bindings are native and override supplied access callbacks.
 * Hooks are caller-serialized/nonthrowing/nonreentrant and outlive retained
 * output dependencies. No model, worker, HTTP, RNG or mutable global cache. */
lie_schema_frontend_status lie_schema_frontend_create(
  const lie_schema_frontend_description *, lie_schema_frontend **,
  lie_schema_frontend_error *);
/* One compilation per context; failure/publication requires retirement.
 * Schema is a stable borrowed native JSON tree; object_only permits NULL.
 * Success publishes program/prompt and sealed lexeme table as separate owners.
 * Program/states BORROW that table: retire them before releasing the table.
 * Input/context may retire after success. Allocator hooks retain output lifetime.
 * Refusal preserves output and copies diagnostic details before temporary trees
 * retire. Error spans borrow the frontend until release (input need not survive
 * diagnostic inspection). Retained diagnostic storage can itself refuse, then
 * RESOURCE replaces that refusal. No output/error/input/allocator-state alias.
 * EMPTY bodies retain existing placeholder/finite-language semantics. Existing
 * schema depth/enum/character/reference/private child bounds remain unchanged. */
lie_schema_frontend_status lie_schema_frontend_compile(lie_schema_frontend *,
  const lie_json_value *, bool strict, bool object_only,
  lie_schema_frontend_output *, lie_schema_frontend_error *);
void lie_schema_frontend_describe(const lie_schema_frontend *, lie_schema_frontend_info *);
void lie_schema_frontend_release(lie_schema_frontend *);
/* Output is a move-only ownership record: never shallow-copy owning records.
 * Release retires program before predicate table and resets the record. */
void lie_schema_frontend_output_release(lie_schema_frontend_output *);
#ifdef __cplusplus
}
#endif
#endif
