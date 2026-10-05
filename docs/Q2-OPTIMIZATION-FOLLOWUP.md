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

Latest completed experiment: [eight-half output stores](Q2-DOWN-HALF-VECTOR.md)
measure1570.106384 PP /25.18915597 TG, a small nominal+0.201424% PP against
saved1566.950178. All720 guarded outputs,108 consumers and21 parent model
files are exact. Preserve both sources and the marginal gain; required PP
increase to fixed UD is now7.367062%. This experiment is no longer pending.
The new half-input consumer ownership proposal is listed below; it has no
implementation or GPU result yet. Inherited quality and full curves remain open.

Previous completed experiment: [paired-half down epilogue](Q2-DOWN-HALF-PAIR.md)
measures1566.950178 PP /25.19259094 TG,+1.271715% PP against saved1547.273268.
It restores/rounds in registers and transposes halves before paired stores.
All513 down outputs,99 consumers and21 saved parent model files are exact.
The required increase to fixed UD falls to7.583324%; inherited F16 quality
and full-curve parity remain open. This epilogue is no longer pending.
The remaining hypotheses below retain their status; no blanket rerun follows.

Previous update: [half expert-output storage](Q2-DOWN-HALF-STORAGE.md) completes
at1547.273268 PP /25.17198641 TG, nominal+2.394022%/+0.099966% against retained
1511.097261 /25.14684805.315 rounding checks and99 consumer checks pass.
All model tokens match but eight logits differ; max parentKL0.002693241666.
This is a faster numerically different experiment, with independent task quality
still open. Keep both sources; no production promotion. Fixed Q2/UD/input/timers
stay unchanged and the remaining throughput increase to UD is8.951478%.


