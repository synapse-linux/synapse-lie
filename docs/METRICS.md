# Actuator / Micrometer-inspired contract v1 (implemented subset)

This is a C registry and an Actuator v3 JSON shape, not a JVM or a full Spring
implementation. The official Actuator reference and Micrometer timer source
were retrieved; URLs, hashes and timestamps are in local evidence. Default
management listener: `127.0.0.1:19880`.

## Registry

Types: Counter (nonnegative increments), Gauge (explicit sampled value), Timer
(nonnegative finite seconds). Logical names use lower-case letters/digits,
underscores/dots; labels use lower-case letters/digits/underscores. `le` and
`__*` are reserved. Descriptions, units and tags are copied and owned. Values
are controlled at instrumentation sites, never prompt/request/conversation IDs.
Capacity is 32 metric families / 128 series / 4 tags / 12 finite histogram
bounds, explicit compile-time safety limits, not inference concurrency limits.

A metric name fixes its type, description, unit, tag-key set and histogram
configuration. Registration with reordered tag pairs returns the same series
handle; conflicting metadata/key sets or Prometheus name/suffix collisions are
refused. Families/series have registry lifetime; no stale handles from eviction.
Registration, updates and snapshots are mutex-protected. Shutdown must join all
registry users before destruction. JSON/export serialization runs on a detached
copy, not under the mutex. No GPU call or hardware query occurs in a scrape.

Counters/counts and finite bounds accumulate since process start; no per-request
reset. Counter growth beyond exact double integer range is refused. Invalid,
negative or nonfinite updates do not change the series. Timer sum overflow is
refused. Gauge aggregation overflow returns an error, not invalid JSON.

Timer MAX: three rotating 60-second buckets on the monotonic clock, maximum of
all nonexpired buckets. A recorded maximum lives between 120 and 180 seconds
according to its position in the rotation; after 180 seconds without new
observations it is zero. This is the declared Micrometer-style expiry=60s,
bufferLength=3 bounded maximum, not lifetime MAX and not an exact rolling
180-second event log. Count, sum and histogram buckets do NOT expire with MAX.

## Actuator JSON

`GET /actuator/metrics` -> `{"names":[...]}`.

`GET /actuator/metrics/{name}?tag=backend:hip&tag=model:qwen` uses AND filters.
URL-encoded colon and values are accepted. Duplicate keys/malformed filters are
400. Unknown metric or no matching series is 404. Only repeated `tag` parameters
are accepted. The result contains `name`, `description`, `baseUnit` (null if
unset), `measurements` and `availableTags`. Filtered keys are omitted from
availableTags; remaining values come only from matching series.

- Gauge: `VALUE`, sum of selected series.
- Counter: `COUNT`, sum of selected series.
- Timer: `COUNT` and `TOTAL_TIME` summed; `MAX` is the maximum of selected maxima,
  not their sum. Timer baseUnit is `seconds`.

JSON is `application/vnd.spring-boot.actuator.v3+json`. It does not contain
histogram buckets or invented p95 values. Header behavior is documented in
HTTP.md; no blanket Actuator compatibility claim.

## Prometheus mapping

Replace dots with underscores. Timer adds `_seconds`; bytes/seconds units add
that suffix to other types unless already present. Other units remain metadata.
Counter adds `_total`. Timer count/sum/max/bucket namespaces are reserved against
other meters, even when buckets are disabled.

Examples:

| Logical name/type | Prometheus series |
|---|---|
| llm.tokens.generated / Counter | llm_tokens_generated_total |
| llm.requests.active / Gauge (future) | llm_requests_active |
| llm.request.duration / Timer (future) | llm_request_duration_seconds_count, _sum, _max, _bucket |

Counter/Gauge have HELP/TYPE plus samples. Timer with bounds has TYPE histogram,
cumulative `_bucket{le="..."}` including `+Inf == _count`, `_count`, `_sum` and
separate TYPE gauge `_max`. Without bounds it uses TYPE summary for count/sum
(no quantiles) and a separate max gauge. Labels escape `\\`, quote and newline;
HELP text escapes backslash/newline. No exemplar/timestamp/OpenMetrics claim.
Content-Type is exactly `text/plain; version=0.0.4; charset=utf-8`.

## Instrumentation actually wired now

