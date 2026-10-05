# Actuator / Micrometer-inspired contract v1 (implemented subset)

`dense_sampling` is a build/backend identity in actuator and benchmark metadata,
not a timer, counter or proof of GPU execution. Values distinguish the owned
C17 dense selector, Gufo control, unavailable backend and synthetic fixture.
It changes no inference-worker count or existing timing/count semantics.

The `1bff953` [Point GPU receipt](../development/validation/c17-sampling-point-gpu-2026-10-05.json)
records 37 AR/37 MTP controls and six fixed-TG128 sessions. Up to 44 observed
process threads include provider/runtime helpers; this is not a reactive-worker
count or speedup claim. Native `--progress-ms` snapshots are emitted on stderr,
independently of final measurement JSONL. `prefill_started`/`prefill_returned`
and confirmed per-job token counts remain progress, not completion or a finished
throughput sample. Sampled GTT/temperatures are observational resources, not
allocation-exact or device-fault qualification.

The C17 compiled-schema cache adds no HTTP metric, inference worker or timing
claim. Its optional inspection reports resident entries and key bytes only;
opaque handles, programs and transient insertion storage are excluded. Matching
allocation-exact resources and cost remain separate qualification gates.

The new sampler-history extraction adds no counter/timer or worker. Its selected
source/header/glue and exact integration recipe are bound in the provider build
receipt; this does not extend older dense-selector GPU qualification to history.
The new compact/speculative probability extraction likewise adds no worker or
metric. Its additional source/header/glue and exact recipe are receipt-bound;
`dense_sampling` still identifies the dense selector, not complete sampler or
model ownership. Caller storage includes transient bulk and probability scratch;
allocation-exact provider cost remains a separate gate. The new byte-grammar
runtime adds no worker or metric; its copied program tables, owned snapshots
and vector marshalling are extra bounded storage, still requiring measured
allocation-exact resources and matched cost. Schema/predicate/trie/cache
ownership is not implied by `dense_sampling`.

Numeric grammar extraction adds no metric or worker. Its copied policy and
per-call arithmetic workspace count as additional bounded allocations. The
current 45-file provider inventory and numeric edit recipe bind its selection;
`dense_sampling` does not identify complete grammar/compiler ownership. Actual
allocation cost and original-weight GPU comparisons remain separate gates.

The Unicode extraction adds no metric/worker. Copied DFA tables, unique graph
edges and optional reachability scratch are owned C allocations. The provider
retires transitional construction vectors after sealing; this is not a measured
GPU memory or speed claim. State canonicalization touches only a copied mask key.
The 45-file inventory and owned recipes bind the source selection. Vocabulary
trie/transition/cache policy and regex expression/derivative/partition/BFS
algorithms and regex syntax/assertion expansion are now C17. Unicode-set registry,
range translation and input buffers are C17 using ICU C APIs. ICU remains the
property/set/conversion dependency; JSON Schema compilation and provider container
storage remain transitional. Snapshot bridge planning/validation/copies use C17.

Vocabulary queries expose optional local counters for visited nodes, advances,
interned states (including dead/input slots), direct nodes, transition hits and
peak depth. These are not new
HTTP metrics or inference worker counters. Failed queries leave caller counters
unchanged. Fixture allocator peaks count requested payload only; they do not
establish whole-process allocations, GPU memory fit or provider latency.

Regex compilation adds no HTTP metric or inference worker. Its counted work
budget is a construction admission limit, not elapsed time or throughput.
Expression/derivative hash tables and temporary partition/BFS storage belong to
the C17 compiler. Fixture allocator peaks exclude helper headers, the provider,
whole-process and GPU allocations; original-weight resources and cost remain
separate gates.

Parser AST/expansion vectors are bounded C17 transient allocations and are retired
on success/refusal. The Unicode context owns UTF16 input, handles and registry arrays; ICU
allocates its own set internals. Own allocator hooks exclude ICU allocations. Counted work and fixture peaks do not establish whole-process
cost, GPU fit or speedup. No HTTP metric or inference worker is introduced.

