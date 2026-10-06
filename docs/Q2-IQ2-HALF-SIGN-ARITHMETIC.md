<!-- SPDX-License-Identifier: MIT -->

# IQ2 half-byte sign arithmetic

This private experiment starts from the retained SSM-bounds Q2 provider,
1585.308983 PP / 25.16079073 TG. The fixed original-counting point remains
exact2048 prompt /128 outputs /127 timed decode calls, capacity9216,
chunk2048, C1 greedy, MTP off, one warmup and three measurements with15-second
untimed pauses. Saved Q2 reference1443.672867 PP and UD1685.777092 PP remain
unchanged and are not rebuilt or rerun. Whole-curve parity remains unmet.

The existing four-lane IQ2 ownership publishes compact high half-bytes to LDS.
The candidate replaces the eight-byte sign-table lookup and mask with parity,
two full32-bit multiply/mask expressions and sign-bit XOR. It adds no table,
allocation, stream or callback. Runtime dispatch changes only unpacked IQ2
gate/up m640/k2560 with BN64/128; all other dimensions, decode, Q8, Q2 down,
attention, full640 scaling/packing and public ABI/state/metrics stay unchanged.
This differs from the earlier integer-magnitude WMMA-sign experiment: half
sign-bit XOR avoids its signed-byte negation. Historical trials stay preserved.

The host arithmetic audit checks all128 sign tags/1024 sign bytes against the
independently fetched original Qwen sign table. Device assembly retains all162
original bodies and resources exactly, adding two private bodies. Both remove
four static global64-bit loads and add11 total static instructions. BN64 keeps
104 VGPR/17536 LDS bytes; BN128 keeps150 VGPR/25728 LDS bytes and reduces SGPR38
to36. Neither spills. F16 FMA, WMMA and barrier counts are unchanged. These
facts do not establish runtime correctness or a speedup.

A new fixture exhausts32768 code/sign combinations and compares101 complete
float outputs including ragged n1/16/17/49/65/129/144/145/257, m1/65/640,
three weight rotations, uniform160/512 experts and captured layers0/3/22.
Seventy alternating operator timings include two warmups and five measured
repetitions. The synchronized monotonic wall timer is retained separately from
raw HIP event values; invalid HIP zeros cannot become a speed claim. Format
buffers and any differing full outputs are preserved. Finite numerical or
timing rejection still allows the original-model experiment; guard, unwritten,
nonfinite or device faults stop further GPU work.

The first fixture host/device compilation fails because the original sign table
is in the global namespace. Corrected retries exit0; both actual failures remain
in local evidence. An initial plan-freeze attempt before result collection also
fails; the collected retry succeeds without rerunning host tests.

On .157, host-r1 finishes2026-10-06T11:12:21.906973UTC with36/36 Debug and36/36
ASan/UBSan, six exits0 and seven collected artifacts. Freeze153 fixture hashes,
six manifests and1028 provider files. Fresh original lease/process/KFD/model-stat
checks pass11:11:23UTC against previous release6b3c8f27. Core explicitly reports
no own .157 work. GPU admission and component/model results are pending.

[Source](../config/q2-iq2-half-sign-arithmetic-source.json),
[static audit](../config/q2-iq2-half-sign-arithmetic-static.json),
[plan](../config/q2-iq2-half-sign-arithmetic-plan.json).
