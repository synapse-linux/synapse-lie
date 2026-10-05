<!-- SPDX-License-Identifier: MIT -->
# Unread activation stores in scaled-Q2 down

This new candidate starts from the measured IQ2 live-stage composition,
1511.097261 PP /25.14684805 TG. The active scaled-Q2 down matrix loop already
skips whole16-row fragments beyond an expert bucket, but its activation loader
still stores zero tiles there in every K stage. The patch computes slot
eligibility once and omits those stores at BN48/64. BN16, padding inside the
final live fragment, original640/768 K-tail handling, affine weights, ordered
WMMA, inverse scaling and F32 scatter remain unchanged.

Source derives from independently fetched official Gufo at
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, keeping its notices. The isolated
[source inventory](../config/q2-down-live-stage-source.json) has1025 files,
with one changed. A literal parent kernel remains inside the new component
fixture. This is a new down-consumer experiment; the old IQ2 component is not
used as its GPU qualification.

Local production compilation changes only the two scaled-Q2 down bodies;
all155 others remain exact. Both bodies retain their VGPR, SGPR and LDS
allocation, original arithmetic/barrier counts and zero private bytes.
[Static report](../config/q2-down-live-stage-static.json). Those static facts
do not prove a GPU speedup or race freedom.

The new component checks477 whole-output pairs over three rotated weight sets:
BN16/48/64, token counts around16/32/48/64/96 boundaries, partial output rows,
and the original2048x2560x640 top10 shape with64/128/512 experts at both wide
tile sizes. Guard bytes, every required output, finite values and original
input/weight immutability are checked. It retains changed arrays on numerical
failure; a damaged guard or unwritten output stops further device work.

The six timed distributions alternate literal-parent and candidate calls in
one new binary, with two warmups and five measurements, three rotated weights
per sample. Rotation sizes are123,863,040 /247,726,080 /990,904,320 bytes.
Preparation/uploads are outside that component timer. The full model includes
all original inference preparation and runs even after a safe numerical or
component-timing rejection.

The [plan](../config/q2-down-live-stage-plan.json) freezes63 fixture files,
five manifests and one new original-model comparison: exact2048 input,
chunk2048, capacity9216, tg128 with127 timed decode calls, C1, greedy, MTP off,
one warmup and three measurements. Fixed Q2 1443.672867 /25.09595499,
UD1685.777092 /24.34174251 and parent1511.097261 /25.14684805 are saved evidence;
none is rebuilt or rerun. New launcher115 guards and capsule checks pass.
The .157 host cohort passes27/27 Debug and27/27 ASan/UBSan; all six commands
exit zero and seven collected artifacts verify.
[Host receipt](../config/q2-down-live-stage-host-results.json).

At preparation, GPU numerics/performance remain unproven. Model outputs,
complete samples and a comparison graph are required. Full PP/TG curve parity
and independent task quality remain open. GPU work needs fresh coordinated
admission on .157; no Q4, full curve, cleanup, dependency installation, tuning
or deployment is part of this experiment. Core ABI, state and metrics are unchanged.