This update supersedes the historical queue above. Before the half-storage experiment, best retained nominal Q2
prefill was1511.097261 PP /25.14684805 TG from the live-stage composition,
compared with its saved1509.852296 /25.20625148 four-lane parent. The new
comparison is+0.082456% PP/-0.235669% TG with overlapping historical PP ranges;
it does not establish a stable causal gain. Both sources remain available.
Original fixed Q2 remains1443.672867 and UD1685.777092. From that1511 parent,
reaching UD required11.559801% more throughput; the newer1547 result above
reduces the remaining requirement to8.951478%. The original exact2048/tg128 input/timers
remain fixed. No new runtime work is scheduled by this inventory; Q4 stays deferred.

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
| Measured negative: compact IQ2 gate/up producer | BM256 only for nonpacked BN64, same-wave gate/up and shared activation fetches across 128 logical rows. | Completed 84 exact component pairs and 21 exact parent model files. PP1494.649738 regresses 1.006890% against the saved1509.852296 parent. This experiment is no longer pending; all evidence is retained. |
| Measured negative: routed Q2 down output reuse | Change output-row BM128 to BM256 only for scaled BN48, keeping token routing width and original K order. | [Completed new candidate](Q2-DOWN-OUTPUT-REUSE.md):135 exact component pairs and21 exact parent model files. PP1501.068984 regresses0.581733% against saved1509.852296. Component time improves2.618742% at64 experts but regresses1.550516%/3.811054% at128/512. Preserve the source and distribution-specific result; no unconditional promotion or rerun. |
| Measured negative: whole short-expert tiles | BN48 for entire buckets1..48, with original128/64 elsewhere. | Completed39 exact GPU pairs and21 exact parent model files; actual192 model records retain45120 short48 descriptors. PP1493.009363 regresses0.806755% against best1505.152258. The original64 kernel already skips nonlive WMMA fragments, so this replacement does not reduce useful matrix operations for1..48. Retain evidence without promotion or rerun; exact <=16 counts remain absent. |
| High: routed Q2 down / expert consumer chain | Adapt DS4 fused SwiGLU/down or producer-Q8 consumer ideas to the active Qwen route, with logical640/stored768 tail handling and explicit activation arithmetic. | MMQ audit only. Existing fallback already shares routing/quantization and fixed2048 uses paired IQ2 WMMA instead. A real new dispatch/consumer is needed before a speed claim. |
| Measured negative: scaled-Q2 down activation stores | Apply unread-fragment store suppression to active scaled-down BN48/64, preserving BN16, final live16-row padding and the640/768 K tail. | The [new candidate](Q2-DOWN-LIVE-STAGE.md) completes with477 exact guarded output pairs and21 exact parent model files. PP1506.753016/TG25.15614684 changes-0.287489%/+0.036978% against saved1511.097261/25.14684805. Component changes are near zero. Preserve the result and keep the1511 parent; this test is no longer pending. |
| High: encoded Q8 dense loads | Diagnose load scheduling and compact weight layout for SSM/plain/attention, preserving native accumulation and original decode. | Grouped and K16 changes are measured; expanded F16 mirrors are exact but lose2.164926% model PP. Hardware bandwidth/cache/occupancy contributions remain unisolated. A new compact loader would be a new implementation. |
| Measured marginal: IQ2 live-stage store suppression | Compose the existing omission of unread activation-fragment stores with the current compact producer. | [New composition](Q2-IQ2-LIVE-COMPOSE.md) completes at1511.097261 PP /25.14684805 TG,+0.082456%/-0.235669% against saved1509.852296 /25.20625148. All21 parent files are exact. The old component's318 artifacts are reused without rerun. Preserve both sources and the marginal result; this model test is no longer pending. |
| Medium: HC combine/norm/materialization | Remove additional full-buffer passes or connect a consumer directly to a producer while preserving rounded feedback and per-chain accumulations. | Existing row reuse, F32 combine, deferred MoE norm and BK256 are already measured. Further fusion/lifetime changes require new complete-cycle checks. |
| New source proposal: half-input MoE consumer | Process eight hidden values per lane with two independent ordered F32 accumulation vectors, then preserve the existing shared row and all HC/norm arithmetic. | [Retained ISA review](../config/q2-half-consumer-vector-opportunity.json) confirms the current four-value consumer already uses64-bit expert loads. Eight-value ownership would reduce outer passes from three to two and may permit128-bit loads; register pressure and full-cycle timing remain untested. No implementation or speedup yet. |
| Exploratory: expert-output representation | Reduce or avoid the F32 per-expert output materialization before weighted combine. | The [saved buffer audit](Q2-GPU-DATAFLOW.md) identifies200MiB at the fixed shape. A direct consumer would need ordered combination. The [F16-storage candidate](Q2-DOWN-HALF-STORAGE.md) is now measured at1547.273268 PP:315 rounding checks,99 consumer checks and original model complete. Eight parent logits differ despite exact generated tokens; independent quality remains open. A direct ordered consumer that avoids the materialization entirely is still unimplemented. Logical bytes are not measured DRAM traffic or a promised gain. |
| Medium: wide shared-Q8 gate/up | Share one activation tile between both projections and emit the existing rounded SwiGLU output directly at M640/N2048/K2560. | Not implemented. Input quantization is already shared and raw-HC publishes its Q8 tile. DeepSeek's small-batch pair is not a working2048 implementation. |
| Lower: shared-down specialization | Test the actual M2560/N2048/K640 consumer with a shape-specific native/library path; any GPU-only mirror would cover only150MiB across48 layers. | Source proposal only. This small shape was excluded from the just-completed large-projection mirror experiment; a benefit is not presumed. |
| Integration: bounded reactive PLE preparation | Compose the measured two-slot lookahead with the current best provider and verify first-access/warm complete model behavior. | Earlier8K first-access gain is measured, but this best-provider composition remains unqualified. It addresses row I/O, not warmed GPU matrix time. |
| Separate decode/concurrency: Q8 GEMV and native batching | Measure useful native C2/C4/C8 grouping, complete-token throughput, C1 latency and memory. | Existing vector quantization caches are already covered. The outer C dispatcher does not establish profitable batching of the internal numerical executor; current fixed-point decode does not qualify the context/concurrency curve. |
| Separate decode: scalar HC up/mix fusion | Fuse the scalar projection with ordered mixing/injection while preserving reduction and injection-partial layout. | [Concrete eight-wave design](Q2-HC-DECODE-ATTRIBUTION.md) remains a proposal. The already measured wide HC up/mix fusion selects at least96 tokens and does not implement this scalar path. |
| Separate scheduling: GPU region admission and buffer ownership | Select complementary ready regions by measured resource demand and retain every buffer until its last GPU reader completes. Attribute route-map preparation/upload before considering a device-side replacement. | The naive two-stream shared/routed fork regresses PP; a general internal resource policy is not yet implemented/qualified. Existing count/event/CPU-map overlap is already present. Reclamation can reduce memory without proving a throughput gain. |
| Later: sparse indexer at high context | Reuse keys across query rows and distribute exact selection with deterministic rank/tie ordering. | Source-backed Halogen/GSQ hypotheses, no LIE runtime result. Selection is inactive at the fixed2048 point and cannot close that point's gap. |
| Later: attention K/V layout at high context | Compare packed K/V against direct gathers by actual sparse-attention shape, including packing cost. | Existing fused WMMA attention and mask-window compaction are already present. New layout/full-cycle qualification remains open; no fixed-point or high-context gain is inferred. |