Snapshot bridge planning adds bounded transient C storage for writable frame
views and input/output intervals. Heap-sort work is a construction budget,
not timing or throughput. Import states retire on any callback refusal;
private provider vector/string staging retires at the exception boundary.
No inference worker, HTTP metric or DS4 tensor/cache identity changes. Actual
whole-provider allocation cost and GPU continuation remain separate gates.

Grammar construction adds bounded C rule/class/table and
productivity/cycle scratch allocations. Its 64-million-unit default work budget
is admission accounting, not elapsed time or throughput. The provider retains
private composition templates, schema dispatch and private composition caching and leaf translation. The independent
fixture peak counts requested owned payload only, excluding helper headers,
provider/ICU/process/GPU allocations. No new HTTP metric or inference worker
is introduced; original-weight allocation-exact cost remains unqualified.

Schema equality/reference/conjunction adds bounded C scratch and private provider
staging, with no HTTP metric or inference worker. Sixteen inline equality pairs
avoid heap storage for small comparisons; larger frontiers use bounded growth.
The 64-million-unit work limit is a refusal budget, not timing or throughput.
Own allocator checks exclude provider/ICU/process/GPU allocations. Original-weight
allocation-exact resources and matched cost remain separate gates.

Finite-value/container construction adds a separate bounded C scratch stack,
quoted-byte/symbol buffers and required-name sorting. Sixteen inline traversal
frames avoid scratch allocation for shallow values; deeper values grow only
up to their declared limit. Shared property/character counts include nested
visitor work. Callback staging, cached predicates, binary-double serialization
and builder allocations have distinct ownership; the C refusal checks do not
measure their whole-process cost. This adds no inference worker or HTTP metric,
and its 64-million-unit work budget is not elapsed time or throughput.

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

Job terminal state/output notification and aggregate core retirement counters
are separate publications. A terminal job snapshot does not promise that a
simultaneous core snapshot already includes its completion/cancellation delta.
Clients checking retirement must consume core notifications and wait within
their deadline for the counters; the direct reactive probe does so while
preserving the held output loan. No additional inference worker is introduced.

Synthetic test executables have explicitly synthetic provider identity and may
exercise these counters. Their values never constitute inference throughput.
Original-weight observations are retained in [T0-LIFECYCLE.md](../archive/T0-LIFECYCLE.md),
the later tool/Responses checks in [OPENAI-GPU.md](../archive/OPENAI-GPU.md), and the shared
batch dispatcher measurements in [REACTIVE-INFERENCE-RESULT.md](../archive/REACTIVE-INFERENCE-RESULT.md).

## Required inference instrumentation (pending, not emitted as fake zero)

Engine counters, resource accounting and execution snapshots belong to the
shared C core, regardless of whether HTTP, benchmark or a future chat/eval client
submitted the job. JSON/Prometheus serializers and transport counters are client
projections. Current `lie_core_snapshot` and `lie_job_snapshot` expose the same
execution counters/durations to direct clients and HTTP. `--suite core` measures
client wall time from before submit to observed output/terminal and labels it
separately from per-job prefill/decode call time. It includes copying, preparation,
queueing, inference and consumption; its first-token clock is not first SSE write.
An internal core queue-duration clock and complete resource accounting remain
pending. Direct-core and HTTP results must label these different timing scopes.

`lie_job_info.output_token_limit` records the generation budget resolved after
full prompt preparation; zero means the job is not prepared yet. A direct
`max_tokens=0` or omitted/null HTTP limit selects min(remaining context, the
existing 4096-token engine ceiling). Explicit limits remain exact. This is a
budget, not an executed-token count; EOS, stop and cancellation may end earlier.
Chat projects it as `lie_timings.output_token_limit`; completed Responses and
stored replay use `max_output_tokens`. Model list/detail metadata advertise
configured `context_length` and the engine `max_output_tokens` ceiling so an
evaluation client can discover its actual limits.

