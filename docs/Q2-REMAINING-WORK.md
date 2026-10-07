<!-- SPDX-License-Identifier: MIT -->
# Current Q2 optimization assessment — 7 October 2026

The [four-key value layout](Q2-ATTENTION-V-TILES.md) now has a completed
original-model trial: 1332.109243 PP / 26.037992 TG, versus retained
1337.972303 / 26.101627. All four outputs are exact, but -0.438205% PP is
not a measured model gain. Keep R3 and preserve the positive component
separately. Bounded expert-scratch reuse and its 232 Debug/ASan contract
checks are complete; no pending model trial or GPU reservation remains.

Owner priority: focus new work on prefill, preserving original input,
2048-token chunks and retained model comparisons. Keep any improvement that
benefits only decode behind its decode dispatch; do not require a prefill win
or apply it globally. The [planar Q8 component](Q2-DECODE-Q8-PLANAR.md) now
retains vocabulary/SSM candidates separately while rejecting its shared gated
and attention-output shapes. No new decode model test is scheduled.

The unchanged four-row Q2 candidate now completes after the owner restores
performance/120 W:1337.972303 PP /26.101627 TG on original130925/8, versus
retained HC1337.119965 /25.914406 (+0.064% /+0.722% observed). All four
replies match. The earlier low-power post-reboot sample remains separate;
its recovery is not a kernel speedup. Power/fans verify before/after. All36
artifacts collect before verified released74a7eaa; no Q2 remote window remains.
The active goal needs another10.569963s off complete prefill and4.978455ms
off each measured decode call. [Full comparison](Q2-DECODE-DOWN-ROWS.md).

The IQ2 codebook-LDS candidate is now measured on the original model:
1338.152114 PP /26.087829 TG, all four replies exact. Its incremental
+0.013439% PP /-0.052859% TG is effectively flat; retain the four-row reference.
[Completed trial](Q2-IQ2-DECODE-LDS.md). Selector query LDS is also measured
and slower; exact8x8 key tiling fails the continuous diagnostic in all24 pairs.
Neither selector variant is integrated and neither remains a pending trial.
[Selector evidence](Q2-SELECT-QUERY-PAIR.md).

The latest [decode padding component](Q2-DECODE-DOWN-LIVE.md) preserves517
complete outputs and passes1034 independent checks while reducing complete
quantizer/down latency46.047198→45.728529us (-0.692049%, six of six pairs).
Keep its bound single-file patch for phase-specific composition; original-model
validation is pending. Its small operator saving must not be presented as the
same percentage of whole decode or as a route that closes the4.978455ms gap.

The [original128K GPU attribution](Q2-NATIVE128-GPU-PROFILE.md) now completes
on unchanged R3 with positive176014 kernel/4187 copy/481972 API durations and
exact CSV/ROCPD timestamp agreement. Completed-call analysis excludes loading,
preparation and post-forward KV copies. Dense GEMM23.017s, HC20.285s and
IQ2experts14.222s lead absolute prefill costs; attention11.668s and selection
3.625s account for most growth with position. Decode Q8 GEMV is17.380ms per
forward,48.26% of kernel time. A genuinely new compact, lossless Q8 operand
loader and complete attention-path changes deserve screening against the
retained negative variants. No speedup is inferred from this cost ranking.
Steady external submission gaps average0.125ms, far below the4.978ms target
gap; reactive work needs an internal measured dependency opportunity.
The client succeeds but profiled server shutdown times out(-9), a remaining
observability/lifecycle defect. All44 files verify before20:04:00 release
0a924578 and20:04:35 strong closure. No GPU reservation or changed reference.
Do not rerun rejected tiles/mirrors, saved throughput controls, Q4 or the full
curve as a substitute for a different implementation.

The [Q2_K scalar-down component](Q2-DECODE-DOWN-ROWS.md) now gives a
four-row candidate with6.96% less complete quantizer/down latency; the
eight-row version is31.71% slower. All1359 independent checks pass, while
898/906 exact replays differ by small finite values. Preserve exit1 and the
successful timings. Its original-input model observation is recorded above;
do not extrapolate the component's6.96% saving to whole-model decode or
claim independent quality acceptance.

