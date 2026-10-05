<!-- SPDX-License-Identifier: MIT -->
# Compact IQ2 decode ownership across four lanes

One new candidate starts from the measured IQ2 raw-prefetch provider:
1505.152258 PP /25.15493858 TG. Original fixed Q2 remains1443.672867 and
UD1685.777092, using the same exact2048 input/tg128 tester. This experiment
changes the IQ2 gate/up producer's ownership, not expert routing geometry.
Source and fixtures are prepared; no GPU or model result is claimed yet.

Every lane retains its original eight-byte encoded group and two-byte scale
prefetch. Four-lane groups exchange those compressed words; each lane decodes
one of four eight-value portions for each original owner. The resulting64-bit
slices cover the original compact LDS cells exactly once. Scale publication
stays with the original owner, followed by the unchanged block barrier.
Codebook/sign bytes, scale rounding, WMMA accumulation and epilogues remain
unchanged. Q2 down, vector decode, dense kernels and attention are untouched.

This differs from the measured8/16-value local commit variants, which did not
redistribute ownership, and from the older Q2-down half-wave sharing probe.
It does not introduce another table, tensor allocation, stream or geometry.
Its source is derived from independently fetched official Gufo at
f783fedb9bea2ec7de941f6da4e02f4a4596b29e; no sibling DS4 code is imported.

## Static preparation

The1025-file source inventory changes one numerical file. All149 unrelated
kernel bodies remain identical; eight IQ2 bodies change. A separate ownership
enumeration verifies1024 unique slices over8192 shared bytes, with peer lanes
always in the same wave. This is not a GPU race or numerical proof.

| BN | Parent next-free VGPR | Candidate next-free VGPR | LDS bytes | Private bytes |
|---|---:|---:|---:|---:|
|16|78|86|11392|0|
|48|88|96|15488|0|
|64|96|104|17536|0|
|128|142|150|25728|0|

Both output specializations have these resources. Next-free register metadata
does not measure allocated occupancy. Eight static32-bit exchanges and four
64-bit stores replace the two128-bit compact stores per producer stage;
weight/codebook load totals and ordered arithmetic are retained. More register
pressure can erase any access benefit; only runtime measurement decides.
Production assembly, fixture host/device compilation and107 launcher guards
pass. The retained parent assembly is reused without rebuilding old controls.

## Frozen new-candidate qualification

The [plan](../config/q2-iq2-lane-commit-plan.json) freezes57 fixture files,
four manifests and the coordination helper. New .157 host Debug/ASan gates
pass27 tests each, six commands exit0 and seven artifacts verify. Local capsule preparation
already verifies every frozen fixture and all1025 provider files before SSH.
Fresh root handover confirms no root use/reservation of .157 after the saved
short48 release; the helper separately checks actual ownership and device state.

The component compares81 complete guarded outputs against the literal retained
parent in one new binary: BN16/48/64/128 with ragged15/17/129 token rows,
F32/packed outputs, then actual2048x640x2560 mixed128/64 dispatch for64/128/512
experts. Three weight rotations exceed32MiB. The42 timing records include two
warmups and five alternating measured cycles per arm and expert count.
Safe numerical failures save their arrays and preserve timings; unsafe guards
or unwritten required outputs stop subsequent device work.

One original model follows despite safe numerical or component timing rejection:
2048 prompt tokens,128 output tokens,127 timed decode calls, capacity9216,
chunk2048, greedy C1, MTP off, one warmup and three measurements,15-second
cooldowns outside timers. Compilation/loading are outside PP/TG. Historical
Q2, best-parent and UD files/binaries/results remain unchanged and are reused.
No qualified cohort, Q4 or full curve is rerun. Independent task quality and
whole-curve parity remain open.

[Source](../config/q2-iq2-lane-commit-source.json),
[patch](../experiments/q2-iq2-lane-commit.patch),
[static evidence](../config/q2-iq2-lane-commit-static.json),
[host evidence](../config/q2-iq2-lane-commit-host-results.json),
[local capsule check](../config/q2-iq2-lane-commit-staging-results.json).
