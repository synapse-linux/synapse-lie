<!-- SPDX-License-Identifier: MIT -->
# Compact shared memory for the fused SSM projection

The completed candidate measures **1555.078658 prefill tokens/s and
25.13403225 decode calls/s** on the original exact2048/tg128 model. Prefill is
1.906904% below retained1585.308983 and1.591421% below its construction
parent1580.226725. Keep **ssm-fixed-bounds1585.308983 /25.16079073** as the
performance base. Fixed UD1685.777092 still needs another6.337447% PP from that
retained candidate; the complete-curve goal remains open.

All30 complete component pairs and60 sampled FP64 checks pass. Both21-file
model comparisons, against construction1580 and retained1585, are byte-exact,
as are all nine within-arm replays. The inherited F16 task-quality gap remains;
this result adds no independent model-quality or production acceptance.

The paired component is slower10.364322%:4928.835869 to5439.676285us. HIP reports
49152→32768 shared bytes,222→207 registers, zero private bytes and a computed
maximum of1→2 blocks per multiprocessor. These limits do not measure active
occupancy. Smaller shared storage does not compensate for the changed K-stage
schedule in this experiment; relative contributions from synchronization,
address permutation and load scheduling are not isolated by hardware counters.

## Complete component samples

Projection plus boundary convolution, M16384/N2048/K2560; each sample rotates
three weight sets totaling133693440 bytes. Two warmups and five measured pairs
alternate order. Allocation, copies and validation are excluded.

| Session | Literal reference us | Compact LDS us |
| --- | ---: | ---: |
| Warmup 1 | 4870.56128184 | 5501.99953715 |
| Warmup 2 | 4932.86673228 | 5392.09556580 |
| Measured 1 | 4946.87938690 | 5439.67628479 |
| Measured 2 | 4924.40923055 | 5352.58483887 |
| Measured 3 | 4928.83586884 | 5440.83658854 |
| Measured 4 | 4940.66206614 | 5352.41190592 |
| Measured 5 | 4921.10220591 | 5465.43502808 |

[All component samples](figures/q2-ssm-compact-lds-component.csv),
[chart](figures/q2-ssm-compact-lds-component.png),
[component report](../config/q2-ssm-compact-lds-component-results.json).

## Original model: unchanged input, timers and comparisons

Only the new candidate is rebuilt and run. All four comparator arms are saved
measurements, without rerun. Input SHA256 remains
`75343e606f5b815fe01f69ddc6ce50a997e2de96d8a20304a82a7f24f1180b35`.
Capacity9216/chunk2048, greedy C1, MTP off,128 output tokens/127 timed decode
calls, one warmup and three measurements remain unchanged. Cooldown15s stays
outside PP/TG timers. PP means prefill tokens/s; TG means decode calls/s.

| Session: PP / TG | Fixed Q2 | Construction1580 | Retained1585 | Compact LDS | Fixed UD |
| --- | ---: | ---: | ---: | ---: | ---: |
| Warmup | 1438.259006 / 25.08847266 | 1578.810990 / 25.08217355 | 1586.508538 / 25.13300114 | 1558.006146 / 25.14053762 | 1689.043527 / 24.34239962 |
| Measured 1 | 1443.398207 / 25.10565683 | 1580.873846 / 25.11185031 | 1586.342395 / 25.17262901 | 1555.719196 / 25.13403225 | 1686.364042 / 24.34621613 |
| Measured 2 | 1443.672867 / 25.08698337 | 1580.226725 / 25.09349758 | 1584.079076 / 25.16079073 | 1554.541999 / 25.14856702 | 1685.777092 / 24.34174251 |
| Measured 3 | 1443.841794 / 25.09595499 | 1579.621125 / 25.10411864 | 1585.308983 / 25.15297051 | 1555.078658 / 25.11422122 | 1685.400011 / 24.15102104 |
| Median measured | 1443.672867 / 25.09595499 | 1580.226725 / 25.10411864 | 1585.308983 / 25.16079073 | 1555.078658 / 25.13403225 | 1685.777092 / 24.34174251 |

