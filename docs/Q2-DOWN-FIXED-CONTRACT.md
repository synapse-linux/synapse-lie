<!-- SPDX-License-Identifier: MIT -->
# Q2 down specialization for known null arguments

This new candidate derives from retained **1587.893545 PP / 25.12414406 TG**,
with unchanged fixed UD **1685.777092 PP / 24.34174251 TG**. The parent still
needs **6.164365%** more prefill throughput. There is no runtime result yet.

The actual `LaunchRoutedQ2HalfStorage` call passes null `swiglu_gate` and
`out_half`. Making these two values compile-time constants removes unused
output routes and their live registers. The private route also omits the
active output alignment/row checks proven by its selector: `m=2560`, `k=640`,
16-byte-aligned output, 20 full blocks of 128 rows and token tiles 16/48/64.
Ragged expert/token checks remain. The original kernel handles other shapes
and alignments. The generator verifies the literal null call arguments.

| Token tile | Parent / candidate instructions | Parent / candidate VGPR | LDS bytes |
| ---: | ---: | ---: | ---: |
| 16 | 1254 / 469 | 85 / 84 | 14464 |
| 48 | 2641 / 764 | 96 / 95 | 18560 |
| 64 | 3350 / 880 | 104 / 103 | 20608 |

The integrated provider preserves all 164 original device bodies and exactly
matches the three separately compiled private draft bodies, with no spills.
Much of the instruction reduction removes inactive branches; this is not a
runtime speedup measurement. Unlike the previous bounds-only draft, all three
specializations use fewer VGPRs than the retained parent.

Encoded Q2 bytes, activation/scale layout, F32 affine FMA, half palettes,
K16 WMMA order, inverse-scale product, half-output rounding and register
transpose stay unchanged. There is no allocation, lifetime, stream, callback,
public ABI or scheduler change. This is a private transitional HIP experiment,
derived from independently fetched official Gufo at
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, retaining MIT provenance.

The bounded experiment tests only this new candidate. The GPU component uses
44 cases / 132 guarded whole-output pairs, five whole-buffer checks after
timing, aligned and four-byte-aligned fallback output, and saved layer 0/3/22
routing. Timings alternate the literal parent and candidate over three weight
rotations beyond 32 MiB MALL. Synchronized monotonic wall time and raw HIP event
validity are retained separately. Finite numerical differences are preserved
and do not suppress the original-model performance measurement.

The model comparison remains exact2048 input / tg128 with 127 timed decode
calls, capacity9216 / chunk2048, C1 greedy, MTP off, one warmup and three
measurements, and 15-second pauses outside timers. Reuse saved Q2/UD/1587 parent
results without rebuilding or rerunning them. No Q4 or full curve is included.
Collect all artifacts, retire jobs and release the GPU window before analysis.

[Provider manifest](../config/q2-down-fixed-contract-source.json),
[static binding](../config/q2-down-fixed-contract-static.json),
[draft evidence](../config/q2-down-fixed-contract-draft-static.json).

New .157 host 37 Debug and 37 ASan/UBSan checks pass, ending
2026-10-06T13:14:38.530298+00:00. All seven artifacts collect; the
[plan](../config/q2-down-fixed-contract-plan.json) freezes 198 runtime fixtures
and six manifests. GPU admission and numerical/model measurements remain pending.
