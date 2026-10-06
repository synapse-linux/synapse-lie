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

## Current roadmap — 2026-10-05 UTC

Strix Point integration is merged into `develop` at `30598a3`; current context
and OpenAI work remains on `feature/context-million-openai`. Recorded GPU
results belong to their stated source and binary identities. They do not
automatically qualify a later runtime or another model/platform.

This is the work queue owned by this thread. Separate DGX Spark/CUDA,
Antirez weight-format/quantization and Strix Point port tasks stay with their
assigned agents. Unspecified future weight streaming, additional model families
and new client applications are not queued here. Their architectural boundaries
do not constitute implementation tasks. GPU qualification in this queue uses
`.161` with fresh coordination and admission for every run.

Item 1 records completed qualification. The active queue is items 2–7 below.
At the owner's request, Terminal Bench (item 2) is deferred until the functional
modifications and their qualification are finished. Continue items 3–7 first;
the next source work is the remaining C17 extraction (item 7). No Terminal Bench
client/server restart or machine reservation is queued in the meantime.

1. **Completed: OpenAI GPU controls for the r11 runtime.**
   The corrected `abb69d5` runtime passes the same 34 original-weight checks
   in AR and explicit MTP, including tools and 21 additional controls. The new
   MTP window has server/client/controller/supervisor exits 0, fifteen verified
   artifacts and complete process/service/lease closure.
   [AR and retained failures](development/validation/openai-controls-point-gpu-2026-10-04.json) ·
   [MTP qualification](development/validation/openai-controls-mtp-point-gpu-2026-10-04.json).
   This closes these wire/lifecycle checks for r11; later filters, fixed-EOS
   measurements and steering require their own qualification.
2. **Deferred: run Terminal Bench after the functional modifications.** Use the pinned
   Terminal Bench Mini smoke task, then Core-19 with unchanged instructions and
   verifiers. Record task rewards, transcripts, truncation and infrastructure
   failures separately. Its Terminus text command protocol and native OpenAI
   function calls have separate checks; clients execute the commands.
   The shared core now resolves omitted/null HTTP output budgets after prompt
   preparation, preserving the existing 4,096-token output ceiling, and exposes
   model context/output limits. Nine Debug and nine sanitizer host checks pass.
   The new r12 AR runtime passes 37 original-weight HTTP checks, including actual
   327-token omitted/null output in both APIs; the new MTP gate is interrupted
   by an external GPU client. The newer integrated `1bff953` runtime now passes
   all 37 checks in both AR and MTP on `.161`; the interrupted result remains
   evidence for r12. Earlier preparation verifies the unchanged smoke source,
   client and cached image, plus 4/19 cached Core-19 images; it records no task
   score. The newer finite-value/cache runtime `2359488`
   also passes AR37/MTP37. Its unchanged Core-19 smoke now passes **1/1 task at
   the first attempt**, with CPU/GPU/process/container/lease/HTTP-permit closure
   verified. The full **19-task** run started at 20:08:35 UTC with CPU client
   `.157` and GPU HTTP port 8000 `.161`, then was stopped by the owner at
   21:42 UTC before any task completed. Processes, owned task containers,
   HTTP8000 listener, original leases and the temporary HTTP permit are closed;
   the preexisting router is restored. No full score is qualified. The later
   run must use the finished runtime and a freshly coordinated placement,
   preserving original conditional attempts, C1 and three hours per attempt.
   [Smoke qualification](development/validation/terminal-smoke-point-gpu-2026-10-05.json) ·
   [Full-run startup](development/validation/terminal-full-point-start-2026-10-05.json) ·
   [Operator stop and closure](development/validation/terminal-full-stopped-point-2026-10-05.json).
   [Current GPU receipt](development/validation/c17-finite-cache-point-gpu-2026-10-05.json).
3. **Close full 1M context acceptance.** The newly declared `1bff953` `.161`
   run completes all **1,048,448 physical prefill tokens and 128 output tokens**
   with explicit YaRN4 and `--ignore-eos`. The
   [capacity/function receipt](development/validation/physical1m-fixed-point-gpu-2026-10-05.json)
   verifies actual retirement, collection, model identities and service/lease
   closure. The older natural-EOS43 failure remains unchanged. Long-context
   recall checks still need completion; this single run is not a matched
   performance comparison. Native live progress also reaches its confirmed
   final snapshot, separately from process and lease retirement.
4. **Finish the requested Gufo/Halogen benchmark methods.** Compare full cold
   prefill and decode through 1M, and multi-user C1/2/4/6/8, with matched physical
   work, cache policy, output length, repetitions and server lifecycle. Retain
   PP, TG, TTFT, resources and correctly scaled graphs. Profile the prefill
   decline above 256K and separate batching from reactive responsiveness.
