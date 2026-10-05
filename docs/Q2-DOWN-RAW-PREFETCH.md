<!-- SPDX-License-Identifier: MIT -->
# Deferred extraction in scaled Q2 down prefill

One new candidate starts from the retained IQ2 raw-prefetch composition at
1505.152258 PP /25.15493858 TG. It changes the three scaled Q2_K down prefill
specializations only. The original 32 code bytes, affine scale bits and half
headers are fetched at the same frequency; bitplane shifts and masks move from
fetch into LDS commit. Affine arithmetic, half construction, K16 WMMA order,
inverse row scale and final outputs remain unchanged. No new cache, allocation,
table, stream, public ABI, state or metrics contract is introduced.

The saved profile places 188.348921 milliseconds in this projection across
48 calls on the fixed model point. That profile identifies a target; it is
neither a current candidate timing nor proof of a speedup.

Local matched assembly reuses the saved parent without a rebuild. It verifies
157 bodies: three scaled Q2 bodies change and the remaining 154 are exact,
including the retained IQ2 raw-prefetch bodies. Private scratch stays zero and
LDS is unchanged:

| Token tile | Parent / new instructions | Parent / new next-free VGPR | LDS bytes |
| ---: | ---: | ---: | ---: |
| 16 | 1058 /1028 |86 /85 |14464 |
| 48 | 2551 /2529 |96 /95 |18560 |
| 64 | 3225 /3201 |104 /103 |20608 |

Static reductions remove duplicated initial/loop extraction bodies; source
bytes and dynamic fetch frequency are unchanged. They establish no occupancy,
bandwidth or inference gain. The first static stdout summary incorrectly says
eight changed bodies, while all checks and the saved report correctly identify
three. Its original stdout is retained; the display-only correction does not
rerun compilation or rewrite the report.

The new fixture compares 117 complete guarded output pairs against a literal
copy of the retained parent. Cases cover BN16/48/64, token counts1/15/17/129,
output row tail129 and K128/256/640, then original-shape2048x2560x640/top10
with64/128/512 active experts. It checks original inputs unchanged after each
case, all required outputs finite/written, and output guard bytes. Upload,
poison, launch and readback share one nonblocking stream.

Three distinct original-Q2 weight rotations occupy123863040 /247726080 /
990904320 bytes, above32MiB MALL. Forty-two alternating observations include
two warmups and five measured samples per arm/shape; device event timers exclude
uploads, maps and allocation. They measure down projection only, not whole MoE
or model throughput. Numeric failures preserve arrays and timing. Guard/runtime
faults stop device work; any safe numerical/timing verdict still proceeds to
the original model performance measurement requested by the owner.

The comparison remains original exact2048/tg128,127 timed decode calls,
capacity9216/chunk2048,MTP off,one warmup and three measured sessions with
15-second waits outside timers. Fixed Q2 PP1443.672867 /TG25.09595499, fixed UD
PP1685.777092 /TG24.34174251 and saved parent PP1505.152258 /TG25.15493858
are reused without rerunning their builds, cohorts or inference. No full context
curve, cleanup, tuning, deployment or dependency installation is admitted.

Local production/fixture device compilation, host syntax,89 launch guards and
new-file formatting pass. The shared formatter retains exit1 for nine unchanged
inherited files.1024 packed bitplane checks match independent byte extraction.
All38 fixture hashes,four manifest hashes and1025 provider files are frozen.
A local staging preflight verifies the complete component capsule and stops
before SSH, with zero network calls or GPU work. New `.157` host qualification passes25/25 Debug and25/25 ASan/UBSan,
with six zero command exits,seven artifacts and all38 frozen files verified.
These tests access neither models nor GPU. Fresh coordinated admission is
still required before the component build/run or original model.

At this preparation checkpoint no new GPU component or original model has run.
Compilation and host checks are not numerical acceptance or performance evidence.
The existing IQ2 raw-prefetch composition remains the measured base.

[Frozen plan](../config/q2-down-raw-prefetch-plan.json),
[source inventory](../config/q2-down-raw-prefetch-source.json),
[static evidence](../config/q2-down-raw-prefetch-static.json),
[staging evidence](../config/q2-down-raw-prefetch-staging-results.json),
[patch](../experiments/q2-down-raw-prefetch.patch),
[literal parent](../experiments/q2-down-raw-prefetch-control.inc),
[new fixture](../tests/q2_down_raw_prefetch.hip).
