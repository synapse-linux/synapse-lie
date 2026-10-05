<!-- SPDX-License-Identifier: MIT -->
# Scaled Q2 down output-row reuse

One new candidate starts from the retained nominal 1509.852296 PP parent.
It changes only the scaled Q2 down BN48 dispatch from BM128 to BM256. The
generic numerical template is unchanged; each wave now handles two output
fragments that share the same activation stage. At M2560 the output grid
shrinks from 20 to 10 blocks. Useful matrix operations and weight decoding
are not eliminated. Larger register and LDS demands may outweigh reuse.

Original encoded Q2_K weights, the scaled-half activation plane, inverse row
scale, ordered K16 WMMA updates, F32 scatter and logical640/stored768 tail are
unchanged. BN16/64 down, IQ2 gate/up, dense, attention and scalar decode retain
their original dispatches. Earlier scaled-tile experiments changed token width
BN while retaining BM128; this output-row change is a distinct mechanism.
The completed IQ2 wide-pair regression is a different kernel and is excluded
from this candidate's lineage.

Only `q2_scaled_input.inc` changes among 1025 provider files. Source derives
from independently fetched official Gufo at
f783fedb9bea2ec7de941f6da4e02f4a4596b29e and the recorded LIE patches. No
sibling DS4 source or artifact is imported. The literal measured parent
template is compiled into the new fixture as its same-process control; old
qualified model binaries and cohorts are not rebuilt or rerun.

## Static comparison

Production assembly replaces one specialization and preserves 156 bodies
exactly. The retained parent's assembly is reused without compilation.

| Resource | Parent BM128 | Candidate BM256 |
| --- | ---: | ---: |
| Output rows per block | 128 | 256 |
| Next-free VGPR | 96 | 169 |
| LDS bytes | 18560 | 30848 |
| Private bytes | 0 | 0 |
| Static block barriers | 8 | 8 |
| Static WMMA instructions per body | 12 | 24 |

The candidate performs twice the output work per block. Static instruction
counts do not measure executed traffic or active-wave occupancy. Production
assembly, fixture host/device compilation and all 111 launcher guards pass;
GPU numerical and performance results are still pending at preparation.

The fresh .157 host cohort passes27 Debug and27 ASan/UBSan checks. All six
commands exit zero and seven artifacts verify. Local staging binds61 frozen
fixture files and all1025 provider files. Root confirms fresh non-use after
release73a6cae4; a source checkpoint and own admission are still required
before any remote HIP build or GPU execution.

## Frozen experiment

The new fixture calls the production `RoutedQ2ScaledGemm` dispatcher, covering
135 complete guarded output pairs: n1/17/47/48/49/129 crossed with
m1/127/129/255/256/257/2560 at K640, plus the actual2048x2560x640 down shape
with top10 and64/128/512 experts, each across three weight rotations. The
rotations exceed32MiB for every timed shape. Two warmups and five alternating
measurements retain42 timing records. Guards and required-output coverage
must pass; safe numerical or timing rejection still permits the model test.

One original exact2048/tg128 model follows. Capacity9216, chunk2048, greedy
C1, MTP off, one warmup/three measured sessions and127 timed decode calls stay
fixed. Compilation, loading and15-second cooldowns remain outside PP/TG.
Fixed Q2 1443.672867, retained parent1509.852296 and fixed UD1685.777092
results are reused. No Q4, full curve, cleanup, tuning or dependency change.
Independent task quality and full PP/TG parity remain open.

[Source](../config/q2-down-output-reuse-source.json),
[patch](../experiments/q2-down-output-reuse.patch),
[static comparison](../config/q2-down-output-reuse-static.json),
[frozen plan](../config/q2-down-output-reuse-plan.json),
[host results](../config/q2-down-output-reuse-host-results.json),
[local staging](../config/q2-down-output-reuse-staging-results.json),
[original opportunity](../config/q2-down-output-reuse-opportunity.json).
