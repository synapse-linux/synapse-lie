<!-- SPDX-License-Identifier: MIT -->
# Synapse LIE — original Q2 support for official Gufo

The [new IQ2 paired-row candidate](docs/Q2-IQ2-WIDE-PAIR.md) is prepared from
the1509 parent. Only nonpacked BN64 doubles logical output rows per block and
keeps gate/up in the same wave. Other156 kernel bodies remain identical;
next-free VGPR104→169 and LDS17536→26752 can offset the saved epilogue barriers.
One new component and original model remain pending; no speedup is claimed.

The [four-lane IQ2 producer](docs/Q2-IQ2-LANE-COMMIT.md) completes on .157:
PP1509.852296/TG25.20625148, nominally+0.312263% PP versus saved1505.152258.
All81 component pairs and21 parent model files are exact, while component time
increases0.606644–2.408259%. Retain this small positive model result as the next
composition source, without claiming a stable causal gain or runtime promotion.
Host27+27 and all13 commands/37 artifacts pass; the GPU window is released.
Original Q2/UD controls remain unchanged; fixed UD1685.777092 still requires
11.651788% more prefill throughput. Q4 and the full curve remain deferred.

The [1KiB IQ2 sign-mask candidate](docs/Q2-IQ2-SIGN-MASK.md) completes on .157
at PP1504.885103/TG25.17103717. Prefill differs-0.017749% from saved best
1505.152258 with overlapping ranges; retain the marginal candidate while
keeping that parent as the base. All81 component outputs and21 parent model
files are exact; the small component gain adds no established model speedup.
All13 commands/39 artifacts verify,97 guards and25 Debug/25 ASan pass.
The window is released; Q4 stays deferred and the fixed comparison stays unchanged.

The [new fused IQ2 table](docs/Q2-IQ2-FUSED-GRID.md) completes on .157 at
PP1331.128807/TG25.11415619, an11.561850% prefill regression against saved
best1505.152258. All81 component output pairs and21 parent model files are
exact despite fewer static instructions. The full candidate, samples and
graphs remain preserved; the1505.152258 provider stays the base. All13
commands/39 artifacts verify and the GPU window is released. Q4 stays deferred.

The [Q4 one-shot](docs/Q4-ONESHOT.md) stops before inference because the plain Antirez Q4 GGUF lacks required rope.dimension_sections metadata. Exit1 and original evidence are retained, the window is released, and the owner defers Q4 and resumes Q2 from the saved1505.152258 prefill parent. No followup Q4/UD test is started.

An owner-requested [one-shot original Q4 comparison](docs/Q4-ONESHOT.md)
is prepared using the two retained reference/candidate binaries, unchanged
exact2048/tg128 timing and no compilation. This is a single separate campaign,
not a new recurring Q2 check. Engine sources and the Q2/UD target are unchanged.

The [new IQ2 raw/selective-Q2 composition](docs/Q2-IQ2-RAW-SELECTIVE.md)
completes on .157 at PP1503.961988/TG25.19241290. Its nominal prefill change
is-0.079080% versus the saved IQ2 raw parent1505.152258, with overlapping
samples; that parent remains the base. All21 parent model files and nine
replays are exact. The marginal selector and full composition stay preserved;
10 commands/33 artifacts verify, host Debug/ASan25/25 each pass and the GPU
window is released. No old component or qualified control is rerun.

The [ordered Q8 K16-phase candidate](docs/Q2-Q8-K16-PHASES.md) now completes66 exact
component output pairs and its original fixed model on .157.
PP1501.482502/TG25.17806319 changes prefill
-0.243813% versus saved IQ2 parent1505.152258. The retained
base is PP1505.152258; fixed UD1685.777092 remains unmet. All21
parent model files are exact, host Debug/ASan25/25 each pass and the GPU window
is released. No qualified controls/cohorts or curve are rerun; full values and
graphs are retained.


The [new scaled-Q2 down extraction candidate](docs/Q2-DOWN-RAW-PREFETCH.md)
now completes117 exact component output pairs and its original fixed model on
.157. PP1503.711045/TG25.16358276 changes PP
-0.095752% versus saved IQ2 parent1505.152258. The retained
base is PP1505.152258; fixed UD1685.777092 remains unmet. All21
parent model files are exact, host Debug/ASan25/25 each pass and the GPU window
is released. No qualified controls/cohorts or curve are rerun; full values and
graphs are retained.


This isolated workstream adds the original antirez Q2 GGUF to official Gufo
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, without the antirez Qwen engine.
The acceptance target is **Q2 at least as fast as UD in both prefill and decode
at every point of the requested context curve**. The
[canonical comparison contract](docs/Q2-CURVE-PARITY.md) restores Gufo's HTTP
pp2048/tg128 prose workload and ordered cached-prefix depths from 0 to 128K.
The [ordered-IQ2 four-arm comparison](docs/Q2-IQ2-CANONICAL.md) measures
ordered IQ2 decode **4.055–5.526% above UD at all eight depths**, preserving all
20 Q2 request/output histories. Prefill remains **7.348–9.299% below UD at0–16K**;
long-context crossings remain sensitive to UD variability. Whole-curve parity
and independent model numerical qualification remain open. The complete graph
and CSV retain the candidate, UD and both unchanged Q2 controls.

The [DeepSeek-inspired mixed 128/64 tile comparison](docs/Q2-IQ2-MIXED.md)
uses unchanged numerical kernels with a new C17 descriptor map. Its host
qualification passes 22/22 Debug and 22/22 ASan/UBSan on .157. The GPU comparison
now saves1.487–4.148% of complete component time across four measured-routing
cases, or1.723–3.765% including map construction/upload. All ten output pairs
are exact and independent FP64 checks pass. The full-tile control costs0.3%
more; no model prefill gain is claimed. Full results, graph and140-sample CSV
are retained, and the GPU window is released.

Its [complete four-arm model comparison](docs/Q2-IQ2-MIXED-CANONICAL.md) now
finishes all eight depths. All 20 Q2 histories replay exactly, but mixed-map
prefill is 4.331% lower at depth 0 and 0.750% higher at 128K than the repeated
unchanged control; no uniform model gain is established. Q2 PP remains below
UD at every point. The graph retains both controls, the candidate and UD,
with all 32 observations and complete request durations in the CSV. The broader
latency, concurrency, resource and quality acceptance gates remain open.

The [exact historical counting replay](docs/Q2-COUNTING-REGRESSION.md) confirms
1435.999/1440.579/1443.673 PP for old/ordered/mixed Q2, against 1685.777 for fresh
UD. Every saved Q2 output and logit file remains exact. The old 1439 result is
reproduced on its original repetitive input; it is not a canonical prose rate.
The complete four-arm graph includes all measured sessions and warmups.

