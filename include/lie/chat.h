/* SPDX-License-Identifier: MIT */
#ifndef LIE_CHAT_H
#define LIE_CHAT_H
#include "lie/executor.h"
#include <stdbool.h>
#include <stddef.h>
#define LIE_CHAT_MAX_MESSAGES 32
#define LIE_CHAT_MAX_OUTPUT 512
#define LIE_CHAT_TOKEN_BYTES 256
/* Parsed messages own their copies. Strict text-only, greedy, thinking-off T0. */
typedef struct {
    lie_chat_message messages[LIE_CHAT_MAX_MESSAGES];
    size_t count;
    unsigned max_tokens;
    bool stream, include_usage;
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
