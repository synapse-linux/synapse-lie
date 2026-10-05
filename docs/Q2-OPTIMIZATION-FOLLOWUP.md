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

The inventory below separates unimplemented mechanisms from component-only
candidates and measured features awaiting integration. Latest retained original
exact2048/tg128 wave-packing result is1574.505432 PP /25.17589001 TG; saved shared
pair1573.621201/25.11363913 and earlier sources remain available. The nominal
PP gain is0.056191% with overlapping historical ranges; scalar decode is unchanged.
Fixed UD1685.777092 requires7.067086% more PP from the new candidate. Q4 stays deferred. No qualified
control rerun or context-curve expansion follows this update.

| Region | Remaining concrete work | Status / priority |
| --- | --- | --- |
| Compact expert producer layout | Write compact expert-major rows in gate/up, preserve wave packing, then consume contiguous rows in down. | [Completed experiment](Q2-COMPACT-EXPERT-CHAIN.md): 96 exact numerical pairs, independent routing/packing pass, 21 exact parent files; model 1572.956730 PP (-0.098361%). Full-chain component time +0.287% balanced / +0.413% skew. Preserve; keep 1574. This trial is no longer pending. |
| Active routed expert chain | Adapt producer-Q8 or fused SwiGLU/down to the actual WMMA route, preserving logical640/stored768 tails and documenting arithmetic changes. | Source audit only; high. Existing fallback routing/quantization reuse is already present. |
| Measured marginal: active-chain activation packing | One wave per complete640-value row, eight rows per CTA; preserve row maximum and scaled-half contract. | [Completed candidate](Q2-SCALED-WAVE-PACK.md):52 exact component pairs,21 exact parent model files; packing/down time-0.632%, model1574.505432 PP nominal+0.056191% with overlapping ranges. Scalar oracle exit1 retained and fully attributed to signed zero in both arms. This trial is no longer pending; full producer fusion remains open. |
| Active-chain activation traversal | Pack scaled half rows in existing expert order, then read contiguously in down. | [Completed experiment](Q2-SCALED-EXPERT-ORDER.md):107 exact component pairs,cycle-4.745%; model1571.009498 PP (-0.222034%) and21 exact parent files. Preserve variant; keep1574. This test is no longer pending. |
| Expert-output consumer | Feed ordered weighted combine directly, avoiding the remaining100MiB F16 intermediate at2048. | Unimplemented; high. Half storage and vector stores are already measured. Logical bytes do not establish DRAM savings. |
| HC combine/norm consumers | Remove additional buffer passes through a real producer/consumer fusion, potentially with a deferred-Q8 consumer. | New design needed; high. Ordinary deferred normalization already lost10.292% complete-cycle time; only MoE deferred norm is retained. |
| Encoded Q8 dense loading | Change compact load/staging dataflow for SSM/plain/attention after attributing transactions, cache and wave occupancy. | Open investigation; high. The aligned-pair trial is now complete and negative, not pending. |
| Measured marginal: wide shared-Q8 gate/up | Pair corresponding gate/up row tiles inside each wave and emit rounded SwiGLU directly at M640/N2048/K2560. | Completed:43 component pairs/24 sampled FP64 checks/21 parent model files pass. Component cycle time-3.309%; original model1573.621201 PP is nominal+0.121187% with overlapping ranges. Retain both sources; this trial is no longer pending. No reduction of total activation tile fetches is claimed. |
| Small shared-down | Shape-specific native/library path at M2560/N2048/K640; any GPU F16 mirror is bounded to150MiB across48 layers. | Source proposal; lower. This shape was excluded from the failed large-mirror trial. |
| IQ2 component candidates | Selectively compose live-epilogue or prefill codebook-LDS variants with the current provider. | Components already tested with mixed/marginal timings; current full-model composition unqualified. No blanket rerun. |
| PLE/ngram preparation | Compose the measured two-slot lookahead with saved1571 and check first-access/warm behavior. | Integration pending. Historical8K first-access10.982→7.791s; warm gain0.57%, not a warm GPU-matrix gain. |
| Scalar HC decode | Fuse up projection with ordered mix/injection using the retained eight-wave design. | Unimplemented proposal; separate decode work. |
| IQ2 vector decode | Stage the2KiB codebook in LDS while preserving Q8_1 activations. | Source proposal; barrier/cache tradeoff unmeasured. Distinct from prefill codebook experiments. |
| Q8 GEMV and batching | Qualify native C2/C4/C8 useful-token throughput, C1 latency and memory with the current numerical executor. | Unqualified. The outer reactive dispatcher and existing quantization caches do not establish a numerical batching gain. |
| GPU scheduling and buffer lifetimes | Resource-aware region admission, last-reader retirement, and critical-path attribution of CPU route-map/upload before a device port. | General policy unimplemented/unqualified. Naive shared/routed two-stream overlap already regressed1.029%. |
| Long-context indexer | Reuse keys across queries and distribute exact top-k with deterministic ordering/ties. | Source-backed proposals; after fixed-point parity. Selection is inactive at2048. |
| Long-context attention | Compare packed K/V with direct gathers including packing cost. | Unqualified new layout; after fixed-point parity. Fused WMMA attention and mask-window compaction already exist. |
| Diagnosis and source organization | Isolate hardware bandwidth/cache/active-wave limits; further separate decode, staging, arithmetic and buffer ownership without changing instruction bodies. | Current stage trace complete; hardware attribution and further organization remain. Neither is a measured throughput gain. |
| Acceptance | Complete independent Core-19 quality, then qualify the retained provider over the requested PP/TG context curve after the point gate. | Open qualification, not kernel optimization. F16 lineage differences remain. |

