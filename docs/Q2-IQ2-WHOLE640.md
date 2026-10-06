<!-- SPDX-License-Identifier: MIT -->

# Whole-row IQ2 producer and packing


## Integrated LDS chain prepared — 2026-10-06 UTC

The new `iq2-whole640-chain` provider integrates the measured sixteen-wave LDS
body only for the existing full2048 IQ2 mixed route. The C17 partition preserves
wide128 and ordinary64 work; the final1–16-row span keeps the original64-row
encoding. Down descriptors, slot layout, allocations, streams and count
downloads are unchanged. Other prefill widths keep the retained route.

Fused slots write directly into the existing scaled-half/inverse buffer and
leave their obsolete F32 gate slots unwritten. A new selective pack kernel
visits only ordinary slots; the unchanged Q2 down consumer sees the complete
packed buffer. These disjoint writes are required for correctness, not only
for performance. The partial F32 buffer cannot be passed to the original
whole-buffer pack while any fused span is present.

The [source manifest](../config/q2-iq2-whole640-chain-source.json) binds1034
provider files to the immutable1587 parent and qualified LDS donor. Compiler
checks establish164 unchanged parent ISA/resource bodies and an identical
LDS donor body; only selective packing is new device arithmetic. Host/device
fixture compilation passes. Shared provider formatting reports exit1,
including retained diagnostics and C17-style headers; no retained source is
reformatted. The new .157 host cohort passes39 Debug and39 ASan/UBSan checks, with six zero
command exits and all seven artifacts collected. Plan freezes265 fixture files
and eight manifests. GPU/model qualification still needs fresh admission.

The new guarded fixture compares mixed ordinary/fused work through packing
and both F16/F32 down consumers. It retains finite numerical disagreements,
checks expected-unwritten F32 slots, guards and immutable inputs, and verifies
the actual last timed rotation before reset. The one timing case uses2048
synthetic rows/64 experts, three weight banks beyond MALL and the complete
producer/pack/down wall time. It does not replace the original model prompt.
One original2048/TG128 candidate follows if device work is safe; saved model
controls and the full curve are reused without reruns. The fixed target is
still1685.777092 PP versus retained1587.893545, with no new model gain claimed.


The fixed comparison remains Q2 **1587.893545 PP / 25.12414406 TG** against
UD **1685.777092 PP / 24.34174251 TG**. The first eight-wave experiment has
completed its .157 component trial: both drafts are bit-exact to the parent,
but slower. Neither is selected by the model executor.

The [collected results](../config/q2-iq2-whole640-results.json) preserve all
63 timings, including warmups, and all 380 component artifacts. Mean wall
time over the five measured samples, in microseconds for gate/up plus packing:

| Live rows per expert | Current chain | Register draft | LDS draft | LDS time change |
|---:|---:|---:|---:|---:|
| 4 | 505.059 | 2705.759 | 618.025 | +22.367% |
| 8 | 518.792 | 2766.647 | 631.133 | +21.654% |
| 16 | 644.021 | 2840.109 | 763.476 | +18.548% |

These are new synthetic operator timings, not replacements for the fixed
model comparison. The 16-row case contains high observations in both the
parent and LDS samples; all remain included. No median substitution or
outlier removal is used. No model or saved model control was rerun.

All 104 candidate output pairs are bit-exact, including the actual buffers
from 21 timed samples. Device guards, written/finite values and immutable
inputs pass; an offline check independently reconstructs the original packing
for 9,381,676 saved values and inverse scales. These checks establish component
equivalence over the tested tensors, not independent model quality.

Keep the retained provider. Removing the global F32 intermediate is correct
but does not pay for this execution layout. Register spilling, block residency
and the ten sequential output groups are possible costs; this trial does not
isolate their contributions. The next local draft uses sixteen waves and five
128-column groups, retaining only 40 accumulator and 20 packing floats per
thread. It needs its own device evidence and has no production selector.

The sixteen-wave [device trial](../config/q2-iq2-whole640-wave16-results.json)
also completes with 104 bit-exact output pairs, 21 actual timed-buffer replays,
9,381,676 independently checked packing values/scales and three zero exits.
All 63 timing records and 380 component artifacts are retained. Mean times:

| Live rows per expert | Current chain | Register, 16 waves | LDS, 16 waves | LDS time change |
|---:|---:|---:|---:|---:|
| 4 | 502.546 | 1185.782 | 539.336 | +7.321% |
| 8 | 572.859 | 1203.190 | 543.308 | −5.159% |
| 16 | 641.944 | 1211.871 | 615.053 | −4.189% |

The LDS outcome is mixed. Its nominal gains at 8/16 rows include high parent
observations: 769.959 microseconds at 8 rows and 794.359/793.326 at 16 rows.
The candidate also has an 843.481-microsecond observation at 16 rows. None is
removed. The 4-row case is consistently slower. Keep this marginal candidate
available, but do not claim a demonstrated model improvement or combine these
component percentages with historical model gains.

