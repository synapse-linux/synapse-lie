<!-- SPDX-License-Identifier: MIT -->
# Four-row grouping for the fused SSM projection

This is local preparation, without GPU numerics or model timing. The original
standalone experiment derives from saved1574.505432 PP /25.17589001 TG at
original exact2048/tg128, against fixed Q2/UD1443.672867 /1685.777092 PP.
The independently completed
[register-scatter experiment](Q2-DOWN-REGISTER-SCATTER.md) subsequently measures
1580.226725 PP /25.10411864 TG. A separate composition now applies the same
two SSM changes to that retained1580 provider. Both source inventories and
their preparation evidence remain available; neither SSM variant has run on
a GPU. Saved model results and archived register-scatter capsules are unchanged.

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

Remote host27 Debug +27 ASan/UBSan, GPU component and original model remain
pending. Core's CPU .157 full19 window is active; both reported process
identities are independently observed live at20:11:40UTC. Q2 has no remote
job, build, client, lease, waiter or reservation. A fresh handover and full ownership
checks are required before runtime work. The planned component is followed by
one new original2048/tg128 model even after safe numerical/timing rejection.
Saved Q2/UD/1580 controls are reused; no Q4 or full curve is included.

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
above, but the fixture has never executed on a GPU.

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

The launcher and frozen plan are prepared; future work needs .157 host
qualification and fresh coordinated ownership before any remote numerical build/run. No
current remote job, GPU reservation or waiting process is created here. No
qualified comparator rerun, Q4 test, full curve, model conversion or .157 cleanup
is part of this preparation. Independent inherited F16 task quality stays open.

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
changes. This experiment supplies no throughput or quality acceptance yet.
