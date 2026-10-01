# HTTP / SSE and monitor contract — native function tools

The optional real provider is linked. A separately leased original-weight C1
JSON/SSE smoke passed (`t0-model-smoke-r4`), but full numerical/hardware qualification
remains open. The later native tool extension is CPU/Pi-protocol tested and
HIP-linked, not yet exercised with the actual model. CPU transport tests use a
separate, clearly labelled synthetic executable. No model is configured by default and no synthetic provider can be
selected in `synapse-lie-server`.

## Management listener

| Route | Behavior |
|---|---|
| GET /actuator | Relative `_links` discovery and templated flag |
| GET /actuator/health | 200 `UP` after model/executor open, otherwise 503 `OUT_OF_SERVICE` |
| GET /actuator/health/liveness | 200 `UP` while event loop is serving |
| GET /actuator/health/readiness | Same model lifecycle readiness, independent of GPU busyness |
| GET /actuator/info | Application/version/instance/build label; selected backend metadata or null; inference_verified false |
| GET /actuator/metrics | Metric names |
| GET /actuator/metrics/{name} | Detail with repeatable `tag` AND filters |
| GET /actuator/prometheus | Prometheus text 0.0.4 |
| GET /actuator/llm | Ready/backend/scheduler snapshots; unsupported measurements remain null |
| GET /monitor | Embedded en_US development page, no CDN |

Backend metadata identifies engine, source pin, build label and ownership
(`delegated`, `none`, or test-only `synthetic-test-fixture`). Unsupported native
batching, MTP and snapshot restore are explicit. `tools:true` denotes protocol
support, not model quality or server-side tool execution. `tool_streaming` is
`buffered-complete-turn`; context/output/request/message limits are reported. `hardware_qualified:false`
and `inference_verified:false` are not changed merely because a request succeeded.
Readiness is operational model/executor open, not a quality certificate. No probe
inference, device synchronization or filesystem scan occurs in a health/scrape.
The model loads on the worker; loading/failed/unconfigured instances stay unready.

`scheduler.executor` has scope `owner_dispatch_intervals`: `phase` is `none`,
`prefill` or `decode`, with cumulative `prefill_started/returned` and
`decode_started/returned` counters. Each pair differs by zero or one; only one
pair may be outstanding because there is one device owner. These counters count
ABI dispatch/returns, including cancelled/failed returns, not useful tokens.
`none` does not exclude preparation, token rendering or retirement work.
`cancel_during_prefill/decode` counts a job's first cancellation observed while
that job is still in the respective dispatch interval; repeat cancellation is not
counted again. An interval includes small boundary bookkeeping and is not proof
of actual HIP kernel execution or preemption; racing cancellations can fall
outside this observation. These are diagnostic counters, not a GPU event trace.

`scheduler.output_blocked` counts active jobs the worker last observed unable to
reserve output credit/capacity. It is cleared when the worker resumes or retires
the job. It is bounded by `active`, and is not a queue, remote consumption or
instantaneous TCP-window measurement. Counter/phase/occupancy fields come from a
single worker snapshot; overall readiness/backend objects remain separate reads.

Actuator responses use v3 vendor Content-Type. Errors use `application/json`,
`error.code` and `error.message`. No content negotiation/OpenMetrics claim.
Ordinary responses include Content-Length, Connection: close, no-store, nosniff
and CSP. Unknown routes: 404; unsupported management method: 405. No host-derived
absolute URLs or `.txt` Content-Disposition workaround.

## Transport and resource bounds

IPv4 HTTP/1, one request per connection. No keepalive, pipelining, upgrade, TLS,
compression or authentication. llhttp validates framing, including ambiguous
lengths. Trailing input in the completing buffer is refused before admission;
later input cancels the existing request, never admits a second one. A peer EOF is
cancellation, so write-half-close request semantics are not supported.

- 64 connections; 16 KiB header field/value bytes, 1 MiB body, 2047-byte target;
  additional total-wire bound, including chunking overhead.
- At most 18,878,512 bytes per response/write buffer (bounded UTF-8/JSON
  expansion), not a preallocated resident allowance. Eight admitted jobs (queued
  plus executing); overflow 429. One active sequence by default, optionally up to eight (`--max-active 1..8`).
  Ready sequences with output credit use the shared native-batch dispatcher;
  a lone ready sequence uses scalar decode.
