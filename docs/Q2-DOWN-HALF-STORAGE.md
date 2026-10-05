<!-- SPDX-License-Identifier: MIT -->
# Compact Q2 expert-output storage

This experiment starts from the retained1511.097261 PP /25.14684805 TG
provider. It stores the inverse-scaled Q2 down result as F16 and consumes it
directly in the ordered F32 MoE/deferred-normalization kernel. At the fixed
2048-token/top10/hidden2560 shape, the logical output shrinks from200MiB to100MiB.
The existing allocation keeps its full capacity. These are logical bytes,
not measured DRAM traffic, memory-peak savings or an established speedup.

The F16 store introduces one real rounding boundary. Original encoded weights,
activation scaling, WMMA accumulation, inverse-scale multiplication and expert
sum order are retained. Guarded output checks distinguish exact implementation
of that rounding from agreement with the F32 parent and independent model
quality. The parent remains available and selected until model evidence exists.

The new dispatch is limited to the Q2 wide2048 chain with HC4/rank320 and the
immediate block-output consumer. The existing F16-pending lifetime owns the
buffer; a separate Q2 marker selects the new consumer and is cleared when
consumed or scratch is replaced. Other shapes and scalar decode retain their
original dispatch. There are no new allocations, streams, model conversions,
core ABI/state/metrics changes or production deployment.

The isolated [source](../config/q2-down-half-storage-source.json) derives from
independently fetched official Gufo pin
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, retaining its notices. It has1026
files: five existing files change and one numerical include is added. The
generator derives the new bodies from the literal parent, rather than
reimplementing its arithmetic. All157 original production kernels retain exact
instructions, operands and resources after removing only comments and local
function-label numbering. Four specializations are added with zero private
bytes. [Static report](../config/q2-down-half-storage-static.json).

The component covers315 down-output comparisons across ragged token/output
tails, BN16/48/64 and three rotated weight sets. An independent integer
binary32-to-binary16 RN-even conversion checks every stored output. Another99
comparisons run the original consumer on expanded rounded values against the
new half consumer, checking residuals, normalization scales and half inputs.
Parent differences remain recorded separately. Guard corruption or unwritten
required outputs stop further device work; safe numerical rejection retains
timing and does not suppress the new original-model performance test.

There are168 planned timing observations: down alone and down plus combine,
BN48/64,64/128/512 experts, two arms, two warmups and five measured samples.
Each sample rotates three weight sets exceeding32MiB. Input preparation,
uploads and residual reset are outside component timers; the full model
includes all original inference work.

The [v2 plan](../config/q2-down-half-storage-plan-v2.json) freezes64 fixture
files and four manifests. Original exact2048/tg128/C1/greedy/MTP-off input,
capacity9216/chunk2048, one warmup and three measured sessions stay unchanged.
Fixed Q2 1443.672867, parent1511.097261 and UD1685.777092 use saved evidence;
none is rebuilt or rerun. Full context/concurrency curves and Q4 remain deferred.

The first local staging exits2 because an inherited launcher count expected
1025 source files instead of the new1026. It refuses before SSH; source bytes
and manifests are unchanged. The corrected capsule verifies all64 fixtures
and1026 provider files;117 launcher guards pass. The original plan/failure
are retained. Separate .157 host checks pass27 Debug and27 ASan/UBSan tests,
with six zero exits and seven verified artifacts.
[Host receipt](../config/q2-down-half-storage-host-results.json).

GPU rounding, complete-model speed and independent quality remain unproven
at preparation. Fresh coordinated admission is required before remote HIP
build/run. No lease or reservation is inherited from the previous release.
