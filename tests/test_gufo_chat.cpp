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
    assert(lie_gufo::order_tool_results(*chat,input));
    assert(lie_gufo::guide_constrained_tools(*chat));
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
    assert(lie_gufo::order_tool_results(*chat,plain));
    assert(lie_gufo::guide_constrained_tools(*chat));
    options.require_tool_call=false;
    auto actual=gufo::tokenization::QwenChatTemplate::Render(chat->messages,chat->tools,options,&why);
    std::vector<gufo::tokenization::ChatMessage> old={{gufo::tokenization::ChatRole::kSystem,"system"},{gufo::tokenization::ChatRole::kUser,"hello"}};
    assert(actual==gufo::tokenization::QwenChatTemplate::Render(old,options,&why));
    plain.count=LIE_CHAT_MAX_MESSAGES+1; assert(!lie_gufo::translate_chat(plain));
    // A strict request must guide the same JSON syntax that its sampler accepts.
    // No question, call count, function choice or expected answer is inserted.
    const char *strict_body=R"JSON({"model":"m","tools":[{"type":"function","function":{"name":"get_value","strict":true,"parameters":{"type":"object","properties":{"key":{"type":"string","enum":["alpha","beta"]}},"required":["key"],"additionalProperties":false}}}],"messages":[{"role":"user","content":"Call both functions."}]})JSON";
    assert(lie_chat_parse(strict_body,std::strlen(strict_body),"m",&r,error));
    input={r.messages,r.details,r.count,r.tools,r.tool_count,0};
    chat=lie_gufo::translate_chat(input); assert(chat && chat->messages.size()==1);
    const auto image=std::make_shared<const std::vector<uint8_t>>(std::initializer_list<uint8_t>{1,2,3});
    chat->messages[0].images.push_back({4,image}); // Formatter fixture, no image decoding.
    assert(lie_gufo::guide_constrained_tools(*chat));
    assert(chat->messages.size()==2 && chat->messages[0].role==gufo::tokenization::ChatRole::kSystem);
    assert(chat->messages[1].content=="Call both functions.");
    assert(chat->messages[1].images.size()==1 && chat->messages[1].images[0].bytes==image && chat->messages[1].images[0].offset==4);
    const std::string instruction=chat->messages[0].content;
    assert(instruction.find("<tool_call>{\"name\":\"function_name\",\"arguments\":{...}}</tool_call>")!=std::string::npos);
    assert(instruction.find("alpha")==std::string::npos && instruction.find("beta")==std::string::npos && instruction.find("get_value")==std::string::npos);
    chat->messages[1].images.clear();
    rendered=gufo::tokenization::QwenChatTemplate::Render(chat->messages,chat->tools,options,&why); assert(rendered);
    assert(rendered->find(instruction)>rendered->find("<IMPORTANT>"));
    assert(!std::strcmp(r.messages[0].content,"Call both functions.") && r.count==1);
    // Existing system text and history stay owned and ordered; mixed strict/
    // non-strict tools use one grammar, so any strict definition selects guidance.
    chat=lie_gufo::translate_chat(input); assert(chat);
    chat->messages.insert(chat->messages.begin(), {gufo::tokenization::ChatRole::kSystem,"Keep existing policy."});
    chat->tools.push_back({"other","strict-looking text", "{}", "{\"function\":{\"strict\":false}}"});
    assert(lie_gufo::guide_constrained_tools(*chat));
    assert(chat->messages.size()==2 && chat->messages[0].content=="Keep existing policy.\n\n"+instruction);
    chat=lie_gufo::translate_chat(input); assert(chat);
    chat->tools[0].definition_json="{\"function\":{\"strict\":false,\"description\":\"strict:true\"}}";
    assert(lie_gufo::guide_constrained_tools(*chat) && chat->messages.size()==1);
    chat->tools[0].definition_json="{\"function\":{\"strict\":null}}";
    assert(lie_gufo::guide_constrained_tools(*chat) && chat->messages.size()==1);
    chat->tools[0].definition_json="{\"function\":{\"strict\":\"true\"}}";
    assert(!lie_gufo::guide_constrained_tools(*chat) && chat->messages.size()==1);
    chat->tools[0].definition_json="{";
    assert(!lie_gufo::guide_constrained_tools(*chat) && chat->messages.size()==1);
    lie_chat_free(&r);
    // The native renderer loses IDs: reversed results and different correlated
    // values previously rendered identically. The shared C17 view must preserve
    // that distinction without injecting expected answers or new instructions.
    lie_chat_message history[]={{LIE_CHAT_USER,"Query.",6},{LIE_CHAT_ASSISTANT,"",0},
        {LIE_CHAT_TOOL,"{\"value\":941}",13},{LIE_CHAT_TOOL,"{\"value\":137}",13},
        {LIE_CHAT_USER,"Continue.",9}};
    lie_tool_argument args[]={{"key","alpha",1},{"key","beta",1}};
    lie_tool_call calls[]={{"id-alpha","get_value",&args[0],1},{"id-beta","get_value",&args[1],1}};
    lie_chat_details details[5]{};
    details[1].calls=calls;details[1].call_count=2;
    details[2].tool_call_id="id-beta";details[3].tool_call_id="id-alpha";
    lie_chat_template reversed{history,details,5,nullptr,0,0};
    auto incoming=lie_gufo::translate_chat(reversed);assert(incoming);
    auto old_incoming=gufo::tokenization::QwenChatTemplate::Render(incoming->messages,options,&why);assert(old_incoming);
    lie_chat_details changed_details[5];std::memcpy(changed_details,details,sizeof(details));
    changed_details[2].tool_call_id="id-alpha";changed_details[3].tool_call_id="id-beta";
    lie_chat_template changed{history,changed_details,5,nullptr,0,0};
    auto different=lie_gufo::translate_chat(changed);assert(different);
    assert(old_incoming==gufo::tokenization::QwenChatTemplate::Render(different->messages,options,&why));
    // Images already attached at original user indices keep their storage,
    // offsets and ordering. Tool-result groups contain no user image messages.
    incoming->messages[0].images.push_back({2,image});
    incoming->messages[4].images.push_back({3,image});
    assert(lie_gufo::order_tool_results(*incoming,reversed));
    assert(incoming->messages[2].content=="{\"value\":137}" && incoming->messages[2].tool_call_id=="id-alpha");
    assert(incoming->messages[3].content=="{\"value\":941}" && incoming->messages[3].tool_call_id=="id-beta");
    assert(incoming->messages[0].images[0].bytes==image && incoming->messages[0].images[0].offset==2);
    assert(incoming->messages[4].images[0].bytes==image && incoming->messages[4].images[0].offset==3);
    incoming->messages[0].images.clear();incoming->messages[4].images.clear();
    auto correlated=gufo::tokenization::QwenChatTemplate::Render(incoming->messages,options,&why);assert(correlated);
    assert(correlated!=old_incoming);
    assert(lie_gufo::order_tool_results(*different,changed));
    assert(correlated!=gufo::tokenization::QwenChatTemplate::Render(different->messages,options,&why));
    lie_chat_message ordered_messages[5];std::memcpy(ordered_messages,history,sizeof(history));
    std::swap(ordered_messages[2],ordered_messages[3]);
    lie_chat_template ordered{ordered_messages,changed_details,5,nullptr,0,0};
    auto same=lie_gufo::translate_chat(ordered);assert(same);
    auto old_ordered=gufo::tokenization::QwenChatTemplate::Render(same->messages,options,&why);
    assert(lie_gufo::order_tool_results(*same,ordered));
    auto new_ordered=gufo::tokenization::QwenChatTemplate::Render(same->messages,options,&why);
    assert(correlated==old_ordered && new_ordered==old_ordered);
    assert(!std::strcmp(history[2].content,"{\"value\":941}") && !std::strcmp(details[2].tool_call_id,"id-beta"));
    // A refusal leaves translated storage unchanged, including image owners.
    different=lie_gufo::translate_chat(reversed);assert(different);
    different->messages[0].images.push_back({2,image});
    details[3].tool_call_id="unknown";
    assert(!lie_gufo::order_tool_results(*different,reversed));
    assert(different->messages[2].content=="{\"value\":941}" && different->messages[0].images[0].bytes==image);
    std::cout<<"Pinned Qwen formatting, constrained guidance and correlated result view: PASS (CPU formatter, NOT inference)\n";
}
