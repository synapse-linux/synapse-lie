/* SPDX-License-Identifier: MIT */
#include "lie/responses.h"
#include "lie/tools.h"
#include <openssl/evp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static json_object *get(json_object *o,const char *key) {
    json_object *v=NULL; (void)json_object_object_get_ex(o,key,&v); return v;
}
static bool literal(json_object *o,const char *s) {
    return json_object_is_type(o,json_type_string) && (size_t)json_object_get_string_len(o)==strlen(s) && !memcmp(json_object_get_string(o),s,strlen(s));
}
static bool fields(json_object *o,const char *const *names,size_t n) {
    if (!json_object_is_type(o,json_type_object)) return false;
    json_object_object_foreach(o,key,value) {
        (void)value; bool found=false;
        for (size_t i=0;i<n;++i) if (!strcmp(key,names[i])) found=true;
        if (!found) return false;
    }
    return true;
}
static json_object *message(const char *role,json_object *content) {
    json_object *o=json_object_new_object(); json_object_object_add(o,"role",json_object_new_string(role));
    json_object_object_add(o,"content",json_object_get(content)); return o;
}
json_object *lie_chat_history_json(const lie_core_request *r) {
  if (!r || r->kind != LIE_INPUT_MESSAGES)
    return NULL;
  json_object *messages = json_object_new_array();
  const char *roles[] = {"system", "user", "assistant", "tool"};
  for (size_t i = 0; i < r->chat.count; ++i) {
    const lie_chat_message *msg = &r->chat.messages[i];
    const lie_chat_details *d = r->chat.details ? &r->chat.details[i] : NULL;
    json_object *m = json_object_new_object();
    json_object_object_add(m, "role", json_object_new_string(roles[msg->role]));
    json_object *parts = NULL;
    size_t offset = 0;
    for (size_t k = 0; k < r->image_count; ++k)
      if (r->images[k].message_index == i) {
        const lie_image_input *image = &r->images[k];
        if (!parts)
          parts = json_object_new_array();
        if (image->text_offset > offset) {
          json_object *p = json_object_new_object();
          json_object_object_add(p, "type", json_object_new_string("text"));
          json_object_object_add(
              p, "text",
              json_object_new_string_len(msg->content + offset,
                                         (int)(image->text_offset - offset)));
          json_object_array_add(parts, p);
        }
        size_t cap = 4 * ((image->bytes + 2) / 3) + 64;
        char *url = malloc(cap);
        if (!url) {
          json_object_put(parts);
          json_object_put(m);
          json_object_put(messages);
          return NULL;
        }
        int prefix = snprintf(url, cap, "data:%s;base64,",
                              image->format == LIE_IMAGE_PNG ? "image/png"
                                                             : "image/jpeg");
        EVP_EncodeBlock((unsigned char *)url + prefix, image->data,
                        (int)image->bytes);
        json_object *p = json_object_new_object(),
                    *image_url = json_object_new_object();
        json_object_object_add(p, "type", json_object_new_string("image_url"));
        json_object_object_add(image_url, "url", json_object_new_string(url));
        json_object_object_add(p, "image_url", image_url);
        json_object_array_add(parts, p);
        free(url);
        offset = image->text_offset;
      }
    if (parts) {
      if (offset < msg->bytes) {
        json_object *p = json_object_new_object();
        json_object_object_add(p, "type", json_object_new_string("text"));
        json_object_object_add(
            p, "text",
            json_object_new_string_len(msg->content + offset,
                                       (int)(msg->bytes - offset)));
        json_object_array_add(parts, p);
      }
      json_object_object_add(m, "content", parts);
    } else
      json_object_object_add(
          m, "content",
          json_object_new_string_len(msg->content, (int)msg->bytes));
    if (d && d->tool_call_id)
      json_object_object_add(m, "tool_call_id",
                             json_object_new_string(d->tool_call_id));
    if (d && d->call_count) {
      json_object *calls = json_object_new_array();
      for (size_t k = 0; k < d->call_count; ++k) {
        const lie_tool_call *c = &d->calls[k];
        json_object *call = json_object_new_object(),
                    *fn = json_object_new_object(),
                    *args = json_object_new_object();
        for (size_t a = 0; a < c->argument_count; ++a) {
          const lie_tool_argument *arg = &c->arguments[a];
          bool valid = true;
          json_object *v =
              arg->is_string
                  ? json_object_new_string(arg->value)
                  : lie_json_parse(arg->value, strlen(arg->value), &valid);
          if (!valid) {
            json_object_put(args);
            json_object_put(fn);
            json_object_put(call);
            json_object_put(calls);
            json_object_put(m);
            json_object_put(messages);
            return NULL;
          }
          json_object_object_add(args, arg->name, v);
        }
        json_object_object_add(call, "id", json_object_new_string(c->id));
        json_object_object_add(call, "type",
                               json_object_new_string("function"));
        json_object_object_add(fn, "name", json_object_new_string(c->name));
        json_object_object_add(
            fn, "arguments",
            json_object_new_string(
                json_object_to_json_string_ext(args, JSON_C_TO_STRING_PLAIN)));
        json_object_put(args);
        json_object_object_add(call, "function", fn);
        json_object_array_add(calls, call);
      }
      json_object_object_add(m, "tool_calls", calls);
    }
    json_object_array_add(messages, m);
  }
  return messages;
}
bool lie_responses_parse_history(const char *body, size_t bytes,
                                 const char *model,
                                 const lie_core_request *history,
                                 lie_chat_request *out, char error[256]) {
  memset(out, 0, sizeof(*out));
  snprintf(error, 256, "invalid_responses_request");
  bool ok = false;
  json_object *root = lie_json_parse(body, bytes, &ok);
  const char *const allowed[] = {"model",
                                 "input",
                                 "instructions",
                                 "tools",
                                 "tool_choice",
                                 "parallel_tool_calls",
                                 "max_output_tokens",
                                 "temperature",
                                 "top_p",
                                 "stream",
                                 "store",
                                 "text",
                                 "background",
                                 "previous_response_id",
                                 "metadata",
                                 "user",
                                 "safety_identifier",
                                 "service_tier",
                                 "top_logprobs",
                                 "include",
                                 "truncation"};
  json_object *chat = json_object_new_object(),
              *messages = json_object_new_array();
  json_object_object_add(chat, "messages", messages);
  if (!ok || !fields(root, allowed, sizeof(allowed) / sizeof(*allowed)))
    goto fail;
  json_object *previous = get(root, "previous_response_id");
  if (previous && (!lie_json_text(previous) ||
                   !json_object_get_string_len(previous) || !history)) {
    snprintf(error, 256, "invalid_previous_response_id");
    goto fail;
  }
  json_object *v = get(root, "background");
  if (v && !json_object_is_type(v, json_type_boolean)) {
    snprintf(error, 256, "invalid_background");
    goto fail;
  }
  bool background = v && json_object_get_boolean(v);
  const char *keys[] = {"model",       "temperature", "top_p",
                        "stream",      "store",       "parallel_tool_calls",
                        "metadata",    "user",        "safety_identifier",
                        "service_tier"};
  for (size_t i = 0; i < sizeof(keys) / sizeof(*keys); ++i)
    if ((v = get(root, keys[i])))
      json_object_object_add(chat, keys[i], json_object_get(v));
  if ((v = get(root, "instructions"))) {
    if (!json_object_is_type(v, json_type_string))
      goto fail;
    json_object_array_add(messages, message("developer", v));
  }
  if (history) {
    json_object *prior = lie_chat_history_json(history);
    if (!prior)
      goto fail;
    for (size_t i = 0; i < json_object_array_length(prior); ++i)
      json_object_array_add(
          messages, json_object_get(json_object_array_get_idx(prior, i)));
    json_object_put(prior);
  }
  if (!get(root, "store"))
    json_object_object_add(chat, "store", json_object_new_boolean(true));
  if ((v = get(root, "truncation")) && !literal(v, "disabled") &&
      !literal(v, "auto")) {
    snprintf(error, 256, "invalid_truncation");
    goto fail;
  }
  if ((v = get(root, "top_logprobs"))) {
    json_object_object_add(chat, "logprobs", json_object_new_boolean(true));
    json_object_object_add(chat, "top_logprobs", json_object_get(v));
  }
  if ((v = get(root, "include"))) {
    if (!json_object_is_type(v, json_type_array))
      goto fail;
    for (size_t i = 0; i < json_object_array_length(v); ++i)
      if (!literal(json_object_array_get_idx(v, i),
                   "message.output_text.logprobs"))
        goto fail;
    if(json_object_array_length(v))json_object_object_add(chat, "logprobs", json_object_new_boolean(true));
  }
  json_object *input = get(root, "input");
  if (json_object_is_type(input, json_type_string))
    json_object_array_add(messages, message("user", input));
  else if (json_object_is_type(input, json_type_array)) {
    if (!json_object_array_length(input) ||
        json_object_array_length(input) > LIE_CHAT_MAX_MESSAGES)
      goto fail;
    for (size_t i = 0; i < json_object_array_length(input); ++i) {
      json_object *item = json_object_array_get_idx(input, i),
                  *type = get(item, "type"), *content = get(item, "content");
      if (literal(type, "function_call")) {
        const char *const keys2[] = {"type", "id",        "call_id",
                                     "name", "arguments", "status"};
        if (!fields(item, keys2, 6))
          goto fail;
        json_object *call = json_object_new_object(),
                    *f = json_object_new_object(),
                    *calls = json_object_new_array(),
                    *m = message("assistant", NULL);
        json_object_object_add(call, "id",
                               json_object_get(get(item, "call_id")));
        json_object_object_add(call, "type",
                               json_object_new_string("function"));
        json_object_object_add(f, "name", json_object_get(get(item, "name")));
        json_object_object_add(f, "arguments",
                               json_object_get(get(item, "arguments")));
        json_object_object_add(call, "function", f);
        json_object_array_add(calls, call);
        json_object_object_add(m, "tool_calls", calls);
        json_object *prior =
            json_object_array_length(messages)
                ? json_object_array_get_idx(
                      messages, json_object_array_length(messages) - 1)
                : NULL;
        json_object *prior_calls = get(prior, "tool_calls");
        if (prior_calls) {
          json_object_array_add(prior_calls, json_object_get(call));
          json_object_put(m);
        } else
          json_object_array_add(messages, m);
      } else if (literal(type, "function_call_output")) {
        const char *const keys2[] = {"type", "id", "call_id", "output",
                                     "status"};
        if (!fields(item, keys2, 5))
          goto fail;
        json_object *m = message("tool", get(item, "output"));
        json_object_object_add(m, "tool_call_id",
                               json_object_get(get(item, "call_id")));
        json_object_array_add(messages, m);
      } else {
        const char *const keys2[] = {"type", "id", "role", "content", "status"};
        if (!fields(item, keys2, 5) || (type && !literal(type, "message")))
          goto fail;
        json_object *m = json_object_new_object();
        json_object_object_add(m, "role", json_object_get(get(item, "role")));
        if (json_object_is_type(content, json_type_array)) {
          json_object *parts = json_object_new_array();
          for (size_t j = 0; j < json_object_array_length(content); ++j) {
            json_object *part = json_object_array_get_idx(content, j),
                        *pt = get(part, "type");
            if (literal(pt, "input_image")) {
              const char *const ik[] = {"type", "image_url", "detail"};
              if (!fields(part, ik, 3) ||
                  !json_object_is_type(get(part, "image_url"),
                                       json_type_string)) {
                json_object_put(parts);
                json_object_put(m);
                goto fail;
              }
              json_object *image = json_object_new_object(),
                          *p = json_object_new_object();
              json_object_object_add(p, "type",
                                     json_object_new_string("image_url"));
              json_object_object_add(p, "image_url", image);
              json_object_object_add(image, "url",
                                     json_object_get(get(part, "image_url")));
              if (get(part, "detail"))
                json_object_object_add(image, "detail",
                                       json_object_get(get(part, "detail")));
              json_object_array_add(parts, p);
              continue;
            }
            if ((!literal(pt, "input_text") && !literal(pt, "output_text")) ||
                !json_object_is_type(get(part, "text"), json_type_string)) {
              json_object_put(parts);
              json_object_put(m);
              goto fail;
            }
            json_object *p = json_object_new_object();
            json_object_object_add(p, "type", json_object_new_string("text"));
            json_object_object_add(p, "text",
                                   json_object_get(get(part, "text")));
            json_object_array_add(parts, p);
          }
          json_object_object_add(m, "content", parts);
        } else
          json_object_object_add(m, "content", json_object_get(content));
        json_object_array_add(messages, m);
      }
    }
  } else
    goto fail;
  if ((v = get(root, "max_output_tokens")))
    json_object_object_add(chat, "max_completion_tokens", json_object_get(v));
  if ((v = get(root, "text"))) {
    const char *const keys2[] = {"format"};
    if (!fields(v, keys2, 1))
      goto fail;
    json_object *format = get(v, "format");
    if (!json_object_is_type(format, json_type_object))
      goto fail;
    if (literal(get(format, "type"), "json_schema")) {
      const char *const keys3[] = {"type", "name", "schema", "strict",
                                   "description"};
      if (!fields(format, keys3, 5))
        goto fail;
      json_object *f = json_object_new_object(),
                  *spec = json_object_new_object();
      json_object_object_add(f, "type", json_object_new_string("json_schema"));
      for (size_t i = 1; i < 5; ++i)
        if (get(format, keys3[i]))
          json_object_object_add(spec, keys3[i],
                                 json_object_get(get(format, keys3[i])));
      json_object_object_add(f, "json_schema", spec);
      json_object_object_add(chat, "response_format", f);
    } else
      json_object_object_add(chat, "response_format", json_object_get(format));
  }
  if ((v = get(root, "tools"))) {
    if (!json_object_is_type(v, json_type_array))
      goto fail;
    json_object *tools = json_object_new_array();
    json_object_object_add(chat, "tools", tools);
    const char *const keys2[] = {"type", "name", "description", "parameters",
                                 "strict"};
    for (size_t i = 0; i < json_object_array_length(v); ++i) {
      json_object *t = json_object_array_get_idx(v, i);
      if (!fields(t, keys2, 5) || !literal(get(t, "type"), "function"))
        goto fail;
      json_object *o = json_object_new_object(), *f = json_object_new_object();
      json_object_object_add(o, "type", json_object_new_string("function"));
      for (size_t k = 1; k < 5; ++k)
        if (get(t, keys2[k]))
          json_object_object_add(f, keys2[k],
                                 json_object_get(get(t, keys2[k])));
      json_object_object_add(o, "function", f);
      json_object_array_add(tools, o);
    }
  }
  if ((v = get(root, "tool_choice"))) {
    if (json_object_is_type(v, json_type_string))
      json_object_object_add(chat, "tool_choice", json_object_get(v));
    else {
      const char *const keys2[] = {"type", "name"};
      if (!fields(v, keys2, 2) || !literal(get(v, "type"), "function"))
        goto fail;
      json_object *o = json_object_new_object(), *f = json_object_new_object();
      json_object_object_add(o, "type", json_object_new_string("function"));
      json_object_object_add(f, "name", json_object_get(get(v, "name")));
      json_object_object_add(o, "function", f);
      json_object_object_add(chat, "tool_choice", o);
    }
  }
  const char *normalized =
      json_object_to_json_string_ext(chat, JSON_C_TO_STRING_PLAIN);
  ok = lie_chat_parse(normalized, strlen(normalized), model, out, error);
  if (ok)
    out->truncate_oldest = literal(get(root, "truncation"), "auto");
  if (ok) {
    out->background = background;
    out->previous_response_id =
        previous ? json_object_get_string(previous) : NULL;
    json_object_object_add(out->json_owner, "lie_response",
                           json_object_get(root));
  }
  json_object_put(root);
  json_object_put(chat);
  return ok;
fail:
  json_object_put(root);
  json_object_put(chat);
  return false;
}
bool lie_responses_parse(const char *body, size_t bytes, const char *model,
                         lie_chat_request *out, char error[256]) {
  return lie_responses_parse_history(body, bytes, model, NULL, out, error);
}
static json_object *text_item(const char *id,const char *text,size_t n,const char *status) {
    json_object *item=json_object_new_object(), *parts=json_object_new_array(), *part=json_object_new_object();
    char item_id[128]; snprintf(item_id,sizeof(item_id),"msg_%s",id);
    json_object_object_add(item,"id",json_object_new_string(item_id)); json_object_object_add(item,"type",json_object_new_string("message"));
    json_object_object_add(item,"role",json_object_new_string("assistant")); json_object_object_add(item,"status",json_object_new_string(status));
    json_object_object_add(part,"type",json_object_new_string("output_text")); json_object_object_add(part,"text",json_object_new_string_len(text,(int)n));
    json_object_object_add(part,"annotations",json_object_new_array()); json_object_array_add(parts,part);
    json_object_object_add(item,"content",parts); return item;
}
static json_object *call_item(const char *id,json_object *call) {
    json_object *item=json_object_new_object(), *f=get(call,"function");
    json_object_object_add(item,"id",json_object_new_string(id)); json_object_object_add(item,"type",json_object_new_string("function_call"));
    json_object_object_add(item,"status",json_object_new_string("completed"));
    json_object_object_add(item,"call_id",json_object_get(get(call,"id")));
    json_object_object_add(item,"name",json_object_get(get(f,"name"))); json_object_object_add(item,"arguments",json_object_get(get(f,"arguments"))); return item;
}
json_object *lie_response_object(const char *id, const char *model,
                                 int64_t created, const char *text, size_t n,
                                 json_object *calls, const lie_job_info *info) {
  bool done = info && (info->finish == LIE_FINISH_STOP ||
                       info->finish == LIE_FINISH_LENGTH);
  const char *status = !info                               ? "in_progress"
                       : info->finish == LIE_FINISH_CANCEL ? "cancelled"
                       : info->finish == LIE_FINISH_LENGTH ? "incomplete"
                       : done                              ? "completed"
                                                           : "failed";
  json_object *o = json_object_new_object(), *output = json_object_new_array();
  json_object_object_add(o, "id", json_object_new_string(id));
  json_object_object_add(o, "object", json_object_new_string("response"));
  json_object_object_add(o, "created_at", json_object_new_int64(created));
  json_object_object_add(o, "model", json_object_new_string(model));
  json_object_object_add(o, "status", json_object_new_string(status));
  json_object_object_add(o, "store", json_object_new_boolean(false));
  json_object_object_add(o, "background", json_object_new_boolean(false));
  json_object_object_add(o, "error", NULL);
  json_object_object_add(o, "incomplete_details", NULL);
  json_object_object_add(o, "instructions", NULL);
  json_object_object_add(o, "previous_response_id", NULL);
  json_object_object_add(o, "metadata", json_object_new_object());
  if (info && !done && info->finish != LIE_FINISH_CANCEL) {
    json_object *e = json_object_new_object();
    json_object_object_add(e, "code",
                           json_object_new_string("inference_failed"));
    json_object_object_add(e, "message", json_object_new_string(info->error));
    json_object_object_add(o, "error", e);
  }
  if (info && info->finish == LIE_FINISH_LENGTH) {
    json_object *d = json_object_new_object();
    json_object_object_add(d, "reason",
                           json_object_new_string("max_output_tokens"));
    json_object_object_add(o, "incomplete_details", d);
  }
  if (done) {
    if (n || !calls)
      json_object_array_add(output, text_item(id, text, n, status));
    for (size_t i = 0; calls && i < json_object_array_length(calls); ++i) {
      char item_id[128];
      snprintf(item_id, sizeof(item_id), "fc_%s_%zu", id, i);
      json_object_array_add(
          output, call_item(item_id, json_object_array_get_idx(calls, i)));
    }
  }
  json_object_object_add(o, "output", output);
  json_object *u = NULL;
  if (done) {
    u = json_object_new_object();
    json_object_object_add(u, "input_tokens",
                           json_object_new_int64(info->prompt_tokens));
    json_object_object_add(u, "output_tokens",
                           json_object_new_int64(info->output_tokens));
    json_object_object_add(u, "total_tokens",
                           json_object_new_int64((uint64_t)info->prompt_tokens +
                                                 info->output_tokens));
    json_object *in = json_object_new_object(), *out = json_object_new_object();
    json_object_object_add(in, "cached_tokens",
                           json_object_new_int64(info->cached_tokens));
    json_object_object_add(out, "reasoning_tokens", json_object_new_int(0));
    json_object_object_add(u, "input_tokens_details", in);
    json_object_object_add(u, "output_tokens_details", out);
  }
  json_object_object_add(o, "usage", u);
  return o;
}
static json_object *event(const char *type,uint64_t *sequence) {
    json_object *o=json_object_new_object(); json_object_object_add(o,"type",json_object_new_string(type));
    json_object_object_add(o,"sequence_number",json_object_new_uint64((*sequence)++)); return o;
}
static char *serialize(json_object *o) {
    const char *type=json_object_get_string(get(o,"type")), *json=json_object_to_json_string_ext(o,JSON_C_TO_STRING_PLAIN);
    size_t n=strlen(type)+strlen(json)+20; char *s=malloc(n);
    if (s) snprintf(s,n,"event: %s\ndata: %s\n\n",type,json);
    json_object_put(o); return s;
}
static bool append(char **s,char *part) {
    if (!part) return false;
    size_t n=*s?strlen(*s):0, m=strlen(part);
    if (n>32u*1024u*1024u || m>32u*1024u*1024u-n) { free(part); return false; }
    char *copy=realloc(*s,n+m+1); if (!copy) { free(part); return false; }
    memcpy(copy+n,part,m+1); *s=copy; free(part); return true;
}
static void text_location(json_object *o,const char *id) {
    char item_id[128]; snprintf(item_id,sizeof(item_id),"msg_%s",id);
    json_object_object_add(o,"item_id",json_object_new_string(item_id));
    json_object_object_add(o,"output_index",json_object_new_int(0)); json_object_object_add(o,"content_index",json_object_new_int(0));
}
static bool text_start(char **s,const char *id,uint64_t *sequence) {
    json_object *o=event("response.output_item.added",sequence);
    json_object_object_add(o,"output_index",json_object_new_int(0));
    json_object *item=text_item(id,"",0,"in_progress");
    json_object_object_add(item,"content",json_object_new_array()); json_object_object_add(o,"item",item);
    if (!append(s,serialize(o))) return false;
    o=event("response.content_part.added",sequence); text_location(o,id);
    json_object *p=json_object_new_object(); json_object_object_add(p,"type",json_object_new_string("output_text"));
    json_object_object_add(p,"text",json_object_new_string("")); json_object_object_add(p,"annotations",json_object_new_array());
    json_object_object_add(o,"part",p); return append(s,serialize(o));
}
char *lie_response_begin(const char *id,const char *model,int64_t created,uint64_t *sequence,bool text) {
    char *s=NULL;
    const char *types[]={"response.created","response.in_progress"};
    for (size_t i=0;i<2;++i) {
        json_object *o=event(types[i],sequence); json_object_object_add(o,"response",lie_response_object(id,model,created,"",0,NULL,NULL));
        if (!append(&s,serialize(o))) { free(s); return NULL; }
    }
    if (text && !text_start(&s,id,sequence)) { free(s); return NULL; } return s;
}
char *lie_response_delta(const char *id,const char *text,size_t n,uint64_t *sequence) {
    json_object *o=event("response.output_text.delta",sequence); text_location(o,id);
    json_object_object_add(o,"delta",json_object_new_string_len(text,(int)n)); return serialize(o);
}
char *lie_response_end(const char *id, const char *model, int64_t created,
                       const char *text, size_t n, json_object *calls,
                       const lie_job_info *info, uint64_t *sequence,
                       bool text_started) {
  char *s = NULL;
  bool done =
      info->finish == LIE_FINISH_STOP || info->finish == LIE_FINISH_LENGTH;
  if (done && (n || !calls)) {
    if (!text_started &&
        (!text_start(&s, id, sequence) ||
         !append(&s, lie_response_delta(id, text, n, sequence))))
      goto fail;
    json_object *o = event("response.output_text.done", sequence);
    text_location(o, id);
    json_object_object_add(o, "text", json_object_new_string_len(text, (int)n));
    if (!append(&s, serialize(o)))
      goto fail;
    o = event("response.content_part.done", sequence);
    text_location(o, id);
    json_object *item = text_item(
                    id, text, n,
                    info->finish == LIE_FINISH_CANCEL   ? "cancelled"
                    : info->finish == LIE_FINISH_LENGTH ? "incomplete"
                                                        : "completed"),
                *part = json_object_array_get_idx(get(item, "content"), 0);
    json_object_object_add(o, "part", json_object_get(part));
    if (!append(&s, serialize(o))) {
      json_object_put(item);
      goto fail;
    }
    o = event("response.output_item.done", sequence);
    json_object_object_add(o, "output_index", json_object_new_int(0));
    json_object_object_add(o, "item", item);
    if (!append(&s, serialize(o)))
      goto fail;
  }
  if (done && calls)
    for (size_t i = 0; i < json_object_array_length(calls); ++i) {
      size_t index = i + (n ? 1 : 0);
      char item_id[128];
      snprintf(item_id, sizeof(item_id), "fc_%s_%zu", id, i);
      json_object *item =
          call_item(item_id, json_object_array_get_idx(calls, i));
      json_object *start = NULL;
      if (json_object_deep_copy(item, &start, NULL)) {
        json_object_put(item);
        goto fail;
      }
      json_object_object_add(start, "status",
                             json_object_new_string("in_progress"));
      json_object_object_add(start, "arguments", json_object_new_string(""));
      json_object *o = event("response.output_item.added", sequence);
      json_object_object_add(o, "output_index",
                             json_object_new_int64((int64_t)index));
      json_object_object_add(o, "item", start);
      if (!append(&s, serialize(o))) {
        json_object_put(item);
        goto fail;
      }
      o = event("response.function_call_arguments.delta", sequence);
      json_object_object_add(o, "item_id", json_object_new_string(item_id));
      json_object_object_add(o, "output_index",
                             json_object_new_int64((int64_t)index));
      json_object_object_add(o, "delta",
                             json_object_get(get(item, "arguments")));
      if (!append(&s, serialize(o))) {
        json_object_put(item);
        goto fail;
      }
      o = event("response.function_call_arguments.done", sequence);
      json_object_object_add(o, "item_id", json_object_new_string(item_id));
      json_object_object_add(o, "output_index",
                             json_object_new_int64((int64_t)index));
      json_object_object_add(o, "name", json_object_get(get(item, "name")));
      json_object_object_add(o, "arguments",
                             json_object_get(get(item, "arguments")));
      if (!append(&s, serialize(o))) {
        json_object_put(item);
        goto fail;
      }
      o = event("response.output_item.done", sequence);
      json_object_object_add(o, "output_index",
                             json_object_new_int64((int64_t)index));
      json_object_object_add(o, "item", item);
      if (!append(&s, serialize(o)))
        goto fail;
    }
  json_object *o =
      event(!done                               ? "response.failed"
            : info->finish == LIE_FINISH_LENGTH ? "response.incomplete"
                                                : "response.completed",
            sequence);
  json_object_object_add(
      o, "response",
      lie_response_object(id, model, created, text, n, calls, info));
  if (!append(&s, serialize(o)))
    goto fail;
  return s;
fail:
  free(s);
  return NULL;
}
