<!-- SPDX-License-Identifier: MIT -->
# Skip empty prefill selector blocks

The retained selector sizes its score grid for the allocated context capacity.
This supports captured decode graphs as their position advances, but eager
prefill already knows the last complete key block. At early prefix depths,
most dispatched blocks immediately return without reading keys or writing
scores. The candidate bounds only this grid by the known live key extent.

All164 original numerical device bodies and resources remain instruction-exact.
The score pitch33440,1045 mask words, capacity133760, ratio4,512-block budget,
FP32 queries, F16 keys, score arithmetic and original top-k consumer are
unchanged. Captured decode must retain its original capacity grid. No model
dispatch has been changed or qualified by this component.

The [fixture](../config/q2-select-live-grid-fixture.json) reuses the complete
score-plus-top-k checks from the preceding query-pair trial: all timed outputs
checked before reuse, full byte identity, finite active scores, unchanged
inactive score sentinels, mask cardinality/causal bounds, independent sampled
FP64 scores and CPU top-k/ties, guards and immutable inputs. Finite differences
retain timing. Two warmups and five measured repetitions alternate arm order;
completed monotonic wall time remains separate from HIP event validity.

| Timed slice in original saved prefix | Query rows | Chunk start | First query | Grid columns: capacity → live |
|---|---:|---:|---:|---:|
| 4K final tail | 504 | 2048 | 1536 | 131 → 4 |
| 32K last full chunk | 512 | 28672 | 1536 | 131 → 30 |
| 128K last full chunk | 512 | 126976 | 1536 | 131 → 126 |
| 128K final tail | 365 | 129024 | 1536 | 131 → 128 |

The original chunks remain2048 tokens with only their actual final tails.
These rows are internal selector slices, not replacement model prompts or
shortened intermediate prefill chunks. One/three rows, small values and ties
crossing the budget boundary are extra correctness cases. This fixture uses
synthetic operator inputs and does not establish model throughput or quality.

Expected gain is depth-dependent: less empty dispatch earlier, little to remove
near full capacity. Measure before adoption; keep all completed-model PP/TG
references unchanged. No saved control rebuild/rerun, Q4, full curve, model
conversion, dependency installation or cleanup is part of this component.
