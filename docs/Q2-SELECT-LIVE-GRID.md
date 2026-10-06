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

## Component collected — 2026-10-06 UTC

All62 complete score/mask pairs are exact; all62 independent reports pass.
All164 original device bodies and resource descriptors remain identical.
Completed wall means below retain every raw sample in the
[result](../config/q2-select-live-grid-results.json). All56 zero HIP event
durations are invalid. Ranges overlap and variability is large, especially
on the128K full-chunk slice; these percentages are not full-model speedups.

| Original selector slice | Capacity grid µs | Live grid µs | Time change |
|---|---:|---:|---:|
| 4K final tail | 673.6406 | 254.0094 | −62.293% |
| 32K last full chunk | 1288.4108 | 943.3298 | −26.783% |
| 128K last full chunk | 2924.7486 | 2657.6954 | −9.131% |
| 128K final tail | 1626.5640 | 1596.0868 | −1.874% |

HOST39+39 and three component commands pass. Four artifacts collect before
release21:56:42.312392UTC /358b1fd0, with1766 identities/1411 groups retired,
empty KFD and unchanged/free original leases and model stat tuples. Mirrors
agree and Core receives closure before analysis.

## Private model integration

The [candidate](../config/q2-select-live-grid-model-source.json) changes three
private provider files: the executor passes a host-known slice extent only
when `prefill_phase` is true; the selector host launcher uses it for grid size.
Zero keeps the original capacity grid in decode, including captured replay.
No new buffers, streams, callbacks, public ABI or state format are introduced.
Local compilation confirms all164 device bodies/resources remain exact.

The model trial uses the saved native C client binary and reuses the retained
MMQ archive after binding its complete source and qualification. It replays
the original first nine full-prefill requests through32K, preserving the
preparation sequence and both8K attempts. Capacity133760, chunks2048, original
final tails, C1, zero prefix hits and eight-token replies are unchanged.
Only the new candidate is built/run. HOST39+39 passes on .157; frozen plan
55bf5bcb still requires a committed checkpoint and fresh GPU admission.
