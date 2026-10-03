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

## Active priority — 2026-10-03

The owner postponed new performance campaigns to develop MTP and vision on
separate branches, both based on the shared-core/native-tools checkpoint
`a262902`. Existing benchmark results remain historical and unchanged.

| Branch | Work | Integration gate |
| --- | --- | --- |
| `feature/mtp` | Model-neutral bursts/clients; C predictor, hidden/controller state codec and shared auxiliary persistence. | Device binding, complete pooled predictor history and stable predictor identity; then GPU correctness and AR comparison. |
| `feature/vision` | Owned images/clients; C MRoPE/physical-position state codec and shared auxiliary persistence. | Image identity in lookup/persistence and matching device/restart inputs; then GPU quality and resource checks. |

MTP and vision are capabilities for multiple model families and platforms.
The C17 core owns policy, scheduling, lifetimes and metrics. Each binding owns
predictor/encoder semantics, tensor geometry and exact state contents. Qwen is
the first provider binding, not a core assumption. CPU fixtures use different
provider geometries to exercise that separation; they do not qualify another
real model. Merge the branches and qualify combined operation before advertising
MTP plus vision together. Keep benchmark gaps open until the deferred campaign.


## Two implementations behind LIE-owned contracts

```text
HTTP/SSE adapter, direct benchmark, future chat/eval clients
                                  |
        Shared LIE C17 core: sessions, reactive scheduling, cache and budgets
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
| Multi-model cache | One shared RAM/SSD policy and lifecycle; model-specific complete state descriptors and payload codecs, without Qwen geometry in generic storage/scheduling; qualify a second family and reject incompatible reuse before mutation ([contract](reference/STATE.md#multi-model-requirement)) |
| Model weights on SSD (future) | Keep weight persistence/streaming separate from KV checkpoints: `--model-*` controls, independent storage identity, budgets and lifecycle. KV controls use `--kv-*`. No weight-SSD runtime option is implemented yet. |
| MTP | Explicit predictor identity and admission, bounded draft/rollback state and verified output bursts, target-correct sampling, independent per-row credit and cancellation; compare against AR before claiming speedup |
| Vision | Bounded image decode/preparation and encoder work, explicit physical positions and image identity, compatible state reuse and image/text isolation; linked image helpers do not establish a multimodal API |
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
The controlled ready-row/native-batch experiment establishes a concurrency gain
over scalar dispatch; it does not isolate a reactive-only gain over native Gufo
batching or an optimization inside a single forward. See
[REACTIVE-INFERENCE-RESULT.md](archive/REACTIVE-INFERENCE-RESULT.md).

## Separation assessment — 2026-10-02

**Begin separation now, before extending session state for cache, MTP and vision.**
This is a design decision and extraction order, not an implemented replacement.
The current C ABI already protects HTTP and scheduling clients from C++ types,
but the adapter still owns a Gufo `Model`, `Session` and external `SamplerState`.
Loading/binding, tokenization, sampling, persistent model state and layer forward
remain delegated. The worker creates and closes a sequence per HTTP job; it does
not retain a cross-request prefix. Changing the adapter's language alone would
leave that whole-engine dependency in place.

### Separate engine policy, model semantics and device execution

| Boundary | C17 ownership target | What must remain explicit |
|---|---|---|
| Shared engine core | Admission, lifecycle, reactive scheduling/credit, cancellation, resource budgets, RAM/SSD cache policy and typed metrics | One device owner, bounded queues, confirmed frontiers and failure retirement; HTTP, bench and future chat/eval are clients |
| Model family | Configuration, tensor-role binding, topology/layer order, RoPE, attention/recurrent/PLE state, MTP and vision semantics | Required operations/state components and exact model/format identity; no Gufo classes |
| Device/numerical provider | A versioned C boundary for buffers, kernels, memory, streams and completion | Dtypes, quantization packing, strides/alignment, arithmetic profile, native batching/fusion and qualified hardware capabilities |

Tokenizer/template and sampler components also become C17-owned, with separately
qualified semantics. They must not depend on the HTTP server. Quantization is a
format/codec and kernel capability, independently of model family and platform;
support for GGUF alone does not qualify every tensor packing or dtype. The
parallel official-Gufo compression audit can record these requirements without
coupling its format changes to a simultaneous model-executor rewrite.

All engine features belong to the shared core, including session/cache policy,
MTP, vision execution and model output semantics. HTTP is an external protocol
adapter; it owns JSON/SSE, sockets and wire errors, not engine decisions. Core
requests/events and metrics snapshots use owned C data independent of HTTP
parser lifetimes. The benchmark must exercise this same core directly; future
chat/eval clients must not require an HTTP service or duplicate the engine.
The [source audit and extraction gates](reference/ARCHITECTURE.md#shared-core-and-client-boundary)
now cover the implemented `lie_core` lifecycle and direct `--suite core` consumer,
not just the shared decode dispatcher. Structured tool-output semantics and
RAM state/cache now follows the same neutral core boundary; MTP/vision remain pending.

Keep operations coarse enough to preserve efficient fused kernels and native
multirow work. Avoid a callback per scalar/tensor operation or a universal graph
framework before a real second implementation needs it. An initial owned graph
may remain synchronous; future asynchronous submission must introduce explicit
completion and pinned lifetimes rather than reinterpret completed return values.
New families require model implementations; new platforms require qualified
numerical providers. A C boundary makes these changes local, not automatic.

### C17 milestone and complete C++ removal

The first ownership milestone is C17 engine, model/session/layer control,
loading/binding, tokenizer/template and sampling, calling selected numerical
providers. Existing HIP kernels can temporarily remain in a disclosed C++/HIP
component while this milestone is measured. This is not complete C++ removal.

The user's full C++-removal objective additionally requires replacement of those
kernel sources and any required C++ runtime dependencies on the selected path.
The current subset build uses C++20/HIP20 and requires `gfx1151`; it is not a
portable C backend. AMD's [HIP compiler documentation](https://rocm.docs.amd.com/projects/HIP/en/latest/how-to/kernel_language_cpp_support.html)
describes a C++ kernel language and HIP-capable compilation. Separately compiled
GPU code objects may reduce the host boundary, but do not make their source or
toolchain C17. `extern "C"`, dynamic loading or renaming classes also do not meet
the complete-removal gate.

Qualify an alternative kernel/backend path before replacing working HIP kernels.
The complete gate needs a source/build/dependency inventory, actual original-
weight numerical and performance evidence, and no required whole-engine C++
objects on that path. Keep this gate separate from host/model C17 ownership;
neither architectural separation nor a language change guarantees a speedup.

### First slices and feature order

1. The first shared C engine lifecycle extraction and direct core benchmark
   consumer are implemented and pass the first [GPU regression](archive/CORE-GPU-RESULT.md).
   Owned normalized-message/physical-token inputs are implemented. Complete typed
   model-semantic events,
   capability/state identity and frontier contracts. Use the current adapter as
   an explicitly delegated reference; add capture/restore only for complete
   version-qualified state. Do not introduce a public unused framework.
2. C17 now owns prefix lookup, immutable component storage, pinning/clone
   lifetime, eviction, budgets and Qwen AR state layout. RAM defaults on; only
   SSD defaults off. The transitional adapter binds fields and completed HIP
   copies, without calling the Gufo snapshot serializer. Active device buffers
   and forward math still belong to the transitional provider. Qualify complete
   frontiers and capture/restore cost under [STATE-GPU-PROTOCOL.md](development/protocols/STATE-GPU-PROTOCOL.md).
3. Optional SSD persistence is implemented in the C core with explicit
   enable/path/quota and bounded staging/I/O ([implementation](reference/SSD-PREFIX.md)).
   Disabled means no store I/O. Complete device qualification of restart, corruption,
   incompatible identities, atomic writes and eviction races. This persists
   hybrid frontiers; it does not page active KV or stream weights from SSD.
   The [HTTP/restart/C2 checker](development/protocols/SSD-HTTP-PROTOCOL.md) now passes CPU fixtures
   and [R5 original-weight raw-state checks](archive/CACHE-FEATURES-GPU.md). Shared utility eviction and lossless checkpoint
   compression have independent default-ON build options. [R6](archive/CACHE-COMPRESSION-GPU.md)
   qualifies exact compressed SSD restore at 128K but exposes excessive latency
   for a 15–16% saving; current admission instead requires 2:1 retained reduction.
   A new high-ratio Qwen codec is deferred under the owner's scope clarification:
   the reviewed antirez Qwen path does not provide one. DS4 format compatibility
   remains required. Active-KV compression is future model/kernel work, with the boundary specified
   in [the cache boundary](reference/STATE.md#retention-policy-and-compression-boundary).
4. Add MTP after defining verified multi-token output and resource reservations.
   Admit predictor weights/configuration explicitly. Qualify greedy AR equality,
   sampled target distribution, rejection/residual correction, rollback, per-row
   credit/cancellation and exact compatible resume before performance claims.
   Same seed need not produce the AR stream when speculative RNG draws differ.
5. Add vision with bounded decoded pixels, encoder/preprocessing identity,
   image placement and physical positions. Qualify same-image reuse and
   different-image refusal, mixed histories, cancellation and restart. Vision
   contract/preparation work can proceed independently of MTP; sharing the state
   contract does not require a single monolithic implementation.
6. Extract C17 sampler/tokenizer/binding, state layouts and layer graph in
   measured slices, replacing each corresponding Gufo delegation. Retain
   qualified kernels through the C numerical boundary until their replacement
   separately passes the complete C++-removal gate.

The first feature deliverable after core extraction, **RAM prefix reuse through
the same core in direct benchmark and HTTP**, is implemented and GPU-qualified.
Optional SSD restore follows its separate qualification protocol. The historical
two-turn 100K HTTP experiment re-prefilled the whole history and took
69.76/71.79s; it does not measure the later cached path.
See [full timings](archive/FULL-PREFILL-HTTP-RESULT.md), [state contract](reference/STATE.md),
[future execution contracts](reference/ABI.md#planned-state-mtp-vision-and-owned-execution-contracts)
and the [remaining qualification matrix](development/TEST-COVERAGE-LONG-CONTEXT.md).

For every extraction compare identical physical inputs, weights/format,
context/RoPE, chunking, sampling and cache policy on `.157`. Preserve the current
native-batch control and separately measure C1 PP/TG, C2..8 aggregate throughput,
HTTP TTFT/inter-token percentiles, allocation peaks and snapshot overhead. Use a
predeclared regression bound and repetitions sufficient for observed variance;
do not accept an ownership rewrite merely because it compiles. Cache-hit tests
must distinguish reused tokens, new prefill, capture/read/upload costs and total
request latency. CPU fixtures/sanitizers qualify their C contracts, not GPU
equivalence, memory fit or numerical speed.

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

RAM snapshots now use the LIE C17 component representation. The user's clarified
requirement supersedes the earlier option of caching opaque Gufo payloads.
Do not reintroduce that serializer when adding SSD: persistent identity and
encoding belong in the shared core. Existing foreign formats remain incompatible.

Fetch/reference Gufo independently, not through the DS4 fork. Preserve notices,
licenses, pins and per-component source/hash/change records for numerical ports.
No weight conversion, dependency installation or operational deployment is
implied by permission to use an embedded adapter.

## Earlier Q2 experiment withdrawn

This section records the earlier rollback on this branch. Later work in
`feature/antirez-compat-audit` is separate and does not inherit its qualification.
The owner canceled the earlier Q2 extension. Active code/build/tests are restored to
`4307486`; historical reports and evidence remain archived. Gufo is not assumed
to be the basis of another Q2 attempt. The [replacement plan](archive/REPLAN.md) requires
a working native Q2 reference and an early matched comparison before more porting.
The delivery uses the existing Unsloth runtime through a general OpenAI-compatible
server, with Pi as an ordinary client. This change does
not cancel the C17 ownership objective or claim it has already been achieved.

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
see [C1-BASELINE.md](archive/C1-BASELINE.md). The later `t0-model-lifecycle-r1` original-
weight run passes bounded real prefill/decode cancellation, TCP backpressure,
peer isolation/recovery and JSON/SSE timings. Full T0 acceptance still needs its
independent numerical and GPU failure gates; this is not native batching or
preemption. Neither v0.1 nor deployment is qualified; see PROGRESS.md for receipts.

Subsequently, the shared C readiness/credit dispatcher added native AR batching
through eight rows while retaining scalar dispatch for a single ready row.
The matched `.157` serial/reactive campaign and production HTTP checks are in
[REACTIVE-INFERENCE-RESULT.md](archive/REACTIVE-INFERENCE-RESULT.md): C8 aggregate TG
improves 4.11× with exact tested frontier/output equality, while C1 remains
within 0.35% through occupied 128K. This closes the measured concurrent-dispatch
gap; numerical ownership, internal asynchronous forward, MTP and the independent
quality/fault gates remain separate.