Elapsed seconds for the same new samples (historical elapsed times are also
preserved in the complete20-row CSV):

| Session | Prefill seconds | Decode seconds |
| --- | ---: | ---: |
| Warmup | 1.314500591 | 5.051602393 |
| Measured 1 | 1.316432943 | 5.052909884 |
| Measured 2 | 1.317429829 | 5.049989524 |
| Measured 3 | 1.316975183 | 5.056895808 |

[Every model sample](figures/q2-ssm-compact-lds-model-wrapped.csv),
[chart](figures/q2-ssm-compact-lds-model-wrapped.png),
[model report](../config/q2-ssm-compact-lds-model-results.json).

Compilation154.254658s and loading13.72569846s are excluded from PP/TG.
Resident43156012544 bytes, deferred scratch7946240 and session376777748
remain unchanged. Scalar decode is not changed by this prefill kernel; the
observed -0.106350% TG relative to saved1585 is not assigned a causal mechanism.
Model-campaign temperature peaks are80.375C CPU and71C GPU.

## Closure and next action

Seven new runtime commands exit0 and30 new artifacts verify. Earlier host30
Debug/30 ASan/UBSan evidence is reused only after exact102-fixture and archive
verification; its six commands/seven artifacts stay separately identified.
The1027 source files, fifteen manifests/helper and six exports verify.
The model axis labels were shortened after visual review; the first exports
and first audit remain under the local preparation's plot-review-r1 directory.
All measurements remain exact. Both final PNGs are reviewed.

Admission00:24:17.868844UTC follows fresh Core closure/non-use and previous
releasea94c8b81, from checkpoint5dbb2ad. Both new cohorts are terminal and
collected before release2026-10-06T00:30:45.862213UTC. Release retires1219
recorded identities/973 groups, leaves KFD empty and verifies four free
unchanged original leases/seven unchanged model stat tuples. Canonical,
main and remote mirrors agree; Core receives closure. No Q2 job, build,
waiter, reservation, automatic restart or cleanup remains.

Preserve this measured regression. Reducing LDS through BK1, including the
previous alternating-buffer attempt, has not improved the retained prefill.
Do not compose either variant into1585 based on theoretical occupancy.
Further work should investigate data movement or producer/consumer costs
while preserving the measured BK2 path. The retained profile is timing
attribution from1571, not current1585 hardware-counter evidence; that gap
must be kept explicit when selecting a further optimization. No new profile,
full curve, Q4 or independent task-quality run is claimed here.

[Final audit](../config/q2-ssm-compact-lds-final-audit.json),
[disposition](../config/q2-ssm-compact-lds-disposition.json),
[release](../config/q2-ssm-compact-lds-window-release.json).

## Preserved preparation record

The following records source preparation and then-pending runtime states.
The completed measurements above supersede their GPU-pending statements.

The previously prepared source is now bound to its first GPU campaign after
the compressed-cache result. Retained performance remains1585.308983 PP /
25.16079073 TG; the literal construction parent1580 and fixed Q2/UD are also
read from saved evidence. No performance reference is rebuilt or rerun.
The current102 fixture files are byte-identical to the completed .157
host30+30 capsule, so that qualification is reused. Fifteen manifests and a
fresh window helper bind the new component/model runs. Two locally staged
capsules verify1027 source files and every fixture with SSH intercepted.
The additional1585 comparison verifies its own original90-fixture archive,
not the newer campaign's fixture set; saved samples and binary stay exact.
Three corrupted-reference identity cases are rejected. GPU results remain
pending. [Plan](../config/q2-ssm-compact-lds-plan.json),
[reused host](../config/q2-ssm-compact-lds-host-results.json),
[staging](../config/q2-ssm-compact-lds-staging.json).

The sections below preserve the original source preparation and its then-current
ownership status. The follow-up launcher is now applied and qualified.

