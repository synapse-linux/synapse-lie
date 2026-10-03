<!-- SPDX-License-Identifier: MIT -->
# Synapse LIE — original Q2 support for official Gufo

This isolated workstream adds the original antirez Q2 GGUF to official Gufo
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, without the antirez Qwen engine.
The acceptance target is **Q2 at least as fast as UD in both prefill and decode
at every point of the requested context curve**. The
[canonical comparison contract](docs/Q2-CURVE-PARITY.md) restores Gufo's HTTP
pp2048/tg128 prose workload and ordered cached-prefix depths from 0 to 128K.
The complete Q2/UD curve has not yet been measured. Historical counting-prompt
tests, including the 1411→1439 prefill result, are diagnostics with a different
workload and timing scope; they do not fill cells in that curve.

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
