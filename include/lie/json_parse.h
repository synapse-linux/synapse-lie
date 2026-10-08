/* SPDX-License-Identifier: MIT */
#ifndef LIE_JSON_PARSE_H
#define LIE_JSON_PARSE_H
#include "lie/grammar.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_JSON_PARSE_ABI 1u
#define LIE_JSON_PARSE_MAX_DEPTH 128u
typedef enum {
  LIE_JSON_PARSE_OK, LIE_JSON_PARSE_INVALID, LIE_JSON_PARSE_SYNTAX,
  LIE_JSON_PARSE_RESOURCE, LIE_JSON_PARSE_LIMIT, LIE_JSON_PARSE_CALLBACK
} lie_json_parse_status;
typedef enum {
  LIE_JSON_BEGIN_OBJECT, LIE_JSON_END_OBJECT, LIE_JSON_BEGIN_ARRAY,
  LIE_JSON_END_ARRAY, LIE_JSON_KEY, LIE_JSON_STRING, LIE_JSON_NUMBER,
  LIE_JSON_BOOL, LIE_JSON_NULL
} lie_json_event_kind;
typedef struct {
  lie_json_event_kind kind;
  const char *text;
  size_t text_bytes;
  double number;
  bool boolean;
} lie_json_event;
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t max_input_bytes, max_owned_bytes, max_work;
  unsigned max_depth;
  lie_grammar_allocator allocator;
} lie_json_parse_description;
typedef struct { const char *message; size_t offset; } lie_json_parse_error;
typedef struct {
  size_t input_consumed, events, work, allocations, peak_owned_bytes;
} lie_json_parse_info;
typedef struct {
  void *context;
  /* No exception crosses this boundary. False terminates with CALLBACK. */
  bool (*emit)(void *, const lie_json_event *);
} lie_json_sink;
void lie_json_parse_description_init(lie_json_parse_description *);
/* Complete single-root JSON: ordered events, finite binary64 numbers,
 * strict UTF8/control/escape/surrogate handling and decoded duplicate-key
 * refusal before a duplicate's value. C17 owns iterative syntax, decoding
 * and per-object key tables; sink owns typed tree construction.
 * Input is borrowed for this synchronous call. Copy every event span before
 * returning from emit: decoder storage may be reused by the next event.
 * On ANY refusal discard all sink staging: partial events are not a result.
 * Error/info are diagnostic and may change on refusal; all arguments/output
 * storage are disjoint from input and allocator/sink state. Null diagnostics
 * are permitted. Allocator hooks are paired and outlive the call. Every owned
 * allocation retires before return, including callback/allocator refusal.
 * Defaults:128 levels,64MiB input/owned payload,268435456 lexical/key work units.
 * Number conversion uses the independent bounded binary64 codec. Info charges
 * requested C heap bytes (including growth overlap), not stack, allocator
 * overhead, sink/private typed containers, device memory or process cost.
 * No model, HTTP, cache, RNG, thread or global mutable state. */
lie_json_parse_status lie_json_parse_events(const char *, size_t,
  const lie_json_parse_description *, const lie_json_sink *,
  lie_json_parse_error *, lie_json_parse_info *);
#ifdef __cplusplus
}
#endif
#endif
