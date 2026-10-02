<!-- SPDX-License-Identifier: MIT -->
# Qwen3.8 Flash Next on AMD Strix Halo

[Model platforms](../README.md) · [Benchmark index](../../../README.md)

## Unsloth UD-Q4_K_XL

Original-weight measurements use the designated `.157` Strix Halo host and the
transitional HIP provider targeting `gfx1151`. Local `.155` compilation and CPU
fixtures are separate evidence. Each linked report binds the exact model,
executable, numerical archives and measurement protocol.

| Experiment | Available result | Scope and remaining gap |
|---|---|---|
| Initial C1 PP and TG | [Fresh-session baseline](../../../../C1-BASELINE.md) | Short contexts, executor only |
| Executor and HTTP | [Performance report](../../../../PERFORMANCE-RESULT.md) | Distinct timing intervals; preserve the report's original limits |
| Occupied context through 128K | [Eight-depth comparison](../../../../BENCHMARK-RESULTS.md) | About 2048 new tokens after the prefix; simplified direct Gufo control |
| AR concurrency C1/2/4/6/8 | [Reactive and serial comparison](../../../../REACTIVE-INFERENCE-RESULT.md) | Native GPU batches; cohort decode throughput, not Gufo's published HTTP protocol |
| Fresh PP through 258794 tokens | [Fresh and HTTP measurements](../../../../FULL-PREFILL-HTTP-RESULT.md) | Two repetitions for fresh PP; HTTP shapes and conversation retain their own sample counts |
| Shared C core | [GPU regression](../../../../CORE-GPU-RESULT.md) | C1/C2/C4/C8 and fresh PP through 128K; includes core latency |
| RAM prefix state | [GPU state and cache result](../../../../STATE-GPU-RESULT.md) | Exact same-provider restore through 128K, core cache off/on timings and HTTP smoke |
| SSD restart and C1 off/RAM/SSD | [Completed SSD result](../../../../SSD-GPU-COMPLETION.md) | Exact restore through 128K, 4K-to-8K extension, PP/TG/TTFT and 1 Hz thermal graphs; earlier software stops retained |
| Cache features and HTTP SSD | [R5 results](../../../../CACHE-FEATURES-GPU.md) | ON/OFF core through 128K; raw SSD restart, C2, cancellation and slow-client checks; numeric-byte codec is a separate revision |
| Lossless checkpoint packing | [R6/R7 cost and benefit gate](../../../../CACHE-COMPRESSION-GPU.md) | Exact compressed SSD restore at 128K; 15–16% saving has excessive restore cost; stricter admission passes matched ON/OFF regression, retaining raw states |
| DS4-style cache policy | [Policy and retention measurements](../../../../CACHE-DS4-GPU.md) | Exact generated-frontier and context-growth restore; C1/C2 and 128K retention cost; these measurements use the legacy component representation |
| DS4 runtime payload | [Paired runtime measurements](../../../../KVC-GPU-RESULT.md) |15/15 GPU arms,24 exact state pairs through128K; larger checkpoint and+19% median RAM-hit TTFT at128K; foreign DS4-produced restore remains unqualified |
| HTTP capacity and Pi | [256K and tool receipt](../../../../HTTP-256K-PI.md) | Capacity and functional tool tests; not a 256K quality/performance campaign |

Reports link full tables, graph exports and machine-readable samples. Preserve
fresh PP, suffix PP and restored-prefix costs separately. The 4.11x C8 result
compares LIE native batching against LIE serial dispatch on the same provider;
it does not isolate a reactive advantage over Gufo native batching.

The [SSD HTTP restart/C2 client](../../../../SSD-HTTP-PROTOCOL.md) includes
first-text/gap percentiles, executed PP/TG and graph exports. R5 now supplies
original-weight measurements. Preserve its raw-checkpoint and sample-count
limits when comparing later codec revisions.

## Other weight formats

Antirez Q2/Q4 compatibility is separate work on `feature/antirez-compat-audit`.
Its current measurements are not integrated here. The [earlier Q2 records](../../../../ANTIREZ-BENCHMARKS.md)
retain their dated investigation/withdrawal scope and do not qualify the current
parallel branch. Add a new format-specific campaign only with its own checkpoint,
build, numerical status and measured PP/TG; never reuse UD results as Q2 results.
