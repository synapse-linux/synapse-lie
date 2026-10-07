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

## Current roadmap — 2026-10-07 UTC

The corrected `acfb9d26` runtime now passes the unchanged original-weight greedy
Chat JSON two-call question: both `alpha` and `beta` are emitted. The next fixed
follow-up fails: reversed results beta941/alpha137 produce alpha941/beta137.
Five new checks and five baseline controls pass; one new check fails and 65 are
unexecuted. The [current failed AR receipt](development/validation/tool-transitions-ar-point-r3-2026-10-07.json)
retains both observations, actual exits and verified machine closure. The
[earlier one-call failure](development/validation/tool-transitions-ar-point-r2-2026-10-07.json)
remains unchanged historical evidence. MTP is prepared but unadmitted.

Source diagnosis finds that the pinned Qwen renderer omits tool call IDs and
emits contiguous tool results in received order. Preserving their correlation
in the model prompt is now an identified functional correction; neither the
question nor acceptance criteria change. JSON format guidance already has
[grouped HOST checks](development/validation/tool-prompt-guidance-host-2026-10-07.json)
and a [coherent HIP build](development/validation/tool-prompt-guidance-point-build-2026-10-07.json).
Result correlation needs its own source correction and grouped HOST/HIP/original
weight checks. Wider tool acceptance, steering quality, long-context recall/HTTP,
fault/resource gates, matched comparisons and Terminal Bench remain open.
Terminal Bench stays last.

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
The owner confirms this order: finish functional implementation, qualify the
combined runtime, run the comparative benchmarks, then run Terminal Bench
(item 2) last. Do not alternate component changes with full test campaigns.
Complete and compile the remaining functional changes before running further
tests. Group the required focused local CTest and ASan/UBSan checks at the end
of that integration, then qualify the combined runtime on `.161`, run matched
benchmarks and run Terminal Bench last. Qualification-only client preparation
belongs to that final validation phase; do not turn it into another intermediate
implementation campaign.
GPU qualification uses `.161` with fresh admission. The owner's latest request
defers further GPU/test campaigns until all remaining functional implementation
is finished. The old prepared r37 MTP manifest remains unlaunched. Subsequent
final-phase r47 qualification uses a newly bound manifest and the current r45
runtime; its selected MTP-enabled HTTP controls pass as recorded below. Peer
non-use replies grant no future admission. No intermediate remote campaign,
Terminal Bench restart or machine reservation is queued.

The functional source audit now maps items 3–7 to integrated context/recall,
benchmark/dispatch, steering, generation-profile and three C17 sampler paths.
The build-coherence correction also covers typed observer identity and the
canonical full-provider Point build route. Source integration, compilation and
runtime acceptance are separate. Final
combined local checks and current coherent `.161` private producer/consumer HIP
compilation pass. At the integrated checkpoint, source hashes match all 650 files
in the final HOST receipt. Later capture/replay tooling adds development clients,
build targets and an owner-only stop-token metadata accessor. Executor ABI
layouts, HTTP/reactive scheduling and numerical algorithms remain unchanged;
the matching device-free r38 HIP build now links the new accessor/client along
with the four existing consumers. Its [receipt](development/validation/integrated-point-capture-hip-build-2026-10-07.json)
binds the exact source and all five artifacts; collection and strict machine
closure pass without a model or GPU test. Original-weight qualification remains open.
The final unavailable-backend stop metadata export is corrected at `229b1e13`,
with focused Release and sanitizer linkage checks. That source audit was followed
by the newly identified model-prompt result-correlation defect above. Its source
correction remains open; the acceptance checks below remain open for final integrated
qualification, with fresh admission for each remote window.
Comparative performance follows those gates; Terminal Bench stays last.
All six items remain open until their separate acceptance evidence is collected.

The live prefill controls at `d6431db8` now have grouped local Release/sanitizer
checks and matching coherent `.161` ROCm 10 compilation of both providers and
all six consumers. The [current prefill build receipt](development/validation/prefill-runtime-point-build-2026-10-07.json)
binds source, artifacts and verified machine release. This supersedes earlier
build identities for the new feature; original-weight chunk parity, memory,
cache, cancellation, fairness and performance still require final acceptance.

The subsequent C17 sparse-prefill admission correction uses the actually visible
mask extent while retaining its allocated stride and the existing workspace
limit. Focused local policy checks, exact source composition and local HIP 7.2
cross-compilation for `gfx1150` now pass. Both full providers and all five
consumers compile/link with exit0, with devices hidden and no model execution
([local compilation receipt](development/validation/prefill-visible-mask-local-hip-2026-10-07.json)).
The [coherent `.161` ROCm10 build](development/validation/integrated-point-attention-hip-build-2026-10-07.json)
includes this guard and the long-workspace recipe at source `120e2fce`.
The prepared r40 GPU capture was
rejected by automatic approval review before launch, citing an optimization/
qualification priority conflict. r40/r41 remain unadmitted and stale after this
source change. The owner's latest visible instruction confirms implementation
before further tests and supersedes the pending sequencing question. No
intermediate campaign is queued. Final original-weight gates remain required;
the r39 numerical receipt qualifies its recorded binary only.

