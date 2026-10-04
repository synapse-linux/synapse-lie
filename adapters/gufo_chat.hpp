// SPDX-License-Identifier: MIT
#ifndef LIE_GUFO_CHAT_HPP
#define LIE_GUFO_CHAT_HPP
#include "lie/executor.h"
#include "src/models/qwen/chat_template.hpp"
#include <cstring>
#include <optional>
#include <string>
#include <vector>
namespace lie_gufo {
struct Chat {
    std::vector<gufo::tokenization::ChatMessage> messages;
    std::vector<gufo::tokenization::ChatTool> tools;
};
// Pure translation of LIE-owned data. No HTTP parsing, scheduling or model work.
inline std::optional<Chat> translate_chat(const lie_chat_template &input) {
    using namespace gufo::tokenization;
    if (!input.messages || !input.count || input.count>LIE_CHAT_MAX_MESSAGES ||
        input.tool_count>LIE_CHAT_MAX_TOOLS || (input.tool_count && !input.tools) ||
        input.require_tool_call>1 || (input.require_tool_call && !input.tool_count)) return std::nullopt;
    constexpr size_t bound=4*LIE_CHAT_BODY_BYTES;
    size_t total=0;
    auto string_ok=[&](const char *s) {
        if (!s) return false;
        size_t n=strnlen(s,bound+1);
        if (n>bound-total) return false;
        total+=n; return true;
    };
    Chat out;
    for (size_t i=0;i<input.count;++i) {
        const auto &msg=input.messages[i];
        if (!msg.content || msg.bytes>bound-total || msg.role<LIE_CHAT_SYSTEM || msg.role>LIE_CHAT_TOOL) return std::nullopt;
        total+=msg.bytes;
        ChatRole role=msg.role==LIE_CHAT_SYSTEM?ChatRole::kSystem:msg.role==LIE_CHAT_USER?ChatRole::kUser:
                      msg.role==LIE_CHAT_TOOL?ChatRole::kTool:ChatRole::kAssistant;
        ChatMessage m(role,std::string(msg.content,msg.bytes));
        if (input.details) {
            const auto &d=input.details[i];
            if (d.call_count>LIE_CHAT_MAX_CALLS || (d.call_count && (!d.calls || msg.role!=LIE_CHAT_ASSISTANT))) return std::nullopt;
            if (d.name) { if (!string_ok(d.name)) return std::nullopt; m.name=d.name; }
            if (d.tool_call_id) { if (!string_ok(d.tool_call_id)) return std::nullopt; m.tool_call_id=d.tool_call_id; }
            for (size_t k=0;k<d.call_count;++k) {
                const auto &call=d.calls[k];
                if (!string_ok(call.id) || !string_ok(call.name) || call.argument_count>LIE_CHAT_MAX_ARGUMENTS ||
                    (call.argument_count && !call.arguments)) return std::nullopt;
                ChatMessage::ToolCall c; c.id=call.id; c.name=call.name;
                for (size_t j=0;j<call.argument_count;++j) {
                    const auto &a=call.arguments[j];
                    if (!string_ok(a.name) || !string_ok(a.value) || a.is_string>1) return std::nullopt;
                    c.arguments.push_back({a.name,a.value,a.is_string!=0});
                }
                m.tool_calls.push_back(std::move(c));
            }
        }
        if (msg.role==LIE_CHAT_TOOL && m.tool_call_id.empty()) return std::nullopt;
        out.messages.push_back(std::move(m));
    }
    for (size_t i=0;i<input.tool_count;++i) {
        const auto &t=input.tools[i];
        if (!string_ok(t.name) || !string_ok(t.description) || !string_ok(t.parameters_json) || !string_ok(t.definition_json)) return std::nullopt;
        out.tools.push_back({t.name,t.description,t.parameters_json,t.definition_json});
    }
    return out;
}
}
#endif
