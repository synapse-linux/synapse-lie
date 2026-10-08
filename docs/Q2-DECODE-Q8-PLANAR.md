<!-- SPDX-License-Identifier: MIT -->
# Lossless planar Q8 decode screen

The current original-128K R3 GPU trace attributes 48.261% of decode kernel
time to Q8 matrix-vector projections, or 17.380 ms per forward. Four-row
workgroup grouping did not improve the large projections. This new component
changes their encoded operand layout instead: code words and 16-bit scales
occupy separate contiguous arrays, while the native one-row wave, integer dot,
scale products, accumulation and reduction remain.

The payload is still 34 bytes per 32 weights. Codes and scale bits are copied
exactly, with no Q5, F16 expansion or new quantization. This may simplify
aligned code loads but adds a separate scale stream and address calculations.
No speedup or reduced total weight traffic is inferred from the layout.

GPU packing is measured separately as a one-time operation. The component
retains original and planar weights simultaneously and reports the additional
resident bytes explicitly. A future model implementation would need bounded
ownership, startup and memory-fit qualification; none is introduced here.
The original GGUF, model dispatch, prefill and current throughput references
remain unchanged.

The synthetic fixture checks all 65536 possible scale bit patterns, including
NaNs and signed zero, through the packing operation only. Numerical projection
checks use finite inputs, tiny scales, signed scales, zero scales and ragged
K32-block counts. Encoded weights, planar arrays and activations end exactly
at their allocation boundary; outputs have guards and are poisoned before
every measured round. All original and packed bytes are checked before and
after consumption.

Timed shapes are 16384x2560 plain, 2560x6144 plain, 248320x2560 vocabulary and
640x2560 gated. Each arm has at least 64 MiB of rotating encoded weights and
64 graph calls with distinct destinations. Two warmups precede six measured
pairs, three with each arm first. Every output is retained through its check;
FP64 formulas cover sampled rows for every bank, and full output bytes are
compared for every call and repetition. Finite differences preserve timings
and exit 1; unsafe outputs stop with exit 2. Quantization is equally outside
both consumer timers and cannot be credited as a complete-decode improvement.

Local same-flag compilation succeeds. The two scalar control functions are
byte-exact to retained R3. Plain/gated planar kernels use 15/21 VGPRs versus
14/20 for the originals, all with zero private scratch. Function sizes grow
568 to 640 bytes and 832 to 892 bytes. Fewer alignment constraints therefore
do not imply fewer total instructions or better occupancy.

Official independently fetched Gufo pin:
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`; all 1032 parent provider files
verify against the retained manifest. No sibling DS4 source is imported.
The first build remains preserved; the final host fixture adds allocation-end
coverage and the exhaustive scale-bit check without changing numerical kernels.

At preparation, GPU results and original-model improvement remain unproven.
Fresh `.157` CPU fixtures, coordination and the five original leases are
required before the bounded component run. No model access, remote build,
dependency, service, tuning or cleanup is requested.

[Source binding](../config/q2-decode-q8-planar-source.json),
[device audit](../config/q2-decode-q8-planar-static.json),
[candidate](../experiments/q2-decode-q8-planar.inc),
[fixture](../tests/q2_decode_q8_planar.hip).

## Completed component and phase-specific decision

The .157 component exits 0 on 2026-10-07. All 2057 complete-output
comparisons are exact and all 68 sampled independent FP64 checks pass.
The exhaustive 65536 scale-bit packing check, immutable inputs, written
finite outputs and allocation guards pass. No original model is executed.

| Decode projection | Original mean, us | Planar mean, us | Latency change | Improving pairs |
|---|---:|---:|---:|---:|
| ssm-in | 195.242368 | 194.570728 | -0.344003% | 6/6 |
| attn-out | 78.609578 | 102.269926 | +30.098556% | 0/6 |
| vocabulary | 2970.850269 | 2898.801287 | -2.425197% | 6/6 |
| shared-gated | 18.161294 | 19.159398 | +5.495776% | 0/6 |

All six measured pairs and both warmups are retained in the
[bound result](../config/q2-decode-q8-planar-results.json). Their arithmetic
means describe this component only and do not replace the frozen model
reference. Startup packing and simultaneous original/planar residency remain
separate costs; vocabulary adds 675430400 bytes and takes 6.243517 ms to pack.

Retain vocabulary and the small SSM result as decode-only candidates; do not
apply planar loading globally or to prefill. Model integration and complete
decode qualification remain pending. Per the owner's new priority, new
experiments focus on prefill. A benefit exclusive to decode is preserved for
that phase, with no requirement that it also improve prefill.

CPU fixture, verify, admit, run and release all exit 0. All 36 artifacts
(817727 bytes) hash-verify at 20:34:04 UTC before release at 20:38:30, SHA
63ef8bc62ff61ad53c79df9ab764ccaa3193f32b5bd7ba5e1360071624212850.
Independent closure at 20:39:18 checks the registry, 18 retired identities
including the supervisor and owned groups, empty KFD, five original free
leases and seven unchanged model stats. Core and GLM receive closure; no
Q2 window or reservation remains. No remote cleanup or tuning occurs.
