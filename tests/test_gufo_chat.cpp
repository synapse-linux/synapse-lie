// SPDX-License-Identifier: MIT
// CPU formatter only. Uses the independently pinned native Qwen template;
// never opens weights, a HIP device, or a model-forward executor.
#include "gufo_chat.hpp"
extern "C" {
#include "lie/chat.h"
}
#include <cassert>
#include <cstring>
#include <iostream>
int main() {
    const char *body=R"JSON({"model":"m","tools":[{"type":"function","function":{"name":"edit","description":"Edit text","parameters":{"type":"object","properties":{"path":{"type":"string"},"edits":{"type":"array"}}}}}],"tool_choice":"required","messages":[{"role":"system","content":"A coding assistant."},{"role":"user","content":"Edit the file."},{"role":"assistant","content":null,"tool_calls":[{"id":"call-1","type":"function","function":{"name":"edit","arguments":"{\"path\":\"  x.txt \",\"edits\":[{\"oldText\":\" old \",\"newText\":\"new\\nline\"}]}"}}]},{"role":"tool","tool_call_id":"call-1","content":"Done."}]})JSON";
    lie_chat_request r{}; char error[256];
    assert(lie_chat_parse(body,std::strlen(body),"m",&r,error));
    lie_chat_template input{r.messages,r.details,r.count,r.tools,r.tool_count,1};
    auto chat=lie_gufo::translate_chat(input); assert(chat);
    assert(chat->messages[3].role==gufo::tokenization::ChatRole::kTool);
    assert(chat->messages[3].tool_call_id=="call-1");
    assert(chat->messages[2].tool_calls[0].arguments[0].value=="  x.txt ");
    gufo::tokenization::ChatTemplateOptions options;
    options.enable_thinking=false; options.require_tool_call=true;
    std::string why;
    auto rendered=gufo::tokenization::QwenChatTemplate::Render(chat->messages,chat->tools,options,&why);
    assert(rendered);
    assert(rendered->find("<tools>\n{\"type\": \"function\"")!=std::string::npos);
    assert(rendered->find("<tool_call>\n<function=edit>\n<parameter=path>\n  x.txt \n</parameter>\n<parameter=edits>\n[{\"oldText\":\" old \",\"newText\":\"new\\nline\"}]\n</parameter>\n</function>\n</tool_call>")!=std::string::npos);
    assert(rendered->find("<|im_start|>user\n<tool_response>\nDone.\n</tool_response><|im_end|>")!=std::string::npos);
    assert(rendered->find("You must call at least one available function")!=std::string::npos);
    assert(rendered->ends_with(gufo::tokenization::GenerationPrompt(false)));
    lie_chat_free(&r);
    // Text-only formatting remains byte-identical to the former direct path.
    lie_chat_message m[]={{LIE_CHAT_SYSTEM,"system",6},{LIE_CHAT_USER,"hello",5}};
    lie_chat_template plain{m,nullptr,2,nullptr,0,0};
    chat=lie_gufo::translate_chat(plain); assert(chat);
    options.require_tool_call=false;
    auto actual=gufo::tokenization::QwenChatTemplate::Render(chat->messages,chat->tools,options,&why);
    std::vector<gufo::tokenization::ChatMessage> old={{gufo::tokenization::ChatRole::kSystem,"system"},{gufo::tokenization::ChatRole::kUser,"hello"}};
    assert(actual==gufo::tokenization::QwenChatTemplate::Render(old,options,&why));
    plain.count=LIE_CHAT_MAX_MESSAGES+1; assert(!lie_gufo::translate_chat(plain));
    std::cout<<"Pinned Qwen template/tool mapping: PASS (CPU formatter, NOT inference)\n";
}
