<!-- SPDX-License-Identifier: MIT -->
# Fixed bounds for the active Q2 expert down projection

The new private candidate starts from retained **1587.893545 PP /25.12414406 TG**.
Fixed UD remains **1685.777092 PP /24.34174251 TG**. Runtime results are pending.

The actual half-output route has m2560/k640. Its 20 blocks each own 128 complete
output rows, and ten K64 stages cover the input exactly. Specialize these bounds
and row strides, remove their row-tail checks, and select the aligned output
path only when the output address is divisible by 16. All other shapes or
alignment retain the original body. Ragged token/expert bounds, encoded weight
bytes, affine FMA/half palette, WMMA order, inverse-scale multiplication and
half-output rounding remain unchanged. No extra allocation or executor lifetime
change is introduced.

| Token tile | Parent / candidate instructions | Parent / candidate VGPR | LDS bytes |
| ---: | ---: | ---: | ---: |
|16|1254 /971|85 /85|14464|
|48|2641 /1729|96 /97|18560|
|64|3350 /2152|104 /105|20608|

All 164 parent bodies and the three standalone draft bodies match the integrated
candidate instruction-for-instruction and resource-for-resource, with zero
spills. Static instruction reduction is not a measured throughput increase.

The new component covers 44 cases/132 complete guarded output pairs, including
ragged rows, output widths 1/65/2560, token tiles 16/48/64, four-byte-aligned
outputs, uniform routing and saved real-layer 0/3/22 counts. Five complete
post-timing buffers must equal their own initial replay. Timings alternate the
literal parent and new selector over three weight rotations beyond 32 MiB MALL;
two warmups and five measurements use synchronized monotonic wall time. Raw HIP
event values and validity are retained separately. Numerical finite differences
retain their full arrays and do not suppress the original-model performance test.
Device/guard/unwritten/nonfinite failures prevent further GPU work.

Host 37 Debug and 37 ASan/UBSan checks pass on .157. The frozen plan binds190
fixtures, six manifests and1029 provider files. One original2048/tg128 model
uses the fixed input, capacity9216, chunk2048, C1 greedy, MTP off, one warmup,
three measured sessions,127 timed decode calls and outside-timer pauses. Saved
Q2/UD/parents are reused without rebuilding/rerunning; no Q4/full curve.

A local registration-preparation script first exited1 on a stale text anchor
before any file mutation or remote action; that failure is preserved. The
corrected preparation passes syntax and actual .157 host checks. It is not a
numerical or GPU failure.

[Source](../config/q2-down-fixed-bounds-source.json),
[static comparison](../config/q2-down-fixed-bounds-static.json),
[plan](../config/q2-down-fixed-bounds-plan.json).
