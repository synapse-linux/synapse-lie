<!-- SPDX-License-Identifier: MIT -->
# IQ2 pre-masked signs: bounded1KiB lookup

The owner defers Q4 and resumes Q2. The preceding large signed-grid lookup is
numerically exact but regresses full-model PP11.561850%; it remains preserved.
This distinct candidate starts from the measured best raw-prefetch provider
PP1505.152258/TG25.15493858. It retains the original2048-byte magnitude grid
and replaces the original sign lookup followed by bit7 masks with a128-entry,
1024-byte pre-masked sign table. It adds no heap buffer, stream or model-file
conversion. Raw prefetch, F16 scale/rounding, compact LDS, ordered WMMA,
routing/tails/SwiGLU, Q2 down, decode, Q8 and attention remain unchanged.

The scalar generator exhausts32768 sign/code combinations/eight lanes:
262144 independent parity/IEEE-half checks pass. Device and host fixture
compilation passes; inherited enumeration-switch warnings remain visible.
All97 launch guards pass. The isolated1026-file provider changes only the
IQ2 sign lookup and a generated include; the original notices and tables stay.
The official independently fetched Gufo pin remains
f783fedb9bea2ec7de941f6da4e02f4a4596b29e. No sibling workspace source/artifact
is imported; DS4 remains separately owned.

Local production assembly preserves149 unrelated bodies and changes exactly
eight IQ2 bodies. Each loses14 static instructions; global64-bit loads remain
10. VGPR/LDS and zero private storage remain unchanged, as do packed F16 FMA
and WMMA counts. The constant tables are2048 bytes magnitude plus1024 bytes
signs. These static facts do not establish dynamic cache behavior or speedup.

A new fixture exhausts all32768 combined device encodings with guarded full
readback, checks81 complete IQ2 gate/up output pairs and records42 rotated
weight timings. Its literal control is the saved best parent's kernel inside
this new fixture; no old qualified component cohort is rerun. Safe numerical
or timing rejection does not block the new full-model measurement. Unwritten
outputs or guard faults stop device work. Full floating arrays are checked
and their hashes logged; only the two guarded format arrays are saved by this
inherited fixture. Failures and actual exits remain preserved.

The original tester remains exact2048/tg128,127 timed decode calls,
capacity9216/chunk2048,C1,greedy,MTP off,one warmup/three measurements and
15-second pauses outside timers. Fixed Q2 PP1443.672867, saved best1505.152258
and fixed UD1685.777092 are reused without compilation or rerunning.
The frozen plan binds44 fixtures/four manifests. A preparation checkpoint and
fresh lease admission from release d0437a91 remain required before GPU work.
Q4, old controls/cohorts, full context curves, cleanup, tuning, dependency
installation and deployment are outside this bounded experiment.

[Source](../config/q2-iq2-sign-mask-source.json),
[static evidence](../config/q2-iq2-sign-mask-static.json),
[plan](../config/q2-iq2-sign-mask-plan.json),
[local staging](../config/q2-iq2-sign-mask-staging-results.json).

The new .157 host gate passes25/25 Debug and25/25 ASan/UBSan checks;
all six commands exit0 and seven artifacts verify. Source capsule44 fixtures
and1020 CPU-default provider files match, with no GPU/model access.
[Host evidence](../config/q2-iq2-sign-mask-host-results.json).
