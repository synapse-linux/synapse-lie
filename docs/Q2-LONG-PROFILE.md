<!-- SPDX-License-Identifier: MIT -->
# Native long-prefix critical path — 7 October 2026

The original preparation inputs and32711-token prefix complete on .157 with
the saved server9993fdce/client87d856cf. Capacity133760, chunk2048, C1 AR,
original output8 and zero prefix hits remain exact. This is a diagnostic,
not a new throughput reference. No numerical source or model changes.

**GPU duration attribution fails:** all84621 kernel and3947 copy records have
identical start/end timestamps. Their apparent zero cost cannot rank kernels,
establish GPU utilization or establish speedup. The197552 CPU API intervals
have nonzero durations. Dispatch stack IDs link all47 embedding submissions
to their original21 prefill and26 decode calls; correlation IDs are zero.
[Bound report](../config/q2-long-profile-results.json).

The existing expert-count event is a completed dependency boundary. The48
event waits per prefill chunk allow comparison of CPU completion intervals;
each includes the previous layer's MoE/shared work and the current layer's
attention/HC work. These are not individual GPU kernel timings.

| Full2048 chunk start | Embedding submission to completion, ms | Twelve full-attention completion intervals, ms | Other34 linear intervals, ms |
|---:|---:|---:|---:|
|2048|1342.792|385.385|885.876|
|8192|1376.496|424.338|881.742|
|16384|1474.888|452.807|889.301|
|28672|1477.550|474.606|896.009|

The other two linear intervals include first-layer preparation and PLE.
Late chunks show45–70ms CPU gaps immediately before the20MiB HostToDevice
PLE upload; its API arguments confirm size20971520 and the inference stream.
The first chunk has a longer preparation gap. These observations support
targeting row readiness and depth-dependent attention, but do not separate
disk latency, scheduling and conversion or predict a128K gain.

Warm native decode differs from the older direct-executor diagnostic: six
observed calls submit prefix/suffix graphs back-to-back and complete in
38.606–38.681ms from embedding submission. For the five available following
boundaries, completion to next submission is0.092–0.097ms. Most time is inside
the final HIP synchronization; this includes executing queued device work,
not merely CPU scheduling. More external callbacks/threads cannot be credited
with the old diagnostic's5.33ms/token gap. C2 aggregate throughput also cannot
satisfy the C1 target. The eight original outputs do not qualify TG128.

The next row-reader experiment addresses a concrete amplification in the
current code: BF16 rows contain320 bytes, but successful O_DIRECT selection
requests aligned4096/8192-byte windows. Existing evidence records buffered
fallback on this compressed model despite O_DIRECT. A private BF16 buffered
descriptor could read only row bytes, preserving cache capacity, order and
values. Its memory/storage effects and complete-model result must be measured;
no cache eviction, model mutation, tuning or throughput gain is assumed.

All four primary commands and the native client exit0. After completed requests,
rocprofv3 flushes its database on SIGTERM; its chained handler fails to retire
within30s, and the existing supervisor kills its owned server (exit−9).
This is not a clean server-shutdown qualification. Eleven artifacts collect,
then releasecb2b68d9 at03:49:52.464972UTC retires all1821 recorded identities
and1454 groups, with empty KFD, unchanged/free original leases and unchanged
seven model stat identities. No inference rerun repairs this diagnostic.

## Exact 128K follow-up prepared — 7 October 2026

The row-sized reader improves the original32K request but regresses at64K
and128K, so it is not a route to the current1500-token/s target. The next
diagnostic applies this same profiler/host-boundary method to the saved
**130925-token** request, without changing a prompt, intermediate chunk or
benchmark control. It keeps the original three preparations, capacity133760,
63 full2048-token chunks plus the1901-token tail, C1 AR and eight outputs.
The server and native benchmark binaries are reused; profiler timings remain
ineligible as PP/TG results.

The new input validator checks exact serialized request bytes, token counts,
64 prefill calls, zero cached tokens and the original backend timer scope.
Existing32K analysis still reproduces exactly. The .157 CPU-only gate passes
43 Debug and43 ASan/UBSan checks; the collected host capsule and
[frozen plan](../config/q2-long-profile128-plan.json) bind one model diagnostic.
The [128K analyzer](../tools/analyze-q2-long-profile128.py) reports actual
per-chunk host completion intervals and four depth quarters, while rejecting
zero GPU event durations as kernel timings. It cannot isolate individual
kernels from a previous-layer/current-layer completion boundary.

