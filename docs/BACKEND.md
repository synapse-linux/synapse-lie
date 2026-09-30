# Backend evolution — bootstrap, then requirement-driven refactoring

The destination is **an autonomous Synapse LIE inference backend**, primarily in
C. The user also permits an initial embedded Gufo adapter to establish real
inference before completing that reimplementation. This supersedes the previous
blanket exclusion of an in-process adapter, not the owned-backend objective.
Historical source, failed checks and qualification receipts remain unchanged.

A C ABI over Gufo Model/Session is still delegation, not reimplementation. It is
acceptable as an **explicit transitional implementation**, not something to
rename and claim as an owned backend. Do not require a big-bang rewrite before
learning from real workloads; do not let the prototype define the final limits.

## Two implementations behind LIE-owned contracts

```text
LIE HTTP/SSE, management, reactive admission and device-owner scheduling
                                  |
                         LIE execution contracts
                                  |
        +-------------------------+---------------------------+
        |                                                     |
T0: explicit in-process Gufo adapter              T1/T2: progressively owned
    pinned Model/Session operations                  LIE model/session/executor
    delegated, temporary                             + numerical/device C ABI
        |                                                     |
        +--------------------------- GPU ---------------------+

Pristine Gufo comparator: separate test artifact, never the claimed LIE result
```

Start with in-process integration, not another HTTP service/process hop. Keep
Gufo types/includes and upstream lifecycle assumptions inside the adapter.
Frontend, scheduler, metrics and storage clients consume LIE-owned contracts,
not upstream types. Core/network/scheduling/resource policy remain C17. C++/HIP
is allowed inside the transitional engine and the eventual numerical layer.

Select and disclose the engine explicitly. Once serving exists, report engine
identity, source/build pin, capabilities and ownership (delegated/partial/owned)
in diagnostics and receipts. T0 now reports provider/source pin/build label,
ownership and unsupported capabilities; hardware qualification stays false.
`--build-info` inspects the compiled provider without opening a model. Never
silently fall back from a failing owned executor to Gufo or CPU forward. Runtime
failure after mutation is not permission to retry through the other engine.

## Requirements drive the contract, not the adapter

| Requirement | Required contract / acceptance gate |
|---|---|
| Reactive HTTP/SSE | Bounded admission and output, demand/credit feedback, ordered confirmed tokens, out-of-band cancellation, retirement after in-flight work and writes complete |
| Concurrent agents | One device owner, isolated session/sampler state, fair decode/prefill, measured memory admission; no native batching claim for a serial loop |
| Tool continuation | Explicit turn/wait/resume states and preserved token/template semantics; no retry/replay of external side effects |
| Prefix and SSD state | RAM reuse independent of optional, default-off SSD save/restore with explicit enable/path/quota controls; complete hybrid frontier plus applicable RNG/MTP/continuation state; exact identity/version, pure pre-admission refusal and qualified future continuation after restart |
| Observability | LIE event/accounting definitions, honest unavailable values, completed-work timing; do not equate upstream counters with LIE semantics without checking |
| Portability and evolution | No upstream types outside the adapter; versioned execution/state contracts, capability negotiation/refusal and regression tests when behavior changes |

The bootstrap need not implement every row at once. Unsupported capabilities
must remain explicit. It cannot relax a requirement, invent a metric or emulate
inference to make the transitional engine appear feature-complete.

## Bootstrap and refactoring gates

### T0 — obtain a real, bounded vertical slice

- Agree the DS4 lease before any GPU/heavy-I/O work. Build a pinned, isolated
  pristine comparator; use the original existing read-only model weights.
- Audit the experimental adapter's ownership/completion semantics, link it into
  one device-owner worker, connect bounded work queues and `lie_flow`, and add
  the real model-specific renderer. Object compilation is not this integration.
- Qualify short-context C1 AR first: physical input IDs, completed frontier/output,
  HTTP nonstream/SSE equivalence, UTF-8/terminal ordering, cancellation, client
  backpressure and lifetime safety. Declare matching settings/oracles beforehand.
- Keep readiness false until the real model/executor is usable. Record the result
  as **LIE serving with embedded Gufo**, not an autonomous LIE numerical backend.

### T1 — replace a responsibility at a time

Use observed requirements, behavior and measurements to choose the next slice,
not an arbitrary rewrite order. Candidate slices include C GGUF/binding, memory
and scratch ownership, session/frontier state, batch execution, model graph,
sampling/MTP, and snapshot capture/restore. Useful Gufo kernels and numerical
helpers can be source-ported rather than rewritten without a reason.

