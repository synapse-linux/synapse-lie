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
