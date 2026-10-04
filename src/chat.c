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
  if (!out || !error)
    return false;
  memset(out, 0, sizeof(*out));
  out->max_tokens = 128;
  out->choices = 1;
  out->generation =
      (lie_generation_options){.abi_version = LIE_GENERATION_ABI,
                               .struct_bytes = sizeof(lie_generation_options),
                               .top_p = 1,
                               .seed = -1};
  const char *why = "invalid_json";
  json_object *root = NULL;
  if (!model_id)
    goto fail;
  bool valid = false;
  root = lie_json_parse(body, bytes, &valid);
  if (!valid || !json_object_is_type(root, json_type_object))
    goto fail;
  why = "unsupported_request_field";
  json_object_object_foreach(root, name, value) {
    (void)value;
    if (strcmp(name, "model") && strcmp(name, "messages") &&
        strcmp(name, "max_tokens") && strcmp(name, "stream") &&
        strcmp(name, "temperature") && strcmp(name, "seed") &&
        strcmp(name, "stream_options") &&
        strcmp(name, "chat_template_kwargs") && strcmp(name, "tools") &&
        strcmp(name, "tool_choice") && strcmp(name, "parallel_tool_calls") &&
        strcmp(name, "max_completion_tokens") && strcmp(name, "store") &&
        strcmp(name, "top_p") && strcmp(name, "top_k") && strcmp(name, "min_p") &&
        strcmp(name, "frequency_penalty") &&
        strcmp(name, "presence_penalty") && strcmp(name, "stop") &&
        strcmp(name, "n") && strcmp(name, "logit_bias") &&
        strcmp(name, "logprobs") && strcmp(name, "top_logprobs") &&
        strcmp(name, "response_format") && strcmp(name, "metadata") &&
        strcmp(name, "user") && strcmp(name, "safety_identifier") &&
        strcmp(name, "service_tier"))
      goto fail;
  }
  json_object *v;
  why = "unknown_model";
  if (!json_object_object_get_ex(root, "model", &v) || !literal(v, model_id))
    goto fail;
  why = "invalid_sampling";
  const char *keys[] = {"temperature", "top_p", "frequency_penalty",
                        "presence_penalty", "min_p"};
  double *values[] = {&out->generation.temperature, &out->generation.top_p,
                      &out->generation.frequency_penalty,
                      &out->generation.presence_penalty, &out->generation.min_p};
  const double lo[] = {0, 0, -2, -2, 0}, hi[] = {2, 1, 2, 2, 1};
  for (size_t i = 0; i < sizeof(keys) / sizeof(*keys); ++i)
    if (json_object_object_get_ex(root, keys[i], &v)) {
      if ((!json_object_is_type(v, json_type_double) &&
           !json_object_is_type(v, json_type_int)) ||
          !isfinite(json_object_get_double(v)))
        goto fail;
      double x = json_object_get_double(v);
      if (x < lo[i] || x > hi[i] || (i == 1 && x == 0))
        goto fail;
      *values[i] = x;
    }
  if (json_object_object_get_ex(root, "top_k", &v)) {
    if (!json_object_is_type(v, json_type_int) || json_object_get_int64(v) < 0 ||
        json_object_get_uint64(v) > INT32_MAX)
      goto fail;
    out->generation.top_k = (int32_t)json_object_get_int64(v);
  }
  if (json_object_object_get_ex(root, "seed", &v)) {
    if (!json_object_is_type(v, json_type_int) || json_object_get_int64(v) < 0)
      goto fail;
    out->generation.seed = json_object_get_int64(v);
  }
  why = "invalid_store";
  if (json_object_object_get_ex(root, "store", &v)) {
    if (!json_object_is_type(v, json_type_boolean))
      goto fail;
    out->store = json_object_get_boolean(v);
  }
  why = "invalid_n";
  if (json_object_object_get_ex(root, "n", &v)) {
    if (!json_object_is_type(v, json_type_int) || json_object_get_int(v) < 1 ||
        json_object_get_int(v) > LIE_CORE_JOBS)
      goto fail;
    out->choices = (unsigned)json_object_get_int(v);
  }
  why = "invalid_stop";
  if (json_object_object_get_ex(root, "stop", &v) && v) {
    if (json_object_is_type(v, json_type_string)) {
      out->stop[0] = json_object_get_string(v);
      out->stop_count = 1;
    } else if (json_object_is_type(v, json_type_array)) {
      out->stop_count = json_object_array_length(v);
      if (out->stop_count > LIE_STOP_MAX)
        goto fail;
      for (size_t i = 0; i < out->stop_count; ++i) {
        json_object *s = json_object_array_get_idx(v, i);
        if (!lie_json_text(s))
          goto fail;
        out->stop[i] = json_object_get_string(s);
      }
    } else
      goto fail;
    for (size_t i = 0; i < out->stop_count; ++i)
      if (!*out->stop[i] || strlen(out->stop[i]) > LIE_STOP_BYTES ||
          !lie_utf8_valid(out->stop[i], strlen(out->stop[i]), false))
        goto fail;
  }
  why = "invalid_logprobs";
  if (json_object_object_get_ex(root, "logprobs", &v) && v) {
    if (!json_object_is_type(v, json_type_boolean))
      goto fail;
    out->generation.logprobs = json_object_get_boolean(v);
  }
  if (json_object_object_get_ex(root, "top_logprobs", &v) && v) {
    if (!json_object_is_type(v, json_type_int) || json_object_get_int(v) < 0 ||
        json_object_get_int(v) > (int)LIE_TOP_LOGPROBS_MAX ||
        !out->generation.logprobs)
      goto fail;
    out->generation.top_logprobs = (unsigned)json_object_get_int(v);
  }
  why = "invalid_logit_bias";
  if (json_object_object_get_ex(root, "logit_bias", &v) && v) {
    if (!json_object_is_type(v, json_type_object) ||
        (unsigned)json_object_object_length(v) > LIE_LOGIT_BIAS_MAX)
      goto fail;
    json_object_object_foreach(v, key, value) {
      if (!*key)
        goto fail;
      uint64_t id = 0;
      for (const char *p = key; *p; ++p) {
        if (*p < '0' || *p > '9' || id > INT32_MAX / 10u)
          goto fail;
        id = id * 10u + (unsigned)(*p - '0');
        if (id > INT32_MAX)
          goto fail;
      }
      if ((!json_object_is_type(value, json_type_int) &&
           !json_object_is_type(value, json_type_double)) ||
          !isfinite(json_object_get_double(value)) ||
          fabs(json_object_get_double(value)) > 100)
        goto fail;
      for (size_t i = 0; i < out->generation.logit_bias_count; ++i)
        if (out->bias[i].token == (int32_t)id)
          goto fail;
      out->bias[out->generation.logit_bias_count++] =
          (lie_logit_bias){(int32_t)id, json_object_get_double(value)};
    }
    out->generation.logit_bias =
        out->generation.logit_bias_count ? out->bias : NULL;
  }
  why = "invalid_response_format";
  if (json_object_object_get_ex(root, "response_format", &v) && v) {
    if (!json_object_is_type(v, json_type_object))
      goto fail;
    json_object *type = NULL, *spec = NULL;
    if (!json_object_object_get_ex(v, "type", &type))
      goto fail;
    if (literal(type, "text")) {
      if (json_object_object_length(v) != 1)
        goto fail;
    } else if (literal(type, "json_object")) {
      if (json_object_object_length(v) != 1)
        goto fail;
      out->format = LIE_FORMAT_JSON_OBJECT;
    } else if (literal(type, "json_schema")) {
      if (json_object_object_length(v) != 2 ||
          !json_object_object_get_ex(v, "json_schema", &spec) ||
          !json_object_is_type(spec, json_type_object))
        goto fail;
      json_object *schema = NULL, *name = NULL, *strict = NULL;
      if (!json_object_object_get_ex(spec, "name", &name) ||
          !lie_json_text(name) ||
          !lie_tool_name(json_object_get_string(name)) ||
          !json_object_object_get_ex(spec, "schema", &schema) ||
          !json_object_is_type(schema, json_type_object))
        goto fail;
      json_object_object_foreach(spec, k, x) {
        (void)x;
        if (strcmp(k, "name") && strcmp(k, "description") &&
            strcmp(k, "schema") && strcmp(k, "strict"))
          goto fail;
      }
      if (json_object_object_get_ex(spec, "strict", &strict)) {
        if (!json_object_is_type(strict, json_type_boolean))
          goto fail;
        out->strict = json_object_get_boolean(strict);
      }
      out->format = LIE_FORMAT_JSON_SCHEMA;
      out->schema_json =
          json_object_to_json_string_ext(schema, JSON_C_TO_STRING_PLAIN);
    } else
      goto fail;
  }
  why = "invalid_metadata";
  if (json_object_object_get_ex(root, "metadata", &v) && v) {
    if (!json_object_is_type(v, json_type_object) ||
        json_object_object_length(v) > 16)
      goto fail;
    json_object_object_foreach(v, k, x) {
      if (strlen(k) > 64 || !lie_json_text(x) ||
          json_object_get_string_len(x) > 512)
        goto fail;
    }
  }
  const char *identity[] = {"user", "safety_identifier"};
  for (size_t i = 0; i < 2; ++i)
    if (json_object_object_get_ex(root, identity[i], &v) && v &&
        (!lie_json_text(v) || json_object_get_string_len(v) > 512))
      goto fail;
  why = "unsupported_service_tier";
  if (json_object_object_get_ex(root, "service_tier", &v) && v &&
      !literal(v, "auto") && !literal(v, "default"))
    goto fail;
  why = "invalid_max_tokens";
  json_object *alias = NULL;
  if (json_object_object_get_ex(root, "max_completion_tokens", &alias) &&
      json_object_object_get_ex(root, "max_tokens", &v))
    goto fail;
  if (json_object_object_get_ex(root, "max_tokens", &v) ||
      json_object_object_get_ex(root, "max_completion_tokens", &v)) {
    if (!json_object_is_type(v, json_type_int) ||
        json_object_get_int64(v) < 1 ||
        json_object_get_int64(v) > LIE_CHAT_MAX_OUTPUT)
      goto fail;
    out->max_tokens = (unsigned)json_object_get_int(v);
  }
  why = "invalid_stream";
  if (json_object_object_get_ex(root, "stream", &v)) {
    if (!json_object_is_type(v, json_type_boolean))
      goto fail;
    out->stream = json_object_get_boolean(v);
  }
  why = "unsupported_stream_options";
  if (json_object_object_get_ex(root, "stream_options", &v)) {
    json_object *flag;
    if (!out->stream || !json_object_is_type(v, json_type_object) ||
        json_object_object_length(v) != 1 ||
        !json_object_object_get_ex(v, "include_usage", &flag) ||
        !json_object_is_type(flag, json_type_boolean))
      goto fail;
    out->include_usage = json_object_get_boolean(flag);
  }
  why = "thinking_not_supported";
  if (json_object_object_get_ex(root, "chat_template_kwargs", &v)) {
    json_object *flag;
    if (!json_object_is_type(v, json_type_object) ||
        json_object_object_length(v) != 1 ||
        !json_object_object_get_ex(v, "enable_thinking", &flag) ||
        !json_object_is_type(flag, json_type_boolean) ||
        json_object_get_boolean(flag))
      goto fail;
  }
  if (!lie_chat_tools_parse(root, out, &why) ||
      !lie_chat_messages_parse(root, out, &why))
    goto fail;
  out->json_owner = root;
  error[0] = 0;
  return true;
fail:
  if (root)
    json_object_put(root);
  lie_chat_free(out);
  snprintf(error, 256, "%s", why);
  return false;
}
