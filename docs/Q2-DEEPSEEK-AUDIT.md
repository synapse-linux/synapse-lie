<!-- SPDX-License-Identifier: MIT -->
# DeepSeek techniques applicable to the Qwen Q2 workstream

The independently fetched official Gufo source at
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e` contains the DeepSeek port with the
same **IQ2_XXS gate/up and Q2_K down** encodings. This is a useful source of
mechanisms, but its activation formats, routing geometry and arithmetic differ.
The audit compares actual launch paths with the measured Qwen provider and
the retained experiment history. No sibling DS4 source or artifact is imported.
[Source identities](../config/q2-deepseek-audit.json) pin the inspected files.

The [prefill reuse follow-up](Q2-IQ2-PREFILL-REUSE.md) has completed four
component arms: cached IQ2 scales advance to a native canonical model test;
LDS codebook staging does not. The separate
[scaled-row input reuse](Q2-SCALED-ROW-REUSE.md) audit finds a second input pass
that can be removed with three retained values per thread. That newer candidate
has matched device assembly only and is excluded from the current model run.

## Opportunities identified in this Q2 workstream

| Mechanism | DeepSeek implementation | Current Qwen difference and proposed check |
| --- | --- | --- |
| Packed integer IQ2 sign expansion in vector decode | `dev_iq2_i8x8_lut`, `ds4_rocm_iq2_gate.hip.hpp:57`: parity completion, multiply/mask to spread sign bits, packed xor/add negation. | Completed in the ordered Qwen candidate: full-model decode improves 4.446–5.188% against an unchanged order control across all eight canonical depths. This change is retained in the current PLE campaign; it does not improve prefill. |
| Large row groups followed by smaller tails in one expert map | `ds4_rocm_q2_down_tile_map`, `ds4_rocm_q2_down.hip.hpp:11`, with separate launch spans in `ds4_rocm_moe_launch.hip.hpp:303`. | The isolated Qwen mixed128/64 component saves 1.487–4.148% across four recorded-routing cases, with exact outputs and passing independent FP64 checks. The completed [canonical model comparison](Q2-IQ2-MIXED-CANONICAL.md) retains exact Q2 histories but establishes no uniform model gain; prefill remains below UD at every depth. |
| Stage the IQ2 codebook once per workgroup | DeepSeek vector gate/up stages 256 eight-byte grid entries plus bounded Q8_K activations in shared memory before reusing them across output rows (`ds4_rocm_iq2_gate.hip.hpp:238`). | Qwen vector dot reads the constant grid. A separate candidate could stage the 2 KiB codebook while retaining Q8_1 activation layout. Test the extra barrier/LDS cost and actual global-cache behavior; do not combine this with the sign change initially. |

The mixed-map proposal must preserve every slot exactly once and the ordered
K accumulation. Two launches and larger descriptor storage can lose more than
padding costs. DeepSeek's 128/64 split is an example, not a Qwen tuning result:
our prior global tile 128 trial regressed every tested distribution, while 64
helped only the most shared synthetic routing. Start from the existing gate/up
64/128 specializations and real canonical histograms; do not force 128 down.

The follow-up [canonical routing profile](Q2-ROUTE-PROFILE.md) now records those
counts with unchanged numerical kernels. Inspection also confirms that Qwen
already omits empty WMMA fragments but still executes their paired epilogue
stores/barriers. A separate [live-epilogue candidate](Q2-IQ2-LIVE-EPILOGUE.md)
adds only a uniform guard, with unchanged VGPR/LDS and zero scratch in device
assembly. Its completed GPU comparison is numerically exact but shows mixed,
sub-percent timing; neither variant advances to a model run. The distinct
[mixed 128/64 map experiment](Q2-IQ2-MIXED.md) now has a C17 map builder and
complete component fixture, with 22/22 Debug and ASan/UBSan host checks on .157.
Its completed GPU comparison improves all four recorded-routing cases, with
the small full-tile regression retained. Reserved padding is not a model speedup.

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
explicit scale-rounding fix. The subsequent
[canonical comparison](Q2-IQ2-CANONICAL.md) measures 4.446–5.188% full-model decode
improvement; independent model quality and whole-curve parity remain open.

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
The completed device qualification verifies this identity and the retained
ordered-scale variant; source algebra alone was not the acceptance evidence.

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

## Follow-up in the active prefill WMMA loader — 2026-10-04

The [canonical IQ2 campaign](Q2-IQ2-CANONICAL.md) now confirms the ordered
MMVQ change improves complete-model decode by 4.446–5.188% against the unchanged
post-candidate control. It does not improve prefill. The generic IQ2 MMQ tile
loader already expands signs arithmetically, but that is not the selected
Q2 prefill path for hidden2560 / expert640 / padded-down768. `MoeExperts`
selects `RoutedGatedIQ2Gemm`, whose dedicated `RoutedF16GEMMKernel` still reads
the eight-byte `ksigns64` entry for each packed sign index. The earlier presence
of arithmetic signs in MMQ therefore does not close this WMMA opportunity.

The new isolated `.deps/gufo-q2-curve-iq2-wmma-signs` source starts from the
measured ordered-decode provider and changes only that integer sign expansion
in `kernels.hip.cpp`. The other 1019 files remain exact, including the accepted
decode experiment's scale boundary. Codebook, FP16 scale rounding, WMMA
accumulation, SwiGLU, routing/tile geometry, Q2 down, PLE and C17 core are unchanged.
The [generator](../tools/prepare-q2-iq2-wmma-signs.py),
[patch](../experiments/q2-iq2-wmma-signs.patch) and
[full source manifest](../config/q2-iq2-wmma-signs-source.json) retain provenance.

Same-flag gfx1151 device compilation gives the following ordinary-output bodies:

| Expert tile rows | Static instructions, original → candidate | Global loads | VGPR | Scratch bytes |
| ---: | ---: | ---: | ---: | ---: |
| 16 | 661 → 718 | 25 → 17 | 82 → 82 | 0 → 0 |
| 48 | 1161 → 1221 | 32 → 24 | 94 → 94 | 0 → 0 |
| 64 | 1391 → 1442 | 34 → 26 | 102 → 102 | 0 → 0 |
| 128 | 2381 → 2441 | 48 → 40 | 148 → 148 | 0 → 0 |

The eight eliminated loads come at an integer-instruction cost. WMMA instruction
counts and register allocations are unchanged; the sign table may already be
cache-resident. These are static instruction bodies, not dynamic memory traffic,
GPU timings or a model speedup. Full-output replay remains required because
unchanged floating-point source does not prove unchanged compiled results.

The component fixture reuses all eighteen independent IQ2 operator cases and
adds two full-size narrowing → routing compaction → fused gate/up/SwiGLU cycles:
2040 tokens / 512 active experts / tile64, and 2048 / 128 / tile128. Each cycle
touches respectively 432,537,600 or 108,134,400 encoded weight bytes, exceeding
the documented 32 MiB MALL capacity. Two warmups and five measured samples each
contain eight complete calls. Uploads, allocations, hashing and validation stay
outside HIP-event timing. Full guarded outputs and independent FP64 samples are
retained: 22 output files, 20 oracle reports and 105,371,008 output bytes per arm.
These routing patterns are synthetic; they do not establish real-context parity.

The isolated `iq2-wmma-signs-check` mode rejects model dispatch, detached runs
and unrelated sources. Its component target directly builds the production
kernel translation unit with the same numerical flags; MMQ is not part of this
component cycle. The paired analyzer binds source inventories, host-qualified
harness, leases, binary and operands, checks all samples and output buffers,
and preserves an exact-replay failure as exit1. A component gain would admit a
future canonical PP/TG comparison; no such model arm is implemented or admitted.

[Static validation](../config/q2-iq2-wmma-signs-static.json) verifies both
1020-file inventories, exact generator reconstruction, host-only fixture syntax,
both device compilations and the five-command build graph. The first renamed-main
syntax failure and new formatting failure remain retained; both are corrected.
The shared formatter still reports the same five untouched failing files as the
parent. No GPU/runtime result is claimed. The [bounded plan](../config/q2-iq2-wmma-signs-plan.json)
starts with the paired PLE 21-test Debug/ASan host cohort, then the two component
arms, after core's next window has been released. No observer, waiter or restart
is scheduled. Existing independent model numerical rejection remains open.

Before runtime admission, a review closes an evidence gap in the new fixture:
numerical-tolerance failures now save their arrays and allow the remaining
operator cases and timings to finish. Limits and the original scalar oracle
are unchanged. The completed fixture and analyzer still return exit1 whenever
any numerical case fails; runtime, nonfinite-value and guard faults stop the
run. A complete failure summary is required, so an interrupted run cannot be
reported as a completed numerical failure. The model analyzers retain their
strict all-zero command requirement. [Updated harness evidence](../config/q2-iq2-wmma-ready.json)
records corrected syntax and a byte-equivalent reanalysis of the retained
four-arm canonical result after separating artifact integrity from success.

## Completed WMMA component comparison — 2026-10-04

Both `.157` arms complete with all three command exits zero. The independent
FP64 checks pass in every one of the 20 cases per arm: maximum relative RMS
error is 0.0005699411 and maximum scaled error is 0.0005210963, below the unchanged
0.002 limits. All 22 complete F32 output pairs, 105,371,008 bytes per arm, are
byte-identical. Source, harness, input and weight inventories match the declared
pair. No original model is loaded by these component checks.

| Tokens / active experts / tile | Original median µs | Candidate median µs | Time change |
| --- | ---: | ---: | ---: |
| 2040 / 512 / 64 | 5863.463 | 6009.215 | +2.486% |
| 2048 / 128 / 128 | 4346.467 | 4458.464 | +2.577% |

Each median contains five samples of eight complete narrowing/compaction/
gate-up-SwiGLU calls, after two warmups. All five candidate samples are slower
than all five reference samples for their shape. This single paired campaign
does not isolate clock/order effects, but it supplies no evidence of a speedup.
The additional integer instructions and already cached sign table are plausible
explanations, not established causal attribution. The candidate is **not advanced
to a model arm**. The measured ordered MMVQ decode improvement remains retained;
this result applies to the separate prefill WMMA replacement only.

The [paired result](../config/q2-iq2-wmma-signs-results.json) retains every sample,
oracle metric and full-buffer comparison. The same host capsule passes 21/21
Debug and ASan/UBSan, including the independent
[PLE cache-first comparison](Q2-PLE-CACHE-FIRST.md#paired-host-results-on-157--2026-10-04).
All 12 commands exit zero and 59 artifacts verify. Fresh release at
02:58:06.736101 UTC checks 15 recorded processes and 12 groups absent, empty KFD
and four unchanged original lease identities EX|NB/free. The remote/main
[release receipt](../config/q2-ple-wmma-window-release.json) and shared registry
record closure; no Q2 job, waiter or restart remains. Whole-curve PP/TG parity
and independent original-model numerical qualification are still open.

## Further prefill data reuse — 2026-10-04

The [four-arm follow-up](Q2-IQ2-PREFILL-REUSE.md) adapts DeepSeek's shared IQ2
codebook and per-superblock data reuse as separate Qwen candidates. Scale reuse
saves 0.815–3.743% of complete component time against the repeated control on
the four recorded routing shapes; full tiles cost 0.445% more. All output arrays
remain exact. It advances only to preparation for the native C canonical model
comparison. Codebook-LDS has mixed results and does not advance. Existing wide
affine LDS stores and token-compact narrowing are already present in Qwen;
the active DeepSeek Q8 MMQ path is not a drop-in for the current F16 arithmetic.
No new full-model prefill improvement is established by this component result.

## Provenance

The sign technique is adapted from official Gufo's DeepSeek port, retaining
Gufo's MIT notice and the existing llama.cpp vendor notices. Gufo records
antirez/ds4 ancestry at `84cc882352757baf628a1776badf7cc54d584e28`, its DS4
GB10/GX10 adapter ancestry at `910501e`, and shared llama.cpp kernels at
`5c0e9468378eba6bf3cc1989ff5d62fbbe4d9e3a` in the retained third-party inventory.
No antirez Qwen runtime is introduced. Core ABI, persistent state, scheduling
and metrics contracts are unchanged by this source-only numerical experiment.
