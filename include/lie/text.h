/* SPDX-License-Identifier: MIT */
#ifndef LIE_TEXT_H
#define LIE_TEXT_H
#include <stdbool.h>
#include <stddef.h>
bool lie_utf8_valid(const char *, size_t, bool allow_nul);
typedef struct { unsigned char pending[4]; unsigned used, wanted; } lie_utf8_decoder;
bool lie_utf8_feed(lie_utf8_decoder *, const char *, size_t, bool final,
                   char *out, size_t capacity, size_t *written);
#endif
