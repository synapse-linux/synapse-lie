<!-- SPDX-License-Identifier: MIT -->
# Compressed expert slots from the antirez/ds4 design

The requested reference is the original **antirez/ds4**, independently fetched
at `0aaea5a238fb41a35106a551e73c8409dfb751ac`. Its streaming cache keeps original
quantized expert bytes in bounded slots, protects the complete selected set,
loads missing experts and reuses slots only after their GPU consumers finish.
Its [SSD streaming guide](https://github.com/antirez/ds4/blob/0aaea5a238fb41a35106a551e73c8409dfb751ac/docs/SSD_STREAMING.md)
recommends resident inference when the whole model fits. This is the mechanism
implemented here. The earlier [FP16 mirror experiment](Q2-EXPERT-CACHE.md)
used the wrong reference and is retained separately. Its hypothetical 225GiB
expansion is not a requirement of antirez/ds4 or this implementation.

The source derives from retained Q2 1585.308983 PP /25.16079073 TG. IQ2_XXS
gate/up and padded Q2_K down bytes remain unchanged. The C17 policy owns a
direct key map and LRU list. A key belongs to one immutable model/layer/expert;
the model owns its original file-range metadata and upload pipeline. Selected
hits are pinned before choosing victims, including hits encountered after a
miss in the same request. Pending triplets cannot become later hits after a
failed load. Metadata operations are linear in the selected expert count.

The experimental budget is 32GiB for compressed expert weights, with an 8GiB
device reserve. It admits 23061 slots out of24576 experts. Each slot owns
422400-byte gate and up ranges and a645120-byte down range. Arena allocations
total34359057408bytes including three4096-byte tails. Other weights stay
resident; measured initial model allocation is40898208304bytes versus
43156012544bytes in the saved fully resident parent. Dynamic selected-ID
allocation is counted by `DeviceModel::resident_bytes()` and final telemetry.
This budget replaces original expert allocations; it does not add FP16 copies.
If all experts fit the configured source budget, the original resident path
remains. Unsupported model layouts retain that original path too.

Ten additional prefill specializations resolve expert addresses through a
slot map; their numerical loops remain the retained kernels. Decode remaps
selected IDs into the same compressed arenas and calls existing vector
kernels. All162 original assembly bodies/resources remain exact, binding only
the new default-false template parameter; all ten added kernels have zero
scratch. Cache misses read the bound GGUF through the existing owned upload
pipeline. Upload completion precedes address publication. A model-local mutex
and HIP completion event protect reuse across calls and streams. Streaming
execution disables captured decode graphs because routing and misses must be
resolved each call. Full residency retains the original graph path. C1 is the
current measurement scope; serving concurrency and cancellation qualification
are not established by this experiment.

Revision1 compiles. Revision2 adds accounting for dynamic selected-ID storage;
its numerical sources are byte-identical and their compilation is reused.
Both source inventories and patches remain. Host tests on .157 pass30 Debug
and30 ASan/UBSan checks, including30000 adversarial transactions, duplicate
requests, protecting later hits, failed loads and insufficient capacity.
A fresh second host capsule binds the final launcher to revision2; no saved
performance control is rebuilt or rerun.

The component compares complete encoded bytes and complete numerical outputs
after shuffling experts into noncontiguous slots. It preserves the previous
ragged shapes, four production timing cases, three weight rotations beyond
32MiB,216 replay pairs and56 timing samples. Setup is outside component kernel
timers. The subsequent original exact2048/tg128 model test includes real miss
reads, transfers and GPU waits inside PP/TG. One warmup plus three measured
sessions,127 timed decode calls,capacity9216/chunk2048,greedy C1 and MTP off
remain unchanged. Controls are saved fixed Q21443.672867,retained1585.308983
and fixed UD1685.777092. Speed and memory are separate outcomes; full residency
already avoids expert disk reads, so a throughput improvement is not assumed.

The GPU component completes with all 117 complete encoded-byte checks and all
216 numerical output pairs exact. Across those checks, 2575768356 bytes are
compared; these are repeated fixture checks, not that many distinct model bytes.
All three component commands exit 0. The four projection medians are:

| Projection | Active experts | Original us | Compressed slots us | Time change |
| --- | ---: | ---: | ---: | ---: |
| IQ2 gate/up | 512 | 5554.953893 | 5658.884684 | +1.870957% |
| IQ2 gate/up | 64 | 3781.224569 | 3798.864365 | +0.466510% |
| Q2 down, half output | 512 | 3346.542676 | 3369.128545 | +0.674902% |
| Q2 down, half output | 64 | 2587.255001 | 2598.641396 | +0.440096% |

All 56 timings, including warmups, are retained in the
[CSV](figures/q2-compressed-cache-component.csv) and
[chart](figures/q2-compressed-cache-component.png).
Kernel indirection has a small cost in these cases. The completed model run
includes costs excluded by this component test.

The original exact2048/tg128 benchmark finishes on .157 at
2026-10-06T00:15:11UTC. Only the new candidate is built and run; all three
historical controls are reused. The new measurements are:

| Sample | Prefill s | Prefill tokens/s | Decode s | Decode calls/s |
| --- | ---: | ---: | ---: | ---: |
| Warmup | 11.955135980 | 171.3071272 | 6.855057925 | 18.52646635 |
| 1 | 1.299486043 | 1576.007692 | 5.220800594 | 24.32577106 |
| 2 | 1.301071811 | 1574.086828 | 5.219296567 | 24.33278094 |
| 3 | 1.299383462 | 1576.132112 | 5.220324236 | 24.32799080 |
| Three-sample median | 1.299486043 | 1576.007692 | 5.220324236 | 24.32799080 |

| Saved comparison | Prefill tokens/s | Decode calls/s | New PP change | New TG change |
| --- | ---: | ---: | ---: | ---: |
| Fixed Q2 | 1443.672867 | 25.09595499 | +9.166538% | -3.060111% |
| Retained Q2 parent | 1585.308983 | 25.16079073 | -0.586718% | -3.309912% |
| Fixed UD | 1685.777092 | 24.34174251 | -6.511501% | -0.056494% |

All 21 files compared with the retained parent are byte-identical, including
full saved logits and output tokens; all nine within-arm replay comparisons
pass. This retains the parent's independent quality limitations. Component
and model agreement does not establish independent task quality.

The first 2048-token request follows the unchanged short arithmetic/counting
checks, so its cache is partly populated, not pristine. Its 11.955136-second
prefill includes remaining miss reads; warmups are always exported and remain
outside the established three-sample median. The model-load report is
2.463946 seconds, excluding later expert loading. That value alone does not
measure time to first completed request. No KV or prompt cache is added.

Across the whole process, including the short checks, the cache records 25392
calls, 302037 hits, 16124 misses/loads, zero failed loads and zero evictions.
Logical GGUF payload read is 24023470080 bytes (22.373600GiB); this counter is
not physical disk traffic and includes every prompt. The complete observed
expert working set fits the 23061-slot cache. Eviction policy is exercised by
the adversarial C17 tests; this model run does not qualify GPU eviction under
an overflowing working set or different prompts.

The device-model allocation falls from40.192169GiB to38.089425GiB at load.
Including81920 dynamic ID bytes, the reduction is2.102668GiB. The additional
persistent upload buffers consume0.250061GiB; subtracting those leaves a
known allocation reduction of1.852607GiB, before CPU metadata/runtime overhead.
This is accounting of known allocations, not a measured process-memory peak.
Session allocation stays376777748bytes, with7946240 deferred scratch bytes.

Keep **1585.308983 PP /25.16079073 TG** as the performance base. Preserve the
compressed-cache experiment for memory-constrained work: this32GiB setting
does not improve throughput on the fixed workload. Address indirection,
host routing/synchronization and disabling decode graphs are changed costs;
this run does not isolate their individual shares of the regression. The
retained resident candidate still needs6.337447% PP to reach fixed UD.

[All 16 model samples](figures/q2-compressed-cache-model.csv),
[model chart](figures/q2-compressed-cache-model.png),
[model report](../config/q2-compressed-cache-model-results.json).

This ports the bounded compressed-slot mechanism, not all DS4 streaming
optimizations. Next-layer prefetch, resident-layer prioritization, allocation
backoff and public runtime budget selection are not implemented here. Misses
use Gufo's retained upload pipeline and each selected set waits for its data;
no inference/transfer overlap benefit is claimed. That pipeline retains 16
host staging buffers of 16MiB + 4096 bytes each (268500992 bytes total), outside
the reported device-model allocation. Model allocation is not process or
system peak memory. Dynamic ID accounting also needs concurrency review before
serving promotion; this campaign measures C1 only. Full curve, Q4 and
independent task quality remain outside this campaign.

All13 primary host/component/model commands exit0 and37 artifacts verify.
The preliminary host capsule adds six exit0 commands and seven preserved
artifacts (44 total). The frozen102 fixtures/nine manifests/1030 provider
files remain exact. Both charts are visually reviewed. Model-campaign peaks
are79.375C CPU and72C GPU. Release at2026-10-06T00:15:46.954550UTC retires1210
recorded identities/966 groups, leaves KFD empty and verifies four unchanged
free leases/seven unchanged model stat tuples. Canonical/main/remote mirrors
agree and Core is notified. No Q2 job, build, waiter, reservation or cleanup
remains. No saved control, Q4 or full curve is rerun.

[Reference identities](../config/q2-compressed-cache-reference.json),
[source](../config/q2-compressed-cache-source-v2.json),
[static comparison](../config/q2-compressed-cache-static-v2.json),
[frozen plan](../config/q2-compressed-cache-plan.json),
[staging](../config/q2-compressed-cache-staging.json).
[Final audit](../config/q2-compressed-cache-final-audit.json),
[release](../config/q2-compressed-cache-window-release.json).
