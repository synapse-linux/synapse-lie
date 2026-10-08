/* SPDX-License-Identifier: MIT */
#include "lie/chat_history.h"
#include <string.h>

bool lie_chat_tool_result_order(const lie_chat_template *input,
                                size_t *order, size_t capacity) {
    if (!input || !input->messages || !input->count ||
        input->count > LIE_CHAT_MAX_MESSAGES || !order || capacity < input->count)
        return false;
    size_t view[LIE_CHAT_MAX_MESSAGES];
    const char *seen[LIE_CHAT_MAX_MESSAGES];
    size_t seen_count = 0, pending = 0, result_start = 0;
    const lie_tool_call *calls = NULL;
    size_t call_count = 0;
    bool returned[LIE_CHAT_MAX_CALLS] = {false};
    for (size_t i = 0; i < input->count; ++i)
        view[i] = i;
    for (size_t i = 0; i < input->count; ++i) {
        const lie_chat_message *message = &input->messages[i];
        lie_chat_details detail = input->details ? input->details[i] : (lie_chat_details){0};
        if (message->role < LIE_CHAT_SYSTEM || message->role > LIE_CHAT_TOOL ||
            detail.call_count > LIE_CHAT_MAX_CALLS ||
            (detail.call_count && (!detail.calls || message->role != LIE_CHAT_ASSISTANT)))
            return false;
        if (message->role == LIE_CHAT_TOOL) {
            if (!pending || !detail.tool_call_id || !*detail.tool_call_id)
                return false;
            size_t k = 0;
            while (k < call_count && strcmp(calls[k].id, detail.tool_call_id))
                ++k;
            if (k == call_count || returned[k] ||
                (detail.name && strcmp(detail.name, calls[k].name)))
                return false;
            returned[k] = true;
            view[result_start + k] = i;
            --pending;
            continue;
        }
        if (pending || detail.tool_call_id)
            return false;
        if (!detail.call_count)
            continue;
        calls = detail.calls;
        call_count = pending = detail.call_count;
        result_start = i + 1;
        if (pending > input->count - result_start)
            return false;
        memset(returned, 0, sizeof(returned));
        for (size_t k = 0; k < call_count; ++k) {
            const lie_tool_call *call = &calls[k];
            if (!call->id || !*call->id || !call->name || !*call->name ||
                seen_count == LIE_CHAT_MAX_MESSAGES)
                return false;
            for (size_t s = 0; s < seen_count; ++s)
                if (!strcmp(seen[s], call->id))
                    return false;
            seen[seen_count++] = call->id;
        }
    }
    if (pending)
        return false;
    memcpy(order, view, input->count * sizeof(*order));
    return true;
}
