/* SPDX-License-Identifier: MIT */
/* Protocol projection only; model output policy/grammar belongs to the core. */
#include "lie/tools.h"
#include "lie/output.h"
#include <stdio.h>
#include <string.h>

static json_object *field(json_object *o, const char *key) {
  json_object *v = NULL;
  (void)json_object_object_get_ex(o, key, &v);
  return v;
}
bool lie_tool_policy_copy(const lie_chat_request *r, lie_tool_policy *p) {
  memset(p, 0, sizeof(*p));
  p->choice = r->tool_choice;
  p->parallel = r->parallel_tools;
  if (r->named_tool)
    snprintf(p->named, sizeof(p->named), "%s", r->named_tool);
  json_object *tools = field(r->json_owner, "tools");
  return !tools || json_object_deep_copy(tools, &p->tools, NULL) == 0;
}
void lie_tool_policy_free(lie_tool_policy *p) {
  json_object_put(p->tools);
  memset(p, 0, sizeof(*p));
}
json_object *lie_output_call_json(const lie_output_call *c) {
  if (!c || !c->id || !c->name || !c->arguments_json)
    return NULL;
  json_object *call = json_object_new_object(), *fn = json_object_new_object();
  if (!call || !fn) {
    json_object_put(call);
    json_object_put(fn);
    return NULL;
  }
  json_object_object_add(call, "id", json_object_new_string(c->id));
  json_object_object_add(call, "type", json_object_new_string("function"));
  json_object_object_add(fn, "name", json_object_new_string(c->name));
  json_object_object_add(
      fn, "arguments",
      json_object_new_string_len(c->arguments_json, (int)c->arguments_bytes));
  json_object_object_add(call, "function", fn);
  return call;
}
bool lie_tool_reply(const lie_tool_policy *p, const char *text, size_t bytes,
                    bool completed, const char *id, json_object **message,
                    char error[256]) {
  if (!p || !message || *message) {
    snprintf(error, 256, "malformed_tool_output");
    return false;
  }
  lie_chat_tool tools[LIE_CHAT_MAX_TOOLS] = {0};
  size_t n = p->tools ? json_object_array_length(p->tools) : 0;
  if (n > LIE_CHAT_MAX_TOOLS) {
    snprintf(error, 256, "invalid_tool_schema");
    return false;
  }
  for (size_t i = 0; i < n; ++i) {
    json_object *fn = field(json_object_array_get_idx(p->tools, i), "function"),
                *params = field(fn, "parameters");
    tools[i].name = json_object_get_string(field(fn, "name"));
    tools[i].parameters_json =
        params ? json_object_to_json_string_ext(params, JSON_C_TO_STRING_PLAIN)
               : "{}";
  }
  lie_output_policy policy = {tools, n, p->choice, p->parallel, p->named};
  lie_output_turn turn = {0};
  if (!lie_output_parse(&policy, text, bytes, completed, id, &turn, error))
    return false;
  json_object *result = json_object_new_object();
  if (!result) {
    lie_output_turn_clear(&turn);
    snprintf(error, 256, "allocation_failed");
    return false;
  }
  json_object_object_add(result, "role", json_object_new_string("assistant"));
  json_object_object_add(
      result, "content",
      turn.bytes || !turn.count
          ? json_object_new_string_len(turn.text, (int)turn.bytes)
          : NULL);
  if (turn.count) {
    json_object *calls = json_object_new_array();
    if (!calls) {
      json_object_put(result);
      lie_output_turn_clear(&turn);
      snprintf(error, 256, "allocation_failed");
      return false;
    }
    for (size_t i = 0; i < turn.count; ++i) {
      json_object *call = lie_output_call_json(&turn.calls[i]);
      if (!call) {
        json_object_put(calls);
        json_object_put(result);
        lie_output_turn_clear(&turn);
        snprintf(error, 256, "allocation_failed");
        return false;
      }
      json_object_array_add(calls, call);
    }
    json_object_object_add(result, "tool_calls", calls);
  }
  lie_output_turn_clear(&turn);
  *message = result;
  return true;
}
