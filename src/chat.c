/* SPDX-License-Identifier: MIT */
#include "lie/chat.h"
#include "lie/tools.h"
#include <json-c/json.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned utf8_width(unsigned char c) {
    if (c < 0x80) return 1;
    if (c >= 0xc2 && c <= 0xdf) return 2;
    if (c >= 0xe0 && c <= 0xef) return 3;
    if (c >= 0xf0 && c <= 0xf4) return 4;
    return 0;
}
static bool continuation(const unsigned char *p, unsigned used, unsigned char c) {
    if (c < 0x80 || c > 0xbf) return false;
    if (used != 1) return true;
    return !(p[0] == 0xe0 && c < 0xa0) && !(p[0] == 0xed && c > 0x9f) &&
           !(p[0] == 0xf0 && c < 0x90) && !(p[0] == 0xf4 && c > 0x8f);
}
bool lie_utf8_valid(const char *s, size_t n, bool allow_nul) {
    const unsigned char *p = (const unsigned char *)s;
    if (!p && n) return false;
    for (size_t i = 0; i < n;) {
        unsigned w = utf8_width(p[i]);
        if (!w || w > n - i || (!p[i] && !allow_nul)) return false;
        for (unsigned j = 1; j < w; ++j) if (!continuation(p+i, j, p[i+j])) return false;
        i += w;
    }
    return true;
}
bool lie_utf8_feed(lie_utf8_decoder *d, const char *src, size_t n, bool final,
                   char *out, size_t cap, size_t *written) {
    if (!d || (!src && n) || !out || !written || n > (SIZE_MAX-4)/3 || cap < (n+1)*3) return false;
    size_t size = 0;
    for (size_t i = 0; i < n;) {
        unsigned char c = (unsigned char)src[i];
        if (d->used) {
            if (!continuation(d->pending, d->used, c)) {
                memcpy(out+size, "\xef\xbf\xbd", 3); size+=3; d->used=d->wanted=0; continue;
            }
            d->pending[d->used++] = c; ++i;
            if (d->used == d->wanted) {
                memcpy(out+size, d->pending, d->used); size+=d->used; d->used=d->wanted=0;
            }
        } else {
            unsigned w = utf8_width(c); ++i;
            if (!w) { memcpy(out+size, "\xef\xbf\xbd", 3); size+=3; }
            else if (w == 1) out[size++] = (char)c;
            else { d->pending[0]=c; d->used=1; d->wanted=w; }
        }
    }
    if (final && d->used) { memcpy(out+size, "\xef\xbf\xbd", 3); size+=3; d->used=d->wanted=0; }
    *written = size; return true;
}
void lie_chat_free(lie_chat_request *r) {
    if (!r) return;
    for (size_t i = 0; i < r->count; ++i) {
        free((void *)r->messages[i].content);
        for (size_t k=0;k<r->details[i].call_count;++k)
            free((void *)r->details[i].calls[k].arguments);
        free((void *)r->details[i].calls);
    }
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
            strcmp(name,"max_completion_tokens") && strcmp(name,"store")) goto fail;
    }
    json_object *v;
    why = "unknown_model";
    if (!json_object_object_get_ex(root,"model",&v) || !literal(v,model_id)) goto fail;
    why = "unsupported_sampling";
    if (json_object_object_get_ex(root,"temperature",&v) &&
        ((!json_object_is_type(v,json_type_double) && !json_object_is_type(v,json_type_int)) ||
         !isfinite(json_object_get_double(v)) || json_object_get_double(v)!=0)) goto fail;
    if (json_object_object_get_ex(root,"seed",&v) &&
        (!json_object_is_type(v,json_type_int) || json_object_get_int64(v)<0)) goto fail;
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