| Name | Type/unit | Tags | Update point |
|---|---|---|---|
| runtime.uptime | Gauge/seconds | none | 250ms CPU loop tick, monotonic since start |
| runtime.ready | Gauge/dimensionless | none | model/executor open and non-poisoned; zero without model; worker notification / loop tick |
| http.connections.active | Gauge/connections | none | accepted TCP connection / completed close callback |
| http.server.requests | Timer/seconds | method=GET,POST,OTHER; status=2xx,4xx,5xx | from TCP accept until response enqueue (NOT network write completion); bounds .001,.01,.1,1,5,+Inf |
| llm.requests.rejected | Counter/requests | reason=backend_unavailable,queue_full,invalid_request | framed request refused at HTTP admission |
| llm.tokens.generated | Counter/tokens | none | worker's successful bounded decode/text results, sampled into registry on the 250ms loop tick; zero without model |
| llm.responses.tool_errors | Counter/responses | none | completed generation rejected by C17 tool-output validation; no request/tool-name labels |

A scrape's own HTTP timer is updated after its snapshot; different endpoint
responses are not a cross-request atomic transaction. Incomplete/time-expired
connections do not enter the response timer. These are truthful, deliberately
limited metrics, not substitutes for inference latencies. Streaming records
first header/role enqueue, not TTFT or stream duration; nonstream records final
response enqueue. Runtime readiness is not hardware/quality qualification.

The worker summary reports queued/active and completed/cancelled/failed generation
outcomes. These are not client receipt counters: transport may abandon queued
output after generation completed. Confirmed-token count can include later
abandoned queued output; executor-suppressed late cancellation is not counted,
nor is un-emitted EOS. Tool protocol validation occurs after generation:
`completed` can therefore coexist with an increment in `llm.responses.tool_errors`.
Such protocol failures suppress successful HTTP usage/timings/tool deltas, but
do not poison the executor or erase work already completed. This is not a GPU
compute-work or client-delivery meter.

Synthetic test executables have explicitly synthetic provider identity and may
exercise these counters. Their values never constitute inference throughput.
Original-weight observations are retained in [T0-LIFECYCLE.md](T0-LIFECYCLE.md),
the later tool/Responses checks in [OPENAI-GPU.md](OPENAI-GPU.md), and the shared
batch dispatcher measurements in [REACTIVE-INFERENCE-RESULT.md](REACTIVE-INFERENCE-RESULT.md).

## Required inference instrumentation (pending, not emitted as fake zero)

At admission: accepted/rejected counters, active/queued gauges, input tokens.
On worker start: queue duration. TTFT starts at full HTTP request admission,
including tokenization and queue time, ends at first confirmed token ready for
output. Separately measure first actual SSE write and inter-emission gaps.
A speculative step may emit multiple tokens; SSE spacing is not per-token time.

On completed steps: prefill/decode durations and processed tokens, executor step
and batch-size distributions; on terminal outcome: request duration/completion,
cancellation and deadlines exactly once. Separate drafted/accepted tokens and
cycles/cost; AR is the reference. Zero/one-token requests produce no invalid
inter-token division.

On backend allocation/accounting snapshots: weights, active state, retained
prefixes, workspace, MTP/rollback and I/O buffers (shared RAM, no double count).
On cache/store events: hit/miss by RAM/SSD, eviction, failed/incompatible restore,
read/write bytes, save/restore duration and occupancy/budget. On queues/network:
backpressure, output bytes, paused rows and disk queue depth.

Add these meters only with real update sites. Future percentile estimates must
use interval histogram deltas with a documented window and bucket interpolation;
no p95 is implemented or claimed today. Instrumentation overhead has not been
benchmarked on inference.

Responses uses the same admission/invalid-request counters, tool-output error
counter, worker generation and retirement counters as Chat Completions. Wire
text deltas/done projections are not additional generated tokens. Sampling
options configure per-sequence draw state; they do not redefine physical token
usage or executor-call timing. No modality or reactive-speedup meter is invented.

## Reactive inference dispatch

The scheduler mode is `single-owner-reactive-ready-batch`. `max_active` admits
1..8 independent sequences; `native_batch_capacity` reports allocated adapter
capacity. `decode_started/returned` count dispatch calls, including a shared
batch once. `decode_batches` counts calls with more than one selected row,
`decode_batch_rows` sums those selected rows, and `decode_single_calls` counts
scalar calls. These are dispatch observations, not successful-token counts;
`generated_tokens` retains validated completed output accounting. Cancellation
during dispatch counts each affected request once, and cannot prove kernel
preemption.

Each participating request receives one completed decode call and the shared
call duration. Per-request durations overlap; summing them is not GPU elapsed
time or aggregate throughput. Credit stalls, prefill peers and network writes
remain excluded. The benchmark reports aggregate confirmed tokens over a common
wall interval, including the C inference dispatch and its flow bookkeeping.
