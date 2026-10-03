/* SPDX-License-Identifier: MIT */
#include "core_events.h"
#include "lie/output.h"
#include "lie/text.h"
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

struct lie_event_stream {
  lie_job *job;
  lie_flow *flow;
  lie_output_policy policy;
  char identity[64];
  lie_utf8_decoder utf8;
  char *scratch, *buffer;
  size_t capacity, bytes, buffer_capacity, limit;
  lie_output_turn turn;
  size_t call_index;
  lie_flow_event raw;
  uint64_t generation, offset;
  bool tools, borrowed, raw_loan, terminal, text_sent, done, checked;
  const char *failure;
  lie_job_info final;
};
lie_event_stream *lie_event_stream_create(lie_job *job, lie_flow *flow,
                                          const lie_core_request *r,
                                          unsigned burst,
                                          const char *identity) {
  lie_event_stream *s = calloc(1, sizeof(*s));
  if (!s)
    return NULL;
  s->job = job;
  s->flow = flow;
  s->capacity = ((size_t)burst * LIE_CORE_TOKEN_BYTES + 1) * 3 + 8;
  s->scratch = malloc(s->capacity);
  if (!s->scratch) {
    free(s);
    return NULL;
  }
  s->policy =
      (lie_output_policy){r->chat.tools, r->chat.tool_count, r->tool_choice,
                          r->parallel_tool_calls, r->named_tool};
  if (r->chat.require_tool_call && s->policy.choice == LIE_TOOLS_AUTO)
    s->policy.choice = LIE_TOOLS_REQUIRED;
  s->tools = r->chat.tool_count || s->policy.choice != LIE_TOOLS_AUTO;
  s->limit = (size_t)r->max_tokens * LIE_CORE_TOKEN_BYTES * 3 + 8;
  snprintf(s->identity, sizeof(s->identity), "%s", identity);
  return s;
}
void lie_event_stream_destroy(lie_event_stream *s) {
  if (!s)
    return;
  if (s->borrowed)
    abort();
  free(s->scratch);
  free(s->buffer);
  lie_output_turn_clear(&s->turn);
  free(s);
}
bool lie_event_stream_done(const lie_event_stream *s) { return s && s->done; }
static void notify(lie_event_stream *s) {
  uint64_t one = 1;
  ssize_t n;
  do {
    n = write(lie_flow_fd(s->flow, LIE_FLOW_OUTPUT_READY), &one, sizeof(one));
  } while (n < 0 && errno == EINTR);
  if (n < 0 && errno != EAGAIN)
    abort();
}
static bool append(lie_event_stream *s, const char *p, size_t n) {
  if (n > s->limit - s->bytes)
    return false;
  size_t want = s->bytes + n + 1;
  if (want > s->buffer_capacity) {
    size_t c = s->buffer_capacity ? s->buffer_capacity : 4096;
    while (c < want)
      c *= 2;
    if (c > s->limit + 1)
      c = s->limit + 1;
    char *q = realloc(s->buffer, c);
    if (!q)
      return false;
    s->buffer = q;
    s->buffer_capacity = c;
  }
  memcpy(s->buffer + s->bytes, p, n);
  s->bytes += n;
  s->buffer[s->bytes] = 0;
  return true;
}
static void loan(lie_event_stream *s, lie_event *e) {
  s->borrowed = true;
  e->ticket = (lie_event_ticket){s->job, ++s->generation};
}
lie_flow_status lie_event_stream_release(lie_event_stream *s,
                                         lie_event_ticket t) {
  if (!s || !s->borrowed || t.owner != s->job || t.generation != s->generation)
    return LIE_FLOW_INVALID;
  if (s->raw_loan) {
    lie_flow_status rc = lie_flow_release(s->flow, s->raw.ticket);
    if (rc != LIE_FLOW_OK)
      return rc;
    s->raw_loan = false;
  }
  s->borrowed = false;
  if (s->terminal)
    notify(s);
  return LIE_FLOW_OK;
}
lie_flow_status lie_event_stream_next(lie_event_stream *s, lie_event *e) {
  if (!s || !e)
    return LIE_FLOW_INVALID;
  if (s->borrowed)
    return LIE_FLOW_BUSY;
  if (s->done)
    return LIE_FLOW_CLOSED;
  *e = (lie_event){.abi_version = LIE_EVENT_ABI,
                   .struct_bytes = sizeof(*e),
                   .end = LIE_FLOW_ACTIVE,
                   .token_offset = s->offset};
  if (!s->terminal) {
    lie_flow_status rc = lie_flow_next(s->flow, &s->raw);
    if (rc != LIE_FLOW_OK)
      return rc;
    if (s->raw.end == LIE_FLOW_ACTIVE) {
      s->raw_loan = true;
      size_t n = 0;
      if (!lie_utf8_feed(&s->utf8, (const char *)s->raw.data, s->raw.bytes,
                         false, s->scratch, s->capacity, &n))
        abort();
      e->tokens = s->raw.tokens;
      e->token_offset = s->raw.token_offset;
      s->offset = s->raw.token_offset + s->raw.tokens;
      bool buffered = !s->tools || s->failure || append(s, s->scratch, n);
      if (!buffered) {
        s->failure = "semantic_output_limit";
        lie_job_cancel(s->job);
      }
      e->kind = s->tools ? LIE_EVENT_PROGRESS : LIE_EVENT_TEXT;
      if (!s->tools) {
        e->text = s->scratch;
        e->bytes = n;
      }
      loan(s, e);
      return LIE_FLOW_OK;
    }
    s->terminal = true;
  }
  if (!s->checked) {
    lie_job_snapshot(s->job, &s->final);
    if (!s->final.retired)
      return LIE_FLOW_WOULD_BLOCK;
    s->checked = true;
    if (s->raw.end == LIE_FLOW_CANCELLED)
      s->final.finish = LIE_FINISH_CANCEL;
    else if (s->raw.end == LIE_FLOW_ERROR &&
             s->final.finish != LIE_FINISH_INVALID)
      s->final.finish = LIE_FINISH_BACKEND;
    if (s->failure) {
      lie_job_semantic_result(s->job, 0, s->failure);
      lie_job_snapshot(s->job, &s->final);
    } else if (s->final.finish == LIE_FINISH_STOP ||
               s->final.finish == LIE_FINISH_LENGTH) {
      size_t n = 0;
      if (!lie_utf8_feed(&s->utf8, "", 0, true, s->scratch, s->capacity, &n))
        abort();
      if (s->tools) {
        char error[256] = {0};
        bool valid = append(s, s->scratch, n) &&
                     lie_output_parse(&s->policy, s->buffer, s->bytes,
                                      s->final.finish == LIE_FINISH_STOP,
                                      s->identity, &s->turn, error);
        lie_job_semantic_result(
            s->job, valid ? (unsigned)s->turn.count : 0,
            valid ? NULL : (*error ? error : "semantic_output_limit"));
        lie_job_snapshot(s->job, &s->final);
      } else {
        lie_job_semantic_result(s->job, 0, NULL);
        lie_job_snapshot(s->job, &s->final);
        if (n) {
          e->kind = LIE_EVENT_TEXT;
          e->text = s->scratch;
          e->bytes = n;
          loan(s, e);
          return LIE_FLOW_OK;
        }
      }
    }
  }
  /* A cancellation after the raw terminal but before publishing pending calls
   * still suppresses those calls. A previously borrowed event stays valid. */
  if (!s->failure && lie_job_semantic_cancelled(s->job)) {
    s->final.finish = LIE_FINISH_CANCEL;
    s->final.tool_calls = 0;
    lie_output_turn_clear(&s->turn);
  }
  if (s->final.finish == LIE_FINISH_STOP ||
      s->final.finish == LIE_FINISH_LENGTH) {
    if (s->tools && !s->text_sent) {
      s->text_sent = true;
      if (s->turn.bytes) {
        e->kind = LIE_EVENT_TEXT;
        e->text = s->turn.text;
        e->bytes = s->turn.bytes;
        loan(s, e);
        return LIE_FLOW_OK;
      }
    }
    if (s->call_index < s->turn.count) {
      e->kind = LIE_EVENT_TOOL_CALL;
      e->call = &s->turn.calls[s->call_index++];
      loan(s, e);
      return LIE_FLOW_OK;
    }
  }
  e->kind = LIE_EVENT_TURN_END;
  e->info = s->final;
  e->end = s->final.finish == LIE_FINISH_CANCEL ? LIE_FLOW_CANCELLED
           : s->final.finish == LIE_FINISH_STOP ||
                   s->final.finish == LIE_FINISH_LENGTH
               ? LIE_FLOW_COMPLETE
               : LIE_FLOW_ERROR;
  e->reason = e->end == LIE_FLOW_CANCELLED           ? LIE_TURN_CANCELLED
              : e->end == LIE_FLOW_ERROR             ? LIE_TURN_ERROR
              : s->turn.count                        ? LIE_TURN_TOOL_CALLS
              : s->final.finish == LIE_FINISH_LENGTH ? LIE_TURN_LENGTH
                                                     : LIE_TURN_STOP;
  s->done = true;
  return LIE_FLOW_OK;
}
