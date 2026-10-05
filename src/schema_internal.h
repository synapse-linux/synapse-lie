/* SPDX-License-Identifier: MIT */
/* Private C17 construction helpers, not a public or persisted ABI. */
#ifndef LIE_SCHEMA_INTERNAL_H
#define LIE_SCHEMA_INTERNAL_H
#include "lie/schema_transform.h"
typedef struct {
  const lie_schema_transform_description *d;
  size_t work;
  lie_schema_error *error;
} lie_schema_context;
bool lie_schema_internal_valid(const lie_schema_transform_description *);
lie_schema_status lie_schema_internal_tick(lie_schema_context *, size_t);
lie_schema_status lie_schema_internal_fail(lie_schema_context *,
                                           lie_schema_status, const char *);
void *lie_schema_internal_allocate(lie_schema_context *, size_t);
void lie_schema_internal_release(lie_schema_context *, void *);
lie_schema_status lie_schema_internal_describe(lie_schema_context *,
                                               lie_schema_node,
                                               lie_schema_value *);
lie_schema_status lie_schema_internal_child(lie_schema_context *,
                                            lie_schema_node, size_t,
                                            lie_schema_bytes *,
                                            lie_schema_node *);
lie_schema_status lie_schema_internal_find(lie_schema_context *,
                                           lie_schema_node, lie_schema_bytes,
                                           lie_schema_node *);
lie_schema_status lie_schema_internal_field(lie_schema_context *,
                                            lie_schema_node, const char *,
                                            lie_schema_node *);
lie_schema_status lie_schema_internal_equal(lie_schema_context *,
                                            lie_schema_node, lie_schema_node,
                                            bool *);
lie_schema_status lie_schema_internal_reference(lie_schema_context *,
                                                lie_schema_node,
                                                lie_schema_node,
                                                lie_schema_node *);
lie_schema_status lie_schema_internal_clone(lie_schema_context *,
                                            lie_schema_node, lie_schema_node *);
lie_schema_status lie_schema_internal_create(lie_schema_context *,
                                             lie_schema_value,
                                             lie_schema_node *);
lie_schema_status lie_schema_internal_put(lie_schema_context *, lie_schema_node,
                                          lie_schema_bytes, lie_schema_node);
lie_schema_status lie_schema_internal_append(lie_schema_context *,
                                             lie_schema_node, lie_schema_node);
#endif
