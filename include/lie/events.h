/* SPDX-License-Identifier: MIT */
#ifndef LIE_EVENTS_H
#define LIE_EVENTS_H
#include "lie/core.h"
#define LIE_EVENT_ABI 1u
typedef enum {
  LIE_EVENT_PROGRESS,
  LIE_EVENT_TEXT,
  LIE_EVENT_TOOL_CALL,
  LIE_EVENT_TURN_END
} lie_event_kind;
typedef enum {
  LIE_TURN_STOP,
  LIE_TURN_LENGTH,
  LIE_TURN_TOOL_CALLS,
  LIE_TURN_CANCELLED,
  LIE_TURN_ERROR
} lie_turn_reason;
typedef struct {
  const lie_job *owner;
  uint64_t generation;
} lie_event_ticket;
typedef struct {
  const char *id, *name, *arguments_json;
  size_t arguments_bytes, index;
} lie_output_call;
typedef struct {
  uint32_t abi_version, struct_bytes;
  lie_event_kind kind;
  lie_event_ticket ticket;
  uint64_t tokens, token_offset; /* Confirmed output, never draft tokens. */
  const char *text;
  size_t bytes;
  const lie_output_call *call;
  lie_flow_end end;       /* ACTIVE except TURN_END. */
  lie_turn_reason reason; /* TURN_END only. */
  lie_job_info info;      /* Final semantic status on TURN_END. */
} lie_event;
/* Exactly one consumer. Choose semantic events OR the legacy raw flow for a
 * job; mixing them is refused. No HTTP/JSON-library/provider types here.
 * TEXT is incremental valid UTF-8. A tool-enabled turn emits credit-bearing
 * PROGRESS while buffering, then TEXT and validated whole TOOL_CALL events.
 * All calls validate before any call is exposed. No tool is executed here.
 * Every nonterminal event is borrowed until release, even with zero tokens.
 * Release before requesting more credits or releasing the job. TURN_END has
 * no loan and is observed once, after outstanding device work has retired.
 * Poll readiness, drain, then next until WOULD_BLOCK; pending semantic events
 * remain readable. Initial credit is eight confirmed tokens, as for raw flow.
 */
int lie_job_event_fd(lie_job *);
lie_flow_status lie_job_event_drain(lie_job *);
lie_flow_status lie_job_event_request(lie_job *, uint64_t tokens);
lie_flow_status lie_job_event_next(lie_job *, lie_event *);
lie_flow_status lie_job_event_release(lie_job *, lie_event_ticket);
#endif
