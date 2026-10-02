/* SPDX-License-Identifier: MIT */
#include "core_input.h"
#include "lie/text.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

void lie_core_request_init(lie_core_request *r) {
    if (!r) return;
    *r=(lie_core_request){.abi_version=LIE_CORE_REQUEST_ABI,.struct_bytes=sizeof(*r),
        .kind=LIE_INPUT_MESSAGES,.max_tokens=128,
        .generation={.abi_version=LIE_GENERATION_ABI,.struct_bytes=sizeof(lie_generation_options),.top_p=1,.seed=-1}};
}
typedef struct { unsigned char *data; size_t used, capacity; bool valid; } arena;
static void *reserve(arena *a, size_t n) {
    size_t align=_Alignof(max_align_t), padding=(align-a->used%align)%align;
    if (!a->valid || padding>a->capacity-a->used || n>a->capacity-a->used-padding) {
        a->valid=false; return NULL;
    }
    a->used+=padding;
    void *p=a->data?a->data+a->used:NULL;
    a->used+=n;
    return p;
}
static const char *span(arena *a, const char *s, size_t n) {
    if (!s || n>=LIE_CORE_INPUT_BYTES || !lie_utf8_valid(s,n,false)) { a->valid=false; return NULL; }
    char *p=reserve(a,n+1);
    if (p) { memcpy(p,s,n);p[n]=0; }
    return p;
}
static const char *string(arena *a, const char *s, bool required) {
    if (!s) { if (required) a->valid=false; return NULL; }
    size_t n=strnlen(s,LIE_CORE_INPUT_BYTES);
    if (required && !n) { a->valid=false;return NULL; }
    return span(a,s,n);
}
static bool generation_valid(const lie_generation_options *o) {
    return o->abi_version==LIE_GENERATION_ABI && o->struct_bytes==sizeof(*o) &&
        isfinite(o->temperature) && o->temperature>=0 && o->temperature<=2 &&
        isfinite(o->top_p) && o->top_p>0 && o->top_p<=1 &&
        isfinite(o->frequency_penalty) && o->frequency_penalty>=-2 && o->frequency_penalty<=2 &&
        isfinite(o->presence_penalty) && o->presence_penalty>=-2 && o->presence_penalty<=2 && o->seed>=-1;
}
static bool layout(const lie_core_request *r, lie_core_request *out, arena *a) {
    *out=*r;
    if(!lie_cache_metadata_valid(&r->cache))return false;
    if(r->cache.text_bytes){char *p=reserve(a,r->cache.text_bytes+1);
        if(p){memcpy(p,r->cache.text,r->cache.text_bytes);p[r->cache.text_bytes]=0;}out->cache.text=p;}
    if(r->cache.trailer_bytes){void *p=reserve(a,r->cache.trailer_bytes);
        if(p)memcpy(p,r->cache.trailer,r->cache.trailer_bytes);
        out->cache.trailer=p;}

    if (r->kind==LIE_INPUT_TOKENS) {
        int32_t *p=reserve(a,r->token_count*sizeof(*p));
        for (size_t i=0;i<r->token_count;++i) if (r->tokens[i]<0) return false;
        if (p) memcpy(p,r->tokens,r->token_count*sizeof(*p));
        out->tokens=p; return a->valid;
    }
    if (r->kind==LIE_INPUT_TEXT) {
        out->text=span(a,r->text,r->text_bytes); return a->valid;
    }
    const lie_chat_template *t=&r->chat;
    lie_chat_message *messages=reserve(a,t->count*sizeof(*messages));
    lie_chat_details *details=reserve(a,t->count*sizeof(*details));
    lie_chat_tool *tools=reserve(a,t->tool_count*sizeof(*tools));
    out->chat.messages=messages;out->chat.details=details;out->chat.tools=tools;
    for (size_t i=0;i<t->count && a->valid;++i) {
        lie_chat_message m=t->messages[i];
        lie_chat_details d=t->details?t->details[i]:(lie_chat_details){0};
        if (m.role<LIE_CHAT_SYSTEM || m.role>LIE_CHAT_TOOL || d.call_count>LIE_CHAT_MAX_CALLS ||
            (d.call_count && !d.calls)) return false;
        m.content=span(a,m.content,m.bytes);
        d.tool_call_id=string(a,d.tool_call_id,false);d.name=string(a,d.name,false);
        lie_tool_call *calls=reserve(a,d.call_count*sizeof(*calls));
        const lie_tool_call *src=t->details?t->details[i].calls:NULL;
        for (size_t k=0;k<d.call_count && a->valid;++k) {
            lie_tool_call c=src[k];
            if (c.argument_count>LIE_CHAT_MAX_ARGUMENTS || (c.argument_count && !c.arguments)) return false;
            c.id=string(a,c.id,true);c.name=string(a,c.name,true);
            lie_tool_argument *args=reserve(a,c.argument_count*sizeof(*args));
            for (size_t n=0;n<c.argument_count && a->valid;++n) {
                lie_tool_argument arg=c.arguments[n];
                if (arg.is_string>1) return false;
                arg.name=string(a,arg.name,true);arg.value=string(a,arg.value,false);
                if (!c.arguments[n].value) return false;
                if (args) args[n]=arg;
            }
            c.arguments=args;
            if (calls) calls[k]=c;
        }
        d.calls=calls;
        if (messages) messages[i]=m;
        if (details) details[i]=d;
    }
    out->named_tool=string(a,r->named_tool,r->tool_choice==LIE_TOOLS_NAMED);
    bool named=false;
    for (size_t i=0;i<t->tool_count && a->valid;++i) {
        lie_chat_tool tool=t->tools[i];
        tool.name=string(a,tool.name,true);tool.description=string(a,tool.description,false);
        tool.parameters_json=string(a,tool.parameters_json,true);
        tool.definition_json=string(a,tool.definition_json,true);
        if (a->valid && r->named_tool && !strcmp(r->named_tool,t->tools[i].name)) named=true;
        if (tools) tools[i]=tool;
    }
    return a->valid && (r->tool_choice!=LIE_TOOLS_NAMED || named);
}
bool lie_core_input_copy(const lie_core_request *r, lie_core_request *out, void **storage) {
    if (!r || !out || !storage || *storage || r->abi_version!=LIE_CORE_REQUEST_ABI ||
        r->struct_bytes!=sizeof(*r) || !r->max_tokens || r->max_tokens>LIE_CORE_MAX_OUTPUT ||
        !generation_valid(&r->generation) || r->kind<LIE_INPUT_MESSAGES || r->kind>LIE_INPUT_TEXT ||
        r->tool_choice<LIE_TOOLS_AUTO || r->tool_choice>LIE_TOOLS_NAMED) return false;
    if (r->kind==LIE_INPUT_MESSAGES) {
        if (!r->chat.messages || !r->chat.count || r->chat.count>LIE_CHAT_MAX_MESSAGES ||
            r->chat.tool_count>LIE_CHAT_MAX_TOOLS || (r->chat.tool_count && !r->chat.tools) ||
            r->chat.require_tool_call>1 || (r->chat.require_tool_call && (!r->chat.tool_count || r->tool_choice==LIE_TOOLS_NONE)) ||
            (r->tool_choice>=LIE_TOOLS_REQUIRED && !r->chat.tool_count) ||
            r->tokens || r->token_count || r->text || r->text_bytes) return false;
    } else {
        if (r->chat.messages || r->chat.details || r->chat.count || r->chat.tools || r->chat.tool_count ||
            r->chat.require_tool_call || r->tool_choice!=LIE_TOOLS_AUTO || r->named_tool) return false;
        if (r->kind==LIE_INPUT_TOKENS && (!r->tokens || !r->token_count ||
            r->token_count>LIE_CORE_MAX_CONTEXT || r->text || r->text_bytes)) return false;
        if (r->kind==LIE_INPUT_TEXT && (!r->text || !r->text_bytes ||
            r->text_bytes>LIE_CHAT_BODY_BYTES || r->tokens || r->token_count)) return false;
    }
    arena a={.capacity=LIE_CORE_INPUT_BYTES,.valid=true};lie_core_request copied;
    if (!layout(r,&copied,&a)) return false;
    size_t bytes=a.used;
    a=(arena){.data=malloc(bytes?bytes:1),.capacity=bytes,.valid=true};
    if (!a.data) return false;
    if (!layout(r,&copied,&a) || a.used!=bytes) { free(a.data);return false; }
    *out=copied;*storage=a.data;return true;
}