## Exact 128K diagnostic completed

The original request, all64 prefill chunks and eight output calls complete on
the saved binaries with four command exits0. All95 embedding submissions match
the original sequence, including the three preparations and1901-token tail.
All11 collected artifacts match their receipt hashes. The default collection
exits1 (`Oversized collection`) because the313462784-byte trace exceeds its
128MiB total cap; the scoped512MiB collector verifies the already downloaded
archive without touching .157. The release precedes this offline analysis.

All178605 GPU dispatches and4187 copies have invalid zero device durations.
The table therefore uses completed host API boundaries, **not** individual
kernel times, device utilization or benchmark throughput. Each full-attention
boundary includes prior-layer MoE/shared work and current-layer attention/HC.

| Original2048-token chunk quarter | Mean completion, ms | Twelve full-attention boundaries, ms | Other linear boundaries except first two, ms | Mean largest CPU API gap, ms |
|---:|---:|---:|---:|---:|
|0–15|1468.272|437.362|890.028|78.635|
|16–31|1544.225|502.545|900.238|79.060|
|32–47|1599.163|556.106|902.197|78.361|
|48–63|1606.454|591.077|907.756|45.839|

The twelve full-attention boundaries grow154ms per chunk between the first and
last quarters, while the overall completion grows138ms. Each of the twelve
boundaries shows the same broad depth trend. The mean largest CPU API gap
shrinks late, so it does not explain that growth. Holding every later chunk's
full-attention boundary to the first-quarter mean would account for about5.40s
across this instrumented trace. The cold unprofiled target still needs12.59s,
so removing depth growth alone would not reach1500 token/s; baseline expert or
dense costs also need attention. The hypothetical5.40s is an arithmetic
counterfactual, not a predicted speedup or an upper bound on attention work.

The six warmed output intervals are about39.78–39.97ms under profiling; their
completion-to-next-submission gaps are about0.096–0.107ms. These eight output
calls do not qualify sustained TG128. The saved unprofiled128K observation
remains1310.874605 PP and25.344213 TG on eight outputs.

The launch/API identities remain usable even though device durations are not.
The first2048-token chunk stays below the sparse-selection budget. Each of the
next63 chunks submits **48 score and48 mark launches** (four512-row query
slices in each of12 attention layers), while all64 chunks submit12 WMMA
attention launches each. Expert gate/up submits96 launches per chunk.

| Original128K prefill launch family | Count |
|---|---:|
| SelectScoreKernel / SelectMarkKernel |3024 / 3024|
| WmmaCausalAttentionKernel |768|
| RoutedIq2FixedBoundsKernel |6144|
| RoutedQ2HalfStorageKernel |3024 (full chunks; final tail takes another route)|

Every score launch uses the capacity-sized131-block second grid dimension,
including early chunks with far fewer visible blocks. This submits51.864
billion score threads across the original request; the source's causal guards
leave25.705 billion score cells eligible for arithmetic. These are *logical
dispatch counts*, not device time or measured bandwidth. The live-grid
candidate could roughly halve those dispatched threads. Its first32K model
trial fell10.731% with lower observed GPU clocks, while a later
[same-session A-B-B-A replay](Q2-SELECT-LIVE-GRID.md) found only +0.478% mean
prefill rate. It remains unpromoted and cannot be claimed as a128K saving.

The previous8.36ms selector extrapolation was invalid: its10.889µs component
gain was measured for **one decode query**, while each of these prefill
score/mark calls handles up to512 query rows. Multiplying that one-row value
by either768 attention layers or3024 score/mark slices does not predict a
prefill saving. The trace establishes the launch count, not a selector
optimization's completed time. The repeated score **arithmetic** is a
separate candidate family, but the tested two-query and four-query
register-reuse designs were slower. A new design must preserve enough query
parallelism and prove its complete model effect.

[All64 chunk records, eight output intervals and validity checks](../config/q2-long-profile128-results.json).
The [Halogen comparison](Q2-HALOGEN-TRANSFER.md) uses these observations to
rank testable mechanisms without substituting its different checkpoint or
benchmark conditions.
