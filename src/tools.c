/* SPDX-License-Identifier: MIT */
#include "lie/tools.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static json_object *field(json_object *o, const char *key) {
    json_object *v=NULL; (void)json_object_object_get_ex(o,key,&v); return v;
}
bool lie_tool_policy_copy(const lie_chat_request *r, lie_tool_policy *p) {
    memset(p,0,sizeof(*p)); p->choice=r->tool_choice; p->parallel=r->parallel_tools;
    if (r->named_tool) snprintf(p->named,sizeof(p->named),"%s",r->named_tool);
    json_object *tools=field(r->json_owner,"tools");
    return !tools || json_object_deep_copy(tools,&p->tools,NULL)==0;
}
void lie_tool_policy_free(lie_tool_policy *p) { json_object_put(p->tools); memset(p,0,sizeof(*p)); }
static void spaces(const char **s) { while (**s==' ' || **s=='\t' || **s=='\r' || **s=='\n') ++*s; }
static void newline(const char **s) { if (**s=='\r' && (*s)[1]=='\n') *s+=2; else if (**s=='\n') ++*s; }
static bool take(const char **s, const char *literal) {
    size_t n=strlen(literal); if (strncmp(*s,literal,n)) return false;
    *s+=n; return true;
}
static bool tag_name(const char **s, const char *prefix, char out[129]) {
    if (!take(s,prefix)) return false;
    const char *end=strchr(*s,'>'); if (!end || end==*s || end-*s>128) return false;
    size_t n=(size_t)(end-*s); memcpy(out,*s,n); out[n]=0;
    if (!lie_tool_name(out)) return false;
    *s=end+1; newline(s); return true;
}
static bool marker(const char *s) {
    return strstr(s,"<tool_call") || strstr(s,"</tool_call") || strstr(s,"<function=") ||
           strstr(s,"</function") || strstr(s,"<parameter=") || strstr(s,"</parameter");
}
static json_object *definition(const lie_tool_policy *p, const char *name) {
    if (p->choice==LIE_TOOLS_NONE || (p->choice==LIE_TOOLS_NAMED && strcmp(p->named,name))) return NULL;
    size_t n=p->tools?json_object_array_length(p->tools):0;
    for (size_t i=0;i<n;++i) {
        json_object *fn=field(json_object_array_get_idx(p->tools,i),"function");
        if (lie_json_literal(field(fn,"name"),name)) return fn;
    }
    return NULL;
}
static bool type_is(json_object *schema, const char *name) {
    json_object *type=field(schema,"type");
    if (lie_json_literal(type,name)) return true;
    if (json_object_is_type(type,json_type_array)) {
        for (size_t i=0;i<json_object_array_length(type);++i)
            if (lie_json_literal(json_object_array_get_idx(type,i),name)) return true;
    }
    const char *union_keys[]={"anyOf","oneOf"};
    for (size_t k=0;k<2;++k) {
        json_object *parts=field(schema,union_keys[k]);
        if (json_object_is_type(parts,json_type_array))
            for (size_t i=0;i<json_object_array_length(parts);++i)
                if (type_is(json_object_array_get_idx(parts,i),name)) return true;
    }
    return false;
}
/* Basic JSON type/required checks; no promise of general JSON-Schema or
 * constrained sampling. The caller still validates its own tool contract. */
