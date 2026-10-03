<!-- SPDX-License-Identifier: MIT -->
# Synapse LIE — original Q2 support for official Gufo

This isolated workstream adds the original antirez Q2 GGUF to official Gufo
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, without the antirez Qwen engine.
The minimum acceptance requirement remains **no prefill or decode regression**.
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
