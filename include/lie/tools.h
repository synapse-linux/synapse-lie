/* SPDX-License-Identifier: MIT */
#ifndef LIE_TOOLS_H
#define LIE_TOOLS_H
#include "lie/chat.h"
#include "lie/events.h"
#include <json-c/json.h>
/* JSON/text only. No tool code or process is ever executed by the server. */
bool lie_tool_name(const char *);
bool lie_json_text(json_object *);
bool lie_json_literal(json_object *, const char *);
json_object *lie_json_parse(const char *, size_t, bool *valid);
bool lie_chat_tools_parse(json_object *, lie_chat_request *, const char **error);
bool lie_chat_messages_parse(json_object *, lie_chat_request *, const char **error);
/* Independent UI-owned schema copy, because json-c reference counts are not a
 * cross-thread lifetime protocol. Destroy on the UI thread after transport use. */
typedef struct {
    json_object *tools;
    lie_tool_choice choice;
    bool parallel;
    char named[129];
} lie_tool_policy;
bool lie_tool_policy_copy(const lie_chat_request *, lie_tool_policy *);
void lie_tool_policy_free(lie_tool_policy *);
/* Full-turn validation before publishing executable deltas. Successful message
 * is owned by caller. Incomplete/malformed calls never become text or success. */
bool lie_tool_reply(const lie_tool_policy *, const char *text, size_t bytes,
                    bool completed, const char *request_id, json_object **message,
                    char error[256]);
/* Projection of an already validated shared-core call; no output parsing. */
json_object *lie_output_call_json(const lie_output_call *);
#endif
