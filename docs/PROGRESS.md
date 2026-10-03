<!-- SPDX-License-Identifier: MIT -->
# Development progress

## Clocked performance follow-up prepared — 2026-10-03

Ten arms are prepared locally at frozen runtime checkpoint `15c6082`: the
missing 12288-token depth pair at capacity 133760, then balanced C17/control
orders for fresh PP1500/TG128 at capacity 262144. Four arms use no model warmup
and four use two warmups, with three measured samples each. First and later
samples remain distinct; OS file cache is uncontrolled, so these are not
cold-file measurements.

The private supervisor adds read-only optional GPU clock/power and CPU-frequency
snapshots with monotonic bounds, correlated with the new native PP/TG clocks.
GPU-masked build-info/help exits are zero and all ten capsule manifests verify.
**No GPU run, model load/hash or remote staging occurs; admission remains
disabled until a new Q2 handover.** The
[preparation receipt](development/validation/performance-followup-preparation-2026-10-03.json)
binds source, binaries, commands and the planned acceptance checks. The earlier
1500-token slowdown remains unresolved.

The combined published CSV duration headers now correctly say `seconds` rather
than `ns`. All 17 rows and their data bytes remain unchanged; 204 duration cells
match the native summaries. Raw measurements and figures remain unchanged.

## Benchmark phase clocks and durations — 2026-10-03

Native direct benchmarks now record monotonic prefill/decode bounds and a
wall-clock sample start for correlation with supervised telemetry. They exclude
prefix construction, frontier copies and flow setup from the timed calls. The
C report exports duration distributions in seconds to JSON/CSV, validates full
ordered clock tuples and exact duration differences, and retains support for
older raw data without a clock declaration. This is host timing, not a GPU
kernel timeline or preemption claim.

Focused ASan/UBSan/LeakSanitizer `native-benchmark-contract` passes, including
four malformed clock cases, old-evidence compatibility and existing HTTP/SSD
fixtures. Both pinned HIP compositions link with GPU visibility masked. The
first build's incorrect helper name/exit1 is preserved and corrected. Re-export
of all three original-weight datasets adds duration columns without changing
any existing witness, comparison or SVG/PNG hash. The
[source-bound receipt](development/validation/bench-phase-clocks-2026-10-03.json)
records CPU-only validation; this does not resolve the 1500-token GPU slowdown.

## Local GPU thermal benchmark — 2026-10-03

At the owner's request, the editing ASUS ROG Flow Z13 `.155` completes eight
consecutive rocBLAS FP16 GEMM4096 trials, each with five warmups and 4000 timed
iterations. All child/supervisor exits are 0. The campaign lasts **201.79 s**,
including **185.99 s** in the timed GEMM loops. Median throughput is
**23.766 TFLOP/s**; the last trial is **0.79%** below the first. Sampled peaks
are **CPU93.5/GPU97/NVMe38.85 C**, with no 98 C guard stop, hardware shutdown
or deterioration observed. The last trials generally remain around 92–94 C
under load, with brief GPU peaks. Both existing fan curves select PWM255 from
60 C; loaded fans run at 8700–8900 RPM. No settings change during the benchmark.

This is a **synthetic matrix workload**, not LIE inference or a model token-rate
comparison. Eight short processes do not qualify longer steady-state operation;
there is no controlled comparison with earlier fan settings. The independent
local lease is acquired afresh for each arm. All sixteen owned process identities
retire, KFD is empty and the original lease inode is unchanged/free afterwards.
The [thermal receipt](development/validation/local-thermal-155-2026-10-03.json)
binds every trial, 380 sensor samples, OS thread counts (up to five), raw hashes
and temperature/fan/throughput plots. Raw files stay under local `evidence/`.

## Original-weight GPU continuation — 2026-10-03

After the Q2 thread's verified release at 17:37:05 UTC, root takes the `.157`
window under fresh four-lease admission for each arm. Checkpoint `f0f58b3`
passes **32 AR HTTP assertions** with the original UD weights: new sampling
controls, strict schemas/functions, correlated tools, retained Chat/Responses,
stream/replay/cursors, cancellation, truncation and RAM reuse. Child/helper
exit 0. Sampled peaks are CPU74.375/GPU76 C. This is same-provider functional
evidence, not an independent numerical or performance qualification.

The first two attempts preserve verifier failures: nullable logprobs when a
stop hides every token, and the deliberately rejected over-context request
incrementing `failed`. Their servers retire cleanly; no runtime change masks
these outcomes. The successful AR arm is `gpu-functional-f0-r3/ar-http`.

The following MTP arm confirms completed TG128, 95 proposed/accepted tokens
and controlled target-AR fallback, then fails on long-prefix capture. The UD
metadata declares **48 trunk blocks and no nextn field**, while a separate Q8
predictor is actually admitted. The adapter inferred zero predictor layers
from trunk metadata. Its state geometry now binds the admitted predictor;
the C17 codec, cache policy and DS4 payload framing remain unchanged. The
original failed request/exit remain in `gpu-functional-f0-r3/mtp-http`.

The corrected MTP HTTP/cache arm passes **12 assertions**, including actual
2669-token prefix reuse. A C17 probe compares all 248320 logits and confirmed
tokens/counters across fresh/restored predictor state: greedy 24 dispatches,
47/47 accepted proposals; sampled 18 dispatches, 32/35 accepted. All restored
frontiers match exactly, including three rejected proposals and cancellation.
The destination sampler is fresh; this is prefix continuation, not live RNG
session restoration. Peak CPU71.625/GPU61 C for the state probe.

The legacy C++ sampler HTTP control also passes **32 assertions**; fifteen
matched JSON cases have identical output, usage and logprobs. Client timings
from these functional arms are not a paired performance result. Combined
vision refuses the available Q8 projector before READY because the pinned
encoder requires BF16 dense weights. The failed admission is retained; a
separate `feature/vision-q8` checkpoint `bec0955` prepares C17 upload decoding.

The [functional receipt](development/validation/c17-gpu-functional-2026-10-03.json)
binds all eight passed/failed arms, observed OS threads, temperatures and raw
artifact hashes. The [declared protocol](development/protocols/C17-GPU-PROTOCOL.md)
keeps matched performance, process-restarted MTP/vision SSD, real reactive peer
progress and independent numerical/quality gates separate. All six declared
C17/C++ performance arms finish with child/helper exits 0 through full fresh
prefill at 258794 tokens. Their thirty collected result files SHA-verify. All
46 measured and 12 warmup pairs have identical physical IDs, outputs, counters
and full frontier hashes. Native C figures, CSV/JSON and raw compressed JSONL
are now in the single [Strix Halo benchmark page](benchmarks/models/qwen3.8-flash-next/strix-halo/README.md).
TG differs by less than 1% except the retained un-warmed 1500-token point,
which loses 16.64% and keeps the performance gate open. The missing 12288 depth
and exact Gufo HTTP/MTP protocols remain explicit. The `.157` window releases
at **19:41:04 UTC**: all 28 owned process identities retire, KFD is empty, the
four original leases are unchanged/free, and six model stat witnesses and all
used source capsules are unchanged. The controller exits 0; there is no observer,
queued restart or waiter. The prepared vision/SSD/reactive continuation has not
run. No source in `/tmp`, DS4 modification, remote build, installation or tuning
occurs.

## C17 dense sampling extraction — 2026-10-03

`feature/c17-sampling` starts from `develop` in a persistent worktree and
incorporates checkpoint `8992c0b`. The shared C17 library now owns dense greedy
selection, penalties/bias, top-k/top-p/min-p, normalization and random draws.
The verified provider enables it by default; `LIE_C17_SAMPLING=OFF` retains the
C++ control. HTTP and direct clients use the same core. Reactive demand,
cancellation, batching, MTP and the one device-owner worker are preserved.
Sampler ABI is **1**; existing executor/request/generation/state ABIs are unchanged.
History, grammar compilation, compact speculative distributions and model
forward remain delegated; this is the first slice of the autonomous C executor.
See [ownership and build instructions](development/C17-SAMPLING.md).

Final ASan/UBSan/LeakSanitizer suites pass **43/43** native tests, **18/18**
headless MTP/vision-OFF tests and **14/14** host reference tests. Complete
distribution/draw/RNG witnesses agree for **1200** configurations against the
independently fetched official Gufo pin and the legacy control, another **1200**
biased configurations against the prior C++ bias variant, and **12** complete
248320-logit synthetic rows. The pinned HIP provider and server/bench compile
and link. A symbol/metadata audit confirms the direct Gufo reference excludes
the C selector while server and LIE bench include it. These checks are
**NOT-INFERENCE**; no original weights or GPU execution were used.

Read-only admission found `.157` reserved by an enclosing Q2 campaign, so this
turn took the owner's development fallback without a lease or GPU/model access.
The [source-bound receipt](development/validation/c17-sampling-2026-10-03.json)
preserves final identities, actual failures/exits and thermal evidence. Two
owned build children were stopped by a **95 C software guard**; no hardware
shutdown or deterioration was observed. Later serialized provider builds used
the owner's 98 C CPU allowance and stayed below it; there was no fan/clock/power
tuning. Original-weight continuation/cache correctness and matched performance
qualification on `.157` remain open. No speedup is claimed.

## OpenAI generation and retained responses — 2026-10-03