Latest isolated HC qualification: original130925/8 is1337.119965 PP /
25.914406 TG, versus saved1310.874605 /25.344213; all four outputs exact.
The candidate isolates scalar -g0 compilation while918 common numerical
GPU functions retain exact original bytes. Two diagnostic functions differ;
common sizes/resources match. Its64-exact/50-FP64 component retains the
19.16%/4.74% operation savings. Earlier global Release observations remain
build-confounded, and the intervening all-g HC result was1335.257764/24.825466.
No repeated controls or revised input are needed to preserve those records.

The scalar down/SiLU fusion is now measured: component latency improves
5.67% alone and3.09% through the full HC consumer, with70 exact/24 FP64
checks. The unchanged original128K model result1332.307970/25.595276 does
not improve the retained up/mix result. Preserve the component for composition;
do not promote it or repeat controls. The subsequent
[Q8 SSM BK4 staging trial](Q2-SSM-BK4.md) passes72 exact/144 FP64 checks,
but complete-operator latency increases47.66%; it is not integrated. Both
variants allow one theoretical block per multiprocessor despite170 versus220
registers. Do not repeat this geometry or extrapolate register savings to speed.

[Phase-specific routing](Q2-PHASE-DISPATCH.md) retains the prefill body even
for a one-token tail; the scalar logits head has its own qualified operation.
No new full curve is justified. Eight output calls are not sustained TG128;
inherited task quality and30TG/1500PP remain open. No extra requantization
counts toward the goal.

The owner requires performance gains without quality degradation. The
[quality audit](Q2-QUALITY-PRESERVING-STATUS.md) makes the inherited F16
intermediate differences explicit: retained1587/1310 observations cannot be
reported as proven quality-preserving gains over the original reference.
New scalar HC up/mix work retains original weights/precision and requires
exact complete component replay before an original-model trial. The .157
component now passes64 exact pairs and50 independent checks; complete
operation time improves19.41% with injection and4.76% without. The subsequent
original2048/tg128 model reaches26.24707057 decode (+4.469512% versus saved
25.12414406), with all21 parent files and nine internal replays exact. Its
prefill1571.380247 is1.039950% below saved1587.893545; retain both binaries.
The same provider now reaches26.825569 TG on the original native32K workload,
versus saved26.250492/26.253731 using the same sequence (+2.19%/+2.18%). All
four responses/token sequences match. Native PP1419.137366 regresses0.52% /
0.26% against those controls; the earlier full-curve1402.245716 remains visible
with its different preceding sequence. Reuse this native binary for the
original130925-token request next; do not infer sustained TG128, native128K
rates or independent parent-quality qualification from the eight-output32K case.

The active goal is now **C1 AR decode30 token/s and complete prefill at least
1500 token/s through the original130925-token input**. The old fixed-point UD
parity objective is paused, not completed. Preserve its reference below, but
do not prioritize it over the new long-context goal or replace the long-prefix
measurement with a2048-token continuation. The retained128K observation is
1310.874605 PP /25.344213 TG; TG is the original eight output calls, not TG128.
Prefill must fall from99.876067s to at most87.283333s, a12.592734s saving.
The [Halogen transfer audit](Q2-HALOGEN-TRANSFER.md) records public source
clues and the actual48-layer route counts. Its private 256-token IQ2 probe
passes exact C17 coverage and GPU output checks, but the .157 component
regresses2.4–3.7% on three saved routing layers. Its242 VGPR/42,112-byte LDS
footprint plausibly raises occupancy pressure. Keep production on the retained
128/64-token path. No complete-chain or model throughput result was produced.
The separate live-grid selector's [matched original32K A-B-B-A
trial](Q2-SELECT-LIVE-GRID.md) gives only +0.478% mean prefill rate with
exact outputs. It does not establish a 128K saving and remains unpromoted.

The [completed native32K diagnostic](Q2-LONG-PROFILE.md) rejects all zero
GPU timestamps and uses valid CPU intervals only. It identifies45–70ms gaps
before PLE uploads and depth-dependent attention-completion intervals. Warm
C1 completion-to-next-submission gaps are only0.092–0.097ms; the older direct
harness's5.33ms/token gap is not native-server headroom.
The [completed original128K diagnostic](Q2-LONG-PROFILE.md) now extends the
same host-boundary view to all64 unchanged prefill chunks. Its twelve full-
attention boundaries rise437.4→591.1ms/chunk across the first/last quartiles;
other linear boundaries are near890→908ms/chunk. Every full-attention
boundary shows depth growth, but each includes previous-layer MoE/shared and
current-layer attention/HC work. All GPU device timestamps are invalid zero.
Flattening the instrumented boundary trend to the first-quarter mean accounts
for only about5.40s of a12.59s target gap, so a baseline complete-chain gain
is still needed. The older PLE gap does not grow late in this128K trace.