The [saved1571 current profile](Q2-CURRENT-BEST-PROFILE.md) now completes with
zero GPU builds/control reruns and exact saved prefill logits/first16 tokens.
Its prefill totals1321.833498ms kernel work in1326.923958ms: Q8/F16 dense293.227ms,
IQ2 gate/up239.500ms, HC combine/norm186.168ms and Q2 down161.558ms. The older1496
trace remains historical. Decode15-call busy/span is86.971%; bandwidth/cache/
active-wave attribution is still unisolated. This closes the profiling proposal
below without changing original1571.716479 PP/25.20732109 TG or the curve gate.
It profiles the saved parent, not the subsequently measured shared-pair provider.

The compact producer experiment now closes the follow-up suggested by the
negative expert-order trial. Both changed traversal mechanisms are measured;
neither adds a model gain to saved 1574. Full-chain component timings include
routing and gate/up, unlike the preceding packing/down scope. These results
prioritize eliminating actual intermediate passes (active producer-Q8/fused
down, ordered expert consumption, HC materialization) over another equivalent
row-ordering trial. They do not isolate a bandwidth/cache/occupancy cause.

The [wave-packing disposition](../config/q2-scaled-wave-pack-disposition.json)
retains1574.505432 PP for the next measured composition alongside saved1573/1571.
All128 model tokens and complete parent files match, while inherited F16
independent task quality remains open. The remaining high-priority work is
active routed-expert producer/consumer fusion, direct ordered combination and
HC materialization; current hardware bandwidth/cache/occupancy causes remain
unisolated. Marginal component/model gains are not summed into an invented rate.

The [aligned-pair Q8 fetch trial](Q2-Q8-ALIGNED-PAIR.md) is now complete:
102 exact component pairs and21 exact parent model files, but1496.176691 PP /
25.17052112 TG, nominal-4.806197% PP versus saved1571. Component times increase
10.840–16.393%. Preserve this negative candidate and keep1571 as the base.
The source-only opportunity record remains historical; this mechanism is no
longer pending. Hardware transaction/cache attribution remains unisolated.