- Eight 256-byte token slots per flow. The pinned vocabulary's documented maximum
  rendered entry is 128 bytes; the larger slot is checked before publication.
  UTF-8 expansion and JSON/SSE writes are independently bounded.
- One outstanding uv_write per connection. Request 16 KiB socket send buffer
  (kernel actual size/overhead is platform-defined); local write completion is
  not remote consumption. Nonstream/tool-enabled aggregate bound is 3,145,736
  bytes, independent of socket capacity. Retired jobs/output remain bounded by live connections.
- Five-second accept-to-close deadline for control/incomplete requests. Admitted
  inference uses accept-to-close `--request-timeout-ms`, default 300000,
  configurable 100–1800000 ms, checked on a 250 ms loop tick. It includes queue,
  preparation and output time. Deadline closes the connection and cancels work;
  it does not preempt a kernel or promise a final error response.

These are application bounds, not measured RSS/GPU budgets. Model state and
workspace remain delegated and need target measurements. No fixed 32 GiB reserve.

## API listener

`GET /v1/models` returns an empty list until ready, then the configured model ID.
Management routes do not exist here; model routes do not exist on management.
Without a ready backend, framed chat requests return 503 `backend_unavailable`,
not a fabricated completion or an SSE header.

Ready `POST /v1/chat/completions` accepts this deliberately narrow JSON subset:

```json
{"model":"qwen3.8-flash-next","messages":[{"role":"user","content":"Reply briefly."}],"temperature":0,"max_tokens":32,"stream":true,"stream_options":{"include_usage":true},"chat_template_kwargs":{"enable_thinking":false}}
```

- Required exact configured `model`; 1–128 messages. Roles: leading
  `system`/`developer`, `user`, `assistant`, `tool`. Content is a string or a
  nonempty array of text parts (joined with newlines); valid UTF-8, no NUL. No
  image parts. A real user message must exist. Assistant content may be null
  when carrying tool calls. Message `name` is optional and validated.
- `max_tokens`: integer 1–4096, default 128. `max_completion_tokens` is an alias;
  sending both is refused. `store:false` is accepted; `store:true` is refused. Physical rendered prompt plus output
  budget must fit configured context (128–32768, default 4096). No silent
  truncation. Template/tokenization/context refusal precedes forward.
- `temperature`: omitted defaults to greedy zero; numeric 0–2 selects the
  per-sequence sampler. `top_p` defaults to 1 and accepts >0–1. Frequency and
  presence penalties accept −2–2. Optional nonnegative `seed` initializes the
  per-sequence draw state; omission selects provider entropy for stochastic draws.
- `stream`: boolean, default false. `stream_options` may contain only boolean
  `include_usage` and only for a streaming request.
- `chat_template_kwargs` may contain only `enable_thinking:false`; thinking is
  disabled even when omitted. Rendering/tokenization uses the pinned upstream
  Qwen implementation inside the adapter, after GGUF template validation.
- `tools`: up to 128 OpenAI `type:function` definitions with name, optional
  description and object parameter schema. No server-side execution. Explicit
  `strict:true` is refused: no constrained-sampling or full JSON-Schema guarantee.
- `tool_choice`: `auto` (default), `none`, `required`, or a named function object.
  Named choice renders only the selected declaration; required/named turns must
  actually generate a valid call. `parallel_tool_calls:false` rejects multiple
  generated calls rather than executing a partial set.
- Assistant `tool_calls` carry nonempty unique IDs, `type:function`, function
  name and JSON-object arguments encoded as a string. Tool messages must match
  unresolved IDs (and name if supplied); all calls require results before the
  next non-tool message. Orphan, duplicate, missing and mismatched results are
  refused before forward. Up to 16 calls per turn, 128 IDs in history and 128
  parameters per call. Names match `[A-Za-z_][A-Za-z0-9_.-]{0,127}`; IDs are at
  most 128 UTF-8 bytes. Reserved Qwen argument delimiters are refused.
- Temperature 0–2, top_p >0–1, frequency/presence penalties −2–2 and
  nonnegative seed configure the per-sequence sampler.
