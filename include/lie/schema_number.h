/* SPDX-License-Identifier: MIT */
#ifndef LIE_SCHEMA_NUMBER_H
#define LIE_SCHEMA_NUMBER_H
#include "lie/schema_transform.h"
#include "lie/grammar_number.h"
#include "lie/grammar_builder.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_SCHEMA_NUMBER_ABI 1u
#define LIE_SCHEMA_NUMBER_TEXT_CAPACITY 64u
typedef struct {
  uint32_t abi_version, struct_bytes;
  lie_schema_transform_description transform;
  size_t number_work;
  void *conversion_context;
  /* Optional binary64 codec overrides: locale-neutral JSON spelling/parsing,
   * no lookup, validation, interval/grid or representability policy. Serialize
   * writes at most capacity bytes, without a NUL; parse consumes the full span.
   * Neither callback retains a view. Refusals must not throw across the C ABI.
   * Each NULL hook independently selects the owned C17 binary64 codec; that
   * path ignores conversion_context, retains no state and allocates no heap.
   * Native codec refusal returns CALLBACK with a static English error message.
   * Custom hook statuses pass through unchanged; callers own their errors. */
  lie_schema_status (*serialize)(void *, double, char *, size_t, size_t *);
  lie_schema_status (*parse)(void *, lie_schema_bytes, double *);
} lie_schema_number_description;
void lie_schema_number_description_init(lie_schema_number_description *);
/* Synchronous borrowed-reader contract follows schema_transform. C17 owns
 * ordered keyword lookup, finite/positive checks, exact-decimal preparation,
 * scalar type selection, LCM representability and literal publication. The
 * initialized description selects the owned binary64 codec without callbacks;
 * clients can override either conversion independently. Native parse uses the
 * bounded default lie_binary64 limits and consumes the complete span.
 * number_work=0 selects grammar_number's default. Its paired allocator owns
 * policies/workspaces and must outlive a created policy. No shared mutable
 * cache, model, HTTP, RNG or thread ownership. Refusals preserve outputs; a
 * nonnumeric value is an ordinary successful false result for accept. Builder
 * mutations on refusal require retiring that private builder, as in its ABI.
 * Output/error storage must be disjoint from borrowed nodes/callback state. */
lie_schema_status lie_schema_number_create(const lie_schema_number_description *,
  lie_schema_node schema, bool integer, lie_number_policy **, lie_schema_error *);
lie_schema_status lie_schema_number_accept(const lie_schema_number_description *,
  const lie_number_policy *, lie_schema_node value, bool *, lie_schema_error *);
lie_schema_status lie_schema_number_intersect(const lie_schema_number_description *,
  lie_schema_node left, lie_schema_node right, double *, lie_schema_error *);
lie_schema_status lie_schema_number_literal(const lie_schema_number_description *,
  lie_schema_node value, lie_grammar_builder *, uint32_t *, lie_schema_error *);
#ifdef __cplusplus
}
#endif
#endif