The [fixed-shape norm full-model comparison](docs/Q2-NORM-FIXED-MODEL.md)
now completes on that exact2048 reference: candidate1444.467 PP versus
1444.863/1443.057 for unchanged Q2 controls and1688.699 for fresh pristine UD.
The PP differences remain inside observed control variation. All tokens match,
but logits change; component rejection and numerical gates remain. The owner
requests retaining the marginal candidate for targeted composition. All111
host/model artifacts verify; the GPU window is released and no curve is admitted.
The [renewed DeepSeek/shared-Q8 audit](docs/Q2-DEEPSEEK-SHARED-PREFILL.md)
identifies two remaining producer/fusion hypotheses without a new GPU run.
The [raw-HC shared-Q8 producer](docs/Q2-SHARED-Q8-PRODUCER.md) now has an
isolated source and complete-cycle fixture. Existing device kernel bodies are
unchanged; FFN cache publication enables their existing Q8 output. Host Debug
and ASan/UBSan each pass22/22 on `.157`. The completed GPU component preserves
all50 reference/candidate output checks and records90 timing samples:
producer time falls4.39%, complete shared-expert time2.01–2.08%, with15/15
paired wins. The original independent GPU format rejection at127/2048 is now
traced to cross-stream fixture initialization: the saved-array replay passes
40/40 same-stream outputs. Its original exit1 and97 artifacts remain.
The candidate is retained, the GPU window released,
and no new model rate or context curve is claimed.

The [latest DeepSeek prefill comparison](docs/Q2-IQ2-PREFILL-REUSE.md) completes
four GPU component arms. Block-scale reuse saves 0.815–3.743% of complete-cycle
time on recorded short/128K routing shapes against the repeated reference;
the full-tile control costs 0.445% more. All 102 output arrays remain exact and
51 independent checks pass per arm. Shared-codebook staging has mixed results
and does not advance. The subsequent native C model comparison establishes
no uniform scale-reuse gain, so the candidate is not promoted.

The [native canonical model comparison](docs/Q2-NATIVE-SCALE-CURVE.md) completes
all four 0–128K curves: 32 accepted points, 32 zero model-command exits and 68
verified artifacts. Both complete Q2 history comparisons are exact. At 128K,
scale Q2 gives 1127.232 PP against 1157.600 for the repeated reference. The
unchanged d0 control itself rises 851.328→1246.179, so the first-to-second
increase cannot be credited to the patch. All values, including the measured
UD dips, remain in the four-arm graph and full CSV. The GPU window is released.

The final wrapper and native client pass 22/22 and 3/3 respectively in Debug
and ASan/UBSan on .157. All twenty real canonical request/reply/count histories
also match the old driver. A separate [scaled-row input reuse probe](docs/Q2-SCALED-ROW-REUSE.md)
removes a second input read. Three GPU component arms now show about 15% less
packing time and 0.4–1.8% less complete pack/down time against the repeated
control, with identical whole-buffer outputs. Every arm preserves the same
fifteen numerical rejections and exit 1. This is no new model PP/TG result;
the candidate remains isolated and the GPU window is released.
Its [native canonical model comparison](docs/Q2-NATIVE-ROW-CURVE.md) completes
all four 0–128K curves, with 32 zero model-command exits, 68 verified artifacts
and exact Q2 request histories. Row reuse is below the repeated control in
four of eight PP points and its depth-zero TG is 18.026% lower. It is not
promoted. The unchanged Q2 depth-zero PP itself rises 849.444→1255.841;
all control variation and UD observations remain in the full graph and CSV.
The GPU window is released and the complete parity target remains open.

The separate [live-stage store-mask comparison](docs/Q2-LIVE-STAGE.md) completes
three GPU component arms: all 51 independent checks pass per arm and all 102
output arrays match. Complete cycles save 0.817–2.081% against the final
reference on recorded routing shapes. Two cases fail the frozen advancement
threshold, so no further model curve is launched. All 105 samples and the
graph are retained; the GPU window is released. Existing host qualification
is reused after exact comparison of all sixteen measured files.

The [paired norm at 2040 rows](docs/Q2-NORM-RAGGED.md), the actual canonical
depth-zero size, saves 2.658%/6.772% in complete ordinary/MoE component cycles,
with exact paired output and unchanged independent down failures. This selects
one model point before another full context curve. No model gain or complete
Q2/UD parity is established by the component result.

