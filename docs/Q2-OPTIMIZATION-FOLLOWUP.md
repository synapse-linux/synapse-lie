<!-- SPDX-License-Identifier: MIT -->
# Focused optimization queue after shared-Q8 component timing

The fixed model comparator remains exact2048, original direct-executor input
and timers: Q2 PP1443.672867 / UD1685.777092. PP/TG parity over the requested
curve remains the goal. No context-curve expansion is admitted while the fixed
point has a large gap. Marginal candidates remain retained for measured
composition rather than deleted.

The completed [shared-Q8 cycle](Q2-SHARED-Q8-PRODUCER.md) saves2.01–2.08% of
component time against both unchanged controls. Its independent GPU format
fixture still fails; all production reference/candidate buffers match. These
facts are separate from model throughput and independent quality acceptance.

| Priority | Mechanism | Current evidence and next boundary |
| --- | --- | --- |
| 1 | Independent Q8 format/store diagnosis | Replay the retained failed arrays with explicitly ordered initialization on the nonblocking oracle stream; preserve production source, FP32 arithmetic and existing gates. The possible default-stream memset race is not yet causally tested. |
| 2 | Specialized original-F16 HC-down staging | Explore bounded native-vector loads, wider K pieces and a direct epilogue while preserving original accumulation boundaries; compare the actual retained library consumer and preparation cost. Generic coalesced/tile probes already have negative or inconclusive results. |
| 3 | Eight-value IQ2 producer partition | Test weight-fetch/decode partition and compact codebook representation without repeating the earlier packed-sign WMMA probe or substituting BF16 arithmetic. Prefetch and mixed compact routing already exist. |
| 4 | Paired wide shared-Q8 gate/up | Input quantization is already shared; a paired kernel must improve the full gate/up/SwiGLU/down cycle, including register/resource effects. |
| Later, after point parity | Cross-query indexer-key reuse and distributed exact top-k | Current scoring reloads keys per query and selection uses one workgroup per query. Preserve dot reductions, rank and tie ordering. Selection is inactive at the fixed2048 point and cannot fix that point's deficit. |

The [retained diagnostic profile](Q2-SCALED-LIBRARY-PROFILE.md) attributes70.29%
of net extra prefill GPU time to preparation plus HC down. It describes that
measured composition, not a fresh current-provider trace. More scheduler
callbacks cannot remove this work. PLE read overlap, serving concurrency and
single-request kernel throughput keep distinct evidence.

The existing provider already compacts sparse attention tiles across mask
windows, shares activation quantization between shared-expert gate/up, and
limits predictor FFN work after draft KV catch-up. These are not missing
optimizations. Packed sparse layouts or changed softmax tile ordering require
their own numerical and full-cycle qualification.

The private read-only research snapshot, pinned source inventories and the
external positive/negative results are retained under local
`evidence/external-optimization-audit-20261004/`. No external code, dependency,
host setting or service was changed. Qualified whole-model control-binary
replay is implemented and CPU checked, but the owner now requests using
retained controls without rerunning them. Component controls already share
one binary. The [two new retained compositions](Q2-REAUDIT-COMPOSITION.md)
measure1451.924906 /1452.143206 PP without changing the fixed input/timers.
Row reuse remains model-exact; added norm reproduces the previous norm logits.
The fixed-point PP gap remains13.86%; the complete curve stays deferred.

## Current remaining work — 5 October 2026

This update supersedes the historical queue above. Best retained Q2 is now
1505.152258 PP /25.15493858 TG. Original fixed Q2 remains1443.672867 and
UD1685.777092; reaching that UD PP requires12.000436% more throughput from
the best. The original exact2048/tg128 input/timers remain fixed. No new
runtime work is scheduled by this inventory; Q4 remains deferred.

The independent Q8 initialization race is already diagnosed and corrected.
Raw-HC Q8 publication, row reuse, native HC-down BK256 and MoE-only deferred
norm are already included in the measured best lineage. Routing-selective down
tiles were measured separately and are not in the1505 base. The nineteen-report
recovery has zero selective integrations pending.
IQ2 half staging/high-byte representation/raw prefetch/sign masks/large table,
Q8 grouped loads/K16 phases and large persistent F16 mirrors all have retained
component and full-model results. Their existing cohorts need no rerun.

