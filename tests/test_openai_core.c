/* SPDX-License-Identifier: MIT */
/* Native headless contracts. Synthetic fixture, not model inference. */
#include "../src/generation.h"
#include "fake_executor.h"
#include "lie/choices.h"
#include "lie/output.h"
#include "lie/records.h"
#include <assert.h>
#include <math.h>
#include <poll.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
static void pause_short(void) {
  struct timespec t = {0, 1000000};
  nanosleep(&t, NULL);
}
static void state(lie_core *c, lie_core_state wanted) {
  for (unsigned i = 0; i < 5000; ++i) {
    lie_core_info info;
    lie_core_snapshot(c, &info);
    if (info.state == wanted)
      return;
    pause_short();
  }
  assert(!"deadline");
}
static lie_core_request request(const char *text, lie_chat_message *m) {
  lie_core_request r;
  lie_core_request_init(&r);
  *m = (lie_chat_message){LIE_CHAT_USER, text, strlen(text)};
  r.chat.messages = m;
  r.chat.count = 1;
  r.max_tokens = 128;
  return r;
}
static lie_job_info consume(lie_job *job, char *text, size_t capacity) {
  size_t bytes = 0;
  for (unsigned i = 0; i < 10000; ++i) {
    lie_event e;
    lie_flow_status rc = lie_job_event_next(job, &e);
    if (rc == LIE_FLOW_WOULD_BLOCK) {
      struct pollfd p = {lie_job_event_fd(job), POLLIN, 0};
      assert(poll(&p, 1, 2) >= 0);
      lie_job_event_drain(job);
      continue;
    }
    assert(rc == LIE_FLOW_OK);
    if (e.kind == LIE_EVENT_TURN_END) {
      text[bytes] = 0;
      return e.info;
    }
    if (e.kind == LIE_EVENT_TEXT) {
      assert(bytes + e.bytes < capacity);
      memcpy(text + bytes, e.text, e.bytes);
      bytes += e.bytes;
    }
    assert(lie_job_event_release(job, e.ticket) == LIE_FLOW_OK);
    if (e.tokens)
      (void)lie_job_event_request(job, e.tokens);
  }
  assert(!"consume deadline");
  return (lie_job_info){0};
}
static void pump(lie_record *r) {
  for (unsigned i = 0; i < 10000; ++i) {
    assert(lie_record_pump(r));
    lie_record_view v;
    lie_record_snapshot(r, &v);
    if (v.done)
      return;
    pause_short();
  }
  assert(!"record deadline");
}
static void retained_terminal_before_retirement(lie_core *core) {
  lie_records_options limits = {1, 4 * 1048576, 10};
  lie_records *records = lie_records_create(&limits);
  assert(records);
  lie_chat_message message;
  lie_core_request input = request("ok", &message);
  input.max_tokens = 1;
  lie_record *record =
      lie_records_insert(records, "resp_terminal_pending", 100, &input, 0, true);
  assert(record);
  lie_job *job = NULL;
  /* Publishing the last output closes demand before sequence teardown and
   * retired metadata. Hold that real lifecycle boundary deterministically. */
  fake_barrier_arm_phase(FAKE_CLOSE);
  assert(!lie_core_submit(core, &input, &job) && lie_record_attach(record, job));
  fake_barrier_wait();
  lie_record_view view;
  lie_record_snapshot(record, &view);
  assert(!view.done && !view.info.retired && view.info.output_tokens == 1);
  assert(lie_record_pump(record));
  lie_record_snapshot(record, &view);
  assert(!view.done && !view.info.retired && view.info.output_tokens == 1 &&
         view.bytes == 8 && !memcmp(view.text, "fixture:", 8));
  /* Await retirement without cancelling or duplicating the retained output. */
  assert(lie_record_pump(record));
  fake_barrier_release();
  pump(record);
  lie_record_snapshot(record, &view);
  assert(view.done && view.info.retired &&
         view.info.finish == LIE_FINISH_LENGTH && view.info.output_tokens == 1 &&
         view.bytes == 8 && !memcmp(view.text, "fixture:", 8) &&
         lie_record_event_count(record) == 1);
  assert(lie_records_delete(records, "resp_terminal_pending"));
  lie_record_release(record);
  lie_records_destroy(records);
}
static void nested_tools(void) {
  const char *schema =
      "{\"type\":\"object\",\"properties\":{\"items\":{\"type\":\"array\","
      "\"minItems\":1,\"items\":{\"$ref\":\"#/$defs/"
      "value\"}}},\"required\":[\"items\"],\"additionalProperties\":false,\"$"
      "defs\":{\"value\":{\"type\":\"string\",\"enum\":[\"a\"]}}}";
  lie_chat_tool tool = {"read", "", schema, "{}"};
  lie_output_policy policy = {&tool, 1, LIE_TOOLS_REQUIRED, false, NULL};
  const char *valid = "<tool_call>{\"name\":\"read\",\"arguments\":{\"items\":["
                      "\"a\"]}}</tool_call>";
  const char *invalid = "<tool_call>{\"name\":\"read\",\"arguments\":{"
                        "\"items\":[\"b\"]}}</tool_call>";
  lie_output_turn turn = {0};
  char error[256];
  assert(lie_output_parse(&policy, valid, strlen(valid), true, "test-schema",
                          &turn, error) &&
         turn.count == 1);
  lie_output_turn_clear(&turn);
  assert(!lie_output_parse(&policy, invalid, strlen(invalid), true,
                           "test-schema", &turn, error) &&
         !turn.count);
  lie_output_turn_clear(&turn);
}
int main(void) {
  nested_tools();
  lie_core_options o;
  lie_core_options_init(&o);
  o.model_path = ":fixture:";
  o.context = 4096;
  o.chunk = 64;
  o.max_active = 8;
  o.prefix_cache_bytes = 0;
  lie_core *core = lie_core_create(&o);
  assert(core);
  state(core, LIE_READY);
  retained_terminal_before_retirement(core);
  lie_chat_message m;
  lie_core_request r = request("ok", &m);
  r.stop[0] = "🙂";
  r.stop_count = 1;
  lie_job *job = NULL;
  assert(!lie_core_submit(core, &r, &job));
  char text[8192];
  lie_job_info info = consume(job, text, sizeof(text));
  assert(info.finish == LIE_FINISH_STOP && !strcmp(text, "fixture: ") &&
         info.output_tokens == 5);
  lie_job_release(job);
  r = request("ok", &m);
  r.stop[0] = "🙂";
  r.stop_count = 1;
  r.generation.logprobs = 1;
  job = NULL;
  assert(!lie_core_submit(core, &r, &job));
  info = consume(job, text, sizeof(text));
  assert(!strcmp(text, "fixture: ") && info.output_tokens == 5);
  for (size_t i = 0; i < 5; ++i) {
    lie_token_logprobs score;
    assert(lie_job_logprob(job, i, &score) == LIE_OK);
    assert(score.token.bytes == (i == 0 ? 8 : i == 1 ? 1 : 0));
  }
  lie_job_release(job);
  char old[4097];
  memset(old, 'x', 4096);
  old[4096] = 0;
  lie_chat_message conversation[] = {
      {LIE_CHAT_SYSTEM, "TRUNCATION-FIXTURE", 18},
      {LIE_CHAT_USER, old, 4096},
      {LIE_CHAT_ASSISTANT, "old reply", 9},
      {LIE_CHAT_USER, "ok", 2}};
  r = request("ok", &m);
  r.chat.messages = conversation;
  r.chat.count = 4;
  job = NULL;
  assert(!lie_core_submit(core, &r, &job));
  info = consume(job, text, sizeof(text));
  assert(info.finish == LIE_FINISH_INVALID &&
         !strcmp(info.error, "context_budget_exceeded"));
  lie_job_release(job);
  r.truncate_oldest = true;
  job = NULL;
  assert(!lie_core_submit(core, &r, &job));
  info = consume(job, text, sizeof(text));
  assert(info.finish == LIE_FINISH_STOP && info.prompt_tokens == 6);
  lie_job_release(job);
  r = request("ok", &m);
  r.stop[0] = "€";
  r.stop_count = 1;
  job = NULL;
  assert(!lie_core_submit(core, &r, &job));
  info = consume(job, text, sizeof(text));
  assert(info.finish == LIE_FINISH_STOP && strstr(text, "�"));
  lie_job_release(job);
  r = request("ok", &m);
  r.generation.logprobs = 1;
  r.generation.top_logprobs = 20;
  job = NULL;
  assert(!lie_core_submit(core, &r, &job));
  info = consume(job, text, sizeof(text));
  assert(info.output_tokens == 8);
  for (size_t i = 0; i < 8; ++i) {
    lie_token_logprobs score;
    assert(lie_job_logprob(job, i, &score) == LIE_OK);
    assert(score.token.token == (int)i && isfinite(score.token.logprob) &&
           score.token.logprob < 0 && score.top_count == 20 &&
           score.top[0].token == (int)i);
  }
  lie_job_release(job);
  r = request("ok", &m);
  r.format = LIE_FORMAT_JSON_SCHEMA;
  r.strict = true;
  r.schema_json =
      "{\"type\":\"object\",\"properties\":{\"ok\":{\"type\":\"boolean\"}},"
      "\"required\":[\"ok\"],\"additionalProperties\":false}";
  job = NULL;
  assert(!lie_core_submit(core, &r, &job));
  info = consume(job, text, sizeof(text));
  assert(info.finish == LIE_FINISH_STOP && !strcmp(text, "{\"ok\":true}"));
  lie_job_release(job);
  r = request("ok", &m);
  r.generation.seed = INT64_MAX;
  lie_choices *choices = NULL;
  assert(lie_core_submit_choices(core, &r, 2, &choices) == 3 && !choices);
  r.generation.seed = 7;
  assert(!lie_core_submit_choices(core, &r, 3, &choices));
  for (unsigned i = 0; i < 3; ++i) {
    info = consume(lie_choices_job(choices, i), text, sizeof(text));
    assert(info.finish == LIE_FINISH_STOP);
  }
  lie_choices_release(choices);
  lie_records_options tiny_limits = {1, 128 * 1024, 10};
  lie_records *tiny = lie_records_create(&tiny_limits);
  assert(tiny);
  r = request("ok", &m);
  lie_record *quota = lie_records_insert(tiny, "resp_quota", 90, &r, 0, false);
  assert(quota);
  job = NULL;
  assert(!lie_core_submit(core, &r, &job));
  assert(
      !lie_record_attach(quota, job)); /* Failure does not transfer the job. */
  info = consume(job, text, sizeof(text));
  assert(info.finish == LIE_FINISH_STOP);
  lie_job_release(job);
  assert(lie_records_delete(tiny, "resp_quota"));
  lie_record_release(quota);
  lie_records_destroy(tiny);
  lie_records_options limits = {2, 4 * 1048576, 10};
  lie_records *records = lie_records_create(&limits);
  assert(records);
  lie_chat_message messages[] = {{LIE_CHAT_SYSTEM, "old instructions", 16},
                                 {LIE_CHAT_USER, "ok", 2}};
  r = request("ok", &m);
  r.chat.messages = messages;
  r.chat.count = 2;
  lie_record *record =
      lie_records_insert(records, "resp_one", 100, &r, 1, true);
  assert(record);
  job = NULL;
  assert(!lie_core_submit(core, &r, &job) && lie_record_attach(record, job));
  pump(record);
  size_t journal = lie_record_event_count(record);
  assert(journal > 0);
  size_t replay_bytes = 0;
  for (size_t i = 0; i < journal; ++i) {
    lie_event e;
    assert(lie_record_replay(record, i, &e));
    assert(e.kind == LIE_EVENT_TEXT);
    replay_bytes += e.bytes;
  }
  lie_record_view replay_view;
  lie_record_snapshot(record, &replay_view);
  assert(replay_bytes == replay_view.bytes);
  lie_core_request history;
  void *storage = NULL;
  assert(lie_record_history(record, &history, &storage));
  assert(history.chat.count == 2 &&
         history.chat.messages[0].role == LIE_CHAT_USER &&
         history.chat.messages[1].role == LIE_CHAT_ASSISTANT);
  free(storage);
  lie_record *found = lie_records_get(records, "resp_one", 109);
  assert(found == record);
  lie_record_release(found);
  assert(!lie_records_get(records, "resp_one", 110));
  lie_record_release(record);
  /* The retained journal owns provisional arguments after the job retires.
   * Replaying it reconstructs exactly the committed complete call. */
  r = request("TOOL", &m);
  r.max_tokens = 512;
  lie_chat_tool tool = {
      "read", "Read",
      "{\"type\":\"object\",\"properties\":{\"path\":{\"type\":\"string\"},"
      "\"offset\":{\"type\":\"integer\"},\"options\":{\"type\":\"object\"}},"
      "\"required\":[\"path\"],\"additionalProperties\":false}",
      "{}"};
  r.chat.tools = &tool;
  r.chat.tool_count = 1;
  record = lie_records_insert(records, "resp_tool_journal", 111, &r, 0, true);
  assert(record);
  job = NULL;
  assert(!lie_core_submit(core, &r, &job) && lie_record_attach(record, job));
  pump(record);
  char reconstructed[4096] = {0};
  size_t argument_bytes = 0;
  unsigned starts = 0, deltas = 0, committed = 0;
  for (size_t i = 0; i < lie_record_event_count(record); ++i) {
    lie_event e;
    assert(lie_record_replay(record, i, &e));
    if (e.kind == LIE_EVENT_TOOL_START) {
      ++starts;
      assert(e.call->index == 0 && !e.call->arguments_bytes);
    }
    if (e.kind == LIE_EVENT_TOOL_ARGUMENT_DELTA) {
      assert(starts == 1 &&
             e.call->arguments_bytes < sizeof(reconstructed) - argument_bytes);
      memcpy(reconstructed + argument_bytes, e.call->arguments_json,
             e.call->arguments_bytes);
      argument_bytes += e.call->arguments_bytes;
      reconstructed[argument_bytes] = 0;
      ++deltas;
    }
    if (e.kind == LIE_EVENT_TOOL_CALL) {
      assert(!strcmp(reconstructed, e.call->arguments_json));
      ++committed;
    }
  }
  assert(starts == 1 && deltas > 2 && committed == 1);
  assert(lie_records_delete(records, "resp_tool_journal"));
  lie_record_release(record);
  r = request("SLOW-DECODE", &m);
  r.max_tokens = 100;
  record = lie_records_insert(records, "resp_cancel", 120, &r, 0, true);
  assert(record);
  job = NULL;
  assert(!lie_core_submit(core, &r, &job) && lie_record_attach(record, job));
  assert(lie_record_cancel(record) && lie_record_cancel(record));
  pump(record);
  lie_record_view view;
  lie_record_snapshot(record, &view);
  assert(view.done && view.info.retired &&
         view.info.finish == LIE_FINISH_CANCEL);
  assert(lie_records_delete(records, "resp_cancel") &&
         !lie_records_get(records, "resp_cancel", 120));
  lie_record_release(record);
  lie_records_destroy(records);
  lie_core_stop(core);
  state(core, LIE_STOPPED);
  lie_core_destroy(core);
  return 0;
}