The native direct-core client can sample these metadata with `--progress-ms N`.
Its stderr JSONL schema `synapse-lie.core-progress.v1` records per-job completed
prefill tokens/calls, cached tokens, confirmed model output, consumer-observed
tokens and executor-call durations. Global execution phase and started/returned
counters come from the core snapshot; each job has its own metadata lock, so
the collection is not a single atomic snapshot across all jobs. An in-flight
call contributes no new completed-input count until it returns successfully.
A failed call can increase the returned-call count with zero completed input.
`final_snapshot` marks the client's last observation before job release, including
deadline/failure; `retired` separately reports the job's retirement state.
These observations are not the credit-bearing `LIE_EVENT_PROGRESS` output event,
GPU kernel clocks or benchmark samples. Interval `0` disables them by default.
Result identity records `progress_interval_ms`; paired native reports require
the same value, treating a missing historical field as zero.

Independent steering-policy snapshots report completed retained target positions,
revision, effective history epochs, at most two outstanding plans, policy bytes
and staged bytes. The shared bank's vector bytes are separate. These are host
policy/resource metadata, not executed-token counters, GPU timing or evidence
that a numerical steering edit occurred. `lie_job_steering_snapshot` projects the
latest owner-confirmed policy, submitted/completed tickets, pending status,
application status and retained application position. The semantic image scope
is separate from the combined scope. The retained-request HTTP `/steering`
extension projects these snapshots without waiting for inference. Its optional
`/{choice}` suffix identifies one independent child. `schedule` reports a
creation-time plan's declared scales, attempted/applied status, actual positions
and terminal completion; an unreached step has a cancellation status and null
actual position. Extra stored-choice retention is charged to the record budget
only with an admitted bank. Native core
identity carries the complete binary32 scale schedule; every planned job reports
attempted/applied steps, actual positions, final scales and confirmed history/scope.
Optional progress includes the same schedule snapshot. Reports refuse unfulfilled
or crossed steps and compare the complete plan, treating absent historical plans
as empty. These host projections do not qualify numerical changes.
[Core/provider/cache binding](../development/STEERING.md).
The direct C model query reports immutable bank geometry/host vector bytes and
the private provider's owned device vector allocation separately from model
weights; allocator overhead and workspace are not included. The sequence query
reports the C17 policy metadata. `lie_core_steering_snapshot`, the backend's
`steering` object in actuator info/LLM snapshots, and native `core_ready.steering`
project the READY model admission. `host_vector_bytes` and `device_vector_bytes`
are vector-data counts, not allocation peaks or additions to reported weight
residency. Bank file/geometry hashes and initial FFN/attention scales identify
the admission; a synthetic fixture correctly reports zero device bytes.
No public GPU steering counters or performance
samples are qualified by the activation descriptor or syntax checks.
The 192-byte policy metadata serializes semantic history/scales/frontier only;
it does not restore source revision, capacity, allocation or executed-token
counters. A restore uses the destination's capacity and advances its own local
revision once. Typed policy/scope tails use ordinary retained RAM/SSD accounting;
the source binding adds no tensor scratch copy or runtime thread. Shared-worker
HTTP/bench live-policy projection is wired; GPU continuation remains pending. Host state
roundtrips and checksum validation are not numerical or performance samples.

The native core report requires positive prefill time and call count when new
prompt tokens are processed. Decode time and call count must agree, and confirmed
output requires a decode call. Prefill plus decode time must fit inside the
individual job's total wall time; durations from different jobs may overlap in
a batch. These checks include warmups. A fully cached prompt still has zero
executed prefill time/calls and no PP rate. An EOS decode may have no confirmed
output while retaining its actual call time. Invalid phase records are refused
before a summary or graph is written.

Core result identity additionally records `eos_policy`. The default `stop`
can end with an un-emitted EOS while retaining the completed call time.
Explicit `ignore` treats EOS as a confirmed token, including zero text bytes,
and requires the full declared output budget and a length finish. It does not
remove EOS from the sampling distribution. Paired reports refuse different
policies; a missing historical field means `stop`. This policy is independent
of the generation filters and progress interval.

