<!-- SPDX-License-Identifier: MIT -->
# Qwen3.8 Flash Next — AMD Strix Halo

[All benchmarks](../../../README.md) · [Run these workloads](../../../../guides/BENCHMARKS.md)

**Latest measurements: October 3, 2026.** PP means prefill throughput; TG means
confirmed generation throughput, both in tokens per second. Tables include PP
wait time. Charts use separate PP/TG scales beginning at zero; bars show observed
minimum/maximum around the median. Duration columns in downloaded CSVs are
seconds; throughput columns are tokens per second.

| Measurement setup | Value |
| --- | --- |
| Model | Original Unsloth UD-Q4_K_XL, four shards, revision `38bb39ee97821de2c9009abb7e93950eec396e66`. |
| Platform | Bosgame AXB35-02, Ryzen AI Max+ 395, 128 GB, HIP `gfx1151`, host `.157`. |
| Builds | Checkpoint `b72f4e8`; C17 sampler enabled versus disabled, embedded Gufo pin `f783fedb`. |
| Timing | Direct reactive executor, AR greedy, chunk 2048, TG128; no HTTP, MTP, image or retained-cache timing. |
| Repetitions | Depth/concurrency: one warmup plus three samples. Full prompt: two samples, no warmup. |

The **C++ control is LIE with its C17 selector disabled**, using the same reactive
scheduler and GPU model graph. It is not the separate Gufo HTTP server. All
**46 measured pairs and 12 warmup pairs** have identical physical inputs, output
IDs, stopping/batch counters and full prefill/decode-logit hashes. Greedy selection
retains GPU argmax in both builds; these data do not measure dense host-sampler cost.

TG differs by less than 1% across the depth/concurrency tests and full prompts
from 8192 tokens. **The un-warmed 1500-token point is slower by 16.64% in C17**;
its cause remains unresolved and the performance gate stays open. No sample
clock/power trace was captured. The values below retain this result.

## Single user: occupied context through 128K

Prefill processes approximately 2048 new tokens after the listed prefix. Prefix
construction is excluded from PP time. Both builds reserve capacity 133760.
This campaign has seven depths; **12288 is still missing** from the full eight-point
Gufo shape. The historical eight-point results are retained below.

| Prefix tokens | New PP tokens | C17 PP | C++ PP | C17 PP seconds | C++ PP seconds | C17 TG | C++ TG |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 2,048 | 1,635.95 | 1,630.86 | 1.252 | 1.256 | 25.95 | 26.02 |
| 4,096 | 2,047 | 1,521.93 | 1,517.88 | 1.345 | 1.349 | 25.93 | 26.02 |
| 8,192 | 2,048 | 1,475.04 | 1,468.25 | 1.388 | 1.395 | 25.85 | 25.93 |
| 16,384 | 2,048 | 1,447.93 | 1,410.12 | 1.414 | 1.452 | 25.79 | 25.86 |
| 32,768 | 2,048 | 1,380.68 | 1,380.40 | 1.483 | 1.484 | 25.64 | 25.73 |
| 65,536 | 2,048 | 1,336.33 | 1,337.76 | 1.533 | 1.531 | 25.21 | 25.45 |
| 131,072 | 2,048 | 1,278.98 | 1,279.45 | 1.601 | 1.601 | 24.79 | 24.87 |

![Latest suffix prefill and generation through 128K](charts/current-depth.svg)

## Concurrent users: one through eight

Each sequence has 2048 prompt tokens and capacity 4096. All sequences finish
prefill before timed decode. PP is the total prompt count divided by prefill time;
TG is the total confirmed output divided by the cohort's decode time.

| Users | PP tokens per user | C17 PP | C++ PP | C17 PP seconds | C++ PP seconds | C17 TG | C++ TG |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 2,048 | 1,633.32 | 1,635.95 | 1.254 | 1.252 | 26.02 | 26.02 |
| 2 | 2,048 | 1,631.20 | 1,631.76 | 2.511 | 2.510 | 45.75 | 45.92 |
| 4 | 2,048 | 1,619.29 | 1,620.96 | 5.059 | 5.054 | 75.46 | 75.90 |
| 6 | 2,048 | 1,608.74 | 1,601.86 | 7.638 | 7.671 | 94.39 | 94.67 |
| 8 | 2,048 | 1,603.38 | 1,601.76 | 10.218 | 10.229 | 106.36 | 107.17 |

![Latest concurrent prefill and confirmed generation](charts/current-multi.svg)

