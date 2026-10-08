<!-- SPDX-License-Identifier: MIT -->
# Four-row grouping for the fused SSM projection

The composed SSM row-group4 experiment completes on .157 on5 October2026.
Its complete projection/convolution cycle time decreases1.321083%, but original
model prefill is1576.943074 tokens/s versus saved1580.226725 (-0.207796%).
Decode is25.12187977 versus25.10411864 calls/s (+0.070750%), with overlapping
sample ranges. Keep the source as a measured experiment and retain the1580
register-scatter provider as the performance base. No decode speedup is inferred.

All30 component output pairs are exact, all60 sampled FP64 checks pass, and
all21 parent model files plus nine internal replays are exact. The largest
sampled relative RMS/scaled errors are1.067384e-5/1.108063e-5, below0.002.
Identical parent logits retain the inherited difference from fixed Q2/UD;
independent task quality and full context/concurrency parity remain open.

## Complete model samples

The original exact2048/tg128 input,127 timed decode calls, capacity9216,
chunk2048, greedy C1, MTP off, one warmup/three measurements and15-second
cooldowns remain unchanged. Only the new SSM model runs. The other columns
are saved evidence, without recompilation or another inference run.
PP is prefill tokens/s; TG is decode forward calls/s.

| Session | Fixed Q2 PP / TG | Saved1580 PP / TG | New SSM PP / TG | Fixed UD PP / TG |
| --- | ---: | ---: | ---: | ---: |
| Warmup | 1438.259006 / 25.08847266 | 1578.810990 / 25.08217355 | 1578.011782 / 25.09727524 | 1689.043527 / 24.34239962 |
| Measured 1 | 1443.398207 / 25.10565683 | 1580.873846 / 25.11185031 | 1576.680364 / 25.10952130 | 1686.364042 / 24.34621613 |
| Measured 2 | 1443.672867 / 25.08698337 | 1580.226725 / 25.09349758 | 1576.943074 / 25.12409589 | 1685.777092 / 24.34174251 |
| Measured 3 | 1443.841794 / 25.09595499 | 1579.621125 / 25.10411864 | 1577.662261 / 25.12187977 | 1685.400011 / 24.15102104 |
| Median | 1443.672867 / 25.09595499 | 1580.226725 / 25.10411864 | 1576.943074 / 25.12187977 | 1685.777092 / 24.34174251 |

New measured prefill spans1576.680364–1577.662261 tokens/s; saved-parent
values span1579.621125–1580.873846. Their observed ranges do not overlap,
while historical controls do not establish a contemporaneous causal estimate.
The required gain from the retained1580 base to fixed UD1685.777092 remains
6.6794445%; this candidate does not close it.

[All model rates and elapsed times](figures/q2-ssm-row-group-model-wrapped.csv),
[model chart](figures/q2-ssm-row-group-model-wrapped.svg),
[all14 component timings](figures/q2-ssm-row-group-component.csv),
[component chart](figures/q2-ssm-row-group-component.svg).

The component median is4941.275597→4875.997225 microseconds, timing projection
and boundary convolution together with three weight rotations beyond32MiB.
This is a component result; its small saving does not translate into a whole
model gain in this run. The cause of the difference is not isolated by these
measurements, and no hardware cache/bandwidth saturation claim follows.

Host27 Debug +27 ASan/UBSan pass. All13 runtime commands exit0 and37 collected
artifacts verify. Model CPU/GPU peaks are82.125/74.0°C, without a thermal stop.
The154.251403-second candidate build and13.57126461-second load are excluded
from PP/TG. Resident memory remains43,156,012,544 bytes.

The window releases at21:55:33.594774UTC:1115 process identities and889 groups
retired, KFD empty, four original leases free and seven model stat tuples
unchanged. Canonical/main/remote mirrors agree. No job, waiter, restart,
reservation or .157 cleanup remains. Further work requires fresh admission.

[Model report](../config/q2-ssm-row-group-model-results.json),
[component report](../config/q2-ssm-row-group-component-results.json),
[final audit](../config/q2-ssm-row-group-final-audit.json),
[disposition](../config/q2-ssm-row-group-disposition.json),
[release](../config/q2-ssm-row-group-window-release.json).

The original standalone source derives from saved1574 and remains unexecuted.
The measured composition applies the same two SSM changes to saved1580.
Both source inventories and their original preparation evidence are retained.

## Composition and runnable scope

The1027-file composition preserves the inherited register-scatter include
exactly. Comparison against saved1580 assembly preserves161 other kernels,
including all register-scatter specializations; the new SSM body is identical
to the previously compiled standalone group4 body. The literal test control
also matches the current1580 parent. No qualified parent is recompiled.

Launcher modes `ssm-row-group-check` and `q2-counting-ssm-row-group` admit only
the matched `ssm-row-group` source. The frozen plan binds88 runtime fixtures,
five manifests and a separate coordination helper. Both real source capsules
are constructed locally with SSH intercepted, then their1027 provider files,
88 fixtures and five manifests are verified.142 launcher guards and eight
analysis checks pass. The analysis checks use synthetic log records only;
they are neither GPU execution nor throughput evidence.

An initial analysis test run retains exit1 because five negative tests expected
RuntimeError while the shared checker raises ValueError; correcting only the
test exception expectations gives eight passes. The initial composition
verifier temporarily reused the historical standalone filename. The historical
file is restored exactly; the composition uses its own tool, and both initial
and final receipts are retained. No numerical source or tolerance changed.

Execution follows the fresh Core-19 CPU closure and explicit .157 handover.
Original source/fixture/manifest hashes remain exact through host qualification,
GPU admission, component and model execution, collection and release. Saved
Q2/UD/1580 controls are reused; no Q4 or full curve is included.