| Priority / region | Actual remaining experiment | Current boundary |
| --- | --- | --- |
| High: compact IQ2 gate/up producer | Assess an actual fetch/decode ownership repartition while retaining compact staging and accumulation boundaries. | Eight-/sixteen-value commit lifetime variants are now measured:81 exact component pairs and21 exact parent model files each, but PP1493.182914/1500.783083 regress0.795225%/0.290281%. Allocated VGPR remains unchanged. These do not implement lane repartition; existing cohorts need no rerun. |
| Measured negative: whole short-expert tiles | BN48 for entire buckets1..48, with original128/64 elsewhere. | Completed39 exact GPU pairs and21 exact parent model files; actual192 model records retain45120 short48 descriptors. PP1493.009363 regresses0.806755% against best1505.152258. The original64 kernel already skips nonlive WMMA fragments, so this replacement does not reduce useful matrix operations for1..48. Retain evidence without promotion or rerun; exact <=16 counts remain absent. |
| High: routed Q2 down / expert consumer chain | Adapt DS4 fused SwiGLU/down or producer-Q8 consumer ideas to the active Qwen route, with logical640/stored768 tail handling and explicit activation arithmetic. | MMQ audit only. Existing fallback already shares routing/quantization and fixed2048 uses paired IQ2 WMMA instead. A real new dispatch/consumer is needed before a speed claim. |
| High: encoded Q8 dense loads | Diagnose load scheduling and compact weight layout for SSM/plain/attention, preserving native accumulation and original decode. | Grouped and K16 changes are measured; expanded F16 mirrors are exact but lose2.164926% model PP. Hardware bandwidth/cache/occupancy contributions remain unisolated. A new compact loader would be a new implementation. |
| Medium: HC combine/norm/materialization | Remove additional full-buffer passes or connect a consumer directly to a producer while preserving rounded feedback and per-chain accumulations. | Existing row reuse, F32 combine, deferred MoE norm and BK256 are already measured. Further fusion/lifetime changes require new complete-cycle checks. |
| Medium: wide shared-Q8 gate/up | Share one activation tile between both projections and emit the existing rounded SwiGLU output directly at M640/N2048/K2560. | Not implemented. Input quantization is already shared and raw-HC publishes its Q8 tile. DeepSeek's small-batch pair is not a working2048 implementation. |
| Lower: shared-down specialization | Test the actual M2560/N2048/K640 consumer with a shape-specific native/library path; any GPU-only mirror would cover only150MiB across48 layers. | Source proposal only. This small shape was excluded from the just-completed large-projection mirror experiment; a benefit is not presumed. |
| Integration: bounded reactive PLE preparation | Compose the measured two-slot lookahead with the current best provider and verify first-access/warm complete model behavior. | Earlier8K first-access gain is measured, but this best-provider composition remains unqualified. It addresses row I/O, not warmed GPU matrix time. |
| Separate decode/concurrency: Q8 GEMV and native batching | Measure useful native C2/C4/C8 grouping, complete-token throughput, C1 latency and memory. | Existing vector quantization caches are already covered. The outer C dispatcher does not establish profitable batching of the internal numerical executor; current fixed-point decode does not qualify the context/concurrency curve. |
| Separate scheduling: GPU region admission and buffer ownership | Select complementary ready regions by measured resource demand and retain every buffer until its last GPU reader completes. Attribute route-map preparation/upload before considering a device-side replacement. | The naive two-stream shared/routed fork regresses PP; a general internal resource policy is not yet implemented/qualified. Existing count/event/CPU-map overlap is already present. Reclamation can reduce memory without proving a throughput gain. |
| Later: sparse indexer at high context | Reuse keys across query rows and distribute exact selection with deterministic rank/tie ordering. | Source-backed Halogen/GSQ hypotheses, no LIE runtime result. Selection is inactive at the fixed2048 point and cannot close that point's gap. |
| Later: attention K/V layout at high context | Compare packed K/V against direct gathers by actual sparse-attention shape, including packing cost. | Existing fused WMMA attention and mask-window compaction are already present. New layout/full-cycle qualification remains open; no fixed-point or high-context gain is inferred. |

The first ownership repartition is now [prepared](Q2-IQ2-LANE-COMMIT.md):
four lanes share raw groups and publish their eight-value slices into the
unchanged compact staging. Its next-free VGPR grows8 with no LDS/private change;
GPU component and model evidence remain pending. The static change is not a gain.

The saved MoE diagnostic attributes254.797ms to IQ2 gate/up,188.349ms to Q2
down,293.725ms to Q8/F16 dense and211.530ms to HC combine/norm/inject. It
profiles the earlier1496.830907 provider, not a new baseline or the current
1505 source. It prioritizes work but cannot predict additive model gains.

Independent task quality remains open: Core-19 has only a partial historical
run, not a complete matched result for the retained variants. Complete current
PP/TG context-curve qualification remains deferred until the fixed-point gap
closes. These are qualification tasks, not measured kernel speedups. Preserve
safe numerical failures and run only new candidates with saved references.

[MMQ adaptation audit](Q2-MMQ-REUSE-AUDIT.md),
[shared-Q8 shape audit](Q2-DEEPSEEK-SHARED-PREFILL.md),
[dataflow/ownership review](Q2-GPU-DATAFLOW.md),
[saved operator attribution](Q2-FIXED-MOE-PROFILE.md),
[latest negative mirror result](Q2-Q8-MIRROR.md),
[new measured IQ2 commit variants](Q2-IQ2-SLICE-COMMIT.md),
[retained short-expert routing audit](../config/q2-iq2-tail-audit.json).