The completed [focused native model diagnostic](docs/Q2-NORM-POINT.md) retains
all twelve samples and both controls, with exact Q2 histories. Its three
prompts contain 2040/2032/2053 tokens and are not identical-input repetitions.
Observed +1.532%/+1.664% PP differences on the two affected inputs remain
exploratory. They do not update the [fixed 1443.673 Q2 / 1685.777 UD
reference](docs/Q2-VALIDATION.md#comparators-and-preparation); improvement on
that comparison has not been measured. Independent quality and whole-curve
parity remain open; no full sweep follows.
Further context-curve tests wait until Q2 matches UD on the fixed comparison.
Until then, performance work uses relevant component controls and that same
model point; small gains and cumulative checkpoints do not bypass this gate.
The [fixed-shape paired norm probe](docs/Q2-NORM-FIXED-SHAPE.md) is rejected:
despite37% fewer static instructions, its complete2048-row cycles save only
0.648% ordinary /0.125% MoE against the repeated control and introduce output
differences. All60 component samples remain available. The component gate
admits no model test. The later owner-requested exploratory
comparison above preserves this rejection and the fixed1443.673 Q2 /1685.777
UD reference. The candidate remains isolated for targeted composition.

The subsequent [PLE four-arm comparison](docs/Q2-PLE-CANONICAL.md) completes
all eight depths and retains both unchanged ordered-Q2 controls. It establishes
no stable additional PLE gain: at 128K candidate/control PP is 1156.229/1154.364,
versus UD 1275.705 token/s. Candidate prefill remains below UD at every point.
All 20 Q2 request/output histories replay exactly; the full graph and 32-row CSV
preserve short-context variability and UD's low decode observations as measured.

The completed [canonical routing diagnostic](docs/Q2-ROUTE-PROFILE.md) records
7248 layer-count observations, preserving all 20 Q2 histories. On the accepted
large prefill calls, 48.612–50.855% of paired epilogue fragments are empty; the
matrix loop already skips their WMMA work. A separate
[uniform epilogue guard](docs/Q2-IQ2-LIVE-EPILOGUE.md) and its early-exit variant
now complete their GPU comparison on `.157`. All 51 independent numerical
checks pass in each of the three arms, and both candidates preserve all 102
output arrays exactly. Their timing changes are small and mixed: the early exit
saves 0.111–0.818% in the four measured-routing component cases, while the
full-tile control takes 0.647% longer. Neither variant advances to a full model
comparison. These are complete component-cycle times with synthetic operands,
not model prefill rates. The report retains all 105 samples, a graph and the
unchanged host 21/21 Debug and 21/21 ASan/UBSan qualification.

Two earlier [complete paired curves](docs/Q2-CANONICAL-REPEATS.md) measured the
reference provider on
`.157`, with every physical token count, PP/TG duration, graph and CSV.
Reversing model order does not confirm the first pair's near-parity at128K:
Q2 is **10.455% below UD in PP** and **2.263% below in TG** there in the second
pair. At depth0 its PP deficit is49.795%. All40 same-model request histories
and completion hashes replay exactly. Both metrics' means remain below UD at
all eight points; the observed variability needs attribution.
Both models use the same C17 executor-call timer; published Gufo scheduler
timing is not asserted identical. The [first pair](docs/Q2-CANONICAL-HTTP.md)
remains retained separately.
Historical counting-prompt tests, including the 1411→1439 prefill result,
remain separate diagnostics. Existing numerical rejection remains; the
attribution retains the full canonical workload.

The [canonical PLE attribution](docs/Q2-CURVE-PROFILE.md) is complete on `.157`:
at depth zero Q2 host PLE waiting is 1180.492 ms versus UD 113.939 ms, falling
to 138.881/112.701 ms at 128K. Process reads are 2046.773/98.359 MiB at depth
zero. Host waiting can overlap GPU work; it is not guaranteed recoverable time.
Both profiles preserve all 40 request/output histories and remain separate
from throughput results. Host checks pass 19/19 Debug and ASan/UBSan.
The verified window is released to core; no Q2 remote job or retry remains.

The [official DeepSeek source audit](docs/Q2-DEEPSEEK-AUDIT.md) identifies
mixed expert full/tail tiles and packed integer IQ2 sign expansion as distinct
opportunities. The [packed-sign decode experiment](docs/Q2-IQ2-SIGNS.md)
reduces the complete 512-expert rotating component cycle from 85.352 to
50.047 µs (41.364% less time), with 110 byte-exact output comparisons after
constraining scale rounding. This is component evidence, not a model speedup.
The canonical whole-model path, complete-history comparison and three-series
plot export pass 19/19 Debug and ASan/UBSan host checks on `.157`. Core released
its window, and fresh Q2 admission at 00:51:48 UTC on 2026-10-04 starts the
full-MMQ baseline/ordered-candidate/UD campaign.
The [completed Q2 order control](docs/Q2-IQ2-CANONICAL.md) measures
**4.446–5.188% higher full-model decode** at every depth with the ordered
candidate. All 20 request/output histories replay exactly. An unchanged Q2
repeat reproduces the apparent PP increase, so it is not credited to this
kernel patch. The final UD comparison is complete, and the verified window
is released at 01:33:37 UTC. Full Q2/UD parity and model quality remain open.
Histogram tile selection is already present, while D2R and producer-Q8 reuse
are inactive stubs in the pinned DeepSeek HIP port.

The [active WMMA prefill follow-up](docs/Q2-DEEPSEEK-AUDIT.md#follow-up-in-the-active-prefill-wmma-loader--2026-10-04)
now removes the dedicated gate/up loader's sign-table lookup in an isolated
source, retaining the measured decode improvement. Device assembly trades eight
loads for extra integer instructions with unchanged register allocation. Two
full-size component cycles now complete on `.157`: all 20 independent checks per
arm pass and 22 full output pairs are exact, but the candidate takes 2.49–2.58%
more time. It is not advanced to a canonical model arm.
Numerical failures retain their output arrays and performance samples with exit1;
they cannot become a successful qualification through partial reporting.

A separate [PLE cache-first candidate](docs/Q2-PLE-CACHE-FIRST.md) consumes
resident rows before colliding misses can replace them. Capacity and all row
values are unchanged. The paired control/candidate host path is now wired,
with distinct colliding row contents and retained actual read counters.
The paired suite passes 21/21 Debug and 21/21 ASan/UBSan on `.157`: the original
reader rereads 120–128 initially resident rows in each collision fixture, while
the candidate rereads none and preserves every value. The completed canonical
campaign composes only this reader
with measured ordered IQ2 decode, retaining an unchanged control before and after
the candidate plus pristine UD. It does not establish a stable model gain;
the PLE candidate is not promoted. The earlier IQ2 comparison remains unchanged.

The [ragged HC library experiment](docs/Q2-HC-LIBRARY-RAGGED.md) is complete.
Its 41–48% component time saving at 2042/2047 rows translates to only
**1.975% full-model prefill gain at 2042 tokens**, with no measured decode gain.
The [three-point diagnostic comparison](docs/Q2-HC-LIBRARY-RAGGED-MODEL.md)
still misses UD parity. Library FP64 and row-position checks fail at unchanged
limits; the candidate is not promoted. The `.157` window has been released.

A [decode sequence audit](docs/Q2-HC-DECODE-ATTRIBUTION.md) now separates HC up
from generic kernel groups in the retained traces. Q2 HC up plus preparation
costs 1.003 ms/token more than UD, alongside 1.296 ms/token extra HC down.
Routed experts are already faster there. These are diagnostic stage costs,
not a new throughput result or guaranteed recoverable savings.

The [exact historical C17 benchmark comparison](docs/Q2-DECODE-BASELINE.md)
now confirms UD's original **26.049 token/s** reference: fresh UD measures
**26.061**, versus **25.514 for Q2** at 2042 physical prompt tokens and 128
completed decode steps. Q2 remains **2.099% slower** in decode and **18.079%
slower** in prefill (1362.819 versus 1663.579 token/s). The original benchmark,
ABI and adapter are frozen unchanged; both providers were fully rebuilt on
`.157`. All 36 historical UD output/frontier witnesses replay exactly.

At 502/8191 prompt tokens, Q2 decode is 26.184/25.483 versus UD 26.865/25.970.
The report includes every sample, PP/TG duration, CSV and standalone graphs.
The previous strict diagnostic's 25.080 Q2 / 25.463 UD comparison has different
sampling cost. Restoring the original benchmark does not establish a GPU
speedup; Q2's twelve checked 2042-token witnesses match that diagnostic.

The [scalar HC reduction candidate](docs/Q2-HC-DECODE-REDUCTION.md) passes
11 independent FP64 cases and 27 complete byte-exact output pairs. Reducing
123 to 91 static instructions saves only **0.3345% component time**
(30.272 to 30.171 microseconds). It remains component-only, without promotion
or a full-model speedup claim. The same multiply/load loop and traffic remain.

Existing operator failures and qualified-reference KL **0.002996 > 0.002**
remain rejected. Both host configurations pass **17/17** tests; the completed
campaign verifies **90 artifacts** and **4079 source-file instances**, with
19 command exits zero. The GPU window is released; parity is not met.
The preceding [paired norm/library addition](docs/Q2-LIBRARY-NORM.md)
retains its separate **+1.953% prefill** evidence.

The preceding [composed Q2/UD profile](docs/Q2-SCALED-LIBRARY-PROFILE.md)
locates 70.29% of the then-remaining extra prefill kernel time in activation
preparation and HC down. The new paired producer now saves time with the
actual library consumer; its standalone cycle reductions are 2.53% ordinary
and 6.12% MoE, with 80/80 complete hash pairs exact. These component percentages
are not added to the measured model gain above.

The preceding [scaled + HC-library comparison](docs/Q2-SCALED-LIBRARY.md) combines
two separate arithmetic improvements and measures another **1.86% prefill gain**:
1386.762 to 1412.563 token/s, with prefill falling 1.476821 to 1.449847 seconds.
Fresh UD reaches 1660.059 token/s: Q2 remains **14.909% below UD** in prefill
and 0.642% below its 24.273 decode calls/s. All nine token files match the
scaled base, but eight logit files change and the qualified-reference KL maximum
is 0.002996, above the unchanged 0.002 limit. The source remains experimental.
Every sample, duration and numerical failure is preserved with graphs and CSV;
181 artifacts verify and the GPU window is released. Q2/UD parity is not met.

The preceding [cumulative comparison](docs/Q2-COMBINED.md) tests the compatible
retained optimizations together with exact vector conversion and prepared PLE.
Fresh same-fan 2K controls show no additional gain: retained PP changes
1344.795 to 1341.148 (-0.271%), scaled PP 1388.492 to 1383.503 (-0.359%).
All 21 files match each addition's own base. Fresh UD reaches 1659.557 PP;
combined scaled remains 16.634% below it, with its existing numerical rejection.
Complete rates, prefill/decode durations and every sample have graphs and CSV.
At 8K, C17 lookahead overlaps preparation but improves only 0.122%
over native, with overlapping samples; all 432 frontiers and cancellation pass.
Nine runners and 176 artifacts verify, and the GPU window is released.

The earlier [scaled-input experiment](docs/Q2-SCALED-INPUT.md) improved C1 prefill
1336.121 to 1378.319 token/s (+3.16%), but fails targeted numerical checks and
trailed its contemporary UD reference by 18.10%. It is not promoted. The owner-requested
[Terminal-Bench comparison](docs/Q2-TERMINAL-BENCH.md) now passes its original
smoke task on all three variants (5/5 verifier checks each); the full Core-19
baseline stopped at the 98 C thermal guard after two completed tasks (one pass,
one verifier failure). The other full arms have not started. The candidate uses one extra agent step on
that task, so this is no general quality or efficiency equivalence claim.
The protocol documents all observed serving ceilings and bounded, streaming
evidence collection for long runs; its host guards pass 15/15 on `.157`.
The earlier [HC160 algorithmic reduction](docs/Q2-HC-ROW160-INSTRUCTIONS.md)
keeps160 rows and removes14.7% of emitted main-loop instructions. Two `.157`
comparisons show no useful speed gain, with all22 outputs exact and inherited
numerical failures retained. No model change is selected from that screen.
Scaled-input previously gained +3.16% in its first cohort and +3.25% in a fresh
control; the later library composition above gains another measured +1.86%,
still outside the numerical gate.
The [measured tile experiment](docs/Q2-SCALED-TILES.md) rejects global 64/128-row
selection: tile128 adds 18.09–22.18% component time; tile64 only saves 4.49%
in the 64-active-expert routing. All tile outputs agree exactly, while 48
inherited original-input numerical failures remain (actual exit 1).
The [conversion experiment](docs/Q2-NARROW-VECTOR.md) passes all 192 GPU cases
and both complete consumer outputs. Conversion alone saves 3.6–3.9% time;
complete cycles overlap at only 0.8–1.4% median reductions. No model change
is selected. Both reports include every sample and standalone graphs.
At the owner's request, `.157` now uses [fans reaching 100% at 82 C](docs/Q2-FAN-CURVE.md),
persisted through the AXB35 configuration and fan-only startup loader.
The 98 C software limit is corrected to CPU only. New Q2/UD performance arms
must share this cooling policy; no gain is yet attributed to it.
Those component runs are collected/hash verified and their window was released.
The later cumulative campaign has its own coordination record. Full Core-19
and Q2/UD parity remain open.
The [C17-controlled GPU overlap trial](docs/Q2-SHARED-OVERLAP.md) now runs shared
and routed experts on separate streams with bounded buffer ownership. CPU
Debug/ASan each pass 13/13, 32 GPU lifecycle cases pass, and all 21 complete-model
files are exact. Prefill falls 1336.260 to 1322.514 token/s (-1.03%); decode is
unchanged. The variant is retained as evidence and is not selected.
The [GPU dataflow/code-organization audit](docs/Q2-GPU-DATAFLOW.md) maps existing
overlap, scratch lifetimes and the limits of internal reactive scheduling.
A 741-line routed-module extraction preserves all 146 compiled kernel bodies.
The resulting [F32 scatter experiment](docs/Q2-DOWN-SCATTER.md) preserves every
checked output but adds 2.376% component time; it is rejected without model runs.
The earlier [80-row HC down experiment](docs/Q2-HC-ROW80.md) lowers isolated
projection time 5.71%, but complete-model prefill changes only +0.104% with
overlapping ranges. All 21 model files remain exact; the candidate is not
selected. Full rates, durations, samples and graphs are retained.
The earlier [deferred HC normalization screen](docs/Q2-HC-DEFERRED-NORM.md) avoids
the large F32 norm buffer but adds 10.29% ordinary cycle time and introduces
new complete-output differences. A 1.89% MoE median decrease is unqualified;
all timings and failures are retained, with no model run or promotion.
The earlier [complete HC sequence experiment](docs/Q2-HC-SEQUENCE.md) measures
the norm producer and its down consumer together. Paired F32/F16 output adds
26.69% ordinary / 9.31% MoE time; the half-row geometry does not recover the
regression. All complete outputs remain exact, with one common independent
tiny-input failure retained. Neither variant is selected. Full samples,
graphs and the buffer-lifetime analysis are recorded; no reactive or model
speedup is inferred from these synthetic tests.
The [reassessment](docs/Q2-REASSESSMENT.md) reconciles the warm GPU
gap, measured reactive PLE benefit and read-only historical DS4 results.
Fused WMMA attention is already active in both Q2 and UD. New exact tile48/64
component comparisons regress by 4.40–7.51%; the next investigation concerns
documented activation and accumulation boundaries, with numerical acceptance
still open. No new model speedup or engine promotion is claimed by that recap.
The subsequent [single-chain HC screen](docs/Q2-HC-SINGLE-CHAIN.md) regresses
down component time by **14.14%** and adds eight independent numerical failures;
it is rejected without a complete-model benchmark. Fresh retained Q2/UD traces
pass all 28 replay checks and locate 319.49 ms of additional prefill kernel time.
The separate [bitfield/conversion probe](docs/Q2-BIT-CONVERSION.md) finds identical
extraction assembly for bitfields and shifts, but fewer instructions for a
bounded packed-FP16 construction. That is static evidence, with no new runtime
speed claim; direct bit construction remains an applicable optimization technique.
The [shared-palette follow-up](docs/Q2-STAGED-PALETTE.md) halves those duplicated
mixed-half FMA instructions at equal tile48 register/LDS counts and preserves
all checked outputs, but component time rises **0.98%**. It is not selected;
full samples, numerical evidence and closure are retained.
The [HC row-reuse comparison](docs/Q2-HC-ROW-REUSE.md) also preserves outputs:
320-row tiles add 3.18% component time, while a 160-row tile's initial -1.33%
changes to +0.44% in reverse-order confirmation. Neither variant is selected.
The runtime patch is implemented. Parser/sanitizer, independent synthetic HIP
operators and original-model C1 screens run on `.157`. The latest retained
development candidate, [paired HC up](docs/Q2-HC-UP-CHAINS.md), builds on the
[Q2 affine palette](docs/Q2-AFFINE-PALETTE.md) and preserves the
[HC16 decode gain](docs/Q2-HC-DECODE-WAVES.md). Fresh 2K prefill rises
**1312.92 -> 1335.84 tokens/s (+1.75%)**, with all 21 saved model files
byte-exact. Decode measures **24.092 calls/s**, 0.0813% below the reference
with overlapping sample ranges and unchanged scalar source.
**The performance requirement is not met:** fresh UD reaches 1671.71 PP/24.333
TG; selected Q2 trails by 20.09% and 0.99%. These short sequential screens
do not establish zero-margin parity. Earlier checkpoint drift and independent
model qualification remain unresolved; the qualified runtime patch is unchanged.
The subsequent [wider HC down screen](docs/Q2-HC-DOWN-WIDE.md) preserves all
22 operator outputs but selects none of its three variants. Component time
changes -0.80% with overlapping samples, +194.17% with one-block staging,
and +9.74% with contiguous stage reads. All four arms retain the same four
numerical-control failures. No original-model run was justified by these
results; paired HC up remains selected. Complete samples, graphs and CSVs
are retained, and the GPU window is released.
The [fresh GPU profile and HC follow-up](docs/Q2-PREFILL-GAP.md) localize
321.10 ms of additional Q2 prefill kernel time. Two compiler-boundary probes
preserve all component outputs but regress time by 7.93% and 6.12%; both are
rejected. The subsequent [HC data-reuse comparison](docs/Q2-HC-DATA-REUSE.md)
rejects direct fragments and paired accumulation waves. Combining paired waves
with coalesced reads saves 5.04% component time, but complete-model prefill
changes -0.30%, with all 21 reference/candidate output files exact. The palette
source remained selected at that checkpoint. The subsequent
[bounded HC library comparison](docs/Q2-HC-LIBRARY.md) finds seven
zero-workspace algorithms at both tested workspace caps. The best
down candidate saves 16.97% component time and raises complete-model prefill
to **1341.37 tokens/s (+2.06%)**, still 19.47% below fresh UD. Greedy tokens
match, but logits change and independent operator limits fail; it remains an
isolated performance lead. Complete rates, durations, samples and graphs are
retained. No numerical limit is relaxed or runtime promotion made.
The subsequent [HC consumer-narrowing comparison](docs/Q2-HC-INPUT.md) preserves
all 21 saved model outputs but lowers prefill to **1289.12 tokens/s (-2.05%)**,
despite a 6.34% component time saving. It is rejected; complete rates, durations
and every measured sample are retained with a graph. One additional synthetic
FP64 case fails on both identical paths at the unchanged threshold. Fresh
profiles locate the loss: removing 96 narrowing calls saves 60.19 ms, but the
consuming HC down projection adds 90.67 ms. All 28 profile replay checks pass;
the experiment does not establish a hardware cache cause.
The prior [expert-kernel experiment](docs/Q2-EXPERT-STACK.md) produced the main
prefill gain: 1240.52 tok/s, up 88.29% over the previous HC checkpoint.
The initial unoptimized screen was 48–66% slower in prefill and 16–17% in decode.
See the [complete results and plots](docs/Q2-RESULTS.md) and the now-qualified
[Q2/UD phase profiles](docs/Q2-PROFILING.md). The first WMMA down
[experiment](docs/Q2-DOWN-EXPERIMENT.md) improved PP by 34–64% but exceeded the
saved-logit limit and was rejected. The subsequent
[integer scheduling experiments](docs/Q2-REGISTER-EXPERIMENT.md) reduce static
register spills but fail exact operator replay. The original runtime is restored;
the subsequent owner-authorized [performance exploration](docs/Q2-PERFORMANCE-EXPLORATION.md)
measures +13–42% PP for bounded K and +1–28% for the barrier. Numerical work
and the overall no-regression target remain open.
The separate [F16 HC down experiment](docs/Q2-HC-EXPERIMENT.md) measures a
2.86x component speedup and about 12% higher model decode, with original weight
bytes. The fresh reference is thermally interrupted; the comparison is
incomplete and the candidate remains 5.7% below UD decode at 2K.
The subsequent [HC prefill WMMA experiment](docs/Q2-HC-PREFILL.md) completes both
matched model arms: PP rises from 608.8 to 658.8 tok/s (+8.22%), TG stays near 23.
All changed synthetic operator cases pass; greedy tokens match, but model logits
differ. The candidate still trails UD and remains isolated. The owner-approved
test ceiling is now 98 C inclusive, with lower exposed hardware limits retained.

The packed activation move passes 30 independent GPU operator cases, 32 exact
packing/down/chain checks and 42 saved-model comparisons against fresh/retained
Q2 references. Fresh UD also replays all 21 retained model buffers exactly.
[Complete samples and graph](docs/Q2-PACKED-ACTIVATIONS.md#fresh-complete-model-performance)
include prefill/decode rates and durations. The current baseline profile points
to remaining HC projection/epilogue and activation-conversion costs.

The [raw-F16 HC up/mix fusion](docs/Q2-HC-UP-FUSION.md) passes seven GPU cases
and 19 byte-exact complete buffers. It removes the intermediate gate write/read
and emits the existing half input in the producer. Prefill improves 2.91% over
the fresh packed checkpoint; decode is unchanged. The subsequent
[scalar HC up vector kernel](docs/Q2-HC-UP-VECTOR.md) speeds up its isolated
component 15.22% and the full-model decode 1.16% without model-logit drift.

The subsequent F32 MoE/HC fusion retains the original norm reduction and passes
eight GPU cases with 15 exact complete buffer pairs. Its component is 9.74%
faster; full-model prefill improves 0.92% while decode measures 0.21% lower in
the fresh comparison. Complete samples, durations and the new graph are in
[Q2-HC-MOE-FUSION.md](docs/Q2-HC-MOE-FUSION.md).

The subsequent [paired F32/F16 norm experiment](docs/Q2-HC-NORM-FUSION.md)
passes every saved operator and model replay, but prefill falls from 1294.14 to
1289.12 tok/s (-0.39%) despite 12–16% component speedups. It is not retained as
a performance improvement. Its fresh UD control reaches 1683.84 PP/24.33 TG;
complete timings, the initial rounding failure and graphs are preserved.

Separate [HC down prefetch variants](docs/Q2-HC-PREFETCH.md) retain exact
synthetic outputs but are 0.44% and 7.35% slower in the rotating-weight GPU
microbenchmark. Neither is promoted.

The [n-gram/PLE investigation](docs/Q2-PLE-ANALYSIS.md) exposes a separate
new-input bottleneck hidden by repeated padding: first varied 2K input spends
3,374 ms waiting for Q2 rows versus 169 ms for UD. Q2's row cache holds four
times fewer entries, and sampled Q2 PLE extents are compressed by Btrfs while
sampled UD PLE extents are not. Hashing is below 0.08 ms. This is instrumented
diagnostic evidence; the warm-padding GPU performance deficit remains distinct.
Complete first/repeated results and a graph are retained. The new
[64x64 HC down tile](docs/Q2-HC-DOWN-TILES.md) is byte-exact but 5.93% slower.
The three follow-up scheduling variants also preserve the outputs and regress
component time by 9.03–79.97%; their numerical control failures remain explicit.

The subsequent [PLE I/O/cache comparison](docs/Q2-PLE-CACHE.md) measures about
21x physical read amplification on new Q2 row sets; descriptor-local RANDOM
advice gives no benefit. A 64K-row BF16 cache halves repeated row-gather time,
but complete varied 2K prefill improves only 1.09% and forced decode is unchanged.
All 264 compared model frontiers replay exactly. The extra cache stores 15 MiB
more encoded rows plus metadata; it remains an isolated instrumented experiment.
The report includes the full comparison, graph and retained validation failures.

The [reactive PLE lookahead experiment](docs/Q2-PLE-LOOKAHEAD.md) prepares the
next prompt chunk using a bounded C17 two-buffer flow. Its lifetime, ordering
and cancellation fixtures pass on `.157` in Debug and ASan/UBSan. Original-Q2
8K comparison verifies 432 exact frontiers and 174–187 ms of hidden preparation,
but prefill improves only 0.36% over native (1236.75 -> 1241.15 tokens/s).
This small repeated-input result does not establish a robust speedup or parity;
the qualified runtime remains unchanged. Full samples and a graph are retained.

The [balanced new-input follow-up](docs/Q2-PLE-FIRST-ACCESS.md) measures a
substantial I/O-bound benefit: 8K prefill falls 10.982 -> 7.791 s, **+40.96%**
throughput, with similar observed page residency and physical traffic across
first-position groups. On replay the gain is only 0.57%. All 576 frontiers match.
This is an isolated scheduling result, not controlled identical cold states,
production adoption or warm Q2/UD parity. PLE in the Q2-named model is BF16;
filesystem compression is a separate layer and its causal contribution remains
unisolated. The report includes every prefill/decode sample, graph and CSV.

The [Q2 weight-staging candidate](docs/Q2-STAGED-WEIGHTS.md) passes independent
GPU checks, 62 saved-buffer comparisons and 52.4 million exact synthetic output
values, but its component is 4.94% slower. It is rejected. The subsequent
[paired half-wave decode](docs/Q2-HALF-WAVE.md) preserves all outputs with the
original shared-memory footprint, but shuffle is 1.44% slower and direct row
permute is effectively unchanged (+0.05% time). Neither is promoted; the report
retains the independent checks, all timing samples and the unchanged control.

The [HC coalesced-fetch probe](docs/Q2-HC-DOWN-COALESCED.md) preserves all
outputs but changes component throughput only 0.66%, within the overlapping
sample distributions. No model sweep or runtime promotion follows.

The [packed-Q2 code-reuse probe](docs/Q2-CODE-REUSE.md) retains original code
bytes across adjacent stages. It passes independent GPU checks and exact replay,
but increases component time 2.59%, with an unchanged control at -0.13%.
It is rejected; all samples, graph and closure evidence are retained.

- [Implementation and evidence](docs/Q2-IMPLEMENTATION.md)
- [Audit and source pins](docs/ANTIREZ-Q2-AUDIT.md)
- [Format and storage contract](docs/Q2-FORMAT-CONTRACT.md)
- [Correctness and performance protocol](docs/Q2-VALIDATION.md)
- [Progress](docs/PROGRESS.md) and [third-party provenance](third_party/README.md)

The reviewable change is `patches/gufo-q2.patch`. Given the exact official
archive recorded in `config/gufo-source.json`, reconstruct it with:

```sh
python3 tools/prepare-gufo.py .deps/gufo-f783fedb.tar.gz .deps/gufo-q2-reconstructed
```

The qualification capsule builds the pinned upstream HIP executor and tests;
it is not a replacement for the C17 LIE core or `synapse-lie-bench`. Run the
fixed remote checks with `tools/q2-remote.py`; GPU modes acquire all four known
nonblocking leases and refuse contention. Sources and evidence stay in persistent
project directories. Models are read-only; no conversion, deployment or publication.

Branch `feature/antirez-compat-audit` starts at empty `develop` (`ce3ce59`).
The server/cache branch is separate. Q4, MXFP4 predictor execution, HTTP
integration, concurrency qualification and long-context qualification remain
separate gates. The original Q2 predictor descriptor is understood with MTP off.

The [shared-Q8 focused model plan](config/q2-shared-q8-fixed-model-plan.json)
retains the existing exact2048 Q2/UD references and runs only the new candidate
under the owner’s explicit exploratory authorization. Host gates pass23/23 in
Debug and ASan/UBSan; component numerical rejection remains recorded.

The [completed shared-Q8 model comparison](docs/Q2-SHARED-Q8-FIXED-MODEL.md)
measures1446.083285 PP and25.10338822 TG on the unchanged exact2048 input.
All21 saved Q2 replay files and logits remain identical. Fixed UD parity
remains open; no controls were relaunched and the .157 window is released.

The [retained-composition recheck](config/q2-reaudit-composition-plan.json)
now measures Q8+row reuse at1451.924906 PP/25.14929256 TG and the additional
fixed norm at1452.143206 PP/25.18103518 TG on the unchanged reference.
Only the two new candidates run; historical Q2/UD results are retained.
The first preserves all21 Q2 replay files; the second preserves the previous
norm replay, including its changed logits. Fixed UD prefill parity remains open.
[All samples, comparisons and graph](docs/Q2-REAUDIT-COMPOSITION.md).

The [independent Q8 saved-array replay](docs/Q2-ORACLE-REPLAY.md) confirms a
fixture initialization race:40/40 same-stream outputs match every production
byte, while39/40 legacy cross-stream outputs differ. The independent GPU
arithmetic and15 saved arrays are unchanged. Configure/build/replay exit0/0/0;
84 artifacts verify. The original producer fixture now initializes its oracle
on the same stream; host Debug/ASan pass23/23 each. No model, production kernel
or qualified inference control rerun occurs, and existing PP/TG values remain.

The [original-F16 HC-down comparison](docs/Q2-HC-DOWN-BK256.md) now measures
the bounded port at **1477.969324 PP /25.10545360 TG** on the unchanged fixed
2048 model input: **+2.376% PP versus fixed Q2**, +1.794% versus its saved
Q8+row parent, and **12.327% below fixed UD**. Only this new model runs;
qualified controls are reused. All128 greedy tokens match Q2, while eight
logit files change (maximum matched-history KL0.001732). Strict component
failures remain recorded and independent task quality remains open.
The bounded kernel saves30–33% of projection time and9–13% of complete
producer/projection time; the spilled first version is much slower and retained.
All112 component samples,16 plotted model samples, graphs and source identities
are saved. Initial small-shape FP64 recovery finds native errors roughly half
the library errors. Later unchanged-output BK128/BN64 fixtures recover unrounded
2048 errors: all aligned native cases pass the original limits, library cases fail.
The .157 GPU window is released. Full curves still wait for fixed-point parity.

Two [new BK128 staging candidates](docs/Q2-HC-BK128.md) change only the measured
bounded kernel's launch template. They compile with97/98 VGPRs and zero private
scratch, but actual GPU tests show both are slower than the saved BK256 parent.
Double buffering saves 5.830%/4.417% ordinary/MoE cycle time against its library,
less than the parent's 13.048%/8.827%; no model is selected. All 112 new timings,
graph and 88 artifacts remain. Every new output matches the parent. Unrounded
FP64 checks at 2048 pass for the native kernel and fail for the library under
unchanged limits; 97 ordinary remains slightly outside. Independent model
quality remains open. Host Debug/ASan pass 23/23; the .157 window is released.

Two [wider-token HC tiles](docs/Q2-HC-BN64.md) measure 64-token workgroups
with two wave partitions. They change only the launch template/grid, retaining
original F16 operands and each output's two K16 chains. Both compile without
spills; host Debug/ASan pass 23/23. Both GPU components retain all 112 timings
despite exits 0/0/1. All parent outputs match, but the best normalized complete
cycle regresses 42.973%; no model is selected. Unchanged FP64 limits pass at
2048 for native down and fail for library down; strict byte rejections remain.
Graphs and all samples are saved; the .157 window is released. Fixed-model
PP remains 1477.969324 against UD 1685.777092.

The [current rejected-family recovery audit](config/q2-rejected-recovery-scaled-update.json)
verifies all nineteen original report hashes: fifteen candidate records represent
eleven families, alongside four host/status reports. Five mechanisms already
belong to fixed Q2, five families have new measured compositions, and one has
measured cycle regressions. No selective model integration in that inventory
remains pending. Only shared-Q8
has a confirmed false format-rejection cause. This does not establish nineteen
independent gains or parity; the new selective candidate still needs 12.565%
higher throughput for UD.
The [reconciled recovery explanation](docs/Q2-REJECTED-TEST-REAUDIT.md) shows
the saved complete-model comparison and identifies earlier pending counts as
historical; no qualified measurement is rerun or overwritten.

A [new MoE-only deferred-norm composition](docs/Q2-HC-MOE-DEFERRED.md) integrates
one pending family into the best measured provider. It reuses HC-gate scratch
for scales, with C17 producer/consumer identities and a reconstruction fallback.
Ordinary/Q8 routes remain; no device allocation or stream is added. The numerical
port compiles without private scratch; .157 host Debug/ASan pass 24/24 each.
The frozen plan admits only one new fixed model, retaining prior numerical
rejections and reusing all qualified references. That model now measures
**1496.830907 PP /25.17435733 TG**, +1.276% PP versus saved best parent and
**+3.682% versus fixed Q2**. All128 output tokens match; eight logits files change,
with maximum matched-history KL0.001257 to Q2. Only this new model runs; the
.157 window is released. Candidate PP remains11.208% below fixed UD;
the candidate needs12.623% higher throughput. Independent task quality and
full-curve parity remain open. Every new and saved sample is retained.

A [saved-candidate kernel diagnosis](docs/Q2-FIXED-MOE-PROFILE.md) reuses that
binary and the original2048 input without recompilation or comparator reruns.
Prefill GPU busy is99.639% of kernel span: routed gate/up+down total443.146 ms
and Q8 dense339.606 ms. It prioritizes numerical kernel load/decode work while
keeping reactive concurrency and serving gains separate. Complete stage/kernel/
routing CSVs and a graph are retained. The shortened diagnostic decode does
not replace the fixed pp2048/tg128 result1496.830907/25.17435733; quality and
the complete context-curve target remain. The .157 window is released.

A [grouped Q8 decode/store experiment](docs/Q2-Q8-GROUPED.md) now tests that
diagnosis. Its new operator passes 12 complete output comparisons and saves
2.280% SSM / 1.208% output-projection time, but the original exact2048/tg128
model measures **1495.403157 PP / 25.16620404 TG**, within the saved parent's
sample range. No whole-model gain is observed. All 21 model input/output/logit
files match the parent byte-for-byte. The best measured composition remains
**1496.830907 PP**, against unchanged fixed UD **1685.777092**. The variant and
all samples remain available without promotion; only new candidate runs occur,
no qualified comparator rerun or full curve. The `.157` window is released.

The [selective Q2 tile composition](docs/Q2-SCALED-SELECTIVE.md)
is measured on the saved MoE parent. A C17 selector assigns 64-row down tiles
to large expert buckets only when row reservation does not increase; others
retain 48. Existing numerical kernels and gate/up maps remain byte-identical.
It reuses buffers and retained component evidence. Only the new original fixed
model runs: **1497.606050 PP / 25.15356932 TG**, +0.051786% PP versus parent,
with overlapping ranges. All21 model input/output/logit files are exact to
parent. Actual routing selects64 for28.591105% of rows but reduces total row
reservation only0.400847%. The marginal candidate is retained without promotion;
fixed UD remains1685.777092 and full-curve/independent quality remain open.
The `.157` window is released; complete samples and routing records are saved.

A [new IQ2 shared-F16 stage](docs/Q2-IQ2-HALFSTAGE.md) targets duplicated
half-wave weight conversion in the saved254.797 ms gate/up stage. The producer
uses the same packed add/FMA and ordered K16 consumers read staged halves.
XOR activation layout keeps the expanded BN128 stage at32768 bytes. Local
compilation preserves149 other kernel bodies and has zero private scratch;
larger LDS/register requirements remain a runtime risk. The new fixture has
a literal saved control, ragged/packed output coverage and rotating weights.
The new component preserves81 complete outputs but slows13.640–16.820%.
Its new original exact2048/tg128 model also runs:1465.267121 PP /25.19208710 TG,
-2.109% PP versus parent, with all21 parent replay files exact. No default
promotion follows; source, all samples and graph are retained. The `.157`
window is released. The fixed Q2/UD comparison and full-curve target remain.

A [compact IQ2 half-byte candidate](docs/Q2-IQ2-HALFBYTE.md) keeps one byte per
weight in the existing LDS stage and reconstructs its exact signed F16 bits.
Local assembly removes the consumer half additions, retains rounded half FMA
and ordered WMMA, and preserves LDS/register sizes at widths 48/64/128. Both
encodings pass exhaustive host format checks; the permutation variant uses
fewer instructions while shifts add instructions. Only one new component/model
pair runs with the unchanged fixed comparison. All 81 whole component outputs
and 3,670,016 packed format-word pairs are exact. New model PP 1498.799455 / TG
25.16866636 nominally adds 0.131514% PP versus saved parent, with every parent
replay file exact. The marginal candidate is retained without default promotion
or stable-gain proof. Fixed UD still needs 12.475160% more PP throughput; model
task quality and full-curve parity remain open. The `.157` window is released.

A new [Q8 integer-half pair lookup](docs/Q2-Q8-HALFPAIR.md) starts from that
compact parent and replaces dense Q8 conversion with a generated 256 KiB
device table. Original rounded scale/FMA, WMMA order and stage sizes remain.
Local assembly preserves 149 other bodies; indexed loads increase total
instruction counts despite removing the conversion adds. All 84 launch guards
and the new `.157` Debug/ASan host fixtures pass. All 12 component buffer pairs
are exact; a false coverage failure checks intentionally unused SSM raw cells.
The actual component exit 1 and saved-array diagnosis are retained separately.
Its new original fixed-input model completes at 1114.763382 PP/25.16483410 TG,
a 25.622913% PP regression versus the compact parent, with all 21 parent replay
files exact. The lookup is retained as a measured rejection; the best composition
remains 1498.799455 PP. Qualified controls and the full curve are not rerun.
All samples and a comparison graph are saved; the `.157` window is released.

A new [SSM row128 projection](docs/Q2-SSM-ROW128.md) starts from the retained
compact IQ2 source, halves accumulator values per thread and explicitly sizes
the existing convolution transpose to36KiB. The row grid doubles, so lower
static counts are not a speedup claim. Local compilation preserves156 other
kernel bodies; the new fixture verifies all required raw SSM values and full
convolution outputs at1024/1025/1057/2048 tokens: all24 pairs are exact and all
required values written/finite. Component time regresses86.359829%; its new
original fixed model measures1434.616272 PP/25.16688019 TG,4.282306% less PP
than the retained compact parent, with all21 replay files exact. All samples
and the graph are saved. The measured rejection does not replace the best
1498.799455 PP composition; no qualified control or curve is rerun. The initial
admission helper-path failure and corrected plan remain retained; the `.157`
GPU window is released.

A new [deferred IQ2 raw-prefetch candidate](docs/Q2-IQ2-RAW-PREFETCH.md) keeps
tile geometry and compact staging while moving unchanged expansion to LDS
commit. Local assembly reduces next-free VGPR by5–6 in eight IQ2 bodies,
preserves149 others and keeps LDS/private scratch unchanged. A new full-output
fixture and the unchanged original fixed model comparison are prepared;
no GPU performance, quality or parity claim follows from static counts.

The new [IQ2 raw-prefetch result](docs/Q2-IQ2-RAW-PREFETCH.md) preserves all81
component outputs and reduces synthetic IQ2 time4.407–6.317%. Its original
fixed model measures1505.152258 PP /25.15493858 TG: nominally+0.423859% PP versus
the compact parent, with all21 parent files/logits exact. Retain this new base;
no default/independent quality promotion or full curve follows. Fixed UD still
needs12.000436% more PP throughput. All samples/graphs and original local launch
failures remain. The R2 GPU window is released; no qualified control is rerun.

A new [persistent Q8 mirror experiment](docs/Q2-Q8-MIRROR.md) preserves native Q8 accumulation/decode while preparing GPU F16 dense weights once at upload. The own C17 policy bounds auxiliary allocations to6GiB; expected resident increase is5,348,130,816 bytes. All157 original kernels preserve instructions/operands/resources. New whole-output, scale/code and unchanged2048/tg128 model checks are prepared; performance remains unmeasured. Q4/curve and qualified control reruns remain suspended.

The [Q8 mirror experiment](docs/Q2-Q8-MIRROR.md) completes on .157: all11,534,848 format combinations,66 whole-output pairs and21 saved-parent model files are exact. New PP1472.566824/TG25.18240342 loses2.164926% PP to the unchanged1505.152258 base and adds5,348,130,816 resident bytes. The candidate is retained as a negative storage result without promotion; no reactive gain is claimed. All13 exits0/39 artifacts verify,26+26 host gates pass, and the777-identity/614-group window is released at07:57:20UTC with four free original leases, empty KFD and unchanged model stats. Complete samples and graph are saved; Q4/curve remain deferred.

Two new [compact IQ2 commit variants](docs/Q2-IQ2-SLICE-COMMIT.md) complete on .157:81 component pairs and21 parent model files are exact per variant, but PP1493.182914/1500.783083 regress0.795225%/0.290281% against saved best1505.152258. Allocated VGPR/LDS remain unchanged. All20 runtime exits0/67 artifacts verify;26+26 host tests and103 launcher guards pass. Complete samples and graph are retained, with no old control rerun or promotion. The window releases at08:50:49UTC; best1505 remains unchanged.

A new [whole short-expert IQ2 tile candidate](docs/Q2-IQ2-SHORT-TILES.md) preserves original128/64 routing for other experts and all numerical kernels. Bounded C17 coverage, sanitizer and HIP syntax checks plus105 launcher guards pass;39 guarded GPU pairs and the unchanged2048/tg128 model comparison remain pending. The counted provider emits bounded usage records after timers. Saved best1505 and qualified controls stay unchanged; no Q4, full curve or GPU gain is claimed.

The [whole short-expert48 experiment](docs/Q2-IQ2-SHORT-TILES.md) completes on .157:39 guarded GPU pairs and21 parent model files are exact, but PP1493.009363 regresses0.806755% against unchanged best1505.152258. Actual192 routing records retain45120 short48 descriptors; the original64 kernel already skips nonlive WMMA fragments. All13 runtime exits0/37 artifacts verify and27+27 host gates pass. The818-identity/647-group GPU window is released at09:39:41UTC, with four free original leases, empty KFD and seven unchanged model stat tuples. Source, complete samples and graphs remain retained; no old comparator, Q4 or full curve is rerun.