The [new BF16 exact-row candidate](Q2-PLE-ROW-BYTES.md) improves the original
32K full prefill from1402.245716 to1440.767919 token/s (+2.747%) with identical
replies. Smaller prefixes are mixed, including regressions. The new64K/128K
observations also regress:1369.779064/1296.437473 PP, −1.343%/−1.101% versus
saved retained. All replies match. Preserve the reader as a closed experiment
and keep the earlier provider; do not continue its full-curve testing.
The complete2048-row attention staging component is closed: exact outputs,
no convincing latency benefit, no model trial. The new C1 partition selector
keeps local top512 candidates across nine4096-block slices before an exact
merge;36KiB bounded scratch and lower-index ties. The .157 GPU component
passes all56 full-mask/CPU-sort pairs. Its128K median latency falls48.549 to
37.660us(-22.429%);32K/64K regress55.108%/15.720%. Preserve it for a bounded
deep-only integration with live GPU position, scratch ownership and an original
native-model trial. It is not a measured token-rate gain. Attention staging
and selector results do not close the1500PP/30TG goal. The next larger prefill
mechanism remains active expert-chain or dense projection operand reuse.
This does not alter prefill chunking or ranking. The ordinary greedy path already runs at temperature0; a GPU argmax
could reduce full-logit downloads, but needs correct snapshot/logprobs and
multi-sequence ownership before it is a usable decode optimization.

The scalar Q8 instruction trial is complete: large projections are unchanged
within noise, shared-down improves2.30% locally and gated shared-up slows3.06%.
There is no new model-level speedup. Multi-request batching and reactive
responsiveness are separate from the C1 goal; they cannot count as30 token/s.

Halogen's same-engine short-context serial comparison gives a useful decode
mechanism:35.4 token/s on its 4-bit dense checkpoint versus25.4 on a
losslessly repacked UD-IQ4_XS GGUF with 8-bit dense layers. It attributes the
gap to about2GB extra weights read per token. LIE's large Q8 GEMV components
already complete near222–228GB/s of logical traffic, so repeating scalar
instruction reductions has a weak chance of saving the required5.3ms per
native32K C1 step. The next C1 investigation should first account for actual
weight bytes and completed per-family time at unchanged32K and long-depth
inputs. The original antirez Q2 file has no native Q5 tensors. The later
[lossy shared-down Q5 overlay trial](Q2-DENSE-DECODE-FEASIBILITY.md) improves
exact2048 direct decode only0.0975% while changing final logits7.7198% RMS;
it is rejected. The owner's performance tally excludes quality-reducing
re-quantization. Subsequent C1 work stays on the original Q8/IQ2/Q2_K
representations. Halogen's rates cannot be credited to the retained Q2 file.
Its 16K/32K prefill-arena result
also cannot justify changing LIE's fixed2048-token comparison chunks.

The new [bounded dense-Q8 screen](Q2-DENSE-DECODE-FEASIBILITY.md) counts3.897GB
of encoded Q8 tensors and finds every sampled block requires eight code bits
for simple lossless per-block range packing. A hypothetical Q6 cut saves at
most0.917GB of those bytes while introducing2.26–2.62% sampled weight-domain
RMS error; even perfect traffic removal at228GB/s covers only about4.02ms of
the native32K step's5.27–5.35ms gap. No compressed kernel or model change is
qualified. Keep the remaining non-Q8 decode stages in the optimization scope.

## Mechanisms to test next at the fixed long-prefix input

The prefill target needs12.592734s less at130925 tokens. Prioritize a complete
2048-row routed-expert chain experiment: the current IQ2 gate/up path already
pairs projections, but still materializes a packed scaled-half plane before Q2
down. Its existing whole640 producer/pack replacement was11.08% slower in the
mixed component, so a new candidate must reduce repeated expert-weight reads
or increase useful row reuse across the complete chain. Measure actual routed
tile counts and weight traffic before choosing an altered layout. Keep current
quantization, exact prompt chunks and saved control binary.

