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