C17 reaches **106.36 tok/s** at eight users; its matched C++ control reaches
**107.17 tok/s**. Both batch native GPU decode. This comparison does not isolate
a reactive advantage. Eight users are sequences, not inference threads: one
caller owns device dispatch. The sampled process thread count ranges from
**1 to 51** in every arm, including runtime helpers and load/retirement phases;
a per-phase thread allocation is not available. Gufo's published HTTP test instead
sums individual request rates, so that exact comparison is still pending.

## Full prompt prefill: through 258794 tokens

This starts from an empty sequence and includes the entire prompt prefill.
It measures the wait for a new long input, separate from suffix PP and cache
reuse. Both builds reserve capacity 262144. Rate and time medians are summarized
independently; with two samples, the median rate need not equal tokens divided
by median time.

| Full prompt tokens | PP tokens | C17 PP | C++ PP | C17 PP seconds | C++ PP seconds | C17 TG | C++ TG |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,500 | 1,500 | 1,380.20 | 1,451.37 | 1.100 | 1.037 | 22.02 | 26.41 |
| 8,192 | 8,192 | 1,540.62 | 1,550.52 | 5.317 | 5.283 | 25.75 | 25.79 |
| 32,768 | 32,768 | 1,469.29 | 1,471.31 | 22.302 | 22.271 | 25.70 | 25.74 |
| 131,072 | 131,072 | 1,352.50 | 1,351.98 | 96.912 | 96.949 | 24.82 | 24.88 |
| 258,794 | 258,794 | 1,286.84 | 1,287.68 | 201.109 | 200.977 | 23.83 | 23.87 |

![Latest full prompt prefill and generation](charts/current-fresh.svg)

The 258794-token prompt takes **201.109 s** in C17 versus **200.977 s** in the
C++ control. TG is **23.83** versus **23.87 tok/s**. Across all six arms,
sampled peaks are CPU94.625/GPU97/NVMe75.85 C; no 98 C operating guard stop
occurs. Fans are not exposed on this host. Desktop activity and denied FD
visibility limit isolation claims; the cooperative leases are not universal
exclusivity. File-cache state is uncontrolled and model construction is excluded.

## Reproduce and download

[Full-precision values and timing ranges](charts/current-values.csv) combine all
three workloads. Native summary JSON/CSV and SVG/PNG live in [charts/](charts/).
Raw measured inputs/outputs are in [data/](data/), named `current-depth`,
`current-multi` and `current-fresh`, with `c17` and `cpp` arms. The
[source-bound validation receipt](../../../../development/validation/c17-gpu-performance-2026-10-03.json)
records every comparison and artifact hash. Existing files are never overwritten
by the native exporter.

To regenerate a figure from its downloaded raw pair, without a GPU or Python:

```sh
mkdir -p results
gzip -dc docs/benchmarks/models/qwen3.8-flash-next/strix-halo/data/current-depth-c17.jsonl.gz > results/c17-depth.jsonl
gzip -dc docs/benchmarks/models/qwen3.8-flash-next/strix-halo/data/current-depth-cpp.jsonl.gz > results/cpp-depth.jsonl
build/release/synapse-lie-bench-report --suite report results/c17-depth.jsonl \
  --output results/depth-charts --label 'LIE C17' \
  --compare results/cpp-depth.jsonl --reference-label 'LIE C++ control'
```