The query-grouped selector scoring experiment is closed. The current
`SelectScoreKernel` loads a128-value key separately for each query row and
reuses it across four heads. A new four-query workgroup keeps that key resident
and preserves every FP32 score bit and top-512 mask in16 component pairs, but
its32K/128K median completed times are2.15x/4.09x the retained scorer.
The candidate raises VGPR use115→185 and removes parallel query workgroups.
Keep the original scorer; this design cannot justify a full-model trial.
The still-open higher-impact route is the complete routed-expert chain above.

The completed128K partition-selector component saves10.889us per **one-row
decode** selection. The original128K trace submits48 score/mark slices per
scored chunk,3024 across63 chunks, each with up to512 query rows. The earlier
8.36ms prefill extrapolation and a revised32.93ms multiplication are both
invalid because the component and trace have different row shapes. There is
no measured prefill saving from this component. Deep selector work may still
help one-row decode, but the existing evidence cannot count toward the
12.59s full-prefill gap.

## Historical fixed-point assessment (paused)

The preserved original fixed comparison is **1587.893545 PP versus
UD1685.777092 PP**. Closing it requires **74.889015 ms**, or5.806435% less
prefill time /6.164365% more throughput. Original exact2048 input,128 outputs,
127 timed decode calls, capacity9216 and all saved controls remain fixed.
The [complete saved-input prefill through 128K](Q2-FULL-PREFILL128.md) now
provides eight observations on the latest retained Q2, with zero cached tokens
and full 2048-token intermediate chunks. At 130925 tokens, Q2 measures
1310.874605 token/s versus archived UD 1253.555692, nominally +4.573%.
This does not replace the fixed comparison: the saved requests, capacities
and measured phases are different. Historical controls, one sample per input,
SSE transport and separate cooled 64K/128K sessions limit attribution.

The earlier 256K campaign remains inadmissible for historical comparison:
changing capacity changed sparse attention dispatch. Its results do not
replace either the fixed reference or the saved native-curve UD values.

## Next interventions, ranked after the complete prefill

1. **Dense Q8 operand reuse, especially the fused SSM projection.** The saved
   Q8/F16 region costs293.227ms, including160.218ms in that projection.
   Target active operand/accumulator work and useful block residency without
   an expanded permanent weight mirror. Register/LDS resources must be checked
   before one new model trial. Aligned-pair loaders, mirrors, row-group4,
   compact-LDS and pingpong variants are completed negatives, not new work.
   The unchanged BM256/BN128 wave-balance trial is now also closed:
   WM4/WN2 reduces logical LDS operand reads20%, but complete SSM component
   latency increases15.421% with all72 outputs exact. It provides no model
   gain and does not justify another wave-grid permutation by itself.
2. **A complete HC buffer-pass removal.** The saved combine/norm/injection
   region costs186.168ms. Remove an active read/write pass while preserving
   ten-expert reduction order, residual contributions and last-reader ownership.
   Raw-Q8 injection and ordinary RMS trials have already run; retain marginal
   candidates for measured composition without adding their percentages.
3. **Expert chain ownership beyond short-tail fusion.** The saved IQ2 gate/up
   plus Q2 down region totals401.058ms. The whole640 LDS integration now
   [completes](Q2-IQ2-WHOLE640.md): exact component/model outputs, but11.08%
   slower mixed-chain time and1576.766972 PP, −0.700713% versus retained1587.
   Keep the negative candidate. Another rearrangement of that same short-tail
   route is lower priority. A new design must improve active expert-weight or
   consumer reuse; removing the17.096-ms packing pass alone cannot close74.889ms.

These historical costs come from the retained 1571 diagnostic executable,
not a fresh profile of the current 1587 provider; regions may overlap.
They rank mechanisms, not predicted savings. The next numerical trial should
use one new complete-chain fixture and the unchanged exact-2048 model
comparison, reusing archived controls. Do not rerun the entire curve for each
small edit or prioritize partial-token routes to close the full-chunk gap.