[Composition source](../config/q2-ssm-row-group-compose-source.json),
[assembly audit](../config/q2-ssm-row-group-compose-static.json),
[frozen plan](../config/q2-ssm-row-group-plan.json),
[local preparation](../config/q2-ssm-row-group-compose-preparation.json).

## Why this region

The saved1571 diagnostic attributes160.217893ms over36 calls to the fused SSM
projection, inside293.227373ms of Q8/F16 dense work. That is a saved-parent
profile, not a fresh1574 measurement or an estimate of recoverable time.
Q8 loads already use128-bit instructions. Earlier narrower SSM tiles, wider
prefetch, expanded mirrors and aligned-pair fetching have negative evidence.
This experiment changes grid traversal only, retaining the current geometry.

## Exact source boundary

The1027-file provider is copied from the saved1574 inventory. Only two source
substitutions change: the SSM epilogue assertion admits row-group4 as well as1,
and `DenseF16SsmGemm` selects4 instead of1. The existing generic mapping already
serves HC; it is newly selected for this SSM specialization. Every arithmetic,
weight-decode, convolution, boundary-kernel and launch-guard source statement
otherwise remains literal. No allocation, stream, weight representation or
number of launches changes.

Dispatch remains n>=1024, M16384/K2560,10240 convolved channels and four taps.
The64 output-row blocks divide exactly into groups of four. BM256/BN128/BK2,
eight row waves and original K16 WMMA order remain unchanged. For a grid with
16 token blocks at2048, the first entries change as follows:

| Mapping | First grid-enumerated (row block, token block) entries |
| --- | --- |
| Existing group1 | (0,0), (0,1), (0,2), (0,3), ... |
| Candidate group4 | (0,0), (1,0), (2,0), (3,0), (0,1), ... |

This places consumers of the same activation tile closer in grid enumeration,
while separating consumers of the same weight tile. Neither actual hardware
execution order nor cache hits are guaranteed. Logical bytes read/written and
the1024 workgroups at the fixed point are unchanged. The experiment does not
implement a general reactive scheduler or modify the recurrent GDN algorithm.

## Local checks

Patch reconstruction and both full provider inventories verify. Comparison
against saved assembly preserves161 of162 kernel instruction bodies, operands
and resource descriptors exactly; the saved parent is not recompiled.

| Property | Parent | Candidate |
| --- | ---: | ---: |
| Whole SSM body instructions | 4027 | 4037 |
| Compiler `NumVgprs` | 222 | 222 |
| Descriptor `next_free_vgpr` | 241 | 241 |
| LDS bytes | 49152 | 49152 |
| Private scratch bytes | 0 | 0 |
| Static WMMA instructions | 64 | 64 |
| Static block barriers | 2 | 2 |

Descriptor register reservation and compiler register use are separate fields.
The compiler's static occupancy value4 is unchanged; measured hardware active
waves remain unknown. Extra grid-index instructions may outweigh improved reuse.
Global128-bit loads and LDS128-bit load/store counts also remain unchanged.

CPU integer checks cover1292 grid shapes and1896192 tile identities, including
odd token-grid widths and ragged tails, without gaps or duplicate ownership.
Convolution checks cover33408 token/channel-class masks, initial history and
the first/last three raw rows around32-token windows. These are symbolic
ownership checks, not CPU model inference, GPU semantics, or a context sweep.

The first static checker exits1 because its symbol pattern uses `ELi` rather
than `ILi` for the first template argument. The corrected check passes without
a candidate change. Its initial successful report omitted compiler comments;
the additive v2 report binds the actual222-register use and241 reservation.
The initial checker/report and command exits remain preserved. Compilation
retains the existing enumeration warnings.

## Prepared component and remaining execution

The fixture contains the literal saved1574 dense template and SSM wrapper under
test-only names, also verified exact to saved1580. Host and gfx1151 device
syntax checks pass. Its composed source is wired into the launcher as described
above; its first GPU execution is the completed composition reported here.

Five shapes1024/1025/1057/2048/2049 with three weight rotations cover30 complete
projection/convolution output pairs, poisoned intentionally-unwritten raw rows,
allocation guards and immutable inputs. Sixty sampled FP64 operator checks,
24 outputs each, independently check rounded-F16 projection operands and the
four-tap convolution/SILU. Exact replay and the0.002 sampled error limits are
separate checks; CPU operator calculations use synthetic fixture operands only.

Only M16384/N2048/K2560 is timed: two warmups and five measured samples per
arm, alternating order, three rotated weight sets totaling133693440 bytes.
All input preparation, copies and checks stay outside those14 event timings.
The timed cycle includes projection and the unchanged convolution-boundary
kernel. Safe numerical failures retain exit1 and continue timing; runtime or
guard exceptions exit2. The new original-model experiment must still follow
safe execution even if this component is numerically or temporally negative.

The original frozen plan is now completed. The prepared fixed-shape,
fixed-bounds, compact-LDS and alternating-buffer variants remain separate,
unmeasured sources. Prioritize the compact alternating-buffer implementation
next; use a new frozen plan and fresh admission, without repeating this arm or
its qualified saved model controls. Independent inherited F16 task quality
stays open.

[Source](../config/q2-ssm-row-group-source.json),
[static audit](../config/q2-ssm-row-group-static.json),
[fixture contract](../config/q2-ssm-row-group-fixture.json),
[preparation receipt](../config/q2-ssm-row-group-preparation.json).

## Provenance

The source derives from independently fetched official Gufo pin
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e` and the retained LIE1574 lineage.
The existing HC tile mapping is reused without importing DS4 or sibling
CachyOS sources or artifacts. MIT SPDX markers and upstream notices remain.
No C17 ABI, persistent-state, resource-accounting or public metrics contract
changes. Measured component/model timing is reported above; independent task-quality acceptance remains open.