The owned recipe subsequently adds a separately instantiated 8,192-word sparse
WMMA workspace through 1M visible tokens. Default-ON `LIE_LONG_CONTEXT_WMMA`
keeps the short kernel unchanged and supports an explicit OFF control. The
receipt and Point build routes enforce the selected option in providers and
clients. This completes the long-workspace source path; GPU numerical, quality,
resource and performance acceptance remains in the final integrated phase.
It changes neither reactive scheduling nor thread counts.
The [local compilation receipt](development/validation/prefill-long-wmma-local-hip-2026-10-07.json)
binds source `c9c79a70`, three complete providers and nine linked consumers;
this is local HIP 7.2 evidence, not `.161` ROCm10 or inference qualification.

The [generated attention GPU component](development/validation/attention-fixture-point-2026-10-07.json)
subsequently passes 13 complete cases through 1M on `.161`, with 270,336 values
matching the recorded fallback bit for bit. This qualifies generated attention
after selection at its recorded runtime; original weights, indexer, resource
fit, quality and comparative performance remain open.

The shared core now separates a live selected prefill chunk from immutable
provider scratch capacity, both bounded at 32,768. New requests capture the
selection; queued/active requests retain theirs. RAM/SSD semantic identities
isolate chunk choices. HTTP exposes the core setter on its management listener;
native direct/core benchmarks record the reservation and actual chunk. Defaults
remain 2,048 with unchanged existing public layouts and scheduler thread counts.
These later provider changes require a fresh coherent build and original-weight
qualification; the preceding r43/r44 receipts do not qualify larger chunks.
The matching r45 build now passes selected original-weight PP8192/TG32 parity
at chunks 2048/4096/8192 and fixed capacity 8192/context 16384/C1. All 32 output IDs
are identical, completed prefill calls are 4/2/1 and native dispatch accounting
has no geometry/mask-pitch refusal
([functional receipt](development/validation/prefill-original-point-2026-10-07.json)).
The subsequent PP32768/TG32 comparison passes exact greedy parity at chunks
2048/16384/32768 with fixed capacity 32,768/context 65,536/C1, completed calls 16/2/1
and no geometry/mask-pitch refusal
([32K functional receipt](development/validation/prefill-original-32k-point-2026-10-07.json)).
These selected configurations do not qualify live changes, cache/cancel/fairness,
broader quality/fault/resource behavior or matched performance; those gates remain open.

The native C17 benchmark now provides explicit `--prefill-probe live|ram|ssd`
qualification clients for those remaining gates. Full physical input/output,
in-flight owner counters, immutable queued choices, credit/cancellation recovery
and five cache-namespace stages are saved. Performance report readers refuse
these functional identities. Focused native Release and unsuppressed sanitizer
checks pass 5/5 each; six AR/MTP synthetic probes, fourteen CLI refusals and a
deliberate failed prefill are retained. All 82 optional mocked supervisor checks
pass. The [HOST receipt](development/validation/prefill-probe-host-r2-2026-10-07.json)
preserves corrected preparation/test failures. No engine ABI, scheduler, provider
or numerical algorithm changes; a newly bound `.161` client build and actual
original-weight live/cache runs are still required. All six items remain open.

The matching r50 device-hidden `.161` build of `cb75a48f` now compiles both
providers and all six consumers with exit 0. Source/recipe/linkage reconstruction,
collection and strict machine closure pass in the
[client build receipt](development/validation/prefill-probe-point-build-2026-10-07.json).
A later host-only supervisor control isolates full input checkpoints for cache
probes and passes 83 mocked checks; normal engine/cache defaults are unchanged.
The compiled native client and that supervisor are bound separately. This is
compilation and client-contract evidence; original-weight live/cache/cancel/
fairness and broader acceptance still need fresh admission. All six items stay open.

The r50 runtime subsequently passes original Q4 AR PP32768/TG32/C2 live
selection with fixed context 65,536/capacity 32,768. Active/queued choices remain
2,048/revision 1 and 32,768/revision 2 while the core returns to 2,048/revision 3.
Complete peer output matches the cold baseline and fresh post-cancellation
output. Withheld-credit peer progress, borrowed-output stability and actual
zero-output cancellation during prefill pass. The
[live functional receipt](development/validation/prefill-live-original-point-2026-10-07.json)
binds actual exits, sampled resources, independent review and strict closure.
RAM/SSD/MTP, broader quality/fault/resource and matched performance gates remain
open; this selected functional pass does not establish a throughput gain.

