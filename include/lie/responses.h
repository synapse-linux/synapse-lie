/* SPDX-License-Identifier: MIT */
#ifndef LIE_RESPONSES_H
#define LIE_RESPONSES_H
#include "lie/chat.h"
#include "lie/events.h"
#include "lie/worker.h"
#include <json-c/json.h>
/* Normalize a stateless text/function Responses request into the owned chat contract. */
bool lie_responses_parse(const char *,size_t,const char *,lie_chat_request *,char error[256]);
bool lie_responses_parse_history(const char *,size_t,const char *,const lie_core_request *,lie_chat_request *,char error[256]);
json_object *lie_chat_history_json(const lie_core_request *);
json_object *lie_response_input_items(const lie_core_request *,size_t skip);
json_object *lie_wire_page(json_object *items,const char *query,bool completions,char error[256]);
json_object *lie_response_object(const char *,const char *,int64_t,const char *,size_t,
                                 json_object *calls,const lie_job_info *);
char *lie_response_begin(const char *,const char *,int64_t,uint64_t *sequence,bool text_item);
char *lie_response_delta(const char *,const char *,size_t,uint64_t *sequence);
char *lie_response_since(char *owned,int64_t starting_after);
bool lie_response_retrieve_query(const char *,bool *stream,int64_t *starting_after);
char *lie_response_end(const char *,const char *,int64_t,const char *,size_t,
                       json_object *calls,const lie_job_info *,uint64_t *sequence,bool text_started);
char *lie_response_end_streamed(const char *,const char *,int64_t,const char *,size_t,
                       json_object *,const lie_job_info *,uint64_t *,bool,size_t started_calls);
char *lie_response_tool_event(const char *,const lie_output_call *,bool start,
                              size_t index,uint64_t *);
char *lie_response_text_event(const char *,const char *,size_t,uint64_t *,bool *started);
#endif