The direct `single`/`multi`/`fresh` benchmark records `timing_clock` as
`CLOCK_MONOTONIC`. A sample carries `sample_begin_monotonic_ns`,
`sample_begin_wall_time_ns` (CLOCK_REALTIME, correlation only),
`prefill_begin_monotonic_ns`, `prefill_end_monotonic_ns`,
`decode_begin_monotonic_ns` and `decode_end_monotonic_ns`.
The two phase differences equal `prefill_ns` and `decode_ns` exactly; ordered
bounds exclude prefix construction, frontier copies and flow setup from the
timed GPU calls. These host bounds do not identify individual device kernels
or constitute preemption evidence. They are optional only for older raw
records with no clock declaration; partial or contradictory new bounds are
rejected by the native report. `prefill_seconds`/`decode_seconds` distributions
and `pp_*_s`/`tg_*_s` CSV columns expose measured duration separately from rate.

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

For prefix reuse distinguish physical prompt usage, reused frontier tokens and
new tokens actually processed. Count avoided prefill separately from executed PP;
cache hits must not inflate GPU prefill throughput. Record capture, serialization,
SSD read/write and upload costs separately from lookup and HTTP total latency.
Charge checkpoint storage, cloned active state and in-flight staging to their
actual owners; shared allocations count once. For vision account image/pixel/
patch work and encoder storage explicitly. None of these pending cache/modality
meters exists merely because the numerical dependency supports the feature.

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

## Implemented RAM prefix accounting

Core snapshots own `cache`: byte budget, retained and peak logical bytes,
lookups, hits, misses, reused tokens, captures, evictions, skipped captures and
entry count. `retention_policy` identifies utility-v1 or LRU;
`checkpoint_compression` identifies the build capability; `checkpoint_codec`
identifies the current writer (`byte-plane4-zstd1-v1` or `none`). Historical
reports may still name `lz4-blocks-v1`; current builds cannot read codec 1.
`expanded_bytes` is
the raw equivalent of currently retained states; `compressed_captures` counts
successful packs and `compression_attempts` counts eligible capture-path calls
(including calls refused by size/budget or the bounded benefit probe). A true
build capability does not imply any state was packed: current admission requires
at least 50% retained saving. These are not active GPU KV savings.
`/actuator/llm` projects this object and reports the actual
`ssd_enabled` flag, false by default, plus a separate `ssd` object.
The budget covers the immutable descriptor/payload allocations, including the
in-progress capture after pre-eviction; it excludes allocator/driver overhead,
active sequences and model scratch. It is not total RSS or a memory-fit proof.

Per-job `cached_tokens` is the restored physical prefix, not newly executed PP.
Successful completion satisfies `prefill_tokens + cached_tokens = prompt_tokens`.
Chat usage reports `prompt_tokens_details.cached_tokens` on a hit; Responses
always reports `input_tokens_details.cached_tokens`. Prompt usage remains full
physical input length. Pure PP tokens/s uses only executed tokens and time;
a full hit has zero PP calls/time and no PP throughput value.

`cache_restore_ns` (HTTP `cache_restore_ms`) covers lookup plus completed restore,
including a cheap lookup on a miss. `cache_capture_ns` includes planning,
deduplication, eviction, allocation, completed capture and optional packing.
Restore includes full expansion when needed. These are whole cache
path durations, not isolated DMA bandwidth. Client total wall/TTFT includes them.
Counters reflect actual core events, independent of HTTP. Capture/restore do not
increment prefill/decode call counters; faults/cancellation can leave lookups
without a successful hit or miss. These timers do not establish kernel overlap.

## Implemented optional SSD accounting

`lie_core_info.ssd` and `/actuator/llm.cache.ssd` report quota, logical and
allocated file bytes, entries, pending operation, staging cap/reservation and its
peak, lookups, checksum-valid file hits, misses, durable writes, evictions,
skipped writes, errors, cancelled reads and successful file bytes/read/write
durations. Staging byte counters are **reservations**, not RSS/allocation peaks;
reads reserve the cap and keep it through owner upload/result release. A file hit
can still fail the provider geometry check and is distinct from actual reuse.

