<!-- SPDX-License-Identifier: MIT -->

# Exact Promessi sposi PP/TG curves

**Withdrawn as a full-prefill or optimization comparison (2026-10-08).**
These are final-chunk timings after untimed prefix replay, on a different
corpus from the retained counting reference. Exact counts do not make these
scopes comparable. Preserve this historical table and its raw evidence;
see [measurement correction](Q2-BENCHMARK-CORRECTION.md).

Original Q2 on .157; IOMMU enabled; performance/120 W; C1 reactive AR.
Each prefill measurement covers the final complete 2048/4096/8192-token block
at the stated exact prompt frontier. Prior-prefix replay is outside PP/TG timers.
One measured run per point, no warmup or averaging; all shared frontiers use identical physical IDs.
Source checkpoint `032323df`; candidate binary `23b53980` reuses all 923 retained device functions.
Corpus SHA-256 `f53e0d80cb2d4492d24ebd63c7000c397b16ae70f9bf09b3763e5d8323ec209f`.

| Prompt tokens | PP 2K | PP 4K | PP 8K | TG 2K | TG 4K | TG 8K |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2048 | 929.71 | — | — | 26.89 | — | — |
| 4096 | 919.17 | 1452.12 | — | 27.24 | 27.29 | — |
| 8192 | 946.24 | 1375.44 | 1384.96 | 27.04 | 27.39 | 27.33 |
| 16384 | 954.84 | 1349.84 | 1368.60 | 27.29 | 27.31 | 27.35 |
| 32768 | 1000.46 | 1310.49 | 1338.25 | 27.00 | 26.91 | 27.21 |
| 65536 | 1076.65 | 1255.56 | 1271.90 | 26.97 | 26.61 | 26.97 |
| 131072 | 1008.92 | 1205.28 | 1215.65 | 26.36 | 26.28 | 26.19 |

All rates are token/s. A dash means the frontier is smaller than the chunk.
TG uses actual completed tokens; requested budget is 128. Completed budgets: 18/18.

## Output consistency

Chunk 4096: 0/6 generated token arrays match chunk 2048; differing frontiers: [4096, 8192, 16384, 32768, 65536, 131072].
Chunk 8192: 0/5 generated token arrays match chunk 2048; differing frontiers: [8192, 16384, 32768, 65536, 131072].

The 4K and 8K outputs match each other at all five common frontiers: True.
Compared with 2K, the first differing token is between zero-based positions 3 and 22; all first output tokens match.
Output differences are reported separately from throughput and are not an independent quality verdict.
These results do not measure an engine optimization over the earlier HTTP corpus.
No reference baseline is replaced, and no IOMMU-off comparison has been performed.

[Combined PP/TG graph](figures/q2-exact-bench128.png) · [CSV](figures/q2-exact-bench128.csv) ·
[Benchmark contract and command](Q2-EXACT-BENCH.md)

Evidence: `evidence/q2-exact-bench128-r1`; plan: `config/q2-exact-bench128-plan.json`.
The native executable also emits validated JSON/CSV/SVG/PNG reports for each arm.
