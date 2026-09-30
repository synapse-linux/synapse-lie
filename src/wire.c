/* SPDX-License-Identifier: MIT */
#include "lie/wire.h"
#include <json-c/json.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static json_object *base(const char *id, const char *model, int64_t created, bool stream) {
    json_object *o=json_object_new_object();
    json_object_object_add(o,"id",json_object_new_string(id));
    json_object_object_add(o,"object",json_object_new_string(stream?"chat.completion.chunk":"chat.completion"));
    json_object_object_add(o,"created",json_object_new_int64(created));
    json_object_object_add(o,"model",json_object_new_string(model));
    json_object_object_add(o,"system_fingerprint",json_object_new_string(lie_backend_name()));
    return o;
}
static json_object *usage(const lie_job_info *i) {
    json_object *u=json_object_new_object();
    json_object_object_add(u,"prompt_tokens",json_object_new_int64(i->prompt_tokens));
    json_object_object_add(u,"completion_tokens",json_object_new_int64(i->output_tokens));
    json_object_object_add(u,"total_tokens",json_object_new_int64((uint64_t)i->prompt_tokens+i->output_tokens));
    return u;
}
static void choice(json_object *o, const char *key, json_object *value, const char *finish) {
    json_object *array=json_object_new_array(), *c=json_object_new_object();
    json_object_object_add(c,"index",json_object_new_int(0));
    json_object_object_add(c,key,value);
    json_object_object_add(c,"finish_reason",finish?json_object_new_string(finish):NULL);
    json_object_array_add(array,c); json_object_object_add(o,"choices",array);
}
static char *serialize(json_object *o, bool stream) {
    const char *text=json_object_to_json_string_ext(o,JSON_C_TO_STRING_PLAIN);
    size_t n=strlen(text); char *copy=malloc(n+9);
    if (copy) { if (stream) snprintf(copy,n+9,"data: %s\n\n",text); else memcpy(copy,text,n+1); }
    json_object_put(o); return copy;
}
char *lie_wire_completion(const char *id, const char *model, int64_t created,
                          const char *content, size_t bytes, const lie_job_info *i) {
    if (i->finish!=LIE_FINISH_STOP && i->finish!=LIE_FINISH_LENGTH) return NULL;
    json_object *o=base(id,model,created,false), *m=json_object_new_object();
    json_object_object_add(m,"role",json_object_new_string("assistant"));
    json_object_object_add(m,"content",json_object_new_string_len(content,(int)bytes));
    choice(o,"message",m,i->finish==LIE_FINISH_STOP?"stop":"length");
    json_object_object_add(o,"usage",usage(i)); return serialize(o,false);
}
char *lie_wire_chunk(const char *id, const char *model, int64_t created,
                     const char *content, size_t bytes, bool role) {
    json_object *o=base(id,model,created,true), *d=json_object_new_object();
    if (role) json_object_object_add(d,"role",json_object_new_string("assistant"));
    json_object_object_add(d,"content",json_object_new_string_len(content,(int)bytes));
    choice(o,"delta",d,NULL); return serialize(o,true);
}
char *lie_wire_end(const char *id, const char *model, int64_t created,
                   const lie_job_info *i, bool with_usage) {
    json_object *o=base(id,model,created,true);
    if (i->finish!=LIE_FINISH_STOP && i->finish!=LIE_FINISH_LENGTH) {
        json_object *e=json_object_new_object();
        json_object_object_add(e,"code",json_object_new_string(i->finish==LIE_FINISH_CANCEL?"cancelled":"inference_failed"));
        json_object_object_add(e,"message",json_object_new_string(i->error));
        json_object_object_add(o,"error",e);
    } else choice(o,"delta",json_object_new_object(),i->finish==LIE_FINISH_STOP?"stop":"length");
    char *first=serialize(o,true), *second=NULL;
    if (with_usage && (i->finish==LIE_FINISH_STOP || i->finish==LIE_FINISH_LENGTH)) {
        o=base(id,model,created,true);
        json_object_object_add(o,"choices",json_object_new_array());
        json_object_object_add(o,"usage",usage(i)); second=serialize(o,true);
    }
    if (!first || (with_usage && !second && (i->finish==LIE_FINISH_STOP || i->finish==LIE_FINISH_LENGTH))) { free(first); free(second); return NULL; }
    size_t n=strlen(first)+(second?strlen(second):0)+16;
    char *result=malloc(n);
    if (result) snprintf(result,n,"%s%sdata: [DONE]\n\n",first,second?second:"");
    free(first); free(second); return result;
}
