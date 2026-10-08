/* SPDX-License-Identifier: MIT */
#ifndef LIE_SCHEMA_TRANSFORM_H
#define LIE_SCHEMA_TRANSFORM_H
#include "lie/grammar.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_SCHEMA_TRANSFORM_ABI 1u
typedef const void *lie_schema_node;
typedef struct { const char *data; size_t size; } lie_schema_bytes;
typedef enum { LIE_SCHEMA_NULL, LIE_SCHEMA_BOOL, LIE_SCHEMA_NUMBER,
  LIE_SCHEMA_STRING, LIE_SCHEMA_ARRAY, LIE_SCHEMA_OBJECT } lie_schema_kind;
typedef struct {
  lie_schema_kind kind;
  size_t count;
  double number;
  bool boolean;
  lie_schema_bytes text;
} lie_schema_value;
typedef enum { LIE_SCHEMA_OK, LIE_SCHEMA_INVALID, LIE_SCHEMA_EMPTY,
  LIE_SCHEMA_RESOURCE, LIE_SCHEMA_WORK_LIMIT, LIE_SCHEMA_CALLBACK } lie_schema_status;
/* Error spans borrow the input tree; static message + detail + suffix form the
 * deterministic English diagnostic. Error output is meaningful on refusal. */
typedef struct {
  const char *message;
  lie_schema_bytes detail;
  const char *suffix;
} lie_schema_error;
typedef struct {
  void *context;
  lie_schema_status (*describe)(void *, lie_schema_node, lie_schema_value *);
  lie_schema_status (*child)(void *, lie_schema_node, size_t,
                            lie_schema_bytes *, lie_schema_node *);
  lie_schema_status (*clone)(void *, lie_schema_node, lie_schema_node *);
  lie_schema_status (*create)(void *, const lie_schema_value *, lie_schema_node *);
  lie_schema_status (*put)(void *, lie_schema_node, lie_schema_bytes, lie_schema_node);
  lie_schema_status (*append)(void *, lie_schema_node, lie_schema_node);
  /* Declared format/numeric leaves, separate from tree traversal/merging.
   * The current numeric adapter routes policy through schema_number C17;
   * binary64 conversion and format expansion remain private hooks. */
  lie_schema_status (*format)(void *, lie_schema_bytes, lie_schema_node *);
  lie_schema_status (*multiple)(void *, lie_schema_node, lie_schema_node, lie_schema_node *);
} lie_schema_access;
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t max_work, max_pairs;
  lie_grammar_allocator allocator;
  lie_schema_access access;
} lie_schema_transform_description;
void lie_schema_transform_description_init(lie_schema_transform_description *);
/* Synchronous, caller-serialized borrowed-node contract. Read hooks return
 * stable views for the complete call. Writer hooks publish stable private
 * nodes in a caller-owned staging arena, never mutate input nodes, and copy
 * every supplied span. Refused calls preserve the result argument; retire all
 * staging nodes after success or refusal. Object keys are unique; their order
 * is retained. Output/error storage must be disjoint from borrowed nodes and
 * callback state. No hook retains scratch/input views.
 * No model, HTTP, thread, RNG or cache ownership. Paired allocators outlive the
 * call. Default limits: 64M counted work units and 262144 equality pairs.
 * Work is a refusal budget, not a timing/performance measurement. */
lie_schema_status lie_schema_equal(const lie_schema_transform_description *,
  lie_schema_node, lie_schema_node, bool *, lie_schema_error *);
lie_schema_status lie_schema_reference(const lie_schema_transform_description *,
  lie_schema_node root, lie_schema_node reference, lie_schema_node *, lie_schema_error *);
lie_schema_status lie_schema_keys(const lie_schema_transform_description *,
  lie_schema_node, lie_schema_error *);
lie_schema_status lie_schema_conjoin(const lie_schema_transform_description *,
  lie_schema_node root, lie_schema_node left, lie_schema_node right,
  unsigned depth, lie_schema_node *, lie_schema_error *);
#ifdef __cplusplus
}
#endif
#endif
