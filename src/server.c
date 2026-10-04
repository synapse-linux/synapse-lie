/* SPDX-License-Identifier: MIT */
#include "lie/choices.h"
#include "lie/metrics.h"
#include "lie/records.h"
#include "lie/responses.h"
#include "lie/state.h"
#include "lie/tools.h"
#include "lie/wire.h"
#include "lie/worker.h"
#include <errno.h>
#include <json-c/json.h>
#include <llhttp.h>
#include <locale.h>
#include <poll.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <uv.h>

#define JSON_TYPE "application/vnd.spring-boot.actuator.v3+json"
#define PROM_TYPE "text/plain; version=0.0.4; charset=utf-8"
#define MAX_RESPONSE                                                           \
  (32u * 1024u * 1024u) /* Bounded Responses done events + final projection.   \
                         */
#define MAX_BODY LIE_CHAT_BODY_BYTES
#define MAX_HEADERS (16 * 1024)
#define MAX_CONNECTIONS 64
#define TIMEOUT_NS UINT64_C(5000000000)
#define INFERENCE_TIMEOUT_NS UINT64_C(600000000000)
#define MAX_TEXT (LIE_CHAT_MAX_OUTPUT * LIE_CHAT_TOKEN_BYTES * 3 + 8)

typedef struct server server;
typedef struct connection connection;
typedef struct stored_request stored_request;
typedef struct {
  uv_poll_t poll;
  connection *parent;
  bool initialized, done;
  char *text;
  size_t bytes;
  uint64_t logprob_cursor;
  json_object *calls, *completion;
  lie_job_info info;
} choice_output;
typedef struct {
  uv_tcp_t tcp;
  server *owner;
  bool management;
} listener;
struct connection {
  uv_tcp_t tcp;
  uv_write_t write;
  llhttp_t parser;
  server *owner;
  connection *next;
  char url[2048];
  size_t url_size, headers_size, body_size, wire_size;
  uint64_t started;
  char *response, *body, *text;
  size_t body_capacity, text_bytes;
  bool management, responded, input_done, closing, writing, streaming,
      include_usage;
  unsigned handles;
  enum { WRITE_FINAL, WRITE_STREAM, WRITE_STREAM_END } write_kind;
  uv_poll_t output_poll;
  bool poll_initialized, loan;
  lie_event event;
  lie_job *job;
  lie_record *record;
  stored_request *stored;
  lie_choices *choices;
  choice_output choice[LIE_CORE_JOBS];
  unsigned choice_count, choice_done, choice_cursor;
  bool logprobs;
  uint64_t logprob_cursor;
  json_object *wire_options;
  bool buffer_tool_turn, responses;
  bool await_cancel;
  bool replay, replay_started;
  size_t replay_index;
  int64_t replay_after;
  uint64_t response_sequence;
  json_object *calls;
  char request_id[96];
  int64_t created;
};
struct server {
  uv_loop_t loop;
  listener api, management;
  uv_timer_t timer;
  uv_signal_t interrupt, terminate;
  llhttp_settings_t settings;
  connection *connections;
  size_t active;
  bool stopping;
  lie_metrics *metrics;
  lie_meter uptime, ready, connections_meter, rejected, tokens, http[3][3];
  uint64_t started;
  char instance[64];
  const char *model_id;
  lie_worker *worker;
  lie_records *records;
  stored_request *stored;
  uv_poll_t worker_poll;
  bool worker_poll_initialized;
  uint64_t request_counter, generated_seen, inference_timeout_ns;
  unsigned max_active;
  lie_meter rejected_capacity, rejected_invalid, tool_errors;
};
struct stored_request {
  server *owner;
  stored_request *next;
  lie_record *record;
  uv_poll_t poll;
  bool polling, closing, background, responses, store;
  json_object *options;
  json_object *completion;
  uint64_t started;
  connection *foreground;
};
static void close_connection(connection *c);
static void pump_job(connection *c);
static void pump_choices(connection *c);
static void pump_replay(connection *c);
static void job_error(connection *, const lie_job_info *);
static char *decorate_wire(connection *, char *, bool);
static void closed(uv_handle_t *h);
static char *json_text(json_object *j) {
    char *s = strdup(json_object_to_json_string_ext(j, JSON_C_TO_STRING_PLAIN));
    json_object_put(j); return s;
}
static const char *reason(int code) {
  switch (code) {
  case 200:
    return "OK";
  case 400:
    return "Bad Request";
  case 404:
    return "Not Found";
  case 409:
    return "Conflict";
  case 405:
    return "Method Not Allowed";
  case 413:
    return "Content Too Large";
  case 431:
    return "Request Header Fields Too Large";
  case 429:
    return "Too Many Requests";
  case 500:
    return "Internal Server Error";
  case 502:
    return "Bad Gateway";
  case 503:
    return "Service Unavailable";
  default:
    return "Error";
  }
}
static void release_loan(connection *c) {
    if (!c->loan) return;
    if (lie_job_event_release(c->job,c->event.ticket)!=LIE_FLOW_OK) abort();
    if ((!c->closing || (c->stored && c->stored->background)) && c->event.tokens)
        (void)lie_job_event_request(c->job,c->event.tokens);
    c->loan=false;
}
static void wrote(uv_write_t *w, int status) {
    connection *c=w->data;
    free(c->response); c->response=NULL; c->writing=false;
    if (status<0) close_connection(c);
    release_loan(c);
    if (c->write_kind!=WRITE_STREAM) close_connection(c);
    else if (!c->closing) pump_job(c);
}
static void record_response(connection *c, int code) {
    size_t method=c->parser.method==HTTP_GET?0:c->parser.method==HTTP_POST?1:2;
    size_t status=code<400?0:code<500?1:2;
    (void)lie_timer_record(c->owner->metrics,c->owner->http[method][status],
                          (double)(lie_monotonic_ns()-c->started)/1e9);
}
static void queue_write(connection *c, char *owned, size_t bytes, int kind) {
  if (owned && kind != WRITE_FINAL && strncmp(owned, "HTTP/", 5)) {
    owned = decorate_wire(c, owned, true);
    bytes = owned ? strlen(owned) : 0;
  }
  if (!owned || c->closing || c->writing || bytes > MAX_RESPONSE) {
    free(owned);
    close_connection(c);
    release_loan(c);
    return;
  }
  c->response = owned;
  c->write_kind = kind;
  c->writing = true;
  c->write.data = c;
  uv_buf_t b = uv_buf_init(c->response, (unsigned)bytes);
  if (uv_write(&c->write, (uv_stream_t *)&c->tcp, &b, 1, wrote)) {
    free(c->response);
    c->response = NULL;
    c->writing = false;
    close_connection(c);
    release_loan(c);
  }
}
static void respond(connection *c, int code, const char *type,
                    const char *body) {
  if (c->responded || uv_is_closing((uv_handle_t *)&c->tcp))
    return;
  c->responded = true;
  uv_read_stop((uv_stream_t *)&c->tcp);
  if (!body || strlen(body) > MAX_RESPONSE) {
    code = 500;
    type = "application/json";
    body = "{\"error\":\"response_unavailable\"}";
  }
  char *decorated = NULL;
  if (code == 200 && c->request_id[0] && !strcmp(type, "application/json")) {
    decorated = decorate_wire(c, strdup(body), false);
    if (decorated)
      body = decorated;
  }
  size_t length = strlen(body), cap = length + 512;
  char *response = malloc(cap);
  if (!response) {
    free(decorated);
    close_connection(c);
    return;
  }
  int h = snprintf(
      response, cap,
      "HTTP/1.1 %d %s\r\nContent-Type: %s\r\nContent-Length: "
      "%zu\r\nConnection: close\r\nCache-Control: "
      "no-store\r\nX-Content-Type-Options: nosniff\r\nContent-Security-Policy: "
      "default-src 'none'; style-src 'unsafe-inline'; script-src "
      "'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'\r\n\r\n",
      code, reason(code), type, length);
  if (h < 0 || (size_t)h >= cap || length >= cap - (size_t)h) {
    free(decorated);
    free(response);
    close_connection(c);
    return;
  }
  memcpy(response + h, body, length);
  free(decorated);
  record_response(c, code);
  queue_write(c, response, (size_t)h + length, WRITE_FINAL);
}
static void error_detail(connection *c, int code, const char *key, const char *message) {
    json_object *j=json_object_new_object(), *e=json_object_new_object();
    json_object_object_add(e,"type",json_object_new_string(code>=500?"server_error":"invalid_request_error"));
    json_object_object_add(e,"param",NULL);
    json_object_object_add(e,"code",json_object_new_string(key));
    json_object_object_add(e,"message",json_object_new_string(message));
    json_object_object_add(j,"error",e);
    char *body=json_text(j); respond(c,code,"application/json",body); free(body);
}
static void error_response(connection *c, int code, const char *key) { error_detail(c,code,key,reason(code)); }
static json_object *record_calls(lie_record_view *v) {
  if (!v->call_count)
    return NULL;
  json_object *calls = json_object_new_array();
  for (size_t i = 0; i < v->call_count; ++i) {
    json_object *call = lie_output_call_json(&v->calls[i]);
    if (!call) {
      json_object_put(calls);
      return NULL;
    }
    json_object_array_add(calls, call);
  }
  return calls;
}
static json_object *stored_object(stored_request *r) {
  if (r->completion) {
    json_object *metadata = NULL;
    if (json_object_object_get_ex(r->options, "metadata", &metadata))
      json_object_object_add(r->completion, "metadata",
                             json_object_get(metadata));
    return json_object_get(r->completion);
  }
  lie_record_view v;
  lie_record_snapshot(r->record, &v);
  json_object *calls = record_calls(&v), *object = NULL;
  if (r->responses)
    object = lie_response_object(v.id, r->owner->model_id, v.created, v.text,
                                 v.bytes, calls, v.done ? &v.info : NULL);
  else if (v.done && (v.info.finish == LIE_FINISH_STOP ||
                      v.info.finish == LIE_FINISH_LENGTH)) {
    json_object *message = json_object_new_object();
    json_object_object_add(message, "role",
                           json_object_new_string("assistant"));
    json_object_object_add(
        message, "content",
        v.bytes || !calls ? json_object_new_string_len(v.text, (int)v.bytes)
                          : NULL);
    if (calls)
      json_object_object_add(message, "tool_calls", json_object_get(calls));
    char *text = lie_wire_message(v.id, r->owner->model_id, v.created, message,
                                  &v.info, false, false);
    json_object_put(message);
    if (text) {
      object = json_tokener_parse(text);
      free(text);
    }
  }
  json_object_put(calls);
  if (!object)
    return NULL;
  if (v.done && lie_record_input(r->record)->generation.logprobs) {
    json_object *output = NULL;
    if (r->responses && json_object_object_get_ex(object, "output", &output)) {
      for (size_t i = 0; i < json_object_array_length(output); ++i) {
        json_object *parts = NULL;
        if (json_object_object_get_ex(json_object_array_get_idx(output, i),
                                      "content", &parts))
          for (size_t k = 0; k < json_object_array_length(parts); ++k)
            json_object_object_add(json_object_array_get_idx(parts, k),
                                   "logprobs",
                                   lie_wire_logprobs(lie_record_job(r->record),
                                                     0, v.info.output_tokens));
      }
    } else if (!r->responses && !calls &&
               json_object_object_get_ex(object, "choices", &output)) {
      json_object *logs = json_object_new_object();
      json_object_object_add(logs, "content",
                             lie_wire_logprobs(lie_record_job(r->record), 0,
                                               v.info.output_tokens));
      json_object_object_add(logs, "refusal", NULL);
      json_object_object_add(json_object_array_get_idx(output, 0), "logprobs",
                             logs);
    }
  }
  json_object_object_foreach(r->options, k, x)
      json_object_object_add(object, k, json_object_get(x));
  json_object_object_add(object, "store", json_object_new_boolean(r->store));
  if (r->responses)
    json_object_object_add(object, "background",
                           json_object_new_boolean(r->background));
  return object;
}
static stored_request *stored_find(server *s, const char *id, bool responses) {
  lie_record *record = lie_records_get(s->records, id, (int64_t)time(NULL));
  if (!record)
    return NULL;
  lie_record_release(record);
  for (stored_request *r = s->stored; r; r = r->next) {
    lie_record_view v;
    lie_record_snapshot(r->record, &v);
    if (r->responses == responses && !strcmp(v.id, id))
      return r;
  }
  return NULL;
}
static void stored_closed(uv_handle_t *h) {
  stored_request *r = h->data;
  lie_record_release(r->record);
  json_object_put(r->options);
  json_object_put(r->completion);
  free(r);
}
static void stored_dispose(stored_request *r) {
  if (r->closing)
    return;
  r->closing = true;
  stored_request **p = &r->owner->stored;
  while (*p && *p != r)
    p = &(*p)->next;
  if (*p)
    *p = r->next;
  if (r->polling) {
    uv_poll_stop(&r->poll);
    uv_close((uv_handle_t *)&r->poll, stored_closed);
  } else {
    lie_record_release(r->record);
    json_object_put(r->options);
    json_object_put(r->completion);
    free(r);
  }
}
static void stored_event(uv_poll_t *poll, int status, int events) {
  stored_request *r = poll->data;
  if (status < 0 || !(events & UV_READABLE)) {
    lie_job_cancel(lie_record_job(r->record));
    uv_poll_stop(poll);
    return;
  }
  lie_job_event_drain(lie_record_job(r->record));
  if (!lie_record_pump(r->record)) {
    lie_job_cancel(lie_record_job(r->record));
  }
  lie_record_view v;
  lie_record_snapshot(r->record, &v);
  if (v.done)
    uv_poll_stop(poll);
  for (connection *c = r->owner->connections; c; c = c->next)
    if (c->replay && c->record == r->record)
      pump_replay(c);
}
static bool stored_start(stored_request *r) {
  if (r->polling)
    return true;
  lie_job *job = lie_record_job(r->record);
  if (!job)
    return false;
  if (uv_poll_init(&r->owner->loop, &r->poll, lie_job_event_fd(job)))
    return false;
  r->poll.data = r;
  r->polling = true;
  if (uv_poll_start(&r->poll, UV_READABLE, stored_event))
    return false;
  return lie_record_pump(r->record);
}
static json_object *stored_options(lie_chat_request *request, bool responses) {
  json_object *root = request->json_owner, *options = json_object_new_object(),
              *source = NULL;
  if (responses) {
    json_object_object_get_ex(root, "lie_response", &source);
    root = source;
  }
  const char *keys[] = {
      "instructions", "previous_response_id", "metadata", "temperature",
      "top_p",        "max_output_tokens",    "text",     "tools",
      "tool_choice",  "parallel_tool_calls",  "user",     "safety_identifier",
      "service_tier"};
  for (size_t i = 0; i < sizeof(keys) / sizeof(*keys); ++i) {
    if (!responses && strcmp(keys[i], "metadata") && strcmp(keys[i], "user") &&
        strcmp(keys[i], "service_tier"))
      continue;
    json_object *v = NULL;
    if (json_object_object_get_ex(root, keys[i], &v))
      json_object_object_add(options, keys[i], json_object_get(v));
  }
  json_object *tier = NULL;
  if (json_object_object_get_ex(options, "service_tier", &tier))
    json_object_object_add(options, "service_tier",
                           json_object_new_string("default"));
  return options;
}
static void project_options(connection *c, json_object *o) {
  json_object *options = c->stored ? c->stored->options : c->wire_options;
  if (options) {
    json_object_object_foreach(options, k, v) {
      if (c->responses || !strcmp(k, "metadata") || !strcmp(k, "user") ||
          !strcmp(k, "service_tier"))
        json_object_object_add(o, k, json_object_get(v));
    }
  }
  if (c->responses && !c->replay) {
    json_object_object_add(
        o, "store", json_object_new_boolean(c->stored && c->stored->store));
    json_object_object_add(
        o, "background",
        json_object_new_boolean(c->stored && c->stored->background));
  }
}
static char *decorate_wire(connection *c, char *owned, bool stream) {
  if (!owned)
    return NULL;
  if (c->responses && stream && !c->logprobs &&
      !strncmp(owned, "event: response.output_text.delta\n", 34))
    return owned;
  if (!c->logprobs && !c->stored && !c->wire_options)
    return owned;
  size_t capacity = strlen(owned) + 4096, length = 0;
  char *out = malloc(capacity);
  if (!out) {
    free(owned);
    return NULL;
  }
  const char *p = owned;
  do {
    const char *end = stream ? strstr(p, "\n\n") : p + strlen(p);
    if (!end) {
      free(owned);
      free(out);
      return NULL;
    }
    const char *data = stream ? strstr(p, "data: ") : p;
    size_t prefix = stream ? (size_t)(data ? data + 6 - p : 0) : 0;
    if (!data || data >= end) {
      free(owned);
      free(out);
      return NULL;
    }
    char *raw = strndup(p + prefix, (size_t)(end - p) - prefix);
    json_object *o = raw && raw[0] == '{' ? json_tokener_parse(raw) : NULL;
    if (o) {
      json_object *response = NULL, *choices = NULL, *type = NULL;
      if (json_object_object_get_ex(o, "response", &response))
        project_options(c, response);
      else if (!stream || json_object_object_get_ex(o, "choices", &choices))
        project_options(c, o);
      if (c->logprobs && c->job) {
        lie_job_info info;
        lie_job_snapshot(c->job, &info);
        size_t offset = stream ? c->logprob_cursor : 0,
               count = stream
                           ? (size_t)(c->event.token_offset + c->event.tokens)
                           : info.output_tokens;
        if (count < offset)
          count = offset;
        count -= offset;
        if (choices || json_object_object_get_ex(o, "choices", &choices)) {
          for (size_t i = 0; i < json_object_array_length(choices); ++i) {
            json_object *choice = json_object_array_get_idx(choices, i),
                        *message = NULL, *content = NULL, *calls = NULL;
            json_object_object_get_ex(choice, stream ? "delta" : "message",
                                      &message);
            json_object_object_get_ex(message, "content", &content);
            json_object_object_get_ex(message, "tool_calls", &calls);
            if (content && json_object_get_string_len(content) && !calls) {
              json_object *logs = lie_wire_logprobs(c->job, offset, count);
              json_object *logobj = json_object_new_object();
              json_object_object_add(logobj, "content", logs);
              json_object_object_add(logobj, "refusal", NULL);
              json_object_object_add(choice, "logprobs", logobj);
              if (stream)
                c->logprob_cursor += count;
            } else
              json_object_object_add(choice, "logprobs", NULL);
          }
        }
        if (c->responses) {
          json_object_object_get_ex(o, "type", &type);
          if (type && lie_json_literal(type, "response.output_text.delta")) {
            json_object_object_add(o, "logprobs",
                                   lie_wire_logprobs(c->job, offset, count));
            c->logprob_cursor += count;
          }
          json_object *target = response  ? response
                                : !stream ? o
                                          : NULL,
                      *output = NULL;
          if (target && json_object_object_get_ex(target, "output", &output))
            for (size_t i = 0; i < json_object_array_length(output); ++i) {
              json_object *item = json_object_array_get_idx(output, i),
                          *parts = NULL;
              if (json_object_object_get_ex(item, "content", &parts))
                for (size_t k = 0; k < json_object_array_length(parts); ++k)
                  json_object_object_add(
                      json_object_array_get_idx(parts, k), "logprobs",
                      lie_wire_logprobs(c->job, 0, info.output_tokens));
            }
        }
      }
      free(raw);
      raw = strdup(json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN));
      json_object_put(o);
    }
    if (!raw) {
      free(owned);
      free(out);
      return NULL;
    }
    size_t n = strlen(raw) + prefix + (stream ? 2 : 0);
    if (n > MAX_RESPONSE - length) {
      free(raw);
      free(owned);
      free(out);
      return NULL;
    }
    if (length + n + 1 > capacity) {
      capacity = length + n + 4096;
      char *next = realloc(out, capacity);
      if (!next) {
        free(raw);
        free(owned);
        free(out);
        return NULL;
      }
      out = next;
    }
    memcpy(out + length, p, prefix);
    length += prefix;
    memcpy(out + length, raw, strlen(raw));
    length += strlen(raw);
    free(raw);
    if (stream) {
      memcpy(out + length, "\n\n", 2);
      length += 2;
    }
    p = stream ? end + 2 : end;
  } while (*p);
  out[length] = 0;
  free(owned);
  return out;
}
static char *wire_join(char *a, char *b) {
  if (!a || !b) {
    free(a);
    free(b);
    return NULL;
  }
  size_t n = strlen(a), m = strlen(b);
  char *out = m <= MAX_RESPONSE - n ? malloc(n + m + 1) : NULL;
  if (out) {
    memcpy(out, a, n);
    memcpy(out + n, b, m + 1);
  }
  free(a);
  free(b);
  return out;
}
static void choice_event(uv_poll_t *poll, int status, int events) {
  choice_output *row = poll->data;
  if (status < 0 || !(events & UV_READABLE)) {
    close_connection(row->parent);
    return;
  }
  connection *c = row->parent;
  unsigned index = (unsigned)(row - c->choice);
  lie_job_event_drain(lie_choices_job(c->choices, index));
  pump_choices(c);
}
static json_object *choices_completion(connection *c) {
  json_object *out = NULL, *choices = json_object_new_array();
  uint64_t tokens = 0;
  unsigned prompt = 0;
  for (unsigned i = 0; i < c->choice_count; ++i) {
    json_object *child = c->choice[i].completion, *list = NULL;
    if (!child || !json_object_object_get_ex(child, "choices", &list)) {
      json_object_put(choices);
      json_object_put(out);
      return NULL;
    }
    if (!out && json_object_deep_copy(child, &out, NULL)) {
      json_object_put(choices);
      return NULL;
    }
    json_object_array_add(choices,
                          json_object_get(json_object_array_get_idx(list, 0)));
    tokens += c->choice[i].info.output_tokens;
    prompt = c->choice[i].info.prompt_tokens;
  }
  json_object_object_add(out, "choices", choices);
  json_object *usage = json_object_new_object();
  json_object_object_add(usage, "prompt_tokens", json_object_new_int64(prompt));
  json_object_object_add(usage, "completion_tokens",
                         json_object_new_uint64(tokens));
  json_object_object_add(usage, "total_tokens",
                         json_object_new_uint64(prompt + tokens));
  json_object_object_add(out, "usage", usage);
  json_object_object_del(out, "lie_timings");
  return out;
}
static void pump_choices(connection *c) {
  if (c->closing || c->writing)
    return;
  if (c->streaming && !c->responded) {
    bool prepared = false;
    for (unsigned i = 0; i < c->choice_count; ++i) {
      lie_job_info info;
      lie_job_snapshot(lie_choices_job(c->choices, i), &info);
      if (info.retired && (info.finish == LIE_FINISH_INVALID ||
                           info.finish == LIE_FINISH_BACKEND)) {
        job_error(c, &info);
        return;
      }
      prepared |= info.prepared;
    }
    if (!prepared)
      return;
    char *intro = strdup("HTTP/1.1 200 OK\r\nContent-Type: text/event-stream; "
                         "charset=utf-8\r\nConnection: close\r\nCache-Control: "
                         "no-store\r\nX-Accel-Buffering: no\r\n\r\n");
    for (unsigned i = 0; i < c->choice_count && intro; ++i)
      intro = wire_join(
          intro,
          lie_wire_reindex(lie_wire_chunk(c->request_id, c->owner->model_id,
                                          c->created, "", 0, true),
                           i, false));
    c->responded = true;
    record_response(c, 200);
    queue_write(c, intro, intro ? strlen(intro) : 0, WRITE_STREAM);
    return;
  }
  for (unsigned scan = 0; scan < c->choice_count; ++scan) {
    unsigned i = (c->choice_cursor + scan) % c->choice_count;
    choice_output *row = &c->choice[i];
    if (row->done)
      continue;
    c->job = lie_choices_job(c->choices, i);
    for (;;) {
      lie_flow_status rc = c->record && i == 0
                               ? lie_record_next(c->record, &c->event)
                               : lie_job_event_next(c->job, &c->event);
      if (rc == LIE_FLOW_WOULD_BLOCK || rc == LIE_FLOW_CLOSED)
        break;
      if (rc != LIE_FLOW_OK) {
        close_connection(c);
        return;
      }
      bool terminal = c->event.kind == LIE_EVENT_TURN_END;
      if (!terminal)
        c->loan = true;
      if (c->event.kind == LIE_EVENT_PROGRESS) {
        release_loan(c);
        continue;
      }
      if (c->event.kind == LIE_EVENT_TOOL_CALL) {
        if (!row->calls)
          row->calls = json_object_new_array();
        json_object *call = lie_output_call_json(c->event.call);
        if (!call || !row->calls) {
          json_object_put(call);
          close_connection(c);
          release_loan(c);
          return;
        }
        json_object_array_add(row->calls, call);
        release_loan(c);
        continue;
      }
      if (c->event.bytes > MAX_TEXT - row->bytes) {
        close_connection(c);
        release_loan(c);
        return;
      }
      if (c->event.bytes)
        memcpy(row->text + row->bytes, c->event.text, c->event.bytes);
      row->bytes += c->event.bytes;
      if (!terminal) {
        if (c->streaming && !c->buffer_tool_turn && c->event.bytes) {
          c->choice_cursor = (i + 1) % c->choice_count;
          c->logprob_cursor = row->logprob_cursor;
          char *chunk = lie_wire_reindex(
              lie_wire_chunk(c->request_id, c->owner->model_id, c->created,
                             c->event.text, c->event.bytes, false),
              i, false);
          queue_write(c, chunk, chunk ? strlen(chunk) : 0, WRITE_STREAM);
          row->logprob_cursor = c->logprob_cursor;
          return;
        }
        release_loan(c);
        continue;
      }
      row->info = c->event.info;
      row->done = true;
      ++c->choice_done;
      if (row->info.finish != LIE_FINISH_STOP &&
          row->info.finish != LIE_FINISH_LENGTH) {
        lie_choices_cancel(c->choices);
        if (!c->streaming)
          job_error(c, &row->info);
        else {
          char *end = lie_wire_end(c->request_id, c->owner->model_id,
                                   c->created, &row->info, false);
          queue_write(c, end, end ? strlen(end) : 0, WRITE_STREAM_END);
        }
        return;
      }
      json_object *message = json_object_new_object();
      json_object_object_add(message, "role",
                             json_object_new_string("assistant"));
      json_object_object_add(
          message, "content",
          row->bytes || !row->calls
              ? json_object_new_string_len(row->text, (int)row->bytes)
              : NULL);
      if (row->calls)
        json_object_object_add(message, "tool_calls",
                               json_object_get(row->calls));
      char *plain = lie_wire_reindex(
          lie_wire_message(c->request_id, c->owner->model_id, c->created,
                           message, &row->info, false, false),
          i, false);
      plain = decorate_wire(c, plain, false);
      row->completion = plain ? json_tokener_parse(plain) : NULL;
      free(plain);
      if (!row->completion) {
        json_object_put(message);
        close_connection(c);
        return;
      }
      bool last = c->choice_done == c->choice_count;
      char *chunk = NULL;
      if (c->streaming) {
        c->logprob_cursor = 0;
        chunk =
            c->buffer_tool_turn
                ? lie_wire_message(c->request_id, c->owner->model_id,
                                   c->created, message, &row->info, true, false)
                : lie_wire_end(c->request_id, c->owner->model_id, c->created,
                               &row->info, false);
        chunk = lie_wire_reindex(chunk, i, false);
      }
      json_object_put(message);
      if (last) {
        json_object *complete = choices_completion(c);
        if (!complete) {
          free(chunk);
          close_connection(c);
          return;
        }
        if (c->stored) {
          size_t charge = strlen(json_object_to_json_string_ext(
                              complete, JSON_C_TO_STRING_PLAIN)) *
                              8 +
                          8192;
          if (!lie_record_charge(c->stored->record, charge)) {
            lie_record_view v;
            lie_record_snapshot(c->stored->record, &v);
            lie_records_delete(c->owner->records, v.id);
            json_object_put(complete);
            free(chunk);
            if (c->streaming) {
              char *failure =
                  strdup("data: "
                         "{\"error\":{\"message\":\"response_store_full\","
                         "\"type\":\"server_error\",\"code\":\"response_store_"
                         "full\"}}\n\ndata: [DONE]\n\n");
              queue_write(c, failure, failure ? strlen(failure) : 0,
                          WRITE_STREAM_END);
            } else
              error_response(c, 429, "response_store_full");
            return;
          }
          c->stored->completion = json_object_get(complete);
        }
        if (!c->streaming) {
          c->logprobs = false;
          char *body = json_text(complete);
          respond(c, 200, "application/json", body);
          free(body);
          return;
        }
        if (c->include_usage) {
          json_object *usage = NULL;
          json_object_object_get_ex(complete, "usage", &usage);
          json_object_object_add(complete, "choices", json_object_new_array());
          json_object_object_add(complete, "usage", json_object_get(usage));
          const char *json =
              json_object_to_json_string_ext(complete, JSON_C_TO_STRING_PLAIN);
          size_t n = strlen(json) + 9;
          char *u = malloc(n);
          if (u)
            snprintf(u, n, "data: %s\n\n", json);
          chunk = wire_join(chunk, u);
        }
        json_object_put(complete);
        chunk = wire_join(chunk, strdup("data: [DONE]\n\n"));
        queue_write(c, chunk, chunk ? strlen(chunk) : 0, WRITE_STREAM_END);
        return;
      }
      if (c->streaming) {
        c->choice_cursor = (i + 1) % c->choice_count;
        queue_write(c, chunk, chunk ? strlen(chunk) : 0, WRITE_STREAM);
        return;
      }
      break;
    }
  }
}
static void job_error(connection *c, const lie_job_info *info) {
    bool invalid=info->finish==LIE_FINISH_INVALID;
    error_detail(c,invalid?400:503,invalid?"invalid_request":"inference_failed",
                 info->error[0]?info->error:"inference_failed");
}
static bool backend_ready(server *s) {
    if (!s->worker || s->stopping) return false;
    lie_worker_info info; lie_worker_snapshot(s->worker,&info);
    return info.state==LIE_READY;
}
static void output_event(uv_poll_t *poll, int status, int events) {
    connection *c=poll->data;
    if (status<0 || !(events&UV_READABLE)) { close_connection(c); return; }
    (void)lie_job_event_drain(c->job);
    pump_job(c);
}
/* Observers replay the C journal. Only the original foreground/background
 * consumer drains the job fd and returns inference credits. */
