<!-- SPDX-License-Identifier: MIT -->
# IQ2 signed-codebook fusion

The owner defers Q4 and resumes Q2 from the retained raw-prefetch parent
PP1505.152258/TG25.15493858. This candidate replaces the two magnitude/sign
lookups and their masks/XOR with one lossless signed-high-byte table lookup.
No raw weight/header prefetch, scale expression, F16 rounding, compact LDS
layout, packed FMA, ordered K16 WMMA, routing, tail or SwiGLU operation changes.
Q2 down, decode, dense Q8, attention and scheduling remain unchanged.

The independently fetched official Gufo pin remains
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`. Original codebooks and notices
remain. No model payload is converted or copied. The isolated provider has
1026 verified files and changes only the IQ2 lookup and a generated include.
The scalar generator exhausts32768 entries/eight lanes, checking262144 half
operands against original magnitudes, independently completed sign parity
and IEEE half bits.

The production assembly changes exactly eight IQ2 specializations; the other
149 kernels match the saved parent without rebuilding that parent. Each
IQ2 body loses31 instructions (BN16/48/128) or32 (BN64), and static
`global_load_b64` count changes10 to6. VGPR, LDS and zero private scratch stay
the same. Packed F16 FMA and WMMA instruction counts match. These are static
counts, not dynamic bandwidth, measured occupancy or a model speedup.

The new table occupies262144 device bytes; the parent's unused2048-byte high
table is omitted from the production object, giving260096 additional constant
bytes in this translation unit. Random table traffic can offset fewer
instructions. The earlier Q8 table regression remains evidence, not an
assumption that this different lookup will win or fail.

The new fixture includes an exhaustive guarded device-table replay,81 complete
IQ2 gate/up output pairs and42 timing samples with three weight rotations
larger than32MiB. Its literal control is the measured raw-prefetch parent,
not a rerun of an old qualified component. A safe numerical/timing rejection
does not block the original model measurement. Guard/unwritten-output faults
stop device work. All errors and actual exits are retained.

The unchanged model tester uses exact2048/tg128,127 timed decode calls,
capacity9216/chunk2048, C1, greedy, MTP off, one warmup/three measurements and
15-second pauses outside timers. The fixed Q2 reference1443.672867 and
UD1685.777092 remain unchanged and are reused without relaunching. No full
context curve is admitted until the fixed-point gap is closed.

[Source](../config/q2-iq2-fused-grid-source.json),
[static evidence](../config/q2-iq2-fused-grid-static.json),
[plan](../config/q2-iq2-fused-grid-plan.json),
[staging](../config/q2-iq2-fused-grid-staging-results.json),
[host](../config/q2-iq2-fused-grid-host-results.json).
Ninety-five launch guards and25 Debug/25 ASan/UBSan tests pass. Host/device
fixture compilation passes. The initial fixture namespace qualification
error exits1 and is corrected only in the test wrapper; an initial local host
reader before collection also exits1. Neither is numerical or model evidence.

GPU execution still requires a preparation checkpoint and fresh admission
from the Q4 releasef1eaaaece9aab1f305d58d888a522e7ac505b9b4dd855434709d29b6f9d35424.
Core confirms no .157 use. No Q4, qualified comparator/component rerun,
cleanup, dependency installation, tuning or deployment is included.