Job `ssd_cached_tokens` is a subset of `cached_tokens`; `ssd_read_ns` (HTTP
`ssd_read_ms`) is lookup/read/checksum and optional host packing time. GPU restore remains separately in
`cache_restore_ns`, and no avoided PP is credited as executed PP throughput.
Write completion may outlive its originating job, so write timing is store-wide.
The bench emits `ssd_drained` after graceful shutdown and adds SSD columns to
JSON/CSV. The precise [store contract](SSD-PREFIX.md) defines exclusions.
[Original-weight C1 SSD comparisons](../archive/SSD-GPU-COMPLETION.md) now report those
intervals at 8K/128K; full hits retain undefined executed-PP throughput. HTTP
with SSD enabled and concurrent SSD performance remain separate measurements.

Core bench identity and CSV include both build options; sample rows include raw
equivalent and retained bytes. Ordinary comparisons refuse differing build
features. `bench-report.py --compare-cache-build --compare ...` explicitly
permits only those feature differences, reports them, and still requires matched
workload/runtime settings and output tokens. This is an ON/OFF ablation, not an
unqualified model/server comparison.

## Direct-core reactive probe

Core benchmark identity includes the optional `reactive_probe` boolean. When
true, the client emits a `reactive` event instead of measured job/sample rows.
`scope=direct-c-core-held-loan-peer-cancel` identifies the check: one borrowed
text block remains held while a peer completes, then the held job is cancelled.
All bytes of that block must remain unchanged until release. The event records
peer and held output counts, borrowed token count, blocked rows, completion and
cancellation deltas, decode batch deltas and MTP draft/acceptance deltas.

These are functional assertions, without elapsed-time or throughput estimates;
the regular benchmark report requires measured samples and does not export this
probe as a performance comparison. The `synthetic` field retains its usual
meaning. Historical normal core records without `reactive_probe` remain readable.