static void pump_replay(connection *c) {
  if (c->closing || c->writing || !c->record)
    return;
  lie_record_view v;
  lie_record_snapshot(c->record, &v);
  const lie_core_request *input = lie_record_input(c->record);
  for (;;) {
    char *part = NULL;
    bool terminal = false;
    if (!c->replay_started) {
      c->replay_started = true;
      part = lie_response_begin(v.id, c->owner->model_id, v.created,
                                &c->response_sequence, !c->buffer_tool_turn);
    } else if (!c->buffer_tool_turn &&
               c->replay_index < lie_record_event_count(c->record)) {
      if (!lie_record_replay(c->record, c->replay_index++, &c->event)) {
        close_connection(c);
        return;
      }
      if (c->event.kind != LIE_EVENT_TEXT || !c->event.bytes)
        continue;
      part = lie_response_delta(v.id, c->event.text, c->event.bytes,
                                &c->response_sequence);
    } else if (v.done) {
      json_object *calls = record_calls(&v);
      bool valid = v.info.finish == LIE_FINISH_STOP ||
                   v.info.finish == LIE_FINISH_LENGTH;
      part = lie_response_end(v.id, c->owner->model_id, v.created,
                              valid ? v.text : "", valid ? v.bytes : 0,
                              valid ? calls : NULL, &v.info,
                              &c->response_sequence, !c->buffer_tool_turn);
      json_object_put(calls);
      terminal = true;
    } else
      return;
    c->job = lie_record_job(c->record);
    c->logprobs = input->generation.logprobs;
    part = decorate_wire(c, part, true);
    c->job = NULL;
    c->logprobs = false;
    part = lie_response_since(part, c->replay_after);
    if (!part) {
      close_connection(c);
      return;
    }
    if (!c->responded) {
      const char *header =
          "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream; "
          "charset=utf-8\r\nConnection: close\r\nCache-Control: "
          "no-store\r\nX-Accel-Buffering: no\r\n\r\n";
      part = wire_join(strdup(header), part);
      c->responded = true;
      record_response(c, 200);
    }
    if (!*part) {
      free(part);
      if (terminal) {
        close_connection(c);
        return;
      }
      continue;
    }
    queue_write(c, part, strlen(part),
                terminal ? WRITE_STREAM_END : WRITE_STREAM);
    return;
  }
}
static void pump_job(connection *c) {
  if (c->replay) {
    pump_replay(c);
    return;
  }
  if (c->choices) {
    pump_choices(c);
    return;
  }
  if (c->await_cancel && !c->closing && !c->writing) {
    lie_record_view v;
    lie_record_snapshot(c->record, &v);
    if (v.done) {
      stored_request *r = stored_find(c->owner, v.id, true);
      char *body = r ? json_text(stored_object(r)) : NULL;
      respond(c, body ? 200 : 404, "application/json", body);
      free(body);
    }
    return;
  }
  if (c->closing || c->writing || !c->job)
    return;
  lie_job_info info;
  lie_job_snapshot(c->job, &info);
  if (!c->responded && info.retired &&
      (info.finish == LIE_FINISH_BACKEND ||
       info.finish == LIE_FINISH_INVALID)) {
    job_error(c, &info);
    return;
  }
  if (c->streaming && !c->responded && info.prepared) {
    const char *header = "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream; "
                         "charset=utf-8\r\nConnection: close\r\nCache-Control: "
                         "no-store\r\nX-Content-Type-Options: "
                         "nosniff\r\nX-Accel-Buffering: no\r\n\r\n";
    char *intro =
        c->responses
            ? lie_response_begin(c->request_id, c->owner->model_id, c->created,
                                 &c->response_sequence, !c->buffer_tool_turn)
            : lie_wire_chunk(c->request_id, c->owner->model_id, c->created, "",
                             0, true);
    intro = decorate_wire(c, intro, true);
    if (!intro) {
      close_connection(c);
      return;
    }
    size_t n = strlen(header) + strlen(intro);
    char *body = malloc(n + 1);
    if (body)
      snprintf(body, n + 1, "%s%s", header, intro);
    free(intro);
    c->responded = true;
    record_response(c, 200);
    queue_write(c, body, n, WRITE_STREAM);
    return;
  }
  if (c->streaming && !c->responded)
    return;
  for (;;) {
    lie_flow_status status = c->record ? lie_record_next(c->record, &c->event)
                                       : lie_job_event_next(c->job, &c->event);
    if (status == LIE_FLOW_WOULD_BLOCK || status == LIE_FLOW_CLOSED)
      return;
    if (status != LIE_FLOW_OK) {
      close_connection(c);
      return;
    }
    bool terminal = c->event.kind == LIE_EVENT_TURN_END;
    if (!terminal)
      c->loan = true;
    if (c->event.kind == LIE_EVENT_PROGRESS) {
      release_loan(c);
      continue;
    }
    if (c->event.kind == LIE_EVENT_TOOL_CALL) {
      json_object *call = lie_output_call_json(c->event.call);
      if (!c->calls)
        c->calls = json_object_new_array();
      if (!call || !c->calls) {
        json_object_put(call);
        close_connection(c);
        release_loan(c);
        return;
      }
      json_object_array_add(c->calls, call);
      release_loan(c);
      continue;
    }
    const char *text = c->event.text;
    size_t bytes = c->event.bytes;
    if (terminal)
      info = c->event.info;
    if (!c->streaming || c->buffer_tool_turn || c->responses) {
      if (bytes > MAX_TEXT - c->text_bytes) {
        close_connection(c);
        release_loan(c);
        return;
      }
      if (bytes)
        memcpy(c->text + c->text_bytes, text, bytes);
      c->text_bytes += bytes;
      if (!terminal) {
        if (c->responses && c->streaming && !c->buffer_tool_turn && bytes) {
          char *chunk = lie_response_delta(c->request_id, text, bytes,
                                           &c->response_sequence);
          queue_write(c, chunk, chunk ? strlen(chunk) : 0, WRITE_STREAM);
          return;
        }
        release_loan(c);
        continue;
      }
      bool finished =
          info.finish == LIE_FINISH_STOP || info.finish == LIE_FINISH_LENGTH;
      if (!finished) {
        if (info.output_invalid)
          (void)lie_counter_add(c->owner->metrics, c->owner->tool_errors, 1);
        if (!c->streaming) {
          if (info.output_invalid)
            error_detail(c, 502, "invalid_tool_output", info.error);
          else
            job_error(c, &info);
        } else {
          char *end = c->responses
                          ? lie_response_end(c->request_id, c->owner->model_id,
                                             c->created, "", 0, NULL, &info,
                                             &c->response_sequence, false)
                          : lie_wire_end(c->request_id, c->owner->model_id,
                                         c->created, &info, false);
          queue_write(c, end, end ? strlen(end) : 0, WRITE_STREAM_END);
        }
        return;
      }
      if (c->buffer_tool_turn) {
        json_object *message = json_object_new_object();
        if (!message) {
          close_connection(c);
          return;
        }
        json_object_object_add(message, "role",
                               json_object_new_string("assistant"));
        json_object_object_add(
            message, "content",
            c->text_bytes || !c->calls
                ? json_object_new_string_len(c->text, (int)c->text_bytes)
                : NULL);
        if (c->calls)
          json_object_object_add(message, "tool_calls",
                                 json_object_get(c->calls));
        char *response =
            c->responses
                ? (c->streaming
                       ? lie_response_end(c->request_id, c->owner->model_id,
                                          c->created, c->text, c->text_bytes,
                                          c->calls, &info,
                                          &c->response_sequence, false)
                       : json_text(lie_response_object(
                             c->request_id, c->owner->model_id, c->created,
                             c->text, c->text_bytes, c->calls, &info)))
                : lie_wire_message(c->request_id, c->owner->model_id,
                                   c->created, message, &info, c->streaming,
                                   c->include_usage);
        json_object_put(message);
        if (c->streaming)
          queue_write(c, response, response ? strlen(response) : 0,
                      WRITE_STREAM_END);
        else {
          respond(c, 200, "application/json", response);
          free(response);
        }
        return;
      }
      if (c->responses && c->streaming) {
        char *end = lie_response_end(c->request_id, c->owner->model_id,
                                     c->created, c->text, c->text_bytes, NULL,
                                     &info, &c->response_sequence, true);
        queue_write(c, end, end ? strlen(end) : 0, WRITE_STREAM_END);
        return;
      }
      char *response =
          c->responses
              ? json_text(lie_response_object(c->request_id, c->owner->model_id,
                                              c->created, c->text,
                                              c->text_bytes, NULL, &info))
              : lie_wire_completion(c->request_id, c->owner->model_id,
                                    c->created, c->text, c->text_bytes, &info);
      respond(c, 200, "application/json", response);
      free(response);
      return;
    }
    if (!terminal) {
      if (!bytes) {
        release_loan(c);
        continue;
      }
      char *chunk = lie_wire_chunk(c->request_id, c->owner->model_id,
                                   c->created, text, bytes, false);
      queue_write(c, chunk, chunk ? strlen(chunk) : 0, WRITE_STREAM);
      return;
    }
    char *end = lie_wire_end(c->request_id, c->owner->model_id, c->created,
                             &info, c->include_usage);
    queue_write(c, end, end ? strlen(end) : 0, WRITE_STREAM_END);
    return;
  }
}
static void submit_chat(connection *c) {
  server *s = c->owner;
  if (!backend_ready(s)) {
    lie_counter_add(s->metrics, s->rejected, 1);
    error_response(c, 503, "backend_unavailable");
    return;
  }
  lie_core_request history = {0};
  void *history_storage = NULL;
  if (c->responses) {
    bool valid = false;
    json_object *root = lie_json_parse(c->body, c->body_size, &valid),
                *previous = NULL;
    if (valid &&
        json_object_object_get_ex(root, "previous_response_id", &previous) &&
        previous) {
      if (!lie_json_text(previous)) {
        json_object_put(root);
        error_response(c, 400, "invalid_previous_response_id");
        return;
      }
      stored_request *prior =
          stored_find(s, json_object_get_string(previous), true);
      if (!prior ||
          !lie_record_history(prior->record, &history, &history_storage)) {
        json_object_put(root);
        error_response(c, 400, "previous_response_unavailable");
        return;
      }
    }
    json_object_put(root);
  }
  lie_chat_request request;
  char error[256];
  bool parsed =
      c->responses
          ? lie_responses_parse_history(c->body, c->body_size, s->model_id,
                                        history_storage ? &history : NULL,
                                        &request, error)
          : lie_chat_parse(c->body, c->body_size, s->model_id, &request, error);
  free(history_storage);
  if (!parsed) {
    lie_counter_add(s->metrics, s->rejected_invalid, 1);
    error_response(c, 400, error);
    return;
  }
  c->streaming = request.stream;
  c->include_usage = request.include_usage;
  c->logprobs = request.generation.logprobs != 0;
  c->wire_options = stored_options(&request, c->responses);
  if (c->wire_options && !json_object_object_length(c->wire_options)) {
    json_object_put(c->wire_options);
    c->wire_options = NULL;
  }
  c->buffer_tool_turn = request.tool_count != 0 ||
                        request.tool_choice != LIE_TOOLS_AUTO ||
                        (c->logprobs && request.stop_count);
  c->choice_count = request.choices;
  if (!c->streaming || c->buffer_tool_turn || c->responses) {
    c->text = malloc(MAX_TEXT);
    if (!c->text) {
      lie_chat_free(&request);
      error_response(c, 500, "allocation_failed");
      return;
    }
  }
  snprintf(c->request_id, sizeof(c->request_id), "%s%s-%llu",
           c->responses ? "resp_" : "chatcmpl-", s->instance,
           (unsigned long long)++s->request_counter);
  c->created = (int64_t)time(NULL);
  lie_core_request input;
  lie_chat_core_request(&request, &input);
  stored_request *stored = NULL;
  if (request.store || request.background) {
    stored = calloc(1, sizeof(*stored));
    json_object *source = NULL, *instructions = NULL;
    if (c->responses) {
      json_object_object_get_ex(request.json_owner, "lie_response", &source);
      json_object_object_get_ex(source, "instructions", &instructions);
    }
    lie_record *record =
        stored
            ? lie_records_insert(s->records, c->request_id, c->created, &input,
                                 instructions ? 1 : 0, request.background)
            : NULL;
    if (!record) {
      free(stored);
      lie_chat_free(&request);
      error_response(c, 429, "response_store_full");
      return;
    }
    stored->started = lie_monotonic_ns();
    stored->owner = s;
    stored->record = record;
    stored->responses = c->responses;
    stored->store = request.store;
    stored->background = request.background;
    stored->options = stored_options(&request, c->responses);
    size_t options_charge =
        stored->options ? strlen(json_object_to_json_string_ext(
                              stored->options, JSON_C_TO_STRING_PLAIN)) *
                                  8 +
                              8192
                        : 0;
    if (!stored->options || !lie_record_charge(record, options_charge)) {
      lie_records_delete(s->records, c->request_id);
      lie_record_release(record);
      json_object_put(stored->options);
      free(stored);
      lie_chat_free(&request);
      error_response(c, 429, "response_store_full");
      return;
    }
    stored->foreground = c;
    stored->next = s->stored;
    s->stored = stored;
    c->stored = stored;
    c->record = lie_records_get(s->records, c->request_id, c->created);
  }
  int result = c->choice_count > 1
                   ? lie_core_submit_choices(s->worker, &input, c->choice_count,
                                             &c->choices)
                   : lie_core_submit(s->worker, &input, &c->job);
  lie_chat_free(&request);
  if (!result && c->choices)
    c->job = lie_choices_job(c->choices, 0);
  if (result) {
    if (stored) {
      lie_records_delete(s->records, c->request_id);
      stored_dispose(stored);
      c->stored = NULL;
      lie_record_release(c->record);
      c->record = NULL;
    }
    lie_counter_add(s->metrics,
                    result == 2 ? s->rejected_capacity : s->rejected, 1);
    error_response(c,
                   result == 2   ? 429
                   : result == 3 ? 400
                                 : 503,
                   result == 2   ? "queue_full"
                   : result == 3 ? "invalid_request"
                                 : "backend_unavailable");
    return;
  }
  if (stored) {
    if (c->choices)
      lie_job_retain(c->job);
    if (!lie_record_attach(stored->record, c->job)) {
      if (c->choices)
        lie_job_release(c->job);
      lie_job_cancel(c->job);
      if (c->choices) {
        lie_choices_cancel(c->choices);
        lie_choices_release(c->choices);
        c->choices = NULL;
      } else
        lie_job_release(c->job);
      c->job = NULL;
      lie_records_delete(s->records, c->request_id);
      stored_dispose(stored);
      c->stored = NULL;
      lie_record_release(c->record);
      c->record = NULL;
      error_response(c, 429, "response_store_full");
      return;
    }
  }
  if (c->choices) {
    free(c->text);
    c->text = NULL;
    for (unsigned i = 0; i < c->choice_count; ++i) {
      choice_output *row = &c->choice[i];
      row->parent = c;
      row->text = malloc(MAX_TEXT);
      if (!row->text ||
          uv_poll_init(&s->loop, &row->poll,
                       lie_job_event_fd(lie_choices_job(c->choices, i)))) {
        close_connection(c);
        return;
      }
      row->initialized = true;
      row->poll.data = row;
      ++c->handles;
      if (uv_poll_start(&row->poll, UV_READABLE, choice_event)) {
        close_connection(c);
        return;
      }
    }
    pump_choices(c);
    return;
  }
  if (stored && stored->background && !c->streaming) {
    stored->foreground = NULL;
    if (!stored_start(stored)) {
      error_response(c, 500, "background_unavailable");
      return;
    }
    c->job = NULL;
    char *body = json_text(stored_object(stored));
    respond(c, 200, "application/json", body);
    free(body);
    return;
  }
  if (uv_poll_init(&s->loop, &c->output_poll, lie_job_event_fd(c->job))) {
    close_connection(c);
    return;
  }
  c->output_poll.data = c;
  c->poll_initialized = true;
  ++c->handles;
  if (uv_poll_start(&c->output_poll, UV_READABLE, output_event)) {
    close_connection(c);
    return;
  }
  pump_job(c);
}
static int hex(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}
static bool decode_component(char *s) {
    char *to = s;
    for (char *p = s; *p; ++p) {
        if (*p == '%') {
            if (!p[1] || !p[2] || hex(p[1]) < 0 || hex(p[2]) < 0) return false;
            char ch = (char)((hex(p[1]) << 4) | hex(p[2]));
            if (!ch || (unsigned char)ch < 32 || ch == 127) return false;
            *to++ = ch; p += 2;
        } else { if ((unsigned char)*p < 32) return false; *to++ = *p == '+' ? ' ' : *p; }
    }
    *to = 0; return true;
}
static bool query_tags(char *query, lie_tag *filters, size_t *count) {
    *count = 0;
    if (!query) return true;
    if (!*query) return false;
    char *p = query;
    while (p) {
        char *end = strchr(p, '&'); if (end) *end++ = 0;
        if (strncmp(p, "tag=", 4) || *count == LIE_MAX_TAGS || !decode_component(p + 4)) return false;
        char *colon = strchr(p + 4, ':'); if (!colon || colon == p + 4) return false;
        *colon = 0; filters[*count] = (lie_tag){p + 4, colon + 1}; ++*count;
        p = end;
    }
    return true;
}
static char *discovery(void) {
    const char *names[] = {"self", "health", "liveness", "readiness", "info", "metrics", "metrics-requiredMetricName", "prometheus", "llm", "monitor"};
    const char *paths[] = {"/actuator", "/actuator/health", "/actuator/health/liveness", "/actuator/health/readiness", "/actuator/info", "/actuator/metrics", "/actuator/metrics/{requiredMetricName}", "/actuator/prometheus", "/actuator/llm", "/monitor"};
    json_object *j = json_object_new_object(), *links = json_object_new_object();
    for (size_t i = 0; i < sizeof(names) / sizeof(*names); ++i) {
        json_object *link = json_object_new_object();
        json_object_object_add(link, "href", json_object_new_string(paths[i]));
        json_object_object_add(link, "templated", json_object_new_boolean(i == 6));
        json_object_object_add(links, names[i], link);
    }
    json_object_object_add(j, "_links", links); return json_text(j);
}
static const char PAGE[] =
    "<!doctype html><html lang=en-US><meta charset=utf-8><title>Synapse "
    "LIE</title>"
    "<style>body{font:16px "
    "monospace;background:#171b24;color:#d8e6ef;margin:2em}pre{white-space:pre-"
    "wrap}</style>"
    "<h1>Synapse LIE: development diagnostics</h1><p id=status>No inference "
    "backend connected. Unknown is not zero.</p>"
    "<pre id=view>Connecting...</pre><script>const history=[];async function "
    "poll(){try{"
    "const r=await fetch('/actuator/llm');if(!r.ok)throw Error('HTTP "
    "'+r.status);const s=await r.json();"
    "document.getElementById('status').textContent=s.ready?'Model loaded. See "
    "engine ownership and capability limits below.':'No inference backend "
    "connected. Unknown is not zero.';"
    "history.push({at:new "
    "Date().toISOString(),state:s});if(history.length>30)history.shift();"
    "document.getElementById('view').textContent=JSON.stringify(history["
    "history.length-1],null,2);"
    "}catch(e){document.getElementById('view').textContent='Unavailable: "
    "'+e.message;}setTimeout(poll,2000);}poll();</script></html>";
