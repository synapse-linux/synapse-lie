/* SPDX-License-Identifier: MIT */
#ifndef LIE_JSON_VALUE_H
#define LIE_JSON_VALUE_H
#include "lie/json_parse.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_JSON_VALUE_ABI 1u
#define LIE_JSON_VALUE_MAX_DEPTH 512u
typedef enum {
  LIE_JSON_VALUE_OK, LIE_JSON_VALUE_INVALID, LIE_JSON_VALUE_RESOURCE,
  LIE_JSON_VALUE_LIMIT, LIE_JSON_VALUE_SYNTAX, LIE_JSON_VALUE_CALLBACK,
  LIE_JSON_VALUE_NONFINITE
} lie_json_value_status;
typedef enum {
  LIE_JSON_VALUE_NULL, LIE_JSON_VALUE_BOOL, LIE_JSON_VALUE_NUMBER,
  LIE_JSON_VALUE_STRING, LIE_JSON_VALUE_ARRAY, LIE_JSON_VALUE_OBJECT
} lie_json_value_kind;
typedef struct lie_json_value lie_json_value;
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t max_owned_bytes, max_nodes, max_work;
  unsigned max_depth;
  lie_grammar_allocator allocator;
  /* Optional private facade storage, aligned to max_align_t. Hooks are paired,
   * nonthrowing; initialize returns false to refuse and must retire its own
   * partial projection before false. release runs only after true. Context is
   * borrowed and hooks cannot mutate the tree or reenter an operation. */
  size_t view_bytes;
  void *view_context;
  bool (*view_initialize)(void *, lie_json_value *, void *);
  void (*view_release)(void *, void *);
} lie_json_value_description;
typedef struct {
  size_t live_owned_bytes, peak_owned_bytes, live_nodes, allocations;
} lie_json_value_info;
typedef struct {
  void *context;
  bool (*write)(void *, const char *, size_t);
} lie_json_value_sink;
void lie_json_value_description_init(lie_json_value_description *);
/* C17 owns scalar payloads, exact byte strings/keys, ordered child tables,
 * cloning, replacement, traversal and serialization. No model/HTTP/RNG/thread.
 * Defaults:64MiB requested heap,262144 nodes,268435456 copy/output work units,
 * 512 levels. Allocator hooks outlive roots, return max_align_t-aligned fresh
 * storage and are paired/caller-synchronized. Info includes context, facade
 * storage and growth overlap, excludes allocator overhead, stack and facade
 * allocations made outside this allocator. Each root owns its own domain.
 * All mutations preserve observable content and output pointers on refusal;
 * diagnostic allocation/peak counters may advance. Child/view/byte pointers
 * are borrowed until the containing payload is replaced or root is released.
 * release accepts ROOTS only. Node identity survives assignment; child handles
 * are stable across sibling insertion. Queries accept NULL as a null value.
 * Spans are exact bytes including embedded NUL. append_member allows duplicates;
 * find/member use the first exact key. Parsing independently rejects duplicates.
 * Coercing to array/object clears only that table, retaining the other inactive
 * table, matching the transitional ordered-value contract. size is active;
 * array_size/object_size expose inactive tables for private compatibility. */
lie_json_value_status lie_json_value_create(const lie_json_value_description *,
                                            lie_json_value **);
void lie_json_value_release(lie_json_value *);
lie_json_value_status lie_json_value_clone(const lie_json_value *,
  const lie_json_value_description *, lie_json_value **);
lie_json_value_status lie_json_value_assign(lie_json_value *, const lie_json_value *);
/* Move copies into the destination domain transactionally, then retires the
 * source's string/child payloads while preserving its kind/scalars/key/identity.
 * move_assign requires disjoint trees/subtrees; ancestor relations refuse. */
lie_json_value_status lie_json_value_move_clone(lie_json_value *,
  const lie_json_value_description *, lie_json_value **);
lie_json_value_status lie_json_value_move_assign(lie_json_value *, lie_json_value *);
lie_json_value_status lie_json_value_set(lie_json_value *, lie_json_value_kind,
  bool, double, const char *, size_t);
lie_json_value_status lie_json_value_member(lie_json_value *, const char *, size_t,
                                           lie_json_value **);
lie_json_value_status lie_json_value_append_member(lie_json_value *, const char *,
  size_t, const lie_json_value *, lie_json_value **);
lie_json_value_status lie_json_value_append(lie_json_value *, const lie_json_value *,
                                           lie_json_value **);
lie_json_value_kind lie_json_value_type(const lie_json_value *);
bool lie_json_value_boolean(const lie_json_value *, bool);
double lie_json_value_number(const lie_json_value *, double);
size_t lie_json_value_size_number(const lie_json_value *, size_t);
const char *lie_json_value_string(const lie_json_value *, size_t *);
const char *lie_json_value_key(const lie_json_value *, size_t *);
size_t lie_json_value_size(const lie_json_value *);
size_t lie_json_value_array_size(const lie_json_value *);
size_t lie_json_value_object_size(const lie_json_value *);
const lie_json_value *lie_json_value_at(const lie_json_value *, bool, size_t);
const lie_json_value *lie_json_value_find(const lie_json_value *, const char *, size_t);
void *lie_json_value_view(const lie_json_value *);
uint64_t lie_json_value_revision(const lie_json_value *);
void lie_json_value_describe(const lie_json_value *, lie_json_value_info *);
/* Parse publishes only a complete tree. Any syntax/callback/allocation/limit
 * refusal retires all staging. Parser and persistent-tree budgets are separate.
 * Parser diagnostic errors retain their existing wording/offsets. */
lie_json_value_status lie_json_value_parse(const char *, size_t,
  const lie_json_value_description *, const lie_json_parse_description *,
  lie_json_value **, lie_json_parse_error *, lie_json_parse_info *);
/* Synchronous borrowed output spans; false stops with CALLBACK. Partial output
 * is staging and must be discarded on ANY refusal. Finite binary64 formatting
 * and byte escaping are locale-neutral. Output bound includes punctuation. */
lie_json_value_status lie_json_value_dump(const lie_json_value *,
                                         const lie_json_value_sink *);
#ifdef __cplusplus
}
#endif
#endif
