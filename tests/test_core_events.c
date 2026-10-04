/* SPDX-License-Identifier: MIT */
/* Headless semantic lifecycle/parser contracts; fixtures only, NOT-INFERENCE.
 */
#include "../src/output_json.h"
#include "fake_executor.h"
#include "lie/events.h"
#include "lie/output.h"
#include "lie/text.h"
#include <assert.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
static void pause_short(void) {
  struct timespec t = {0, 1000000};
  nanosleep(&t, NULL);
}
static void state(lie_core *c, lie_core_state wanted) {
  for (unsigned i = 0; i < 5000; ++i) {
    lie_core_info s;
    lie_core_snapshot(c, &s);
    if (s.state == wanted)
      return;
    pause_short();
  }
  assert(!"core deadline");
}
static lie_event next(lie_job *j) {
  for (unsigned i = 0; i < 5000; ++i) {
    lie_event e;
    lie_flow_status rc = lie_job_event_next(j, &e);
    if (rc == LIE_FLOW_OK) {
      assert(e.abi_version == LIE_EVENT_ABI && e.struct_bytes == sizeof(e));
      return e;
    }
    assert(rc == LIE_FLOW_WOULD_BLOCK);
    struct pollfd p = {lie_job_event_fd(j), POLLIN, 0};
    assert(poll(&p, 1, 1) >= 0);
    assert(lie_job_event_drain(j) == LIE_FLOW_OK);
  }
  assert(!"event deadline");
  return (lie_event){0};
}
static void release(lie_job *j, lie_event e) {
  assert(lie_job_event_release(j, e.ticket) == LIE_FLOW_OK);
  assert(lie_job_event_release(j, e.ticket) == LIE_FLOW_INVALID);
  if (e.tokens)
    (void)lie_job_event_request(j, e.tokens);
}
static lie_job *submit_policy(lie_core *c, const char *input, bool tools,
                              unsigned budget, lie_tool_choice choice,
                              bool parallel) {
  lie_core_request r;
  lie_core_request_init(&r);
  lie_chat_message m = {LIE_CHAT_USER, input, strlen(input)};
  lie_chat_tool t = {
      "read", "Read",
      "{\"type\":\"object\",\"properties\":{\"path\":{\"type\":\"string\"},"
      "\"offset\":{\"type\":\"integer\"},\"options\":{\"type\":\"object\"}},"
      "\"required\":[\"path\"],\"additionalProperties\":false}",
      "{}"};
  r.chat =
      (lie_chat_template){&m, NULL, 1, tools ? &t : NULL, tools ? 1 : 0, 0};
  r.tool_choice = choice;
  r.parallel_tool_calls = parallel;
  r.max_tokens = budget;
  lie_job *j = NULL;
  assert(!lie_core_submit(c, &r, &j));
  assert(lie_job_event_fd(j) >= 0);
  assert(lie_job_flow(j) == NULL);
  return j;
}
static lie_job *submit(lie_core *c, const char *input, bool tools,
                       unsigned budget, lie_tool_choice choice) {
  return submit_policy(c, input, tools, budget, choice, true);
}
static void consume(lie_job *j, lie_turn_reason reason, unsigned calls,
                    bool cancel_prose) {
  uint64_t tokens = 0;
  unsigned seen_calls = 0;
  char text[4096] = {0};
  size_t bytes = 0;
  bool checked = false;
  char arguments[LIE_CHAT_MAX_CALLS][4096] = {{0}};
  size_t argument_bytes[LIE_CHAT_MAX_CALLS] = {0};
  bool started[LIE_CHAT_MAX_CALLS] = {false};
  for (;;) {
    lie_event e = next(j);
    if (e.kind == LIE_EVENT_TURN_END) {
      assert(e.reason == reason && e.info.retired);
      assert(e.info.output_tokens == tokens);
      assert(e.token_offset == tokens);
      if (reason == LIE_TURN_ERROR)
        assert(e.info.output_invalid && e.info.semantic_checked &&
               e.info.error[0]);
      assert(seen_calls == calls);
      lie_event again;
      assert(lie_job_event_next(j, &again) == LIE_FLOW_CLOSED);
      break;
    }
    assert(e.token_offset == tokens);
    tokens += e.tokens;
    lie_event ignored;
    assert(lie_job_event_next(j, &ignored) == LIE_FLOW_BUSY);
    lie_event_ticket wrong = e.ticket;
    wrong.generation++;
    assert(lie_job_event_release(j, wrong) == LIE_FLOW_INVALID);
    if (e.kind == LIE_EVENT_TEXT) {
      assert(lie_utf8_valid(e.text, e.bytes, true));
      assert(bytes + e.bytes < sizeof(text));
      memcpy(text + bytes, e.text, e.bytes);
      bytes += e.bytes;
      if (cancel_prose) {
        assert(!seen_calls);
        lie_job_cancel(j);
        assert(!memcmp(e.text, "Reading.\n", e.bytes));
      }
    }
    if (e.kind == LIE_EVENT_TOOL_CALL) {
      assert(!strcmp(e.call->name, "read") && e.call->index == seen_calls &&
             e.call->id[0]);
      assert(started[e.call->index] &&
             !strcmp(arguments[e.call->index], e.call->arguments_json));
      oj_node *a = oj_parse(e.call->arguments_json, e.call->arguments_bytes);
      assert(a);
      assert(!strcmp(oj_field(a, "path")->string, "  caffè 🙂.txt  "));
      assert(oj_field(a, "offset")->number == 3);
      assert(oj_field(oj_field(a, "options"), "raw")->boolean);
      oj_free(a);
      ++seen_calls;
      checked = true;
    }
    if (e.kind == LIE_EVENT_TOOL_START) {
      assert(e.call->index < LIE_CHAT_MAX_CALLS && !started[e.call->index]);
      started[e.call->index] = true;
      assert(!e.call->arguments_bytes && !e.tokens);
    }
    if (e.kind == LIE_EVENT_TOOL_ARGUMENT_DELTA) {
      size_t i = e.call->index;
      assert(i < LIE_CHAT_MAX_CALLS && started[i] && !e.tokens);
      assert(e.call->arguments_bytes <
             sizeof(arguments[i]) - argument_bytes[i]);
      memcpy(arguments[i] + argument_bytes[i], e.call->arguments_json,
             e.call->arguments_bytes);
      argument_bytes[i] += e.call->arguments_bytes;
      arguments[i][argument_bytes[i]] = 0;
    }
    release(j, e);
  }
  if (!calls && reason == LIE_TURN_STOP)
    assert(!strcmp(text, "fixture: 🙂\"\\\n�"
                         "�"));
  if (calls)
    assert(checked && !strcmp(text, "Reading.\n"));
  lie_job_release(j);
}
static void parser(void) {
  const char *bad[] = {"01",
                       "1e999",
                       "{\"x\":1e999}",
                       "{\"x\\u0000y\":1}",
                       "[true,]",
                       "{\"a\":1,\"a\":2}",
                       "\"\\ud800\"",
                       "\"\\u0000\"",
                       "{\"a\":\"x}",
                       "[1] trailing"};
  for (size_t i = 0; i < sizeof(bad) / sizeof(*bad); ++i)
    assert(!oj_parse(bad[i], strlen(bad[i])));
  const char *good[] = {
      "null",          "true",
      "-12.5e-3",      "{\"a\":\"\\ud83d\\ude42\",\"b\":[1,false,null]}",
      "\"\\\\u0000\"", "0e99999"};
  for (size_t i = 0; i < sizeof(good) / sizeof(*good); ++i) {
    oj_node *v = oj_parse(good[i], strlen(good[i]));
    assert(v);
    oj_free(v);
  }
  char nested[100];
  memset(nested, '[', 40);
  nested[40] = '0';
  memset(nested + 41, ']', 40);
  assert(!oj_parse(nested, 81));
  const char *schema =
      "{\"properties\":{\"path\":{\"type\":\"string\"},\"value\":{\"anyOf\":[{"
      "\"type\":\"integer\"},{\"type\":\"null\"}]}},\"required\":[\"path\"],"
      "\"additionalProperties\":false}";
  lie_chat_tool tool = {"read", "", schema, "{}"};
  lie_output_policy p = {&tool, 1, LIE_TOOLS_AUTO, true, NULL};
  const char *one =
      "<tool_call><function=read><parameter=path> x "
      "</parameter><parameter=value>1.0</parameter></function></tool_call>";
  lie_output_turn t = {0};
  char error[256];
  assert(lie_output_parse(&p, one, strlen(one), true, "id", &t, error));
  assert(t.count == 1);
  lie_output_turn_clear(&t);
  for (size_t n = strlen("<tool_call>"); n < strlen(one); ++n) {
    assert(!lie_output_parse(&p, one, n, true, "id", &t, error));
    assert(!t.count && !t.text);
  }
  char twice[1024];
  snprintf(twice, sizeof(twice), "%s%s", one, one);
  p.parallel = false;
  assert(!lie_output_parse(&p, twice, strlen(twice), true, "id", &t, error));
  p.parallel = true;
  assert(lie_output_parse(&p, twice, strlen(twice), true, "id", &t, error) &&
         t.count == 2);
  lie_output_turn_clear(&t);
  const char *invalid =
      "<tool_call><function=read><parameter=path>x</"
      "parameter><parameter=value>1.5</parameter></function></tool_call>";
  assert(
      !lie_output_parse(&p, invalid, strlen(invalid), true, "id", &t, error));
}
static void incremental_prefixes(void) {
  lie_chat_tool tool = {
      "run", "Run",
      "{\"type\":\"object\",\"properties\":{\"command\":{\"type\":\"string\"},"
      "\"payload\":{\"type\":\"object\"},\"optional\":{\"type\":[\"string\","
      "\"null\"]}},"
      "\"required\":[\"command\",\"payload\"],\"additionalProperties\":false}",
      NULL};
  lie_output_policy policy = {&tool, 1, LIE_TOOLS_AUTO, true, NULL};
  const char *cases[] = {
      "Plan.\n<tool_call>\n<function=run>\r\n<parameter=command>\r\n"
      "echo \"caffè 🙂\" \\\nnext\r\n</parameter>\n<parameter=payload>\n"
      "{ \"rows\": [1, {\"s\": \"x\\n\\\"\"}], \"ok\": true }\n</parameter>"
      "<parameter=optional>null</parameter></function>\n</tool_call>",
      "<tool_call><function=run><parameter=command>\n\n\r\n</parameter>"
      "<parameter=payload>{}</parameter><parameter=optional>nullified</"
      "parameter>"
      "</function></tool_call>\n<tool_call><function=run><parameter=command>x</"
      "parameter>"
      "<parameter=payload>{\"nested\":{\"a\":[null, false]}}</parameter>"
      "</function></tool_call>",
      "<tool_call>{\"name\":\"run\",\"arguments\":{\"command\":\"x\","
      "\"payload\":{}}}</tool_call>"};
  for (size_t c = 0; c < sizeof(cases) / sizeof(*cases); ++c) {
    const char *text = cases[c];
    lie_output_turn previous = {0};
    unsigned extensions = 0;
    for (size_t n = 0; n <= strlen(text); ++n) {
      if (!lie_utf8_valid(text, n, false))
        continue;
      lie_output_turn current = {0};
      assert(lie_output_preview(&policy, text, n, "prefix-oracle", &current));
      assert(current.count >= previous.count);
      for (size_t i = 0; i < previous.count; ++i) {
        assert(!strcmp(current.calls[i].id, previous.calls[i].id));
        assert(current.calls[i].arguments_bytes >=
               previous.calls[i].arguments_bytes);
        assert(!memcmp(current.calls[i].arguments_json,
                       previous.calls[i].arguments_json,
                       previous.calls[i].arguments_bytes));
        extensions += current.calls[i].arguments_bytes >
                      previous.calls[i].arguments_bytes;
      }
      lie_output_turn_clear(&previous);
      previous = current;
    }
    lie_output_turn validated = {0};
    char error[256];
    assert(lie_output_parse(&policy, text, strlen(text), true, "prefix-oracle",
                            &validated, error));
    assert(previous.count == validated.count);
    for (size_t i = 0; i < validated.count; ++i)
      assert(!strcmp(previous.calls[i].arguments_json,
                     validated.calls[i].arguments_json));
    if (c < 2)
      assert(extensions > 10);
    lie_output_turn_clear(&previous);
    lie_output_turn_clear(&validated);
  }
}
static void family(const char *predictor) {
  lie_core_options o = {.model_path = ":fixture:",
                        .context = 1024,
                        .chunk = 2,
                        .max_active = 2,
                        .mtp_model_path = predictor};
  lie_core *c = lie_core_create(&o);
  assert(c);
  state(c, LIE_READY);
  consume(submit(c, "normal", false, 32, LIE_TOOLS_AUTO), LIE_TURN_STOP, 0,
          false);
  consume(submit(c, "TOOL", true, 512, LIE_TOOLS_AUTO), LIE_TURN_TOOL_CALLS, 1,
          false);
  const char *bad[] = {"TOOL-TRUNCATED", "TOOL-UNKNOWN", "TOOL-DUPLICATE",
                       "TOOL-JSON-BAD"};
  for (size_t i = 0; i < sizeof(bad) / sizeof(*bad); ++i)
    consume(submit(c, bad[i], true, 512, LIE_TOOLS_AUTO), LIE_TURN_ERROR, 0,
            false);
  consume(submit(c, "TOOL", true, 40, LIE_TOOLS_AUTO), LIE_TURN_ERROR, 0,
          false);
  consume(submit(c, "TOOL", true, 512, LIE_TOOLS_NONE), LIE_TURN_ERROR, 0,
          false);
  consume(submit(c, "normal", true, 32, LIE_TOOLS_REQUIRED), LIE_TURN_ERROR, 0,
          false);
  consume(submit(c, "TOOL", true, 512, LIE_TOOLS_AUTO), LIE_TURN_CANCELLED, 0,
          true);
  consume(submit(c, "TOOL-TWICE", true, 512, LIE_TOOLS_AUTO),
          LIE_TURN_TOOL_CALLS, 2, false);
  consume(submit_policy(c, "TOOL-TWICE", true, 512, LIE_TOOLS_AUTO, false),
          LIE_TURN_ERROR, 0, false);
  lie_core_info info;
  lie_core_snapshot(c, &info);
  assert(info.output_validation_errors == 8);
  /* Hold a provisional argument loan while another row completes. */
  lie_job *tool_job = submit(c, "TOOL", true, 512, LIE_TOOLS_AUTO);
  lie_event argument;
  for (;;) {
    argument = next(tool_job);
    assert(argument.kind != LIE_EVENT_TURN_END);
    if (argument.kind == LIE_EVENT_TOOL_ARGUMENT_DELTA)
      break;
    release(tool_job, argument);
  }
  char saved[4096];
  assert(argument.call->arguments_bytes < sizeof(saved));
  memcpy(saved, argument.call->arguments_json, argument.call->arguments_bytes);
  lie_job_info streaming;
  lie_job_snapshot(tool_job, &streaming);
  assert(!streaming.retired);
  lie_job *peer = submit(c, "normal", false, 32, LIE_TOOLS_AUTO);
  consume(peer, LIE_TURN_STOP, 0, false);
  lie_job_cancel(tool_job);
  assert(!memcmp(saved, argument.call->arguments_json,
                 argument.call->arguments_bytes));
  release(tool_job, argument);
  argument = next(tool_job);
  assert(argument.kind == LIE_EVENT_TURN_END &&
         argument.reason == LIE_TURN_CANCELLED);
  lie_job_release(tool_job);
  /* Release the client after PROGRESS, without draining the internally pinned
   * preview. Destruction must retire the raw loan, with no borrowed event. */
  tool_job = submit(c, "TOOL", true, 512, LIE_TOOLS_AUTO);
  for (;;) {
    argument = next(tool_job);
    assert(argument.kind != LIE_EVENT_TURN_END);
    bool abandoned = argument.kind == LIE_EVENT_TOOL_START;
    release(tool_job, argument);
    if (abandoned)
      break;
  }
  lie_job_release(tool_job);
  /* Borrowed text survives cancellation. Withhold credit on one row while
   * another finishes; unchanged fixed thread count, independent demand. */
  lie_job *a = submit(c, "LONG-A", false, 128, LIE_TOOLS_AUTO),
          *b = submit(c, "normal", false, 32, LIE_TOOLS_AUTO);
  lie_event loan = next(a);
  assert(loan.kind == LIE_EVENT_TEXT && loan.bytes >= 256);
  char retained = loan.text[0];
  consume(b, LIE_TURN_STOP, 0, false);
  lie_job_info ai;
  lie_job_snapshot(a, &ai);
  assert(ai.output_tokens == 8 && !ai.retired);
  lie_job_cancel(a);
  assert(loan.text[0] == retained);
  release(a, loan);
  lie_event terminal = next(a);
  assert(terminal.kind == LIE_EVENT_TURN_END &&
         terminal.reason == LIE_TURN_CANCELLED);
  lie_job_release(a);
  /* No semantic terminal while a prefill call is still running. */
  fake_barrier_arm_phase(FAKE_PREFILL);
  a = submit(c, "normal", false, 32, LIE_TOOLS_AUTO);
  fake_barrier_wait();
  lie_job_cancel(a);
  lie_event e;
  assert(lie_job_event_next(a, &e) == LIE_FLOW_WOULD_BLOCK);
  fake_barrier_release();
  e = next(a);
  assert(e.kind == LIE_EVENT_TURN_END && e.info.retired &&
         e.reason == LIE_TURN_CANCELLED);
  lie_job_release(a);
  /* Legacy raw consumers remain usable and cannot mix semantic consumption. */
  lie_core_request r;
  lie_core_request_init(&r);
  r.kind = LIE_INPUT_TEXT;
  r.text = "normal";
  r.text_bytes = 6;
  r.max_tokens = 32;
  a = NULL;
  assert(!lie_core_submit(c, &r, &a));
  assert(lie_job_flow(a));
  assert(lie_job_event_next(a, &e) == LIE_FLOW_INVALID);
  lie_job_release(a);
  lie_core_stop(c);
  state(c, LIE_STOPPED);
  lie_core_destroy(c);
}
int main(void) {
  parser();
  incremental_prefixes();
  family(NULL);
#if LIE_MTP
  family(":fixture:");
  family(":wide-fixture:");
#endif
  puts("C17 headless semantic events, tool policy, UTF-8, credits and "
       "cancellation: PASS (NOT-INFERENCE)");
  return 0;
}
