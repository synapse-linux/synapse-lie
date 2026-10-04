/* SPDX-License-Identifier: MIT */
#include "lie/tools.h"
#include "lie/wire.h"
#include "lie/responses.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *defs="[{\"type\":\"function\",\"function\":{\"name\":\"edit\",\"parameters\":{\"type\":\"object\",\"properties\":{\"path\":{\"type\":\"string\"},\"edits\":{\"type\":\"array\"},\"flag\":{\"type\":\"boolean\"},\"offset\":{\"type\":\"integer\"},\"value\":{\"type\":[\"string\",\"null\"]}},\"required\":[\"path\"],\"additionalProperties\":false}}}]";
static bool parse(const char *messages, const char *extra, lie_chat_request *r) {
    char body[16384],error[256];
    int n=snprintf(body,sizeof(body),"{\"model\":\"m\",\"messages\":%s,\"tools\":%s%s}",messages,defs,extra?extra:"");
    assert(n>0 && (size_t)n<sizeof(body)); return lie_chat_parse(body,(size_t)n,"m",r,error);
}
static json_object *field(json_object *o,const char *key) { json_object *v=NULL; assert(json_object_object_get_ex(o,key,&v)); return v; }
static void bad(lie_tool_policy *p,const char *text,bool complete) {
    json_object *m=NULL; char error[256];
    assert(!lie_tool_reply(p,text,strlen(text),complete,"id",&m,error)); assert(!m && error[0]);
}
int main(void) {
    const char *user="[{\"role\":\"user\",\"content\":\"edit it\"}]";
    lie_chat_request allowed;
    assert(parse(user,",\"tool_choice\":{\"type\":\"allowed_tools\",\"allowed_tools\":{\"mode\":\"required\",\"tools\":[{\"type\":\"function\",\"function\":{\"name\":\"edit\"}}]}}",&allowed));
    assert(allowed.tool_count==1 && allowed.tool_choice==LIE_TOOLS_REQUIRED);lie_chat_free(&allowed);
    assert(parse(user,",\"tool_choice\":{\"type\":\"allowed_tools\",\"allowed_tools\":{\"mode\":\"auto\",\"tools\":[]}}",&allowed));
    assert(!allowed.tool_count);lie_chat_free(&allowed);
    assert(!parse(user,",\"tool_choice\":{\"type\":\"allowed_tools\",\"allowed_tools\":{\"mode\":\"required\",\"tools\":[]}}",&allowed));
    assert(!parse(user,",\"tool_choice\":{\"type\":\"allowed_tools\",\"allowed_tools\":{\"mode\":\"auto\",\"tools\":[{\"type\":\"function\",\"function\":{\"name\":\"other\"}}]}}",&allowed));
    assert(!parse(user,",\"tool_choice\":{\"type\":\"allowed_tools\",\"allowed_tools\":{\"mode\":\"auto\",\"tools\":[{\"type\":\"function\",\"function\":{\"name\":\"edit\"}},{\"type\":\"function\",\"function\":{\"name\":\"edit\"}}]}}",&allowed));
    const char *responses="{\"model\":\"m\",\"input\":\"run\",\"tools\":[{\"type\":\"function\",\"name\":\"edit\",\"parameters\":{\"type\":\"object\"}},{\"type\":\"function\",\"name\":\"read\",\"parameters\":{\"type\":\"object\"}}],\"tool_choice\":{\"type\":\"allowed_tools\",\"mode\":\"required\",\"tools\":[{\"type\":\"function\",\"name\":\"read\"}]}}";
    char allowed_error[256];
    assert(lie_responses_parse(responses,strlen(responses),"m",&allowed,allowed_error));
    assert(allowed.tool_count==1 && !strcmp(allowed.tools[0].name,"read") && allowed.tool_choice==LIE_TOOLS_REQUIRED);
    lie_chat_free(&allowed);
    lie_chat_request r; assert(parse(user,NULL,&r));
    assert(r.tool_count==1 && !strcmp(r.tools[0].name,"edit"));
    lie_tool_policy p; assert(lie_tool_policy_copy(&r,&p));
    lie_chat_free(&r); /* UI policy must remain valid after worker retirement. */
    const char *call="Preface.\n<tool_call>\n<function=edit>\n<parameter=path>\n  €🙂 \n</parameter>\n<parameter=edits>\n[{\"oldText\":\" a \",\"newText\":\"b\\nc\"}]\n</parameter>\n<parameter=flag>\ntrue\n</parameter>\n<parameter=offset>3</parameter>\n<parameter=value>null</parameter>\n</function>\n</tool_call>";
    json_object *m=NULL; char error[256];
    assert(lie_tool_reply(&p,call,strlen(call),true,"id",&m,error));
    assert(lie_json_literal(field(m,"content"),"Preface.\n"));
    json_object *calls=field(m,"tool_calls"), *c=json_object_array_get_idx(calls,0), *fn=field(c,"function");
    assert(lie_json_literal(field(c,"id"),"call-id-0") && lie_json_literal(field(fn,"name"),"edit"));
    bool valid=false;
    const char *raw=json_object_get_string(field(fn,"arguments"));
    json_object *args=lie_json_parse(raw,strlen(raw),&valid); assert(valid);
    assert(lie_json_literal(field(args,"path"),"  €🙂 "));
    assert(json_object_is_type(field(args,"flag"),json_type_boolean));
    assert(json_object_get_int(field(args,"offset"))==3);
    assert(json_object_array_length(field(args,"edits"))==1);
    assert(field(args,"value")==NULL);
    json_object_put(args); json_object_put(m); m=NULL;
    /* Every truncation within an executable call is rejected, including limits
     * ending after a complete call: budget exhaustion is not successful dispatch. */
    const char *start=strstr(call,"<tool_call>");
    for (size_t n=(size_t)(start-call)+strlen("<tool_call>");n<strlen(call);++n) {
        char *prefix=strndup(call,n); assert(prefix); bad(&p,prefix,true); free(prefix);
    }
    bad(&p,call,false);
    const char *invalid[]={
        "<tool_call><function=other></function></tool_call>",
        "<tool_call><function=edit></function></tool_call>",
        "<tool_call><function=edit><parameter=path>a</parameter><parameter=path>b</parameter></function></tool_call>",
        "<tool_call><function=edit><parameter=path>a</parameter><parameter=offset>no</parameter></function></tool_call>",
        "<tool_call><function=edit><parameter=path>a</parameter><parameter=edits>[{\"value\":1e999}]</parameter></function></tool_call>",
        "<tool_call><function=edit><parameter=path>a</parameter><parameter=offset>1.5</parameter></function></tool_call>",
        "<tool_call><function=edit><parameter=path>a</parameter><parameter=flag>1</parameter></function></tool_call>",
        "<tool_call><function=edit><parameter=path>a</parameter><parameter=oops>x</parameter></function></tool_call>",
        "<tool_call><function=edit><parameter=path>a</parameter></function></tool_call>suffix",
        "</tool_call>","<function=edit>","<tool_call", "<tool_call><function=edit><parameter=path>\0"};
    for (size_t i=0;i<sizeof(invalid)/sizeof(*invalid);++i) bad(&p,invalid[i],true);
    assert(lie_tool_reply(&p,"plain",5,false,"id",&m,error)); assert(!json_object_object_get_ex(m,"tool_calls",&args));
    json_object_put(m); m=NULL;
    const char *one="<tool_call><function=edit><parameter=path>x</parameter></function></tool_call>";
    char twice[1024]; snprintf(twice,sizeof(twice),"%s\n%s",one,one);
    assert(lie_tool_reply(&p,twice,strlen(twice),true,"id",&m,error));
    calls=field(m,"tool_calls"); assert(json_object_array_length(calls)==2);
    assert(lie_json_literal(field(json_object_array_get_idx(calls,1),"id"),"call-id-1"));
    json_object_put(m); m=NULL;
    p.parallel=false; bad(&p,twice,true);
    p.choice=LIE_TOOLS_NONE; bad(&p,one,true);
    p.choice=LIE_TOOLS_REQUIRED; bad(&p,"plain",true);
    p.choice=LIE_TOOLS_NAMED; strcpy(p.named,"other"); bad(&p,one,true);
    lie_tool_policy_free(&p);
    assert(parse("[{\"role\":\"developer\",\"content\":\"system\"},{\"role\":\"user\",\"content\":[{\"type\":\"text\",\"text\":\"a\"},{\"type\":\"text\",\"text\":\"b\"}]}]" ,",\"store\":false,\"max_completion_tokens\":4096",&r));
    assert(r.messages[0].role==LIE_CHAT_SYSTEM && !strcmp(r.messages[1].content,"a\nb") && r.max_tokens==4096); lie_chat_free(&r);
    const char *history="[{\"role\":\"user\",\"content\":\"edit\"},{\"role\":\"assistant\",\"content\":null,\"tool_calls\":[{\"id\":\"a\",\"type\":\"function\",\"function\":{\"name\":\"edit\",\"arguments\":\"{\\\"path\\\":\\\"  x \\\",\\\"edits\\\":[{\\\"oldText\\\":\\\" a \\\",\\\"newText\\\":\\\"b\\\"}]}\"}},{\"id\":\"b\",\"type\":\"function\",\"function\":{\"name\":\"edit\",\"arguments\":\"{\\\"path\\\":\\\"y\\\"}\"}}]},{\"role\":\"tool\",\"tool_call_id\":\"b\",\"content\":\"second first\"},{\"role\":\"tool\",\"tool_call_id\":\"a\",\"name\":\"edit\",\"content\":\"done\"}]";
    assert(parse(history,",\"tool_choice\":\"none\"",&r));
    assert(r.details[1].call_count==2 && r.messages[2].role==LIE_CHAT_TOOL);
    assert(!strcmp(r.details[1].calls[0].arguments[0].value,"  x "));
    assert(!strcmp(r.details[1].calls[0].arguments[1].value,"[{\"oldText\":\" a \",\"newText\":\"b\"}]")); lie_chat_free(&r);
    const char *extras[]={",\"tool_choice\":\"garbage\"",",\"parallel_tool_calls\":1",",\"max_tokens\":8,\"max_completion_tokens\":8",",\"store\":1"};
    for (size_t i=0;i<sizeof(extras)/sizeof(*extras);++i) assert(!parse(user,extras[i],&r));
    assert(parse("[{\"role\":\"user\",\"content\":\"x\"},{\"role\":\"system\",\"content\":\"late\"}]",NULL,&r));lie_chat_free(&r);
    assert(!parse("[{\"role\":\"user\",\"content\":[{\"type\":\"image_url\",\"image_url\":{\"url\":\"x\"}}]}]",NULL,&r));
    const char *infinite="{\"nested\":[{\"bad\":1e999}]}";
    args=lie_json_parse(infinite,strlen(infinite),&valid); assert(!valid && !args);
    const char *nul="{\"key\\u0000suffix\":1}"; args=lie_json_parse(nul,strlen(nul),&valid); assert(!valid && !args);
    const char *escaped="{\"key\":\"\\\\u0000\"}"; args=lie_json_parse(escaped,strlen(escaped),&valid); assert(valid && args); json_object_put(args);
    puts("C17 tool schema/history/whitespace/typed-argument/truncation checks: PASS (not inference)");
    return 0;
}
