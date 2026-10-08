<!-- SPDX-License-Identifier: MIT -->

# Focused full-prefill counting diagnostic

Original Q2 on .157, IOMMU enabled, retained numerical provider, C1 greedy AR.
Each sample includes all prompt tokens between its initial/final monotonic timestamps.
One warmup and three measured repetitions per arm; no per-repetition pause.
At a common prompt length all physical IDs are identical. TG uses 128 completed calls.
This is a focused subset, not the pending complete curve through 128K.

| Prompt | Chunk | Allocated context | PP samples (token/s) | Full PP elapsed (s) | TG samples (token/s) |
| ---: | ---: | ---: | --- | --- | --- |
| 2048 | 2048 | 9216 | 1574.90, 1577.63, 1570.75 | 1.300400, 1.298152, 1.303835 | 27.44, 27.42, 27.44 |
| 2048 | 2048 | 133760 | 1572.63, 1569.83, 1572.14 | 1.302277, 1.304601, 1.302680 | 27.49, 27.55, 27.55 |
| 8192 | 2048 | 133760 | 1544.15, 1542.55, 1540.27 | 5.305171, 5.310696, 5.318557 | 27.55, 27.51, 27.49 |
| 8192 | 4096 | 133760 | 1499.86, 1498.31, 1495.90 | 5.461828, 5.467485, 5.476317 | 27.51, 27.51, 27.52 |
| 8192 | 8192 | 133760 | 1439.08, 1438.85, 1439.70 | 5.692527, 5.693432, 5.690066 | 27.52, 27.50, 27.49 |

All warmup/measured samples and phase durations are in the [CSV](figures/q2-counting-full-prefill.csv).
All 128-token continuations match across the five arms. Different prefill
chunk boundaries produce different logits hashes; this counting task does
not establish broad task-quality or numerical equivalence.
At the same 8192-token input, larger chunks are slower in all three measured
samples. Allocating 133760 instead of 9216 tokens does not reproduce the
large earlier discrepancy on the 2048-token counting input. These findings
do not isolate the cause of the raw-corpus result or establish long-context rates.
The 923 GPU functions are unchanged: this is a corrected workload comparison,
not a measured numerical-kernel optimization.

The old 1587.893545 observation is preserved on its own harness: it includes
15-second pauses, a different numerical-provider revision, and 127 timed decode forwards.
No strict historical performance delta or quality equivalence is claimed.
[Measurement correction and source references](Q2-BENCHMARK-CORRECTION.md).

Run 2026-10-08 00:20:53–00:25:04 UTC; all five children and runner exit 0.
All 71 artifacts verify before release at 00:26:00; strong closure at 00:26:28
finds 63 retired process/group identities, empty KFD, five free original leases
and unchanged model stats. CPU peak 90.875 C; IOMMU remains enabled.
Release SHA-256: `d5be8bf0bcff502102dbaf6d89995d236ad46796ac927b3ac3ad0ef74fc7eda9`.
No remote cleanup, model mutation, reboot or tuning occurred.
