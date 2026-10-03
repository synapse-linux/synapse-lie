# OpenAI API over the reactive C runtime

The API is a general OpenAI text/function interface. Client-specific tool
names and executable callbacks do not belong in the server. Clients execute
functions and send correlated results through the ordinary API.

The C17 pipeline owns admission, token demand, bounded buffers, cancellation,
serial output and retirement. libuv provides asynchronous network readiness;
its presence alone is not the reactive contract. The existing `lie_flow`
subscription controls inference dispatch. A stalled text SSE writer retains
its loan until the write callback; no overflow queue or thread per client is
created. Management readiness remains separate from model forward.

This implements demand-driven semantics used by reactive serving. It does not
embed Java Spring/Project Reactor or claim Reactive Streams TCK compliance:
LIE credits count confirmed tokens, rather than callback items. See REACTIVE.md.
The transitional numerical adapter remains synchronous on the exclusive device
owner. It never executes model forward on the HTTP loop or on a CPU fallback.

## API surface and current limits

| Surface | Implemented behavior | Remaining limit |
|---|---|---|
| Chat Completions | Text/vision/functions, correlated results, JSON/SSE, `n=1..8`, stop sequences, stored completion operations | Original-weight qualification of the new controls remains pending |
| Sampling | Temperature, top-p, penalties, seed, token bias, logprobs and up to 20 alternatives | Logprobs are target probabilities before top-p truncation; greedy requests report the underlying distribution |
| Responses | Text/function/image input, instructions, JSON/SSE, stored retrieval/deletion, `previous_response_id`, background polling/cancellation, paginated input items, automatic truncation and stream replay | Named Conversations and compaction services are not implemented |
| Function output | Shared C extraction/validation and stable call IDs; strict arguments constrained during target sampling | Tools execute in the client; argument deltas are published after complete-turn validation |
| Structured output | JSON object and JSON schema constraints, including strict schemas | The transitional provider compiles the supported schema subset; unsupported schemas are refused |
| Images | Explicit projector admission and owned image inputs | Original-weight vision qualification remains pending |
| Other APIs | Documented capability gaps | Audio/video generation, embeddings, hosted tools, vector stores and cloud administration require separate executors/services |

Unknown or unsupported fields are errors. These are local model-serving APIs;
this server does not implement the complete OpenAI cloud platform.

The C17 core owns stop matching, output validation, choice admission, records,
history, credits and cancellation. Constrained token selection uses the verified
Gufo sampler through neutral C controls; its C++ types remain inside the adapter.
This is transitional delegation, not an autonomous C grammar executor. Token
probability normalization is owned C code. Executor ABI 2 and DS4 payloads are
unchanged; request ABI 5 and generation ABI 2 describe the new controls.

Stop sequences are removed before publication, including matches split across
tokens. There are at most four sequences, each bounded to 256 UTF-8 bytes.
Bias accepts at most 1024 vocabulary IDs with values from -100 to 100.
Explicit stop, bias or logprob requests use one target token per decode step;
ordinary requests retain their admitted MTP burst width and native batching.
No performance benefit or parity is inferred from the fixture results.

Responses default to `store=true`; Chat defaults to `store=false`. Retention is
local RAM: 128 records, a conservative 64 MiB quota and a one-hour TTL by default.
Use `--response-store-records`, `--response-store-ram-mb` and
`--response-store-ttl-seconds` to change these bounds. The quota includes owned
history, reserved output, retained job witnesses and retained client projections;
it excludes model weights and the separate KV cache. Exhaustion returns 429.
Deleting a running record cancels its owned job. Server restart drops records.
Background records with `store=false` use the same temporary local bounds; they
remain retrievable until deletion or expiry.
Use `store=false` for stateless evaluation or benchmarks.

Continuation includes the previous input and validated output, with stable call
IDs. Previous top-level instructions are omitted; the new request supplies its
instructions. A missing, expired or unfinished parent is refused. Background jobs
continue after the creating HTTP connection closes and can be retrieved or
cancelled; cancellation is idempotent and the response waits for device retirement.
`truncation:auto` removes the oldest complete turns until the physical prompt
and reserved output fit. System/developer messages and the latest user turn
remain; function calls/results and image positions move together. If they
still exceed the context budget, admission fails. The default `disabled` policy
returns a context error instead. Input-item history records the submitted
conversation, while usage reports the physically admitted prompt.

There is no additional inference thread. Storage and cancellation never execute
tools. A model failure is not a cache miss or an automatic retry.

Retrieve a retained response stream with
`GET /v1/responses/{id}?stream=true&starting_after=N`. The cursor is the last
received `sequence_number`; omitted means replay from zero. The bounded C
semantic journal gives stable event ordering for completed and live background
responses. Observers read that journal; they do not consume inference credits,
drain the job fd or cancel the generator when they disconnect. Slow observers
hold only their current bounded network write. Delete/TTL controls further
lookup, while an existing record pin remains valid until its observer closes.
Chat list pagination accepts `model` and `metadata[key]` filters, `after`,
`limit=1..100` and ascending/descending order.

## Responses stream ownership

`response.created` and `response.in_progress` precede output items. Text streams
publish item/part creation, text deltas, done signals and one response terminal.
Sequence numbers start at zero and increase without gaps. There is no Chat
`[DONE]` sentinel in a Responses stream. Length completion is `incomplete` with
`max_output_tokens`; a failed buffered tool turn publishes `response.failed`,
never a callable partial function. The normal text stream holds its flow loan
through the transport callback even though a separately bounded final text
projection is retained for the terminal response. Tool-enabled streams
acknowledge core progress events and project the validated
[semantic core events](EVENTS.md). HTTP owns no model-output parser.

Each request body is at most 8 MiB, with at most 1024 messages. Context admission
is capped at 262144 physical prompt-plus-reserved-output tokens. A final text projection remains bounded by
MAX_TEXT; each encoded network write remains bounded by MAX_RESPONSE (32 MiB). These are
application bounds, not GPU-memory measurements or proof of remote consumption.
Cancellation, deadlines and shutdown use the existing pinned job/flow lifetime;
no special Responses inference scheduler or socket server exists.

## Verification

The native `openai-headless-controls-state`, `openai-generation-state-http`
and MTP13 HTTP variant tests exercise the new contracts without Python, weights or GPU execution.
The HIP build checks the independently fetched pinned sampler and adapter;
`gufo-constrained-sampler-cpu` checks token bias and grammar masks on host arrays.
These tests do not qualify original-weight numerical behavior or performance.
Current command exits and source identities are recorded in the OpenAI completion
receipt linked from [development progress](../PROGRESS.md).

Protocol references: [Chat create](https://developers.openai.com/api/reference/python/resources/chat/subresources/completions/methods/create),
[Responses create](https://developers.openai.com/api/reference/python/resources/responses/methods/create),
[structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
[conversation state](https://developers.openai.com/api/docs/guides/conversation-state),
and [background execution and stream resumption](https://developers.openai.com/api/docs/guides/background).