Previous completed experiment: [fixed-width half consumer](Q2-HALF-FIXED-WIDTH.md)
measures1569.533792 PP /25.16043516 TG, nominal-0.138873% PP against saved1571.716479.
The candidate is preserved and1571 remains the base.105 residual outputs are
exact,93 scale/61 normalized-half outputs differ (max2/1ULP); generated model
tokens match while eight logits change, max parentKL0.007411541178. All42
component timings and model performance are retained despite numerical failure.
This experiment is complete. A38% static instruction reduction does not improve
the complete model; prioritize changed data movement over further generic
index simplification. The saved-best diagnostic proposal has since completed
as recorded above. Existing1496 stage costs remain historical, not a current
profile or a throughput baseline.


Previous completed experiment: [eight-value half consumer](Q2-HALF-CONSUMER-EIGHT.md)
measures1571.716479 PP /25.20732109 TG, nominal+0.102547% against saved1570.106384.
Historical sample ranges overlap; preserve both sources and the marginal result.
All105 component comparisons and21 parent model files are exact. Reaching fixed
UD still requires7.257073% more PP. The consumer experiment is no longer pending;
the separate fixed-width experiment is now completed above.


Previous completed experiment: [eight-half output stores](Q2-DOWN-HALF-VECTOR.md)
measure1570.106384 PP /25.18915597 TG, a small nominal+0.201424% PP against
saved1566.950178. All720 guarded outputs,108 consumers and21 parent model
files are exact. Preserve both sources and the marginal gain; required PP
increase to fixed UD is now7.367062%. This experiment is no longer pending.
The half-input consumer result above supersedes its earlier preparation status. Inherited quality and full curves remain open.

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
| Measured marginal: half-input MoE consumer | Process eight hidden values per lane with two independent ordered F32 accumulation vectors, then preserve the existing shared row and all HC/norm arithmetic. | [Retained ISA review](../config/q2-half-consumer-vector-opportunity.json) confirms the current four-value consumer already uses64-bit expert loads. Eight-value ownership would reduce outer passes from three to two and may permit128-bit loads; Local compilation preserves VGPR84/LDS10368 and160 other kernels exactly.105 component comparisons and21 parent model files are exact; original-model1571.716479 PP is nominal+0.102547% with overlapping ranges. Preserve both sources; this model test is complete. |
| Measured negative: fixed-width half consumer | Make the existing wrapper-only hidden2560 contract explicit inside the kernel to simplify integer indexing and bounds. | [Current source/ISA review](../config/q2-half-consumer-fixed-width-opportunity.json) retains generic divisions despite the fixed wrapper. The [new candidate](Q2-HALF-FIXED-WIDTH.md) completes with1763 to1093 static instructions but1569.533792 PP (-0.138873%). Scale/half outputs and eight model logits differ despite matching tokens. Preserve all evidence and keep1571 parent; no rerun queued. |
| Exploratory: expert-output representation | Reduce or avoid the F32 per-expert output materialization before weighted combine. | The [saved buffer audit](Q2-GPU-DATAFLOW.md) identifies200MiB at the fixed shape. A direct consumer would need ordered combination. The [F16-storage candidate](Q2-DOWN-HALF-STORAGE.md) is now measured at1547.273268 PP:315 rounding checks,99 consumer checks and original model complete. Eight parent logits differ despite exact generated tokens; independent quality remains open. A direct ordered consumer that avoids the materialization entirely is still unimplemented. Logical bytes are not measured DRAM traffic or a promised gain. |
| Measured marginal: wide shared-Q8 gate/up | Pair corresponding projections and emit the existing rounded SwiGLU output directly at M640/N2048/K2560. | [Completed result](../config/q2-shared-q8-pair-model-results.json):1573.621201 PP, nominal+0.121187%, exact parent files and retained overlapping ranges. This test is no longer pending. Input quantization was already shared. |
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
