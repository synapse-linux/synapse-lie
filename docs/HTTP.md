# HTTP / SSE and monitor contract — T0 candidate

The optional real provider is linked, not hardware-qualified. CPU transport tests
use a separate, clearly labelled synthetic executable. No model is configured by
default and no synthetic provider can be selected in `synapse-lie-server`.

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
batching, tools, MTP and snapshot restore are explicit. `hardware_qualified:false`
and `inference_verified:false` are not changed merely because a request succeeded.
Readiness is operational model/executor open, not a quality certificate. No probe
inference, device synchronization or filesystem scan occurs in a health/scrape.
The model loads on the worker; loading/failed/unconfigured instances stay unready.

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

- 64 connections; 16 KiB header field/value bytes, 64 KiB body, 2047-byte target;
  additional total-wire bound, including chunking overhead.
- At most 1 MiB per response/write buffer. Eight admitted jobs (queued plus
  executing); overflow 429. One active sequence by default, optionally two.
- Eight 256-byte token slots per flow. The pinned vocabulary's documented maximum
  rendered entry is 128 bytes; the larger slot is checked before publication.
  UTF-8 expansion and JSON/SSE writes are independently bounded.
- One outstanding uv_write per connection. Request 16 KiB socket send buffer
  (kernel actual size/overhead is platform-defined); local write completion is
  not remote consumption. Nonstream aggregate bound is 393224 bytes, independent
  of socket capacity. Retired jobs/output remain bounded by live connections.
- Five-second accept-to-close deadline for control/incomplete requests. Admitted
  inference uses accept-to-close `--request-timeout-ms`, default 120000,
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

- Required exact configured `model`; 1–32 messages with only `role` and string
  `content`. Roles: `system`, `user`, `assistant`; valid UTF-8, no embedded NUL.
- `max_tokens`: integer 1–512, default 128. Physical rendered prompt plus output
  budget must fit configured context (128–32768, default 4096). No silent
  truncation. Template/tokenization/context refusal precedes forward.
- `temperature`: omitted or numeric zero only. Optional nonnegative integer
  `seed` is accepted but unused by greedy sampling. No stochastic/penalty controls.
- `stream`: boolean, default false. `stream_options` may contain only boolean
  `include_usage` and only for a streaming request.
- `chat_template_kwargs` may contain only `enable_thinking:false`; thinking is
  disabled even when omitted. Rendering/tokenization uses the pinned upstream
  Qwen implementation inside the adapter, after GGUF template validation.
- Unknown fields, tools, images, arbitrary stops, logprobs, alternative output
  controls and unsupported sampling are errors, not ignored options.

Malformed/unsupported requests are 400; bounded overload is 429. Preparation
failures are 400 `invalid_request`; backend failures before headers are 503
`inference_failed` with a diagnostic message. This is an OpenAI-shaped subset,
not blanket compatibility. Each request creates a fresh session. Supplying prior
messages re-prefills history; it is not retained tool/session/prefix continuity.

### Output and cancellation

Nonstream returns `chat.completion`, one assistant message, `stop`/`length` and
usage. SSE uses close-delimited `text/event-stream`, an initial role delta,
ordered content deltas, a finish delta, optional usage-only chunk (`choices:[]`),
then exactly one `data: [DONE]`. No enqueue-only/speculative output is exposed.
`system_fingerprint` names the provider, including `NOT-INFERENCE` in fixtures.

Token byte boundaries need not be UTF-8 boundaries. One streaming decoder retains
up to three pending bytes and applies replacement decoding to invalid/incomplete
sequences, including at length/EOS. Nonstream uses the same decoder. Output byte
normalization is not a numerical oracle; model tokens/frontiers require separate
qualification. Usage counts physical prompt tokens and executor-confirmed emitted
tokens; the provider's un-emitted stop token is not an emitted output token.

After headers, backend errors are an SSE JSON error followed by `[DONE]`, **not**
a successful finish reason or fabricated usage. Already submitted bytes cannot
be revoked. Disconnect/deadline closes output, latches flow and executor
cancellation, and retires existing work and writes. No completion is sent to the
disconnected client. Cancellation is a latch, not HIP preemption.

The worker owns blocking model calls. Cancellation's atomic backend latch is
protected against concurrent sequence destruction by a short job gate. Worker
and transport references are independent; poll close and write callbacks retire
before the consumer reference is released. The worker drains/closes sequences
before dropping its reference. SIGINT/SIGTERM waits for owned work retirement.
An undrainable loaded-runtime GPU failure terminates the process with exit 70;
no retry/fallback/core dump. That hardware error path remains unqualified.

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
