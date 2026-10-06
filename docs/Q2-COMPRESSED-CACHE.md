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
resident; expected initial model allocation is40898208304bytes versus
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

GPU component/model results remain pending. Source and host qualification do
not establish model correctness, memory fit or performance. Full curve, Q4 and
independent task quality remain outside this campaign.

[Reference identities](../config/q2-compressed-cache-reference.json),
[source](../config/q2-compressed-cache-source-v2.json),
[static comparison](../config/q2-compressed-cache-static-v2.json),
[frozen plan](../config/q2-compressed-cache-plan.json),
[staging](../config/q2-compressed-cache-staging.json).
