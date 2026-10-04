<!-- SPDX-License-Identifier: MIT -->
# DeepSeek techniques applicable to the Qwen Q2 workstream

The independently fetched official Gufo source at
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e` contains the DeepSeek port with the
same **IQ2_XXS gate/up and Q2_K down** encodings. This is a useful source of
mechanisms, but its activation formats, routing geometry and arithmetic differ.
The audit compares actual launch paths with the measured Qwen provider and
the retained experiment history. No sibling DS4 source or artifact is imported.
[Source identities](../config/q2-deepseek-audit.json) pin the inspected files.

## Opportunities identified in this Q2 workstream

| Mechanism | DeepSeek implementation | Current Qwen difference and proposed check |
| --- | --- | --- |
| Packed integer IQ2 sign expansion in vector decode | `dev_iq2_i8x8_lut`, `ds4_rocm_iq2_gate.hip.hpp:57`: parity completion, multiply/mask to spread sign bits, packed xor/add negation. | Qwen `vec_dot_iq2_xxs_q8_1` still uses packed compare/subtract intrinsics. Adapt just the sign expansion, preserving Q8_1 and every dp4a/FP32 operation. An isolated source candidate is prepared below. |
| Large row groups followed by smaller tails in one expert map | `ds4_rocm_q2_down_tile_map`, `ds4_rocm_q2_down.hip.hpp:11`, with separate launch spans in `ds4_rocm_moe_launch.hip.hpp:303`. | Qwen gate/up chooses 64 or 128 rows for the whole layer; selected scaled down uses 48. Earlier 64/128 down tests selected one width for the whole cohort. None of the recorded experiments measures a mixed map per expert. Collect canonical routing histograms, then compare full/tail partitions against the existing selector. |
| Stage the IQ2 codebook once per workgroup | DeepSeek vector gate/up stages 256 eight-byte grid entries plus bounded Q8_K activations in shared memory before reusing them across output rows (`ds4_rocm_iq2_gate.hip.hpp:238`). | Qwen vector dot reads the constant grid. A separate candidate could stage the 2 KiB codebook while retaining Q8_1 activation layout. Test the extra barrier/LDS cost and actual global-cache behavior; do not combine this with the sign change initially. |

The mixed-map proposal must preserve every slot exactly once and the ordered
K accumulation. Two launches and larger descriptor storage can lose more than
padding costs. DeepSeek's 128/64 split is an example, not a Qwen tuning result:
our prior global tile 128 trial regressed every tested distribution, while 64
helped only the most shared synthetic routing. Start from the existing gate/up
64/128 specializations and real canonical histograms; do not force 128 down.

The codebook experiment is distinct from the earlier Q2 affine-palette LDS
staging, packed-weight staging and register code-byte reuse. Those concern
Q2_K down and have retained negative results. A constant table may already be
cached efficiently, so reduced source loads alone do not justify a speed claim.

## Ideas already covered or unavailable

| Apparent opportunity | Audit disposition |
| --- | --- |
| Histogram-based MMQ tile cost model | Already present in Qwen `qfn_mmq_routed_tile_cols_for_counts`, with the same `tiles * (width + 16)` body. Moreover, the selected Q2 prefill branch uses custom F16 WMMA, bypassing this MMQ width hint. Copying the function again would not change it. |
| Compacted active-expert map | Already present through `RouteHints` and `RoutedCompact`. The missing part is mixed full/tail widths, not basic compaction. |
| Paired gate/up, fused SwiGLU and deferred MoE/HC sum | Already present or explored in Q2. DeepSeek's direct F16 intermediate cannot replace Qwen's scaled plane without changing its numerical contract and producer dependencies. |
| Q2 weight staging, wider output fragments and LDS/epilogue reuse | Already explored in Q2 weight staging, code reuse, down scatter and tile experiments. Revisit only with evidence for a different bottleneck/geometry; do not re-label these as new. |
| D2R launchers | HIP implementations return `false`/`-1` in `ds4_mmq_d2r.hip.cpp`. They are fallback stubs for NVIDIA-specific code, not working gfx1151 kernels to enable. |
| Producer-generated Q8_1 activation reuse | MMQ has the consumer hook, but Gufo DeepSeek `backend.hip.cpp:11` always returns 0. It is not an active optimization in this port. Qwen already has two explicit Q8 input slots for eligible dense projections. Broader producer fusion remains independent work. |
| Copy the complete DeepSeek IQ2 decode kernel | It uses Q8_K activation blocks and a different reduction. Identical weight compression does not make this arithmetic interchangeable with Qwen Q8_1. Adapt exact byte decoding only. |
| Copy DeepSeek quality qualification | Inapplicable: its own QUALITY.md explicitly leaves target parity unresolved and records 33/2327 optimized/debug greedy differences. Existing Qwen operator/position/KL failures remain open. |

## Prepared packed-sign candidate

`tools/prepare-q2-iq2-signs.py` verifies the complete measured canonical Q2
provider inventory, then changes one function in `mmq/vecdotq.hpp` in a new
durable `.deps/gufo-q2-curve-iq2-signs` tree. All 1019 other files remain exact.
[Patch](../experiments/q2-iq2-signs.patch),
[source receipt](../config/q2-iq2-signs-source.json), and
[device-only syntax check](../config/q2-iq2-signs-static.json) are retained.
An isolated `iq2-signs-check` runner now requires the matching reference or
candidate inventory and a full MMQ rebuild. It rejects model dispatch and
detached launch. [GPU component qualification](Q2-IQ2-SIGNS.md) now measures
41.364% less complete-cycle time with 110 byte-exact output pairs after an
explicit scale-rounding fix. No whole-model speedup or promotion is established.

Both reference and candidate also compile to gfx1151 device assembly with the
same flags. The fused IQ2 gate/up vector specialization changes from **1036 to
384 static instructions**, while VGPR allocation increases **31 to 68**; neither
has private scratch. The unpaired specialization changes 1008 to 360 instructions
and 32 to 69 VGPRs. The seven grouped specializations also become smaller.
These counts include static branch bodies and scheduling instructions, not
executed instruction totals or throughput. Higher register demand may reduce
residency. Preserve this tradeoff in the GPU comparison rather than treating
the approximately 63% smaller fused body as a speedup.
Both vector bodies retain 16 static integer dot instructions, but the compiler
also selects different floating-point instruction forms (`v_fma_mix_f32` in
the candidate). Unchanged floating-point source does not establish bit-exact
compiled arithmetic; full-output GPU replay is an explicit gate.

For a seven-bit sign index `s`, the eighth bit is its parity. Multiplying each
four-bit half by `0x00204081` and masking with `0x01010101` places a zero or one
in each byte. For nonzero magnitude `g`, `(g xor 255)+1` lies in 1..255 and
cannot carry into an adjacent byte; a positive byte is unchanged. IQ2 grid
magnitudes are 8, 25, 43. This permits the packed operation without dropping any
weight bits. The original helper also accepts an extra eighth input bit and
corrects it by parity; explicitly masking to seven bits gives the same signs.
Actual compiled execution still needs verification.

The qualification compares all 256 codebook entries times 128 sign indices on `.157`, then
the existing IQ2 independent operators and complete byte-exact output replay.
Keep the existing fractional-eighth scale expression, Q8_1 producer and dot
reduction untouched. ISA/register usage and complete decode cycle measurements
precede a canonical model curve. A faster byte primitive is insufficient.
The selected prefill WMMA path is unchanged by this candidate.

`tests/q2_iq2_signs.hip` calls the actual device dot implementation for all
256 codebook entries, 128 sign indices and 32 one-hot lanes (1,048,576 outputs).
Independent scalar parity/sign decoding and output guards check exact values.
The complete fused gate/up cycle rotates 512 experts through 64 C1 calls,
covering 432,537,600 encoded weight bytes. It saves all 409,600 outputs for
reference/candidate replay and checks 640 sampled dot pairs against independent
FP64 decoding at the existing unchanged tolerances. Two warmups and five
measured GPU-event samples include activation quantization, fused gate/up and
SwiGLU; uploads and allocations precede the interval. These are synthetic
component microseconds, not model tokens/s. Existing independent IQ2/Q2 GPU
operators run before this fixture. Both provider variants pass local HIP
syntax checks, which execute no GPU code.

[Prepared scope and file identities](../config/q2-iq2-signs-plan.json) retain
the plan. Successful component evidence can justify a complete canonical
model curve; it cannot establish whole-curve PP/TG parity by itself.

## Relation to the measured whole-curve gap

The [new full-workload PLE profile](Q2-CURVE-PROFILE.md) finds 1180.492 ms Q2
host wait against 113.939 ms UD at depth 0, falling to 138.881/112.701 ms at 128K.
The small Q2 row-cache hit rate stays near 3% while process physical reads fall
from 2046.773 to 266.328 MiB. This pattern is consistent with lower-level storage
warming, not proof that the small row cache explains the curve.

DeepSeek expert-kernel work does not fix this Qwen PLE read path. Priority is
therefore two independent mechanisms: reduce PLE read amplification and repeat
cost on the canonical workload, and qualify the bounded integer decode patch.
A bounded cache/coalesced-read change must preserve original BF16 rows and be
measured without global cache drops or model conversion. At 128K the remaining
host-wait difference is only 26.180 ms; GPU/HC/kernel work still matters there.
Host waits can overlap GPU work, so none of these numbers is a predicted gain.

The acceptance target remains PP and TG at **every** short/long point of the
canonical 0–128K curve. Historical counting fixtures and DeepSeek's own rates
are not substitute acceptance results.

## Provenance

The sign technique is adapted from official Gufo's DeepSeek port, retaining
Gufo's MIT notice and the existing llama.cpp vendor notices. Gufo records
antirez/ds4 ancestry at `84cc882352757baf628a1776badf7cc54d584e28`, its DS4
GB10/GX10 adapter ancestry at `910501e`, and shared llama.cpp kernels at
`5c0e9468378eba6bf3cc1989ff5d62fbbe4d9e3a` in the retained third-party inventory.
No antirez Qwen runtime is introduced. Core ABI, persistent state, scheduling
and metrics contracts are unchanged by this source-only numerical experiment.
