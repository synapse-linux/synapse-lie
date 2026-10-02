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
| Chat Completions | Text messages, developer/system, functions, choices, correlated results, JSON/SSE, usage | Single completion; no logprobs/logit bias or storage |
| Sampling | Temperature 0–2, top_p >0–1, penalties −2–2, nonnegative seed | Provider sampler; deterministic seed is not a universal hardware guarantee |
| Responses | Stateless text/function input, instructions, JSON response objects, typed sequenced SSE, usage, incomplete/failed terminals | No stored response retrieval, previous_response_id, background execution or server-side tools |
| Function output | Complete-turn XML extraction, argument schema checks and stable call IDs | Strict constrained decoding and incremental argument streaming remain open |
| Structured output | Existing plain text | JSON object/schema constrained generation remains open |
| Other modalities | Explicitly refused | No image, audio, video, embedding or vector model executor |

Unsupported fields/capabilities are errors, never silently claimed as supported.
This increment is **not the complete OpenAI platform API**. Modalities and stored
resources require actual backend execution/state ownership, not route stubs.
Responses defaults to local stateless operation (`store=false`); an explicit
`store=true` request is refused. Function-call history remains caller owned.
No tool runs inside LIE.

## Responses stream ownership

`response.created` and `response.in_progress` precede output items. Text streams
publish item/part creation, text deltas, done signals and one response terminal.
Sequence numbers start at zero and increase without gaps. There is no Chat
`[DONE]` sentinel in a Responses stream. Length completion is `incomplete` with
`max_output_tokens`; a failed buffered tool turn publishes `response.failed`,
never a callable partial function. The normal text stream holds its flow loan
through the transport callback even though a separately bounded final text
projection is retained for the terminal response. Tool-enabled streams consume
into the existing bounded complete-turn validator.

Each request body is at most 8 MiB, with at most 1024 messages. Context admission
is capped at 262144 physical prompt-plus-reserved-output tokens. A final text projection remains bounded by
MAX_TEXT; each encoded network write remains bounded by MAX_RESPONSE (32 MiB). These are
application bounds, not GPU-memory measurements or proof of remote consumption.
Cancellation, deadlines and shutdown use the existing pinned job/flow lifetime;
no special Responses inference scheduler or socket server exists.

## Evidence

`run/openai-reactive-cpu-r3` on 192.168.5.157 passed 16 CTest suites in debug and
16 with ASan/UBSan. The new suite checks Responses text JSON/SSE, exact sequence
ordering, function call/results, invalid generated calls and unsupported state/
modality requests, plus worst-case escaping across 4096 full-size chunks. These are synthetic CPU fixtures, never model inference.
The new linked HIP binary and its original-weight run are recorded separately;
results from an older binary do not qualify new functionality.

Protocol references: https://developers.openai.com/api/reference/cli/resources/chat
and https://developers.openai.com/api/docs/guides/function-calling .
