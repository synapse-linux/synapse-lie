/* SPDX-License-Identifier: MIT */
#include "lie/chat.h"
#include "lie/tools.h"
#include <json-c/json.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void lie_chat_free(lie_chat_request *r) {
    if (!r) return;
    for (size_t i = 0; i < r->count; ++i) {
        free((void *)r->messages[i].content);
        for (size_t k=0;k<r->details[i].call_count;++k)
            free((void *)r->details[i].calls[k].arguments);
        free((void *)r->details[i].calls);
    }
    for(size_t i=0;i<r->image_count;++i)free((void *)r->images[i].data);
    json_object_put(r->json_owner);
    memset(r, 0, sizeof(*r));
}
static bool literal(json_object *j, const char *value) {
    return json_object_is_type(j, json_type_string) &&
           (size_t)json_object_get_string_len(j) == strlen(value) &&
           !memcmp(json_object_get_string(j), value, strlen(value));
}
bool lie_chat_parse(const char *body, size_t bytes, const char *model_id,
                    lie_chat_request *out, char error[256]) {
    if (!out || !error) return false;
    memset(out, 0, sizeof(*out)); out->max_tokens = 128;
    out->generation=(lie_generation_options){.abi_version=LIE_GENERATION_ABI,.struct_bytes=sizeof(lie_generation_options),.top_p=1,.seed=-1};
    const char *why = "invalid_json"; json_object *root = NULL;
    if (!model_id) goto fail;
    bool valid=false; root=lie_json_parse(body,bytes,&valid);
    if (!valid || !json_object_is_type(root,json_type_object)) goto fail;
    why = "unsupported_request_field";
    json_object_object_foreach(root, name, value) {
        (void)value;
        if (strcmp(name,"model") && strcmp(name,"messages") && strcmp(name,"max_tokens") &&
            strcmp(name,"stream") && strcmp(name,"temperature") && strcmp(name,"seed") &&
            strcmp(name,"stream_options") && strcmp(name,"chat_template_kwargs") &&
            strcmp(name,"tools") && strcmp(name,"tool_choice") && strcmp(name,"parallel_tool_calls") &&
            strcmp(name,"max_completion_tokens") && strcmp(name,"store") && strcmp(name,"top_p") && strcmp(name,"frequency_penalty") && strcmp(name,"presence_penalty")) goto fail;
    }
    json_object *v;
    why = "unknown_model";
    if (!json_object_object_get_ex(root,"model",&v) || !literal(v,model_id)) goto fail;
    why = "invalid_sampling";
    const char *keys[]={"temperature","top_p","frequency_penalty","presence_penalty"};
    double *values[]={&out->generation.temperature,&out->generation.top_p,&out->generation.frequency_penalty,&out->generation.presence_penalty};
    const double lo[]={0,0,-2,-2}, hi[]={2,1,2,2};
    for (size_t i=0;i<4;++i) if (json_object_object_get_ex(root,keys[i],&v)) {
        if ((!json_object_is_type(v,json_type_double) && !json_object_is_type(v,json_type_int)) || !isfinite(json_object_get_double(v))) goto fail;
        double x=json_object_get_double(v);
        if (x<lo[i] || x>hi[i] || (i==1 && x==0)) goto fail;
        *values[i]=x;
    }
    if (json_object_object_get_ex(root,"seed",&v)) {
        if (!json_object_is_type(v,json_type_int) || json_object_get_int64(v)<0) goto fail;
        out->generation.seed=json_object_get_int64(v);
    }
    why = "storage_not_supported";
    if (json_object_object_get_ex(root,"store",&v) &&
        (!json_object_is_type(v,json_type_boolean) || json_object_get_boolean(v))) goto fail;
    why = "invalid_max_tokens";
    json_object *alias=NULL;
    if (json_object_object_get_ex(root,"max_completion_tokens",&alias) && json_object_object_get_ex(root,"max_tokens",&v)) goto fail;
    if (json_object_object_get_ex(root,"max_tokens",&v) || json_object_object_get_ex(root,"max_completion_tokens",&v)) {
        if (!json_object_is_type(v,json_type_int) || json_object_get_int64(v)<1 || json_object_get_int64(v)>LIE_CHAT_MAX_OUTPUT) goto fail;
        out->max_tokens=(unsigned)json_object_get_int(v);
    }
    why = "invalid_stream";
    if (json_object_object_get_ex(root,"stream",&v)) {
        if (!json_object_is_type(v,json_type_boolean)) goto fail;
        out->stream=json_object_get_boolean(v);
    }
    why = "unsupported_stream_options";
    if (json_object_object_get_ex(root,"stream_options",&v)) {
        json_object *flag;
        if (!out->stream || !json_object_is_type(v,json_type_object) || json_object_object_length(v)!=1 ||
            !json_object_object_get_ex(v,"include_usage",&flag) || !json_object_is_type(flag,json_type_boolean)) goto fail;
        out->include_usage=json_object_get_boolean(flag);
    }
    why = "thinking_not_supported";
    if (json_object_object_get_ex(root,"chat_template_kwargs",&v)) {
        json_object *flag;
        if (!json_object_is_type(v,json_type_object) || json_object_object_length(v)!=1 ||
            !json_object_object_get_ex(v,"enable_thinking",&flag) ||
            !json_object_is_type(flag,json_type_boolean) || json_object_get_boolean(flag)) goto fail;
    }
    if (!lie_chat_tools_parse(root,out,&why) || !lie_chat_messages_parse(root,out,&why)) goto fail;
    out->json_owner=root; error[0]=0; return true;
fail:
    if (root) json_object_put(root);
    lie_chat_free(out); snprintf(error,256,"%s",why); return false;
}
