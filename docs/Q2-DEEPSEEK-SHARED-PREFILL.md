<!-- SPDX-License-Identifier: MIT -->
# Renewed official DeepSeek audit, including shared Q8 prefill

This read-only audit uses independently fetched official Gufo at
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, comparing its DeepSeek kernels with
the exact mixed-Q2 provider behind the fixed1443.672867 reference. It imports
no sibling DS4 source/artifact and changes no numerical implementation.
[Inspected source identities](../config/q2-deepseek-shared-prefill-audit.json).

Two concrete Qwen gaps remain worth investigating: producing the shared-Q8
activation tile in the raw-HC producer, and pairing wide shared gate/up inside
one W8A8 kernel. Neither is a ready-made DeepSeek2048 kernel or a measured gain.
The shared projections themselves have similar Q2/UD cost. Producer fusion
targets part of Q2's extra preparation; it cannot explain or remove the whole gap.

## What is actually active

Qwen `GatedDense` fuses Q8 gate/up for vector/decode calls, but wide prefill
calls `Dense(gate)`, `Dense(up)`, then `SwigluHalf` for the shared down route.
For the original Q2 shape, shared gate/up has M640/K2560 and uses W8A8;
shared down has M2560/K640 and uses on-the-fly Q8-weight dequantization to
F16 matrix inputs, with the private `shexp_half` activation buffer.
Q8 weights do not imply that all three projections use the same activation
format or numerical kernel.

`Dense` already caches the tiled Q8 input by pointer/rows/columns, so gate
and up share one quantization. `SwigluHalf` already writes the consumer's F16
input directly. `SwigluQ8Tiled` also exists for down shapes selecting W8A8.
The two vector Q8 input slots are a separate decode mechanism. Copying another
input cache or adding a separate shared-down narrowing would duplicate work.

DeepSeek's `ds4_gpu_shared_gate_up_swiglu_q8_0_tensor` uses a paired projection
helper followed by a separate SwiGLU. Its prefill graph only selects that
helper at n_tokens<=136; the helper itself falls back to two dense calls above
136. At2048, `rocm_graph.cpp:4166` uses separate shared gate/up and SwiGLU.
Its special hipBLAS shared route is guarded by K2048/M4096, not Qwen K2560/M640.
The fully fused shared-down/HC-expand entry has no batch dimension and is used
in decode; the DeepSeek prefill graph still calls shared down separately.

## Existing measured cost, without changing the benchmark

The retained [scaled/library diagnostic](Q2-SCALED-LIBRARY-PROFILE.md) has
the following prefill kernel-symbol totals:

| Symbol group | Q2 | UD | Scope |
|---|---:|---:|---|
| W8A8 shared gate/up specialization | 96 calls,20.305258ms | 96 calls,20.446291ms | 1.383% of Q2 kernel sum |
| SwiGLU to private F16 | 48 calls,0.842058ms | 48 calls,0.947173ms | Already avoids a separate narrowing |
| Generic F16 shared-down-compatible specialization | 50 calls,14.846804ms | 50 calls,15.548591ms | Includes other calls; not an exact48-call shared-down attribution |

These are older diagnostic traces, not a new performance baseline or current
fixed-point timing. Source and symbol counts support the gate/up mapping.
The generic F16 group bounds the shared-down cost but cannot independently
identify all its calls. Even eliminating the complete20.305ms gate/up group
would remove only1.38% of that historical kernel interval. Real fusion cannot
eliminate its required matrix products. This bounds priority; it does not
discard a useful small optimization or predict fresh model throughput.

## Remaining hypotheses

