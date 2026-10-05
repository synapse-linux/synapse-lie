/* SPDX-License-Identifier: MIT */
#ifndef LIE_SCHEMA_VISIT_H
#define LIE_SCHEMA_VISIT_H
#include "lie/grammar_builder.h"
#include "lie/schema_memo.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_SCHEMA_VISIT_ABI 1u
typedef struct {
  uint32_t abi_version, struct_bytes;
  void *context;
  lie_schema_status (*body)(void *, lie_schema_node, size_t, uint32_t *,
                            lie_schema_error *);
} lie_schema_body_access;
void lie_schema_body_access_init(lie_schema_body_access *);
/* Caller-owned per-compilation memo/builder pair. Look up identity first;
 * on a miss reserve a rule and publish its placeholder before invoking body.
 * Success binds the returned body symbol. EMPTY binds an empty rule and still
 * returns its ID, preserving productive/cycle analysis at finalization.
 * Body writes a symbol compatible with this builder and its declared lexeme
 * table; it is synchronous/nonthrowing and may visit children with this same
 * pair. Stable immutable node identities outlive the entire compilation.
 * Callback owns child recursion, schema depth and body-specific work policy.
 * Its optional error destination is cleared before invocation; borrowed
 * diagnostic text must outlive this call. Non-EMPTY refusals propagate it.
 * The C sequence owns no HTTP/model/thread/RNG or persisted state.
 * Calls are serialized. Outputs/error/callback state are disjoint from memo/
 * builder internals. Refusal preserves result; earlier placeholders and child
 * mutations can remain, so retire the whole compilation pair after refusal.
 * Do not reuse an incomplete pair or destruct it while callbacks are active. */
lie_schema_status lie_schema_visit_rule(lie_schema_memo *, lie_grammar_builder *,
    lie_schema_node, size_t depth, lie_schema_body_access, uint32_t *,
    lie_schema_error *);
#ifdef __cplusplus
}
#endif
#endif
