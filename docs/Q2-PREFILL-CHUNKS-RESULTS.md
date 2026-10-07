<!-- SPDX-License-Identifier: MIT -->

# Enabled-IOMMU prefill chunk measurements

Historical unaligned HTTP observation. These prompt lengths do not satisfy
the owner's requested exact 2K/4K/8K grid. The corrected native corpus
contract is documented in [Q2-EXACT-BENCH.md](Q2-EXACT-BENCH.md); results from
the two input corpora and timing scopes must not be merged.

One original eleven-request curve per chunk on .157, in 2048/4096/8192 order.
The same server and native `synapse-lie-bench` run C1 AR at context capacity
133760 with performance/120 W, unchanged fan settings and zero KV/SSD prefix reuse.
No reboot, boot-configuration change, request padding or weight requantization.

Prompt lengths below are actual tokenizer counts. The original 2055-token
preparation point uses 16 generated tokens; each prefix uses eight.
It is not the separate fixed2048/tg128 benchmark. Calibration points are
reported separately and are not included in the graph.

## Prefill (token/s)

| Actual prompt tokens | Chunk 2048 | Chunk 4096 | Chunk 8192 |
| ---: | ---: | ---: | ---: |
| 2055 (preparation) | 1501.84 | 1048.01 | 966.04 |
| 4088 | 1267.09 | 1230.93 | 1261.70 |
| 8138 | 1250.03 | 1299.61 | 1290.40 |
| 8177 | 1485.52 | 1433.01 | 1345.69 |
| 12242 | 1275.48 | 1264.05 | 1270.25 |
| 16317 | 1280.17 | 1300.15 | 1266.55 |
| 32711 | 1276.22 | 1298.72 | 1319.98 |
| 65440 | 1284.92 | 1298.56 | 1276.42 |
| 130925 | 1302.02 | 1265.10 | 1232.32 |

## AR decode (token/s)

| Actual prompt tokens | Chunk 2048 | Chunk 4096 | Chunk 8192 |
| ---: | ---: | ---: | ---: |
| 2055 (preparation) | 27.38 | 27.11 | 24.08 |
| 4088 | 27.05 | 27.12 | 27.13 |
| 8138 | 27.15 | 27.14 | 27.18 |
| 8177 | 26.97 | 26.73 | 26.93 |
| 12242 | 27.11 | 27.12 | 27.09 |
| 16317 | 27.00 | 27.09 | 26.99 |
| 32711 | 26.95 | 26.78 | 26.82 |
| 65440 | 26.61 | 25.82 | 26.58 |
| 130925 | 25.80 | 25.55 | 26.02 |

## Calibration observations

| Prompt tokens | Chunk | Prefill token/s | Decode token/s | Outputs |
| ---: | ---: | ---: | ---: | ---: |
| 13 | 2048 | 59.82 | 25.20 | 1 |
| 3513 | 2048 | 1498.95 | 27.31 | 1 |
| 13 | 4096 | 66.29 | 25.54 | 1 |
| 3513 | 4096 | 1031.14 | 26.95 | 1 |
| 13 | 8192 | 58.93 | 25.25 | 1 |
| 3513 | 8192 | 1095.31 | 26.81 | 1 |

## Output and observation limits

Short-output mismatches relative to chunk2048:

- Chunk 4096: none (all eleven exact).
- Chunk 8192: original-12-prefix-16384

Eight decode calls do not qualify sustained TG128 or independent task quality.
Chunk partitioning can change arithmetic reduction order even with identical
compiled kernels. No weight precision is reduced.

OS page-cache state is not reset. Fixed execution order and whole-corpus
telemetry limit causal attribution of small differences to chunk size alone.
IOMMU remains enabled throughout; this is not an IOMMU on/off comparison.

[Graph](figures/q2-prefill-chunks128.png) ·
[Full-precision CSV](figures/q2-prefill-chunks128.csv) ·
[Machine-readable audit](../config/q2-prefill-chunks128-results.json)
