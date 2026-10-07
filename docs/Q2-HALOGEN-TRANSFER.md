<!-- SPDX-License-Identifier: MIT -->
# Halogen performance clues for the Q2 long-context goal

This is an independent, read-only comparison of [Halogen's published
measurements](https://github.com/peonist-ai/halogen-flash-server#measured) and
[release notes](https://github.com/peonist-ai/halogen-flash-server/blob/main/CHANGELOG.md)
as viewed on 2026-10-07. The public repository publishes documentation,
deployment and API tooling, but not the numerical engine source. No Halogen
binary, kernel or model artifact is imported into LIE. Its model weights,
compression, arena and measurement conditions differ from the retained Q2
benchmark, so its rates are not LIE controls.

## What matters for the present goal

| Published clue | LIE evidence | Decision |
| --- | --- | --- |
| Halogen 0.14.1 changes its routed-expert prefill kernel. Its own 131,072-token prefill moves from 1,390 to 1,517 token/s, with rounding-level numerical differences. | The saved LIE 2,048-token profile attributes 401.058 ms of 1,321.833 ms kernel time to routed IQ2 gate/up and Q2 down. This older profile is a ranking aid, not a 128K attribution. | Highest-priority algorithm family. Qualify a complete expert-chain change on original routing and arithmetic; do not infer its speed from Halogen's result. |
| Halogen 0.12.0 parallelizes sparse-index selection for one-row decode and reuses block keys in prefill scoring. Its published improvement is largest at 262K–1M. | LIE has a partition-selector component with exact output and 22.429% lower 128K **one-row** selector latency. The original128K trace has3024 prefill score/mark slices of up to512 rows each; the one-row gain cannot be extrapolated to them. Four-query key reuse was exact but 2.15–4.09 times slower. | Test decode selection separately from full prefill. No prefill saving from the partition component has been established; keep the current scorer. |
| Halogen ships a shape-tuned matrix plan. | LIE already has shape-specific native kernels and a hipBLASLt HC-down comparison. All seven tested library alternatives changed numerical outputs; the selected native route remains the qualified one. Dense Q8/F16 is 293.227 ms in the older 2K profile. | Tune an active Q8 shape only with a matched operator and original-model numerical gate. Do not substitute the Halogen plan or claim its result. |
| Halogen's prompt cache avoids repeated prefill on follow-up turns; the 0.12.1 release removed a redundant DeltaNet replay during cold capture. | The LIE target is one complete cold request with zero cached tokens and its original capture policy. LIE's saved long diagnostic has no attributed second recurrence pass. | Audit capture cost only if an actual duplicate pass is found. Cache-hit TTFT cannot count toward cold prefill throughput. |
| Halogen's reported serial greedy decode is 37.6 token/s at 1.5K and 34.1 at 32K; larger served rates use MTP and sometimes prompt lookup. | LIE's 128K record has only eight output calls, so its 25.344 token/s is not a sustained TG128 measure. The native C1 completion-to-next-submission gap is 0.092–0.097 ms, leaving numerical execution as the likely major cost. | Compare serial C1 with serial C1. MTP, lookup and batching may improve serving separately; they do not establish the 30 token/s C1 goal. |
| On the same Halogen engine and machine, its own 4-bit dense trunk reached 35.4 serial token/s at short context while a losslessly repacked UD-IQ4_XS GGUF with 8-bit dense layers reached 25.4; Halogen attributes the difference to about 2 GB more weight traffic per token. | LIE's retained large Q8 decode projections read roughly 222–228 GB/s of logical weights in isolated tests; an older whole-step profile assigned about 49% of decode device time to dense Q8 GEMV. These are different models/inputs from Halogen's matched pair. | Treat dense weight bytes as the leading C1 decode hypothesis. Reordering Q8 instructions cannot remove those bytes; a narrower representation would need a separate quality contract and original-model gates, since it is not lossless for the current Q8 weights. |
| Halogen 0.15.2 optionally keeps its compressed trunk unpacked in memory, using about 5.5 GiB extra for faster long prompts. | LIE already tested a persistent 5,348,130,816-byte Q8 mirror: exact outputs, but original 2K prefill fell 2.165%. The representation, packing and kernels differ. | Do not repeat an unconditional mirror. A new residency design needs an identified consumer and a whole-model win. |
| Halogen's 32K prefill arena is about 9% faster than its 16K arena at a 262K served prompt, with a larger memory footprint. | LIE's retained benchmark uses 2048-token model chunks and its own scratch layout; `HALOGEN_MAX_TOK` is not an equivalent setting. | Inspect LIE's actual expert/attention tile occupancy before considering an arena or chunk change. Preserve the fixed 2048-token benchmark as the comparison control. |
| Halogen 0.15.3 reports faster prompts of every length, and 0.16.1 reports faster decode, especially with concurrent conversations. The changelog does not expose the numerical kernel implementation or a matched C1 rate for these changes. | LIE's serial C1 target and concurrency/reactive measurements are separate. | Treat the release notes as attribution leads, not measured transferable gains. |

## Additional source and measurement checks

Halogen's [0.14.1 note](https://github.com/peonist-ai/halogen-flash-server/blob/main/CHANGELOG.md)
explicitly permits rounding-level differences from its new routed-expert prefill
kernel. A future LIE expert-chain candidate should therefore report both
byte-exact checks where expected and bounded numerical/quality checks where the
operation order changes. A byte mismatch alone does not establish harmful model
error; neither does a small component error establish acceptable quality. The
original cold request and an independent quality task remain the model gates.
This observation does not relax an existing candidate's recorded gate after the
fact.

Halogen's 0.12.1 cold-cache fix removed a second DeltaNet recurrence that its
own cache capture ran over the prompt. In the inspected private LIE provider,
`Executor::SaveSnapshot` walks existing device state and transfers its bytes;
it does not call `GatedDeltaNet` again. The original long request also reports
zero reused prefix tokens. A Halogen-style recurrence deletion is thus not an
identified LIE saving. Snapshot transfer cost can be measured separately if
it appears on the original critical path.

The saved `.157` original128K diagnostic samples 51 GPU-busy (>90%) moments:
median reported clock2635MHz, busy96%, GPU sensor power140.641W and GPU
temperature89°C. These are two-second samples from a *profiled* run, not an
unprofiled throughput control. Halogen reports a2229MHz median clock and about
85W sustained **package** power for its own32K prefill; its power measurement
scope is not established as the same as `.157`'s GPU `power1_average` sensor.
The observed `.157` GPU clock does not suggest a simple sustained underclock
relative to that published condition. It cannot isolate a kernel gap, cooling
effect or IOMMU effect. The `.157` command line lacks an explicit
`amd_iommu=off`, which alone does not establish the runtime IOMMU state.

The exact-output live-grid selector component reduced completed32K slice time
26.8%, but its first original32K model request fell10.7% in prefill rate.
Its approximate telemetry window had median GPU clock2439.5MHz against
2648MHz for the saved retained request, a separate-session confound rather
than proof of the cause. A subsequent [matched original32K A-B-B-A
replay](Q2-SELECT-LIVE-GRID.md) completed at1424.717 retained versus1431.531
live-grid token/s, **+0.478%** mean rate with all outputs exact. This supersedes
the first trial as the controlled 32K effect; no 128K effect is measured.
The modest full-model gain cannot be inflated from the component result and
does not justify promoting this candidate toward the large 128K target gap.

Halogen's 131K uplift is 9.137% in rate. Applying that percentage to LIE's
retained 1,310.875 token/s would give only 1,430.645 token/s; another 4.848%
rate gain would still be required. This is arithmetic, **not** a prediction.
LIE needs the complete 130,925-token request to fall from 99.876067 s to at
most 87.283333 s, with capacity 133760, chunk 2048, the exact saved prompt,
and zero cached tokens. Its 63 intermediate chunks are full 2048-token chunks;
the 1901-token tail is the only partial chunk.
The saved native 32K serial decode interval is 38.606–38.681 ms per step;
30 token/s requires at most 33.333 ms, about 5.27–5.35 ms less per step.
Its observed host completion-to-next-submission gap is under 0.10 ms, so
reactive wakeups alone cannot supply that reduction.

Halogen's 1517 token/s at131K is from its own checkpoint and engine-side cold
prefill, not a generic rate for every GGUF it serves. Its same-session
UD-IQ4_XS GGUF comparison reports served prefill1465 token/s at32K against
1499 for its own w4b checkpoint; the prompt and configuration also differ
from LIE's saved request. This comparison isolates an important mechanism:
Halogen says the 8-bit dense GGUF trunk reads about2GB more per decode token
than its own 4-bit trunk, reducing serial short-context decode from35.4 to
25.4 token/s on the same engine. LIE's large Q8 GEMV component is already
near222–228GB/s in logical weight traffic, so eliminating instructions alone
is unlikely to recover the required5.3ms per C1 step. That is a bandwidth
hypothesis, not a measured LIE memory-controller ceiling or a license to
change Q2 weights. A narrower trunk must be opt-in and separately qualified
for quality, numerical behavior and the original cold PP/C1 TG controls.
The [bounded original-Q2 Q8 screen](Q2-DENSE-DECODE-FEASIBILITY.md) further
rules out simple lossless per-block range packing in its four sampled tensor
families: every sampled block requires eight code bits. A Q6 format has only
weight-domain error evidence and no kernel or quality acceptance.

## What the original128K trace changes

The [completed 130925-token diagnostic](Q2-LONG-PROFILE.md) matches all64
unchanged prefill chunks and eight output calls. The quarter means for its
twelve full-attention completion boundaries rise437.4,502.5,556.1,591.1ms;
overall completed intervals rise1468.3,1544.2,1599.2,1606.5ms. Every one of
the twelve boundaries shows a similar depth trend. These host boundaries
include previous-layer MoE/shared and current-layer attention/HC; all GPU
event durations are invalid zero. They nominate the complete full-attention
chain for one bounded test, but cannot assign154ms/chunk solely to selection,
scoring, V loads or memory traffic. The partition-selector component covers
one decode query; its10.889µs gain cannot be multiplied by the prefill's
3024 multi-query slices. The tested four-query score reuse and V staging
candidates regress or have no clear gain. Repeating
either cannot plausibly close the12.59s gap.

The depth-dependent part of those boundaries is about5.40s if every later
chunk is arithmetically held to the first-quarter mean. That is an
instrumented counterfactual, not a predicted improvement; even such a change
would leave more than7s of the target gap. Halogen's 0.12.0 indexer work has
the strongest published benefit at262K–1M, whereas its 0.14.1 routed-expert
prefill kernel lifted the131K row as well. For LIE the next serious candidate
must remove work in a complete chain: first test the active routed-expert
gate/up→pack→down path and its weight reuse; in parallel design an attention
candidate that reduces *all* repeated block-key work without collapsing query
parallelism or adding register pressure. Follow with the original cold128K
model input before promoting either. The public Halogen repository does not
publish its numerical kernels, so this is a hypothesis from release notes and
LIE measurements, not a port of their implementation.

Halogen's own serial greedy rows are the relevant decode comparison; its
46–56 token/s served rows use a draft head and sometimes prompt lookup. LIE's
greedy sampler is already present. The native under0.1ms completion-to-next-
submission gap gives little host-only headroom. A decode candidate therefore
needs to reduce the actual per-step numerical path, and a separate sustained
128-token C1 measurement must qualify30 token/s.

## Bounded next expert experiment

The [saved fixed-input routing](../config/q2-current-routing-v2-results.json)
contains all 48 layers, 512 expert counts per layer and 20,480 routed rows per
layer. Recomputing the active `floor(ceil(rows / 64) / 2)` wide-IQ2 descriptor
rule gives 6,813 128-token descriptors, matching the archived counts. Of
these, 4,592 (67.4%) belong to the 892 expert/layer pairs receiving at least
256 rows. Pairing successive wide descriptors within each expert would cover
4,180 descriptors (61.35% of all wide descriptors). These are logical work
counts, not measured DRAM reads: cache residency, register pressure, LDS size
and occupancy may erase or reverse any saved fetches. This route fixture is
the fixed 2K input; long-context routing must be checked before extrapolation.

The bounded trial reused one expert's encoded IQ2 weights across successive
**token** tiles, restricted to experts with at least two wide descriptors. It
preserved the existing 640-by-2560 paired gate/up arithmetic, output order,
top-10 routing and 2048-token model chunks. The first GPU screen compared
whole gate/up outputs and completed timings on archived routing counts. The
screen regressed, so the planned compact+gate/up+pack+down and original 32K/
128K model gates were correctly skipped. The prior BM256 experiment enlarged
**output** rows and had also regressed; it tested a different axis.

The private token-side probe changes no production dispatch. Its C17 map
covers every live 64-row unit exactly on all 48 saved routing layers and 18
boundary shapes. Static device compilation preserves all 164 retained bodies
and adds one 256-token body without private scratch. That body uses 242 VGPR
and 42,112 bytes of LDS, versus 150 VGPR and 25,728 bytes for the 128-token
body. The exact manifest, assembly analysis and isolated patch are in
`../config/q2-iq2-token256-probe-source.json`,
`../config/q2-iq2-token256-probe-static.json` and
`../experiments/q2-iq2-token256-probe.patch`.

The .157 host gate passes 43 Debug and 43 ASan/UBSan checks. A single
coordinated GPU component then passes all 15 route maps and 51 guarded,
byte-exact whole-output replays across three rotating synthetic weight sets.
No original model weights are read. All 84 HIP event durations are invalid
zero; the table uses medians of five completed host-wall samples per arm,
after two warmup repetitions. Both arms process the same 2048-token shape.

| Gate/up component routing | Retained128 median µs | Candidate256 median µs | Time change |
| --- | ---: | ---: | ---: |
| Uniform, 160 experts | 3633.256 | 3620.203 | −0.359% |
| Uniform, 512 experts | 5492.852 | 5482.586 | −0.187% |
| Skewed, 64 experts | 3776.666 | 3922.846 | +3.871% |
| Saved layer 0 | 5193.263 | 5318.400 | +2.410% |
| Saved layer 3 | 4136.297 | 4287.383 | +3.653% |
| Saved layer 22 | 5489.219 | 5627.818 | +2.525% |

The three saved-routing cases all regress. Higher VGPR/LDS usage may explain
some of the loss, but this experiment does not isolate occupancy from memory
or scheduling effects. The release receipt confirms an empty KFD, free
original leases, unchanged model stats and no remote cleanup. The bounded
gate therefore stops here: there is no complete-chain or original-model
trial, and no 128K PP or serial TG gain. The retained 128/64-token dispatch
remains active. [Validated component results](../config/q2-iq2-token256-component-results.json)
and [coordination receipt](../config/q2-iq2-token256-window-release.json)
preserve the exact samples and closure. The next prefill candidate must change
useful work across the **complete** expert chain or a measured dense Q8
projection, with unchanged original-input model gates before promotion.

The next private screen changes the IQ2 gate/up *weight layout* without
changing any quantized byte. It puts the two groups used by each stage for 16
successive rows in one contiguous 256-byte segment. The
[stage-pair layout probe](Q2-IQ2-STAGE-LAYOUT.md) preserves all production
kernel bodies and compiles one new private body. The completed .157 screen
passes 51 exact whole-output checks, but saved routing layers are flat or
slower in completed gate/up wall time. This was an inference about coalescing
from LIE's own access pattern, not a claim about Halogen's undisclosed
implementation. The model trial is skipped by the bounded gate.

The [Halogen benchmark conditions](https://github.com/peonist-ai/halogen-flash-server#measured)
identify its measured rows as the older w4b checkpoint: the 0.14.1 prefill
rows used two runs, and the serial decode rows came from 0.2.0. They also
name ROCm, power, IOMMU and arena differences; absolute rates cannot serve as
LIE controls. Halogen reports a 13–16% prefill effect from disabling IOMMU on
its machine, but that is a host-specific A/B observation, not a LIE kernel
gain. This audit authorizes no host tuning, GPU run or altered benchmark input.

The public 0.16.4 changelog changes server streaming only; 0.16.3 reports a
slight multi-stream decode improvement, with no new matched serial C1 rate.
Neither changes the current C1 or cold-prefill priority ranking. The numerical
engine source remains unpublished in this repository; these are algorithm
leads to test in LIE, not code to import.

## Smaller private expert tile, tested and rejected

Halogen's 0.14.1 note gives an algorithm-family lead, not a kernel to port.
The failed 256-token LIE tile spent 242 VGPR and 42,112 bytes of LDS. A private
160-token IQ2 gate/up body now compiles locally at 173 VGPR and 29,824 bytes
of LDS, versus 150 VGPR and 25,728 bytes for the retained 128-token body;
neither body spills private scratch. All 164 retained device bodies preserve
their instruction streams and resource counts. This is a static resource
screen, not runtime occupancy or a speedup. The 256-token failure still warns
that larger tiles can lose despite greater encoded-weight reuse.

The C17 map selects only experts whose padded rows can be covered by 160-row
tiles with at least 64 padded rows in the final tile. All other experts keep the
retained 128/64-row map. The saved 48-layer original 2K routing contains
3,512 private 160-row descriptors; these select 508,126 of 983,040 *real*
routed rows (51.69%) across 991 expert/layer pairs. An independent coverage
audit verifies every padded 16-row unit exactly once for all 48 layers and 18
edge shapes; its failed-capacity paths leave outputs unchanged.

The `.157` component window then completed under the original five leases.
It produced 15 exact route maps, 51 guarded byte-exact whole-output replays
over three rotating synthetic weight sets, and 84 interleaved timing records.
All HIP event durations were invalid zero, so the figures below use five
completed host-wall samples per arm after two warmups. Both arms use the same
2048-token shape and routing.

| Gate/up routing | Retained 128/64 median µs | Private 160 median µs | Candidate time change |
| --- | ---: | ---: | ---: |
| Saved layer 0 | 5215.455 | 5205.038 | −0.200% |
| Saved layer 3 | 4155.780 | 4194.422 | +0.930% |
| Saved layer 22 | 5478.589 | 5542.897 | +1.174% |

Two of three saved-routing layers regress, and the third difference is small.
This fails the component gate. Production dispatch remains on 128/64; no
original-weight model or long-context request was rerun, and no PP/TG gain is
claimed. The release receipt at 2026-10-07 08:36:43 UTC has SHA-256
`b937ad6c4238092a63f534db9851349b6e713b71f716f3d4466ddeb55eb0a7d6`:
empty KFD, five original leases free, seven model stat identities unchanged,
and no remote cleanup. The terminal receipt stored process/group counts rather
than their full lists; an append-only handover receipt at08:44:58UTC restores
the verified 1,952 identities and1,558 groups, SHA256
`66e35d380df5dfbfdb01d9fabf722505ddf1ecb4f7c2f9cb71725be27cb0e38b`.
The original receipt is preserved; the handover is the latest registry release.
[Complete component samples](../config/q2-iq2-token160-component-results.json),
[handover summary](../config/q2-iq2-token160-handover-summary.json),
[map audit](../config/q2-iq2-token160-map-audit.json),
[static resources](../config/q2-iq2-token160-probe-static.json) and
[private patch](../experiments/q2-iq2-token160-probe.patch) preserve the result.
The original 128K prefill and C1 decode goals remain unmet. Given these
negative larger-tile results, another token-width change needs a stronger
mechanism than encoded-weight reuse alone.