static bool arguments_valid(json_object *params, json_object *args) {
    json_object *required=field(params,"required"), *props=field(params,"properties");
    if (required) {
        if (!json_object_is_type(required,json_type_array)) return false;
        for (size_t i=0;i<json_object_array_length(required);++i) {
            json_object *key=json_object_array_get_idx(required,i), *v;
            if (!lie_json_text(key) || !json_object_object_get_ex(args,json_object_get_string(key),&v)) return false;
        }
    }
    json_object_object_foreach(args,key,v) {
        json_object *schema=field(props,key), *type=field(schema,"type");
        if (!schema) {
            if (json_object_is_type(field(params,"additionalProperties"),json_type_boolean) && !json_object_get_boolean(field(params,"additionalProperties"))) return false;
            continue;
        }
        if (!type) continue;
        const char *actual=v?json_type_to_name(json_object_get_type(v)):"null";
        if (json_object_is_type(v,json_type_int)) actual="integer";
        if (json_object_is_type(v,json_type_double)) actual="number";
        bool number=json_object_is_type(v,json_type_int) || json_object_is_type(v,json_type_double);
        if (number && !isfinite(json_object_get_double(v))) return false;
        if (!type_is(schema,actual) && !(number && type_is(schema,"number")) &&
            !(number && type_is(schema,"integer") && floor(json_object_get_double(v))==json_object_get_double(v))) return false;
    }
    return true;
}
bool lie_tool_reply(const lie_tool_policy *policy, const char *text, size_t bytes,
                    bool completed, const char *request_id, json_object **message, char error[256]) {
    const char *why="malformed_tool_output";
    json_object *calls=NULL, *args=NULL, *result=NULL;
    char *copy=NULL;
    if (!message || *message || !request_id || !text || !lie_utf8_valid(text,bytes,false) ||
        bytes>(size_t)LIE_CHAT_MAX_OUTPUT*LIE_CHAT_TOKEN_BYTES*3+8) goto fail;
    copy=malloc(bytes+1); if (!copy) { why="allocation_failed"; goto fail; }
    memcpy(copy,text,bytes); copy[bytes]=0;
    const char *first=strstr(copy,"<tool_call>");
    size_t prose=first?(size_t)(first-copy):bytes;
    if (!first) {
        if (marker(copy)) goto fail;
        if (policy->choice>=LIE_TOOLS_REQUIRED) { why="required_tool_call_missing"; goto fail; }
    } else {
        if (!completed) { why="truncated_tool_output"; goto fail; }
        if (policy->choice==LIE_TOOLS_NONE) { why="tool_call_disabled"; goto fail; }
        /* A delimiter in the preamble is not repaired or interpreted as a call. */
        char saved=copy[prose]; copy[prose]=0; bool bad=marker(copy); copy[prose]=saved;
        if (bad) goto fail;
        calls=json_object_new_array(); if (!calls) { why="allocation_failed"; goto fail; }
        const char *cursor=first;
        for (size_t index=0;;++index) {
            spaces(&cursor); if (!*cursor) break;
            if (index>=LIE_CHAT_MAX_CALLS || (index && !policy->parallel)) { why="too_many_tool_calls"; goto fail; }
            if (!take(&cursor,"<tool_call>")) goto fail;
            spaces(&cursor); char name[129];
            if (!tag_name(&cursor,"<function=",name)) goto fail;
            json_object *fn=definition(policy,name);
            if (!fn) { why="unknown_tool_call"; goto fail; }
            json_object *params=field(fn,"parameters"), *props=field(params,"properties");
            args=json_object_new_object(); if (!args) { why="allocation_failed"; goto fail; }
            size_t count=0;
            for (;;) {
                spaces(&cursor); if (strncmp(cursor,"<parameter=",11)) break;
                char key[129]; json_object *prior;
                if (++count>LIE_CHAT_MAX_ARGUMENTS || !tag_name(&cursor,"<parameter=",key) || json_object_object_get_ex(args,key,&prior)) goto fail;
                const char *end=strstr(cursor,"</parameter>"); if (!end) goto fail;
                size_t n=(size_t)(end-cursor);
                if (n && cursor[n-1]=='\n') { --n; if (n && cursor[n-1]=='\r') --n; }
                char *raw=malloc(n+1); if (!raw) { why="allocation_failed"; goto fail; }
                memcpy(raw,cursor,n); raw[n]=0;
                if (marker(raw)) { free(raw); goto fail; }
                json_object *schema=field(props,key), *value=NULL;
                bool valid=true;
                if (type_is(schema,"string") && !(type_is(schema,"null") && !strcmp(raw,"null"))) value=json_object_new_string_len(raw,(int)n);
                else {
                    value=lie_json_parse(raw,n,&valid);
                    if (!valid && !field(schema,"type") && !field(schema,"anyOf") && !field(schema,"oneOf")) {
                        value=json_object_new_string_len(raw,(int)n); valid=true;
                    }
                }
                free(raw);
                if (!valid) { why="invalid_tool_arguments"; goto fail; }
                json_object_object_add(args,key,value); cursor=end+strlen("</parameter>");
            }
            if (!take(&cursor,"</function>")) goto fail;
            spaces(&cursor); if (!take(&cursor,"</tool_call>")) goto fail;
            if (!arguments_valid(params,args)) { why="invalid_tool_arguments"; goto fail; }
            char id[160]; int length=snprintf(id,sizeof(id),"call-%s-%zu",request_id,index);
            if (length<0 || (size_t)length>=sizeof(id) || length>128) { why="tool_identity_too_long"; goto fail; }
            json_object *call=json_object_new_object(), *function=json_object_new_object();
            json_object_object_add(call,"id",json_object_new_string(id));
            json_object_object_add(call,"type",json_object_new_string("function"));
            json_object_object_add(function,"name",json_object_new_string(name));
            json_object_object_add(function,"arguments",json_object_new_string(json_object_to_json_string_ext(args,JSON_C_TO_STRING_PLAIN)));
            json_object_object_add(call,"function",function); json_object_array_add(calls,call);
            json_object_put(args); args=NULL;
        }
    }
    result=json_object_new_object(); if (!result) { why="allocation_failed"; goto fail; }
    json_object_object_add(result,"role",json_object_new_string("assistant"));
    json_object_object_add(result,"content",prose || !calls?json_object_new_string_len(copy,(int)prose):NULL);
    if (calls) { json_object_object_add(result,"tool_calls",calls); calls=NULL; }
    free(copy); *message=result; error[0]=0; return true;
fail:
    json_object_put(result); json_object_put(calls); json_object_put(args); free(copy);
    snprintf(error,256,"%s",why); return false;
}
