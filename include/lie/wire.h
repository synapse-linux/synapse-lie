/* SPDX-License-Identifier: MIT */
#ifndef LIE_WIRE_H
#define LIE_WIRE_H
#include "lie/worker.h"
#include "lie/events.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
struct json_object;
struct json_object *lie_wire_logprobs(lie_job *,size_t offset,size_t count);
char *lie_wire_reindex(char *owned,unsigned index,bool keep_done);
/* Validated assistant message. Streaming start/argument fragments are
 * provisional; completion requires full-turn validation. */
char *lie_wire_message(const char *id, const char *model, int64_t created,
                       struct json_object *message, const lie_job_info *, bool stream, bool usage);
/* Returned strings are owned. Content is a length-delimited valid UTF-8 span. */
char *lie_wire_completion(const char *id, const char *model, int64_t created,
                          const char *content, size_t bytes, const lie_job_info *);
char *lie_wire_chunk(const char *id, const char *model, int64_t created,
                     const char *content, size_t bytes, bool role);
char *lie_wire_end(const char *id, const char *model, int64_t created,
                   const lie_job_info *, bool usage);
char *lie_wire_tool_event(const char *,const char *,int64_t,
                          const lie_output_call *,bool start);
#endif