See the [benchmark guide](../../../../guides/BENCHMARKS.md) for new GPU runs and
Gufo's pinned [benchmarks](https://github.com/gufo-org/gufo/blob/f783fedb9bea2ec7de941f6da4e02f4a4596b29e/docs/models/qwen3.8-flash-next/BENCHMARKS.md)
and [method](https://github.com/gufo-org/gufo/blob/f783fedb9bea2ec7de941f6da4e02f4a4596b29e/docs/models/qwen3.8-flash-next/QUALITY.md#benchmark-method)
for the reference protocol.

## Remaining Gufo / Halogen coverage

| Workload | Remaining work |
| --- | --- |
| Eight AR prefix depths. | Add the missing 12288 point to the current paired build. |
| Multi-user AR over HTTP. | Implement and run Gufo's per-request-rate protocol. |
| MTP single/multiple users. | MTP is integrated; mixed/repetitive performance campaigns remain pending. |
| Cold model loading. | Measure cold target files to HTTP readiness; current model load leaves OS cache uncontrolled. |
| Peak HIP memory. | Allocation-exact peak accounting; provider estimates are insufficient. |
| 512K–1M context. | Implement and qualify context expansion beyond native 262144. |
| First full prompt at 1500 tokens. | Diagnose the retained 16.64% TG regression with a timed crossover control. |

## Historical measurements — October 1

<details>
<summary>Earlier Gufo reference, reactive versus serial and full-prompt results</summary>

### Single user: context depth through 128K

This test measures approximately 2,048 new prompt tokens **after** the occupied
prefix, then generates 128 tokens. The time to construct the prefix is excluded.
Use it to compare suffix prefill and decoding as the context grows.

| Prefix tokens | New PP tokens | LIE PP | Gufo PP | LIE TG | Gufo TG |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 2,048 | 1,633.37 | 1,610.13 | 26.03 | 25.86 |
| 4,096 | 2,047 | 1,517.17 | 1,500.01 | 26.03 | 25.88 |
| 8,192 | 2,048 | 1,465.62 | 1,454.18 | 25.96 | 25.95 |
| 12,288 | 2,048 | 1,446.02 | 1,401.94 | 25.92 | 25.92 |
| 16,384 | 2,048 | 1,437.71 | 1,402.14 | 25.85 | 25.89 |
| 32,768 | 2,048 | 1,410.20 | 1,364.33 | 25.75 | 25.74 |
| 65,536 | 2,048 | 1,323.24 | 1,322.22 | 25.31 | 25.32 |
| 131,072 | 2,048 | 1,262.38 | 1,264.80 | 24.67 | 24.71 |

![Single-user AR prefill and generation through 128K](charts/single-ar.svg)

Paired local baseline: LIE `openai-reactive-api-r3` and the direct Gufo reference,
one measured repetition after one warmup, capacity 133,760. This predates LIE's
reactive batching change. All eight pairs have matching physical inputs and
output tokens. A later reactive C1 check at depths 0, 16K and 128K stayed within
0.35% of serial median TG; the complete eight-depth reactive rerun is still pending.

### Multiple users: prefill and generation

Each sequence has 2,048 prompt tokens, 128 output tokens and capacity 4,096.
All sequences finish prefill before timed decode. TG is the combined output
count divided by the cohort's decode time. PP is aggregate prefill throughput.

| Users | LIE reactive PP | Gufo earlier PP | LIE reactive TG | Gufo earlier TG | LIE serial TG |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1,625.73 | 1,628.64 | 26.02 | 26.05 | 26.05 |
| 2 | 1,620.22 | 1,624.90 | 45.67 | 45.87 | 26.06 |
| 4 | 1,590.68 | 1,602.50 | 69.17 | 66.89 | 26.07 |
| 6 | 1,586.34 | 1,596.89 | 94.76 | 94.82 | 26.06 |
| 8 | 1,588.75 | 1,580.05 | 107.15 | 107.03 | 26.08 |

![Multi-user AR prefill and generation, with historical Gufo reference](charts/multi-ar.svg)

LIE `reactive-inference-r3` uses three measured repetitions after one warmup.
The Gufo column comes from the earlier direct-reference run, with one measured
repetition. It supplies context, not a paired speedup claim. Gufo's published
HTTP benchmark sums individual request rates, so its metric is also different.

At eight users, LIE native batching reaches **107.15 tok/s**, versus **26.08 tok/s**
for the matched LIE serial control: **4.11×**. The earlier native Gufo run reached
**107.03 tok/s**. These data do not establish a reactive speed advantage over
Gufo's native batching. “Eight users” means eight sequences, not eight inference
workers; the dispatcher has one device-owner caller. A total OS-thread count
was not recorded for this particular campaign.

### Full prompt prefill: through 258,794 tokens

This test starts from an empty sequence and measures the whole prompt. It shows
the actual wait for a new long input. It is a different workload from the
incremental prefill above or a cached conversation follow-up.

| Full prompt tokens | LIE PP (tok/s) | Prefill time (s) | LIE TG (tok/s) |
| ---: | ---: | ---: | ---: |
| 1,500 | 1,446.20 | 1.041 | 26.66 |
| 8,000 | 1,528.70 | 5.233 | 26.00 |
| 8,192 | 1,531.83 | 5.348 | 25.85 |
| 32,768 | 1,457.88 | 22.477 | 25.77 |
| 131,072 | 1,354.82 | 96.767 | 24.73 |
| 258,794 | 1,270.51 | 203.693 | 23.89 |

![Full-prompt prefill and generation through 258794 tokens](charts/fresh-ar.svg)

Build `bench-comparable-r1`: two measured repetitions, no warmup, capacity
262,144, chunk 2,048, output 128. Values are medians; error bars show the observed
minimum and maximum. Time and rate are independently summarized across samples.
No matched Gufo or Halogen full-prefill run is available for this dataset.

</details>

Internal correctness/cache checks remain in the
[development documentation](../../../../development/README.md), separate from
these performance tables.
