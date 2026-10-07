<!-- SPDX-License-Identifier: MIT -->
# Current Q2 optimization assessment — 7 October 2026

The active goal is now **C1 AR decode30 token/s and complete prefill at least
1500 token/s through the original130925-token input**. The old fixed-point UD
parity objective is paused, not completed. Preserve its reference below, but
do not prioritize it over the new long-context goal or replace the long-prefix
measurement with a2048-token continuation. The retained128K observation is
1310.874605 PP /25.344213 TG; TG is the original eight output calls, not TG128.
Prefill must fall from99.876067s to at most87.283333s, a12.592734s saving.

The [completed native32K diagnostic](Q2-LONG-PROFILE.md) rejects all zero
GPU timestamps and uses valid CPU intervals only. It identifies45–70ms gaps
before PLE uploads and depth-dependent attention-completion intervals. Warm
C1 completion-to-next-submission gaps are only0.092–0.097ms; the older direct
harness's5.33ms/token gap is not native-server headroom.

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

## Mechanisms to test next at the fixed long-prefix input

The prefill target needs12.592734s less at130925 tokens. Prioritize a complete
2048-row routed-expert chain experiment: the current IQ2 gate/up path already
pairs projections, but still materializes a packed scaled-half plane before Q2
down. Its existing whole640 producer/pack replacement was11.08% slower in the
mixed component, so a new candidate must reduce repeated expert-weight reads
or increase useful row reuse across the complete chain. Measure actual routed
tile counts and weight traffic before choosing an altered layout. Keep current
quantization, exact prompt chunks and saved control binary.

The secondary long-context experiment is query-grouped selector scoring. The
current `SelectScoreKernel` loads a128-value key separately for each query row,
then reuses it across four heads. A workgroup could hold that key while scoring
four adjacent query rows, preserving each row's FP32 FMA/reduction sequence and
the original top-512 tie rule. This changes score scheduling, not the query
or key data or attention budget. Check full score bits and masks at16/32K
before any64/128K component and original full-model trial. Prior two-query
key reuse in the attention consumer regressed, so it does not qualify this
different indexer hypothesis.

The completed128K partition-selector component saves10.889us per2048-row
selection launch. Even multiplying that by12 full-attention layers and all64
prefill chunks gives only about8.36ms, far below the required12.59s. This is
an intentionally generous illustration, not a measured model attribution;
selection dispatch and chunk depths vary. Deep selector work may still help
one-row decode, whose shape needs its own measurement, but it cannot be the
main route to the full-prefill target.

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