This candidate changes only the fused SSM projection in the retained
1580.226725 PP /25.10411864 TG provider. It has local source, integer-layout
and compilation evidence, with no GPU numerical or timing result. The saved
1571 [profile](Q2-CURRENT-BEST-PROFILE.md) attributes160.217893ms over36 calls
to this projection. That profile identifies a useful target; it is not a fresh
1580 trace or a predicted saving.

The original BK2 stage holds two K32 blocks for256 output rows and128 tokens,
requiring49152 LDS bytes. Switching to BK1 halves staging to24576 bytes, but
the fused convolution still needs a32-token transpose for each of eight waves.
Its original36-float stride requires36864 bytes. The candidate replaces the
four-float padding with an XOR row permutation:

```
index(token, row) = token * 32 + (row ^ ((token & 7) << 2))
```

Each wave now uses1024 floats, so the complete transpose fits32768 bytes.
The low two row bits stay unchanged, preserving aligned contiguous float4
loads. Projection stores and all three earlier convolution reads use the
same mapping. The existing block grid,32-token convolution windows, history
boundary kernel, output masks and convolution arithmetic remain unchanged.
No allocation, stream or launch is added, and scalar decode is unaffected.

Integer enumeration checks1024 unique producer stores and3808 scalar read
coordinates per wave, including every current/history float4 component.
A model with32 banks of four bytes gives the same store-bank multiplicity as
the padded layout over32 store cases. This models store addresses only; it
does not measure hardware bank conflicts or establish vector-read behavior.
Both BK schedules visit the same160 K16 fragments in the same order.

## Compilation and tradeoffs

| Property | Saved parent | Compact LDS |
| --- | ---: | ---: |
| Static instructions | 4027 | 4120 |
| Shared bytes/block | 49152 | 32768 |
| Compiler-reported VGPRs | 222 | 207 |
| Descriptor VGPR reservation | 241 | 207 |
| Scratch bytes/thread | 0 | 0 |
| Compiler occupancy field | 4 | 7 |
| Static WMMA opcodes | 64 | 32 |
| Source K stages | 40 | 80 |
| Source block barriers in K loop | 80 | 160 |

Lower LDS/register use could permit more concurrent work, but the shorter K
stage doubles synchronization and changes load scheduling. Static WMMA totals
reflect a different loop body, not fewer matrix products. No throughput gain
or measured residency follows from these compilation numbers.

The complete1027-file inventory and patch are retained. Only `kernels.hip.cpp`
changes, and161 other kernels retain exact instructions, operands and resource
metadata. The unchanged saved parent assembly is reused. The literal SSM
control still matches the current parent, and the independent FP64 formula
changes only its event name.

## Prepared qualification

The separate fixture retains1024/1025/1057/2048/2049 tokens,30 complete
projection/convolution pairs and60 sampled FP64 checks of24 outputs each.
Original RMS/scaled-maximum limits remain0.002. Fourteen timing records cover
only2048, with two warmups/five measured repetitions per arm and three distinct
weight sets totaling133,693,440 bytes. Timings include projection and unchanged
boundary convolution; allocation, preparation and readback remain outside.
Safe numerical rejection retains timings; guard/write/runtime failures stop.

Two new metadata records will read HIP function attributes and its computed
maximum active blocks for each arm on .157. These API limits are theoretical,
not measured active blocks. Host and gfx1151 device syntax pass locally,
including those calls. Zero GPU checks or resource queries have executed.
Launcher wiring and original-model qualification remain pending after actual
Core-19 CPU closure and fresh coordinated ownership.

The frozen row-group campaign stays first and unchanged:88 fixtures, five
manifests and its original window helper. This candidate starts from saved1580
with row-group1 and does not silently compose the unmeasured fixed-M/K variants.
The fixed Q2/UD comparison, full-curve gate and deferred Q4 scope remain intact.

[Source and integer proof](../config/q2-ssm-compact-lds-source.json),
[assembly and fixture contract](../config/q2-ssm-compact-lds-static.json),
[fixture](../tests/q2_ssm_compact_lds.hip).
Actual local command exits are retained under
`evidence/q2-ssm-compact-lds-preparation/`.