Two separate objectives follow the fixed-point priority. For 256K, first
qualify the [attention capacity draft](Q2-ATTENTION-CAPACITY.md) against the
actual required capacity and visible span, without padding prompts or adding
unrequested context headroom. It has compilation and host checks, but no GPU
result. Historical direct-harness gaps were79.980ms across15 decode calls
versus5.090ms in prefill. The new native measurement above supersedes their
use as a claim about native C1 reactive headroom. Concurrent throughput,
request responsiveness and single-stream token latency remain separate.

## Why the last attempts were too small

The latest down null-contract specialization removes much static code and
saves0.69–1.98% in its complete operator fixture, but the model measures
1586.586480 PP with overlapping parent ranges. Much removed code was in
inactive branches. Even a2% reduction in the historical161.558-ms down region
amounts to only3.23ms, against a74.89-ms gap. Preserve that candidate for later
composition; another variant of the same local simplification is insufficient
grounds for first priority. Marginal results are retained without adding their
percentages or assuming that their combined effect is measured.

## A concrete limit to generalization

The retained executor has **two explicit `n_tokens == 2048` guards**:

| Site | Optimized behavior enabled by the guard |
| --- | --- |
| `Executor::Combine`, line1138 | Publish narrowed HC normalization and eligible deferred-normalization state. |
| `Executor::MoeExperts`, line1813 | Store Q2 expert-down results in F16 and select the corresponding MoE/HC consumer. |

The canonical prose curve produces approximately2048 new tokens, with the
accepted physical count preserved. Saved examples include2040,2042 and2047.
Those requests cannot enter these two exact2048 routes. Long prefix creation
can enter them on full2048-token chunks; its final partial chunk and subsequent
continuation can take different paths. This is a source-proven eligibility
limit, **not yet a measured explanation of a new curve result**.

For one contiguous prefill, intermediate chunks are full-sized:5000 tokens
become2048 +2048 +904. Only the final chunk can be partial. In the canonical
curve, however, the long prefix is prepared separately and restored; the
measured continuation can itself be a single2042-token partial chunk. The
extension therefore targets tails and continuations. It cannot speed up the
already eligible intermediate chunks or close the fixed exact2048 gap.

Extending these guards requires qualifying partial rows, buffer identities,
deferred-state lifetimes and original numerical outputs. Merely deleting the
guards would bypass their qualification. Keep the actual canonical requests;
do not force their token counts to make the optimized path appear active.
This is a distinct next step for whole-curve parity, even after fixed-point
parity is reached. [Bound source audit](../config/q2-remaining-work-audit.json).

The host contract in `lie_q2_deferred_norm_state.h` also requires2048 rows in
both publication and matching. Changing only the two executor guards would
leave that contract inconsistent: a producer could return after publication
was refused. The complete future change must cover producer selection,
publication, matching, reconstruction fallback and last-reader ownership.
Existing operator evidence already covers partial token rows, but it does not
replace this integrated lifetime qualification. An initial1024–2048 range
would cover typical2040/2042 continuations while keeping smaller routes intact;
no such extension is implemented or measured in the current curve.

Here, "contract" means the internal buffer hand-off rules: valid row count,
buffer identity, representation and lifetime. It does not propose a different
normalization formula. The intended extension must preserve the existing
arithmetic, rounding boundaries and reconstruction behavior for each row.

Partial-row evidence already exists: the older
[paired producer component](../config/q2-norm-ragged-results.json) and
[HC library dispatch model experiment](Q2-HC-LIBRARY-RAGGED-MODEL.md) must be
reused, not rerun as new discoveries. The latter extends a different consumer
and is already represented in the retained source. Neither qualifies the
current combined F16 expert-output/deferred-state extension. The
[re-audit](../config/q2-rejected-test-reaudit-progress.json) explicitly records
why broadening these guards adds no mechanism at the fixed2048 point.

## Remaining mechanisms with substantial scope

### Capacity changes can change attention dispatch

The curve's private266240 effective capacity also increases the sparse mask
pitch from2048 to2080 words. Both retained providers reject the WMMA sparse
attention launcher when that pitch exceeds2048 and fall back to
`AttentionKernel` followed by `SigmoidMul`. This is determined by configured
capacity whenever a sparse mask is present, not only by a query crossing256K.
The numerical device bodies are unchanged, but their selection changes.
Consequently this curve cannot isolate the effect of retained Q2 optimizations
against the older133760-capacity curves. The new Q2/UD arms share the fallback.