5. **Complete DS4 directional steering in LIE.** Load its per-layer `.f32`
   directions, validate geometry against the loaded model, and expose FFN and
   attention scales through model-neutral shared-core contracts used by HTTP
   and bench. The [owned C17 implementation](development/STEERING.md) now covers
   immutable banks, scale transactions, history/cache identities and RAM/SSD
   metadata. Direct C model admission and session policies are wired in the
   provider source to prefill, AR and batch AR/MTP, committing only the actual
   retained frontier. The provider source now binds policy metadata to model
   capture/restore, retaining DS4 framing and validating combined semantic scope
   before transfer. Shared-worker admission/resource projection, scoped text
   lookup and initial server/native core bench controls are wired. Twenty-four Debug
   and twenty-four sanitizer host checks pass, including synthetic AR/MTP/vision
   RAM/SSD process restart and both HTTP APIs. Asynchronous shared-core job
   changes now preserve past state, update mixed-history scopes and isolate
   concurrent policies in host tests. The direct provider's graph/controller
   invalidation passes syntax checks. Copied native benchmark schedules now
   split prefill and cap each AR/MTP row at exact physical boundaries. Stored
   requests have asynchronous live controls and confirmed snapshots, with an
   explicit index for independent multi-choice controls. Both HTTP APIs accept
   copied creation-time plans and report exact application/unreached steps.
   Host tests cover cache-boundary limits, full plan identity and charged retained
   choice lifetimes; original-weight GPU qualification remains open.
   DS4's `--dir-steering-file`, `--dir-steering-ffn` and
   `--dir-steering-attn` now select fixed initial model-wide scales through the
   same core used by server and bench.
   Cover both prompt evaluation and generation, session scale changes,
   cache compatibility and AR/MTP interaction. Require unchanged baseline output
   with steering off, malformed-vector refusal and measured quality/performance
   with steering on. DS4 documents Qwen's 48-by-2560 bank and its HC branches;
   that implementation is Metal-only, so it is not evidence for LIE HIP.
   [Upstream steering contract](https://github.com/antirez/ds4/blob/main/dir-steering/README.md).
6. **Complete DS4 generation-temperature and sampling-profile coverage.**
   Temperature already exists in LIE. Qualify the greedy temperature-0 baseline
   and the declared temperature-1 profile with top-p 1, top-k 0 and min-p 0.05. The
   top-k/min-p controls are now exposed in the shared contract, both HTTP APIs
   and native core bench, with CPU contract checks. Retain explicit seeds and
   qualify the new profile on original weights in AR and exact
   target-distribution MTP.
   Require filter/probability oracles, correct tool-mode transitions and measured
   cost; record the selected defaults rather than silently changing profiles.
   The [declared GPU protocol](development/protocols/DS4-SAMPLING-GPU-PROTOCOL.md)
   and optional supervisor pass 78 CPU fixtures. The integrated `1bff953`
   runtime now completes two seeded PP1500/TG128 sessions for greedy AR and
   the DS4 profile in AR/MTP, with exact per-profile token replay and actual MTP
   drafts/acceptance. [GPU receipt](development/validation/c17-sampling-point-gpu-2026-10-05.json).
   Independent original-weight probability/tool-transition coverage and matched
   cost remain pending.
   [Sampling defaults](https://github.com/antirez/ds4/blob/main/docs/SERVER.md) ·
   [MTP sampling semantics](https://github.com/antirez/ds4/blob/main/docs/SPECULATIVE_DECODING.md).
7. **Extract the identified remaining sampling responsibilities into C17.**
   Move provider-owned grammar/masking, sampler history and compact speculative
   distributions behind LIE contracts, one component at a time. Require bounded
   lifetimes, numerical oracles and GPU comparisons before replacing each
   component. Preserve the shared reactive core and limit this task to those
   three identified extractions.
   Sampler history/penalty bookkeeping is now wired through an owned C17
   contract under the default-ON sampler selection, retaining an OFF reference.
   Host FIFO/count oracles and pristine/ON/OFF full witnesses pass; original-weight
   AR/MTP/grammar continuation and cost remain unqualified. Ordered/compact
   distributions, residual correction and host MTP proposal/verification arithmetic
   now also use C17, with caller-owned storage and transactional RNG refusal.
   [Host comparison evidence](development/validation/c17-distribution-host-2026-10-05.json)
   covers complete rows, decisions and draw states; its GPU gates remain open.
   The byte grammar runtime and dense/compact mask application now use C17,
   with immutable programs, bounded snapshots and complete host state/mask
   [witnesses](development/validation/c17-grammar-runtime-host-2026-10-05.json).
   Exact-decimal numeric policy/prefix/LCM now also use C17, with complete
   [host witnesses](development/validation/c17-grammar-number-host-2026-10-05.json).
   JSON number representability now also uses the later C17 module below.
   String/UTF8/escape/surrogate
   predicates, whitespace and Unicode-DFA graph/query runtime now also use C17,
   with complete [host witnesses](development/validation/c17-grammar-unicode-host-2026-10-05.json).
   Vocabulary trie construction, token acceptance, iterative traversal, exact
   transition interning and canonical-state mask-cache policy now use C17
   ([host witnesses](development/validation/c17-grammar-vocabulary-host-2026-10-05.json)).
   Regex expression simplification, memoized iterative derivatives, Unicode
   partitioning and BFS DFA construction now also use the C17 core
   ([host witnesses](development/validation/c17-grammar-compiler-host-2026-10-05.json)).
   Syntax parsing and iterative assertion expansion now also use model-neutral
   C17 contracts with bounded AST/work budgets
   ([host witnesses](development/validation/c17-grammar-parser-host-2026-10-05.json)).
   Unicode-set registry, range translation and UTF8 input buffers now use a
   reusable C17 context through ICU C APIs
   ([host witnesses](development/validation/c17-grammar-uset-host-2026-10-05.json)).
   ICU remains the property/set/conversion dependency. Snapshot reader/writer
   planning, validation and payload copies now use C17
   ([host witnesses](development/validation/c17-grammar-snapshot-host-2026-10-05.json));
   provider vector storage remains private typed translation. Concrete rule/
   class/literal/repetition/JSON-primitive/generic-value/unsigned-interval
   construction, productivity/nullable analysis, iterative cycle checks and
   dead-alternative pruning now use the C17 builder
   ([host witnesses](development/validation/c17-grammar-builder-host-2026-10-05.json)).
   Structural JSON equality, local-reference resolution, supported-key validation
   and schema conjunction/distribution/merging now use shared C17
   ([host witnesses](development/validation/c17-schema-transform-host-2026-10-05.json)).
   Provider container views/staging and the binary64 codec remain private.
   Format and numeric leaf policies now use the later C17 modules below.
   Finite-value filtering/canonicalization,
   JSON quoting and object/array construction now use C17 with bounded shared
   counts and independent host refusal/language tests. The compiled-schema cache now also uses C17 ordering, synchronization and
   opaque ownership, with [host witnesses](development/validation/c17-grammar-cache-host-2026-10-05.json).
   Per-compilation reference identity lookup, placeholder publication and bounded
   storage now also use C17, with [host witnesses](development/validation/c17-schema-memo-host-2026-10-05.json).
   Its 32 pristine/ON/OFF checks and recursive states agree. Type/nullable/keyword
   compatibility, branch
   selection and ordered rule composition now also use C17, with
   [host witnesses](development/validation/c17-schema-dispatch-host-2026-10-05.json).
   Identity-first Visit sequencing, recursive placeholder publication and
   successful/empty body commitment now also use C17, with
   [host witnesses](development/validation/c17-schema-visit-host-2026-10-05.json).
   Ordered definitions, reference/anyOf distribution and enum/const body policy
   now also use C17, with [host witnesses](development/validation/c17-schema-body-host-2026-10-05.json).
   All 19 earlier complete witnesses remain unchanged. The matching memo/dispatch/
   Visit/body build now passes selected AR37/MTP37 GPU controls
   ([receipt](development/validation/c17-schema-body-point-gpu-2026-10-05.json)). Immutable grammar
   composition and the binary64 codec need extraction within the same task. Numeric
   schema preparation, scalar acceptance, LCM representability and literal
   publication now also use C17, with
   [host checks](development/validation/c17-schema-number-host-2026-10-06.json).
   Format selection, bounded pattern construction and schema expansion now also
   use C17 ([host checks](development/validation/c17-schema-format-host-2026-10-06.json)).
   Reasoning/tool composition cache ordering, duplicate-before-eviction policy
   and synchronization now also use C17
   ([host checks](development/validation/c17-composition-cache-host-2026-10-06.json)).
   Opaque key/value containers and immutable grammar composition remain private.
   The later matching `a24875f` 66-file build now passes selected original-weight
   AR37/MTP37 controls on `.161`
   ([GPU receipt](development/validation/c17-schema-policy-point-gpu-2026-10-06.json)).
   Individual numeric/format branches and independent probability/fault/private
   resource/matched cost gates remain open; this is no new SSD BPE qualification.
   [Release/cache host checks](development/validation/release-cache-host-2026-10-05.json)
   pass 79/79/35 with 20 unchanged complete witnesses. The device-free r17 provider
   builds but its application fails a strict optimized C warning; the collected
   build is retired. Corrected `6a48da3` builds and passes the selected GPU gates;
   individual branches, faults, allocation-exact resources and matched cost remain open.
   Earlier finite-value/cache slices have a matching
   provider/application rebuild and pass their own AR37/MTP37 GPU controls
   ([receipt](development/validation/c17-finite-cache-point-gpu-2026-10-05.json)).
   The integrated `1bff953` runtime now passes 37 original-weight OpenAI controls
   in both AR and MTP, including selected grammar/tool paths, and six seeded
   native TG128 sessions. This does not close individual grammar-branch,
   independent numerical, fault, allocation-exact resource or matched cost gates.

Current commands, ownership and evidence are maintained in
[progress](PROGRESS.md), [coordination](COORDINATION.md) and the
[model/platform benchmark index](benchmarks/models/qwen3.8-flash-next/README.md).

## Implemented capabilities and recorded qualification limits

The earlier MTP and vision branches were integrated from `7d85b2f` and
`806a790`. The shared contracts remain model-neutral; only the explicitly
recorded Qwen numerical binding is qualified.

These limits describe the evidence already collected. The numbered queue above
defines this thread's tasks; this table does not assign additional broad campaigns.

| Component | Implementation and recorded evidence | Recorded qualification limits |
| --- | --- | --- |
| MTP | Verified bursts, reactive cancellation, predictor/controller checkpoints, RAM/SSD continuation and recorded AR/MTP GPU comparisons. | Independent predictor oracle, broader rejection/fault/quality and long-context coverage. |
| Vision and joint MTP | Owned images, semantic cache/MRoPE, projector identity and joint RAM/SSD state; Halo image/cache and Point AR/MTP direct gates pass. | Broader image quality, mixed-history/fault cases and allocation-exact resource/performance qualification. |
| Semantic events/functions | Shared C17 text/progress/tool/turn events and incremental arguments; corrected r11 AR and MTP pass all 34 HTTP/function/control checks, including disconnected background completion. | Full agent task evaluation, newer output-budget qualification and performance. |
| C17 sampling | Owned dense selection, penalty/bias arithmetic and random draws; recorded GPU correctness and matched comparisons pass within their stated scope. | Retained cold-short regression; new owned history and compact/speculative probabilities have host checks only. Grammar runtime, vocabulary/cache and regex syntax/expression/DFA construction have host checks only. C17 Unicode registry/input handling has host checks only; ICU remains the property/set/conversion dependency. Snapshot marshalling algorithms have host checks only; provider container storage, JSON Schema compiler and model/controller state remain transitional. |
| Extended context | Explicit native/YaRN2/YaRN4 contracts; short GPU profile gates and 512K/1M capacity allocations pass. Physical PP1,048,448 completes with 43 output tokens. | The declared TG128 gate fails on natural EOS; extended quality and matched performance remain open. |

MTP and vision remain model-neutral capabilities. The C17 core owns policy,
scheduling, lifetimes, storage and metrics; the model binding owns predictor,
encoder, positions and numerical components. The combined Qwen binding is the
first implementation, not a core assumption. Native fixtures cover different
burst and image expansion geometries; they do not qualify another real model.
Keep benchmark gaps open until the deferred campaign.

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
not just the shared decode dispatcher. [Structured tool-output events](reference/EVENTS.md)
and RAM state/cache follow the same neutral core boundary.
[MTP](development/MTP.md) and [vision](development/VISION.md) now share that
core and complete extended state, including joint operation. Original-weight
qualification remains pending.

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
6. Dense sampler math and random draws are now extracted into
   [the shared C17 sampler](development/C17-SAMPLING.md), with host parity and
   original-weight qualification pending. Continue with sampler history/grammar,
   compact speculative distributions, tokenizer/binding, state layouts and layer graph in
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

## OpenAI controls — 2026-10-03

The shared C17 core now owns stop matching, target-probability normalization,
structured-output validation, choice admission, response records, history,
oldest-turn truncation and a retained semantic journal. HTTP projects these
contracts and remains a libuv reactor; background/replay adds no model worker.
The generation contract exposes sparse vocabulary bias, target reporting logits
and JSON/tool constraints without upstream types.

Schema compilation and vocabulary trie/mask caching remain delegated to the
pinned Gufo sampler. Byte-state expansion/transitions and applying resolved
dense/compact masks now use the owned C17 runtime; new GPU gates remain open. The independently fetched state variant also applies the
exact `adapters/gufo-state/sampling-edits.json` recipe for bias and reporting;
source inventory and `sampling_edits_sha256` are verified before linking.
Empty bias preserves upstream fast paths. Bias uses AR steps because compact
speculative distributions have not been ported to the new bias control.
This extends the working transitional slice; it does not complete the C++
executor replacement or qualify original-weight numerics/performance.