For each slice, record the motivating requirement/limitation, current owner,
proposed contract, acceptance tests and the delegation to remove. Keep the prior
qualified implementation as a test reference. Validate the new slice against it
and pristine upstream as appropriate, then the whole path under the original
weights. Retain failures; do not quietly weaken an oracle after a mismatch.

A refactor is complete only when the replacement owns the stated responsibility,
passes its acceptance/whole-path regressions, and the corresponding old delegation
is removed from that selected execution path. CPU tests alone cannot close GPU,
SSE, batching, persistence or performance gates. No automatic rollback/retry of
already mutating inference; selecting an older qualified build is a separate,
explicit operation, not deployment permission.

### T2 — qualify the owned backend, keep evolving

The target ownership remains LIE loading/binding, model topology and layer order,
sessions and hybrid state, memory/scratch, prefill/decode/native batching,
sampling/MTP, and prefix/SSD lifecycle. Numerical/device calls cross a narrow C
ABI. LIE's own executor invokes the operations; an opaque upstream Model/Session
object or a renamed whole engine does not count as reaching this stage.

Exit criteria for the transitional whole-engine dependency: these responsibilities
are implemented and qualified on the owned path; its build/request path does not
require Gufo Model/Session/Executor/DeviceModel; selected kernel reuse has traceable
provenance. HTTP/observability clients still use the LIE contract, or an explicitly
versioned migration, rather than needing a rewrite for each backend replacement.
The old adapter may remain test-only. This is an ownership/behavior gate, not a
claim that all third-party numerical code must disappear.

## Reactive pure-inference investigation

Evaluate reactive execution inside the executor as well as serving, following
[INFERENCE-REACTIVE.md](INFERENCE-REACTIVE.md). Trace actual critical-path stalls,
then test bounded changes to dependencies/synchronization, dispatch, overlap or
buffer liveness. C1 PP/TG, concurrent throughput and HTTP responsiveness have
separate evidence gates. This may motivate a T1 extraction from the synchronous
upstream executor; it is not proof that an outer callback speeds up forward.
No pure-inference performance gain or controlled optimization experiment is established.

## New requirements and upstream evolution

Changes to agent workloads, model families, quantization, kernels/toolchains,
hardware or upstream Gufo should trigger a bounded review: what requirement or
measured bottleneck changes, what contract/state identity is affected, and which
regressions are needed? Pin and evaluate upstream changes; do not blindly track
moving `main` or inherit its benchmark/quality claims. Keep the pristine reference
and locally ported code separate. Adopt improvements selectively, with renewed
numerical, lifetime, concurrency, restore and performance evidence as applicable.

Do not freeze the prototype ABI around Gufo internals or build a universal unused
abstraction. Change contracts explicitly when real requirements justify it;
record unsupported cases and state-format incompatibility instead of concealing
them through fallback. CUDA/DGX Spark follows qualified AMD work through the
same LIE-owned contract principles.

## State formats and provenance

A transitional snapshot may contain a Gufo-specific payload only if its schema
and identity clearly identify that engine/build and all additional continuation
state is accounted for. It is not an owned LIE state format and is not implicitly
loadable by the future owned executor. Refuse incompatible state, or provide an
explicitly versioned and qualified migration; do not reinterpret opaque bytes.

Fetch/reference Gufo independently, not through the DS4 fork. Preserve notices,
licenses, pins and per-component source/hash/change records for numerical ports.
No weight conversion, dependency installation or operational deployment is
implied by permission to use an embedded adapter.

## Current implementation status

The experimental ABI 2 adapter now links under `LIE_GUFO_RUNTIME`, using verified
private Qwen-only upstream archives. Worker/flow/HTTP/nonstream/SSE binding and
pinned chat preparation are implemented. `LIE_GUFO_HEADER_CHECK` remains a
separate object-only check guarded by `LIE_GUFO_ADAPTER_OPT_IN`.

CPU tests exercise the real C serving path with a separate synthetic provider;
no-model smoke also checks the HIP-linked executable. The separately leased
`t0-model-smoke-r4` passed six original-weight C1 JSON/SSE requests with clean
retirement on Strix Halo. This establishes bounded real serving with embedded
Gufo, not pristine numerical equivalence, broad quality or an owned executor.
A later C1 direct-ABI baseline (`t0-c1-perf-r2`) measures completed PP/TG with
repeatable finite frontiers, but no independent comparison or reactive gain;
see [C1-BASELINE.md](C1-BASELINE.md). The later `t0-model-lifecycle-r1` original-
weight run passes bounded real prefill/decode cancellation, TCP backpressure,
peer isolation/recovery and JSON/SSE timings. Full T0 acceptance still needs its
independent numerical and GPU failure gates; this is not native batching or
preemption. Neither v0.1 nor deployment is qualified; see PROGRESS.md for receipts.