The consumer waits for core-wide completion/cancellation counters after job
terminals. A successful row requires one completion and one cancellation; an
MTP probe also requires accepted drafts. A failed gate emits its actual error
and exit code. [Point GPU examples](../benchmarks/models/qwen3.8-flash-next/strix-point/README.md#direct-reactive-core-and-q8-vision-gates)
retain both passing and failing gates.

## Prepared HTTP multi-user benchmark

`synapse-lie.http-multi-bench.v1` contains identity, prepared cohort records and
a required successful terminal record. Each cohort retains every participant's
request SHA, usage/cache counts, assistant output, raw SSE chunks and monotonic
client bounds for both preparation and measurement. All participants share
their phase's client start gate; all preparations finish before measured decode.
Payloads are greedy, thinking off, with distinct stable `X-Client-ID` headers.
Preparation generates one token; measured reuse may replay at most four prompt
tail tokens. Every participant, including warmups, must complete its budget.

`sum_request_decode_tps` is the sum of individual output/server-decode-time
rates. LIE `timings` and Gufo `usage.gufo` are distinct accepted timing profiles;
neither falls back to request-wall throughput. This rate sum is not GPU elapsed
time or delivered cohort throughput. `aggregate_output_tps` uses all output
over the interval from the common measured start to the last complete HTTP
response. `first_output_seconds` is the mean participant HTTP TTFT, distinct
from the direct core's first-token clock.

`preparation_wall_seconds` and `measured_wall_seconds` report the two common
intervals. `preparation_prefill_tokens` sums executed preparation tokens;
`executed_preparation_pp_tps` averages executed per-request PP rates, excluding
full hits. All-hit preparation has a null PP distribution. These are not cache
compression metrics. CSV/JSON contain measured median/min/max/count; four graph
panels keep executed PP, the two decode rates and TTFT on independent scales.

The native report revalidates usage, physical prompt counts, timings, request
hashes, phase gates, session IDs and complete output budgets before export.
Paired comparisons additionally require matching controls, payloads and physical
counts. Output hashes determine eligibility; unequal output yields no speed ratio.
Failed cohorts remain raw evidence and never contribute partial averages.

## Shared progressive cache policy

`/actuator/llm.cache.checkpoint_policy` reports kind (`ds4`/`legacy`), text-prefix
and finish-capture booleans, minimum/cold/continued/trim/alignment limits. Both
cache tiers expose `index_bytes` and `index_budget_bytes` separately from their
payload/staging pools. `cache_capture_ns` accumulates all completed captures of
a job, including periodic frontiers; asynchronous disk write duration remains
store-wide. SSD hits update persisted timestamps and hit counts. Build flags
and every core-bench policy setting are comparison keys. Historical records
without checkpoint-policy fields retain legacy interpretation. No hit metric
asserts DS4 file interoperability or a numerical/performance improvement.

The prompt-retention repair counts complete-prompt captures in the same counters.
Budget refusal to preserve a prompt increments RAM/SSD `skipped`; it is not a
backend or disk error. The SSD worker may refuse after candidate capture/staging,
so `cache_capture_ns` can remain nonzero even when no new file is written. No
metric reclassifies reused tokens as executed prefill. Source/build identity
distinguishes the repaired schedule from earlier `ds4` policy results.
Core benchmark samples also expose `cache_skipped`, `ssd_evictions`,
`ssd_skipped` and `ssd_errors` as cohort deltas. The final `ssd_drained` event
reports cumulative skips/evictions and durable entry/allocated-byte counts,
including writes that finish after a request becomes observable. Older records
without these optional fields remain readable.

The offline [KVC tool](KVC.md) reports `memory_bytes`, text/payload/trailer sizes
and optional Qwen structural-validation fields in its own JSON. These are not
runtime cache hits, throughput or device qualification. Its completed operations
do not change actuator/Prometheus counters or add inference threads.
The detached Qwen component mapper likewise adds no runtime counters. Its
caller accounts borrowed source/auxiliary buffers and output bytes; export
additionally budgets `16 * tokens` bytes of temporary position storage.

## Runtime state format

Backend diagnostics, server `--build-info` and core/state bench identities expose
`state_format`: `ds4-kvc-payload`, `lie-aligned-components`, `none`, or an explicit
`synthetic-*` fixture label. Core comparisons reject differing formats unless
`--compare-cache-build` is selected; the report records that difference. State
ABI-2 capture/read records also contain the representation version. Historical
ABI-1 reports remain readable as legacy evidence.

State SSD writes emit `ssd_prepare.render_and_admission_ns` separately from
`capture_ns` and worker `write_ns`; preparation renders text and admits the async
write. KVC retained/expanded bytes are equal and restore workspace is zero.
Full index allocation is included in provider session accounting; retained host
bytes do not describe total device memory. No new worker, speedup or compression
ratio is inferred from these format changes.

## MTP development observability

Completed MTP calls report `decode_mode`, `max_decode_output_tokens`,
`mtp_drafted_tokens` and `mtp_accepted_tokens` in Chat `lie_timings`.
The actuator executor snapshot includes aggregate draft/acceptance counts.
`decode_calls` counts per-row calls; `decode_tokens` counts confirmed output,
which can exceed calls. Proposed/rejected tokens never enter output throughput.
Counts exclude suppressed cancelled results. Core clients access the same job
snapshots. These are host completed-call timings, not GPU event measurements.

MTP cache reuse uses the existing `cached_tokens`, `ssd_cached_tokens`,
capture/restore timing and RAM/SSD accounting fields. `backend.prefix_state`
and the admitted MTP capability advertise complete predictor state only for a
state-capable composition. A true capability is implementation availability,
not original-weight qualification or a throughput claim. No new inference
worker or metric label is introduced by predictor transfers.
## VISION development observability

Vision prompt counts include image-expanded physical tokens. Executor prefill
time includes encoder work inside the provider prefill call; CPU image decoding,
resizing and prompt preparation occur before that interval and contribute to
client latency. Existing metrics do not isolate encoder time or image memory;
those measurements remain a qualification gate. Never label this combined
prefill rate as text-only prefill throughput.

Joint MTP/vision uses the same draft/acceptance and cache timing fields. Actuator
`backend.prefix_state` requires complete support for every admitted capability.
Core benchmark identity records `mode=mtp+vision`, predictor, draft request,
projector and encoded image hash. Comparisons require matching image and physical
input; differing AR/MTP policies remain visible so their costs can be compared.
Image semantics used for cache identity still come from prepared provider input,
not the benchmark's encoded-file hash. No additional device owner was introduced.

## Semantic output observability

The shared core counts `output_validation_errors` when a semantic client rejects
a complete turn. `/actuator/llm.scheduler.output_validation_errors` exposes that
count for direct clients and HTTP together. The existing HTTP tool-error meter
counts errors projected to HTTP; physical completed/failed executor counters
remain separate. Provisional starts and argument deltas contribute no additional
token credits or committed tool-call count. Their copied journal payloads count
toward the response record quota. No semantic parsing time is relabelled as GPU
decode time.
Job fields `semantic_checked`, `output_invalid` and `tool_calls`, plus the typed
terminal reason, are specified in the [event contract](EVENTS.md).

## OpenAI controls and response lifetime

Multiple Chat choices share the same worker, batching and token counters.
Wire usage counts the prompt once and sums all choices' physical output tokens.
Stop-hidden tokens still count as completed model work; they are excluded from
returned content/logprob bytes. Reporting probabilities copies adjusted target
logits on the device owner and normalizes them in C; it is an opt-in cost,
not a GPU-time metric. Explicit stop, bias and logprob requests use AR steps
while retaining native batching; ordinary requests keep their MTP width.

History lookup, stream replay and observers add no generated tokens, decode
calls or inference threads. Background cancellation waits for the same physical
retirement barrier as foreground cancellation. JSON/schema violations use
`output_validation_errors`; successful object compilation and host sampler
checks do not mark `hardware_qualified` true. Response history has its own
conservative RAM quota and TTL, independent of the KV cache statistics.

## Canonical cached conversation benchmark

`synapse-lie.http-curve-bench.v1` records the pinned Gufo recipe separately from
the simplified direct-executor and prepared-cohort protocols. Its identity binds
model alias, declared context, depth list, task, seed, output/prompt budgets,
warmups, repetitions, endpoint profile, requested AR/MTP mode and tolerance.
`request` events retain calibration, warmup, non-streaming prefix preparation and
streamed measured attempts, including the complete request, payload hash, actual
assistant text, raw response chunks, usage and monotonic HTTP bounds. The client
is a single curl-multi event loop and introduces no worker per request.

Each accepted `point` references its measured request index and records physical
prompt/cached/new-prefill/output counts, completion hash and draft counters.
`pp_tps = (prompt_tokens - cached_tokens) × 1000 / prefill_ms` and
`tg_tps = output_tokens × 1000 / decode_ms` use executed server phases.
`timing_source` identifies validated LIE `synchronous_executor_calls` or Gufo
`usage.gufo` phases; their implementations retain their distinct boundaries.
HTTP wall time, client TTFT and output over HTTP wall are separate metrics.
Phase sums cannot exceed complete request wall time. Measured output must fill
its budget; an EOS-shortened response fails the curve. Preparations retain their
actual reply even if their 8-token budget ends early, matching the Gufo recipe.

The offline report reconstructs calibration and all expected prompts, replies,
attempts and accepted points before aggregation. It requires the final successful
request/point counts and rejects missing events, altered payloads, output budgets,
terminals, timings and point aggregates. Statistics expose every sample, mean,
sample standard deviation, median and min/max. Unexecuted phases remain JSON
null and plot gaps. PP, TG, HTTP wall and TTFT use four independent plot panels.

Comparisons require matching protocol declarations and disclose exact request,
completion and physical-count equality per depth. Gufo's adaptive history may
differ between model quantizations; such a comparison is a workload comparison,
not numerical equivalence or an inference-quality certificate. These records do
not measure server cold loading or peak allocation. CPU fixture values remain
explicitly `NOT-INFERENCE`; they must never be published as GPU results.
