/* SPDX-License-Identifier: MIT */
#ifndef LIE_RESPONSES_H
#define LIE_RESPONSES_H
#include "lie/chat.h"
#include "lie/worker.h"
#include <json-c/json.h>
/* Normalize a stateless text/function Responses request into the owned chat contract. */
bool lie_responses_parse(const char *,size_t,const char *,lie_chat_request *,char error[256]);
json_object *lie_response_object(const char *,const char *,int64_t,const char *,size_t,
                                 json_object *calls,const lie_job_info *);
char *lie_response_begin(const char *,const char *,int64_t,uint64_t *sequence,bool text_item);
char *lie_response_delta(const char *,const char *,size_t,uint64_t *sequence);
char *lie_response_end(const char *,const char *,int64_t,const char *,size_t,
                       json_object *calls,const lie_job_info *,uint64_t *sequence,bool text_started);
#endif
