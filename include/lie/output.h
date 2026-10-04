/* SPDX-License-Identifier: MIT */
#ifndef LIE_OUTPUT_H
#define LIE_OUTPUT_H
#include "lie/events.h"
/* Model output grammar binding. The currently selected providers use Qwen's
 * function tags. Neutral policy/result contracts permit other model bindings.
 * Bounded complete-turn validation; these helpers do not sample or execute.
 * Strings are NUL-terminated, borrowed for parse. Initialize the result to
 * zero; clear it before reuse. Failed parsing leaves that empty result
 * unchanged. */
typedef struct {
  const lie_chat_tool *tools;
  size_t tool_count;
  lie_tool_choice choice;
  bool parallel;
  const char *named;
} lie_output_policy;
typedef struct {
  char *text;
  size_t bytes, count;
  lie_output_call calls[LIE_CHAT_MAX_CALLS];
} lie_output_turn;
bool lie_output_parse(const lie_output_policy *, const char *, size_t,
                      bool completed, const char *identity, lie_output_turn *,
                      char error[256]);
void lie_output_turn_clear(lie_output_turn *);
#endif
