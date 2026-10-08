/* SPDX-License-Identifier: MIT */
#ifndef LIE_SCHEMA_ROOT_H
#define LIE_SCHEMA_ROOT_H
#include "lie/schema_visit.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_SCHEMA_ROOT_ABI 1u
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t max_references;
  lie_schema_transform_description reader;
  lie_schema_body_access visit;
} lie_schema_root_description;
void lie_schema_root_description_init(lie_schema_root_description *);
/* Synchronous root admission and construction, independent of model/HTTP.
 * Schema mode follows local root references, detects repeated node identities,
 * then requires the resolved root to have string type "object" and no anyOf.
 * Visit receives the ORIGINAL schema at depth zero (including ref siblings).
 * Object-only mode skips all reader/visitor calls and constructs the existing
 * generic JSON object at depth16. It permits a NULL schema. Both modes compose
 * whitespace/body/whitespace in this caller-owned C builder.
 * Object-only mode requires initialized builder JSON primitives and their
 * whitespace rule. Schema mode uses caller-supplied valid builder symbols.
 * Builder finalization and predicates have separate contracts.
 * Root reader work is shared across the whole chain, not reset per reference.
 * Default/maximum: 262144 reference identities; default reader work64M. A lazy C identity
 * memo uses the reader's paired allocator; every allocation retires before
 * Visit or return. Stable immutable nodes/spans and allocator/callback contexts
 * outlive the call. Visitor is synchronous/nonthrowing; it may compile children
 * using its own memo/body state, never retain scratch or reenter this call.
 * Operations are caller-serialized; outputs/error are disjoint from input and
 * callback state. Refusal preserves the result; earlier visitor/builder changes
 * may remain, so retire the failed compilation instead of reusing it. No worker,
 * RNG, shared cache, persisted state, thread or device ownership is introduced.
 * Error spans borrow input; diagnostic text must outlive this call. */
lie_schema_status lie_schema_root_rule(const lie_schema_root_description *,
    lie_schema_node schema, bool object_only, lie_grammar_builder *,
    uint32_t whitespace, uint32_t *out, lie_schema_error *);
#ifdef __cplusplus
}
#endif
#endif