The BM256/BN64 [IQ2 candidate is now measured](Q2-IQ2-WIDE-PAIR.md):
156 unchanged kernel bodies and one replacement with104→169 next-free VGPR,
17536→26752 LDS, zero private bytes and10→2 static block barriers.
Those static reductions did not become a model gain. PP samples are
1494.649738 /1494.661516 /1492.591920; TG median25.19840692. All13 commands
exit0/37 artifacts verify and the GPU window is released. No comparator rerun.

The first ownership repartition is [measured](Q2-IQ2-LANE-COMMIT.md), with81
exact component pairs,21 exact parent model files and all13 command exits0.
Its source is retained for the next composition; the original1505 parent stays
available. The distinct Q2 down BM256/BN48 experiment is also complete and
negative at the model level. Neither wider-output tile replaces the1509 base.
Both IQ2 and scaled-Q2 down store predicates now have completed original
fixed-model results above. Down-store omission does not improve the measured
model and does not replace the1511 parent. No rerun of either cycle is queued.

A [new retained-ISA Q8 review](../config/q2-q8-load-review.json) checks the
wide plain/SSM/attention bodies and finds128-bit global payload loads already
emitted. The34-byte encoding alone does not establish scalarized loads or a
new aligned-word saving. Hardware transactions/stalls remain unmeasured;
compact staging and smaller-LDS/tile families also have upstream negative
evidence. A further loader needs a concrete changed dataflow or measured
bottleneck, without relabeling existing vectorization as a missing mechanism.

The inventory also retains component-only IQ2 live-epilogue and prefill
codebook-LDS candidates, with mixed timing evidence and no complete-model
composition. They are lower-priority retained candidates, not untested
mechanisms. The older DeepSeek audit separately proposes codebook staging for
vector decode; its active Q8_1 path must be rechecked before preparing a port.
No blanket rerun of these cohorts or the nineteen-report recovery is scheduled.

Diagnosis remains distinct from implementation: hardware bandwidth, cache
misses and active-wave occupancy have not been isolated for the current best
provider. Existing traces can prioritize candidates but do not establish those
causes. Further source organization can separate decoding, staging, arithmetic
and lifetime ownership; an organization-only move must preserve instruction
bodies and is not itself a performance result.

The saved MoE diagnostic attributes254.797ms to IQ2 gate/up,188.349ms to Q2
down,293.725ms to Q8/F16 dense and211.530ms to HC combine/norm/inject. It
profiles the earlier1496.830907 provider, not a new baseline or the current
1509 source. It prioritizes work but cannot predict additive model gains.

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