- Unknown fields, custom/non-function tools, images, arbitrary stops, logprobs
  and invalid/unsupported sampling are errors, not ignored options.

Malformed/unsupported requests are 400; bounded overload is 429. Preparation
failures are 400 `invalid_request`; backend failures before headers are 503
`inference_failed` with a diagnostic message. This is an OpenAI-shaped subset,
not blanket compatibility. Each request creates a fresh session. Supplying prior
messages re-prefills history; structured tool continuation is supported, but it
is not retained session/prefix state.

### Output and cancellation

Nonstream returns `chat.completion`, one assistant message, `stop`/`length` or
`tool_calls` and usage. SSE uses close-delimited `text/event-stream`, an initial role delta,
ordered content deltas, a finish delta, optional usage-only chunk (`choices:[]`),
then exactly one `data: [DONE]`. No enqueue-only/speculative output is exposed.
`system_fingerprint` names the provider, including `NOT-INFERENCE` in fixtures.

When tools are declared (including choice `none`), **the entire response is
buffered** after the initial SSE role. Native Qwen calls are parsed/validated in
C17 before any executable tool delta is published. A valid response contains
`tool_calls` with stable ID, function name and JSON-string arguments; SSE adds
consecutive zero-based indices. String values preserve significant whitespace;
other typed arguments use JSON. Basic type/required/additional-property checks
are enforced, but the client must validate its full tool schema. Valid calls
finish with `tool_calls`; partial/malformed, unlisted or disabled calls and
budget-truncated call turns fail with JSON 502 `invalid_tool_output`, or an SSE
error/DONE after headers, never success/usage/tool deltas. No parser repair or
retry. Ordinary text with no recognized call can still finish `length`.

Tool-enabled turns return flow credit as their bounded aggregation buffer is
filled, not as individual network tokens drain. This is not argument-level
streaming or the old text-stream backpressure profile. Model generation may be
complete even when subsequent protocol validation fails. Those failures increment
`llm.responses.tool_errors`; they do not poison a numerically healthy executor.
All tools are executed by the requesting client, never by this server.

Token byte boundaries need not be UTF-8 boundaries. One streaming decoder retains
up to three pending bytes and applies replacement decoding to invalid/incomplete
sequences, including at length/EOS. Nonstream uses the same decoder. Output byte
normalization is not a numerical oracle; model tokens/frontiers require separate
qualification. Usage counts physical prompt tokens and executor-confirmed emitted
tokens; the provider's un-emitted stop token is not an emitted output token.

Before token lookup/publication, the C worker validates emitted/stop ranges,
progress, vocabulary and exact completed position (`previous + emitted`, also
for un-emitted EOS). A reported text length must fit the reserved slot. Invalid
successful returns and unexpected executor/text failures mark the worker FAILED,
fail admitted peers and refuse subsequent requests. No retry or fallback; failed
frontiers cannot create usage/timing success or advance generated-token counters.
Cancellation remains nonpoisoning. See [T0-LIFECYCLE.md](T0-LIFECYCLE.md) for the
synthetic fault coverage and the separate original-weight target lifecycle run.

After headers, backend errors are an SSE JSON error followed by `[DONE]`, **not**
a successful finish reason or fabricated usage. Already submitted bytes cannot
be revoked. Disconnect/deadline closes output, latches flow and executor
cancellation, and retires existing work and writes. No completion is sent to the
disconnected client. Cancellation is a latch, not HIP preemption.

The worker owns blocking model calls. Cancellation's atomic backend latch is
protected against concurrent sequence destruction by a short job gate. Worker
and transport references are independent; poll close and write callbacks retire
before the consumer reference is released. A cancelled output flow can become
terminal before a prefill call returns; that terminal is not a sequence-retirement
ACK. The worker reference still pins the job/session and its storage, and the
worker drains/closes sequences before dropping its reference. SIGINT/SIGTERM waits for owned work retirement.
An undrainable loaded-runtime GPU failure terminates the process with exit 70;
no retry/fallback/core dump. That hardware error path remains unqualified.

### Per-request executor timings

