<!-- SPDX-License-Identifier: MIT -->
# Qwen3.8 Flash Next — AMD Strix Halo

[All benchmarks](../../../README.md) · [Run these workloads](../../../../guides/BENCHMARKS.md)

Results, tables and graphs are collected here. **PP** is prefill throughput;
**TG** is generation throughput, both in tokens per second. All throughput axes
start at zero, with independent scales for PP and TG.

| Measurement setup | Value |
| --- | --- |
| Model | Unsloth UD-Q4_K_XL, four shards, revision `38bb39ee97821de2c9009abb7e93950eec396e66`. |
| Platform | AMD Strix Halo, HIP `gfx1151`, dedicated measurement host `.157`. |
| Provider | Embedded Gufo, pin `f783fedb`; autoregressive, greedy, no MTP. |
| Measurement date | October 1, 2026. The build for each dataset is identified below. |
| Timing | Direct GPU executor; HTTP and client latency are excluded. |

These are retained measurements of the listed builds, not a rerun of the latest
cache changes. The workloads follow the shape of Gufo's AR benchmarks; exact
reproduction of its published HTTP campaign is still incomplete.

## Single user: context depth through 128K

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

## Multiple users: prefill and generation

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

## Full prompt prefill: through 258,794 tokens

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

## What is still missing from the Gufo comparison?

| Workload | Remaining work |
| --- | --- |
| Single-user AR. | Repeat all eight depths with the latest reactive/cache build and a paired Gufo control. |
| Multi-user AR over HTTP. | Implement and run the same per-request-rate protocol used by Gufo. |
| Single-user and multi-user MTP. | Integrate MTP before running these workloads. |
| Cold model loading. | Measure cold target files to HTTP readiness; current loading tests leave OS cache uncontrolled. |
| Peak HIP memory. | Measure allocation-exact peak memory; existing provider estimates are insufficient. |
| 512K–1M context. | Extend and qualify the provider beyond its native 262,144-token limit. |

## Reproduce and download

The [benchmark guide](../../../../guides/BENCHMARKS.md) contains the complete
commands for `single`, `multi`, `fresh`, local Gufo controls and graph export.
See Gufo's pinned [benchmarks](https://github.com/gufo-org/gufo/blob/f783fedb9bea2ec7de941f6da4e02f4a4596b29e/docs/models/qwen3.8-flash-next/BENCHMARKS.md)
and [method](https://github.com/gufo-org/gufo/blob/f783fedb9bea2ec7de941f6da4e02f4a4596b29e/docs/models/qwen3.8-flash-next/QUALITY.md#benchmark-method)
for the reference protocol.

Download the [full-precision CSV](charts/values.csv) or the
[plot data and source hashes](charts/data.json). SVG and PNG versions are in
[charts/](charts/). Rebuild this page and its figures without a GPU:

```sh
python3 tools/render-published-benchmarks.py
```

Internal correctness checks, cache experiments and older reports are available
in the [technical archive](../../../../archive/README.md). They are separate
from the performance results presented here.
