/* SPDX-License-Identifier: MIT */
#include "lie/chat.h"
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
    for (size_t i = 0; i < r->count; ++i) free((void *)r->messages[i].content);
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
    if (!body || !model_id || !bytes || bytes > 65536 || !lie_utf8_valid(body, bytes, false)) goto fail;
    json_tokener *tok = json_tokener_new_ex(32); if (!tok) { why="allocation_failed"; goto fail; }
    json_tokener_set_flags(tok, JSON_TOKENER_STRICT | JSON_TOKENER_VALIDATE_UTF8);
    root = json_tokener_parse_ex(tok, body, (int)bytes);
    enum json_tokener_error status = json_tokener_get_error(tok);
    size_t end = json_tokener_get_parse_end(tok); json_tokener_free(tok);
    while (end < bytes && (body[end]==' ' || body[end]=='\n' || body[end]=='\r' || body[end]=='\t')) ++end;
    if (status != json_tokener_success || end != bytes || !json_object_is_type(root, json_type_object)) goto fail;
    why = "unsupported_request_field";
    json_object_object_foreach(root, name, value) {
        (void)value;
        if (strcmp(name,"model") && strcmp(name,"messages") && strcmp(name,"max_tokens") &&
            strcmp(name,"stream") && strcmp(name,"temperature") && strcmp(name,"seed") &&
            strcmp(name,"stream_options") && strcmp(name,"chat_template_kwargs")) goto fail;
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
    why = "invalid_max_tokens";
    if (json_object_object_get_ex(root,"max_tokens",&v)) {
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
    why = "invalid_messages";
    if (!json_object_object_get_ex(root,"messages",&v) || !json_object_is_type(v,json_type_array)) goto fail;
    size_t count=json_object_array_length(v);
    if (!count || count>LIE_CHAT_MAX_MESSAGES) goto fail;
    for (size_t i=0;i<count;++i) {
        json_object *msg=json_object_array_get_idx(v,i), *role, *text;
        if (!json_object_is_type(msg,json_type_object) || json_object_object_length(msg)!=2 ||
            !json_object_object_get_ex(msg,"role",&role) || !json_object_object_get_ex(msg,"content",&text) ||
            !json_object_is_type(text,json_type_string)) goto fail;
        lie_chat_role r;
        if (literal(role,"system")) r=LIE_CHAT_SYSTEM;
        else if (literal(role,"user")) r=LIE_CHAT_USER;
        else if (literal(role,"assistant")) r=LIE_CHAT_ASSISTANT;
        else goto fail;
        size_t n=(size_t)json_object_get_string_len(text);
        const char *s=json_object_get_string(text);
        if (!lie_utf8_valid(s,n,false)) goto fail;
        char *copy=malloc(n+1); if (!copy) { why="allocation_failed"; goto fail; }
        memcpy(copy,s,n); copy[n]=0;
        out->messages[out->count++]=(lie_chat_message){r,copy,n};
    }
    json_object_put(root); error[0]=0; return true;
fail:
    if (root) json_object_put(root);
    lie_chat_free(out); snprintf(error,256,"%s",why); return false;
}