Separate original AR RAM/SSD probes now pass five chunk-namespace trials each
at PP8192/TG32/C1/context 16,384/capacity 8,192. All ten full outputs match;
prefill calls are 4/0/1/0/0 and hot restores cover all 8,192 tokens. SSD has
RAM disabled, two drained writes, actual full reads and zero errors. The
[cache functional receipt](development/validation/prefill-cache-original-point-2026-10-07.json)
binds all exits, original model witnesses and strict closures. Exact DS4 raw
payloads are retained; an enabled generic compression capability does not
establish packing. MTP, broader quality/fault/resources and matched performance
remain open; all six roadmap items stay open.

Original Q4/Q8 MTP now passes the same 8K five-stage RAM/SSD probes, plus a C2
live probe with an actual in-flight setter, immutable admitted selections,
withheld-credit peer progress, borrowed-output stability and prefill cancellation
with recovery. All complete outputs match the same-runtime serial AR reference.
SSD restores full prefixes with RAM disabled and drains two writes without errors.
The [MTP functional receipt](development/validation/prefill-mtp-original-point-2026-10-07.json)
binds all 33 collected files, independent reviews and three strict closures.
This qualifies selected greedy live/cache behavior at PP8192/TG32, not broader
MTP probability/filter/grammar, quality/fault/resources or matched performance.
All six roadmap items remain open; no remote window is reserved.

The next MTP numerical gate now has an additive C17 owner-only observation
contract. Private glue captures completed target/proposal/verification draws,
RNG, history, penalties and grammar masks without changing sampling policy,
core scheduling or worker counts. Focused ON/OFF Release and unsuppressed
sanitizer HOST checks pass. Native AR wire formats stay unchanged; the explicit
MTP writer/replay now passes grouped HOST controls across original/C17/OFF,
including independent probability/RNG/grammar/controller oracles and negative
fixtures ([HOST receipt](development/validation/mtp-capture-host-2026-10-07.json)).
The matching device-hidden ROCm 10 build of `c6625f09` now compiles both
coherent ON/OFF providers and all six consumers. Collection, independent source
reconstruction and strict machine closure pass in the
[build receipt](development/validation/mtp-capture-point-build-2026-10-07.json).
The [selected original-weight text qualification](development/validation/sampling-mtp-text-point-2026-10-07.json)
now captures six 16-token Q4/Q8 profiles and replays all 192 observations across
original/C17/OFF Release and sanitizer programs. Actual proposal, acceptance,
residual/deferred RNG and committed frontiers match independent oracles.
The [required-tool MTP qualification](development/validation/sampling-mtp-tools-point-2026-10-07.json)
also passes all six complete natural-EOS calls, 226 observations and 169 full
target masks across Release and sanitizer programs. Compact proposals retain
the original unconstrained policy; every target/verification mask bit and
acceptance/residual/deferred frontier matches. Greedy covers the host head only.
Wider tool transitions, quality/fault/resources and matched cost remain open;
these diagnostic captures establish no speedup.

An open qualification gate does not mean its implementation is absent:

| Item | Source already integrated in this branch | Final qualification still open |
| --- | --- | --- |
| 3 | 1M context admission, explicit YaRN, client deadlines and native recall/continuation corpus with exact response oracles | Original-weight recall and HTTP at long context |
| 4 | Native benchmark methods, metrics, graph generation, C17 prefill-dispatch observation and optional long sparse-WMMA workspace | Matched Gufo/Halogen runs through 1M and C1/2/4/6/8; long-workspace correctness/resources, actual sparse dispatch and reactive cost |
| 5 | Steering bank, model/session policies, scheduled changes and RAM/SSD identities | Learned-direction quality, graph/correction/fault/vision cases and matched cost |
| 6 | Temperature, top-k/min-p profiles and seeded AR/MTP controls | Wider tool transitions, broader quality/fault/resources and matched cost; selected AR/MTP text and required-function numerical witnesses pass at their recorded runtimes |
| 7 | C17 grammar/masking, history and compact speculative distributions, including buffer ownership | Original-weight numerical/fault/resource/quality and cost gates |

