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
