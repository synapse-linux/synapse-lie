<!-- SPDX-License-Identifier: MIT -->
# Agent clients and function tools

Configure the client with base URL `http://SERVER-IP:8000/v1` and the model ID
listed by `GET /v1/models`. Use an explicit output budget and match the client's
context window to the server. LIE exposes functions through Chat Completions
and Responses; the client executes them and returns their correlated results.
There is no server-side shell executor.

## Chat function round trip

Request a named function with a simple schema:

```sh
curl --fail http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3.8-flash-next","messages":[{"role":"user","content":"Read README.md using the read function."}],"tools":[{"type":"function","function":{"name":"read","description":"Read a local text file.","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"],"additionalProperties":false}}}],"tool_choice":{"type":"function","function":{"name":"read"}},"temperature":0,"max_tokens":512,"store":false}'
```

A successful response has `finish_reason:"tool_calls"`. Copy its assistant
message, including `tool_calls`, into the next request. Append the tool result
with the exact returned `tool_call_id`; for example:

```json
{
  "model": "qwen3.8-flash-next",
  "messages": [
    {"role": "user", "content": "Read README.md using the read function."},
    {"role": "assistant", "content": null, "tool_calls": [
      {"id": "RETURNED_CALL_ID", "type": "function", "function": {
        "name": "read", "arguments": "{\"path\":\"README.md\"}"
      }}
    ]},
    {"role": "tool", "tool_call_id": "RETURNED_CALL_ID", "content": "File contents returned by the client."}
  ],
  "temperature": 0,
  "max_tokens": 512,
  "store": false
}
```

Do not replace the actual arguments with the example when executing the call.
Multiple calls have separate stable IDs and indices. `parallel_tool_calls:false`
permits at most one call per turn. Tool choice also accepts `auto`, `none`,
`required`, and `allowed_tools` subsets. Responses uses flat function definitions
and `function_call_output` items with the matching `call_id`. Retained Responses
can continue through `previous_response_id`; stateless clients carry full history.

## Streaming

Add `stream:true`. Chat emits a call start with ID/name, followed by indexed
argument fragments. Responses emits `response.output_item.added`,
`response.function_call_arguments.delta`, then validated arguments/item done
events and the terminal response. Prose, when present, precedes function items.
Concatenate each call's argument fragments in order; an individual fragment
need not be valid JSON. Qwen XML parameter tags and JSON
name/arguments frames stream incrementally once the function name is complete.
Nested or quoted argument fields cannot change that name.

Execute only after successful turn completion. Failed, cancelled or truncated
turns discard provisional calls, even if their accumulated JSON parses. Stored
Responses retain the same fragment journal for replay with
`GET /v1/responses/ID?stream=true&starting_after=N`. The cursor is the last
received sequence number.

## Evaluation

Use `temperature:0`, explicit `max_tokens`/`max_output_tokens` and `store:false`
for stateless evaluation. The current maximum requested output is 4,096 tokens;
thinking remains disabled. Unsupported fields return errors instead of being
silently ignored. The [API reference](../reference/OPENAI-REACTIVE.md) describes
the available services and schema subset. The [usage guide](USAGE.md#connect-pi)
contains Pi configuration.

The audited TerminalBenchMini/Terminus-2 harness uses ordinary assistant text
containing its JSON command protocol, rather than native OpenAI function calls.
Its previous task failures do not establish a missing function API. Validate
that protocol and the actual task verifier separately from the native function
round trip. Do not change task instructions to reveal observed verifier failures.
The corrected runtime passes thirteen original-weight HTTP checks on Strix
Point, including Chat/Responses functions, incremental argument SSE, correlated
results, a Chat allowed-tool subset and byte-identical retained Responses replay.
Both APIs stream five nonempty argument fragments in that short gate.
[GPU receipt](../development/validation/tool-context-point-gpu-2026-10-04.json).
This qualifies the native function round trip; a full Terminal Bench task run
of the exact runtime remains outstanding. The earlier harness audit is recorded
in development progress.