The integrated checkpoint `88d4c4e5` passes native functional 101/101 and complete
provider 67/67 in both Release and unsuppressed sanitizer builds, plus ICU-OFF
core 69/69 and all 68 strict C17/C++17 public headers. All 30 complete witness
groups agree across builds; all 267 preceding captures remain unchanged. The
[current combined HOST receipt](development/validation/integrated-final-host-2026-10-06.json)
preserves four failed link attempts and binds their corrected dependencies.
It qualifies local synthetic and algorithm paths only. The earlier
[`77bcdc1c` HOST receipt](development/validation/c17-final-functional-host-2026-10-06.json)
and closed r36 HIP build remain historical evidence; that build predates the
observer's private ABI and cannot qualify this checkpoint. The matching
[r37 HIP build](development/validation/integrated-point-hip-build-2026-10-06.json)
now completes both full private providers and consumers with exit0; their exact
variant maps and flags verify, and the run is collected/closed with the router
restored. This is compilation evidence. Original-weight functional, fault and
quality gates need fresh `.161` admission. Comparative performance follows them;
Terminal Bench remains
last. No further intermediate campaign is queued, and compilation alone closes
none of the six items.

1. **Completed: selected original-weight OpenAI GPU controls.**
   The earlier paired runtime `dbdac28d` passes **37 general OpenAI checks
   and 66 additional bounded-integer checks in each AR/MTP mode** on `.161`.
   Tools, JSON/SSE, output budgets and retained Responses lifecycle pass;
   integer checks cover 60 exact outputs and six expected HTTP400 refusals per
   mode. Matching HIP ON/OFF builds, collected wire evidence, actual exits0
   and exact process/service/lease closure are verified.
   [Current qualification](development/validation/c17-json-slot-point-gpu-2026-10-06.json).
   The coherent current runtime `d63b9b7b` / code `88d4c4e5` additionally passes
   AR37+66, with collected wire, independent exact-rational integer checks and
   strict process/service/lease closure
   ([AR receipt](development/validation/integrated-point-ar-2026-10-06.json)).
   The current prefill r45 runtime / code `d6431db8` now passes **37 OpenAI and
   66 bounded-integer controls on an MTP-enabled server**, with original Q4
   weights and Q8 predictor, unchanged model stats and exact process/service/
   lease closure ([MTP receipt](development/validation/integrated-point-mtp-2026-10-07.json)).
   Actual drafted/accepted counters are present. Existing stop/logprobs/bias
   requests fall back to AR, so the pass does not imply every check executes MTP.
   Independent saved-wire review verifies 60 outputs, six HTTP400 refusals and
   30 JSON/SSE pairs. The older AR37+66 receipt uses a different runtime; it is
   not a matched AR/MTP comparison with r45.
   Broader task quality, probabilities, fault coverage and performance remain
   separate acceptance gates in the six open items below.
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
3. **1M source integrated; qualify recall and long-context HTTP.** The declared `1bff953` `.161`
   run completes all **1,048,448 physical prefill tokens and 128 output tokens**
   with explicit YaRN4 and `--ignore-eos`. The
   [capacity/function receipt](development/validation/physical1m-fixed-point-gpu-2026-10-05.json)
   verifies actual retirement, collection, model identities and service/lease
   closure. The older natural-EOS43 failure remains unchanged. Long-context
   recall checks still need completion; this single run is not a matched
   performance comparison. Native live progress also reaches its confirmed
   final snapshot, separately from process and lease retirement.
   The native HTTP client deadline now covers the recorded duration: configurable
   maximum 24 hours, long-context default four hours. Matching Release and
   sanitizer fixtures pass; independent recall and HTTP GPU campaigns remain open.
   The native `long-context-recall` client now prepares three seeded bindings
   at start/middle/end, exact per-turn response oracles and a continuation that
   asks for previously unanswered keys. Actual counts, copied corpus and quality
   misses are retained separately from infrastructure failures. Client source
   and local fixtures do not qualify original-weight long-context recall.
4. **Benchmark methods integrated; run matched Gufo/Halogen comparisons.** Compare full cold
   prefill and decode through 1M, and multi-user C1/2/4/6/8, with matched physical
   work, cache policy, output length, repetitions and server lifecycle. Retain
   PP, TG, TTFT, resources and correctly scaled graphs. Profile the prefill
   decline above 256K and separate batching from reactive responsiveness.
   [Pinned-source dispatch analysis](development/validation/long-context-sparse-dispatch-source-2026-10-06.json)
   identifies the preceding provider's 2,048-word sparse-WMMA limit: configured capacity above
   262,144 tokens can select the per-token fallback even at shallower
   visible depth. The C17 observer and native core report now capture actual
   matrix/scalar, dense/sparse selections, with confirmed/unconfirmed work and
   explicit unsupported views. Focused host checks and exact source recipes
   pass; coherent current HIP compilation also passes. The current policy
   separates visible frontier from allocation pitch and adds a default-ON
   8,192-word specialization through 1M. Its 13 generated `.161` GPU cases
   pass complete bitwise output comparison and independent offline review
   ([component receipt](development/validation/attention-fixture-point-2026-10-07.json)).
   Original-weight GPU dispatch and matched observer cost remain open.
   Capture actual dispatch before attributing
   timings to
   reactive scheduling; this finding is not measured causality or a
   constant-prefill guarantee.
