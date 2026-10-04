/* SPDX-License-Identifier: MIT */
#include "lie/records.h"
#include "core_input.h"
#include "output_json.h"
#include <stdlib.h>
#include <string.h>
typedef struct {
  size_t offset, bytes, call;
  uint64_t token_offset;
  uint32_t tokens;
  lie_event_kind kind;
  lie_output_call fragment;
} retained_event;
struct lie_record {
  lie_records *owner;
  lie_record *next;
  unsigned refs;
  bool visible, background, done;
  char *id, *text;
  size_t bytes, capacity, allocated, instructions, text_budget;
  int64_t created;
  lie_core_request input;
  void *storage;
  lie_job *job;
  lie_job_info info;
  lie_output_call calls[LIE_CHAT_MAX_CALLS];
  size_t call_count;
  retained_event *events;
  size_t event_count, event_capacity;
};
struct lie_records {
  lie_records_options options;
  lie_record *first;
  size_t count, bytes;
};
lie_records *lie_records_create(const lie_records_options *o) {
  if (!o || !o->max_records || !o->max_bytes || !o->ttl_seconds)
    return NULL;
  lie_records *s = calloc(1, sizeof(*s));
  if (s)
    s->options = *o;
  return s;
}
static void drop(lie_record *r) {
  if (--r->refs)
    return;
  lie_records *s = r->owner;
  lie_record **p = &s->first;
  while (*p && *p != r)
    p = &(*p)->next;
  if (*p)
    *p = r->next;
  s->bytes -= r->allocated;
  --s->count;
  if (r->job) {
    lie_job_cancel(r->job);
    lie_job_release(r->job);
  }
  for (size_t i = 0; i < r->call_count; ++i) {
    free((void *)r->calls[i].id);
    free((void *)r->calls[i].name);
    free((void *)r->calls[i].arguments_json);
  }
  free(r->id);
  free(r->text);
  for (size_t i = 0; i < r->event_count; ++i) {
    if (r->events[i].kind == LIE_EVENT_TOOL_START ||
        r->events[i].kind == LIE_EVENT_TOOL_ARGUMENT_DELTA) {
      free((void *)r->events[i].fragment.id);
      free((void *)r->events[i].fragment.name);
      free((void *)r->events[i].fragment.arguments_json);
    }
  }
  free(r->events);
  free(r->storage);
  free(r);
}
void lie_records_destroy(lie_records *s) {
  if (!s)
    return;
  while (s->first) {
    lie_record *r = s->first;
    if (r->refs != 1)
      abort();
    r->visible = false;
    drop(r);
  }
  free(s);
}
static void expire(lie_records *s, int64_t now) {
  lie_record *r = s->first;
  while (r) {
    lie_record *next = r->next;
    if (r->visible && r->done && now >= r->created &&
        (uint64_t)(now - r->created) >= s->options.ttl_seconds) {
      r->visible = false;
      drop(r);
    }
    r = next;
  }
}
lie_record *lie_records_get(lie_records *s, const char *id, int64_t now) {
  if (!s || !id)
    return NULL;
  expire(s, now);
  for (lie_record *r = s->first; r; r = r->next)
    if (r->visible && !strcmp(r->id, id)) {
      ++r->refs;
      return r;
    }
  return NULL;
}
bool lie_records_delete(lie_records *s, const char *id) {
  if (!s || !id)
    return false;
  for (lie_record *r = s->first; r; r = r->next)
    if (r->visible && !strcmp(r->id, id)) {
      r->visible = false;
      if (r->job && !r->done)
        lie_job_cancel(r->job);
      drop(r);
      return true;
    }
  return false;
}
lie_record *lie_records_insert(lie_records *s, const char *id, int64_t created,
                               const lie_core_request *input,
                               size_t instructions, bool background) {
  if (!s || !id || !*id || strlen(id) > 128 || !input ||
      input->kind != LIE_INPUT_MESSAGES || instructions > input->chat.count)
    return NULL;
  expire(s, created);
  if (s->count >= s->options.max_records)
    return NULL;
  for (lie_record *r = s->first; r; r = r->next)
    if (!strcmp(r->id, id))
      return NULL;
  lie_record *r = calloc(1, sizeof(*r));
  if (!r)
    return NULL;
  size_t size = 0;
  if (!lie_core_input_copy_sized(input, &r->input, &r->storage, &size) ||
      !(r->id = strdup(id))) {
    free(r->id);
    free(r->storage);
    free(r);
    return NULL;
  }
  size_t max_tokens = input->max_tokens ? input->max_tokens : LIE_CORE_MAX_OUTPUT;
  r->text_budget = max_tokens * LIE_CORE_TOKEN_BYTES * 3 + 8;
  r->event_capacity =
      2u * max_tokens + 3u * LIE_CHAT_MAX_CALLS + 4;
  r->allocated = sizeof(*r) + size + strlen(id) + 1 + r->text_budget +
                 r->event_capacity * sizeof(*r->events);
  if (r->allocated > s->options.max_bytes - s->bytes) {
    free(r->id);
    free(r->storage);
    free(r);
    return NULL;
  }
  r->events = calloc(r->event_capacity, sizeof(*r->events));
  if (!r->events) {
    free(r->id);
    free(r->storage);
    free(r);
    return NULL;
  }
  r->owner = s;
  r->refs = 2;
  r->visible = true;
  r->background = background;
  r->created = created;
  r->instructions = instructions;
  r->next = s->first;
  s->first = r;
  ++s->count;
  s->bytes += r->allocated;
  return r;
}
void lie_record_release(lie_record *r) {
  if (r)
    drop(r);
}
bool lie_record_charge(lie_record *r, size_t n) {
  if (!r || n > r->owner->options.max_bytes - r->owner->bytes)
    return false;
  r->owner->bytes += n;
  r->allocated += n;
  return true;
}
bool lie_record_attach(lie_record *r, lie_job *j) {
  if (!r || !j || r->job)
    return false;
  size_t charge = lie_job_retention_bytes(j);
  if (charge > r->owner->options.max_bytes - r->owner->bytes)
    return false;
  r->owner->bytes += charge;
  r->allocated += charge;
  r->job = j;
  return true;
}
lie_job *lie_record_job(lie_record *r) { return r ? r->job : NULL; }
const lie_core_request *lie_record_input(lie_record *r) {
  return r ? &r->input : NULL;
}
void lie_record_snapshot(lie_record *r, lie_record_view *out) {
  if (!r || !out)
    return;
  lie_job_info info = r->info;
  if (r->job && !r->done)
    lie_job_snapshot(r->job, &info);
  *out = (lie_record_view){
      r->id,   r->text ? r->text : "", r->bytes,   r->call_count, r->calls,
      r->done, r->background,          r->created, info};
}
static bool reserve(lie_record *r, size_t n) {
  if (n <= r->capacity)
    return true;
  size_t next = r->capacity ? r->capacity : 4096;
  while (next < n)
    next *= 2;
  if (n > r->text_budget)
    return false;
  if (next > r->text_budget)
    next = r->text_budget;
  char *p = realloc(r->text, next);
  if (!p)
    return false;
  r->capacity = next;
  r->text = p;
  return true;
}
lie_flow_status lie_record_next(lie_record *r, lie_event *e) {
  if (!r || !e || !r->job)
    return LIE_FLOW_INVALID;
  lie_flow_status rc = lie_job_event_next(r->job, e);
  if (rc != LIE_FLOW_OK)
    return rc;
  bool ok = true;
  size_t offset = r->bytes, call = r->call_count;
  lie_output_call fragment = {0};
  if (e->kind == LIE_EVENT_TEXT) {
    ok = reserve(r, r->bytes + e->bytes + 1);
    if (ok) {
      memcpy(r->text + r->bytes, e->text, e->bytes);
      r->bytes += e->bytes;
      r->text[r->bytes] = 0;
    }
  }
  if (e->kind == LIE_EVENT_TOOL_CALL) {
    const lie_output_call *c = e->call;
    size_t extra = strlen(c->id) + strlen(c->name) + c->arguments_bytes + 3;
    ok = r->call_count < LIE_CHAT_MAX_CALLS &&
         extra <= r->owner->options.max_bytes - r->owner->bytes;
    if (ok) {
      lie_output_call copy = *c;
      copy.id = strdup(c->id);
      copy.name = strdup(c->name);
      copy.arguments_json = strndup(c->arguments_json, c->arguments_bytes);
      if (!copy.id || !copy.name || !copy.arguments_json) {
        free((void *)copy.id);
        free((void *)copy.name);
        free((void *)copy.arguments_json);
        ok = false;
      } else {
        r->calls[r->call_count++] = copy;
        r->allocated += extra;
        r->owner->bytes += extra;
      }
    }
  }
  if (e->kind == LIE_EVENT_TURN_END) {
    r->done = true;
    r->info = e->info;
  }
  bool provisional = e->kind == LIE_EVENT_TOOL_START ||
                     e->kind == LIE_EVENT_TOOL_ARGUMENT_DELTA;
  if (provisional) {
    const lie_output_call *c = e->call;
    size_t extra = strlen(c->id) + strlen(c->name) + c->arguments_bytes + 3;
    ok = r->event_count < r->event_capacity &&
         extra <= r->owner->options.max_bytes - r->owner->bytes;
    if (ok) {
      fragment = *c;
      fragment.id = strdup(c->id);
      fragment.name = strdup(c->name);
      fragment.arguments_json = strndup(c->arguments_json, c->arguments_bytes);
      ok = fragment.id && fragment.name && fragment.arguments_json;
      if (ok) {
        r->allocated += extra;
        r->owner->bytes += extra;
      } else {
        free((void *)fragment.id);
        free((void *)fragment.name);
        free((void *)fragment.arguments_json);
      }
    }
  }
  if (ok && (e->kind == LIE_EVENT_TEXT || e->kind == LIE_EVENT_TOOL_CALL ||
             provisional)) {
    ok = r->event_count < r->event_capacity;
    if (ok)
      r->events[r->event_count++] =
          (retained_event){offset,    e->bytes, call,    e->token_offset,
                           e->tokens, e->kind,  fragment};
  }
  if (!ok) {
    lie_job_event_release(r->job, e->ticket);
    lie_job_cancel(r->job);
    return LIE_FLOW_INVALID;
  }
  return rc;
}
bool lie_record_pump(lie_record *r) {
  if (!r || !r->job)
    return false;
  if (r->done)
    return true;
  lie_event e;
  lie_flow_status rc;
  while ((rc = lie_record_next(r, &e)) == LIE_FLOW_OK) {
    if (e.kind == LIE_EVENT_TURN_END)
      return true;
    if (lie_job_event_release(r->job, e.ticket) != LIE_FLOW_OK)
      return false;
    if (e.tokens) {
      lie_flow_status credit = lie_job_event_request(r->job, e.tokens);
      /* EOS/length closes demand when the last output is published. Sequence
       * teardown can still be running: CLOSED is a normal terminal boundary,
       * not a failed consumer. Keep pumping until semantic TURN_END retires. */
      if (credit != LIE_FLOW_OK && credit != LIE_FLOW_CLOSED)
        return false;
    }
  }
  return rc == LIE_FLOW_WOULD_BLOCK || rc == LIE_FLOW_CLOSED;
}
bool lie_record_cancel(lie_record *r) {
  if (!r || !r->background)
    return false;
  if (r->job && !r->done)
    lie_job_cancel(r->job);
  return true;
}
size_t lie_record_event_count(lie_record *r) { return r ? r->event_count : 0; }
bool lie_record_replay(lie_record *r, size_t index, lie_event *e) {
  if (!r || !e || index >= r->event_count)
    return false;
  retained_event *saved = r->events + index;
  *e = (lie_event){
      .abi_version = LIE_EVENT_ABI,
      .struct_bytes = sizeof(*e),
      .kind = saved->kind,
      .text = saved->kind == LIE_EVENT_TEXT ? r->text + saved->offset : NULL,
      .bytes = saved->bytes,
      .tokens = saved->tokens,
      .token_offset = saved->token_offset,
      .call = saved->kind == LIE_EVENT_TOOL_CALL ? r->calls + saved->call
              : saved->kind == LIE_EVENT_TOOL_START ||
                      saved->kind == LIE_EVENT_TOOL_ARGUMENT_DELTA
                  ? &saved->fragment
                  : NULL};
  return true;
}
bool lie_record_history(lie_record *r, lie_core_request *out, void **storage) {
  if (!r || !out || !storage || *storage || !r->done ||
      (r->info.finish != LIE_FINISH_STOP &&
       r->info.finish != LIE_FINISH_LENGTH))
    return false;
  size_t count = r->input.chat.count - r->instructions;
  if (count >= LIE_CHAT_MAX_MESSAGES)
    return false;
  lie_chat_message messages[LIE_CHAT_MAX_MESSAGES];
  lie_chat_details details[LIE_CHAT_MAX_MESSAGES];
  for (size_t i = 0; i < count; ++i) {
    messages[i] = r->input.chat.messages[i + r->instructions];
    details[i] = r->input.chat.details[i + r->instructions];
  }
  lie_tool_call calls[LIE_CHAT_MAX_CALLS] = {0};
  lie_tool_argument *args[LIE_CHAT_MAX_CALLS] = {0};
  oj_node *parsed[LIE_CHAT_MAX_CALLS] = {0};
  bool ok = true;
  for (size_t i = 0; i < r->call_count && ok; ++i) {
    parsed[i] =
        oj_parse(r->calls[i].arguments_json, r->calls[i].arguments_bytes);
    if (!parsed[i] || parsed[i]->type != OJ_OBJECT) {
      ok = false;
      break;
    }
    size_t n = 0;
    for (const oj_node *k = parsed[i]->child; k; k = k->next->next)
      ++n;
    args[i] = calloc(n ? n : 1, sizeof(*args[i]));
    if (!args[i]) {
      ok = false;
      break;
    }
    size_t at = 0;
    calls[i] = (lie_tool_call){r->calls[i].id, r->calls[i].name, args[i], 0};
    for (const oj_node *k = parsed[i]->child; k; k = k->next->next) {
      const oj_node *v = k->next;
      args[i][at++] = (lie_tool_argument){
          k->string,
          v->type == OJ_STRING ? v->string : strndup(v->start, v->bytes),
          v->type == OJ_STRING};
      calls[i].argument_count = at;
      if (!args[i][at - 1].value) {
        ok = false;
        break;
      }
    }
  }
  messages[count] =
      (lie_chat_message){LIE_CHAT_ASSISTANT, r->text ? r->text : "", r->bytes};
  details[count] =
      (lie_chat_details){.calls = calls, .call_count = r->call_count};
  lie_image_input images[LIE_VISION_MAX_IMAGES];
  size_t image_count = 0;
  for (size_t i = 0; i < r->input.image_count; ++i)
    if (r->input.images[i].message_index >= r->instructions) {
      images[image_count] = r->input.images[i];
      images[image_count++].message_index -= r->instructions;
    }
  lie_core_request request;
  lie_core_request_init(&request);
  request.chat = (lie_chat_template){messages, details, count + 1, NULL, 0, 0};
  request.images = image_count ? images : NULL;
  request.image_count = image_count;
  if (ok)
    ok = lie_core_input_copy(&request, out, storage);
  for (size_t i = 0; i < LIE_CHAT_MAX_CALLS; ++i) {
    for (size_t k = 0; k < calls[i].argument_count; ++k)
      if (!args[i][k].is_string)
        free((void *)args[i][k].value);
    free(args[i]);
    oj_free(parsed[i]);
  }
  return ok;
}
