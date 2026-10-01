/* SPDX-License-Identifier: MIT */
#ifndef LIE_CHAT_H
#define LIE_CHAT_H
#include "lie/executor.h"
#include <stdbool.h>
#include <stddef.h>
#define LIE_CHAT_MAX_OUTPUT 4096u
#define LIE_CHAT_TOKEN_BYTES 256u
struct json_object;
typedef enum { LIE_TOOLS_AUTO, LIE_TOOLS_NONE, LIE_TOOLS_REQUIRED, LIE_TOOLS_NAMED } lie_tool_choice;
/* Parsed messages own their content. Structured strings borrow the owned JSON
 * tree; it moves with the request to the single worker, never shared with UI. */
typedef struct {
    lie_chat_message messages[LIE_CHAT_MAX_MESSAGES];
    lie_chat_details details[LIE_CHAT_MAX_MESSAGES];
    lie_chat_tool tools[LIE_CHAT_MAX_TOOLS];
    size_t count, tool_count;
    unsigned max_tokens;
    bool stream, include_usage, parallel_tools;
    lie_tool_choice tool_choice;
    const char *named_tool;
    struct json_object *json_owner;
} lie_chat_request;
bool lie_chat_parse(const char *body, size_t bytes, const char *model_id,
                    lie_chat_request *, char error[256]);
void lie_chat_free(lie_chat_request *);
bool lie_utf8_valid(const char *, size_t, bool allow_nul);
/* Streaming replacement decoding, independent of token/write boundaries. */
typedef struct { unsigned char pending[4]; unsigned used, wanted; } lie_utf8_decoder;
bool lie_utf8_feed(lie_utf8_decoder *, const char *, size_t, bool final,
                   char *out, size_t capacity, size_t *written);
#endif