static const char *worker_state(lie_worker_state state) {
    switch (state) {
        case LIE_LOADING:return "LOADING"; case LIE_READY:return "READY";
        case LIE_FAILED:return "FAILED"; case LIE_STOPPING:return "STOPPING";
        case LIE_STOPPED:return "STOPPED";
    }
    return "UNKNOWN";
}
static json_object *backend_json(server *s) {
    if (!s->worker) return NULL;
    lie_worker_info info; lie_worker_snapshot(s->worker,&info);
    json_object *b=json_object_new_object();
    json_object_object_add(b,"engine",json_object_new_string(lie_backend_name()));
    json_object_object_add(b,"source_pin",json_object_new_string(lie_backend_source_pin()));
    json_object_object_add(b,"build_id",json_object_new_string(LIE_BUILD_ID));
    json_object_object_add(b,"ownership",json_object_new_string(lie_backend_ownership()));
    json_object_object_add(b,"dense_sampling",json_object_new_string(lie_backend_dense_sampling()));
    json_object_object_add(b,"state",json_object_new_string(worker_state(info.state)));
    json_object_object_add(b,"model",json_object_new_string(s->model_id));
    json_object_object_add(b,"synthetic",json_object_new_boolean(lie_backend_is_synthetic()));
    json_object_object_add(b,"hardware_qualified",json_object_new_boolean(false));
    json_object_object_add(b,"native_batching",json_object_new_boolean(info.model.native_batch_capacity>1));
    json_object_object_add(b,"native_batch_capacity",json_object_new_int64(info.model.native_batch_capacity));
    json_object_object_add(b,"tools",json_object_new_boolean(true));
    json_object_object_add(b,"tool_streaming",json_object_new_string("buffered-complete-turn"));
    json_object_object_add(b,"context_tokens",json_object_new_int64(info.model.context_tokens));
    json_object_object_add(b,"rope_scaling",json_object_new_string(lie_rope_profile_name(info.rope_profile)));
    json_object_object_add(b,"max_output_tokens",json_object_new_int64(LIE_CHAT_MAX_OUTPUT));
    json_object_object_add(b,"max_request_bytes",json_object_new_int64(LIE_CHAT_BODY_BYTES));
    json_object_object_add(b,"max_messages",json_object_new_int64(LIE_CHAT_MAX_MESSAGES));
    json_object_object_add(b,"vision",json_object_new_boolean(info.vision.max_images!=0));
    json_object_object_add(b,"max_images",json_object_new_int64(info.vision.max_images));
    json_object_object_add(b,"mtp",json_object_new_boolean(info.model.speculative_supported!=0));
    json_object_object_add(b,"max_decode_output_tokens",json_object_new_int64(info.model.speculative_supported?info.mtp.max_output_tokens:1));
    json_object_object_add(b,"snapshot_restore",json_object_new_boolean(false));
    json_object_object_add(b,"prefix_state",json_object_new_boolean(lie_backend_prefix_state_supported()&&(!info.model.speculative_supported||info.mtp.prefix_state_supported)&&(!info.vision.max_images||info.vision.prefix_state_supported)));
    json_object_object_add(b,"state_format",json_object_new_string(lie_backend_state_format()));
    json_object_object_add(b,"error",info.error[0]?json_object_new_string(info.error):NULL);
    return b;
}
static json_object *executor_json(const lie_worker_info *i) {
    json_object *o=json_object_new_object();
    json_object_object_add(o,"scope",json_object_new_string("owner_dispatch_intervals"));
    json_object_object_add(o,"phase",json_object_new_string(i->executor_phase==LIE_EXECUTOR_PREFILL?"prefill":
                                                         i->executor_phase==LIE_EXECUTOR_DECODE?"decode":
                                                         i->executor_phase==LIE_EXECUTOR_CAPTURE?"capture":
                                                         i->executor_phase==LIE_EXECUTOR_RESTORE?"restore":"none"));
    json_object_object_add(o,"prefill_started",json_object_new_uint64(i->prefill_started));
    json_object_object_add(o,"prefill_returned",json_object_new_uint64(i->prefill_returned));
    json_object_object_add(o,"decode_started",json_object_new_uint64(i->decode_started));
    json_object_object_add(o,"decode_returned",json_object_new_uint64(i->decode_returned));
    json_object_object_add(o,"mtp_drafted_tokens",json_object_new_uint64(i->mtp_drafted));
    json_object_object_add(o,"mtp_accepted_tokens",json_object_new_uint64(i->mtp_accepted));
    json_object_object_add(o,"decode_batches",json_object_new_uint64(i->decode_batches));
    json_object_object_add(o,"decode_batch_rows",json_object_new_uint64(i->decode_batch_rows));
    json_object_object_add(o,"decode_single_calls",json_object_new_uint64(i->decode_single_calls));
    json_object_object_add(o,"cancel_during_prefill",json_object_new_uint64(i->cancel_during_prefill));
    json_object_object_add(o,"cancel_during_decode",json_object_new_uint64(i->cancel_during_decode));
    return o;
}
static json_object *prefix_cache_json(const lie_prefix_cache_info *i,const lie_store_info *ssd,const lie_cache_policy *p) {
    json_object *o=json_object_new_object();
    json_object_object_add(o,"kind",json_object_new_string("ram-prefix-checkpoints"));
    json_object_object_add(o,"enabled",json_object_new_boolean(i->budget_bytes!=0));
    json_object_object_add(o,"ssd_enabled",json_object_new_boolean(ssd->enabled));
    json_object_object_add(o,"retention_policy",json_object_new_string(i->utility_policy?"ds4-time-token-byte-utility-v1":"lru"));
    json_object_object_add(o,"checkpoint_compression",json_object_new_boolean(i->compression_enabled));
    json_object_object_add(o,"checkpoint_codec",json_object_new_string(lie_state_compression_codec()));
    json_object *policy=json_object_new_object();
    json_object_object_add(policy,"kind",json_object_new_string(p->enabled?"ds4":"legacy"));
    json_object_object_add(policy,"text_prefix",json_object_new_boolean(p->text_prefix));
    json_object_object_add(policy,"capture_finish",json_object_new_boolean(p->capture_finish));
#define POLICY_FIELD(name) json_object_object_add(policy,#name,json_object_new_uint64(p->name))
    POLICY_FIELD(min_tokens);POLICY_FIELD(cold_max_tokens);POLICY_FIELD(continued_interval_tokens);
    POLICY_FIELD(boundary_trim_tokens);POLICY_FIELD(boundary_align_tokens);
#undef POLICY_FIELD
    json_object_object_add(o,"checkpoint_policy",policy);
    json_object *disk=json_object_new_object();
    json_object_object_add(disk,"enabled",json_object_new_boolean(ssd->enabled));
    json_object_object_add(disk,"retention_policy",json_object_new_string(ssd->utility_policy?"ds4-time-token-byte-utility-v1":"lru"));
    json_object_object_add(disk,"checkpoint_compression",json_object_new_boolean(ssd->compression_enabled));
    json_object_object_add(disk,"checkpoint_codec",json_object_new_string(lie_state_compression_codec()));
#define SSD_FIELD(name) json_object_object_add(disk,#name,json_object_new_uint64(ssd->name))
    SSD_FIELD(quota_bytes);SSD_FIELD(disk_bytes);SSD_FIELD(allocated_bytes);SSD_FIELD(staging_budget_bytes);
    SSD_FIELD(index_bytes);SSD_FIELD(index_budget_bytes);
    SSD_FIELD(staging_bytes);SSD_FIELD(peak_staging_bytes);SSD_FIELD(entries);SSD_FIELD(pending);
    SSD_FIELD(lookups);SSD_FIELD(hits);SSD_FIELD(misses);SSD_FIELD(writes);SSD_FIELD(evictions);SSD_FIELD(skipped);
    SSD_FIELD(errors);SSD_FIELD(cancelled);SSD_FIELD(read_bytes);SSD_FIELD(written_bytes);SSD_FIELD(read_ns);SSD_FIELD(write_ns);
#undef SSD_FIELD
    json_object_object_add(o,"ssd",disk);
    json_object_object_add(o,"accounting",json_object_new_string("payload, descriptors and metadata; index separately bounded; excludes allocator/driver overhead"));
#define CACHE_FIELD(name) json_object_object_add(o,#name,json_object_new_uint64(i->name))
    CACHE_FIELD(budget_bytes);CACHE_FIELD(retained_bytes);CACHE_FIELD(peak_retained_bytes);
    CACHE_FIELD(index_bytes);CACHE_FIELD(index_budget_bytes);
    CACHE_FIELD(lookups);CACHE_FIELD(hits);CACHE_FIELD(misses);CACHE_FIELD(reused_tokens);
    CACHE_FIELD(captures);CACHE_FIELD(evictions);CACHE_FIELD(skipped);CACHE_FIELD(entries);
    CACHE_FIELD(expanded_bytes);CACHE_FIELD(compression_attempts);CACHE_FIELD(compressed_captures);
#undef CACHE_FIELD
    return o;
}
static char *llm_json(server *s) {
    json_object *j=json_object_new_object();
    json_object_object_add(j,"schema",json_object_new_string("synapse-lie.llm.v1"));
    json_object_object_add(j,"ready",json_object_new_boolean(backend_ready(s)));
    json_object_object_add(j,"backend",backend_json(s));
    json_object *scheduler=NULL;
    if (s->worker) {
        lie_worker_info info; lie_worker_snapshot(s->worker,&info);
        json_object_object_add(j,"cache",prefix_cache_json(&info.cache,&info.ssd,&info.cache_policy));
        scheduler=json_object_new_object();
        json_object_object_add(scheduler,"mode",json_object_new_string("single-owner-reactive-ready-batch"));
        json_object_object_add(scheduler,"queued",json_object_new_int(info.queued));
        json_object_object_add(scheduler,"active",json_object_new_int(info.active));
        json_object_object_add(scheduler,"output_blocked",json_object_new_int(info.output_blocked));
        json_object_object_add(scheduler,"executor",executor_json(&info));
        json_object_object_add(scheduler,"max_active",json_object_new_int(s->max_active));
        json_object_object_add(scheduler,"admission_capacity",json_object_new_int(LIE_WORKER_JOBS));
        json_object_object_add(scheduler,"generated_tokens",json_object_new_uint64(info.generated_tokens));
        json_object_object_add(scheduler,"completed",json_object_new_uint64(info.completed_requests));
        json_object_object_add(scheduler,"cancelled",json_object_new_uint64(info.cancelled_requests));
        json_object_object_add(scheduler,"failed",json_object_new_uint64(info.failed_requests));
        json_object_object_add(scheduler,"output_validation_errors",json_object_new_uint64(info.output_validation_errors));
    }
    json_object_object_add(j,"scheduler",scheduler);
    if(!s->worker)json_object_object_add(j,"cache",NULL);
    const char *unknown[]={"memory","speculation","throughput","latency"};
    for (size_t i=0;i<sizeof(unknown)/sizeof(*unknown);++i) json_object_object_add(j,unknown[i],NULL);
    return json_text(j);
}
static void route(connection *c) {
  server *s = c->owner;
  char *query = strchr(c->url, '?');
  if (query)
    *query++ = 0;
  if (!c->management) {
    if (!strcmp(c->url, "/v1/models") && c->parser.method == HTTP_GET &&
        !query) {
      json_object *j = json_object_new_object(),
                  *data = json_object_new_array();
      json_object_object_add(j, "object", json_object_new_string("list"));
      if (backend_ready(s)) {
        json_object *m = json_object_new_object();
        json_object_object_add(m, "id", json_object_new_string(s->model_id));
        json_object_object_add(m, "object", json_object_new_string("model"));
        json_object_object_add(m, "owned_by",
                               json_object_new_string(lie_backend_name()));
        json_object_array_add(data, m);
      }
      json_object_object_add(j, "data", data);
      char *body = json_text(j);
      respond(c, 200, "application/json", body);
      free(body);
      return;
    }
    if (!strcmp(c->url, "/v1/chat/completions") &&
        c->parser.method == HTTP_POST && !query) {
      submit_chat(c);
      return;
    }
    if (!strcmp(c->url, "/v1/responses") && c->parser.method == HTTP_POST &&
        !query) {
      c->responses = true;
      submit_chat(c);
      return;
    }
    const char *prefix = NULL;
    bool responses = false;
    if (!strncmp(c->url, "/v1/responses/", 14)) {
      prefix = c->url + 14;
      responses = true;
    } else if (!strncmp(c->url, "/v1/chat/completions/", 21))
      prefix = c->url + 21;
    if (prefix) {
      char id[129];
      size_t n = strcspn(prefix, "/");
      if (!n || n >= sizeof(id)) {
        error_response(c, 404, "not_found");
        return;
      }
      memcpy(id, prefix, n);
      id[n] = 0;
      if (!decode_component(id)) {
        error_response(c, 400, "invalid_id");
        return;
      }
      stored_request *r = stored_find(s, id, responses);
      if (!r) {
        error_response(c, 404, "response_not_found");
        return;
      }
      const char *tail = prefix + n;
      if (!*tail && c->parser.method == HTTP_GET && (responses || !query)) {
        bool stream = false;
        int64_t after = -1;
        if (responses && !lie_response_retrieve_query(query, &stream, &after)) {
          error_response(c, 400, "invalid_retrieve_query");
          return;
        }
        if (stream) {
          c->record = lie_records_get(s->records, id, (int64_t)time(NULL));
          c->replay = true;
          c->responses = true;
          c->streaming = true;
          c->replay_after = after;
          lie_record_view v;
          lie_record_snapshot(c->record, &v);
          if (n >= sizeof(c->request_id)) {
            error_response(c, 400, "invalid_id");
            return;
          }
          memcpy(c->request_id, id, strlen(id) + 1);
          c->created = v.created;
          const lie_core_request *input = lie_record_input(c->record);
          c->buffer_tool_turn =
              input->chat.tool_count || input->tool_choice != LIE_TOOLS_AUTO ||
              (input->stop_count && input->generation.logprobs);
          c->wire_options = json_object_get(r->options);
          json_object_object_add(c->wire_options, "store",
                                 json_object_new_boolean(r->store));
          json_object_object_add(c->wire_options, "background",
                                 json_object_new_boolean(r->background));
          pump_replay(c);
          return;
        }
        char *body = json_text(stored_object(r));
        respond(c, body ? 200 : 409, "application/json", body);
        free(body);
        return;
      }
      if (!*tail && c->parser.method == HTTP_DELETE && !query) {
        lie_records_delete(s->records, id);
        json_object *j = json_object_new_object();
        json_object_object_add(j, "id", json_object_new_string(id));
        json_object_object_add(
            j, "object",
            json_object_new_string(responses ? "response.deleted"
                                             : "chat.completion.deleted"));
        json_object_object_add(j, "deleted", json_object_new_boolean(true));
        char *body = json_text(j);
        respond(c, 200, "application/json", body);
        free(body);
        return;
      }
      if (responses && !strcmp(tail, "/cancel") &&
          c->parser.method == HTTP_POST && !query) {
        if (!lie_record_cancel(r->record)) {
          error_response(c, 400, "response_not_background");
          return;
        }
        c->record = lie_records_get(s->records, id, (int64_t)time(NULL));
        c->await_cancel = true;
        lie_record_pump(r->record);
        pump_job(c);
        return;
      }
      if (((responses && !strcmp(tail, "/input_items")) ||
           (!responses && !strcmp(tail, "/messages"))) &&
          c->parser.method == HTTP_GET) {
        json_object *instructions = NULL;
        json_object_object_get_ex(r->options, "instructions", &instructions);
        json_object *items =
            responses ? lie_response_input_items(lie_record_input(r->record),
                                                 instructions ? 1 : 0)
                      : lie_chat_history_json(lie_record_input(r->record));
        if (!items) {
          error_response(c, 500, "history_unavailable");
          return;
        }
        if (!responses) {
          json_object *response = stored_object(r), *choices = NULL,
                      *choice = NULL, *message = NULL;
          if (json_object_object_get_ex(response, "choices", &choices) &&
              (choice = json_object_array_get_idx(choices, 0)) &&
              json_object_object_get_ex(choice, "message", &message))
            json_object_array_add(items, json_object_get(message));
          json_object_put(response);
        }
        for (size_t i = 0; i < json_object_array_length(items); ++i) {
          json_object *item = json_object_array_get_idx(items, i);
          char item_id[180];
          snprintf(item_id, sizeof(item_id), "msg_%s_%zu", id, i);
          json_object_object_add(item, "id", json_object_new_string(item_id));
        }
        char page_error[256];
        json_object *j = lie_wire_page(items, query, !responses, page_error);
        json_object_put(items);
        if (!j) {
          error_response(c, 400, page_error);
          return;
        }
        char *body = json_text(j);
        respond(c, 200, "application/json", body);
        free(body);
        return;
      }
      if (!responses && !*tail && c->parser.method == HTTP_POST && !query) {
        bool valid = false;
        json_object *j = lie_json_parse(c->body, c->body_size, &valid),
                    *metadata = NULL;
        if (!valid || !json_object_is_type(j, json_type_object) ||
            json_object_object_length(j) != 1 ||
            !json_object_object_get_ex(j, "metadata", &metadata) ||
            !json_object_is_type(metadata, json_type_object) ||
            json_object_object_length(metadata) > 16) {
          json_object_put(j);
          error_response(c, 400, "invalid_metadata");
          return;
        }
        bool ok = true;
        json_object_object_foreach(metadata, k, v) {
          if (strlen(k) > 64 || !lie_json_text(v) ||
              json_object_get_string_len(v) > 512)
            ok = false;
        }
        if (!ok) {
          json_object_put(j);
          error_response(c, 400, "invalid_metadata");
          return;
        }
        json_object_object_add(r->options, "metadata",
                               json_object_get(metadata));
        json_object_put(j);
        char *body = json_text(stored_object(r));
        respond(c, 200, "application/json", body);
        free(body);
        return;
      }
      error_response(c, 405, "method_not_allowed");
      return;
    }
    if (!strcmp(c->url, "/v1/chat/completions") &&
        c->parser.method == HTTP_GET) {
      json_object *items = json_object_new_array();
      for (stored_request *r = s->stored; r; r = r->next)
        if (!r->responses) {
          lie_record_view v;
          lie_record_snapshot(r->record, &v);
          if (stored_find(s, v.id, false)) {
            json_object *o = stored_object(r);
            if (o)
              json_object_array_add(items, o);
          }
        }
      json_object *ordered = json_object_new_array();
      size_t count = json_object_array_length(items);
      for (size_t i = 0; i < count; ++i)
        json_object_array_add(
            ordered,
            json_object_get(json_object_array_get_idx(items, count - i - 1)));
      json_object_put(items);
      char page_error[256];
      json_object *j = lie_wire_page(ordered, query, true, page_error);
      json_object_put(ordered);
      if (!j) {
        error_response(c, 400, page_error);
        return;
      }
      char *body = json_text(j);
      respond(c, 200, "application/json", body);
      free(body);
      return;
    }
    if (!strncmp(c->url, "/v1/models/", 11) && c->parser.method == HTTP_GET &&
        !query) {
      if (!decode_component(c->url + 11) || strcmp(c->url + 11, s->model_id) ||
          !backend_ready(s)) {
        error_response(c, 404, "model_not_found");
        return;
      }
      json_object *m = json_object_new_object();
      json_object_object_add(m, "id", json_object_new_string(s->model_id));
      json_object_object_add(m, "object", json_object_new_string("model"));
      json_object_object_add(m, "created", json_object_new_int64(0));
      json_object_object_add(m, "owned_by",
                             json_object_new_string(lie_backend_name()));
      char *body = json_text(m);
      respond(c, 200, "application/json", body);
      free(body);
      return;
    }
    error_response(c, 404, "not_found");
    return;
  }
  if (c->parser.method != HTTP_GET) {
    error_response(c, 405, "method_not_allowed");
    return;
  }
  char *body = NULL;
  if (!strncmp(c->url, "/actuator/metrics/", 18)) {
    lie_tag filters[LIE_MAX_TAGS];
    size_t count;
    if (!decode_component(c->url + 18) || !query_tags(query, filters, &count)) {
      error_response(c, 400, "invalid_filter");
      return;
    }
    lie_metric_status st =
        lie_metrics_detail(s->metrics, c->url + 18, filters, count, &body);
    if (st != LIE_METRIC_OK) {
      error_response(c,
                     st == LIE_METRIC_NOT_FOUND ? 404
                     : st == LIE_METRIC_INVALID ? 400
                                                : 500,
                     "metric_unavailable");
      return;
    }
  } else {
    if (query) {
      error_response(c, 400, "unexpected_query");
      return;
    }
    if (!strcmp(c->url, "/actuator"))
      body = discovery();
    else if (!strcmp(c->url, "/actuator/metrics"))
      body = lie_metrics_names(s->metrics);
    else if (!strcmp(c->url, "/actuator/prometheus")) {
      body = lie_metrics_prometheus(s->metrics);
      respond(c, 200, PROM_TYPE, body);
      free(body);
      return;
    } else if (!strcmp(c->url, "/monitor")) {
      respond(c, 200, "text/html; charset=utf-8", PAGE);
      return;
    } else if (!strcmp(c->url, "/actuator/health/liveness")) {
      respond(c, 200, JSON_TYPE, "{\"status\":\"UP\"}");
      return;
    } else if (!strcmp(c->url, "/actuator/health") ||
               !strcmp(c->url, "/actuator/health/readiness")) {
      bool ready = backend_ready(s);
      respond(c, ready ? 200 : 503, JSON_TYPE,
              ready ? "{\"status\":\"UP\"}"
                    : "{\"status\":\"OUT_OF_SERVICE\"}");
      return;
    } else if (!strcmp(c->url, "/actuator/info")) {
      json_object *j = json_object_new_object();
      json_object_object_add(j, "application",
                             json_object_new_string("synapse-lie"));
      json_object_object_add(j, "version", json_object_new_string("0.1.0-dev"));
      json_object_object_add(j, "build_id",
                             json_object_new_string(LIE_BUILD_ID));
      json_object_object_add(j, "instance",
                             json_object_new_string(s->instance));
      json_object_object_add(j, "backend", backend_json(s));
      json_object_object_add(j, "inference_verified",
                             json_object_new_boolean(false));
      body = json_text(j);
    } else if (!strcmp(c->url, "/actuator/llm")) {
      body = llm_json(s);
    } else {
      error_response(c, 404, "not_found");
      return;
    }
  }
  respond(c, 200, JSON_TYPE, body);
  free(body);
}
static int on_url(llhttp_t *p, const char *data, size_t n) {
    connection *c = p->data;
    if (n >= sizeof(c->url) - c->url_size) { error_response(c, 400, "target_too_long"); return HPE_USER; }
    memcpy(c->url + c->url_size, data, n); c->url_size += n; c->url[c->url_size] = 0; return 0;
}
static int on_header(llhttp_t *p, const char *data, size_t n) {
    (void)data; connection *c = p->data; c->headers_size += n;
    if (c->headers_size > MAX_HEADERS) { error_response(c, 431, "headers_too_large"); return HPE_USER; } return 0;
}
static int on_headers(llhttp_t *p) {
    connection *c = p->data;
    if (p->upgrade) { error_response(c, 400, "upgrade_unsupported"); return HPE_USER; }
    if (p->content_length > MAX_BODY) { error_response(c, 413, "body_too_large"); return HPE_USER; }
    return 0;
}
static int on_body(llhttp_t *p, const char *data, size_t n) {
    connection *c=p->data;
    if (n>MAX_BODY-c->body_size) { error_response(c,413,"body_too_large"); return HPE_USER; }
    size_t needed=c->body_size+n+1;
    if (needed>c->body_capacity) {
        size_t cap=c->body_capacity?c->body_capacity:4096;
        while (cap<needed) cap*=2;
        if (cap>MAX_BODY+1) cap=MAX_BODY+1;
        char *body=realloc(c->body,cap);
        if (!body) { error_response(c,500,"allocation_failed"); return HPE_USER; }
        c->body=body; c->body_capacity=cap;
    }
    memcpy(c->body+c->body_size,data,n); c->body_size+=n; c->body[c->body_size]=0; return 0;
}
static int complete(llhttp_t *p) {
    connection *c=p->data; c->input_done=true; return HPE_PAUSED;
}
static void alloc_buffer(uv_handle_t *h, size_t suggested, uv_buf_t *b) {
    (void)h; (void)suggested; b->base = malloc(8192); b->len = b->base ? 8192 : 0;
}
static void read_data(uv_stream_t *stream, ssize_t n, const uv_buf_t *b) {
    connection *c = stream->data;
    if (n > 0) {
        if (c->input_done) { free(b->base); close_connection(c); return; }
        c->wire_size += (size_t)n;
        if (c->wire_size > MAX_BODY + MAX_HEADERS + 2048) error_response(c, 413, "request_too_large");
        else {
            llhttp_errno_t e = llhttp_execute(&c->parser, b->base, (size_t)n);
            if (e != HPE_OK && e != HPE_PAUSED && !c->responded) error_response(c, 400, "invalid_http");
            else if (e==HPE_PAUSED && c->input_done && !c->responded) {
                const char *end=llhttp_get_error_pos(&c->parser);
                if (end && end<b->base+n) error_response(c,400,"pipelining_unsupported");
                else route(c);
            }
        }
    } else if (n < 0) close_connection(c);
    free(b->base);
}
static void closed(uv_handle_t *h) {
  connection *c = h->data;
  server *s = c->owner;
  if (--c->handles)
    return;
  if (c->writing || c->loan)
    abort();
  if (c->stored) {
    stored_request *r = c->stored;
    r->foreground = NULL;
    lie_record_view v;
    lie_record_snapshot(r->record, &v);
    if (s->stopping)
      stored_dispose(r);
    else if (!v.done && !stored_start(r))
      lie_job_cancel(lie_record_job(r->record));
  }
  if (c->record)
    lie_record_release(c->record);
  if (c->choices)
    lie_choices_release(c->choices);
  else if (!c->record && c->job)
    lie_job_release(c->job);
  connection **p = &s->connections;
  while (*p && *p != c)
    p = &(*p)->next;
  if (*p)
    *p = c->next;
  --s->active;
  (void)lie_gauge_set(s->metrics, s->connections_meter, (double)s->active);
  json_object_put(c->calls);
  json_object_put(c->wire_options);
  for (unsigned i = 0; i < c->choice_count; ++i) {
    free(c->choice[i].text);
    json_object_put(c->choice[i].calls);
    json_object_put(c->choice[i].completion);
  }
  free(c->body);
  free(c->text);
  free(c);
}
static void close_connection(connection *c) {
  if (c->closing)
    return;
  c->closing = true;
  if (c->job && (!c->stored || !c->stored->background))
    lie_job_cancel(c->job);
  if (c->choices)
    lie_choices_cancel(c->choices);
  uv_read_stop((uv_stream_t *)&c->tcp);
  if (c->poll_initialized) {
    uv_poll_stop(&c->output_poll);
    uv_close((uv_handle_t *)&c->output_poll, closed);
  }
  for (unsigned i = 0; i < c->choice_count; ++i)
    if (c->choice[i].initialized) {
      uv_poll_stop(&c->choice[i].poll);
      uv_close((uv_handle_t *)&c->choice[i].poll, closed);
      c->choice[i].poll.data = c;
    }
  uv_close((uv_handle_t *)&c->tcp, closed);
  if (!c->writing)
    release_loan(c);
}
static void accepted(uv_stream_t *stream, int status) {
    if (status < 0) return;
    listener *l = stream->data; server *s = l->owner;
    connection *c = calloc(1, sizeof(*c)); if (!c) return;
    if (uv_tcp_init(&s->loop, &c->tcp)) { free(c); return; }
    c->owner = s; c->management = l->management; c->started = lie_monotonic_ns(); c->tcp.data = c; c->handles=1;
    c->next = s->connections; s->connections = c; ++s->active;
    if (uv_accept(stream, (uv_stream_t *)&c->tcp) || s->active > MAX_CONNECTIONS) { close_connection(c); return; }
    (void)lie_gauge_set(s->metrics, s->connections_meter, (double)s->active);
    int send_bytes=16384; (void)uv_send_buffer_size((uv_handle_t *)&c->tcp,&send_bytes);
    (void)uv_tcp_nodelay(&c->tcp,1);
    llhttp_init(&c->parser, HTTP_REQUEST, &s->settings); c->parser.data = c;
    if (uv_read_start((uv_stream_t *)&c->tcp, alloc_buffer, read_data)) close_connection(c);
}
static void tick(uv_timer_t *timer) {
  server *s = timer->data;
  uint64_t now_ns = lie_monotonic_ns();
  (void)lie_gauge_set(s->metrics, s->uptime,
                      (double)(now_ns - s->started) / 1e9);
  (void)lie_gauge_set(s->metrics, s->ready, backend_ready(s) ? 1 : 0);
  if (s->worker) {
    lie_worker_info info;
    lie_worker_snapshot(s->worker, &info);
    if (info.generated_tokens > s->generated_seen) {
      (void)lie_counter_add(
          s->metrics, s->tokens,
          (double)(info.generated_tokens - s->generated_seen));
      s->generated_seen = info.generated_tokens;
    }
  }
  for (connection *c = s->connections; c; c = c->next)
    if (now_ns - c->started >= ((c->job || c->await_cancel || c->replay)
                                    ? s->inference_timeout_ns
                                    : TIMEOUT_NS))
      close_connection(c);
  for (connection *c = s->connections; c; c = c->next)
    if (c->replay)
      pump_replay(c);
  stored_request *r = s->stored;
  while (r) {
    stored_request *next = r->next;
    lie_record_view v;
    lie_record_snapshot(r->record, &v);
    if (!r->foreground && !v.done) {
      if (now_ns - r->started > s->inference_timeout_ns)
        lie_job_cancel(lie_record_job(r->record));
    }
    if (!r->foreground && v.done) {
      lie_record *live = lie_records_get(s->records, v.id, (int64_t)time(NULL));
      if (live)
        lie_record_release(live);
      else
        stored_dispose(r);
    }
    r = next;
  }
}
static void worker_event(uv_poll_t *poll, int status, int events) {
  (void)events;
  server *s = poll->data;
  if (status < 0)
    abort();
  lie_worker_drain(s->worker);
  for (connection *c = s->connections; c; c = c->next)
    if (c->job || c->await_cancel || c->replay)
      pump_job(c);
  lie_worker_info info;
  lie_worker_snapshot(s->worker, &info);
  (void)lie_gauge_set(s->metrics, s->ready, backend_ready(s) ? 1 : 0);
  if (s->stopping && info.state == LIE_STOPPED &&
      !uv_is_closing((uv_handle_t *)poll)) {
    uv_poll_stop(poll);
    uv_close((uv_handle_t *)poll, NULL);
  }
}
static void close_handle(uv_handle_t *handle, void *data) {
  server *s = data;
  if (s && s->worker_poll_initialized &&
      handle == (uv_handle_t *)&s->worker_poll)
    return;
  if (s)
    for (stored_request *r = s->stored; r; r = r->next)
      if (r->polling && handle == (uv_handle_t *)&r->poll)
        return;
  if (!uv_is_closing(handle))
    uv_close(handle, NULL);
}
static void shutdown_server(uv_signal_t *signal, int number) {
  (void)number;
  server *s = signal->data;
  if (s->stopping)
    return;
  s->stopping = true;
  if (s->worker)
    lie_worker_stop(s->worker);
  for (connection *c = s->connections; c; c = c->next)
    close_connection(c);
  stored_request *r = s->stored;
  while (r) {
    stored_request *next = r->next;
    if (!r->foreground)
      stored_dispose(r);
    r = next;
  }
  uv_walk(&s->loop, close_handle, s);
}
static bool init_metrics(server *s) {
    lie_metric_spec spec = {"runtime.uptime", "Runtime uptime", "seconds", LIE_GAUGE, NULL, 0};
    if (lie_metrics_register(s->metrics, &spec, NULL, 0, &s->uptime)) return false;
    spec = (lie_metric_spec){"runtime.ready", "Model and executor ready", NULL, LIE_GAUGE, NULL, 0};
    if (lie_metrics_register(s->metrics, &spec, NULL, 0, &s->ready)) return false;
    spec = (lie_metric_spec){"http.connections.active", "Open HTTP connections", NULL, LIE_GAUGE, NULL, 0};
    if (lie_metrics_register(s->metrics, &spec, NULL, 0, &s->connections_meter)) return false;
    spec = (lie_metric_spec){"llm.requests.rejected", "Requests refused before inference", NULL, LIE_COUNTER, NULL, 0};
    lie_tag tag = {"reason", "backend_unavailable"};
    if (lie_metrics_register(s->metrics, &spec, &tag, 1, &s->rejected)) return false;
    tag.value="queue_full";
    if (lie_metrics_register(s->metrics,&spec,&tag,1,&s->rejected_capacity)) return false;
    tag.value="invalid_request";
    if (lie_metrics_register(s->metrics,&spec,&tag,1,&s->rejected_invalid)) return false;
    spec = (lie_metric_spec){"llm.responses.tool_errors", "Completed model outputs rejected by tool protocol validation", NULL, LIE_COUNTER, NULL, 0};
    if (lie_metrics_register(s->metrics,&spec,NULL,0,&s->tool_errors)) return false;
    spec = (lie_metric_spec){"llm.tokens.generated", "Confirmed generated tokens", "tokens", LIE_COUNTER, NULL, 0};
    if (lie_metrics_register(s->metrics, &spec, NULL, 0, &s->tokens)) return false;
    double buckets[] = {.001, .01, .1, 1, 5};
    spec = (lie_metric_spec){"http.server.requests", "Connection acceptance to response enqueue; not write completion", "seconds", LIE_TIMER, buckets, 5};
    const char *methods[] = {"GET", "POST", "OTHER"}, *statuses[] = {"2xx", "4xx", "5xx"};
    for (size_t m = 0; m < 3; ++m) for (size_t st = 0; st < 3; ++st) {
        lie_tag tags[] = {{"method", methods[m]}, {"status", statuses[st]}};
        if (lie_metrics_register(s->metrics, &spec, tags, 2, &s->http[m][st])) return false;
    }
    return true;
}
static int start_listener(server *s, listener *l, const char *host, int port, bool management) {
    l->owner = s; l->management = management;
    int rc = uv_tcp_init(&s->loop, &l->tcp); if (rc) return rc;
    l->tcp.data = l; struct sockaddr_in address;
    rc = uv_ip4_addr(host, port, &address); if (rc) return rc;
    rc = uv_tcp_bind(&l->tcp, (const struct sockaddr *)&address, 0); if (rc) return rc;
    return uv_listen((uv_stream_t *)&l->tcp, MAX_CONNECTIONS, accepted);
}
static int number(const char *s, int maximum) {
    char *end; errno = 0; long value = strtol(s, &end, 10);
    return errno || !*s || *end || value < 1 || value > maximum ? -1 : (int)value;
}
static int port_number(const char *s) { return number(s,65535); }
int main(int argc, char **argv) {
  setlocale(LC_ALL, "C");
  int port = 19879, management_port = 19880;
  const char *host = "127.0.0.1", *management_host = "127.0.0.1";
  const char *model_id =
      lie_backend_is_synthetic() ? "cpu-test-fixture" : "qwen3.8-flash-next";
  lie_worker_options options;
  lie_core_options_init(&options);
  lie_records_options record_options = {128, 64u * 1024u * 1024u, 3600};
  int timeout_ms = (int)(INFERENCE_TIMEOUT_NS / 1000000);
  for (int i = 1; i < argc; ++i) {
    const char *key = lie_cache_option_name(argv[i]);
    if (!strcmp(key, "--build-info")) {
      printf(
          "{\"build_id\":\"%s\",\"engine\":\"%s\",\"source_pin\":\"%s\","
          "\"ownership\":\"%s\",\"dense_sampling\":\"%s\",\"hardware_qualified\":false,\"cache_retention_"
          "policy\":\"%s\",\"checkpoint_compression\":%s,\"checkpoint_codec\":"
          "\"%s\",\"ds4_cache_policy\":%s,\"state_format\":\"%s\"}\n",
          LIE_BUILD_ID, lie_backend_name(), lie_backend_source_pin(),
          lie_backend_ownership(), lie_backend_dense_sampling(),
          LIE_CACHE_UTILITY ? "ds4-time-token-byte-utility-v1" : "lru",
          lie_state_compression_enabled() ? "true" : "false",
          lie_state_compression_codec(),
          LIE_DS4_CACHE_POLICY ? "true" : "false", lie_backend_state_format());
      return 0;
    }
    if (!strcmp(key, "--help")) {
      puts("Usage: synapse-lie-server [--host IPv4] [--port N] "
           "[--management-host IPv4] [--management-port N]\n  [--model "
           "FIRST-SHARD.gguf] [--model-mtp PREDICTOR.gguf --mtp-draft-tokens "
           "N] [--model-vision PROJECTOR.gguf] [--model-id ID] [--context "
           "128..1048576] [--rope-scaling native|yarn2|yarn4] [--prefill-chunk N] [--max-active 1..8] "
           "[--request-timeout-ms N] [--response-store-ram-mb 64] "
           "[--response-store-records 128] [--response-store-ttl-seconds 3600] "
           "[--kv-cache-ram-mb 4096] "
           "[--kv-cache-policy ds4|legacy]\n  [--kv-cache-min-tokens 512] "
           "[--kv-cache-cold-max-tokens 30000] "
           "[--kv-cache-continued-interval-tokens 10000]\n  "
           "[--kv-cache-boundary-trim-tokens 32] "
           "[--kv-cache-boundary-align-tokens 2048] [--kv-cache-text-prefix "
           "on|off] [--kv-cache-capture-finish on|off]\n  [--kv-disk-dir "
           "ABSOLUTE-DIRECTORY --kv-disk-space-mb N --kv-disk-staging-mb "
           "N]\nWithout --model: management only. Embedded Gufo requires an "
           "opt-in HIP build.\nAR, explicit MTP and vision (also combined) "
           "with per-sequence sampling, thinking disabled. OpenAI function "
           "tools (execution by client). Credit-driven native decode batching. "
           "RAM prefix cache is on by default; zero disables it. KV disk "
           "persistence is opt-in. MTP requires an explicit predictor; KV "
           "reuse requires complete admitted predictor state. Prefix restore "
           "uses fresh request sampling; no exact-session resume.\nCache "
           "budget MB units are binary MiB (1048576 bytes). Legacy --prefix-* "
           "and --cache-* aliases remain accepted.\nModel execution on shared "
           "hardware requires the coordination lease.\n--build-info reports "
           "the compiled provider without opening a model.");
      return 0;
    }
    if (i + 1 == argc) {
      fputs("Missing option value\n", stderr);
      return 2;
    }
    if (!strcmp(key, "--port"))
      port = port_number(argv[++i]);
    else if (!strcmp(key, "--management-port"))
      management_port = port_number(argv[++i]);
    else if (!strcmp(key, "--host"))
      host = argv[++i];
    else if (!strcmp(key, "--management-host"))
      management_host = argv[++i];
    else if (!strcmp(key, "--model"))
      options.model_path = argv[++i];
    else if (!strcmp(key, "--model-vision"))
      options.vision_model_path = argv[++i];
    else if (!strcmp(key, "--model-mtp"))
      options.mtp_model_path = argv[++i];
    else if (!strcmp(key, "--mtp-draft-tokens"))
      options.mtp_draft_tokens = (uint32_t)number(argv[++i], LIE_MTP_MAX_DRAFT);
    else if (!strcmp(key, "--model-id"))
      model_id = argv[++i];
    else if (!strcmp(key, "--context"))
      options.context = (uint32_t)number(argv[++i], LIE_WORKER_MAX_CONTEXT);
    else if (!strcmp(key, "--rope-scaling")) {
      if(!lie_rope_profile_parse(argv[++i], &options.rope_profile)) return 2;
    }
    else if (!strcmp(key, "--prefill-chunk"))
      options.chunk = (uint32_t)port_number(argv[++i]);
    else if (!strcmp(key, "--response-store-ram-mb")) {
      int value = number(argv[++i], 4096);
      if (value < 1)
        return 2;
      record_options.max_bytes = (size_t)value * 1048576u;
    } else if (!strcmp(key, "--response-store-records")) {
      int value = number(argv[++i], 4096);
      if (value < 1)
        return 2;
      record_options.max_records = (size_t)value;
    } else if (!strcmp(key, "--response-store-ttl-seconds")) {
      int value = number(argv[++i], 2592000);
      if (value < 1)
        return 2;
      record_options.ttl_seconds = (uint64_t)value;
    } else if (!strcmp(key, "--max-active"))
      options.max_active = (uint32_t)port_number(argv[++i]);
    else if (!strcmp(key, "--kv-cache-ram-mb")) {
      const char *v = argv[++i];
      int mib = !strcmp(v, "0") ? 0 : number(v, 1048576);
      if (mib < 0) {
        fputs("Invalid KV RAM cache budget\n", stderr);
        return 2;
      }
      options.prefix_cache_bytes = (uint64_t)mib * 1024u * 1024u;
    } else if (!strcmp(key, "--kv-disk-dir"))
      options.ssd.directory = argv[++i];
    else if (!strcmp(key, "--kv-disk-space-mb") ||
             !strcmp(key, "--kv-disk-staging-mb")) {
      bool quota = !strcmp(key, "--kv-disk-space-mb");
      int mib = number(argv[++i], 1048576);
      if (mib < 0) {
        fputs("Invalid KV disk budget\n", stderr);
        return 2;
      }
      if (quota)
        options.ssd.quota_bytes = (uint64_t)mib * 1024u * 1024u;
      else
        options.ssd.staging_bytes = (uint64_t)mib * 1024u * 1024u;
    } else if (!strcmp(key, "--request-timeout-ms"))
      timeout_ms = number(argv[++i], 86400000);
    else {
      int rc = lie_cache_policy_option(&options.cache_policy, key, argv[i + 1]);
      if (rc != 1) {
        fputs(rc ? "Invalid KV cache policy value\n" : "Unknown option\n",
              stderr);
        return 2;
      }
      ++i;
    }
  }
  if ((options.ssd.directory &&
       (!options.model_path || *options.ssd.directory != '/' ||
        !options.ssd.quota_bytes || !options.ssd.staging_bytes)) ||
      (!options.ssd.directory &&
       (options.ssd.quota_bytes || options.ssd.staging_bytes))) {
    fputs("KV disk persistence requires --model, an absolute --kv-disk-dir, "
          "--kv-disk-space-mb and --kv-disk-staging-mb\n",
          stderr);
    return 2;
  }
  if (port < 0 || management_port < 0 ||
      (port == management_port && !strcmp(host, management_host))) {
    fputs("Invalid listener configuration\n", stderr);
    return 2;
  }
  if (options.context < 128 || options.context > LIE_WORKER_MAX_CONTEXT ||
      options.chunk < 1 || options.chunk > 2048 || options.max_active < 1 ||
      options.max_active > LIE_DECODE_MAX_ROWS || timeout_ms < 100 ||
      !*model_id || strlen(model_id) > 128 ||
      !lie_utf8_valid(model_id, strlen(model_id), false) ||
      (options.model_path && !*options.model_path)) {
    fputs("Invalid model configuration\n", stderr);
    return 2;
  }
  if (options.vision_model_path &&
      (!LIE_VISION || !*options.vision_model_path)) {
    fputs("Vision admission is unavailable or empty\n", stderr);
    return 2;
  }
  if (options.mtp_draft_tokens && !options.mtp_model_path) {
    fputs("--mtp-draft-tokens requires --model-mtp\n", stderr);
    return 2;
  }
  if (options.mtp_model_path && (!LIE_MTP || !*options.mtp_model_path)) {
    fputs("MTP requires LIE_MTP=ON and a nonempty predictor path; KV cache "
          "requires complete admitted predictor state\n",
          stderr);
    return 2;
  }
  server s = {0};
  s.records = lie_records_create(&record_options);
  if (!s.records)
    return 1;
  s.started = lie_monotonic_ns();
  s.model_id = model_id;
  s.max_active = options.max_active;
  s.inference_timeout_ns = (uint64_t)timeout_ms * 1000000;
  snprintf(s.instance, sizeof(s.instance), "%ld-%llu", (long)getpid(),
           (unsigned long long)s.started);
  s.metrics = lie_metrics_create(NULL, NULL);
  if (!s.metrics || !init_metrics(&s) || uv_loop_init(&s.loop)) {
    lie_records_destroy(s.records);
    lie_metrics_destroy(s.metrics);
    return 1;
  }
  llhttp_settings_init(&s.settings);
  s.settings.on_url = on_url;
  s.settings.on_header_field = on_header;
  s.settings.on_header_value = on_header;
  s.settings.on_headers_complete = on_headers;
  s.settings.on_body = on_body;
  s.settings.on_message_complete = complete;
  int rc = start_listener(&s, &s.api, host, port, false);
  if (!rc)
    rc = start_listener(&s, &s.management, management_host, management_port,
                        true);
  if (rc) {
    fprintf(stderr, "Listener startup failed: %s\n", uv_strerror(rc));
    uv_walk(&s.loop, close_handle, NULL);
    uv_run(&s.loop, UV_RUN_DEFAULT);
    uv_loop_close(&s.loop);
    lie_records_destroy(s.records);
    lie_metrics_destroy(s.metrics);
    return 1;
  }
  uv_timer_init(&s.loop, &s.timer);
  s.timer.data = &s;
  uv_timer_start(&s.timer, tick, 0, 250);
  uv_signal_init(&s.loop, &s.interrupt);
  s.interrupt.data = &s;
  uv_signal_start(&s.interrupt, shutdown_server, SIGINT);
  uv_signal_init(&s.loop, &s.terminate);
  s.terminate.data = &s;
  uv_signal_start(&s.terminate, shutdown_server, SIGTERM);
  if (options.model_path) {
    s.worker = lie_worker_create(&options);
    rc = s.worker
             ? uv_poll_init(&s.loop, &s.worker_poll, lie_worker_fd(s.worker))
             : UV_ENOMEM;
    if (!rc) {
      s.worker_poll_initialized = true;
      s.worker_poll.data = &s;
      rc = uv_poll_start(&s.worker_poll, UV_READABLE, worker_event);
    }
    if (rc) {
      fprintf(stderr, "Worker startup failed: %s\n", uv_strerror(rc));
      if (s.worker)
        lie_worker_stop(s.worker);
      uv_walk(&s.loop, close_handle, NULL);
      uv_run(&s.loop, UV_RUN_DEFAULT);
      if (s.worker) {
        for (;;) {
          lie_worker_info info;
          lie_worker_snapshot(s.worker, &info);
          if (info.state == LIE_STOPPED)
            break;
          struct pollfd fd = {lie_worker_fd(s.worker), POLLIN, 0};
          (void)poll(&fd, 1, -1);
          lie_worker_drain(s.worker);
        }
        lie_worker_destroy(s.worker);
      }
      uv_loop_close(&s.loop);
      lie_metrics_destroy(s.metrics);
      return 1;
    }
  }
  printf("API http://%s:%d management http://%s:%d backend=%s\n", host, port,
         management_host, management_port,
         s.worker ? lie_backend_name() : "unavailable");
  fflush(stdout);
  uv_run(&s.loop, UV_RUN_DEFAULT);
  rc = uv_loop_close(&s.loop);
  lie_records_destroy(s.records);
  if (s.worker)
    lie_worker_destroy(s.worker);
  lie_metrics_destroy(s.metrics);
  return rc ? 1 : 0;
}
