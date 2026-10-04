<!-- SPDX-License-Identifier: MIT -->
# Gufo provenance

`patches/gufo-q2.patch` modifies independently downloaded official Gufo
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`; its archive receipt is
`config/gufo-source.json`. Gufo's original MIT license, notice and full third-party
notice are retained here. The quantized HIP kernels retain their upstream
llama.cpp notices and formatting. Antirez material was consulted for the file
format; no antirez Qwen engine source is incorporated. No sibling project's
source, binary or cache was imported.

The patch keeps quantized expert weights, separates logical and physical down
widths, and exactly widens the small F16 HC injection matrices at load. The
standalone qualification harness is first-party MIT. Its IQ2 oracle uses the
official format codebook generated from the pinned source at build time, with
independently evaluated unpacking and dot-product arithmetic.

`experiments/q2-hc-four-wave.patch` is first-party MIT numerical work against
the same independently fetched official pin. It changes F16 HC down work
distribution without importing another engine or changing weight precision.
Its qualification harness inherits upstream numerical flags; bounded model
checks may reuse this workstream's unchanged, identity-verified MMQ archive.
The original upstream and llama.cpp notices remain applicable to that archive.

`experiments/q2-hc-prefill-wmma.patch` specializes the same official Gufo raw-F16
WMMA template for the two original Q2 HC prefill projections. It is a separate
experimental delta after the HC4 decode patch, with first-party MIT synthetic
checks and unchanged upstream arithmetic/weight formats. The source receipt
records both modified translation units and all 1019-file inventory coverage.
No antirez engine or sibling workspace source/artifact is incorporated.

`experiments/q2-compensated-down-source.patch` is the source-level delta of this
workstream's retained compensated Q2 down experiment, composed after the HC
patches. `experiments/q2-iq2-pair.patch` extends the same official routed WMMA
template to IQ2_XXS paired gate/up. It uses the codebook and parity sign tables
already present in official `mmq/ggml-common.h`; all upstream/llama.cpp notices
remain applicable. The independent synthetic fixtures and orchestration are
first-party MIT. Source reconstruction verifies every file against the actual
measured trees; hashes are in `config/q2-expert-stack-source.json`. Neither
experimental patch replaces the qualified runtime patch or imports an antirez
engine, sibling source or sibling compiled artifact.

`experiments/q2-packed-activations.patch` moves this workstream's existing
compensated activation representation into its IQ2 producer, using the same
independently fetched official Gufo templates and buffers. It introduces no
external code or new weight format. Existing upstream and llama.cpp notices
remain applicable; prepared synthetic replay fixtures are first-party MIT.
GPU operator, exact full-model replay and fresh Q2/UD performance evidence
are explicit in `docs/Q2-PACKED-ACTIVATIONS.md`. This does not promote the
experimental patch into the qualified runtime or replace its provenance.

`experiments/q2-hc-up-fused.patch` adapts the same official Gufo HC WMMA mixer
to original F16 weights and F32 normalized streams. The numerical work and
independent synthetic fixtures are first-party MIT; existing upstream notices
remain intact. The prepared source reconstructs exactly from this workstream's
packed checkpoint. No antirez engine, DS4 source or KV codec is imported.
Runtime qualification is recorded in `docs/Q2-HC-UP-FUSION.md`.

That isolated fusion has since passed GPU operator and full-model replay on
`.157`; its collected timing and identity evidence are linked from
`docs/Q2-HC-UP-FUSION.md`. `experiments/q2-hc-up-vec.patch` and
`experiments/q2-hc-up-vec-exact.patch` are separate first-party MIT deltas
against the measured fusion. They vectorize original-F16 HC up scalar reads;
the latter fixes the generated FMA order to retain exact Q2 output. Both use
the same independent official Gufo pin and existing upstream/llama.cpp notices.
The faster reassociating variant's numerical drift is retained as evidence in
`docs/Q2-HC-UP-VECTOR.md`. No antirez engine, DS4 source, sibling artifact or
external KV codec is imported.

`experiments/q2-hc-prefetch.patch` independently extends this workstream's F16
HC down kernel on the same official pin. It preserves original weight layout
and uses AMD compiler scheduling/FMA intrinsics; no external engine or artifact
is imported. First-party MIT source and existing upstream notices are retained.
It derives from the measured packed source, not the pending HC up fusion.
Static, host and GPU evidence are in `docs/Q2-HC-PREFETCH.md`.
`experiments/q2-hc-prefetch2.patch` is the separate two-group scheduling delta.
Both HC down prefetch variants are measured and rejected for performance; their
negative GPU results and complete source identity remain in that document.

`experiments/q2-hc-moe-fused.patch` derives its F32 norm mapping and expert
epilogue from the same independently fetched official Gufo source, after this
workstream's measured exact HC up vector checkpoint. It stages the MoE row in
LDS without importing UD activation precision or another engine. The generator,
GPU fixture and orchestration changes are first-party MIT; existing upstream
and llama.cpp notices remain intact. Source/static receipts and the runtime
qualification status are recorded in `docs/Q2-HC-MOE-FUSION.md`.

`experiments/q2-hc-norm-half.patch` independently extends this workstream's
measured F32 MoE/HC fusion on the same official Gufo pin. It emits the existing
F16 consumer copy alongside F32 norm, reuses the existing executor scratch,
and explicitly retains the measured gfx1151 rounding sequence. The generator,
fixture and runner extensions are first-party MIT; upstream notices remain.
No antirez engine, DS4 source/artifact or KV codec is imported. The failed first
round and corrected GPU qualification are retained in `docs/Q2-HC-NORM-FUSION.md`.

`experiments/q2-hc-down64.patch` and the three `q2-hc-down*` scheduling deltas
derive from the same measured MoE/HC source and official pin. First-party MIT
generators retain upstream notices. The 64x64 component and the three scheduling
variants are measured and rejected for performance; exact output hashes and
unchanged numerical control failures remain in `docs/Q2-HC-DOWN-TILES.md` and
persistent evidence. The component plotting tool is first-party MIT.

`experiments/q2-ple-{q2,ud}.patch` add host clocks/counters to `ngram.cpp` plus
a first-party MIT diagnostic header. They independently derive from measured
Q2 MoE/HC and pristine official Gufo, without altering executor/kernels, GGUF
bytes or quantization. Fixtures, analysis/plot tools and bounded storage observer
are MIT. The storage observer uses the independently fetched official GGUF
metadata helper; no CPU model execution or sibling project artifact is imported.
Source identities, observations and limitations are in `docs/Q2-PLE-ANALYSIS.md`.

`experiments/q2-ple-io-{q2,ud}.patch` extend those independently derived PLE
diagnostics with descriptor-local access advice and a BF16 cache-budget control.
`experiments/q2-ple-cache64k-{raw,diagnostic}.patch` isolate only the BF16 capacity
change in the measured MoE/HC source and its instrumented equivalent. All four
patches retain official Gufo provenance and notices; new fixtures, analysis,
plotting and orchestration are first-party MIT. No model data is converted or
copied, and no external engine, DS4 source or sibling artifact is imported.
Source receipts and measured limitations are recorded in `docs/Q2-PLE-CACHE.md`.

`experiments/q2-staged-weights.patch` is first-party MIT work against the same
independently fetched official Gufo pin and measured MoE/HC checkpoint. It moves
the existing Q2 affine decode into shared staging without changing the stored
format or importing another implementation. Existing upstream notices remain.
Its original-shape synthetic benchmark, generator and runner extensions are MIT;
the measured component regression is explicit in `docs/Q2-STAGED-WEIGHTS.md`.

`experiments/q2-half-wave*.patch` independently derive from that same measured
MoE/HC checkpoint and official pin. They distribute the existing affine decode
between paired lanes and exchange already-rounded F16 bits without changing
model bytes or the LDS allocation. The generator and reports are first-party
MIT; upstream notices remain intact. No external project implementation is
imported. LLVM intrinsic documentation informs the alternate exchange primitive;
source links, exact GPU replay and the measured lack of component benefit are
in `docs/Q2-HALF-WAVE.md`. The comparison plotting tool is first-party MIT.

`experiments/q2-ple-lookahead.patch` adds a validated borrowed-input boundary
to the measured official-Gufo-derived executor. Kernels and original model bytes
remain unchanged; upstream notices remain intact. The bounded C17 flow, fixtures,
original-weight harness, generator and analysis are first-party MIT. No external
engine or sibling project artifact is imported. Source and ownership contracts
are recorded in `docs/Q2-PLE-LOOKAHEAD.md`.

`experiments/q2-hc-decode{8,16,32}.patch` are first-party MIT row-partition
changes against the measured MoE/HC checkpoint and the same independently
fetched official Gufo pin. Original F16 model bytes and upstream notices remain
intact. The generator and plotting extensions are first-party MIT; no external
engine or sibling project implementation is imported. Source hashes, changed
reduction order, independent checks and complete-model scope are recorded in
`docs/Q2-HC-DECODE-WAVES.md`.

`experiments/q2-affine-palette.patch` is a first-party MIT delta against the
measured HC16 candidate and the same independently fetched official Gufo pin.
It precomputes the four existing Q2 affine values inside registers, retaining
original model bytes and upstream notices. The generator and admission changes
are MIT; no external engine implementation or sibling artifact is imported.
Source, numerical replay and measured scope are in `docs/Q2-AFFINE-PALETTE.md`.

`experiments/q2-hc-{fragment,stage}-bound.patch` are independent compiler-load
scheduling deltas against the measured affine-palette source and the same
official Gufo pin. Upstream notices, weights and arithmetic remain intact.
The generator, fresh-profile analysis, plot and runner guard changes are
first-party MIT. Both candidates are measured and rejected for performance;
their original numerical control failures remain explicit. No external engine
or sibling artifact is imported. See `docs/Q2-PREFILL-GAP.md` and its source
receipts for provenance, exact replay, limitations and artifact identities.

`experiments/q2-hc-direct.patch` and `experiments/q2-hc-chain-waves.patch`
independently derive from the measured affine palette on the same official
Gufo pin. `experiments/q2-hc-chain-coalesced.patch` applies after the paired-wave
delta. All three retain original F16 values, accumulation chains and upstream
notices. Generators, orchestration and plot tools are first-party MIT; no
external engine, DS4 source or sibling artifact is imported. The first two
candidates fail the component performance gate and the combined path fails
to improve complete-model prefill. Their exact output replays, source hashes,
original numerical-control failures and rejection are in `docs/Q2-HC-DATA-REUSE.md`.
The additional library audit reads only independently fetched official Gufo
`blaslt.cpp` and `dense_blaslt_sweep.hip`; it adds no library implementation or
performance claim.

`tests/q2_hc_pp.cpp` adds a first-party MIT hipBLASLt algorithm diagnostic using
its existing independent FP64 fixture and deterministic synthetic inputs. It
uses the official library extension API; no external benchmark source is copied.
The official Gufo helper at the recorded pin informed the workspace hypothesis,
while this diagnostic retains 100 MiB rotation, all numerical failures and
position-invariance checks. Analysis/plot tools are first-party MIT.
`experiments/q2-hc-library-down.patch` changes only the selected affine-palette
`blaslt.cpp` dispatch for F16 M320/K10240/n2048, preserving upstream notices and
original values. Algorithm index 7526 is installation-specific and exploratory;
it has not passed the declared numerical gate. No antirez engine, DS4 code or
sibling project artifact is imported. Source identity and measured scope are
recorded in `docs/Q2-HC-LIBRARY.md`.

`experiments/q2-hc-input.patch` is an independent MIT delta against the same
measured palette and official Gufo pin. It moves the existing F32-to-F16 input
rounding into HC down's load stage while retaining original F16 model values,
WMMA geometry and both accumulation chains. The source generator, fixture,
runner guards and analysis are first-party MIT. The fixture reuses this
workstream's independent HC oracle; no external test implementation or sibling
artifact is imported. Source identity, preserved numerical failures and the
component/model scope are documented in `docs/Q2-HC-INPUT.md`.

`experiments/q2-hc-up-chains.patch` derives independently from the measured
palette at the same official pin. It distributes the original raw-F16 HC up
K16 sums across wave pairs and combines them in the existing gate LDS, enabling
256x128 tiles without changing stored weights or the arithmetic contract.
The generator, added fixture, guard extensions and analysis/plot tools are
first-party MIT. The fixture reuses this workstream's independent FP64 HC
checks, adds partial tiles and repeated rows, and rotates 100 MiB of synthetic
weights. No external engine, DS4 source or sibling artifact is imported.
Source identities, numerical checks and measured scope are in
`docs/Q2-HC-UP-CHAINS.md`; upstream notices remain intact.

`experiments/q2-hc-down-wide.patch` and its `-k1` companion derive from the
retained paired-HC-up source at the same independently fetched official pin.
They generalize the existing exact wave-pair arithmetic to a wider F16 HC down
tile, with separate one/two-block staging experiments. The additional
`experiments/q2-hc-down-wide-coalesced.patch` derives from the wider BK2 tree
and changes global stage-fetch ownership while retaining the LDS layout and
ordered arithmetic. Its generator adapts this workstream's earlier contiguous
stage-read experiment. No weight conversion, external engine source or sibling
artifact is imported. The generators, source selection guards and component
plotting tool are first-party MIT. Existing
independent HC fixtures retain their original limits and failures. Source
identities and measured scope are in `docs/Q2-HC-DOWN-WIDE.md`; upstream notices
remain intact.

The routed tile fixture extends this workstream's existing MIT packed-Q2
benchmark and calls the retained official-Gufo-derived 16/48/64 dispatches.
No engine source is changed. Its analysis and plotting tools are first-party
MIT; the executed 48/64 component screen and unexecuted tile16 follow-up are
distinguished in `docs/Q2-REASSESSMENT.md`. That report also consults historical
DS4 qualification documents and result metadata read-only, as permitted
reference evidence. Their paths/hashes are in `config/q2-reassessment.json`;
no DS4 source, archive payload, compiled object or test implementation is
imported. The proposed precision-boundary comparisons are hypotheses only.

`experiments/q2-hc-single-chain.patch` independently derives a single ordered
HC down accumulator from the retained paired-up source at the same official
pin. It changes the reduction grouping, with original model bytes and input
narrowing preserved. Historical DS4 reports motivate the hypothesis only;
neither their code nor acceptance result is imported. The candidate is rejected
for component regression and additional FP64 failures, as recorded in
`docs/Q2-HC-SINGLE-CHAIN.md`. The generator, offline classification correction,
regression fixtures and plot-label extensions are first-party MIT. Existing
upstream notices remain intact and the qualified runtime is unchanged.

`experiments/q2-bitfield-isa.hip.cpp` is an independently written first-party
MIT static probe responding to the owner's representation proposal. It compares
unsigned extraction and bounded IEEE floating construction with the installed
HIP compiler; it imports no external implementation and is not a model runtime
or measured GPU benchmark. The documented retained `CodesToHalves` mechanism
belongs to the independently fetched official-Gufo-derived source. Probe
provenance and the distinction from the measured affine-palette optimization
are recorded in `docs/Q2-BIT-CONVERSION.md`.

`experiments/q2-staged-palette.patch` derives independently from this
workstream's retained paired-HC-up source at the same official Gufo pin.
It stores four rounded half weights in the previous affine metadata slot,
preserving original encoded weights, activation precision and matrix arithmetic.
It imports no external implementation, model conversion or sibling artifact.
The generator and source-selection guards are first-party MIT; upstream
notices remain intact. Exact numerical evidence and the component result are
recorded in `docs/Q2-STAGED-PALETTE.md`. The candidate supplies no measured
speed gain and is not promoted to the selected or qualified runtime.

`experiments/q2-hc-full-row.patch` derives from this workstream's retained
paired-HC-up source at the same independent official Gufo pin. It changes
only the original-F16 HC-down geometry and a bounded isolated output epilogue.
`experiments/q2-hc-half-row.patch` is the incremental 160-row geometry change
on that isolated source. Both preserve the two original accumulation chains
and all upstream notices. The generators and source-selection guards are
first-party MIT; no sibling implementation, converted model or external
artifact is imported. Neither geometry is selected after the measured
component comparisons in `docs/Q2-HC-ROW-REUSE.md`.

`experiments/q2-shared-overlap.patch` derives from the retained `hc-up-chains`
source at the same independent official Gufo pin. It changes host dispatch
and lifetime ordering while preserving all eight HIP/MMQ numerical sources.
The C17 lifecycle, HIP callback adapter, synthetic fixture, generator and
saved-evidence readers are independently written first-party MIT files.
Existing upstream notices remain intact. No DS4/core-thread implementation,
converted model or sibling artifact is imported. `docs/Q2-SHARED-OVERLAP.md`
records the bounded experiment, buffer ownership and qualification limits.

`experiments/q2-scaled-input.patch` derives from the retained independently
fetched official Gufo source. Its first-party packing include and test/report
tools are MIT; existing upstream notices remain. It changes activation
arithmetic and is numerically unqualified despite measured prefill gain.

Terminal-Bench Mini is independently fetched from
https://github.com/kyuz0/terminal-bench-mini at
07034484346dc724d0e2c47c821fd196add1d6fb. The unmodified benchmark/tasks retain
their Apache-2.0 license, NOTICE and upstream task attribution. Core-19 task
revision is 5c8eadf1f393183288fa08b8f73ca9a469cc5e00. The task-owned Harbor
0.20.0 environment retains its dependency licenses. No benchmark code is
relabeled first-party MIT. Only first-party orchestration/preparation and the
three-file serving patch use MIT. The serving base is same-repository LIE
commit ae9c34ef26b0bb12ae5c995cb2ec99131da5aefd, archived without modifying
its owner worktree; base and variant hashes are recorded. No sibling CachyOS
project source or artifact is imported. Original upstream example results
staged for runner unit tests are fixtures, never evidence of this Q2 cohort.

The paired HTTP context-curve experiment freezes the same-repository C17 core
at `15c6082152c3df0cb1f40d89ba5329692f307d7b`, including its state adapter and
MIT license. `config/q2-curve-source.json` binds all 333 core files and the
independently fetched official Gufo providers at the pin above. The measured
cumulative Q2 parent and pristine UD parent each receive the identical four-file
friend-access and optional sampling/reporting edits from that frozen core;
their numerical sources remain unchanged from their respective parents.
The optional dense C17 sampler, KVC, SSD, MTP and vision paths are disabled.
No DS4 or sibling CachyOS project implementation is imported.

The first-party composition, HTTP client, evidence analyzer and plotting tools
are MIT. The client imports official Gufo's pinned deterministic prose,
calibration and depth algorithm without copying or relabeling that code.
Original Gufo licenses and notices remain in both private source trees.
The source manifest describes preparation; measured runtime qualification is
separately recorded in `config/q2-canonical-http-results.json`. Neither the
composition nor successful serving changes existing numerical rejection.

The canonical-workload PLE profile derives from those measured provider
compositions. Its new first-party MIT header and tools add host observations
only; the copied `q2_ple_diag.hpp` is this repository's existing MIT diagnostic.
Official Gufo numerical kernels remain byte-identical to each parent. The
two source patches retain upstream licenses and are bound by
`config/q2-curve-profile-source.json`. No external implementation or artifact
is introduced by this instrumentation.

`experiments/q2-reaudit-q8-row.patch` and
`experiments/q2-reaudit-q8-row-norm.patch` compose only this workstream's retained
shared-Q8 dispatch, Q2 row-reuse packing include and two fixed-shape norm bodies
against its independently fetched official Gufo provider at the pin above.
Both preserve upstream licenses/notices and verify all 1022 provider files,
with five changed files per composition. Generators, orchestration and result
readers are first-party MIT. No external engine code or converted model is
introduced. Original numerical rejections remain retained; exact Q2 replay
and the norm composition's preserved prior numerical difference are reported
separately in `docs/Q2-REAUDIT-COMPOSITION.md`.

`experiments/q2-hc-down-bk256.patch` adapts the native vector fragment loader
and `mmb_hcd_kernel` from the independently fetched public MIT GSQHalo.cpp
commit `5fc881b114c1ea130f5df6a30a98be2f8d397de6`. The numerical include retains
the original ggml authors' copyright and full MIT license; the license is also
preserved under `third_party/gsqhalo/LICENSE`. The original public source hash
and exact derivation are bound in `config/q2-hc-down-bk256-source.json`.
LIE's adaptation keeps original F16 model/activation bytes, uses F16 WMMA and
two FP32 K16 chains, and selects only the M320/K10240 HC-down geometry. The
bounded sibling patch changes one unroll pragma. Preparation scripts and
orchestration are first-party MIT. Compilation is not numerical/performance
qualification or a claim of an independently owned model executor.

The `q2-hc-bk256-*-run.patch` runtime siblings format those retained ports
without changing noncomment source tokens. `experiments/q2_hc_blaslt_control.*`
copy the measured official-Gufo library recipe into a test-only renamed class;
the full Gufo MIT license is retained in each file. Their origin/source hashes,
limited renaming and all runtime provider files are recorded in
`config/q2-hc-bk256-run-source.json`. The new component fixture, preparation,
launch guards and orchestration are first-party MIT. Neither this copy nor
successful syntax compilation constitutes a new owned model executor.

The completed HC BK256 component/model results retain those exact source
capsules and public MIT derivation. The offline FP64 tool reconstructs only
deterministic synthetic fixture weights and reads this workstream's saved F16
arrays; it imports no model or sibling project artifact. Analysis and plotting
tools are first-party MIT. GPU performance evidence does not establish owned
executor replacement or independent model quality.
