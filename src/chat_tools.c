/* SPDX-License-Identifier: MIT */
#include "lie/tools.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

bool lie_json_text(json_object *j) {
    if (!json_object_is_type(j,json_type_string)) return false;
    const char *s=json_object_get_string(j); size_t n=(size_t)json_object_get_string_len(j);
    return lie_utf8_valid(s,n,false);
}
bool lie_json_literal(json_object *j, const char *s) {
    return lie_json_text(j) && strlen(s)==(size_t)json_object_get_string_len(j) && !strcmp(s,json_object_get_string(j));
}
bool lie_tool_name(const char *s) {
    if (!s || !*s || strlen(s)>128) return false;
    for (size_t i=0;s[i];++i) {
        unsigned char c=(unsigned char)s[i];
        if (!((c>='a' && c<='z') || (c>='A' && c<='Z') || c=='_' ||
              (i && ((c>='0' && c<='9') || c=='.' || c=='-')))) return false;
    }
    return true;
}
static bool json_values_valid(json_object *j) {
    if (json_object_is_type(j,json_type_double)) return isfinite(json_object_get_double(j));
    if (json_object_is_type(j,json_type_string)) return lie_json_text(j);
    if (json_object_is_type(j,json_type_array)) {
        for (size_t i=0;i<json_object_array_length(j);++i)
            if (!json_values_valid(json_object_array_get_idx(j,i))) return false;
    } else if (json_object_is_type(j,json_type_object)) {
        json_object_object_foreach(j,key,value) { (void)key; if (!json_values_valid(value)) return false; }
    }
    return true;
}
json_object *lie_json_parse(const char *s, size_t n, bool *valid) {
    *valid=false;
    if (!s || !n || n>LIE_CHAT_BODY_BYTES || !lie_utf8_valid(s,n,false)) return NULL;
    /* json-c truncates decoded object keys at NUL. Reject actual JSON NUL
     * escapes, but not a literal escaped backslash followed by u0000. */
    for (size_t i=0;i<n;++i) if (s[i]=='\\') {
        if (i+5<n && !memcmp(s+i+1,"u0000",5)) return NULL;
        ++i;
    }
    json_tokener *t=json_tokener_new_ex(32); if (!t) return NULL;
    json_tokener_set_flags(t,JSON_TOKENER_STRICT|JSON_TOKENER_VALIDATE_UTF8);
    /* A NUL-terminated private copy permits complete primitive JSON (numbers,
     * booleans, null), unlike parse_ex on an unterminated numeric span. */
    char *copy=malloc(n+1); if (!copy) { json_tokener_free(t); return NULL; }
    memcpy(copy,s,n); copy[n]=0;
    json_object *j=json_tokener_parse_ex(t,copy,(int)n+1);
    size_t end=json_tokener_get_parse_end(t);
    while (end<n && (s[end]==' ' || s[end]=='\n' || s[end]=='\r' || s[end]=='\t')) ++end;
    *valid=json_tokener_get_error(t)==json_tokener_success && (end==n || end==n+1) && json_values_valid(j);
    json_tokener_free(t); free(copy);
    if (!*valid) { json_object_put(j); return NULL; }
    return j;
}
static json_object *field(json_object *j, const char *key) {
    json_object *v=NULL; (void)json_object_object_get_ex(j,key,&v); return v;
}
static bool named(json_object *v) { return lie_json_text(v) && lie_tool_name(json_object_get_string(v)); }
static bool id(json_object *v) { return lie_json_text(v) && json_object_get_string_len(v)>0 && json_object_get_string_len(v)<=128; }
static bool keys(json_object *o, const char *const *allowed) {
    if (!json_object_is_type(o,json_type_object)) return false;
    json_object_object_foreach(o,k,v) {
        (void)v; size_t i=0; while (allowed[i] && strcmp(k,allowed[i])) ++i;
        if (!allowed[i]) return false;
    }
    return true;
}
bool lie_chat_tools_parse(json_object *root, lie_chat_request *r, const char **why) {
    json_object *tools=field(root,"tools"), *v;
    *why="invalid_tools";
    if (json_object_object_get_ex(root,"tools",&v)) {
        if (!json_object_is_type(tools,json_type_array) || json_object_array_length(tools)>LIE_CHAT_MAX_TOOLS) return false;
        r->tool_count=json_object_array_length(tools);
        for (size_t i=0;i<r->tool_count;++i) {
            json_object *def=json_object_array_get_idx(tools,i), *fn=field(def,"function");
            const char *const outer[]={"type","function",NULL};
            const char *const inner[]={"name","description","parameters","strict",NULL};
            if (!keys(def,outer) || !lie_json_literal(field(def,"type"),"function") || !keys(fn,inner) || !named(field(fn,"name"))) return false;
            const char *name=json_object_get_string(field(fn,"name"));
            for (size_t k=0;k<i;++k) if (!strcmp(r->tools[k].name,name)) return false;
            json_object *description=field(fn,"description"), *params=field(fn,"parameters");
            if (description && !lie_json_text(description)) return false;
            if (json_object_object_get_ex(fn, "strict", &v) &&
                !json_object_is_type(v, json_type_boolean)) {
              *why = "invalid_strict_tools";
              return false;
            }
            if (!params) { params=json_object_new_object(); json_object_object_add(fn,"parameters",params); }
            if (!json_object_is_type(params,json_type_object) ||
                (json_object_object_get_ex(params,"type",&v) && !lie_json_literal(v,"object"))) return false;
            json_object *props=field(params,"properties");
            if (props) {
                if (!json_object_is_type(props,json_type_object) || (size_t)json_object_object_length(props)>LIE_CHAT_MAX_ARGUMENTS) return false;
                json_object_object_foreach(props,k,schema) {
                    if (!lie_tool_name(k) || !json_object_is_type(schema,json_type_object)) return false;
                }
            }
            r->tools[i]=(lie_chat_tool){name,description?json_object_get_string(description):"",
                json_object_to_json_string_ext(params,JSON_C_TO_STRING_PLAIN),
                json_object_to_json_string_ext(def,JSON_C_TO_STRING_PLAIN)};
        }
    }
    r->parallel_tools=true;
    *why="invalid_parallel_tool_calls";
    if (json_object_object_get_ex(root,"parallel_tool_calls",&v)) {
        if (!json_object_is_type(v,json_type_boolean)) return false;
        r->parallel_tools=json_object_get_boolean(v);
    }
    *why="invalid_tool_choice";
    if (json_object_object_get_ex(root,"tool_choice",&v)) {
        if (lie_json_literal(v,"auto")) r->tool_choice=LIE_TOOLS_AUTO;
        else if (lie_json_literal(v,"none")) r->tool_choice=LIE_TOOLS_NONE;
        else if (lie_json_literal(v,"required")) r->tool_choice=LIE_TOOLS_REQUIRED;
        else {
            const char *const outer[]={"type","function",NULL}, *const inner[]={"name",NULL};
            json_object *fn=field(v,"function");
            if (!keys(v,outer) || !lie_json_literal(field(v,"type"),"function") || !keys(fn,inner) || !named(field(fn,"name"))) return false;
            r->tool_choice=LIE_TOOLS_NAMED; r->named_tool=json_object_get_string(field(fn,"name"));
            size_t i=0; while (i<r->tool_count && strcmp(r->named_tool,r->tools[i].name)) ++i;
            if (i==r->tool_count) return false;
        }
    }
    return r->tool_choice<LIE_TOOLS_REQUIRED || r->tool_count>0;
}
static bool copy_content(json_object *v,bool nullable,lie_chat_message *m,lie_chat_request *r,size_t message_index){
    if(!v&&nullable){m->content=strdup("");return m->content!=NULL;}
    if(lie_json_text(v)){m->content=strdup(json_object_get_string(v));m->bytes=(size_t)json_object_get_string_len(v);return m->content!=NULL;}
    if(!json_object_is_type(v,json_type_array)||!json_object_array_length(v)||json_object_array_length(v)>128)return false;
    bool images=false;
    for(size_t i=0;i<json_object_array_length(v);++i)if(lie_json_literal(field(json_object_array_get_idx(v,i),"type"),"image_url"))images=true;
    size_t total=0;
    for(size_t i=0;i<json_object_array_length(v);++i){json_object *part=json_object_array_get_idx(v,i),*type=field(part,"type");
        if(i&&!images){if(total==LIE_CHAT_BODY_BYTES)return false;++total;}
        if(lie_json_literal(type,"text")){const char *const allowed[]={"type","text",NULL};json_object *t=field(part,"text");
            if(!keys(part,allowed)||!lie_json_text(t)||(size_t)json_object_get_string_len(t)>LIE_CHAT_BODY_BYTES-total)return false;
            total+=(size_t)json_object_get_string_len(t);
        }else if(lie_json_literal(type,"image_url")){const char *const allowed[]={"type","image_url",NULL},*const image_keys[]={"url","detail",NULL};
            json_object *image=field(part,"image_url"),*url=field(image,"url"),*detail=field(image,"detail");
            if(!LIE_VISION||m->role!=LIE_CHAT_USER||r->image_count==LIE_VISION_MAX_IMAGES||!keys(part,allowed)||!keys(image,image_keys)||!lie_json_text(url)||
               (detail&&!lie_json_literal(detail,"auto")&&!lie_json_literal(detail,"high")))return false;
            unsigned char *data=NULL;size_t bytes=0;lie_image_format format;
            if(lie_image_data_url(json_object_get_string(url),(size_t)json_object_get_string_len(url),&data,&bytes,&format,NULL)!=LIE_OK)return false;
            r->images[r->image_count++]=(lie_image_input){data,bytes,format,(uint32_t)message_index,total};
        }else return false;
    }
    char *content=malloc(total+1);if(!content)return false;size_t at=0;
    for(size_t i=0;i<json_object_array_length(v);++i){json_object *t=field(json_object_array_get_idx(v,i),"text");
        if(i&&!images)content[at++]='\n';
        if(t){size_t n=(size_t)json_object_get_string_len(t);memcpy(content+at,json_object_get_string(t),n);at+=n;}}
    content[at]=0;m->content=content;m->bytes=at;return true;
}

