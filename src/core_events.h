/* SPDX-License-Identifier: MIT */
#ifndef LIE_CORE_EVENTS_H
#define LIE_CORE_EVENTS_H
#include "lie/events.h"
typedef struct lie_event_stream lie_event_stream;
lie_event_stream *lie_event_stream_create(lie_job *, lie_flow *,
                                          const lie_core_request *, unsigned,
                                          const char *);
void lie_event_stream_destroy(lie_event_stream *);
bool lie_event_stream_done(const lie_event_stream *);
lie_flow_status lie_event_stream_next(lie_event_stream *, lie_event *);
lie_flow_status lie_event_stream_release(lie_event_stream *, lie_event_ticket);
/* Immutable executor witnesses remain separate from semantic output checks. */
void lie_job_semantic_result(lie_job *, unsigned, const char *);
bool lie_job_semantic_cancelled(lie_job *);
#endif