Successful JSON completions include a top-level `lie_timings` object. SSE includes
it **once on the successful finish delta**, independent of `include_usage`; the
optional usage-only chunk remains unchanged. Content/role chunks, error terminals,
cancelled requests and pre-admission failures do not carry successful timings.
The extension does not change `usage`, content, finish reasons or the single DONE.

Schema `synapse-lie.request-timings.v1`, scope `synchronous_executor_calls`:

| Field | Meaning |
|---|---|
| `valid` | False if a monotonic-clock read fails, is malformed/regresses within a call, or accumulated nanoseconds overflow |
| `prefill_tokens` | Successfully completed physical input deltas, not repeatedly counted cumulative prefixes |
| `decode_tokens` | Confirmed emitted tokens, equal to completion usage on success |
| `prefill_calls`, `decode_calls` | Returned synchronous executor calls; decode includes un-emitted EOS detection |
| `prefill_ms`, `decode_ms` | Sum of `CLOCK_MONOTONIC` wall intervals around the respective executor calls |
| `prefill_tokens_per_second`, `decode_tokens_per_second` | Corresponding tokens divided by measured time; null when duration is zero or invalid |

On invalid timing, **both** durations and rates are null, not fabricated zero or
client-time substitutes; counts remain known. This telemetry failure alone does
not poison inference or trigger a retry. Zero emitted tokens with positive valid
decode duration has rate zero, and the EOS detection call remains in the time.

Calls include required provider synchronization, sampling and transfers. No new
GPU barrier is added. The sums exclude rendering/tokenization, session creation/
retirement, token-text decoding, metadata/flow handling, queueing, other jobs,
credit/backpressure waits and HTTP writes. Tiny clock/call-boundary overhead is
unavoidable. These are **not GPU kernel time, whole-request latency, TTFT, cohort
throughput or a remote-delivery measurement**. A slow client can extend request
latency without directly adding its waiting time to these rates; external CPU/GPU
contention during a call still affects its wall time.

The worker publishes timings and output accounting before the flow can publish
a successful terminal. Partial worker snapshots can contain completed work only;
in-flight work is not counted until the call returns. On failure/cancellation,
internal call counts may include the failed/cancelled return, but no successful
HTTP timing/usage record is produced. No prefix cache exists: completed successful
prefill tokens currently equal the full physical prompt count.

This increment is tested with CPU executor/clock fixtures (including chunk sums,
EOS, queue/credit exclusion, in-flight cancellation, faults, zero resolution and
clock errors/overflow). `t0-model-lifecycle-r1` additionally validates counts,
finite durations/rates and JSON/SSE placement on the original-weight GPU path.
That short lifecycle run is not a throughput benchmark. `/actuator/llm` aggregate
throughput/latency remains null; per-request values are not a percentile histogram.
See [the benchmark direction](BENCHMARKING.md).

## Standalone monitor

C libcurl/json-c monitor; default `http://127.0.0.1:19880`. It validates discovery,
info/readiness, metric details and Prometheus, with response/depth/time bounds.

- `check`: exit 0 means contract valid, not hardware qualified. `--require-ready`
  exits 3 when readiness is unavailable.
- `watch`: bounded duration/interval, 32-sample history, deterministic English.
- `record`: exclusive new JSONL file, schema/source/instance/UTC/monotonic times
  and delta status; no prompts. fflush is not power-loss durability.
- `check --file snapshot.json`: one recorded object, not a complete JSONL stream.

Exit 1 is transport/contract failure; 2 usage; 3 required readiness unavailable.
Partial logs are retained. A scrape may take multiple bounded HTTP timeouts;
duration does not interrupt an in-progress scrape. Endpoint reads are not atomic;
a lifecycle transition can require a retry, not reinterpretation as zero.

Rate is cumulative-confirmed-token delta / monotonic interval. First sample,
instance/uptime/counter regression or layout change produces null / `n/d`. An
unchanged counter after valid samples is zero. Percentiles are not implemented.
The C and independent Python Prometheus subset parsers are checked; promtool
was absent, so official validation is not claimed. No service is installed.
The diagnostics page is not a finished 64-locale release GUI.

Stateless `/v1/responses` text/functions use the same reactive worker/flow;
see [Responses events and current limits](OPENAI-REACTIVE.md). Encoded network
writes are bounded to 32 MiB, including repeated final Responses projections.