`feature/openai-completion` starts from `develop` and incorporates semantic core
checkpoint `a399052` in a persistent worktree. The C17 core now owns stop matching,
probability normalization, structured-output validation, multiple-choice job
admission, bounded response records/history, oldest-turn context truncation and
an immutable semantic journal. Chat and Responses add token bias/logprobs,
JSON/schema output, strict functions, stored CRUD/pagination, conversation
continuation, background cancellation and Responses stream replay from a cursor.
[Usage](guides/USAGE.md#generation-controls-and-stored-responses) gives HTTP
commands on port 8000; [API coverage](reference/OPENAI-REACTIVE.md) records limits.
Request ABI is **5**, generation ABI **2**, executor ABI remains **2**.

The native ASan/UBSan/LeakSanitizer suite passes **42/42**. Final focused HTTP,
semantic and native-bench checks pass **3/3** after preserving ordinary wire fast
paths; a final headless quota/ownership check also passes. The protocol-independent
MTP/vision-OFF configuration passes **17/17**, then passes the final changed
headless test. The headless build discovers/links no HTTP libraries; the default
HTTP and core builds require no Python. Native fixtures cover split-token stops, suppressed stop logprobs, bias, nested function
schemas, strict canonical calls, multiple choices and aggregate SSE usage,
retention quotas/TTL, metadata filters, stored history, automatic truncation,
live/replayed/resumed response streams and idempotent cancellation. The OpenAI
HTTP campaign runs both AR and a synthetic MTP13 provider; background streams
continue after the creating client disconnects, including credit handover when
a write finishes after that disconnect.

The official Gufo pin was fetched independently and rebuilt with the exact
`sampling-edits.json` state variant. HIP server and bench compile/link; host-only
sampler/grammar and template checks pass **2/2**. Constraint compilation/masking
remain delegated C++ through neutral C controls; this is not an autonomous C
model executor. No inference thread was added. Explicit stop/bias/logprob requests
use target AR steps; ordinary requests preserve MTP and bias-free sampler/wire
fast paths. No measured performance gain or parity is claimed.

The [source-bound receipt](development/validation/openai-completion-2026-10-03.json)
preserves command exits, failures, source/provider identities and local thermal
telemetry. The observed CPU peak is **93.375 C** under a 95 C owned-child guard;
there was no shutdown, deterioration or fan/clock/power tuning. No original-weight
model load/hash/conversion, GPU execution, remote build or performance campaign
occurred. Original-weight controls, strict-output/MTP numerical behavior and
resource/performance qualification on `.157` remain pending under coordination.
Audio/video/embedding executors, hosted tools, named Conversations and compaction
are outside the implemented serving surface; unknown fields fail explicitly.

## Shared core semantic events — 2026-10-03

`feature/core-semantic-events` imports MTP/vision checkpoint `01ff720` into a
persistent Git Flow worktree from `develop`. Text, confirmed-token progress,
validated complete tool calls and typed turn completion now use the shared
C17 [event contract](reference/EVENTS.md). HTTP, Responses and the direct core
benchmark consume it; model-output grammar and UTF-8 decoding belong to the
core. Request ABI 4 owns parallel-tool policy. No inference thread was added.

Native ASan/UBSan/LeakSanitizer tests pass **39/39**, including AR/two MTP
geometries, byte-split UTF-8, complete/invalid/truncated tool turns, forbidden
parallel calls, credit starvation with peer progress, retained loans, cancellation
before pending calls and terminal retirement during prefill. Native Chat and
Responses JSON/SSE fixtures verify calls, failure terminals and full-size burst
pieces. The protocol-independent build with MTP/vision OFF passes **16/16**;
it discovers/links no libuv, llhttp or json-c. Existing raw clients remain usable
but a job refuses mixed raw/semantic consumption.

The official pinned Gufo provider was fetched and rebuilt independently in this
worktree. HIP server and benchmark compile/link, and metadata-only `--build-info`
passes with GPU visibility masked. These are **NOT-INFERENCE** checks. The
[source-bound receipt](development/validation/core-events-2026-10-03.json)
preserves actual failures/exits and thermal evidence. No shutdown/deterioration,
model load/hash/conversion, GPU run, remote build or performance campaign occurred.

Semantic parsing runs in the core consumer API. Confirmed-token demand and device
owner scheduling are preserved; this change makes no measured speedup claim.
Original-weight tool behavior and GPU qualification remain open, as do incremental
argument events, constrained generation, scoring/logits and chat/eval clients.

## MTP and vision integration — 2026-10-03

`feature/mtp-vision-integration` combines the complete MTP checkpoint `7d85b2f`
and semantic vision checkpoint `806a790` in a persistent worktree created from
`develop`. The shared C17 core admits target, predictor and projector together;
HTTP and the direct benchmark use that same lifecycle and reactive dispatcher.
A joint checkpoint includes the unchanged DS4 tensor payload, MTP controller,
residual/hidden rows and the prepared vision scope. Prepared positions, scope and
controller are checked before numerical restore; the destination sampler is fresh.
RAM remains default-on and SSD opt-in. No new inference worker was added.

Native ASan/UBSan/LeakSanitizer tests pass **36/36**. Coverage includes combined
burst demand/cancellation, two fixture geometries, equal-token/different-image
isolation, RAM reuse, SSD process restart and Chat/Responses JSON/SSE cache reuse.
The option combinations MTP-OFF, vision-OFF and both-OFF pass **30/30**,
**29/29** and **26/26** tests. Five focused changed identity/cache tests also pass.
The combined synthetic core client exports native JSON/CSV/SVG/PNG.
The official pinned provider was fetched and rebuilt independently with the
combined source manifest; HIP server and benchmark compile and link. These are
host/fixture checks, **not original-weight inference or performance evidence**.
See [configuration](guides/USAGE.md#mtp-with-images) and the
[source-bound receipt](development/validation/mtp-vision-integration-2026-10-03.json).

Original-weight image/text MTP, numerical cache parity, sampled target behavior,
rejection/rollback, resource fit and GPU measurements remain open. No GPU run,
model hash/conversion/load, remote build, deployment or publication occurred.

## Earlier feature checkpoints

The entries below describe their dated branches before integration.

## Complete MTP RAM/SSD binding — 2026-10-03

The C17 codec and shared cache now connect to live predictor transfers, residual
and kept hidden rows, and the adaptive controller. Missing hidden catch-up rows
refuse in both the C codec and device admission. The independently rebuilt Gufo
variant materializes completed MTP pooled keys in scalar/batch paths. SSD identity
pins the actual admitted target/predictor readers and includes the draft policy;
RAM-only startup performs no weight hash. Default RAM retention is preserved.
Unsupported models refuse readiness unless caches are explicitly disabled.

CPU ASan/UBSan/LeakSanitizer checks pass **29/29**, including two synthetic model
families, prompt/verified-frontier clones, budgets, cancellation, SSD process
restart, predictor/draft identity changes and Chat/Responses JSON/SSE cache reuse.
The MTP-OFF lifecycle/cache checks pass **3/3**. HIP libraries and server/bench
compile/link; the synthetic core client also checks default RAM hits and native
CSV/SVG/PNG export. These are **NOT-INFERENCE** results. The source/evidence-bound
[cache receipt](development/validation/mtp-cache-2026-10-03.json) preserves the
initial stale HTTP assertion and every thermal interruption/refusal.

No original-weight model load, GPU execution, heavy model hash, conversion or
`.157` performance run occurred. The CPU build peak was 94.625 C under a 95 C
child-only guard; GPU functional preparation retains its separate 85 C guard.
Original-weight MTP/cache continuation and sampled correctness remain required.
Vision semantic cache identity and device binding are the next separate branch
integration task; the current vision checkpoint remains `3434504`.

## Shared auxiliary KV state and MTP codec — 2026-10-03

The C17 RAM/SSD store now retains typed auxiliary state with complete budget
accounting and SHA-256 admission, preserving original DS4 payload offsets and
version-1 AR files. Two unrelated fixture schemas exercise the same storage path.
The Qwen codec adds predictor K/V, index/pooled keys, residual/kept hidden
rows and adaptive-controller state. Device binding, complete predictor pooling
and stable predictor identity remain pending; live MTP KV reuse stays refused.

Local CPU ASan/UBSan/LeakSanitizer checks pass **28/28**; HIP provider linking
also passes. No model load, GPU run or performance campaign is claimed. Current
functional-GPU authorization and metadata-only USB findings are recorded in
[coordination](COORDINATION.md). Raw failures and actual exits remain under local
`evidence/`; see the [source-bound state receipt](development/validation/mtp-state-2026-10-03.json).


## MTP model-neutral development slice — 2026-10-03

Verified output bursts, per-row credits, explicit predictor admission and draft/acceptance metrics now run through the shared C17 core, HTTP and core benchmark client. The Qwen limit stays inside its provider; fixtures admit both 8- and 13-token bursts.

Native CPU ASan/UBSan/LeakSanitizer checks pass **27/27**, including both APIs,
JSON/SSE, exact output budgets and early EOS. Final focused feature/dispatcher
checks and the feature-OFF headless lifecycle also pass. The HIP adapter and
clients compile/link against the independently verified Gufo pin. No model
was loaded; .157 and GPU performance campaigns were not used. Direct synthetic
core-client runs also produce JSON/CSV/SVG/PNG successfully. These are
NOT-INFERENCE checks, not performance results.

The feature is compiled ON by default but requires explicit model admission.
Its complete extra state is not yet serializable: the development configuration
requires both KV caches explicitly off, with unsupported state advertised as
such. AR's RAM default is unchanged. Original-weight correctness, extended
state/identity and combined MTP+vision integration remain open. Benchmarks are
postponed while these separate feature branches advance. See
[usage and remaining gates](development/MTP.md) and the
[validation receipt](development/validation/mtp-2026-10-03.json).


## Vision semantic RAM/SSD cache binding — 2026-10-03

The shared C17 cache now keys images separately from tokens. RAM lookup,
deduplication, retention/protection and SSD filenames/index/restart use a typed
semantic scope; equal tokens with different images produce a pre-upload miss.
The Qwen binding validates prepared MRoPE positions and the actual loaded
model/projector files. DS4 tensor payload and old AR framing remain unchanged.
RAM keeps its normal default; SSD is opt-in. Clients resupply images after
restart; full-prompt scope conservatively limits earlier-prefix reuse.

Native ASan/UBSan/LeakSanitizer passes **30/30**. Tests cover two fixtures,
KVC/aligned process restart and both HTTP APIs in JSON/SSE. The independently
materialized provider and HIP server/bench compile/link. No model load, GPU
run, weight hash or performance result is claimed. Earlier compiler errors and
fixture assertions remain in local evidence with their actual exits. See
[usage and limits](development/VISION.md) and the
[source-bound receipt](development/validation/vision-cache-2026-10-03.json).


## Shared auxiliary KV state and vision positions — 2026-10-03

The C17 RAM/SSD store now retains typed auxiliary state with complete budget
accounting and SHA-256 admission, preserving original DS4 payload offsets and
version-1 AR files. Two unrelated fixture schemas exercise the same storage path.
The Qwen codec adds MRoPE delta/physical rows and compares them against prepared
input positions. Live vision KV reuse stays refused until image identity also
covers lookup, deduplication, device layout and restart ownership.

Local CPU ASan/UBSan/LeakSanitizer checks pass **28/28**; HIP provider linking
also passes. No model load, GPU run or performance campaign is claimed. Current
functional-GPU authorization and metadata-only USB findings are recorded in
[coordination](COORDINATION.md). Raw failures and actual exits remain under local
`evidence/`; see the [source-bound state receipt](development/validation/vision-state-2026-10-03.json).


## Vision model-neutral development slice — 2026-10-03

Owned PNG/JPEG inputs, model-specific physical token expansion and encoder admission now run through the shared C17 core, Chat/Responses and core benchmark client. Fixtures use distinct image limits and expansion geometry; no Qwen positions or tensor types enter the public C contract.

Native CPU ASan/UBSan/LeakSanitizer checks pass **27/27**, including both APIs,
JSON/SSE, exact output budgets and early EOS. Final focused feature/dispatcher
checks and the feature-OFF headless lifecycle also pass. The HIP adapter and
clients compile/link against the independently verified Gufo pin. No model
was loaded; .157 and GPU performance campaigns were not used. Direct synthetic
core-client runs also produce JSON/CSV/SVG/PNG successfully. These are
NOT-INFERENCE checks, not performance results.

The feature is compiled ON by default but requires explicit model admission.
Its complete extra state is not yet serializable: the development configuration
requires both KV caches explicitly off, with unsupported state advertised as
such. AR's RAM default is unchanged. Original-weight correctness, extended
state/identity and combined MTP+vision integration remain open. Benchmarks are
postponed while these separate feature branches advance. See
[usage and remaining gates](development/VISION.md) and the
[validation receipt](development/validation/vision-2026-10-03.json).


## Native build, benchmark clients and reports — 2026-10-03

Python is no longer required for the normal build, provider verification,
benchmark clients, graph exports or default tests. CMake fetches and verifies
the independently pinned provider and builds its existing state variant.
The HTTP and KV disk benchmark clients, JSON/CSV reports and SVG/PNG renderer
now run in C17; libpng is a documented full-build dependency. Historical Python
oracles remain optional through `LIE_LEGACY_PYTHON_TESTS=ON` (default OFF).

The native tests cover KVC bytes and state mapping, malformed evidence,
request replay, Chat/Responses JSON/SSE, disk restart, C2 consumers and owned
I/O-barrier cancellation/peer witnesses. Report comparisons align physical
workloads even when reference files reorder them. Separate zero-based axes
preserve prefill/generation scale; absent metrics are not plotted as zero.

Local ASan/UBSan/LeakSanitizer checks pass **25/25** with Python discovery
disabled and **44/44** with historical oracles enabled; the final graph fix
passes **3/3** focused checks. Official source fetch, complete provider build
and final HIP link also pass without Python helpers. All are CPU checks or
compilation: no model execution, GPU performance claim or change to inference
scheduling. Initial HTTP failure-marker and relative KVC fixture-path failures
are retained with their exit codes and corrected. [Validation receipt](development/validation/native-tools-2026-10-03.json).

## KV option names and future weight storage — 2026-10-03

Server and shared-core/state benchmark CLIs now use `--kv-*` for inference
checkpoints: `--kv-cache-ram-mb`, `--kv-disk-dir`, `--kv-disk-space-mb` and
`--kv-disk-staging-mb`. Disk and boundary names follow the official DS4 server
CLI. Old names remain aliases in a shared C normalizer, preserving existing
qualified recipes. The HTTP benchmark uses `--server-kv-cache` for its remote
configuration declaration, distinct from `--kv-cache-policy ds4|legacy`.
Future weight persistence/streaming belongs to `--model-*`; it is not implemented
by these cache controls. RAM remains enabled and disk persistence opt-in.

Local CPU ASan/UBSan/LeakSanitizer checks pass **5/5**, including RAM reuse,
KV disk restart across new/old spellings, core/state clients and HTTP benchmark
declarations. Build exit 0, tests exit 0; observed peaks 76.625 C and 72.875 C.
The initial sandboxed test attempt exited 8 because private sockets and
LeakSanitizer were restricted; the failure is retained. Receipts are under
`evidence/kv-cli-names-{build,test,test-unsandboxed}-20261003/`. No GPU run or
performance claim. The separate Python dependency removal remains in progress.

## Complete prompt retention — 2026-10-02

The owner authorizes publication to `https://github.com/synapse-linux/synapse-lie`.
Configured `origin` and pushed only `feature/openai-reactive-api` at `89b1620`;
no other branch, merge, release or deployment was published.

The shared C17 core now captures the complete prompt before generation. Under
RAM/SSD pressure, generated captures preserve the longest prefix reusable by
that input; sufficient budgets still retain conversation continuations. The
guard follows original visibility-key flags separately from generated metadata,
and is local to a capture, not a permanent pin. SSD refusal precedes eviction
and counts as a skip. Numerical kernels, KVC representation, thread count and
reactive credit/cancellation remain unchanged. [Contract and GPU protocol](development/CACHE-PROMPT-RETENTION.md).

Full ASan/UBSan/LeakSanitizer suite **39/39**; headless utility/compression/
interchange-OFF suite **10/10**. Tiny native/KVC fixtures qualify one-record
pressure, unaligned complete prompts, oversized fallback, continuation, key
isolation, independent SSD process restart and RAM promotion. Existing held-I/O
peer/cancellation tests pass. Local receipts retain four failed focused attempts:
fixture chunk misuse and stale BPE expectations, fixture EOS count, the original
visibility-key guard omission, and an SSD quota below the retained-state staging
admission. Corrections pass without disabling sanitizers. No new original-weight
performance claim is made until the separately coordinated GPU comparison.

## DS4 runtime GPU qualification and cost — 2026-10-02

Frozen `a4008b9` completes 15/15 original-weight GPU arms on .157, all child/helper
exits 0. There are 24 exact full-logit/token replay/restore pairs and 12 exact pairs
across the legacy/KVC provider variants, including generated frontiers and SSD
restart at 131072 tokens with context 139264→262144. Core C1/C4 outputs and cache
accounting match. [Full report, values and plots](archive/KVC-GPU-RESULT.md).

At 128K, retained state grows 3.205→3.957 GiB (+23.46%); median RAM-hit TTFT grows
224.815→267.929 ms (+19.18%) and restore 42.195→52.149 ms (+23.59%). Those exceed
the predeclared 5% latency gate. PP/TG and complete-window throughput remain
approximately unchanged in these samples. The requested DS4 format stays ON by
default and its compile-time OFF control remains available. No overall performance
promotion, high-ratio codec or improvement attributable to reactive scheduling is
claimed. The existing default capture-policy retention regression is separate.

Fresh closure 19:18:19.131870 UTC verifies 30 owned identities, controller and
observer absent, KFD empty and four original leases free; 152 artifacts SHA-verify.
Q2 and Point received explicit release. Independent 1747-sample thermal evidence
records CPU 98.25 C / GPU 100 C peaks and their durations, without crash or disconnect.
No model/DS4 mutation, remote build, tuning, deployment or publication. Foreign
DS4-produced import/export and other real model families still need their own
bindings and independent qualification.

## DS4 runtime payload replacement — 2026-10-02

Default-ON `LIE_DS4_RUNTIME_CACHE` now selects exact DS4 Qwen AR payloads in RAM
and optional SSD, through state ABI 2 and the shared C17 core. The model binding
captures directly into wire offsets; the generic store writes KVC `.kv` files
with an opaque trailing LIE stable-identity/integrity extension. Foreign files
without an authenticated binding remain offline. Qwen geometry stays in its
model codec; an additional synthetic family exercises the generic lifecycle.

The independently materialized Gufo variant keeps complete raw index history
and pools completed keys before sparse selection, with full device allocation
included in session admission. Existing kernels are reused; changed scheduling
and memory cost require GPU qualification. Legacy runtime remains compile-time
selectable. SSD remains default-off; KVC bypasses additional Zstandard packing.
Reactive ownership stays one device worker and one optional bounded I/O worker.

ASan/UBSan/LeakSanitizer: full **37/37**, headless interchange/compression OFF
**8/8**, final report/supervisor contract **1/1**. Independent tiny wire fixtures
cover 1/3/4/2048/2049/131072 tokens, exact payload, restart, client trailers,
identity/integrity refusal and budget/cancellation boundaries. These are
NOT-INFERENCE. Both DS4 and legacy HIP compositions compile and link locally.
Retained failures: store-name compiler warning (exit2), old report ABI/event
expectations (35/36, exit8), and invoking the Release all-target build on assert-
based test fixtures (exit2); corrected focused builds/tests pass. Peak local
CPU was95.125 C during provider compilation and93.375 C during the full suite.
Source/binary-bound [CPU receipt](benchmarks/2026-10-02/kvc-runtime/cpu-receipt.json).

Next is the [paired GPU campaign](development/protocols/KVC-GPU-PROTOCOL.md) on .157 after Q2's verified
release. No GPU numerical/performance result is yet claimed for this variant.
DS4-produced import/export, cross-quantization reuse and other real model families
remain separate gates. [Runtime format and precise boundaries](reference/KVC.md).

## Multi-model cache requirement — 2026-10-02

The owner confirms that KV/prefix caching must also serve other model families.
Recorded an explicit [multi-model contract](reference/STATE.md#multi-model-requirement):
shared C17 RAM/SSD policy, resource and reactive lifecycle; model-specific
component geometry, complete frontier capture and exact KVC payload codecs.
The loaded-model binding must select and authenticate a codec before restore;
Qwen-specific history must not enter generic cache/storage policy. Second-family
RAM/SSD lifecycle and numerical qualification are acceptance gates, not existing
support. Different models do not share otherwise incompatible checkpoints.

Source review confirms separate generic state/store/envelope and Qwen model
modules. This checkpoint changes documentation only; no runtime, ABI, model or
GPU work, and no new test execution is needed.

## C17 Qwen KVC/native component mapping — 2026-10-02

Added shared `lie_qwen_kvc`: allocation-free projection of validated text AR
KVC records into native QF1 components, plus exact reverse serialization when
the caller supplies missing index/pool history. It preserves GPU GDN orientation,
PLE order and tensor bits, translates EOS/unset n-gram history and handles both
sides of the index-pooling threshold. Generic layout helpers were extracted
unchanged from device capture/restore, so this library links without a provider.

Independent Python wire and native byte oracles pass thirteen complete
wire→native→wire pairs, including 2047/2048/2049 and 131072 tokens with tiny
synthetic geometry. These are NOT-INFERENCE checks, not full-model memory or
performance measurements. The suite also checks cancellation, budgets, aliasing,
malformed state and refusal of incomplete auxiliary history. Initial headless
suite: 9/9; final full composition: 35/35; interchange-OFF: 7/7. All use ASan/UBSan
with LeakSanitizer enabled; all nine configuration/build/test commands exit 0.
Persistent receipts: `evidence/kvc-map-*`. Local sampled CPU peak 84.625 C
during the OFF build; full-suite peak 78.875 C. No GPU/model work or window request.

Projected layouts deliberately have domain zero and cannot be restored into a
live model. Provider capture of discarded history, model/tokenizer identity
binding and bilateral GPU qualification using a DS4-produced checkpoint remain
open. Runtime RAM/SSD formats, reactive scheduling and inference work are
unchanged. The mapper is built by default under optional `LIE_KVC_INTERCHANGE`;
SSD remains opt-in. [Contracts, source audit and next gates](reference/KVC.md).

## C17 KVC envelope and Qwen payload codecs — 2026-10-02

Added default-ON, independently optional `LIE_KVC_INTERCHANGE`: a shared C17
wire library and `synapse-lie-kvc inspect/copy`, also available without HTTP.
Owned RAM records and file I/O retain KVC v1/ABI2 bytes, bounded text/extensions
and interoperable text filenames. The typed Qwen codec validates and serializes
complete payload components, including full index history, MTP rows and position
metadata, without inventing missing data or changing numerical precision.

An independent Python wire oracle checks C decode/re-encode byte equality.
The suite covers truncation at every byte, size/geometry/token corruption,
4,000 deterministic mutations, cancellation, short I/O/EINTR/ENOSPC, source
mutation, budgets and exclusive output publication. Headless ON: 8/8; complete
HTTP/core composition: 34/34; headless interchange OFF: 7/7, all ASan/UBSan with
LeakSanitizer enabled. All build/configuration/test child exits are 0. Persistent
receipts: `evidence/kvc-*`; local CPU peak 74.875 C. No GPU or model work.

This is wire-format support, not a qualified live-state converter. Native RAM
and `LIEPFX1` SSD serving remain unchanged; there is no new inference thread or
prefill work. Gufo's discarded index history and differing state layout still
require a provider bridge, an independently produced DS4 checkpoint and a
coordinated numerical GPU test. Cross-quant reuse and frontend-specific history
serialization remain open. High-ratio compression beyond reviewed upstream
capability stays deferred. [API, tool, provenance and next gates](reference/KVC.md).

## High-ratio compression deferred to upstream capability — 2026-10-02

The owner explicitly permits skipping high-ratio compression for now when it
is absent from antirez's implementation. The reviewed DS4 Qwen path uses F16/F32
state without an additional high-ratio codec; developing a new one is removed
from the active parity scope. The requirement for DS4-compatible RAM/SSD state
and KVC files remains. KVC conversion, cross-quant reuse and frontend history
serialization retain their separate implementation/qualification gates.

Existing optional packing and the measured raw fallback remain available.
This is a documentation/scope checkpoint; no runtime changes or new GPU tests.

## DS4 policy GPU qualification and retention regression — 2026-10-02

Frozen `f11ab7f` completes 15 GPU child arms across R9/R10/R11 on `.157`:
six exact full-logit/token state pairs, five matched legacy/DS4 core comparisons,
and automatic SSD producer/restarted-reader output equality. Capture after
128 generated tokens and restoring a checkpoint from capacity 131072 into 262144
pass. The later `fffaabb` cache-disabled shortcut retains its separate CPU check.

At 128K/4 GiB, DS4 scheduling keeps only 28672 reusable tokens and recomputes 102400;
warm TTFT is 79.195 s versus legacy 0.227 s. At 8 GiB it keeps 122880 tokens, with TTFT
6.738 s versus matched legacy 0.231 s, retaining 7.524 GB. No high compression or
reactive speedup is claimed. Default-ON features remain independently optional;
runtime `--cache-policy legacy` is available. [Tables, graphs and limits](archive/CACHE-DS4-GPU.md).

R9 retains FAILED controller status for the mistaken 122880-token expectation
under 4 GiB pressure; all nine device children exit 0 and offline outputs match.
R10 retains its mistaken 8231-token expectation for a legacy aligned 8192-token
checkpoint, child exit 0. R11 runs only missing arms and completes successfully.
R8's original adapter refusal and every actual exit remain in the archive.

Final R11 closure 14:56:30.025088 UTC confirms ten owned identities absent,
empty KFD and four unchanged/free leases. Controller is absent; observer exits 0
at 14:56:45.219419 UTC; all 58 collected files verify. Root returns the window
to Q2 and notifies Point, with no GPU job or waiter remaining. Whole-process
inference observations are 36 threads for RAM and 37 with SSD, including provider
threads. `.157` supervisor peaks CPU 98.25/GPU 100 C; no observed crash/reboot.
Independent sampled thermal durations are preserved separately. DS4 binary KVC
conversion, cross-quant reuse and DS4-specific frontend history serializers
remain unimplemented; this is shared policy parity, not full format parity.

## DS4 policy GPU refusal and repair — 2026-10-02

R8 passes native-v3 SSD producer and context131072→262144 reader, with three
exact full-logit/token pairs, then the 8K legacy core control. The first DS4
core arm fails at end-of-generation capture: the adapter still rejected
`sampling_started` sources. Its exit1 and empty surfaced job error are retained.
The repair allows completed capture after decode while restore still requires
an empty unstarted destination, and publishes capture failure before waking a
flow consumer. A zero-frontier shutdown edge is also corrected. The state bench
adds `--capture-decode` to qualify exact live generated frontiers independently.

R8 closes at 14:06:00.539460 UTC with eight owned identities absent, empty KFD,
four unchanged/free leases. Observer retires at 14:06:16.094468, exit 0; all 49 collected
files verify. Root retains the coordinated window for a freshly admitted R9
following local CPU qualification. The incomplete R8 is not a policy pass.

## Shared DS4 cache policy — 2026-10-02

Implemented persistent six-hour utility, bounded dynamic indices, startup quota
eviction, text-prefix/suffix retokenization, owned opaque extensions and
progressive cold/continued/retirement/shutdown captures in the shared C17 core.
One busy SSD operation parks the affected row; peers remain schedulable.
The server and core bench expose matching options and accounting. Request ABI
is now 2. The adapter admits smaller saved contexts after shape validation.

Complete CPU sanitizer suite: 33/33, including failed-write preservation and
shutdown captures; optional-feature OFF checks also pass. Peak CPU in the full
run was 75.25 C on .155, no GPU work in those tests. Retained failed attempts
and successful receipts live in `evidence/ds4-policy-*`. GPU qualification is
prepared after Q2 release at 13:37:03.673156 UTC, with fresh per-arm leases.
**DS4 KVC import/export and cross-quant reuse remain pending.** Native v3 files
persist policy metadata but are not DS4-compatible files.
[Implementation, controls and remaining gates](reference/CACHE-DS4-POLICY.md).

## DS4 format constraint for RAM and SSD — 2026-10-02

The owner requires DS4's compression representation in both memory and SSD,
with higher savings and restore latency close to raw state. The earlier idea
of a separate lossy Q4/Q8 format is therefore not pursued as an equivalent.
Read-only upstream tracing confirms RAM snapshots share the Qwen persistence
serializer; the inspected path retains F16 KV/F32 recurrent tensors without an
extra high-ratio stream. The exact alternative DS4 function/version remains
unidentified. [Source trace and constraint](reference/STATE.md#requested-ds4-representation-parity--clarification-2026-10-02).
No runtime code or numerical precision changes, model reads, new GPU jobs or
DS4 mutations in this clarification. Q2 still owns its separately admitted work.


## Compression cost measured; strict admission qualified — 2026-10-02

R6 passes all six GPU arms, including restarted compressed SSD state at 128K
with three exact full-logit/token pairs. The codec saves 15.35% at 8K and 15.71%
at 128K, but 128K warm restore rises 42.46 to 1228.78 ms and output/wall falls 24.38
to 19.87 tok/s. The owner rejects that tradeoff; this is retained negative evidence.

R7 source `71a4599` passes 4/4 matched ON/OFF arms. Both tested Qwen states fail
the stricter benefit gate and remain raw. At 128K, warm restore 42.41 ms and
output/wall 24.36 tok/s match the OFF control closely; no high compression is
claimed. One cold capture 129.15 versus 118.00 ms remains visible. All 16 jobs
reach 128 identical tokens across matched builds. [Full tables and graphs](archive/CACHE-COMPRESSION-GPU.md).

R6 CPU/GPU peaks 97.875/99 C; R7 peaks 98/100 C, with the 100 C GPU reading confined
to one sampled point bracketed within 2.018 s. No observed crash/reboot/device
failure. R7 closure 12:37:26.556477 UTC confirms eight owned identities absent,
KFD empty, four unchanged/free leases; controller and observer retire, all 50
collected files verify. Root releases the coordinated window to Q2 and informs
Point. Sources, evidence, CSV and graph artifacts remain persistent and local.


## Reject low-benefit checkpoint compression — 2026-10-02

The owner rejects the measured 15–16% checkpoint saving as insufficient for its
capture/restore cost. New default admission requires at least 50% saving of the
complete retained allocation, including its descriptor. A deterministic probe
of at most 48 KiB rejects likely low-benefit data before candidate allocation;
the full result still has to meet the strict size gate. The probe may skip useful
packing but never changes the state or permits lossy conversion. Existing v1/v2
readers remain compatible. Both cache build options remain ON; SSD remains opt-in.

Thirteen focused ON suites and six OFF suites pass ASan/UBSan; local Release
variants link against the unchanged numerical engine. Tests include modest
savings rejected and misleadingly compressible samples that fail final admission.
[CPU source-bound receipt](benchmarks/2026-10-02/cache-benefit-cpu/receipt.json).
The new GPU comparison is pending a fresh per-arm admission after R6 closes.

The upstream Qwen payload audit corrects the earlier architectural generalization:
DS4 supports Qwen, but its reviewed Qwen path writes live F16 KV and F32 recurrent
state without a generic high-compression stream. LIE's independent host codec is
not the same algorithm. High-ratio compression of real Qwen state and low-bit
active KV are not achieved by raising the admission threshold. See the precise
[model/policy boundary](reference/STATE.md#retention-policy-and-compression-boundary).


## Numeric-byte codec follow-up after R5 — 2026-10-02

R5 closes 9/9 original-weight arms at 11:57:08 UTC: six ON/OFF core comparisons,
three exact 8K state pairs, and HTTP SSD producer/restarted reader with 30
samples, three C2 cohorts, natural read cancellation and slow-client isolation.
All states remain raw: LZ4 does not provide an admitted 12.5% payload saving.
At 128K, capture increases 119.638 to 205.906 ms without memory savings; warm
aggregate throughput stays near 24.04 tok/s. [Full R5 result](archive/CACHE-FEATURES-GPU.md).

The follow-up groups numeric byte positions before Zstandard level-1 compression,
using fixed static contexts inside the workspace budget. It preserves every bit,
keeps legacy LZ4 decoding, names the selected codec in metrics/reports and remains
behind default-ON `LIE_CHECKPOINT_COMPRESSION`. Thirteen focused ON suites, six
OFF headless suites and the final report check pass ASan/UBSan; Release variants
link locally. [CPU receipt](benchmarks/2026-10-02/cache-features-zstd-cpu/receipt.json).
Original-model compression benefit is pending a distinct R6 admission. This is
checkpoint storage, not an active KV precision/kernel change. R6 declares 8 GiB
workspace for the 128K packing comparison and lower context capacity 133120 to
bound active-session allocation; matched ON/OFF settings and exact SSD restart
will be checked separately from R5's default-budget result.


## Default-on utility and lossless checkpoint compression — 2026-10-02

Implemented independent CMake switches `LIE_CACHE_UTILITY` and
`LIE_CHECKPOINT_COMPRESSION`, both ON by default. Shared C17 RAM/SSD utility
retention ages reuse and scores saved tokens per stored byte, distinguishes
anchors/continuations and deterministically breaks ties. OFF selects LRU.
The C-owned checkpoint codec preserves every byte with bounded 1 MiB LZ4/raw
blocks, a 12.5% minimum saving, raw fallback and explicit working-memory
admission. Tokens remain directly readable. Raw v1 persists; compressed SSD
files use separately validated v2 framing. SSD alone remains runtime opt-in.

Metrics and benchmark JSON/CSV distinguish expanded/retained memory and build
features. An explicit `--compare-cache-build` enables matched ON/OFF reports;
ordinary comparisons reject those differences. State qualification applies the
same codec before full-logit/token checks. No kernel, active KV format, thread
count or HTTP-owned engine policy was introduced. Host packing/expansion can
add owner latency; active Qwen KV remains F16 and DS4's learned architectural
compression is not claimed.

Thirteen focused ASan/UBSan CPU suites pass with features ON; all six headless
suites pass with both OFF and without LZ4. The first reporting attempt selected
Python without matplotlib and failed two suites; that evidence is preserved.
Using the already installed system interpreter fixes both. Release ON/OFF
executables link the unchanged pinned numerical engine locally; no local GPU
inference. The next `.157` campaign follows Point's verified 11:11:58 UTC
handover, fresh root checks and independent four-lease admission per arm.
GPU performance of these new defaults is not yet claimed at this checkpoint.


## SSD HTTP consumer suite and explicit cache boundary — 2026-10-02

Added `synapse-lie-bench --suite http-ssd`: producer/restarted-reader output
comparison, Chat/Responses JSON/SSE, repeated C2 cohorts, cache-aware PP/TG,
first-text latency and text-event gap distributions, CSV/JSON and SVG/PNG.
Natural disk-wait cancellation and slow-client checks require observed states;
missed windows are INCONCLUSIVE. A test-only held pread proves peer progress
and cancellation deterministically through the real C core and HTTP stack.
The production core/model/ABI are unchanged.

The existing four-lease supervisor now owns the HTTP server and retires its
checker, binds corpus and restarted producer/store/summary identities, and
retains resource/thermal admission. Four focused ASan/UBSan CTest suites pass
(including 16 core-bench, six HTTP-client and two thermal-guard checks), followed
by a passing expanded supervisor/client fixture. R3 tests peak at CPU80.25/GPU57 C;
R4 at CPU71.75/GPU55 C. Commands exit0. [Protocol and receipt](development/protocols/SSD-HTTP-PROTOCOL.md).
The final R5 source repeats the four focused suites with leak detection and
halt-on-error sanitizer settings: 4/4 pass, CPU75.625/GPU54 C, exit0.
No original-model HTTP SSD result is claimed; `.157` is coordinated for the
owner's direct model copy to `.161` following Q2, with no core interleaving.

The owner clarified `antirez/ds4` as the cache reference. LIE's current LRU
retention and F16 KV checkpoints do not implement DS4's disk utility priorities
or a generic high-compression active KV codec. These are explicitly separate
remaining core/model/provider work in [STATE.md](reference/STATE.md#retention-policy-and-compression-boundary).

## Completed SSD GPU continuation and thermal timeline — 2026-10-02

R4 completes 10/10 arms, closing 128K exact SSD restart and core C1 off/RAM/SSD
at 8K/128K. All 24 core jobs (four warmups) emit 128 identical tokens across
policies; three state pairs each match every logit frontier and 16 output tokens.
R2's exact 8K and 4K-to-8K extension passes remain separate from its failed
128K reader. R1/R2/R3 failures and actual exits are retained without rewriting.

At 128K, median core TTFT is 98.583 s off, 0.226 s RAM, 2.186 s restarted SSD;
fresh PP is 1332.098 tok/s and native C1 TG about 25 tok/s. Full hits execute no
PP; startup hashing and write durability have separate measurements. The bench
graphs/CSV expose complete samples and min/max, not just headline rates.

The 1 Hz observer retains 1743 samples: CPU peak 98.125 C, GPU peak 100 C in three
isolated samples. GPU episodes at/above 98 C are bracketed within 3.036 s, while
95 C plateaus last longer. No crash/reboot/device error was observed. Matched
128K fresh PP falls about 2.08% across three samples; there is no controlled
thermal A/B to attribute that variation solely to temperature. No hardware
settings changed. The core adds one optional I/O worker; C1 does not establish
reactive concurrency speedup. [Full result and reproducible evidence](archive/SSD-GPU-COMPLETION.md).

Closure at 09:39:08.072 UTC confirms twenty owned helper/child identities absent,
KFD empty and four unchanged/free leases. Controller and observer retired;
all 106 collected files SHA-verify. The window was returned to Q2 and Point was
notified after collection. HTTP/concurrent SSD GPU tests, fault injection,
256K checkpoint fit, 1M, MTP and vision remain separate roadmap items.

## Owner requested transient-temperature observation — 2026-10-02

R2 closes with five successful SSD state arms and a software thermal stop at
GPU99 C on the 128K reader. R3 stops its first 8K core arm at GPU98 C; neither
is a hardware crash, and its chunk512 alternative never launches. The owner
clarified the dynamic-fan behavior and explicitly requested recording transient
peaks and any performance deterioration/shutdown. An opt-in supervisor policy
now observes CPU/GPU temperatures without the earlier software ceiling, retains
reported hardware bounds and SSD guards, and leaves hardware settings untouched.
Both focused CTest suites pass (15 core-bench and 2 thermal checks), all exits0,
with ASan/UBSan fixture binaries. [Receipt](benchmarks/2026-10-02/ssd-qualification/thermal-observation.json).
The resumed R4 protocol uses the original chunk2048 and a 1 Hz observer that
persists received samples on the editing host. No R4 result is claimed yet.

## Documentation navigation and benchmark scope — 2026-10-02

Added a documentation index and benchmark navigation by model, platform and
weight format. Current UD Strix Halo campaigns link their original reports and
artifacts; other platform/format work is explicitly not integrated evidence.
Corrected stale current-contract statements about RAM/SSD, shared-core ownership,
actual-model tools, Crypto dependencies and local non-performance checks. Dated
result files and hash-bound assets retain their original scope and contents.
The Gufo-style multiuser result remains a simplified direct-executor measurement;
it does not reproduce the published HTTP corpus and per-request-rate aggregation.

## User-authorized Strix Halo temperature revision — 2026-10-02

The 85 C R1 ceiling was an assistant-selected precaution. Following the user's
98 C clarification and AMD's 100 C CPU Tjmax specification, helpers now support
an explicit 98 C CPU/GPU ceiling on the verified 395 host. Lower hardware limits
remain enforced, NVMe stays at 85 C or lower and defaults remain 85 C elsewhere.
No numerical/core source or hardware policy changes. Both focused ASan/UBSan
CTest suites pass, including 14 bench checks and two guard tests, at CPU91.875 /
GPU65 C. The preceding sandbox attempt retains its LeakSanitizer/loopback
restrictions and exit 8. [Thermal revision receipt](benchmarks/2026-10-02/ssd-qualification/thermal-revision.json).

The remaining 14 SSD arms are prepared for a separate continuation; Q2 owns
`.157`, so no new GPU run or heavyweight hash starts before its release.

## First original-weight SSD restart — 2026-10-02

`ssd-gpu-r1` records two successful arms: 512-token durable write and a separate
restart reader with three exact fresh/restored logit/token pairs. Early EOS
limits each pair to two decode calls and one emitted token. File read takes
61.517 ms, median owner upload 4.388 ms; median fresh PP 627.892 ms. Startup model
load and 52.770–60.059 s full-content hashing remain separate, not request latency.

The next 8K producer stops during PP at GPU86/CPU84 C under the initial 85 C
policy, child/supervisor exits 1/1, without forced kill. The campaign remains
FAILED/INCOMPLETE; 13 arms never launched, so there is no long-prefix SSD or core
performance result. All 39 collected files verify. Closure 07:39:00.622 UTC:
six owned identities/controller retired, KFD empty, four unchanged/free leases.
The window was returned to Q2. [Complete timings, failure and scope](archive/SSD-GPU-RESULT.md).

## SSD restart qualification harness — 2026-10-02

`synapse-lie-bench --suite state` now has explicit `--state-ssd-mode write|read`
with independent directory/quota/staging options. Write requires a new empty
store and a durable commit; a separate read process requires the exact frontier
and compares all logits/tokens with fresh recomputation in three pairs. Missing,
shorter and corrupted checkpoints cannot pass through a fallback. The shared
store implementation is unchanged. Reporting separates hashing/write/read/upload.

The leased benchmark supervisor binds new stores or sealed preceding producers,
checks explicit full-content hashing and RAM/staging/disk admission, and records
thermal telemetry with an 85 C or lower sensor ceiling. Q2's persistent release
at 07:13:11.718 UTC was verified read-only: no KFD clients, CPU48.125/GPU46 C;
the next GPU run still needs fresh leases. The [predeclared protocol](development/protocols/SSD-GPU-PROTOCOL.md)
covers exact restart/extension through 128K followed by core off/RAM/SSD timings.

Local [CPU receipts](benchmarks/2026-10-02/ssd-qualification/cpu-receipt.json):
14/14 focused checks, full ASan/UBSan 30/30 (CPU77.75/GPU58 C), HIP server/bench
compile/link exit 0 (CPU73/GPU58 C). All commands exit 0. No original-model SSD
result is claimed by this preparation checkpoint.

## Optional SSD prefix persistence — 2026-10-02

Implemented the version 1 component codec, conservative full-file identity,
private quota-limited store, immutable reference pins, bounded staging and one
asynchronous I/O worker in C17. The shared core integrates disk waits through its
existing event loop while runnable inference peers retain their flow credits.
RAM remains default-on; SSD is opt-in with explicit directory, quota and staging
limits. Server and direct core bench expose the same facility and separate disk /
owner transfer timings. See [SSD-PREFIX.md](reference/SSD-PREFIX.md).

Local non-performance tests are now explicitly user-authorized. Headless R5
passes 5/5 and full Debug R9 passes 29/29, including actual synthetic-process
restart, HTTP/Responses and bench graphs. Raw commands, actual exits and
per-second temperature samples are retained under `evidence/ssd-local-r*/`.
R1 keeps its strict-compiler indentation error; R7 keeps 12 failed suites caused
by the loopback sandbox and a selected Python without Matplotlib. R9 uses the
already installed system Python and permitted private loopback sockets; no
packages were installed. Thermal R4/R10/R11 refused before spawning a build at CPU
89/89.625/91.625 C. The successful full suite's observed peak was CPU84.375/GPU61 C.
Subsequent passive readings reached CPU92.625 C with no owned test running.

Runtime checkpoint `9b6c937` includes the final file-length/timer arithmetic and
Release reference-count checks, expanded identity environment inputs and the
thermal guard fixture. On that source, R12 rebuild and focused Debug checks pass
4/4; R13 ASan/UBSan passes **30/30**, with leak detection and halt-on-error enabled.
All five configure/build/test commands exit 0; the sanitizer suite's observed
peak is CPU79.75/GPU57 C. The HIP adapter and both executables compile/link in
`ssd-linked-r2`, exit 0, CPU74.625/GPU53 C, against the existing qualified numerical
archives. The preceding linked build remains a recorded thermal stop at CPU86.5 C
(owned child SIGTERM, child exit -15, guard exit 125). No numerical archive was
rebuilt. [Source and command receipts](benchmarks/2026-10-02/ssd-prefix-cpu/receipt.json)
bind these completed checks to the committed source; earlier fixtures remain
historical evidence rather than final-source acceptance.

Original-weight SSD restart, fit and performance remain unqualified; no new
model run or heavyweight hash occurred. The Q2 thread retains the coordinated
`.157` window. This completes the local contract/build checks, not the SSD device
acceptance gate. No push, deployment or DS4 mutation.

A separately requested fork, **Synapse LIE — DGX Spark**, was initialized in
`worktrees/dgx-spark`, branch `feature/dgx-spark`, at qualified checkpoint
`07427b1`. That thread owns platform/TensorFold investigation and `.158` read-only
inventory; this thread owns the shared SSD core. Active KV paging and PLE/weight
streaming remain distinct from persisted hybrid prefix checkpoints.


## C17 component state and default RAM retention — 2026-10-02

The user's clarification is implemented: RAM retention defaults on (4 GiB,
lazy allocation), SSD remains off and pending. State layout/allocation and
prefix lookup/budgets/LRU are extracted into C17; Qwen AR component geometry
is a C model module. HTTP and `--suite core` share the same engine cache.
No opaque Gufo serializer is used. The explicit friend-access variant changes
three declarations in two pinned headers, rebuilt separately; active numerical
execution remains delegated. Exact-generation resume, SSD, MTP and vision remain
pending. [State contract](reference/STATE.md), [ABI](reference/ABI.md) and [provenance](../third_party/README.md)
record this boundary.

New coverage includes headless capture/restore, domain/layout rejection,
independent clones, budget eviction, cancellation, fail-closed mutating faults,
cache-aware Chat/Responses and default-on/off bench graphs. `.157`
`reactive-cpu-r12` passes headless 3/3, Debug 26/26 and ASan/UBSan 26/26; all nine
configure/build/CTest commands exit 0. R11 also passed. R10 retains two failed
HTTP assertions that assumed cold/warm usage equality or selected usage from
the timing SSE frame; both expectations were corrected, without hiding failure.
Local compile failures R1/R3/R4 are retained alongside corrected R2/R5/R6 and
the successful HIP link receipts; no test or model ran on the editing host.

`--suite state` adds paired full-logit qualification (greedy, seeded sampling,
independent clone) with completed capture/restore/tail timings. GPU campaign
`state-gpu-r1` now passes **16/16 arms** under the [predeclared protocol](development/protocols/STATE-GPU-PROTOCOL.md).
Exact logits/output pass at 512/8192/131072 tokens and 4096-to-8192 extension;
cache-off frontiers match the pristine historical provider. Core warm-cache
TTFT falls from 98384.31 to 224.93 ms at 128K; whole-request throughput rises
from 1.24 to 24.08 tok/s. C8 aggregate complete-wall throughput rises from 51.14
to 106.02 tok/s, with effectively unchanged per-job TG and no added threads.
These are repeated identical-prefix savings, not faster fresh PP. Default-on
HTTP passes on port 8000. [Full values, cold samples, graphs and limits](archive/STATE-GPU-RESULT.md)
are retained; SSD/MTP/vision remain pending.

Runtime checkpoint `4fe6231`; 153 GPU evidence files SHA-verified. Final postflight
at 04:06:08.842 UTC records 32 owned child/supervisor identities absent, KFD empty,
and four unchanged/free leases. Controller retirement was observed separately;
the window was returned to Q2 before offline analysis. No permanent listener,
publication or DS4 mutation.

## First core GPU regression passed — 2026-10-02

`core-gpu-r2` completes all 13 declared arms on `.157`, all exits 0, with the
successful baseline HTTP arm explicitly retained from failed R1. Baseline
`2ba01ed` and candidate engine `81c2f60` use identical official Gufo archives;
helpers are at `04a0642`. Tokens and executor PP/TG frontier hashes match;
core physical replay and HTTP request/output/usage/finish comparisons also pass.

Matched executor median changes stay within 1%. At 131072 fresh tokens, PP is
1347.00 -> 1342.70 tok/s; C8 pure TG is 106.98 -> 107.09 tok/s. The largest HTTP
first-text median increase is 0.35%. Direct C8 core records 128 eight-row batches
and 51.09 output tok/s over total wall, including prefill. These timing scopes
remain distinct; extraction does not introduce a new numerical/reactive gain.
Actual inference thread samples are 35 executor / 36 core-or-HTTP, with loader
totals 51/52. C8 adds no per-request owner threads.

CPU headless/Debug/ASan checks already pass on `.157` (`reactive-cpu-r9`). All
121 collected GPU files verify against their hashes. Closure at 02:13:52 UTC:
owned identities retired, empty KFD, four unchanged/free leases; the controller
and port 8000 are also retired. The window was returned to the Q2 thread.
Full tables, ranges, thread census, retained preflight failure and graphs:
[GPU result](archive/CORE-GPU-RESULT.md). Pi itself was not rerun; numerical ownership,
RAM/SSD reuse, MTP/vision and 1M remain open. Earlier entries below are historical.

## First core GPU regression campaign prepared — 2026-10-02

The operator authorized the first extraction's original-weight GPU test. New
Release builds compare baseline `2ba01ed` and core `81c2f60`, with identical
verified official Gufo archives. `run-bench.py` now binds core input basename,
size and hash to the staged manifest; `smoke-model.py` accepts explicit private
ports and both supervisors record process thread/RSS observations. New fixture
checks cover malformed, ambiguous, changed and symlinked input declarations.

`.157` receipt `reactive-cpu-r8` passes headless 1/1, Debug 23/23 and ASan/UBSan
23/23; all nine configure/build/test exits are 0. The core benchmark suite now
has seven checks. No new engine/provider code changed after `81c2f60`.
The predeclared [GPU protocol](development/protocols/CORE-GPU-PROTOCOL.md) covers HTTP lifecycle and
latency, C1/2/4/8 and fresh 8192/131072-token prefill with exact physical replay.
GPU results are pending; source-bound CPU evidence is not GPU qualification.

`core-gpu-r1` completed the baseline HTTP performance/lifecycle arm, then the
candidate preflight refused port 8000 before model load. Both owned processes
retired, KFD was empty and all four locks were free. The preflight socket lacked
address reuse after server-side TCP close; a new private-port regression fixture
checks both active-listener refusal and retired TIME_WAIT reuse. The corrected
helper uses SO_REUSEADDR (not SO_REUSEPORT). R1 remains FAILED; its successful
baseline arm is retained with explicit hashes for the continuation.
`reactive-cpu-r9` passes headless 1/1, Debug 23/23 and ASan/UBSan 23/23,
including eight core-benchmark checks and the TCP regression. All exits are 0.

## Shared C17 core and direct benchmark implemented — 2026-10-02

`lie_core` now owns the existing reactive worker independently of the HTTP parser:
neutral deep-copied messages/tools, raw text/physical-token inputs, model/job
lifecycle, bounded admission, ready-row batching, demand, cancellation, snapshots
and retirement. The protocol library translates/frees parsed requests; no JSON
object or SSE state owns a core job. `lie/core.h` is experimental client API 1;
executor ABI 2 and the numerical Gufo pin remain unchanged.

`synapse-lie-bench --suite core` directly consumes those jobs and exports physical
input/output witnesses, per-job PP/decode call times, client first-token/total
latency and cohort throughput over total wall time, with optional plots. Historical
executor and HTTP modes retain their separate timing meanings. No new GPU rate is
claimed. Input copy and retained token witnesses add host cost that still needs
measurement. Tool-output semantic events, cache/MTP/vision and evaluation logits
remain open; the library extraction does not complete those engine features.

Coordinated `.157` receipt `reactive-cpu-r7`: headless build 1/1, full Debug 23/23,
ASan/UBSan 23/23; all nine commands exit 0. The six core benchmark tests include
actual graph export. Original-weight execution did not run; Pi/node were not
available to the private CPU runner. Full logs, exact source SHA-256 inventory
and runner remain under local `evidence/reactive-cpu-r7/`. See
[scope, limitations and next gates](development/CORE-EXTRACTION.md).

Next: bind the core input manifest in the coordinated supervisor, qualify the
refactor with the GPU, then implement RAM prefix reuse and complete hybrid state,
optional SSD, MTP/vision and measured model/numerical extraction. No deployment,
push, merge or dependency installation occurred. The earlier design-only entries
below describe their historical checkpoints, before this implementation.

## Reactive core invariant and historical thread audit — 2026-10-02

The shared-core extraction must retain reactive inference: bounded demand/output
credit, immediate ready-row scalar/native-batch dispatch, one device owner,
bounded prefill, cooperative cancellation and completed-work retirement for
every client. Synchronous provider calls remain a separate internal boundary;
moving ownership out of HTTP must not turn generation into an unbounded blocking
loop or duplicate scheduling in clients.

Source and archived harness inspection confirms one direct-benchmark model
caller, or one server device worker plus its HTTP main loop. C1/2/4/6/8 count
sequences, not CPU model threads. The earlier `performance-http-r1` process
observer contains 693 samples, all with 36 OS threads after warm-up. Gufo has
a separate PLE reader pool capped at 32; exact per-TID attribution was not
recorded. Later reactive/full-prefill campaigns did not record process thread
totals, so their application roles and measured older OS count stay distinct.
[Thread scope and receipt](INFERENCE-REACTIVE.md#thread-topology-of-the-retained-tests).
This is a read-only evidence audit and documentation update, with no new GPU
run, runtime change or performance result.

## Shared engine core required before cache implementation — 2026-10-02

The owner clarified that HTTP is a client/protocol layer; engine features must
live in one C17 core reusable by `synapse-lie-bench` and future `lie-chat` and
`lie-eval`. Corrected the architecture diagram, ownership contract and next-step
order accordingly. The core owns lifecycle, scheduling, state/cache, MTP/vision,
model semantics and typed execution observability. HTTP owns parsing and wire
projection. Direct physical-token input preserves benchmark/evaluation semantics.

Source audit confirms partial sharing today: `lie_inference` and `lie_flow` are
common, while `lie_runtime` combines worker and protocol files. The worker owns
`lie_chat_request`, including `json_owner` and transport options; the direct
benchmark independently manages sequences. A shared dispatcher does not yet
establish shared engine lifecycle/cache. The first implementation step is now
the extraction plus an actual direct-core benchmark consumer, before RAM/SSD
features. The executor diagnostic path remains a separately labelled scope.

This checkpoint updates requirements and documented boundaries only. No new
`lie_core` library, client, runtime API or cache implementation is claimed.
Validation: local documentation links/anchors and Git whitespace checks; no
runtime tests or GPU run in this increment. The ensuing ownership refactor
requires direct and HTTP tests plus ASan/UBSan on `.157`.

## C17 separation and cache/MTP/vision assessment — 2026-10-02

Documentation-only assessment: start separating engine policy, model-family
semantics and device/numerical capabilities now, before adding more session-state
features. The present C boundary still delegates model loading/binding,
tokenization, sampling, hybrid state and forward to Gufo C++ classes. Target
C17 ownership of these responsibilities in measured slices; complete removal
of retained C++/HIP kernels and runtime dependencies is a separate explicit gate.
No replacement, ABI symbol, cache flag, MTP or vision capability is implemented
by this assessment.

The first runtime deliverable is C-owned RAM prefix lifecycle/budgets and complete
version-qualified hybrid capture/restore, then optional default-off SSD storage
with explicit directory/quota and bounded staging/I/O. Contracts now include
verified MTP output bursts, rollback/RNG/predictor identity, image identity and
multimodal restart inputs. Existing Gufo snapshot support alone does not include
the external sampler or serialize image pixels. Model-family, weight packing
and platform support remain independent qualification axes; the parallel format
audit does not require a simultaneous engine rewrite.

Updated [backend assessment](BACKEND.md#separation-assessment--2026-10-02),
[architecture](reference/ARCHITECTURE.md), [planned ABI](reference/ABI.md#planned-state-mtp-vision-and-owned-execution-contracts),
[state design](reference/STATE.md), metrics and README. Corrected stale one-row/no-batching
and pending-Pi statements against existing evidence. Validation is documentation
consistency and Git whitespace/link checks only; no source/build/model/GPU work,
new CPU fixture result or numerical/performance claim in this increment.

## Extended-context benchmark client and closure audit — 2026-10-02

The new HTTP `long-context` preset supplies varied deterministic numeric records
at 258794/524288/786432/1004581 prompt targets, output64, physical-count checks,
corpus export/replay, graphs and an hour socket timeout. Capacity and RoPE are
recorded operator declarations; they do not enable backend support. Comparisons
reject different declarations. Current LIE inference remains native 262144;
the pinned provider lacks YaRN and rejects greater capacities in two layers.
No new GPU run, model access, provider change or host tuning occurred.

Fresh `.157` fixtures in `reactive-cpu-r6` pass **21/21 debug and 21/21 ASan/UBSan**,
all six commands exit 0. The client contract includes a synthetic million-token
usage case, exact corpus replay, output-room rejection and scaling mismatch.
[CPU receipt](benchmarks/2026-10-02/long-context-cpu-receipt.json).
These are wire/accounting fixtures, not real million-token inference.

The [closure matrix](development/TEST-COVERAGE-LONG-CONTEXT.md) lists missing repetitions,
HTTP/cache protocols, MTP/quality/vision/loading/memory tests and the real 1M
implementation gates. It also explicitly distinguishes the measured 4.11x gain
over scalar interleaving from the unproven benefit over existing native batching.

## Full-prefill and HTTP campaign completed

`reactive-suite-r5` on `.157` passed 21:57:54–22:19:05 UTC, 2026-10-01.
Twelve direct samples (six sizes, n=2, no discarded warm-up) reach 258794
physical prompt tokens with TG128; each point preserves exact repeat output
and full PP/TG frontiers. Median full PP is 1531.83 at 8192, 1457.88 at 32768,
1354.82 at 131072 and 1270.51 at 258794 tok/s; corresponding TG at the last two
points is 24.73/23.89 tok/s. All actual outputs have 128 tokens.
HTTP adds six full-prefill observations, ten 256-token shape observations
(mean 25.88 output/complete-wall tok/s) and a two-turn 100K conversation.
The latter takes 69.76/71.79s, confirming full-history re-prefill without cache.
Three calibration requests per applicable HTTP preset stay outside averages.
All helper/model/client exits 0; controller/children absent, KFD empty, four
unchanged leases free. Thirty-three collected files match their hashes.
[Full values, times, plots and limits](archive/FULL-PREFILL-HTTP-RESULT.md).


## HTTP 256K and direct Pi acceptance — completed with retained harness failures

Server and worker now admit context through 262144 total tokens, with a dedicated
context CLI parser rather than the 16-bit port parser. HTTP/parser body bounds
are 8 MiB, history bounds 1024 messages, default request deadline 600 seconds;
physical prompt plus requested output must fit, without truncation. The isolated
Pi profile advertises the same limits and a 630-second provider timeout.
`reactive-cpu-r4` on `.157` passed 20/20 debug and 20/20 ASan/UBSan, all six
command exits 0. New fixtures cover >1MiB Chat/Responses, exact byte/message
bounds, 256K chunk accounting and rejection before forward. These are CPU fixtures.
The HIP-linked `http256-r1` server now passes original-weight Chat/Responses at
262075 prompt tokens. Pi 0.87.1 on `.155` passed real read/edit/read over direct
HTTP `.157:8000` in 24.02 s, without a tunnel. Pi/Node remain absent on `.157`.
The firewall-blocked 19879 attempt and a later SCP-marker collection race are
retained as failed campaigns despite their separately passed capacity/Pi checks.
Both servers retired with exit 0, empty KFD and four unchanged free leases.
See [HTTP-256K-PI.md](archive/HTTP-256K-PI.md) for exact evidence and limits.


## Reactive inference GPU comparison passed and persistent checkpoint

The source now lives at
`/home/paperboy/workspace/projects/synapse-linux/synapse-lie/worktrees/openai-reactive-api`.
The old `/tmp/synapse-lie-pi-tools` copy was removed only after all 1608 files
matched and Git worktree registration was repaired across the filesystem move.
The prior benchmark/report/graph checkpoint is `ad02a01`.

The shared C17 `lie_inference` dispatcher now reserves output credit for ready
sequences and calls scalar or native batch decode immediately. It is used by
both the production worker and `synapse-lie-bench`; `--execution serial` keeps
the previous direct path for A/B. Server admission supports up to eight active
sequences, while one remains the default. ABI-2 layouts remain unchanged;
explicit additive admission and per-row completed-outcome entry points carry
no upstream types. New counters distinguish batch calls and selected rows.

Final `reactive-cpu-r3` passed 19/19 debug and 19/19 ASan/UBSan on `.157`,
including error-terminal metadata ordering; fixtures remain NOT-INFERENCE.
After the operator renewed the free GPU window, `reactive-suite-r2` passed
19:24:01–19:59:02 UTC on 2026-10-01 using code checkpoint `0e2bd45`.
Original-weight HTTP lifecycle, Responses, native tools and the seeded
heterogeneous serial/concurrent pair pass; the pair observes 32 native batches.
Direct serial/reactive comparisons use one warm-up and three measured samples
per point at C1/2/4/6/8 and occupied context 0/16K/128K. All physical/output IDs
and full PP/TG frontier hashes match. C8 decode is 107.15 versus 26.08 token/s
(4.11×); all C1 decode medians differ by at most 0.35%. Prefill remains sequential,
and no PP gain or new HTTP speedup is claimed.

All five helpers and GPU children exit 0; final postflight observes unchanged/free
leases, absent owned processes and empty KFD. All 43 archived files and 67 bound
source files verify. The earlier `reactive-suite-r1` refusal at 18:51:29 UTC
(occupied pipeline lease, exit 1, no model attempt) remains preserved.
See [REACTIVE-INFERENCE-RESULT.md](archive/REACTIVE-INFERENCE-RESULT.md).

## Earlier simplified 128K and concurrency comparison

The reusable C17 `synapse-lie-bench` implements AR depth, concurrency, loading
and memory-estimate suites, JSONL evidence and optional SVG/PNG/CSV/JSON exports.
On `.157`, matched original-weight direct-executor single runs passed all eight
depths through physical prefix 131072 (133120 total prompt tokens). At that depth
LIE TG is 24.67 token/s versus direct Gufo 24.71; all physical/output IDs and full
frontier hashes match. Matched concurrency 1/2/4/6/8 passed: at eight users LIE
aggregates 26.07 versus native Gufo batch 107.03 token/s. That measured adapter
used single-row decode; the shared-dispatcher increment above addresses this gap.

Fresh CPU fixtures passed 18/18 debug and 18/18 ASan/UBSan, including the
small-context calibration regression and graph exports. The initial suite retains
its FAILED root and actual exit 1 before any multi sample; the corrected follow-up
ran only missing arms and completed PASS (all six helper/child exits 0).
Final owned PIDs are absent and no known lease holder is observed. These are
simplified direct AR measurements, not HTTP
128K/cache support, MTP or independent numerical qualification. See
[BENCHMARK-RESULTS.md](archive/BENCHMARK-RESULTS.md) and
[CONTEXT-COMPARISON.md](archive/CONTEXT-COMPARISON.md).

## Earlier serial-runtime performance and DS4 coverage

The `.157` GPU performance matrix passed on 2026-10-01: nine direct C1
measurements, 110 measured HTTP requests plus 22 warm-ups across 16 configurations,
24-client admission burst (8 completed, 16 capacity refusals), and the real-model
cancellation/backpressure/isolation suite. CPU fixtures passed 17/17 in debug
and 17/17 with ASan/UBSan on `.157`. Runtime binary remains the earlier API-qualified
`213c91e` build; harness changes add measured clients and prompt metadata.
All four leases were free/unchanged and owned processes absent at final postflight;
KFD was empty. No deployment or publication.

Direct PP medians are 999.65 / 1648.11 / 1608.97 token/s for physical prompt
counts 502 / 2042 / 8191; TG medians 26.87 / 26.07 / 25.98 token/s. C2 serving
roughly doubles request latency with similar aggregate throughput: no reactive
inference speedup is demonstrated. Full timings, sampled resources and limitations
are in [PERFORMANCE-RESULT.md](archive/PERFORMANCE-RESULT.md).

[DS4-COVERAGE.md](development/DS4-COVERAGE.md) records the read-only comparison. Coverage is
not equivalent: vision, MTP, native batching, prefix/snapshot state, extended
sampling and long-context qualification remain among LIE's missing capabilities.
Neither API completeness nor DS4 historical numerical qualification is inherited.

## API implementation

Worktree `/home/paperboy/workspace/projects/synapse-linux/synapse-lie/worktrees/openai-reactive-api`, branch `feature/openai-reactive-api`, created
from `develop`, then fast-forwarded to the existing native-tools base `e3d0c7a`.
The original worktree remains untouched; no merge, push or deployment.
On 2026-10-01 the linked worktree moved out of `/tmp` at the operator request;
all 1608 transferred files matched before removing the old copy. Benchmark
checkpoint: `ad02a01`. Historical evidence retains its original paths.

User direction: general OpenAI functionality, compatible clients through their
ordinary protocol; C reactive execution, tests on `.157` with GPU. New Responses
normalization/wire and sequence sampling build on the typed native tool API and
existing bounded flow. General API coverage remains incomplete; see
[the exact capability matrix](reference/OPENAI-REACTIVE.md).

Remote `openai-reactive-cpu-r3`: all 16 CTest suites pass in debug and with
ASan/UBSan. Local HIP link succeeds against the pinned LIE-owned upstream build.
The earlier compile type mismatch (`int32` prompt versus upstream unsigned
sampler history) and its actual exit code are retained under
`evidence/openai-reactive-build-r2`; the adapter now explicitly copies the typed
history. Original-weight GPU runs `openai-reactive-gpu-r2/r3` passed lifecycle, Responses
JSON/SSE, seeded sampling and a native function round trip. Final server/helper
exits are 0; all four unchanged leases are free and KFD empty at postflight.
See [the precise result and limits](archive/OPENAI-GPU.md).
These statements do not qualify independent numerics, performance or deployment.

# Resumption — original-weight serving smoke and C1 baseline, numerical gate open

Owner: synapse-lie fork; DS4 remains the other agent's project.
Repository: `/home/paperboy/workspace/projects/synapse-linux/synapse-lie` on `.155`.
Branch: `feature/initial-runtime`, from `develop` seed `ce3ce59`.
The runtime increment starts at `79625ce`; the resumed smoke/runner fix starts
at `b7de609`. No workflow or independent review is claimed.

## Current direction — Q2 withdrawn; operate Unsloth with Pi

The owner requested cancellation/replanning of the Q2 work, then prioritized
making the current Unsloth-backed runtime usable from Pi. Active implementation
was restored to **`4307486`**, removing Q2 overlays, fixtures and build helpers.
C17 runtime/server and the original UD adapter are retained unchanged. Historical
reports/evidence and qualified builds are preserved, not active Q2 support.
The [replacement plan](archive/REPLAN.md) puts Pi tool operation first and any future Q2
reference measurement before another port. No new GPU result is implied by rollback.

Rollback is committed as **`ffca17e`**. A proportional baseline check passed 13
CPU suites with ASan/UBSan. A deferred Q2-restart task is in the Synapse backlog;
that capture does not authorize another port or GPU run.

## Server tools — implemented; native Pi CPU round trip passed

The owner rejected a Pi-specific bridge and required completion of the server.
The unexecuted client draft was withdrawn into `pi-client-bridge-rejected-r1`;
no global Pi configuration was changed. New C17 input/output parsing supports
OpenAI tool declarations, structured calls, correlated results, tool choices,
JSON/SSE results and bounded complete-turn validation. The original native Qwen
template is used through an additive C ABI entry point. No numerical kernels,
weights, source dependency or DS4 artifact changed.

`server-tools-final-cpu-r1`: **15 CPU suites pass with ASan/UBSan**, including
nested nonfinite-value rejection and buffered-tool cancellation/error accounting.
The new production candidate `build/server-tools-linked-r2/synapse-lie-server` links unchanged pinned
provider archives; **16 CPU suites pass**, including the actual Qwen formatter.
All compilation/tests are serial/local and GPU-masked. `server-tools-pi-cpu-r4`
proves the installed Pi's **standard OpenAI provider** consumed a structured call,
executed its real `read`, returned the file content and received a final reply
from the synthetic server. It is not model inference. The earlier Pi fixture
failed because 4096 context equaled Pi's fixed safety margin, reducing the output
budget to one token; raw trace/exit and diagnosis remain. The normal profile now
uses matching server/client context 32768, without changing Pi itself.

The actual Unsloth tool session, 32768-context memory/correctness and updated
serving/PP/TG behavior remain untested. No model/GPU run, remote staging, permanent
listener or new lease was started. Current coordination is required before that
next gate. [Exact scope and setup](archive/SERVER-TOOLS.md).

The Q2 sections below are dated records of the now-withdrawn experiment.

## Historical first real Q2 model test — matched performance never established

`q2-model-first-gpu-r1` completed at **2026-10-01 10:15:04 UTC** on `.157`.
The actual antirez Q2 loaded in **11.638 s**, answered exactly `4`, and generated
128 tokens counting from 1 through 46, with finite checked frontier logits.
The second fresh session had **458 physical prompt tokens**, **368.18 PP tok/s**
and **19.79 TG tok/s**. No benchmark warmup/repetitions or matched comparison:
these results do not prove preserved performance versus the historical UD ~26.

Only an isolated test overlay/executable was enabled. Production upload/link
refusals are unchanged. After the operator dedicated the machine to the model,
the proposed 53.5 GB cumulative allocation cap and 32 GiB reserve were removed
before execution. PLE stays disk-addressed with direct-I/O-only test readers;
reported/cumulative bytes are not an independent resident peak. No CPU forward.

Actual binary: `q2-model-first-relink-r1`, using unchanged HIP archives from
`q2-model-first-build-r2`. Both retain Git base `c0d6c6d` plus their source diffs;
no source-SHA inventory was added. All four leases, current preflight and start/end
registration were used; child/supervisor exited 0 and model stat/artifacts stayed
unchanged. At **10:18:10 UTC** both identities were retired, KFD empty and the four
unchanged leases free. No pending GPU job or standing authorization remains.
See [scope, timings and evidence](archive/Q2-FIRST-MODEL.md). Next is matched UD/Q2
performance and independent quality, not another synthetic-only model verdict.

## Earlier Q2 preflight change closed — local build/tests only

The private `Executor::Create` now validates the entire Q2 descriptor profile
before construction or HIP calls. All gate/up/down expert counts and nonempty
storage must match, alongside geometry, layer count and workspace capacity;
up-only mixed formats are also detected. The C17 planner has 720 single-field
rejection fixtures. No kernel arithmetic, `RowScratch`, upload refusal or
production provider change is included.

`q2-admission-linked-r1`: serial masked HIP build/link and host checks pass.
`q2-admission-close-r1`: all 17 CTest suites pass under GCC, Clang and ASan/UBSan;
source identity uses base commit `82df5dd` plus `source.patch`. Earlier RED logs
remain in `q2-admission-dev-r1`. Closure is deliberately limited to the existing
change: no additional memory subsystem or qualification campaign was started.

At that preflight closure, Q2 model loading and PP/TG were **NOT RUN**;
executor/model integration and necessary memory admission remained unfinished. The previous 24+64 GPU results
belong to their recorded binaries, not this newly compiled candidate. No remote
work, GPU run, model access, DS4 change or publication occurred in this closure.
Details: [Q2-HIP.md](archive/Q2-HIP.md#latest-source-closure--executor-profile-preflight).

## Q2 extended operators — two fixes, 24 + 64 controls pass

The renewed GPU window exposed two genuine arithmetic losses: IQ2 vector
integer division discarded fractional eighths; Q2 MMA rounded scale/minimum
products back to half. Both RED failures and raw outputs are retained. The
private, hash-guarded fixes preserve the original tolerance, bounds, workspace
allocation and production refusal.

`q2-operator-extended-green-r3` passes **24/24** (15 IQ2, 9 Q2), including all IQ2
grid entries, varied weight half mantissas, 640/2560 output widths, last expert
511, requested tile widths 16–80, capacity extremes and workspace reuse.
The offline audit checks **1,725,239 raw outputs**, zero mismatches, maximum
absolute error **3.0517578125e-5**. `q2-operator-legacy-green-r1` additionally
passes the **64 original grid-zero controls** on the corrected candidate.
These are operator fixtures, not original-UD model regression or model inference.

A stale source-receipt SHA field in three cloned manifests is explicitly retained
and documented, with additive verified build/source bindings; the audit is not
an unqualified manifest-consistency PASS. See [Q2-EXTENDED.md](archive/Q2-EXTENDED.md).
At 08:14:28 UTC the four GPU attempts' process identities were retired, KFD empty
and all four unchanged leases free. No model payload, benchmark, deployment,
remote build, tuning or DS4 change occurred. Executor integration, arbitrary
activations, memory admission and independent full-model numerics still block
Q2 model loading; antirez and updated-server PP/TG remain NOT RUN.

## Earlier Q2 initial GPU operators — 64/64 pass, model admission still closed

After the fresh `hai la finestra libera` handover, `.157` passed the fixed
`q2-operator-gpu-r1` synthetic suite at **2026-10-01 07:03:42–07:03:46 UTC**
(supervisor scope, not timing/throughput). All four existing leases were held
nonblockingly. The unchanged r5 probe from `dc5ef28` completed 36 IQ2 and 28 Q2
cases with maximum reported absolute errors 4.76837158e-7 and 0 respectively,
within the predeclared tolerance. Padding/output guards pass; no retries.

Raw case records, empty stderr, nine telemetry samples and start/end registration
are retained and pass offline audit. Child/supervisor exit 0, binary/DSOs/power
settings unchanged; owned PIDs absent/KFD empty at 07:04:44, known leases free at
07:07:03 UTC. Desktop clients/denied FD observations remain visibility limits,
not proof of universal exclusivity. No model access, remote build, deployment,
install, tuning or DS4 changes. Full GPU output arrays were not emitted.

**Scope is limited:** grid-zero IQ2, synthetic power-of-two scales/activations,
small ragged output shapes and tiled width 16. Full codebook/shape qualification,
Executor/RowScratch integration, matched UD regression, role-aware memory
admission and independent full-model parity remain. Model upload/runtime gates
stay closed; antirez and new-server PP/TG remain not run. See [Q2-HIP.md](archive/Q2-HIP.md).

## Earlier Q2 HIP implementation — compiled, before the GPU run

The private candidate now routes IQ2_XXS gate/up (vector, paired/grouped and
prefill tiled) and Q2_K down (vector/tiled). Logical 640-float rows are read with
stride 640 directly into zero-padded quantized storage, while weight stride
remains physical 768. No additional FP32 padded copy/kernel is introduced.
C17 planning reserves one executor-owned workspace for quantization, ID maps,
rank/count and grouped-vector scratch; the new projections do not grow a pool
or global ID-map allocation during forward. Shape/format choices stay on the
host, with specialized dot-product kernels and necessary GPU tail guards.

`q2-route-linked-r5` passes HIP compile/link, the shared upstream formatting
script and masked host refusal/scalar-golden checks. The MMQ TU retains the
upstream C++17/gfx1151/NO_VMM flags. The host recipe received formatting-only
changes; eight host cases still pass all compiler/sanitizer variants.
Seventeen default CPU suites pass in `q2-route-cpu-r2`. Delivery audit r2 checks
all final hashes, production refusal and saved-header GCC/Clang binding again.
Its earlier diff-rendering error on an unchanged binary fixture is retained.
All original sources/builds remain intact.

At this implementation receipt, GPU work was still **not run**. The later
64-case run above advances only the initial operator gate; its scalar expression
covers Q2 affine blocks and IQ2 grid-zero sign/scale cases, not the full codebook.
Runtime admission remains disabled pending broader format/shape checks,
full-model memory admission/reference qualification and PP/TG. See
[Q2-HIP.md](archive/Q2-HIP.md). No reactive speedup or cache capability is claimed.

## Q2 compatibility started — private host path passes, GPU path remains closed

The requested Q2-first implementation now has a private, hash-guarded
transitional provider variant: IQ2_XXS/Q2_K storage and binding, F16 HC inject,
physical 768/logical 640 down-input separation, and MXFP4 descriptor recognition
for the unused stored predictor. No `.deps`, model or qualified build was changed.
This extends delegated Gufo; it is not an autonomous LIE C17 model executor.

A full actual-header-derived binder test uncovered another concrete blocker:
missing `rope.dimension_sections`. The failure is preserved. A narrowly identified
text-AR Q2 rule uses canonical [11,11,10,0] sections from the independently fetched
official pinned Qwen config, without replacing malformed explicit metadata or
editing weights. Source/configuration licenses and identities remain separate.

The same actual **11025350 header bytes / 1256 descriptors** now bind all **48 AR
layers** through `ModelWeights::Bind` with GCC and Clang. Declared payload regions
are PROT_NONE in an anonymous virtual view: no weight values or model forward.
Eight synthetic host contract cases also pass GCC/Clang/ASan/UBSan; the source
materializer has seven contract tests. The original source remains pristine.

**This is not yet GPU Q2 compatibility, full-model loading, numerical
qualification or a benchmark.** Runtime linkage is expressly forbidden for this
host variant and device upload has a pre-allocation Q2 refusal. The subsequent
HIP candidate above implements the routing/padding; GPU qualification,
role-aware memory admission and numerical/model/performance gates remain. See
[Q2-COMPATIBILITY.md](archive/Q2-COMPATIBILITY.md). Cache work stays behind this path.

## Antirez prefill/decode benchmark — format admission work

The operator explicitly requires **full prefill and decode benchmarks for the
antirez model**, not substituted UD-Q4_K_XL numbers. Both protected Q2/Q4 files
were inspected read-only at 2026-10-01 03:35/03:42 UTC, bounded to 24 MiB of
metadata/descriptors per file. All inherited stat identities match; no tensor
payload, model load, GPU execution, weight hash/conversion or DS4 modification.

Concrete layout: Q2 has 96 IQ2_XXS AR gate/up tensors and 48 Q2_K down tensors
with physical input 768 versus logical 640. Q4 has Q4_K gate/up and MXFP4 down,
not uniform Q4_0. Both carry one predictor layer and a 102400491520-byte BF16
PLE table; file size is not a measured all-resident GPU budget. MXFP4 geometry was
identified from independently fetched official upstream source, not a sibling
project import. Initial unknown-type observations are preserved.

The pristine pinned Gufo reader rejects MXFP4 in a CPU in-memory fixture probe;
it occurs in both actual files. Binder restrictions (including F16 HC inject),
padded geometry and routed PP/TG dispatch need additional implementation and
qualification. **Antirez LIE PP/TG remains NOT RUN / blocked**, not zero and not
inherited from a DS4 run. No GPU attempt was made against a known parser blocker.
The [per-format benchmark gate](archive/ANTIREZ-BENCHMARKS.md) specifies full fresh PP
512/2048/8192 targets and TG128, C1 direct-ABI and separate HTTP/server lanes,
matched references, numerical/admission gates and all-sample retention.

The formerly untested `tools/gguf-layout.py` draft now has fifteen synthetic
storage/parser tests and a registered CTest suite. RED reproduced invalid bool/
alignment acceptance and FIFO blocking; the corrected reader is bounded,
regular-file-only, identity checked and explicit about incomplete unknown-type
geometry. `antirez-layout-green-r1/r2`: fourteen suites pass GCC/Clang/ASan/UBSan
and Gufo header checks. These are not inference. Native provider/server numerics
and the C17 executor benchmark were not changed by this discovery increment.
RAM prefix reuse and optional/default-off SSD persistence remain unimplemented.

## Latest GPU result — original-weight lifecycle passed

`t0-model-lifecycle-r1`, **23:01:13–23:01:44 UTC**, used source `efcb7fb` and the
HIP-linked `t0-lifecycle-linked-r1` server. All four actual leases, DSO/model/
binary preflight, start/end registration and owned shutdown passed. It is
`MODEL_HTTP_LIFECYCLE_PASS_NOT_NUMERICAL_QUALIFICATION`.

Six JSON/SSE cases preserve READY/4/caffè 🙂, usage and EOS, with valid per-request
PP/TG timings and one timing finish per SSE. Additional cases observed first
cancellation in prefill/decode dispatch, clean retirement, an unread TCP client
stalled at 65 generated tokens for at least 0.511 s, an unaffected arithmetic peer
and matching post-cancellation recovery. Final: **9 completed, 3 cancelled,
0 failed, 79 generated**, no queued/active/blocked jobs; 12 prefill and 89 decode
calls all returned. Server/helper exit 0; binary and five model stat identities
unchanged; no full weight hash. No foreign client observed, KFD empty after exit.
At 23:05:36 UTC, owned processes were absent and all known leases had no holders.

All 228 lifecycle events, raw responses and 29 telemetry samples are retained;
offline audit exit 0. This is a scoped real-model server result, **not** kernel
preemption, native batching, independent numerical equivalence, capacity testing
or a fresh performance baseline. Neither RAM prefix reuse nor SSD is implemented.
Details/identities: [T0-LIFECYCLE.md](archive/T0-LIFECYCLE.md). No deployment or retry left.

## Source increment — executor guards and lifecycle protocol

A fresh read-only target check at **22:09 UTC** observed an active DS4 Q4 benchmark
campaign, KFD activity and all four leases occupied, including the enclosing
pipeline lease. No formal ACK was present. Receipt: `t0-lifecycle-activity-r1`.
No LIE GPU attempt, staging, lock acquisition, heavyweight I/O or foreign process
intervention followed; no background wait/retry. This is a dated observation,
not permission to enter gaps in that campaign.

The C worker now validates returned positions, token/count/stop ranges and text
sizes before publication. Unexpected provider errors or malformed successful
returns fail the runtime and its peers without retry, rather than allowing
uncertain state to remain ready. Controlled CPU fixtures expose the old invalid-
position bug (RED runtime exit -6, `t0-worker-frontier-red-r1`), then test thirteen
fault modes and prefill/decode cancellation with consumer release before return.
Dispatch counters/phase and output-credit stalls are now visible via management;
these are owner intervals, not proof of GPU-kernel preemption.

`tools/serving_checks.py` is intermediate Python qualification tooling, not the
planned C17 benchmark. The explicit `http-lifecycle-v1` suite in the existing
lease-gated supervisor validates JSON/SSE timings, disconnects during observed
prefill/decode dispatch, sustained TCP backpressure, matching fresh/interleaved
peer responses and clean recovery/accounting. Missed windows are INCONCLUSIVE;
all observations and failures are retained. Hash/settings gates precede model
launch. CPU synthetic coverage passes; the subsequent real-model result is
recorded separately above. Protocol and exact boundaries: [T0-LIFECYCLE.md](archive/T0-LIFECYCLE.md).

The default-off optional SSD requirement is retained in commit `7f6a32`, with
RAM reuse independent of persistence. Neither prefix reuse nor SSD is implemented
by this server-hardening increment. Antirez Q2/Q4 and the independent pristine
numerical comparator remain open. The GGUF inspector was an untested draft at
this lifecycle source commit; its later validation is recorded above.

Initial local receipts: `t0-worker-frontier-green-r1` (twelve suites) and
`t0-lifecycle-helper-r1` (initial thirteen suites), GCC/Clang/ASan/UBSan/header only.
Final CPU closures `t0-lifecycle-closure-r1/r2` pass all thirteen suites;
`t0-lifecycle-linked-r1` links HIP and passes masked/no-model/synthetic checks.
Server SHA256: `f71dbe74f95415bbfe1880a2de1804b73adc3ea24eaab371a6308eaaf8b5db0a`.
The second CPU closure additionally covers exact-verified-byte helper loading.
All of these remain separate from GPU qualification.

At **22:42 UTC**, the operator supplied a new GPU window (`hai a disposizione
gpu`). A fresh read-only probe `t0-lifecycle-activity-r2` observed empty KFD,
GPU busy 0%, no inference/model handles and no holders of the four known leases.
No formal ACK was present. This permits preparing a one-shot attempt, not bypassing
nonblocking lease acquisition/admission or claiming global exclusivity.

## Previous source increment — request timing, no new GPU run

User direction: definitive `synapse-lie-bench` in C17; Python may serve intermediate
development/graphs while server functionality takes priority. Pinned Gufo method
review: `fd1710b5fd090880722e0681a868df2006595c73`, separate from the unchanged
provider pin. [BENCHMARKING.md](archive/BENCHMARKING.md) records exact experiment semantics
and current gaps. No upstream benchmark script was run; the complete named tool
is not implemented. Antirez Q2/Q4 discovery remains unqualified and separate;
the previously written `tools/gguf-layout.py` is still an untested draft.

C worker snapshots and JSON/SSE now expose versioned per-request PP/TG executor-
call timing. Physical input deltas are counted once; EOS detection consumes time
but not an output token. Queue, other-session and credit stalls are not phase
compute time. Invalid clocks latch null duration/rates without retrying inference.
Timing/accounting precedes terminal publication; failure/cancellation cannot
produce a successful timing record. No numerical/adapter/executor ABI changes,
new GPU barriers, prefix reuse, MTP, native batching or aggregate latency metrics.

The HTTP regression failed against the prior qualified CPU fixture binary with
`KeyError: 'lie_timings'` (`t0-request-timings-red-r1`, exit 1). Initial eleven-suite
GCC/Clang/ASan/UBSan/header verification passed (`t0-request-timings-green-r1`).
Final eleven-suite GCC/Clang/ASan/UBSan/header closure passed, additionally checking
partial prefill failure and zero-output rates (`t0-request-timings-closure-r1`).
The new private `t0-request-timings-linked-r1` also passed HIP adapter linking,
build-info, no-model and all synthetic tests, with GPU visibility masked.
Server SHA256: `cf6da02e33b6f8c840bbd5693daf9ec74d8cbb2b287e9cead4f9857f194a16f5`.
Test-only link-time clock wrapping
covers completed counts, queue/credit exclusion, in-flight cancellation, EOS,
clock failure/regression/overflow and zero-resolution division. No model access
or GPU execution; previous measured binaries/baselines remain unchanged. This
source-only increment had no new GPU run at its commit. The later lifecycle
run above exercises these timings on the GPU; a new performance baseline remains
unmeasured.

## Latest target result — C1 baseline, 2026-09-30 20:52 UTC

The user's explicit prefill/decode request produced a new C17 direct-executor
harness and leased supervisor, without changing the adapter or numerical sources.
`t0-c1-perf-r2` completed one warmup and three measured fresh-session runs for each
actual prompt size 502/2042/8191, all TG128, common context9216/chunk2048. Median
PP: **988.68 / 1642.65 / 1607.13 tok/s**. Median TG: **26.851 / 26.049 / 25.965 tok/s**.
Full finite PP/TG frontier logits and outputs matched warmup exactly. All nine
measured samples are retained; no profile/tuning/HTTP or outlier removal.

Child/helper exit 0, original stats and artifact hashes unchanged, no foreign GPU
client observed, KFD empty after retirement. Existing governor `powersave`, EPP
`balance_performance`, GPU DPM `auto` were retained. This is a C1 embedded-provider
baseline, not independent numerical qualification or a reactive speedup. Exact
scope, ranges and all conditions: [C1-BASELINE.md](archive/C1-BASELINE.md).

`t0-c1-perf-r1` had failed before model launch on an absent optional sysfs power
attribute, not a GPU/model error. Its failure and the focused CPU RED/GREEN are
preserved; unavailable telemetry is now explicit null/error. No workload or
admission control was weakened. Code commits `cbb06fc` (harness) and `7f85ef8`
(supervisor fix); ten CPU suites pass, including eleven benchmark contract cases,
with GCC/Clang/ASan/UBSan (`t0-perf-cpu-r3`). HIP/no-model receipt:
`t0-perf-linked-r1`; final documentation/source CPU closure: `t0-perf-closure-r1`.

## Previous target result — serving smoke, 2026-09-30 20:07 UTC

A fresh operator handover (machines free, resume LIE) and read-only observation
preceded successful acquisition of all four existing leases. `t0-model-smoke-r3`
passed target binary/DSO preflight but hit a Python runner name collision directly
after server launch; no inference was observed, helper exit 1/child exit -15.
That failure is retained. `http_client` now avoids the collision, with four
CPU-only HTTP regression cases added as the ninth CTest suite. Focused RED/GREEN
and GCC/Clang/ASan/UBSan/header checks passed (`t0-smoke-runner-fix-r1`).

`t0-model-smoke-r4` then passed **all six original-weight requests**: READY, 4 and
`caffè 🙂`, each nonstream and SSE with identical content/usage/stop, one DONE,
clean retirement and server/helper exit 0. Totals: six completed requests, ten
emitted tokens, zero failed/cancelled. No foreign GPU clients were observed;
KFD was empty after shutdown, and binary/model identities were unchanged.
Executed build remains `t0-linked-r4`; no C/C++ runtime source changed.
See [T0-SMOKE.md](archive/T0-SMOKE.md) and its exact receipts. No pristine numerical,
broad quality, concurrency, cancellation-in-flight or performance qualification follows.

## Previous target admissions — 2026-09-30 18:53 UTC

Following the operator's explicit go-ahead after the idle-node inspection,
`tools/smoke-model.py` and the unchanged `t0-linked-r4` binary were staged under
private LIE run directories on `.157`. Two attempts at 18:49 and 18:51 refused
admission on a busy DS4 download lock, exit 1, **before any LIE model open**.
No target model/DSO smoke or inference was performed. At 18:53 a DS4 `native-perf`
warm-up was using the GPU at 98%, with download/qualification/shared locks held.
Do not enter between its benchmark phases. No background retry is scheduled.

See [T0-SMOKE.md](archive/T0-SMOKE.md) for the exact operator-window scope, predeclared
requests, observations and preserved `t0-model-smoke-r1/r2` receipts. Staging a
private test binary is not a service installation or a working-model result.

## Policy and actual status

The user permits embedded Gufo for T0, followed by requirement-driven T1/T2
refactoring toward an autonomous C backend. The older reference-only prohibition
is superseded, not the autonomy goal. See BACKEND.md and INFERENCE-REACTIVE.md.

**The HIP-linked executable has now performed bounded original-weight GPU
inference through C HTTP/SSE, worker, flow and provider binding.** The first real
serving smoke passed, while the complete T0 acceptance gate (including pristine
numerical comparison and real cancellation/backpressure) remains open. Separate
synthetic tests are still distinct from this actual-model evidence.

## Implemented in this increment

- `src/worker.c`: one pthread device owner, eight bounded admissions, one active
  sequence by default or two explicitly configured interleaved single-row
  sequences. Round-based chunk/step scheduling; never native batching by claim.
- Independent worker and consumer references keep jobs alive after disconnect.
  Short metadata gates protect publication and cancellation-latch versus
  sequence detachment. No GPU wait is held under these gates or on the HTTP loop.
- Eight token slots per job, 256 bytes each. Decode reserves/begins before work;
  SSE releases/replenishes credits only after uv_write completion. Nonstream
  reserves a bounded aggregate sink. Active admission is not a measured RAM fit.
- Text request validation and copied ownership; pinned Qwen renderer, thinking
  disabled, context admission before session creation/forward, greedy AR only.
  Streaming UTF-8 replacement decoding is independent of token boundaries.
- Real nonstream JSON and SSE formatting, usage/finish/error terminals, queue
  refusal, disconnect, request deadline and shutdown lifetime handling.
- ABI 2 adds chat preparation and provider metadata/selection. Gufo types remain
  inside the adapter. The neutral worker opens the selected composition binding;
  `lie_gufo_open` remains explicitly Gufo, not renamed into an ownership claim.
- For loaded-runtime backend failure, adapter drains device work before returning
  failure/allowing retirement. Undrainable device failure exits 70 without retry
  or core dump. This exceptional hardware path is compile/link checked, not GPU
  fault-tested. Successful calls have no added device-wide barrier.
- Diagnostics disclose engine, source pin, build label, delegated/synthetic/none
  ownership and unsupported capabilities. `--build-info` opens no model.
  Hardware qualification is false. Worker counters are not remote-delivery ACKs.
- Opt-in `LIE_GUFO_RUNTIME`; real libraries from independently fetched upstream.
  A LIE-owned Qwen-only CMake scope uses the upstream model target and unchanged
  source. It is not the full upstream release build. No numerical port exists.

No tools, native batching, MTP, vision, prefix reuse, RAM/SSD restore or CUDA is
exposed. Unknown memory/latency/throughput/cache metrics remain null. Default
no-model startup still has readiness 503, empty models and chat 503. The synthetic
provider is only in test executables and reports `NOT-INFERENCE`.

## Preserved build/verification evidence

All paths below are local `evidence/` directories; labels are occupied. Receipts
record actual process exit codes, logs and source/binary identities.

| Label | Observed result / scope |
|---|---|
| `gufo-host-r1` | Full upstream configure failed, exit 1: missing rocWMMA header. No install or fake header. |
| `gufo-qwen-host-r1` | Qwen subset archives built, no execution. |
| `t0-runtime-r1` | Eight CPU/synthetic suites passed with GCC, Clang, ASan/UBSan; Gufo header object passed. Before final cancellation/error refinements. |
| `t0-linked-r1` | Link failed, exit 1: omitted upstream sample/argmax translation unit and curl link dependency. Failure preserved. |
| `gufo-qwen-host-r2` | New private subset build includes real upstream sampling unit and curl dependency; original source unchanged. |
| `t0-linked-r2` | Real HIP adapter linked; eight CPU/synthetic suites and no-model smoke passed. No weight/model/GPU execution. Before final refinements. |

`t0-runtime-r2` passed all eight suites in GCC/Clang/ASan/UBSan at
18:11:53–18:12:10 UTC, including the final binding/error/lifetime refinements.
`t0-linked-r3` passed real linking, `--build-info`, no-model and synthetic tests at
18:12:19–18:12:26 UTC, with no model access/GPU execution. Its binary SHA256 is
`b7b42150d070bf91915d2859ce66b71fed2d386f4a7f12682d5e1736309fd1d6`.

The runtime closure labels are **`t0-runtime-r3`** and **`t0-linked-r4`**.
The resumed runner/documentation closure is **`t0-smoke-closure-r1`** (CPU only).
Their `result.json` and delivery receipts, not a label or build target, establish
success and exact source identity. Label-owned build directories preserve earlier artifacts. Local link verification
masks GPU visibility, isolates HOME/cache/temp, records ELF dependencies and
never supplies `--model` to the real server.

Seventeen current default CPU suites: `chat-parser-wire`, `worker-synthetic`, `worker-timing-contract`,
`worker-executor-contract`, `reactive-flow`, `metrics`, `monitor-parser`,
`executor-c-layout`, `http-monitor`, `http-synthetic`, `model-smoke-helper`,
`serving-lifecycle-helper`, `executor-bench-contract`, `gguf-layout-contract`,
`q2-source-contract`, `q2-route-plan`, `q2-hip-source-contract`.
The eight Q2 host C++ cases are a separate optional suite,
not part of the linked production provider. All contract/helper checks
use CPU clock/HTTP/executor fixtures only, never GPU/model execution.
The synthetic suites exercise in-flight cancellation with a barrier, owner-thread
checks, context refusal, queue saturation, a stalled peer, real TCP backpressure,
UTF-8 split/invalid bytes, JSON/SSE equivalence, deadline, poison, error terminal,
FD cleanup and shutdown. They are not GPU/numerical/quality evidence. ASan/UBSan
covers first-party CPU paths and the fixture, not the GPU kernels.
No TSan, independent review or promtool pass is claimed.

Earlier `cpu-closure-r1/r2`, `reactive-closure-r1`, `backend-scope-r1`,
`backend-evolution-r1`, guard refusals and their delivery receipts remain historical
and unchanged. The old policy/guard result is not reinterpreted retrospectively.

## Coordination: resumed window

The 20:01 UTC observation (`t0-node-activity-r2`) followed the operator's fresh
handover. No DS4 ACK was present; none was written for its owner. Both r3 and r4
held pipeline/download/qualification/shared leases, with actual start/end records.
The successful serving r4 exited at 20:07:42 UTC and released its leases.
A later explicit measurement request admitted `t0-c1-perf-r2`, with its own
start/end records and clean exit at 20:52:07 UTC. No foreign process, DS4
source/build/cache/service/profile, model or qualified artifact was modified.
No deployment or background retry is left running.

This operator window is not permanent shared-runner adoption. Further GPU work
requires a current handover/lease, fresh preflight and register entries; idle
hardware or SSH alone is not authorization. See COORDINATION.md.

## Next work under a fresh admitted run

1. Fresh identity/memory/storage preflight; stat the original five read-only files
   against inventory, without assuming old values are live or rehashing weights.
2. Build a private independently pinned pristine comparator; retain compiler,
   flags, source, binary and target DSO identities. Prefer local serial compilation;
   remote GPU compilation needs separate coordination. Full upstream configure's
   missing rocWMMA dependency remains a blocker, not permission to install it.
   Local workspace visibility on `.157` must not be assumed.
3. Original-weight C1 short-context AR: validate physical prompt IDs, completed
   frontiers and output against the independent reference. Bounded HTTP/SSE,
   UTF-8, cancellation, pressure/isolation and retirement now pass in the lifecycle
   run above; this does not replace the numerical comparator or GPU failure gates.
   Define any extended protocol and oracle before execution. No rollout.
4. Only with a correct baseline, collect separate pure-inference traces and test
   a falsifiable internal-reactive change. Completed PP/TG, concurrency and serving
   improvements remain separate; no benefit has been measured yet.
5. T1/T2 refactoring, native C2/4/8, tool continuity, complete RAM/SSD state and
   MTP remain separate gates; CUDA follows qualified AMD work. SSD save/restore is
   a required **optional, default-off** feature with explicit enable, private
   directory and quota controls; RAM prefix reuse must work independently. The
   clarified [state contract](reference/STATE.md) is design only, not a working CLI flag.

Do not reintroduce the historical assistant-imposed 32 GiB reserve as a user
requirement, call the DS4 300K stop an OOM, or import DS4's benchmarks/quality into
LIE. The monitor/UI is still development en_US; v0.1 is not release-ready.

## Full-prompt and served benchmark increment — 2026-10-01

Added C17 `fresh` suite at capacity 262144, all-new PP sizes through 258794 and
actual TG128; report comparison keys/graphs now distinguish full prompt sizes.
Added `synapse-lie-bench --suite http`, an explicitly separate Python client
harness with calibrated full-prefill, ten original prompt shapes, actual
multi-turn history, exact corpus export/replay, usage/TTFT/wall timings and plots.
No server/cache/MTP configuration or tool execution is performed by this client.
`.157` `reactive-cpu-r5`: 21/21 debug and 21/21 ASan/UBSan; six command exits 0.
Raw source hashes/receipts: `evidence/bench-comparable-cpu-r1/`. The subsequent Pi
profile port-only edit selects 8000 at the user's request. The full-prefill and
HTTP benchmark GPU qualification follows these CPU checks, not implied by them.
Detailed reactive attribution is in `docs/INFERENCE-REACTIVE.md`.

## Reactive and long-prefill audit

`docs/INFERENCE-REACTIVE.md` maps reactor, flow credits, worker, shared inference
dispatcher and synchronous adapter boundaries to code and actual evidence.
The C8 4.11x result is attributed to ready-row dispatch plus native batching;
C1 stays within 0.35%, PP remains sequential and no matched HTTP tail-latency
improvement is claimed. `docs/PREFILL-ANALYSIS.md` records actual pinned-source
candidates, including causal block scoring and repeated host prefix scans,
without claiming a profile or implementing speculative optimizations. The
user-requested external comparison research is retained privately in
`evidence/prefill-research-r1/`; public product documentation stays independent.

## 2026-10-02 — Documentation, published charts and bundled libuv

The README now introduces the project, dependencies, build and first request.
Separate [build](guides/BUILD.md), [usage](guides/USAGE.md) and
[benchmark](guides/BENCHMARKS.md) guides replace the previous scattered setup
instructions. [CHANGELOG.md](../CHANGELOG.md) records user-visible changes.
Contracts live under `reference/`, development protocols under `development/`,
and historical implementation reports under `archive/`. Ten small legacy-path
pointers preserve links from immutable dated measurement records.

The [Qwen/Strix Halo page](benchmarks/models/qwen3.8-flash-next/strix-halo/README.md)
contains the eight-depth AR table, concurrent PP/TG and full fresh prefill through
258,794 tokens, with embedded figures and full-precision CSV. Throughput axes
start at zero. The LIE serial control, later reactive result and earlier Gufo
reference are explicitly identified; 4.11× refers to LIE batching versus its
serial control. No new GPU measurement or matched-current-Gufo claim is made.
`tools/render-published-benchmarks.py` regenerates the page and figures from
hash-bound retained summaries. Dated evidence files remain byte-identical.

Official libuv 1.52.1 is bundled at commit
`1cfa32ff59c076ffb6ed735bbc8c18361558661f`, with 127 unmodified files, full retained
license notices and a SHA-256 acquisition inventory. The default static link
removes the server's `libuv.so` dependency. `LIE_SYSTEM_LIBUV=ON` selects system
libuv. The shared headless core still does not link libuv. No package was
installed, no service deployed, and the Gufo provider and model files were not
changed. Python remains a build/test/HTTP-benchmark/plot helper, with no server
runtime dependency; `libsynapse-core` is not linked by this branch.

The pending core-benchmark accounting work is complete: skipped RAM captures,
SSD evictions/skips/errors and final drained allocation/entry counters are now
exported. CPU fixtures reject negative admission counters and check drained
store values. Existing graph-dependent fixtures now skip only their plot checks
when Matplotlib is absent.

Validation: 39/39 CTests pass with ASan, UBSan and LeakSanitizer against bundled
libuv; six focused HTTP tests pass with system libuv. The release server and
benchmark link successfully against the existing verified HIP provider, with
GPU visibility masked for help-only checks. No model is opened. Documentation
checks cover all local Markdown links/fragments and 19 shell examples; source
hashes, CSV rows and graph axes were verified. Local peak CPU temperature was
92.625 °C, below the configured 98 °C ceiling.

Preserved failed attempts: the first vendor configure omitted `configure.ac`,
which upstream CMake reads for its version; two initial CTests found accidental
mandatory Matplotlib use; the first fixture correction missed a dependent CSV
assertion. All were corrected and rechecked. The earlier wrong-target bench
build failure is retained as well. The [CPU receipt](development/validation/docs-libuv-2026-10-02.json)
records commands, actual exits and artifact hashes; raw logs remain under local
`evidence/docs-*`. GPU prompt-retention performance qualification remains pending;
the `.157` preparation window was released before this documentation work.