1. **Publish Q8 tiles from the raw-HC mix producer.** The active Q2
   `HcMixRawF16Gemm` already writes F32 mixed rows and their F16 copy, but
   `HcMix` publishes only the half-input identity. The next shared gate
   invokes `QuantizeQ8Tiled`. Gufo's wide UD mixer already publishes F16 and
   tiled Q8 copies together. Adapt that working producer/consumer contract
   to the raw-F16 Q2 mixer, computing the exact current Q8 scale/codes from
   rounded F32 mixed values. This can remove one shared-input quantization
   pass per eligible layer. At2048, the48 separate reads cover960MiB of logical
   F32 input; this is not measured DRAM traffic. The older profile's complete
   tiled-quantization group is only10.283ms, including other producers, so
   that number is an upper bound, not a predicted saving. DeepSeek's own
   producer-Q8 hook is disabled; do not claim it supplies an active kernel.
   Buffer publication/invalidation and partial-launch failures require
   lifecycle checks before any model run.

2. **Pair shared gate/up at2048 while preserving W8A8 arithmetic.** One
   workgroup could share its activation tile across both weights and emit
   the existing SwiGLU F16 result directly. Preserve every K32 accumulator
   update, scale order and current rounded SwiGLU boundaries. Check the
   combined producer/consumer, not only launch counts. Two accumulator sets
   can increase VGPR/LDS and spills; DeepSeek's <=136 kernel does not prove
   the design pays at2048. The current96-call/20.305ms group supplies a
   retained reference for prioritization, not a promised gain.

3. **Shape-specific shared-down selection, lower priority.** DeepSeek keeps
   deterministic cached hipBLASLt plans and optional budgeted F16 weight
   mirrors. Qwen's shared down instead uses a generic F16 matrix-core tile
   over original Q8 blocks. A bounded comparison on M2560/N2048/K640 is
   distinct from the already measured HC-down M320/N2048/K10240 sweep.
   A library experiment would need a bit-checked GPU-only F16 mirror of
   the same encoded shared-down weights, no model-file conversion, and
   resource accounting. Retaining original Q8 weights for decode adds
   150MiB for48 F16 mirrors. Deterministic algorithms and the original
   accumulation/quality gates remain required. The small measured compatible
   symbol group limits its likely relevance to the total gap.

These are source-backed proposals, not prepared patches or runtime results.
No hypothesis is added to the retained norm candidate automatically.
Measure a useful component first, then the same frozen exact2048 model
comparison with qualified control-binary replay. Preserve marginal candidates
for a targeted composition; full curves still wait for fixed-point UD parity.

## Paths that are already covered or cannot be copied directly

| Path | Current disposition |
|---|---|
| IQ2 packed vector signs | Already retained; decode gain measured. Separate WMMA-prefill sign replacement was exact but2.49–2.58% slower. |
| Mixed128/64 maps | Already implemented and measured; no uniform model PP gain. |
| IQ2 scale reuse, LDS codebook, dead-fragment staging | Already measured; scale-reuse model curve does not close parity, other gates retain failures. |
| Q2 raw-weight staging/code-byte reuse | Prior negative experiments; a new label is not a new mechanism. |
| One-stage-ahead expert and W8A8 loads | Already present in Qwen `fetch_stage`/`commit_stage`; DeepSeek's prefetch cannot be claimed as missing. |
| Holding norm inputs in registers | Already present in both paired Qwen norm kernels as `float4 v[10]`; the latest fixed-shape change only affects indexing. |
| Shared/routed side-stream overlap | Already measured exact but−1.029% full-model PP; actual overlap did not establish a gain. |
| Direct F16 replacement of shared gate/up | Upstream Qwen shape comments retain0.19ms W8A8 versus0.23ms F16 for640x2560; not a newly discovered positive result. |
| DeepSeek HC pre-block fusion | HC24 projection, Sinkhorn and post-projection RMS differ from Qwen rank320/sigmoid/grouped norm. Transfer retention/tile principles, not its formula or outputs. |
| D2R or producer-prequantization hooks | HIP D2R is stubbed; DeepSeek producer hook returns0. No working gfx1151 path to enable. |

Activation preparation and HC down accounted for70.29% of the older net Q2
extra kernel time; later paired-norm work already removes part of that cost.
Keep those larger families in the roadmap. A shared-Q8 optimization can be
valuable, but the measured common20ms path is insufficient by itself to supply
the roughly16.8% throughput increase required by the fixed Q2/UD comparison.
No new GPU build, model run, profile or context curve occurs in this audit.
