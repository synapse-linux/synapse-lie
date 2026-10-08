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
    if(i->cached_tokens){json_object *details=json_object_new_object();
        json_object_object_add(details,"cached_tokens",json_object_new_int64(i->cached_tokens));
        json_object_object_add(u,"prompt_tokens_details",details);}

    json_object_object_add(u,"completion_tokens",json_object_new_int64(i->output_tokens));
    json_object_object_add(u,"total_tokens",json_object_new_int64((uint64_t)i->prompt_tokens+i->output_tokens));
    return u;
}
static json_object *timings(const lie_job_info *i) {
    json_object *t=json_object_new_object();
    json_object_object_add(t,"schema",json_object_new_string("synapse-lie.request-timings.v1"));
    json_object_object_add(t,"scope",json_object_new_string("synchronous_executor_calls"));
    json_object_object_add(t,"valid",json_object_new_boolean(i->timing_valid));
    json_object_object_add(t,"prefill_tokens",json_object_new_int64(i->prefill_tokens));
    json_object_object_add(t,"cached_tokens",json_object_new_int64(i->cached_tokens));
    json_object_object_add(t,"cache_capture_ms",i->timing_valid?json_object_new_double((double)i->cache_capture_ns/1e6):NULL);
    json_object_object_add(t,"cache_restore_ms",i->timing_valid?json_object_new_double((double)i->cache_restore_ns/1e6):NULL);
    json_object_object_add(t,"ssd_cached_tokens",json_object_new_int64(i->ssd_cached_tokens));
    json_object_object_add(t,"ssd_read_ms",i->timing_valid?json_object_new_double((double)i->ssd_read_ns/1e6):NULL);
    json_object_object_add(t,"decode_mode",json_object_new_string(i->max_decode_output_tokens>1?"mtp":"ar"));
    json_object_object_add(t,"max_decode_output_tokens",json_object_new_int64(i->max_decode_output_tokens?i->max_decode_output_tokens:1));
    json_object_object_add(t,"mtp_drafted_tokens",json_object_new_int64(i->mtp_drafted));
    json_object_object_add(t,"mtp_accepted_tokens",json_object_new_int64(i->mtp_accepted));
    json_object_object_add(t,"decode_tokens",json_object_new_int64(i->output_tokens));
    json_object_object_add(t,"output_token_limit",json_object_new_int64(i->output_token_limit));
    json_object_object_add(t,"prefill_calls",json_object_new_int64(i->prefill_calls));
    json_object_object_add(t,"decode_calls",json_object_new_int64(i->decode_calls));
    json_object_object_add(t,"prefill_ms",i->timing_valid?json_object_new_double((double)i->prefill_ns/1e6):NULL);
    json_object_object_add(t,"decode_ms",i->timing_valid?json_object_new_double((double)i->decode_ns/1e6):NULL);
    json_object_object_add(t,"prefill_tokens_per_second",i->timing_valid && i->prefill_ns?
                           json_object_new_double((double)i->prefill_tokens*1e9/(double)i->prefill_ns):NULL);
    json_object_object_add(t,"decode_tokens_per_second",i->timing_valid && i->decode_ns?
                           json_object_new_double((double)i->output_tokens*1e9/(double)i->decode_ns):NULL);
    return t;
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
    json_object_object_add(o,"usage",usage(i));
    json_object_object_add(o,"lie_timings",timings(i)); return serialize(o,false);
}
char *lie_wire_chunk(const char *id, const char *model, int64_t created,
                     const char *content, size_t bytes, bool role) {
    json_object *o=base(id,model,created,true), *d=json_object_new_object();
    if (role) json_object_object_add(d,"role",json_object_new_string("assistant"));
    json_object_object_add(d,"content",json_object_new_string_len(content,(int)bytes));
    choice(o,"delta",d,NULL); return serialize(o,true);
}
char *lie_wire_tool_event(const char *id,const char *model,int64_t created,
                          const lie_output_call *call,bool start) {
    json_object *o=base(id,model,created,true),*d=json_object_new_object(),
                *calls=json_object_new_array(),*c=json_object_new_object(),
                *fn=json_object_new_object();
    json_object_object_add(c,"index",json_object_new_int64((int64_t)call->index));
    if(start) {
        json_object_object_add(c,"id",json_object_new_string(call->id));
        json_object_object_add(c,"type",json_object_new_string("function"));
        json_object_object_add(fn,"name",json_object_new_string(call->name));
    }
    json_object_object_add(fn,"arguments",json_object_new_string_len(call->arguments_json,(int)call->arguments_bytes));
    json_object_object_add(c,"function",fn);json_object_array_add(calls,c);
    json_object_object_add(d,"tool_calls",calls);choice(o,"delta",d,NULL);
    return serialize(o,true);
}
static char *end_reason(const char *id, const char *model, int64_t created,
                        const lie_job_info *i, bool with_usage, const char *finish) {
    json_object *o=base(id,model,created,true);
    if (i->finish!=LIE_FINISH_STOP && i->finish!=LIE_FINISH_LENGTH) {
        json_object *e=json_object_new_object();
        json_object_object_add(e,"code",json_object_new_string(i->finish==LIE_FINISH_CANCEL?"cancelled":i->finish==LIE_FINISH_INVALID?"invalid_tool_output":"inference_failed"));
        json_object_object_add(e,"message",json_object_new_string(i->error));
        json_object_object_add(o,"error",e);
    } else {
        choice(o,"delta",json_object_new_object(),finish?finish:i->finish==LIE_FINISH_STOP?"stop":"length");
        json_object_object_add(o,"lie_timings",timings(i));
    }
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
char *lie_wire_end(const char *id, const char *model, int64_t created,
                   const lie_job_info *i, bool with_usage) {
    return end_reason(id,model,created,i,with_usage,i->tool_calls?"tool_calls":NULL);
}
char *lie_wire_message(const char *id, const char *model, int64_t created,
                       json_object *message, const lie_job_info *i, bool stream, bool with_usage) {
    if (i->finish!=LIE_FINISH_STOP && i->finish!=LIE_FINISH_LENGTH) return NULL;
    json_object *calls=NULL;
    bool tools=json_object_object_get_ex(message,"tool_calls",&calls) && json_object_array_length(calls)>0;
    if (tools && i->finish!=LIE_FINISH_STOP) return NULL;
    const char *finish=tools?"tool_calls":i->finish==LIE_FINISH_STOP?"stop":"length";
    json_object *o=base(id,model,created,stream);
    if (!stream) {
        choice(o,"message",json_object_get(message),finish);
        json_object_object_add(o,"usage",usage(i)); json_object_object_add(o,"lie_timings",timings(i));
        return serialize(o,false);
    }
    json_object *delta=NULL;
    if (json_object_deep_copy(message,&delta,NULL)) { json_object_put(o); return NULL; }
    json_object_object_del(delta,"role");
    if (json_object_object_get_ex(delta,"tool_calls",&calls))
        for (size_t k=0;k<json_object_array_length(calls);++k)
            json_object_object_add(json_object_array_get_idx(calls,k),"index",json_object_new_int64((int64_t)k));
    choice(o,"delta",delta,NULL);
    char *first=serialize(o,true), *end=end_reason(id,model,created,i,with_usage,finish);
    if (!first || !end) { free(first); free(end); return NULL; }
    size_t n=strlen(first)+strlen(end)+1; char *result=malloc(n);
    if (result) snprintf(result,n,"%s%s",first,end);
    free(first); free(end); return result;
}