5. **Steering integrated; qualify learned directions and runtime behavior.** Load its per-layer `.f32`
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
   choice lifetimes. Selected original-weight scheduled SSD restart cases now
   pass in AR/MTP on the unchanged `20777005` runtime
   ([receipt](development/validation/steering-physical-index-point-gpu-2026-10-06.json)).
   Three FFN/attention changes apply at exact prefill/generation indices;
   cold/SSD physical inputs, 32 output IDs and final policies match within and
   across modes. Divergent saved spelling is refused and the compatible prefix
   restores exactly 128 tokens. MTP accepts 3 of 14 proposals in each case.
   Eighteen host gate and 60 campaign checks pass. The sparse nonzero fixture
   qualifies this regression; learned-direction quality, independent graph/
   correction/fault, vision and matched cost remain open.
   Separate `modern-core-steering-admission` windows now qualify original-model
   malformed-bank refusals and absent/zero/fresh-core recovery equality in AR/MTP
   ([receipt](development/validation/steering-admission-point-gpu-2026-10-06.json)).
   All 272 input/32 output IDs match. Each mode retains three native successes
   with exit 0 and twelve expected loader refusals with exit 1. MTP drafts six
   and accepts zero; this is no accepted-burst qualification. The original QA
   rejection is preserved. Sixteen host/61 campaign checks pass; broader quality,
   independent graph/correction/GPU faults, vision and cost remain open.
   DS4's `--dir-steering-file`, `--dir-steering-ffn` and
   `--dir-steering-attn` now select fixed initial model-wide scales through the
   same core used by server and bench.
   Cover both prompt evaluation and generation, session scale changes,
   cache compatibility and AR/MTP interaction. Require unchanged baseline output
   with steering off, malformed-vector refusal and measured quality/performance
   with steering on. DS4 documents Qwen's 48-by-2560 bank and its HC branches;
   that implementation is Metal-only, so it is not evidence for LIE HIP.
   [Upstream steering contract](https://github.com/antirez/ds4/blob/main/dir-steering/README.md).
6. **Generation profiles integrated; qualify independent sampling behavior.**
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
   The native [complete-row capture and offline replay](development/protocols/DS4-SAMPLING-GPU-PROTOCOL.md#complete-row-capture-and-offline-probability-replay)
   now prepare full probability/RNG/history witnesses and independent mathematical
   filter/residual checks for the final phase. The required-function capture
   also binds the complete vocabulary, masks, natural-stop frontier and validated
   call arguments. Three private samplers and independent byte membership/
   long-double mass oracles agree in local fixtures
   ([tooling receipt](development/validation/sampling-tools-host-2026-10-07.json)).
   The final r39 original-weight AR capture now passes 96 rows across the six
   frozen profiles in original/C17/OFF Release and sanitizer replay. Full
   probability/history/RNG witnesses match, with independent mass and forced
   residual checks. [AR numerical receipt](development/validation/sampling-original-ar-point-2026-10-07.json).
   This preceding receipt covers unconstrained AR only. The new current r45
   runtime also passes 152 required-function rows across all six profiles in
   original/C17/OFF Release and unsuppressed sanitizer replay, including full
   vocabulary masks, mass, history, RNG, residual checks and complete calls.
   All six calls choose the requested arguments and finish with natural EOS.
   [Required-function AR receipt](development/validation/sampling-required-tools-ar-point-2026-10-07.json)
   binds the new GPU runtime and unchanged qualified host-sampler sources.
   Both runs are collected and strictly closed. Actual MTP-controller branches,
   prose/parallel calls/results, broader quality, faults, resources and matched
   cost remain open. The new capture uses the default 2,048-token prefill chunk;
   larger live chunks retain their separate gates.
   The optional Point supervisor now executes the native capture under the same
   owned window and collects bounded raw rows, including failed partial evidence.
   Fifteen focused transport/receipt and seven ownership/build regression controls
   pass locally. [Preparation receipt](development/validation/sampling-capture-supervisor-host-2026-10-07.json).
   Native/runtime numerical sources and the matching HIP build remain unchanged;
   structural receipt validation does not qualify the independent probabilities.
   The [wider function transition client](development/protocols/TOOL-TRANSITIONS-GPU-PROTOCOL.md)
   now prepares 71 frozen HTTP checks across greedy/DS4/filtered profiles,
   including prose, parallel calls, distinct reversed results and eight
   pre-forward refusals. Grouped HOST mock controls pass; original-weight
   AR/MTP observations and matched cost remain open. It changes no native ABI,
   numerical algorithm, reactive scheduling or product dependency.
   [Sampling defaults](https://github.com/antirez/ds4/blob/main/docs/SERVER.md) ·
   [MTP sampling semantics](https://github.com/antirez/ds4/blob/main/docs/SPECULATIVE_DECODING.md).
7. **C17 sampler extractions integrated; qualify the combined runtime.**
   Move provider-owned grammar/masking, sampler history and compact speculative
   distributions behind LIE contracts, one component at a time. Require bounded
   lifetimes, numerical oracles and GPU comparisons before replacing each
   component. Preserve the shared reactive core and limit this task to those
   three identified extractions.
   The later default-ON source also moves token/penalty/probability buffer ownership,
   growth, accounting, logical clones and exact move transfer into C17. Private
   sampler/distribution layouts change; matching complete provider and consumer
   builds are required. Production rows transfer without a C++ probability-vector
   copy; original OFF layouts remain guarded. This increment has 20 edits and
   a 120-file inventory. Combined Release/sanitizer HOST controls now pass the
   ownership/refusal/MTP fixtures and complete original/ON/OFF witnesses.
   The complete current private HIP producer/consumer build passes; original-weight
   and resource/cost gates remain open. See
   [native sampler storage](development/C17-SAMPLING.md#native-sampler-buffer-ownership).
   Full model/controller/kernel replacement remains an architectural destination,
   outside these three identified extractions and the current root queue.
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
   Provider container views/staging remain private; binary64 conversion now
   uses the later shared C17 codec below.
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
   ([receipt](development/validation/c17-schema-body-point-gpu-2026-10-05.json)). Numeric
   schema preparation, scalar acceptance, LCM representability and literal
   publication now also use C17, with
   [host checks](development/validation/c17-schema-number-host-2026-10-06.json).
   Format selection, bounded pattern construction and schema expansion now also
   use C17 ([host checks](development/validation/c17-schema-format-host-2026-10-06.json)).
   Reasoning/tool composition cache ordering, duplicate-before-eviction policy
   and synchronization now also use C17
   ([host checks](development/validation/c17-composition-cache-host-2026-10-06.json)).
   Immutable reasoning/tool grammar composition now also uses C17
   ([host checks](development/validation/c17-composition-host-2026-10-06.json)), with
   complete states/masks and allocation/refusal oracles. JSON binary64 number
   formatting/parsing now also uses C17 with bundled pinned Ryu and independent
   bit/rounding/refusal oracles
   ([host checks](development/validation/c17-binary64-host-2026-10-06.json)). The
   matching `20777005` 83-file inventory (71 first-party + 12 vendor/provenance
   files) now passes selected original-weight AR37/MTP37 controls on `.161`
   ([GPU receipt](development/validation/c17-binary64-point-gpu-2026-10-06.json)).
   Complete JSON syntax, UTF-8/escape decoding and decoded duplicate-key detection
   now also use C17, with [host checks](development/validation/c17-json-parser-host-2026-10-06.json).
   Its matching sealed `904774da` 86-file inventory passes selected original-weight
   AR37/MTP37 controls on `.161`
   ([GPU receipt](development/validation/c17-json-parser-point-gpu-2026-10-06.json)).
   Typed JSON values, exact string/key bytes and ordered object/array storage
   now also use the shared C17 core, including cloning, transactional assignment,
   parsing and serialization
   ([host receipt](development/validation/c17-json-value-host-2026-10-06.json)).
   Private C++ facades preserve the existing callers and synchronize lazy string
   projections for immutable parallel reads. The matching sealed `5227bf4f`
   89-file provider/application build passes selected original-weight AR37/MTP37
   controls on `.161`
   ([GPU receipt](development/validation/c17-json-value-point-gpu-2026-10-06.json)).
   Immutable primitive storage, ordered predicate tables, construction-only
   identity memo and hot dispatch now also use C17
   ([host receipt](development/validation/c17-lexeme-host-2026-10-06.json)).
   Six guarded edits preserve original OFF classes/vector/map; the inventory
   now binds 92 files (80 first-party and 12 vendor/provenance). The matching
   sealed `688b74c5` HIP build passes selected original-weight AR37/MTP37
   controls on `.161`
   ([GPU receipt](development/validation/c17-lexeme-point-gpu-2026-10-06.json)).
   Request grammar snapshots now also remain C-owned across transitions/masks
   and independent speculative copies, with saved-allocator duplication and
   [host checks](development/validation/c17-request-state-host-2026-10-06.json).
   Three guarded edits preserve original OFF state/algorithms. The newer
   93-file inventory has a matching sealed `117cbae6` HIP build and selected
   original-weight AR37/MTP37 controls
   ([GPU receipt](development/validation/c17-request-state-point-gpu-2026-10-06.json)).
   Finished immutable grammar tables no longer have duplicate default-ON C++
   rule/class payloads. Six guarded edits preserve OFF behavior; the new recipe
   is provider-identity gated. [HOST checks](development/validation/c17-grammar-storage-host-2026-10-06.json)
   pass 52 sanitizer and three Release controls, retaining all 29 complete
   witnesses. Matching sealed `ad53e681` HIP ON/OFF providers and private
   consumers pass unchanged AR37/MTP37 original-weight controls on `.161`
   ([GPU receipt](development/validation/c17-grammar-storage-point-gpu-2026-10-06.json)).
   Broader grammar branches/faults/quality/resources and matched cost stay open.
   Private construction/value/error/prompt facades and model/controller remain transitional.
   Per-compilation derived values and transformation/normalization staging now
   retain stable native roots in the shared C17 collection. The
   [HOST receipt](development/validation/c17-schema-store-host-2026-10-06.json)
   records 54 sanitizer checks, three corrected provenance gates and all 29
   complete preceding witnesses unchanged. Original OFF compiler storage remains
   guarded. Matching sealed `72e9e831` coherent 99-file HIP ON/OFF providers
   and private consumers pass unchanged AR37/MTP37 original-weight controls
   ([GPU receipt](development/validation/c17-schema-store-point-gpu-2026-10-06.json)).
   The newer shared C17 compilation/publication workflow and independent native
   prompt ownership pass 56/56 sanitizer HOST checks, one focused C check and
   three provider gates. All 29 preceding complete witness groups remain
   unchanged. [Current HOST scope](development/C17-SAMPLING.md#schema-compilation-and-prompt-publication)
   now has matching sealed `33d12a02` HIP ON/OFF providers and private
   LIE/model/reference consumers passing AR37/MTP37
   ([GPU receipt](development/validation/c17-schema-compile-point-gpu-2026-10-06.json)).
   The official Gufo HTTP frontend is not built in this gate. Signed integer-bound
   interval construction now uses C17, including exact represented magnitudes
   beyond int64 and exclusive endpoints. The new
   [HOST receipt](development/validation/c17-schema-integer-host-2026-10-06.json)
   records 58 sanitizer checks, one focused C check, four Release checks and
   all 29 preceding complete witness groups unchanged. The matching sealed
   `9a4f45b1` 105-file HIP ON/OFF/private-consumer build now passes unchanged
   selected AR37/MTP37 on `.161`
   ([GPU receipt](development/validation/c17-schema-integer-point-gpu-2026-10-06.json)).
   A new independent 66-check bounded-integer protocol passes its first 26 AR
   checks, including binary64-maximum JSON/SSE output, then fails HTTP502 at
   an exclusive lower endpoint near `1e18`. The final shared C validator's
   rounded-double comparison now has a reproducing HOST regression and a C17
   correction: 9,855 exact numeric checks, four Release and seven sanitizer
   tests pass. The corrected `050ae826` runtime now has matching HIP ON/OFF
   builds and passes all 66 integer checks plus the unchanged 37 general
   controls in each AR/MTP mode on `.161`
   ([current GPU receipt](development/validation/output-schema-integer-point-gpu-2026-10-06.json)).
   The earlier failed AR window is preserved; MTP was not started for that failed
   runtime. The corrected build and both successful windows are collected and
   closed. General fractional-number constraints, numeric enum/const and
   `multipleOf` precision remain separate open qualifications.
   JSON root/borrowed ownership, lazy construction, scalar moved state,
   copy/move assignment and root transfer now also use C17. The
   [HOST receipt](development/validation/c17-json-slot-host-2026-10-06.json)
   records five Release, five sanitizer, 58 provider and three contract checks;
   all 30 complete preceding groups/267 files are unchanged. Private facade
   sizes remain unchanged. The matching `dbdac28d` coherent HIP ON/OFF build
   now passes 37 general and 66 integer controls in each AR/MTP mode on `.161`
   ([GPU receipt](development/validation/c17-json-slot-point-gpu-2026-10-06.json)).
   Selected continuation is qualified; broader branches, faults and cost remain open.
   Standard schema-number conversion now calls the C17 binary64 codec directly;
   each conversion hook is an independent optional override. The
   [HOST receipt](development/validation/c17-schema-codec-host-2026-10-06.json)
   records Release5/sanitizer5/provider58/contracts3 and all 30 preceding groups/
   267 files unchanged. Matching new-source HIP/AR/MTP qualification is pending
   in the final phase. The later shared final validator now uses exact output
   spans for fractional bounds, numeric enum/const and `multipleOf`, through
   reusable C17 comparison/divisibility APIs. This later increment passes the
   combined Release/sanitizer HOST fixtures and complete provider witnesses.
   Grammar/final-validator agreement, original-weight AR/MTP, fault and cost
   acceptance remain open alongside the other final gates.
   A later `lie_schema_compiler` context now owns temporary
   builder/memo/derived-root/predicate-memo lifetimes, primitive IDs, counters,
   initialization and one-shot publication. The private adapter projects typed
   callbacks/errors and borrowed state. Matching source inventories include
   three new files; its native/typed HOST fixtures now pass.
   A further native `lie_schema_arena` now creates/copies/mutates
   staging JSON trees, supplies direct C readers and transfers roots through
   C17 ownership. Default-ON transformations/normalization use this path, with
   private typed/error projections and guarded original OFF construction.
   Native/typed fixtures are written; 111-file source inventories are wired.
   Native C17 string-leaf admission/construction now also replaces default-ON
   typed length/pattern/format policy. Lazy unrestricted-program reuse and
   original error ordering remain explicit. Its written native/typed fixtures
   and later 114-file inventory pass combined HOST qualification; GPU remains pending.
   The complete native C17 frontend now also binds all schema bodies/visitors/
   containers/enum leaves, owns predicate registration and diagnostic retirement,
   and publishes independent program/prompt/table results. Production default-ON
   `Compile`/`Object` paths use native trees instead of typed factories/callbacks;
   private error/shared-handle projection, original OFF and retained helper probes
   remain. This further increment's fixtures pass combined Release/sanitizer HOST
   qualification in the integrated 120-file inventory; matching GPU remains pending.
   Remaining private typed grammar/error/shared-handle projections and model/controller
   ownership remain transitional. These increments do not close any of the six items.
   Remaining compiler bindings/typed facades/model ownership and broader branch,
   fault, quality, private-resource and matched-cost gates remain open.
   Root-reference cycle/admission policy and root whitespace/body composition
   now also use C17, with [host checks](development/validation/c17-schema-root-host-2026-10-06.json).
   The matching sealed `3c4cac56` 96-file HIP build verifies complete ON/OFF
   providers and passes the unchanged 37 original-weight OpenAI controls in each
   AR/MTP mode on `.161`
   ([GPU receipt](development/validation/c17-schema-root-point-gpu-2026-10-06.json)).
   Individual root GPU branches, faults and matched cost remain open. Private construction facades,
   schema/regex wrappers, template projections and model/controller remain
   transitional. Broader numerical/fault/resource/quality/matched-cost
   gates remain open.
   The Gufo benchmark control requires a separately verified complete OFF
   provider, including numerical/controller archives, to keep private request
   layouts coherent. The sealed `117cbae6` ON/OFF HIP builds and two short C1
   controls pass with exact physical-input/output/frontier witnesses; these
   warmup0/rep1 correctness controls do not establish a performance gain.
   The earlier matching `a24875f` 66-file build passes selected original-weight
   AR37/MTP37 controls on `.161`
   ([GPU receipt](development/validation/c17-schema-policy-point-gpu-2026-10-06.json)).
   Individual numeric/format branches and independent probability/fault/private
   resource/matched cost gates remain open.
   The dedicated SSD text restart gate now qualifies selected original-weight
   AR/MTP cases on the unchanged `20777005` runtime
   ([receipt](development/validation/ssd-text-restart-point-gpu-2026-10-06.json)).
   New processes restore 2,048/2,064 exact physical tokens from text, with zero
   prefill and matching 32-token outputs; MTP accepts 21 drafts in each process.
   Twelve parser and 59 campaign host tests pass. The raw MTP wrapper exit 1
   remains retained: corrected offline validation requires the full persisted
   prompt instead of the early checkpoint. Selected original-weight scheduled
   physical-index/cache cases now also pass
   ([receipt](development/validation/steering-physical-index-point-gpu-2026-10-06.json));
   broader steering quality/fault/cost remains open. The earlier ten-test
   [host receipt](development/validation/ssd-text-restart-host-2026-10-06.json)
   retains its original host-only scope.
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
| Semantic events/functions | Shared C17 text/progress/tool/turn events and incremental arguments. The current `33d12a02` build passes 37 selected original-weight controls in each AR/MTP mode, including automatic output budgets and retained Responses lifecycle. | Full agent task evaluation, broader API cases and performance. |
| C17 sampling and grammar | Owned selection, history, speculative probabilities, grammar storage/runtime, Unicode input, JSON values, schema publication and prompt ownership. Latest integrated native frontend, exact decimal validator and sampler buffers pass combined Release/sanitizer HOST qualification. Earlier selected AR/MTP GPU controls retain their recorded source scope. | Matching latest-source HIP/AR/MTP, individual branches, faults, quality, private resources and matched cost. Private typed grammar/error/shared-handle projections and model/controller remain transitional. ICU remains the property/set/conversion dependency. |
| Extended context | Explicit native/YaRN2/YaRN4 contracts. The frozen `1bff953` C1 YaRN4 run completes physical PP1,048,448 and fixed TG128 at capacity 1,048,576. | Independent long-context recall and matched performance remain open. The older natural-EOS43 failure is retained separately. |

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