The sixteen-wave [compiler record](../config/q2-iq2-whole640-wave16-static.json)
keeps all 164 parent bodies exact. Register/LDS drafts respectively use
20,608/61,568 shared bytes, 136/0 private bytes per thread, and 1,861/686
static instructions. The LDS allocation uses 169 VGPRs versus 241 in the
eight-wave version. These resource changes are not performance evidence.
The new fixture compiles; .157 host 38+38 checks pass and seven artifacts
collect. Its [separate plan](../config/q2-iq2-whole640-wave16-plan.json) freezes
254 files/four manifests and permits only the two new drafts against the
parent chain, without rerunning the previous drafts or any model control.
The new run finishes 18:52:53.499091 UTC; all artifacts collect before release
18:54:18.937825 UTC/SHA
`d4c60136edd5a9bb83cc16e35ed9d65692043424c6589cf6a03ea73be6d733cf`.

The next model candidate must preserve the current mixed routing map's
wide-128 and ordinary-tail-64 descriptors, partition eligible tails separately
from existing counts, and write the same scaled slot buffer. Packing must
cover only the ordinary rows so it cannot overwrite fused results or read
unwritten F32 cells. Keep the Q2 down consumer and its half-output lifetime
unchanged. Qualify that new mixed producer/packing/down chain before one
original exact-2048/TG128 model measurement against the saved references.
No executor integration, new provider, GPU plan or model admission exists yet.

The retained expert path writes 640 F32 gate/up values per routed row, then
reads that row to choose a dyadic scale and convert it to F16 for Q2 down.
Both drafts keep all 640 values within the producing block and emit the
scaled F16 values plus the original inverse scale directly. Each block handles
one existing expert tail with at most 16 padded rows. This is a routing shape
inside the original 2048-token prefill, not a different prompt length.

The full-row maximum, rounded weight scale, WMMA accumulation order,
`up * gate * sigmoid(gate)` order, F16 rounding and destination slot are
preserved in source. Numerical equality still requires the device test.
This differs from the already tested compact-layout experiment, which retained
the global F32 intermediate.

| Draft | Accumulator storage | LDS bytes | Private bytes/thread | Static instructions |
|---|---|---:|---:|---:|
| Register | Ten groups kept live | 11,392 | 1,380 | 3,913 |
| LDS | One group at a time; full row in shared memory | 52,352 | 0 | 931 |

These are compiler resource counts, not speedups. The register draft reuses
one staged activation across ten output groups but spills. The LDS draft
rereads activation stages for each group and uses more shared memory, which
can reduce block residency. It removes the F32 global write/read without a
new device allocation; its net effect must be timed.

The [static record](../config/q2-iq2-whole640-static.json) binds both formatted
drafts to the independently fetched MIT Gufo pin
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`
and the retained fixed-bounds provider. All 1028 provider files and 164 parent
instruction/operand/resource bodies remain exact. The first-party numerical
drafts derive from that provider's IQ2 kernel and LIE's whole-row scaled pack;
their SPDX license is MIT. No sibling project code or artifacts are imported.

The new [.157 fixture](../tests/q2_iq2_whole640.hip) compares the parent
gate/up plus packing with both drafts:

- 32 edge cases cover 1/2/7/8/9/15/16 live rows, ineligible 17-row tails,
  descriptors beginning at 0 or 128, and aligned or two-byte-offset outputs.
- Complete outputs and inverse scales are saved, with a scalar `frexp`/`ldexp`
  check of the parent packing, guards, unwritten/nonfinite detection and
  immutable inputs. Zero, tiny and signed inputs/scales are included.
- Three 64-expert timing cases use 4/8/16 live rows, three rotated gate/up
  weight banks (about 54 MiB per pair), two warmups and five alternating
  repeats. Synchronized monotonic wall time includes gate/up and packing.
- Each timed arm's actual final buffers are checked before another device
  arm; all 21 sample buffer sets are preserved and compared without rerunning
  the producer. Those checks and transfers are outside timing.

Finite differences are retained and do not suppress timing. Guard, unwritten,
nonfinite or device failures stop further device work. The fixture covers
selected tails, not the complete mixed routing map, Q2 down consumer, model
quality or model throughput. Original model controls are not rebuilt or rerun.

Local device assembly and host/device object compilation pass. The initial
missing generated-codebook include failure is preserved and corrected in
the CMake target. New files pass formatting; the shared provider format check
still exits 1 on inherited diagnostics, without rewriting retained source.
All preparation commands and earlier drafts remain under local
`evidence/q2-iq2-whole640-*`. The .157 host gate passes 38 Debug and 38
ASan/UBSan checks, with six zero exits and all seven artifacts collected.
The [frozen component plan](../config/q2-iq2-whole640-plan.json) binds 246
fixture files and four manifests. The component exits [0,0,0], completes at
18:33:33 UTC and is fully collected before release at 18:35:33 UTC, SHA
`fe9a91904ce626a363a9ce80e3389d0f06fd6de5006e7b83cb796048ff841967`.
No job, lease, reservation or remote cleanup remains.
