/* SPDX-License-Identifier: MIT */
#ifndef LIE_SCHEMA_FORMAT_H
#define LIE_SCHEMA_FORMAT_H
#include "lie/schema_transform.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_SCHEMA_FORMAT_ABI 1u
#define LIE_SCHEMA_FORMAT_PATTERN_CAPACITY 8192u
/* Locale-neutral pinned format expansion. Supported names are date, time,
 * date-time, uuid, ipv4, ipv6, hostname, email and duration. Format constraints
 * retain their existing decoded-string grammar semantics. Patterns are copied
 * without NUL. Fixed bounded construction owns stack scratch, no heap/thread,
 * model, HTTP, RNG or cache. Output spans/length/error must be disjoint from
 * input and each other. Refusal preserves output bytes and length. */
lie_schema_status lie_schema_format_pattern(lie_schema_bytes,
  char *, size_t capacity, size_t *, lie_schema_error *);
/* Expand into fresh private staging nodes using the transform writer contract.
 * Hostname includes maxLength253. Writers copy every supplied span; no input
 * is mutated. Refused calls preserve *output and require staging retirement.
 * Transform ABI/budgets/allocator rules apply. No returned scratch view. */
lie_schema_status lie_schema_format_expand(const lie_schema_transform_description *,
  lie_schema_bytes, lie_schema_node *, lie_schema_error *);
#ifdef __cplusplus
}
#endif
#endif
