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
Only the new candidate is built/run. HOST39+39 passes on .157; plan55bf5bcb
is admitted under checkpoint560b2e36 at22:10:33.221435UTC /5f733e89.

## Completed model: no retained improvement

All nine original requests complete; streamed token pieces, replies, usage and
finish reasons match the saved retained provider. Every full prefix has zero
cached tokens and its original2048 chunks and final tail. One observation per
prefix is compared with the saved observation, without a new median or rerunning
controls. Both original8K calibration attempts remain visible.

| Depth / attempt | Retained PP tok/s | Candidate PP tok/s | PP change | Retained TG tok/s | Candidate TG tok/s |
|---|---:|---:|---:|---:|---:|
| 4K / 0 | 1512.809 | 1507.102 | −0.377% | 26.471 | 26.413 |
| 8K / 0 | 1511.203 | 1502.426 | −0.581% | 26.390 | 26.436 |
| 8K / 1 | 1476.051 | 1478.160 | +0.143% | 26.268 | 26.230 |
| 12K / 0 | 1445.125 | 1461.379 | +1.125% | 26.329 | 26.321 |
| 16K / 0 | 1435.354 | 1433.211 | −0.149% | 26.334 | 26.404 |
| 32K / 0 | 1402.246 | 1251.774 | −10.731% | 26.234 | 25.951 |

[Full precision and original timings](../config/q2-select-live-grid-model-results.json).
TG here covers the original eight decode calls, not TG128. No decode dispatch
or reactive scheduling changed. The component improvement does not establish
a whole-model benefit; retain the previous provider and do not expand this
candidate to64K/128K while its32K result remains unresolved. Preserve the
candidate and the small12K observation, without promoting it.

The [sampled telemetry](../config/q2-select-live-grid-model-thermal.json) also
differs: the approximate32K interval observes GPU clocks1997–2629MHz versus
2541–2682MHz in the saved run. CPU temperatures are lower in the candidate.
The intervals use a session/wall anchor with one-second padding and two-second
sampling. This does not isolate the cause of the32K regression, establish
throttling, or justify correcting/normalizing the measured rates. A future
diagnostic would reuse this candidate binary and preserve the workload.

The six model commands exit0. The launcher exits1 afterward because its new
MMQ receipt omitted the `archive` path required by existing postflight code.
The original failure/result is preserved. A separate read-only
[supplemental verification](../config/q2-select-live-grid-model-supplemental.json)
binds all12 collected artifacts and confirms the original/copied MMQ archive,
server/client binaries and model stat identity. The model is not rerun to
repair bookkeeping. Collection precedes22:15:00.076488UTC release1d62a3a5;
1782 process identities/1423 groups are retired, KFD empty and leases unchanged.

The receipt is corrected for future launches. A regression test exercises the
existing postflight's archive-path/hash contract with private files. Fresh
.157 HOST39+39 passes, seven artifacts collect, and its seven additional
process identities/six groups are confirmed retired at22:20:25.329174UTC.

## Matched original-32K replay prepared — 2026-10-07 UTC

The separate-session32K model regression coincided with a median reported GPU
clock of2439.5MHz for the candidate versus2648MHz for the saved retained arm.
That is a confound, not a correction to either recorded rate. A bounded A-B-B-A
replay uses the **same original32711-token case**, preceded each time by the
same three original preparation requests. It reuses the saved retained server
`9993fdce`, live-grid server`b608798b` and native C client`87d856cf` without
rebuilding. Capacity133760, chunk2048, C1 AR, zero prefix-cache hits, the
original output budget and the model bytes are fixed. The four fresh servers
start only after CPU cooldown to60°C; two-second clock/temperature
telemetry is retained with every arm. This is one diagnostic comparison at32K,
not a new curve or a128K gain claim.

The [frozen plan](../config/q2-select-live-grid-pair-plan.json) binds the exact
selected request hash`200e66bd` and prior release`2ac6b4de`. The runner
validates its own hash, both binaries, client, requests, original model stat
tuples, retired process groups, empty KFD, five original leases and the latest
registry event. Its saved-result parser accepts the original four-case replay
and rejects a changed request or cached-token count in offline tests. Fresh
Core non-use and read-only .157 preflight at07:40:10 confirm1941 retired
identities,1547 groups, seven unchanged model files, five free leases and empty
KFD. The staged runner's remote `verify` exits0 at07:44:58 with no GPU
admission. A fresh explicit window admission, run, artifact collection and
release are still needed before interpreting the pair.
