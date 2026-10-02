# synapse-lie — Local Inference Engine

Primarily C17, initially targeting Qwen3.8 Flash Next on AMD Strix Halo. An
**explicit embedded Gufo adapter** bootstraps inference; it is subsequently
refactored toward LIE-owned model/session/memory/execution. Delegation is not
reimplementation. See the [backend evolution contract](docs/BACKEND.md).

## Current implementation: reactive OpenAI text/function API

The isolated `feature/openai-reactive-api` increment adds stateless Responses
JSON/typed SSE and per-sequence sampling to the same C demand-driven worker/flow.
See [API surface, reactive ownership and explicit limits](docs/OPENAI-REACTIVE.md).
It is not complete OpenAI platform coverage. Tests run on `.157`; CPU fixtures
and original-weight HIP evidence remain separate.

Native AR batching through eight rows is implemented. Cross-request prefix
reuse, optional SSD state, MTP and vision remain implementation gaps. The
[separation assessment](docs/BACKEND.md#separation-assessment--2026-10-02) defines
the C17 engine/model ownership target and phased removal of C++ dependencies;
the [RAM/SSD state contract](docs/STATE.md) requires independent RAM reuse and
explicit opt-in persistence with directory, quota and bounded I/O controls.
The [shared-core contract](docs/ARCHITECTURE.md#shared-core-and-client-boundary)
places engine features behind a common C17 API for HTTP, direct benchmark
and future chat/eval clients. `lie_core` now owns model/job lifecycle, copied
normalized input, reactive scheduling and output retirement independently of HTTP.
`--suite core` exercises it directly with raw text or physical token IDs and
exports latency/prefill/throughput graphs. The [extraction receipt](docs/CORE-EXTRACTION.md)
records headless, Debug and ASan/UBSan checks on `.157`; GPU regression remains open.

## Native tool API baseline

The C17 server now accepts OpenAI function tools, assistant calls and correlated
tool results, returning structured calls in JSON/SSE. The existing Qwen formatter
is used through the adapter; numerical kernels are unchanged. **Pi's standard
OpenAI provider has completed a real `read` tool round trip against the synthetic
CPU test server**, without a custom extension. The linked Gufo build and CPU
template checks pass. On this isolated branch, the original-weight HIP run now
passes a native function call/result and Responses JSON/SSE; see
[the exact GPU scope and cleanup](docs/OPENAI-GPU.md). Pi 0.87.1 also passes real read/edit/read against this GPU model over direct
HTTP on `.157:8000`; [HTTP 256K and Pi evidence](docs/HTTP-256K-PI.md) separates
that tool test from the successful 262075-token capacity requests.
See [server tools, limits and the normal Pi profile](docs/SERVER-TOOLS.md).

The original-weight records below precede the tool extension.

The C worker, bounded admission, reactive flow and HTTP nonstream/SSE path are
implemented. The optional HIP executable **links actual pinned Gufo code**.
On 2026-09-30 at 20:07 UTC, after a fresh operator handover and lease acquisition,
`t0-model-smoke-r4` ran the original UD-Q4_K_XL model on Strix Halo: all six
predeclared JSON/SSE requests passed, with identical content/usage/finish per
pair and clean shutdown. This is **LIE serving with embedded Gufo**, not an owned
numerical backend or full numerical/quality/performance qualification.

Earlier lock refusals and a subsequent runner defect are preserved, not erased
by this success. The runner fix has a CPU-only regression test.
See [the exact smoke scope and record](docs/T0-SMOKE.md).

Without a configured model, readiness remains 503, models is empty and chat is
503. No production fake-output switch exists. A separate `test-synthetic-server`
is visibly labelled `cpu-test-fixture-NOT-INFERENCE` and is never model evidence.
A scoped [C1 executor baseline](docs/C1-BASELINE.md) is now measured: at actual
prompts 502 / 2042 / 8191 tokens, median PP is 988.68 / 1642.65 / 1607.13 tok/s,
and TG128 is 26.851 / 26.049 / 25.965 tok/s. Three measured repetitions per size,
context 9216, chunk 2048, fresh sessions, original UD-Q4_K_XL, no HTTP or tuning.
This is embedded-provider throughput, not a reactive gain or independent comparison.
**v0.1, full numerical/hardware qualification and deployment remain open.**

New server source adds C per-request [PP/TG timings](docs/HTTP.md#per-request-executor-timings)
in JSON/SSE: completed synchronous executor-call wall time, excluding queue/credit
waits and HTTP delivery. CPU clock fixtures and the new original-weight lifecycle
run verify this contract; it is not a new throughput baseline. The C17
`synapse-lie-bench` now implements a simplified direct-executor AR depth and
concurrency suite, with optional SVG/PNG and CSV/JSON exports. Python handles
lease supervision and graph generation. See [usage and scope](docs/CONTEXT-COMPARISON.md)
and [methodology/prerequisites](docs/BENCHMARKING.md). The executable also has full-prompt `fresh` and a separate Python HTTP client
harness (`--suite http`), including exact corpus replay and multi-turn timing.
The [full-prefill/HTTP result](docs/FULL-PREFILL-HTTP-RESULT.md) reaches 258794
physical prompt tokens and records a real 100K follow-up. Cache/MTP execution,
cold-file loading and exact allocation peaks remain open.
The [test coverage and 1M gate](docs/TEST-COVERAGE-LONG-CONTEXT.md) list the remaining
work. A dedicated HTTP `long-context` preset prepares reproducible 256K/512K/768K/1M
workloads; the current LIE provider still supports native 256K only.

**The Q2 experiment has been withdrawn at the owner's request.** Its active
source, recipes, build helpers and tests are removed; rollback commit `ffca17e`
restored the original-Unsloth baseline `4307486`, before the new server tool work. The C17 server/runtime, original Gufo
adapter and UD measurements are retained. Git history, reports and local evidence
remain as an archive, not current build instructions or Q2 support.

**Current scope: a general OpenAI-compatible server and measured reactive
inference**, using the existing Unsloth model. Pi uses the standard client
protocol; no Pi-specific server interface is required. Q2 is deferred under the [replacement plan](docs/REPLAN.md):
measure a working native Q2 reference first, then compare the smallest integration
before undertaking another port. No performance preservation has been demonstrated.

The server now also validates returned executor frontiers and token-text bounds
before publication, fails closed across peers on provider contract errors, and
exposes dispatch/credit-stall diagnostics. The [T0 lifecycle protocol](docs/T0-LIFECYCLE.md)
exercises prefill/decode cancellation, a stalled SSE client, peer isolation and
recovery. Both its synthetic CPU checks and the separately admitted original-
weight **GPU run** (`t0-model-lifecycle-r1`, 23:01 UTC) pass. Final counters are
9 completed / 3 cancelled / 0 failed, no active/queued/blocked jobs, clean exit and
unchanged binary/model stat identities. This does not establish native batching,
GPU-kernel preemption, independent numerical equivalence or a reactive speedup.

## Reactive path

```text
HTTP admission -> bounded queue -> one device-owner worker -> lie_flow -> SSE write
                                          ^                              |
                                          +------ credits / release -----+
disconnect / deadline -> flow stop + executor cancellation latch -> safe retirement
```

Eight admitted jobs; one active sequence by default, optionally up to eight
with `--max-active`. The shared C inference dispatcher gathers prefilled rows
with available output credits and invokes native decode batches immediately.
A single ready row keeps the scalar path; no timer waits for peers. Each flow has eight
preallocated 256-byte token slots. Text-only SSE keeps a loan until its write
callback; nonstream and tool-enabled turns drain into bounded aggregation buffers.
Tool-enabled SSE publishes the validated complete message before its finish,
usage and DONE; it is not incremental argument streaming. Wakeups use eventfd/poll and
libuv, not periodic token polling. CPU fixtures exercise deterministic failure/
lifetime edges; the separately leased GPU lifecycle run covers bounded real-
model UTF-8, cancellation, slow-client pressure, peer progress and retirement.

[REACTIVE.md](docs/REACTIVE.md) specifies ownership and remaining gates. Reactive
scheduling **inside pure inference** is a separate [investigation](docs/INFERENCE-REACTIVE.md):
the shared ready-row dispatcher is implemented and GPU-tested on `.157`.
At eight users, median aggregate decode is **107.15 versus 26.08 token/s** on
the serial path (**4.11×**); C1 decode medians stay within 0.35% through occupied
128K. Physical inputs, outputs and full PP/TG frontier hashes agree. See
[complete PP/TG tables, graphs and limits](docs/REACTIVE-INFERENCE-RESULT.md).
This measures concurrent batching; numerical kernels remain unchanged and no
new HTTP latency improvement is claimed. The [implementation audit](docs/INFERENCE-REACTIVE.md#implementation-audit-how-far-the-reactive-flow-reaches)
records exactly where the flow stops; [prefill analysis](docs/PREFILL-ANALYSIS.md)
separates cold long prompts from cache-dependent follow-ups. No JVM, Project Reactor
or Reactive Streams TCK claim.

## CPU build and verification

Installed dependencies: Linux, C17 compiler, CMake, pkg-config, libuv, llhttp,
json-c, libcurl, Threads and libm. Python is development/test tooling only.
CPU benchmark tests additionally need installed OpenSSL Crypto development headers.
Nothing is installed by the build.

```sh
cmake -S . -B build/debug -G Ninja -DCMAKE_BUILD_TYPE=Debug
cmake --build build/debug -j1
ctest --test-dir build/debug --output-on-failure

# Use a fresh build label; local serial sanitizer check, no model:
cmake -S . -B build/new-cpu-label -G Ninja -DCMAKE_BUILD_TYPE=Debug -DLIE_SANITIZERS=ON
cmake --build build/new-cpu-label -j1
env HIP_VISIBLE_DEVICES=-1 ROCR_VISIBLE_DEVICES=-1 CUDA_VISIBLE_DEVICES=-1 \
  ctest --test-dir build/new-cpu-label --output-on-failure
# The .157 qualification capsules retain explicit source SHA-256 inventories.
```

Twenty-three CPU suites cover flow, parser/UTF-8/wire, worker, metrics, monitor parser,
C ABI layout, HTTP/monitor, HTTP/SSE with the separate synthetic executor,
CPU-only smoke-runner HTTP/identity checks, the executor benchmark contract,
per-request completed-call timing with a test-only deterministic clock,
executor failure/dispatch contracts, the HTTP lifecycle checker, native tool
protocol and HTTP tool round trips, Responses, shared inference dispatch,
256K admission, headless core ownership and direct/core/HTTP benchmark accounting. An additional formatter test is available
in the linked Gufo build; the installed-Pi integration check is separate.
The withdrawn Q2 tests remain only in Git history and local evidence.
The active tests cover bounded overload, stalled consumers, peer progress, disconnect,
in-flight cancellation, poison, error terminals and shutdown. They do not
qualify real model output, numerical equivalence, native batching, GPU faults,
state restore, memory fit or performance. No TSan/independent review claim.

## Explicit HIP build, local compilation only

Additional installed toolchain/libraries: C++20, HIP/ROCm, hipBLAS, hipBLASLt,
rocBLAS, hipCUB/rocPRIM headers, ICU, OpenSSL, PNG and JPEG. Runtime/source
provenance and licensing are in [third_party/README.md](third_party/README.md).

```sh
# Only on a fresh checkout; fetch refuses an existing source directory:
python3 -B tools/fetch-gufo.py
python3 -B tools/build-gufo.py new-gufo-label --qwen-only
python3 -B tools/verify-linked.py new-link-label build/new-gufo-label
build/new-link-label/synapse-lie-server --build-info
```

The Qwen-only build uses unchanged upstream source and the upstream model target;
it is a **LIE-owned build subset, not the complete upstream release build**.
It avoids an unrelated full-tree rocWMMA requirement, without fake headers.
Both source and private archives are verified before linking. Compiler commands,
failures, hashes and logs are retained. Verification masks GPU visibility, uses
private HOME/cache directories, and starts only no-model or synthetic tests.
No weights, kernel execution, remote build or dependency installation occurs.
The independent `LIE_GUFO_HEADER_CHECK` option still builds only an object.
The optional HIP build also provides `lie-executor-bench`; its real-model use is
lease-gated by `tools/bench-model.py` and the [C1 protocol](docs/C1-BASELINE.md).
The separate `test-synthetic-bench` is NOT-INFERENCE.

The same opt-in build provides `synapse-lie-bench` and the benchmark-only
`synapse-lie-bench-gufo-reference`. Both use the original HIP executor; the latter
exercises native upstream batching. On shared `.157`, real-model invocations
run under `tools/run-bench.py` with a fresh admitted manifest and four leases.
The new `--suite core` mode binds its input file to the run manifest and staged
SHA-256 inventory. Its first GPU qualification follows the
[shared-core regression protocol](docs/CORE-GPU-PROTOCOL.md).
`synapse-lie-bench --help` opens no model. Graphs can be generated afterwards:

```sh
python3 build/openai-tools-link-r1/synapse-lie-bench-report.py single.jsonl \
  --output charts --compare gufo-single.jsonl
```

The optional Matplotlib dependency is required only for graph export; no automatic
installation. CPU fixture plots are visibly marked NOT-INFERENCE.

After the coordinated lease, fresh preflight and private runtime setup—not as
part of the local verification—an original-weight candidate can be started with:

```sh
# On the qualified target, with private HOME/XDG_CACHE_HOME and the original
# read-only first shard. MODEL is explicitly supplied by the operator.
build/new-link-label/synapse-lie-server --model "$MODEL" \
  --context 4096 --prefill-chunk 2048 --max-active 1 \
  --port 19879 --management-port 19880
```

Opening succeeds asynchronously on the worker; health becomes ready only after
model/executor open, and goes unavailable on poison. Readiness is not a quality
certificate. `--build-info` never opens a model. Diagnostics disclose source pin,
build label, delegated ownership, capabilities and `hardware_qualified:false`.
A build label locates evidence; it is not self-attestation.

The server accepts text `system/developer/user/assistant/tool` messages, OpenAI
function tools, per-sequence sampling (greedy by default), thinking off, 1–4096 output tokens and physical
context-budget validation. The [Pi profile](config/pi-unsloth.models.json) requires
`--context 262144` and direct LAN port 8000; use the supervised recipe in
[SERVER-TOOLS.md](docs/SERVER-TOOLS.md) rather than the small-context example above. Unsupported
controls/images are explicit errors. See [HTTP.md](docs/HTTP.md) for the subset.

## Management and monitor

```sh
build/debug/synapse-lie-server --port 19879 --management-port 19880
build/debug/synapse-lie-monitor check --url http://127.0.0.1:19880
# Exit 3 while model readiness is unavailable:
build/debug/synapse-lie-monitor check --require-ready
build/debug/synapse-lie-monitor watch --duration 10 --interval 1
build/debug/synapse-lie-monitor record --duration 10 --output run.jsonl
```

Open `http://127.0.0.1:19880/monitor`. Missing memory/cache/latency/throughput
values remain null. The page is an en_US development fallback, not a localized
release GUI. SIGINT/SIGTERM waits for owned work/write retirement; cancellation
is not GPU preemption. **Keep loopback defaults:** no TLS/authentication exists.
No service, deployment, merge or publication is implied.

## Further contracts

[GPU performance results](docs/PERFORMANCE-RESULT.md) ·
[128K and native-batch comparison](docs/BENCHMARK-RESULTS.md) ·
[Performance protocol](docs/PERFORMANCE-PROTOCOL.md) ·
[DS4 coverage comparison](docs/DS4-COVERAGE.md)

[Progress/evidence](docs/PROGRESS.md) · [Architecture](docs/ARCHITECTURE.md) ·
[Execution ABI](docs/ABI.md) · [Metrics](docs/METRICS.md) ·
[State design—not implemented](docs/STATE.md) · [Baseline](docs/BASELINE.md) ·
[DS4 coordination](docs/COORDINATION.md)

Next: qualify the extracted core on the GPU with matched inputs, then implement
C-owned RAM prefix policy and complete hybrid capture/restore, followed by
optional SSD persistence, MTP/vision and measured T1/T2 extractions. Independent
numerical/quality and GPU failure gates remain open; future platform providers
require their own qualification. Native AR batching and real Pi read/edit/read
already have scoped original-weight evidence. Replayed tool history is not prefix reuse.
