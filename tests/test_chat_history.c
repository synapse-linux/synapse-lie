/* SPDX-License-Identifier: MIT */
#include "lie/chat_history.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static void refused(const lie_chat_template *input, size_t capacity) {
    size_t output[LIE_CHAT_MAX_MESSAGES];
    for (size_t i = 0; i < LIE_CHAT_MAX_MESSAGES; ++i) output[i] = 12345;
    assert(!lie_chat_tool_result_order(input, output, capacity));
    for (size_t i = 0; i < LIE_CHAT_MAX_MESSAGES; ++i) assert(output[i] == 12345);
}
int main(void) {
    lie_chat_message messages[] = {
        {LIE_CHAT_SYSTEM, "policy", 6}, {LIE_CHAT_USER, "query", 5},
        {LIE_CHAT_ASSISTANT, "", 0}, {LIE_CHAT_TOOL, "right", 5},
        {LIE_CHAT_TOOL, "left", 4}, {LIE_CHAT_USER, "continue", 8}};
    lie_tool_call calls[] = {{.id="left", .name="lookup"}, {.id="right", .name="lookup"}};
    lie_chat_details details[6] = {0};
    details[2] = (lie_chat_details){.calls=calls,.call_count=2};
    details[3] = (lie_chat_details){.tool_call_id="right",.name="lookup"};
    details[4] = (lie_chat_details){.tool_call_id="left"};
    lie_chat_template input = {.messages=messages,.details=details,.count=6};
    size_t order[6];
    const size_t expected[] = {0,1,2,4,3,5};
    lie_chat_message saved[6]; lie_chat_details saved_details[6];
    memcpy(saved,messages,sizeof(saved));memcpy(saved_details,details,sizeof(saved_details));
    assert(lie_chat_tool_result_order(&input,order,6));
    assert(!memcmp(order,expected,sizeof(expected)));
    assert(!memcmp(saved,messages,sizeof(saved)) && !memcmp(saved_details,details,sizeof(saved_details)));
    for (size_t i=0;i<6;++i) {
        assert(order[i]<6);
        for(size_t j=0;j<i;++j)assert(order[i]!=order[j]);
    }
    refused(&input,5);refused(NULL,6);
    assert(!lie_chat_tool_result_order(&input,NULL,6));
    input.count=0;refused(&input,6);input.count=6;
    details[4].tool_call_id="right";refused(&input,6);details[4].tool_call_id="left";
    details[3].tool_call_id="unknown";refused(&input,6);details[3].tool_call_id="right";
    details[3].name="wrong";refused(&input,6);details[3].name="lookup";
    details[3].tool_call_id=NULL;refused(&input,6);details[3].tool_call_id="right";
    input.details=NULL;refused(&input,6);input.details=details;
    messages[4].role=LIE_CHAT_USER;refused(&input,6);messages[4].role=LIE_CHAT_TOOL;
    input.count=4;refused(&input,6);input.count=6;
    details[2].calls=NULL;refused(&input,6);details[2].calls=calls;
    details[2].call_count=LIE_CHAT_MAX_CALLS+1;refused(&input,6);details[2].call_count=2;
    calls[1].id="left";refused(&input,6);calls[1].id="right";
    calls[0].name=NULL;refused(&input,6);calls[0].name="lookup";
    details[1].tool_call_id="left";refused(&input,6);details[1].tool_call_id=NULL;
    messages[2].role=LIE_CHAT_USER;refused(&input,6);messages[2].role=LIE_CHAT_ASSISTANT;
    messages[5].role=(lie_chat_role)99;refused(&input,6);messages[5].role=LIE_CHAT_USER;
    lie_chat_template plain={.messages=messages,.count=2};
    assert(lie_chat_tool_result_order(&plain,order,6) && order[0]==0 && order[1]==1);
    plain.count=LIE_CHAT_MAX_MESSAGES+1;refused(&plain,6);
    // Exhaust all six arrival orders for three calls, independent of names.
    const size_t permutations[][3]={{0,1,2},{0,2,1},{1,0,2},{1,2,0},{2,0,1},{2,1,0}};
    lie_chat_message triple[5]={{LIE_CHAT_USER,"query",5},{LIE_CHAT_ASSISTANT,"",0},
        {LIE_CHAT_TOOL,"",0},{LIE_CHAT_TOOL,"",0},{LIE_CHAT_TOOL,"",0}};
    lie_tool_call three[]={{.id="a",.name="lookup"},{.id="b",.name="lookup"},{.id="c",.name="other"}};
    lie_chat_details td[5]={0};td[1]=(lie_chat_details){.calls=three,.call_count=3};
    lie_chat_template ti={.messages=triple,.details=td,.count=5};
    for(size_t p=0;p<6;++p){
        for(size_t k=0;k<3;++k)td[k+2].tool_call_id=three[permutations[p][k]].id;
        assert(lie_chat_tool_result_order(&ti,order,6));
        for(size_t k=0;k<3;++k)assert(!strcmp(td[order[k+2]].tool_call_id,three[k].id));
    }
    // Largest admitted call group, reversed arrival, then a new completed cycle.
    char ids[LIE_CHAT_MAX_CALLS][16];lie_tool_call many[LIE_CHAT_MAX_CALLS];
    lie_chat_message group[LIE_CHAT_MAX_CALLS+5];lie_chat_details gd[LIE_CHAT_MAX_CALLS+5]={0};
    group[0]=(lie_chat_message){LIE_CHAT_USER,"query",5};group[1]=(lie_chat_message){LIE_CHAT_ASSISTANT,"",0};
    for(size_t i=0;i<LIE_CHAT_MAX_CALLS;++i){
        snprintf(ids[i],sizeof(ids[i]),"call-%zu",i);many[i]=(lie_tool_call){.id=ids[i],.name="lookup"};
        group[i+2]=(lie_chat_message){LIE_CHAT_TOOL,"result",6};
    }
    gd[1]=(lie_chat_details){.calls=many,.call_count=LIE_CHAT_MAX_CALLS};
    for(size_t i=0;i<LIE_CHAT_MAX_CALLS;++i)gd[i+2].tool_call_id=ids[LIE_CHAT_MAX_CALLS-1-i];
    size_t next=LIE_CHAT_MAX_CALLS+2;lie_tool_call final={.id="next",.name="lookup"};
    group[next]=(lie_chat_message){LIE_CHAT_ASSISTANT,"",0};gd[next]=(lie_chat_details){.calls=&final,.call_count=1};
    group[next+1]=(lie_chat_message){LIE_CHAT_TOOL,"final",5};gd[next+1].tool_call_id="next";
    group[next+2]=(lie_chat_message){LIE_CHAT_USER,"continue",8};
    lie_chat_template gi={.messages=group,.details=gd,.count=next+3};size_t all[LIE_CHAT_MAX_MESSAGES];
    assert(lie_chat_tool_result_order(&gi,all,LIE_CHAT_MAX_MESSAGES));
    for(size_t i=0;i<LIE_CHAT_MAX_CALLS;++i)assert(!strcmp(gd[all[i+2]].tool_call_id,many[i].id));
    assert(all[next]==next && all[next+1]==next+1 && all[next+2]==next+2);
    final.id=ids[0];gd[next+1].tool_call_id=ids[0];refused(&gi,LIE_CHAT_MAX_MESSAGES);
    puts("Model-neutral C17 tool-result correlation order: PASS (HOST, NOT inference)");
    return 0;
}