static bool parse_calls(json_object *list, lie_chat_details *d) {
    if (!json_object_is_type(list,json_type_array) || !json_object_array_length(list) || json_object_array_length(list)>LIE_CHAT_MAX_CALLS) return false;
    d->call_count=json_object_array_length(list);
    lie_tool_call *calls=calloc(d->call_count,sizeof(*calls)); if (!calls) { d->call_count=0; return false; }
    d->calls=calls;
    for (size_t i=0;i<d->call_count;++i) {
        json_object *c=json_object_array_get_idx(list,i), *fn=field(c,"function"), *args=field(fn,"arguments");
        const char *const outer[]={"id","type","function",NULL}, *const inner[]={"name","arguments",NULL};
        if (!keys(c,outer) || !id(field(c,"id")) || !lie_json_literal(field(c,"type"),"function") || !keys(fn,inner) || !named(field(fn,"name")) || !lie_json_text(args)) return false;
        calls[i].id=json_object_get_string(field(c,"id")); calls[i].name=json_object_get_string(field(fn,"name"));
        bool valid=false; json_object *obj=lie_json_parse(json_object_get_string(args),(size_t)json_object_get_string_len(args),&valid);
        if (!valid || !json_object_is_type(obj,json_type_object) || (size_t)json_object_object_length(obj)>LIE_CHAT_MAX_ARGUMENTS) { json_object_put(obj); return false; }
        /* Normalize only our private owned tree, retaining all argument storage. */
        json_object_object_add(fn,"arguments",obj);
        size_t count=json_object_object_length(obj);
        lie_tool_argument *a=calloc(count?count:1,sizeof(*a)); if (!a) return false;
        calls[i].arguments=a; calls[i].argument_count=count;
        size_t k=0;
        json_object_object_foreach(obj,key,value) {
            if (!lie_tool_name(key)) return false;
            bool string=json_object_is_type(value,json_type_string);
            if (string && !lie_json_text(value)) return false;
            const char *raw=string?json_object_get_string(value):json_object_to_json_string_ext(value,JSON_C_TO_STRING_PLAIN);
            if (strstr(raw,"</parameter>") || strstr(raw,"<tool_call>") || strstr(raw,"</function>")) return false;
            a[k++]=(lie_tool_argument){key,raw,string?1u:0u};
        }
    }
    return true;
}
bool lie_chat_messages_parse(json_object *root, lie_chat_request *r, const char **why) {
    *why="invalid_messages";
    json_object *messages=field(root,"messages");
    if (!json_object_is_type(messages,json_type_array)) return false;
    size_t count=json_object_array_length(messages);
    if (!count || count>LIE_CHAT_MAX_MESSAGES) return false;
    const lie_tool_call *pending[LIE_CHAT_MAX_CALLS]={0}; size_t pending_count=0, seen_count=0;
    const char *seen[LIE_CHAT_MAX_MESSAGES]; bool saw_user=false;
    for (size_t i=0;i<count;++i) {
        json_object *msg=json_object_array_get_idx(messages,i), *role=field(msg,"role"), *calls=field(msg,"tool_calls");
        const char *const allowed[]={"role","content","tool_calls","tool_call_id","name",NULL};
        if (!keys(msg,allowed)) return false;
        lie_chat_message *m=&r->messages[i]; lie_chat_details *d=&r->details[i];
        r->count=i+1; /* All partial allocations have one common cleanup path. */
        if (lie_json_literal(role,"system") || lie_json_literal(role,"developer")) {
            m->role=LIE_CHAT_SYSTEM;
        } else if (lie_json_literal(role,"user")) { m->role=LIE_CHAT_USER; saw_user=true; }
        else if (lie_json_literal(role,"assistant")) { m->role=LIE_CHAT_ASSISTANT; }
        else if (lie_json_literal(role,"tool")) { m->role=LIE_CHAT_TOOL; }
        else return false;
        if (m->role!=LIE_CHAT_TOOL && pending_count) { *why="missing_tool_results"; return false; }
        if (calls && (m->role!=LIE_CHAT_ASSISTANT || !parse_calls(calls,d))) return false;
        if (!copy_content(field(msg,"content"),d->call_count>0,m,r,i)) return false;
        json_object *name=field(msg,"name"), *call_id=field(msg,"tool_call_id");
        if (name && !named(name)) return false;
        if (m->role==LIE_CHAT_TOOL) {
            *why="orphan_tool_result";
            if (!id(call_id) || calls) return false;
            size_t k=0; while (k<LIE_CHAT_MAX_CALLS && (!pending[k] || strcmp(pending[k]->id,json_object_get_string(call_id)))) ++k;
            if (k==LIE_CHAT_MAX_CALLS || (name && strcmp(json_object_get_string(name),pending[k]->name))) return false;
            d->tool_call_id=json_object_get_string(call_id); d->name=pending[k]->name;
            pending[k]=NULL; --pending_count;
        } else {
            if (call_id) return false;
            d->name=name?json_object_get_string(name):NULL;
            memset(pending,0,sizeof(pending));
            for (size_t k=0;k<d->call_count;++k) {
                const char *call=d->calls[k].id;
                for (size_t s=0;s<seen_count;++s) if (!strcmp(seen[s],call)) { *why="duplicate_tool_call_id"; return false; }
                if (seen_count==LIE_CHAT_MAX_MESSAGES) return false;
                seen[seen_count++]=call; pending[k]=&d->calls[k]; ++pending_count;
            }
        }
        *why="invalid_messages";
    }
    if (pending_count) { *why="missing_tool_results"; return false; }
    return saw_user;
}