Simply deleting the launch guard is unsafe: the WMMA union scan has eight local
words per thread and2052 shared entries. A future fix must separate allocated
mask pitch from the visible extent and qualify the actual capacity boundary;
contexts beyond262144 require additional kernel coverage. This affects the
long-context experiment, not the fixed9216-capacity parity reference.

The costs below come from the saved1571.716479 diagnostic executable, not a
fresh profile of1587.893545. They prioritize regions; they are neither promised
savings nor quantities to add across overlapping rows.

| Region | Saved prefill time | Concrete remaining work | Main constraint |
| --- | ---: | --- | --- |
| IQ2 gate/up plus Q2 down |401.058ms | Redesign operand/producer/consumer ownership across the expert chain. | Preserve routed token/slot mappings, logical640 versus stored768, matrix accumulation and original rounding boundaries. An18.67% reduction in this region would cover the gap arithmetically; no such gain is measured. |
| Dense Q8 weights / F16 activations |293.227ms, including160.218ms fused SSM projection | Reuse input stages across more useful output work without a persistent weight mirror. | Existing128-bit payload loads, register pressure and49KiB SSM LDS constrain the design. Previous aligned-pair, mirror and pingpong variants are completed negatives. |
| HC combine/norm/injection |186.168ms; MoE combine/norm72.902ms included | Consume expert outputs sooner or fuse remaining residual/normalization work with a compatible consumer. | Ten ordered expert FMAs, shared-expert contribution, four-stream RMS order and last-reader ownership must remain explicit. |
| GDN recurrence and epilogue |82.683ms +21.949ms | Change recurrence/epilogue work distribution or intermediate publication. | The recurrence has a true token dependency. The current full-window unroll draft grows VGPR120→157 and code1150→2868; it is compiler-only and lower priority. |

The next implementation should target the active expert chain or dense operand
work, followed by one complete-chain fixture and the unchanged original model
comparison. Static instruction count alone no longer selects the next model
trial. No hardware occupancy or bandwidth diagnosis follows from the saved
trace: `FETCH_SIZE` failed its independent calibration and remains unusable.

## Fusion boundaries established by source

The gate/up producer writes640 F32 values per routed slot in ten64-column
blocks. The following packing pass needs the maximum across all640 values
before choosing its scale. A simple producer epilogue cannot know that maximum.
At2048/top10, this boundary writes and reads50MiB each per layer. Full-row
ownership could eliminate that boundary, but a naive simultaneous1280-row
gate/up tile exceeds the existing LDS budget. A staged design must account for
all live accumulator registers and any loss of weight reuse at smaller token
tiles. Packing itself takes17.096ms in the saved trace and cannot alone close
74.89ms.

The retained F16 down intermediate is100MiB per layer at2048/top10/hidden2560.
Down blocks own one expert's128-column output slice; the consumer needs all ten
experts for each token, in slot order. Token ownership could eliminate the full
intermediate but may sacrifice the current grouping that reuses expert weights.
A last-producer counter can schedule consumption sooner, but still publishes
and rereads the intermediate and adds atomics: it must not be described as
removing that buffer. These byte counts describe logical payloads, not measured
DRAM traffic or guaranteed time savings.

## Completed avenues and separate objectives

IQ2 half-sign arithmetic, DPP commit, compact table LDS, register-stage reuse,
short-tail/four-wave routes; Q2 register palette, larger output tile and live
stage; Q8 weight mirrors/aligned-pair loaders; SSM pingpong/compact LDS; and the
DS4-style bounded compressed expert cache already have preserved experiments.
They are not an untried queue. Producer-Q8 integer down also ran the original
model despite numerical diagnostics and regressed to1090.135499 PP. Reopening
one requires a new mechanism, not another name for the same test.

The saved C1 prefill trace has only5.090ms between kernels. Reactive launch
scheduling alone cannot recover74.89ms there. Decode has79.980ms between
kernels across15 calls, making it a different hypothesis; concurrency and
serving responsiveness remain separate measurements. Existing matrix WMMA and
fused attention are already active. Independent task quality remains open;
same-parent byte equality does not settle it. Q4 remains deferred by the owner.

Historical measurements and original command exits remain in their individual
reports. This audit adds no GPU run, numerical change or performance claim.
