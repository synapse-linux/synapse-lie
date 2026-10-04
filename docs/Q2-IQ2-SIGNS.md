<!-- SPDX-License-Identifier: MIT -->
# IQ2 packed signs: complete decode component

This experiment applies the packed sign expansion identified in the
[official DeepSeek audit](Q2-DEEPSEEK-AUDIT.md) to Qwen IQ2_XXS vector dots.
The initial candidate changes one header in the measured canonical Q2 provider;
all other 1019 provider files remain exact. It preserves encoded weights,
Q8_1 activations and integer dot order. The prefill WMMA path is unchanged.

## First GPU pair — 2026-10-04

Both providers rebuild fully on `.157` and complete all four commands with
exit 0. Existing independent IQ2/Q2 operators pass, as do all 1,048,576
codebook/sign/lane outputs and 640 independent FP64 sampled cycle values.
The host cohort passes 19/19 Debug and 19/19 ASan/UBSan.

The timed cycle includes Q8_1 activation production, fused gate/up and SwiGLU,
using m640/k2560, ten active experts per call, 512 experts rotated across 64
calls, and 432,537,600 encoded weight bytes. Inputs, weights and routing IDs
are uploaded before timing. The following values are **microseconds per
complete component call**, not model tokens/s.

| Sample | Reference µs | Packed signs µs |
| --- | ---: | ---: |
| Warmup 0 | 85.499466 | 50.020985 |
| Warmup 1 | 85.409470 | 49.897251 |
| Measured 0 | 85.317596 | 49.925377 |
| Measured 1 | 85.510704 | 50.142857 |
| Measured 2 | 85.396339 | 50.017235 |
| Measured 3 | 85.463074 | 49.876610 |
| Measured 4 | 85.419327 | 49.974735 |
| Median, measured only | 85.419327 | 49.974735 |

The median component time falls **41.495%**. This single sequential pair is
not an independent repeated-model comparison or a whole-model speedup.

Full output replay is **not exact**. In the 409,600-value cycle, 298,221
values change, with maximum absolute delta 7.62939453125e-6 and relative L2
1.2502999412561685e-7. Independent FP64 errors remain below the unchanged
0.002 limits in both variants; their largest sampled scaled errors are
5.900832656e-7 and 6.931465109e-7. Exact codebook/sign outputs show that sign
expansion itself is correct. This does not prove model-level harmlessness.

The retained gfx1151 assembly explains a rounding change: the reference
multiplies the Q8 scale by 1/8, then by the weight scale, before the final
accumulating FMA. Fast-math reassociates the candidate's scale with the
integer-dot conversion first and uses mixed FMA. Unchanged source arithmetic
did not preserve compiled rounding. The comparison analyzer retains exit 1
for failed exact replay; successful independent operator exits are separate.

[Complete verified pair and all output comparisons](../config/q2-iq2-signs-results.json).
`tools/analyze-q2-iq2-signs.py` verifies source inventories, host/fixture
identity, full MMQ builds, leases, command exits, output completeness and
artifact hashes before emitting the report. No original model was accessed.

## Ordered-scale follow-up

An isolated variant retains packed signs and explicitly emits the reference
scale product before the accumulating multiply. A preliminary `__fmul_rn`
version failed to constrain fast-math in device assembly; its source patch
and assembly receipt are retained, and it was not run on GPU. The second
variant uses one gfx1151 `v_mul_f32` instruction, without memory fences or
extra global buffers. Device assembly confirms the intended scale order.

[Source inventory](../config/q2-iq2-signs-ordered-asm-source.json),
[patch](../experiments/q2-iq2-signs-ordered-asm.patch), and
[follow-up scope](../config/q2-iq2-signs-ordered-plan.json) are retained.
The second host cohort passes 19/19 Debug and 19/19 ASan/UBSan. The second pair
runs ordered candidate first, followed by a fresh full-build reference.

| Sample | Repeated reference µs | Ordered signs µs |
| --- | ---: | ---: |
| Warmup 0 | 85.420753 | 50.103237 |
| Warmup 1 | 85.281998 | 49.988857 |
| Measured 0 | 85.113892 | 49.887608 |
| Measured 1 | 85.355125 | 50.046986 |
| Measured 2 | 85.289497 | 50.162594 |
| Measured 3 | 85.494965 | 50.111362 |
| Measured 4 | 85.351845 | 50.001968 |
| Median, measured only | 85.351845 | 50.046986 |

The ordered variant saves **41.364%** of component time and all **110 output
buffers (1,568,078 values including guards) are byte-exact** against the
repeated reference. Both original/ordered providers pass the independent
operators and unchanged FP64 limits. Reference r1/r2 also replay exactly for
all 110 buffers. This supports a canonical model experiment; it does not
establish bit identity for every possible input or model throughput parity.
[Verified ordered pair](../config/q2-iq2-signs-ordered-results.json).

The six-cohort window closes at 2026-10-04T00:07:51.297211+00:00 with 28 command
exits zero, 474 collected artifacts, 34 own processes/groups retired, empty KFD
and all four original lease identities free. The initial comparison's analyzer
exit 1 remains preserved. No model run, GPU reservation or restart remains.
[Release receipt](../config/q2-iq2-signs-window-release.json).

All results remain component evidence. The acceptance target is still PP
and TG parity against UD at every canonical context depth, with model quality
verified separately. The measured PLE/storage prefill deficit is unaffected
by this decode-only candidate.
