/* SPDX-License-Identifier: MIT */
#ifndef LIE_CHAT_H
#define LIE_CHAT_H
#include "lie/core.h"
#include "lie/text.h"
#include <stdbool.h>
#include <stddef.h>
#define LIE_CHAT_MAX_OUTPUT LIE_CORE_MAX_OUTPUT
#define LIE_CHAT_TOKEN_BYTES LIE_CORE_TOKEN_BYTES
struct json_object;
/* Protocol-owned parsing storage. Structured strings borrow this JSON tree.
 * Admission copies normalized C data into the core before freeing this tree. */
typedef struct {
    lie_chat_message messages[LIE_CHAT_MAX_MESSAGES];
    lie_chat_details details[LIE_CHAT_MAX_MESSAGES];
    lie_chat_tool tools[LIE_CHAT_MAX_TOOLS];
    size_t count, tool_count;
    lie_image_input images[LIE_VISION_MAX_IMAGES];
    size_t image_count;
    unsigned max_tokens;
    lie_generation_options generation;
    bool stream, include_usage, parallel_tools;
    lie_tool_choice tool_choice;
    const char *named_tool;
    struct json_object *json_owner;
} lie_chat_request;
bool lie_chat_parse(const char *body, size_t bytes, const char *model_id,
                    lie_chat_request *, char error[256]);
void lie_chat_free(lie_chat_request *);
#endif
