<!-- SPDX-License-Identifier: MIT -->
# IQ2 dispatch for one-fragment tails

This candidate starts from saved1585.308983 PP /25.16079073 TG and selects
the existing BN16 kernel for IQ2 tails with1..16 live rows. Wide128 descriptors
and64-row tails with17..64 live rows retain their original kernels and order.
The C17 map converts nonzero tail offsets to16-row index units, adds no
descriptors or device allocation, and appends at most one additional launch
per eligible layer. Original Q2-down maps, model format and decode are unchanged.

The1029-file source changes the adapter's CMake/executor/header and adds the
own C17 map/header. All thirteen numerical HIP/include sources match the
retained1585 parent exactly. Bounded192 usage records for the four prefill
sessions are copied inside the original timers and emitted at executor
teardown, after the original tester's complete event. No timed logging or new
device count transfer is introduced. This is still a measured hypothesis.

The [captured fixed-input routes](Q2-CURRENT-ROUTING.md) show9016/12753 tails
eligible (70.697%), including284 with nonzero offsets. Existing device ISA
reserves86 rather than104 VGPR and11392 rather than17536 LDS bytes for BN16
versus BN64. The original BN64 path already omits empty WMMA fragments and
activation stores; static resource savings do not establish actual occupancy
or throughput gains. The old whole-bucket short48 negative is retained.

Fresh .157 host33+33 passes, including every single count and two-expert split
through4096, all three captured512-expert distributions, map capacity/errors,
unchanged output guards, and launch/provider restrictions. Local HIP host/device
syntax passes. Source-patch reconstruction and all1029 identities verify.
These checks establish preparation, not GPU numerical or model performance.

The GPU fixture retains96 complete guarded output pairs: nine edge token
counts by three output widths, full uniform64-expert control, unchanged-route
uniform512 control, and captured layers0/3/22. Operands are synthetic; counts
are measured. Cyclic assignment gives each token ten distinct experts and
each output slot one owner. The three actual-count cases plus the full control
retain56 timing samples, two warmups/five measured alternating pairs with
three rotated weight sets beyond32MiB. The inherited raw `active_experts`
timing field denotes allocated expert capacity; the bound count arrays show
the number of actually nonempty experts. No independent teacher claim.

Guards/runtime failures exit2 and stop dependent device work. Safe numerical
differences exit1 with timings retained, then the new original2048/tg128 model
still runs as requested. That benchmark preserves the exact input, capacity9216,
chunk2048, C1 greedy/MTP-off, one warmup/three measurements,127 timed decode
calls and15-second pauses. Saved fixedQ2/UD and retained1585 comparisons are
reused without builds/reruns. Full context curves and Q4 remain deferred.

[Source](../config/q2-iq2-tail16-source-v2.json),
[static audit](../config/q2-iq2-tail16-static.json),
[plan](../config/q2-iq2-tail16-plan.json),
[staged capsules](../config/q2-iq2-tail16-staging.json).
No public model/state/metrics ABI changes; the new map contract is
[`q2_iq2_tail16.h`](../experiments/q2_iq2_tail16.h).
