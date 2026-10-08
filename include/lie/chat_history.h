/* SPDX-License-Identifier: MIT */
#ifndef LIE_CHAT_HISTORY_H
#define LIE_CHAT_HISTORY_H
#include "lie/executor.h"
#include <stdbool.h>
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Build a rendering view for templates that correlate results by call order.
 * Only complete, contiguous tool-result groups are reordered. All other
 * messages retain their positions. Input storage and result contents remain
 * caller-owned and untouched; IDs are borrowed NUL-terminated strings.
 * No JSON, model, transport, allocation, thread or GPU operation is involved.
 * The output buffer must not overlap input storage. On invalid history or
 * insufficient capacity, order remains untouched. */
bool lie_chat_tool_result_order(const lie_chat_template *input,
                                size_t *order, size_t capacity);
#ifdef __cplusplus
}
#endif
#endif
