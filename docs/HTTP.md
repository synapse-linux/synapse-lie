# HTTP and monitor contract — development increment

## Management listener

| Route | Current behavior |
|---|---|
| GET /actuator | `_links` discovery, relative hrefs and templated flag |
| GET /actuator/health | 503 `OUT_OF_SERVICE`, model `UNKNOWN`/`NOT_LOADED` |
| GET /actuator/health/liveness | 200 `UP` while the event loop is serving |
| GET /actuator/health/readiness | 503, same unavailable executor state |
| GET /actuator/info | application/version/process-instance ID, backend null, inference_verified false |
| GET /actuator/metrics | metric names |
| GET /actuator/metrics/{name} | detail and repeatable `tag` AND filters |
| GET /actuator/prometheus | Prometheus text 0.0.4 |
| GET /actuator/llm | versioned summary; unavailable scheduler/memory/cache/speculation/latency/throughput are null |
| GET /monitor | embedded development HTML/CSS/JS, loopback same-origin fetch, no CDN |

Readiness will eventually reflect lifecycle/model health, not change simply
because the GPU is busy. No probe inference or global device synchronization
occurs on a health/scrape request. There is currently no loaded backend at all.

Normal Actuator responses use the v3 vendor Content-Type. Protocol errors use
`application/json` with `error.code` and `error.message`. There is no content
negotiation; even an OpenMetrics Accept does not make the server emit OpenMetrics.
Responses include Content-Length, Connection: close, no-store, nosniff and a
restrictive CSP. A `.txt` Content-Disposition workaround from Spring is not
implemented; metric names are not filesystem paths. No host-derived absolute
URLs are generated. Unknown routes: 404; unsupported management method: 405.

Initial transport subset: IPv4 HTTP/1, one request per connection, no pipelining,
upgrade, TLS, compression, authentication or keepalive. llhttp handles framing,
including refusing ambiguous lengths; request bodies/headers/wire bytes are
bounded. Limits: 64 concurrent connections, 16KiB header field/value bytes,
64KiB body, 2047-byte target, 1MiB response, 5s total connection deadline.
Closing on deadline or disconnect frees memory only through libuv completion
callbacks; there is no GPU work to cancel in the current server.

## API listener

- `GET /v1/models`: `{"object":"list","data":[]}`.
- `POST /v1/chat/completions`: 503 `backend_unavailable`, before starting SSE.
  Framing/body-size validation works; model-specific JSON validation, generation,
  normal chat output, SSE, tool calls and multi-turn continuation are NOT wired.
- Management routes are not available here, nor model routes on management.

Do not advertise OpenAI-compatible inference based on these two reserved routes.
When real streaming is implemented, post-header failures must become a defined
SSE error terminal event; no unconfirmed speculative token may be emitted.

The required feedback is not simply `uv_write` callbacks: a per-sequence
subscription must reserve both token demand and bounded output storage before
new decode dispatch; write completion retires a buffer loan and may grant more
credits. Disconnect/deadline cancellation bypasses data capacity, while in-flight
work and writes retain their storage until completion. `lie_flow` now implements
the CPU primitive, **not this HTTP/SSE binding**. See [REACTIVE.md](REACTIVE.md)
for ordering, cancellation races, terminal signals and remaining qualification.

## Standalone monitor

Uses libcurl and json-c, no Prometheus service or Python runtime. Default URL
`http://127.0.0.1:19880`; timeouts and response/depth limits apply. It fetches
Actuator discovery/info/readiness, metric names and every registered detail, then
Prometheus. Vendor JSON/type, required metric shape, statistics and readiness
are validated. Transport errors, missing data and invalid export are not zero.

- `check`: one validated snapshot. Exit 0 means contract valid, not model ready.
  `--require-ready` produces exit 3 for a healthy control plane without a model.
- `watch`: bounded acquisition (`--duration`, `--interval`) and terminal rows,
  with a 32-entry in-memory history; no terminal framework required.
- `record`: same acquisition, JSONL snapshots with schema, source, instance,
  UTC record time, monotonic time, elapsed time and delta status. `--output`
  requires a new file; existing logs are never overwritten. fflush per record,
  not power-loss durability. It records metrics, not prompts or credentials.
- `check --file snapshot.json`: validate one recorded object offline.

Exit 1: transport/format/contract failure. Exit 2: usage. Exit 3: requested
readiness unavailable. Partial JSONL is retained on error. A complete sample
can take several bounded HTTP timeouts; duration is not a hard interrupt of an
already running scrape. Ctrl-C uses normal process termination; history is not
persistent unless recorded. CLI is fixed US English; numeric locale is C.

Confirmed-token rate is delta cumulative tokens / monotonic sample interval.
First sample, instance change, uptime regression, token counter decrease or
series/label/bucket-layout change produces null / `n/d` rather than a spike.
An unchanged counter after two valid samples is genuinely zero. No percentile
or generic rate for every metric is computed yet. Polling different endpoints
is not atomic; a readiness transition detected as inconsistent requires retry.
The current runtime has no such transition because inference is unavailable.

## Independent export checks

The C monitor parser is independent of the exporter: bounded names/label grammar,
escaping, duplicate series, finite values, cumulative histogram order, required
series, +Inf/count and sum presence. It is a **restricted contract validator**,
not a complete Prometheus parser or PromQL evaluator (e.g. full HELP/TYPE family
semantics are not yet checked). CPU integration tests also use a separate Python
stdlib parser. If installed, tests invoke `promtool check metrics` on the actual
scrape. promtool was absent in the initial environment: that independent official
check is recorded as NOT_INSTALLED, not passed. No dependency was installed.

The embedded page is an en_US development fallback with 30 snapshots, not a
finished/localized dashboard; unavailable inference values remain null. The
workspace's 64-locale graphical release gate is still open.
