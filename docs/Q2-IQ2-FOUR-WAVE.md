<!-- SPDX-License-Identifier: MIT -->
# IQ2 gate/up in four waves

This candidate starts from retained1585.308983 PP /25.16079073 TG and changes
only nonpacked IQ2 BN64. Four wave32 groups compute both gate and up, sharing
each activation fragment between their two accumulators. BM128,64 logical
output rows, the grid,17536 LDS bytes and all runtime allocations stay fixed.
The previous rejected BM256 wide-pair trial enlarged both the output tile and
LDS; this candidate does neither.

The wave-local epilogue evaluates the original explicitly rounded F32 product
and SwiGLU value, then transposes final values in four disjoint scratch planes.
K-stage block barriers remain. Eight epilogue block barriers disappear from
the compiled body. Global activation reads per block remain unchanged; only
the sharing of LDS activation reads changes. It introduces no expert or KV cache.

Static comparison with the saved parent assembly finds161 other production
kernel bodies instruction/operand/resource exact, after normalizing the added
private template argument. The affected body uses193 instead of104 VGPRs,
with zero private scratch and unchanged LDS. Its instruction count1351→2138
is per-wave code with twice the row work; it is not a dynamic instruction
count or a speedup. Fewer waves with more registers do not prove occupancy.

The symbolic ownership audit enumerates256 weight-group owners,1024 compact
eight-byte writes,256 scale owners,512 activation chunks and8192 accumulator
owners; both layouts agree. It checks63 ragged output shapes and disjoint
epilogue scratch. The fixture compares96 complete output pairs, including
unaligned rows, mixed128/64 routing, untouched BN16/48/128 and packedBN64.
Three mixed cases rotate weights beyond32MiB and retain42 timings. These are
planned GPU counts, not completed results at preparation time.

Local production assembly, fixture host/device syntax, source reconstruction
and146 launcher guards pass. Fresh .157 host31 Debug+31 ASan/UBSan passes at
2026-10-06T01:55:56UTC, six successful commands/seven verified artifacts.
The plan binds107 fixtures,nine manifests and1027 provider files. Both staged
capsules verify without executing SSH. New GPU admission is required.

The original exact2048/tg128 benchmark is unchanged:127 timed decode calls,
capacity9216/chunk2048,greedy C1,MTP off,one warmup and three measurements,
15-second pauses outside timers. Saved fixedQ21443.672867,retained1585.308983
and fixedUD1685.777092 are reused without rebuilding or rerunning controls.
Safe numerical or timing rejection still permits the requested model test;
runtime/guard exit2 stops dependent device work. Full curve and Q4 remain deferred.

## Priority relative to the remaining gap

The fixed point needs approximately77ms less prefill time, or6.337447% more
throughput. The separately saved1571 profile attributes103.691949ms to IQ2BN64,
135.807810ms to IQ2BN128 and161.558060ms to Q2 down. Those are diagnostic costs
on the older profiled executable, not fresh timings for retained1585.
The current variant addresses the first of these. Improvements there must be
measured before extending the layout to a wider tile with higher register cost.
Q2-down data movement and repeated decode work are the next expert priorities;
previous negative shuffle/palette/output-tile experiments remain evidence.

Ten percent less time across all three expert paths would save about40ms;
twenty percent would save about80ms in that saved trace. These are arithmetic
scenarios, not predicted gains. HC combine/norm/inject186.168095ms is the next
large family for a new mechanism. Additional SSM predicate simplifications,
host callbacks and compressed streaming cache have lower priority: the latest
predicate and cache trials have already failed to improve complete-model time,
and the profile has only5.090460ms between prefill kernels.

[Source](../config/q2-iq2-four-wave-source.json),
[static audit](../config/q2-iq2-four-wave-static.json),
[plan](../config/q2-iq2-four-wave-plan.json),
[profile](Q2-CURRENT-BEST-PROFILE.md).
