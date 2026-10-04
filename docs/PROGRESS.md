<!-- SPDX-License-Identifier: MIT -->
# Progress — Q2 compatibility workstream

## Routing measured; empty epilogue work identified — 2026-10-04

The full canonical profile completes with 1385 Forward spans, 7248 routing
observations and all 20 Q2 histories exact against the unchanged ordered
control. The accepted large calls use 128-row gate/up tiles in 42–46 of 48 layers.
Their paired epilogues visit 48.612–50.855% wholly empty 16-row fragments, although
the matrix loop already skips the corresponding WMMA work. A hypothetical
mixed 128/64 map reduces reservation 26.766–29.441% and tile count 1.417–4.383%;
these are geometry counts, with extra launch cost still unmeasured.

The isolated epilogue guard retains live arithmetic and barriers. Device
assembly keeps VGPR/LDS unchanged and scratch zero, with 23/51 additional static
instructions at 64/128. Actual canonical count vectors are saved for its next
component comparison; no runtime wiring, GPU qualification or speedup is claimed.
The activation staging loop also writes zeros for wholly unused fragments on
every K stage; that distinct opportunity is recorded without combining patches.
See [routing evidence](Q2-ROUTE-PROFILE.md) and
[prepared candidate](Q2-IQ2-LIVE-EPILOGUE.md).

Host 20/20 Debug and ASan/UBSan pass. All 11 commands exit zero and 37 artifacts
verify. Fresh release at 04:21:50.647379 UTC confirms 15 processes/11 groups
retired, KFD empty, four original leases free and five model stats unchanged.
Main/remote receipts and registry record release; core has requested the next
window. Q2 has no job, waiter or restart. Full canonical PP/TG parity remains open.

## Canonical routing diagnostic prepared — 2026-10-04

The next profile retains ordered IQ2 decode and the original PLE reader. It
records the already downloaded per-expert counts, actual tile choices and
complete Forward frontiers without changing device code. A distinct build and
client identity prevents instrumented rates from entering headline comparisons.
The analyzer checks selector geometry, count conservation, layer completeness,
request attribution and all 20 histories against the unchanged ordered control.
Nine Python sources parse, the logger fixture passes strict C++ syntax, and
all 1021 provider files match the new manifest; 1019 parent files are unchanged.
The 20-test Debug/ASan cohort and model profile still require fresh `.157`
admission. [Scope and accounting limits](Q2-ROUTE-PROFILE.md).

## PLE comparison complete; no stable added gain — 2026-10-04

All four canonical 0–128K curves complete with unchanged source/harness and
all 20 Q2 histories exact. The repeated unchanged control recovers much of the
initial prefill deficit, preventing attribution of the first-control increase
to PLE. Against the repeated control, candidate PP varies from −28.348% to
+23.850%; at 128K the difference is +0.161%. Decode is nearly unchanged except
the 4K observation. PLE is not promoted. Full [tables, graph and 32-row CSV](Q2-PLE-CANONICAL.md)
retain every value, including UD's low 32K/128K decode observations. Candidate
PP remains below UD at all eight depths; full parity is still unmet.

Host checks pass 21/21 Debug and 21/21 ASan/UBSan; all 26 commands exit zero and
127 artifacts verify. At 03:51:19.663070 UTC, fresh closure confirms 39 owned
identities and 26 groups retired, empty KFD, four original leases unchanged/free
and five model stat identities unchanged. Remote/main receipts and registry
record release. Outgoing message transport fails; persistent handover receipts
remain available. No Q2 workload, waiter or restart remains.

## PLE candidate curve complete; order control running — 2026-10-04

The PLE-plus-ordered candidate completes all eight depths at 03:32:03 UTC,
with five zero command exits and 30 hash-verified artifacts. All 20 complete
request/output/count histories match the first ordered-Q2 control. Candidate
PP/TG are 1122.526/26.633 token/s at depth 0 and 1156.229/25.654 at 128K.
The 4K prefill point is 958.657, while 8K is 1312.087; every observation is
retained in the [arm validation](../config/q2-ple-curve-candidate-r1-validation.json).
These are candidate rates, not an attributable improvement or a parity verdict.

The first control was slower at every PP point, but earlier unchanged controls
also recovered as the campaign progressed. The mandatory unchanged ordered-Q2
repeat is now running under the same admitted window. Its result and the fresh
UD arm remain outstanding before deciding whether PLE improves the full curve.
No source, harness, model file, global cache or hardware policy is changed
between these arms.

## First PLE-campaign control complete — 2026-10-04

The first ordered-Q2 control completes all eight canonical depths at 03:22:34 UTC,
with five command exits zero and 30 hash-verified artifacts. Its 20 complete
request/output/count histories exactly reproduce the prior ordered provider.
At depth 0 PP/TG are 852.935/26.114 token/s; at 128K they are 1104.323/25.252.
The complete [arm validation](../config/q2-ple-curve-control-r1-validation.json)
retains all intermediate points, physical counts and durations. A 16K decode
outlier 22.948 remains recorded. These are control observations, not PLE gains.

The PLE candidate starts next with the same host-qualified harness. At 03:26:12,
runner 3383689/start 164962420 is verified live during its full source build.
No result or parity verdict is available for the candidate yet. The unchanged
post-candidate control and fresh UD arm remain required within the admitted
window; no interleaving or release has occurred.

## PLE canonical comparison admitted — 2026-10-04

The new provider combines the host-qualified cache-first reader with measured
ordered IQ2 decode; exactly one file differs from that control. The slower WMMA
candidate is absent. A distinct mode/build/HTTP identity prevents mixing this
experiment with unchanged controls or diagnostic instrumentation. The bounded
four-arm plan retains ordered Q2 before and after the candidate, plus pristine
UD, across the complete canonical 0–128K PP/TG grid. The analyzer requires the
order control and verifies complete histories, source/harness identities, counts
and timings. Plot and CSV support retain all four series.

Ten Python sources parse, the local HIP/C17 composition configures with the
expected build ID, and the full dry build graph succeeds without model execution.
The retained four-arm IQ2 report reanalyzes to identical JSON. Fresh admission at
03:11:36.046620 UTC finds the preceding Q2 release still latest in the registry,
all 15 processes and 12 groups retired, empty KFD and four original leases free.
The new host cohort passes 21/21 Debug and 21/21 ASan/UBSan; all six commands
exit zero and seven artifacts verify. The first ordered-Q2 control is building
on `.157`: fresh observation03:14:36 verifies runner3379757/start164901713 live.
Q2 retains this bounded window through verified closure; no performance claim
is added.

## PLE mechanism reproduced; WMMA candidate slower — 2026-10-04

After verified core/Point handover and fresh admission, the `.157` host cohort
passes 21/21 Debug and 21/21 ASan/UBSan. The paired PLE control rereads 120–128
initially resident rows in the private collision fixtures; the candidate rereads
none, with identical oracle values and unchanged cache capacity. This confirms
the mechanism, not model performance. See [host results](Q2-PLE-CACHE-FIRST.md).

Both WMMA component arms pass all 20 independent numerical checks and every one
of 22 full-output pairs is exact. However, complete-cycle median time increases
2.486% at 2040/512 experts and 2.577% at 2048/128 experts. The additional sign
arithmetic is not advanced to a canonical model run. No new full-model rate or
PP improvement is claimed; the previously measured ordered decode gain remains.
The [completed audit](Q2-DEEPSEEK-AUDIT.md#completed-wmma-component-comparison--2026-10-04)
preserves the negative result and corrects the earlier generic-MMQ inference.

All 12 commands exit zero and 59 artifacts verify. Fresh window release at
02:58:06.736101 UTC verifies 15 processes and 12 groups retired, empty KFD and
four original leases unchanged/free. Remote/main receipts and registry record
closure; no Q2 workload, waiter or restart remains. The next candidate requiring
canonical measurement is PLE cache-first, composed with the retained ordered
decode provider. Full Q2/UD PP/TG parity remains unmet.

## Preserve WMMA performance evidence on numerical failure — 2026-10-04

The prepared WMMA fixture now preserves every finite output and continues all
timing cases after a numerical-tolerance failure, while retaining exit1 and the
unchanged independent limits. Runtime/guard faults still stop immediately.
The analyzer requires a complete20-case verdict matching actual errors and
command exit, and keeps numerical qualification separate from exact replay and
cycle speed. Model-curve analysis still rejects every failed command.
Strict fixture syntax and formatting pass; the retained full four-arm canonical
report reanalyzes to exactly the same JSON after the integrity-helper refactor.
New runtime guards remain pending in the21-test Debug/ASan cohort on `.157`.

Core admits `gpu-sampled-core-r1` at02:21:54 UTC. A fresh02:31:22 observation
verifies controller3359322/start164616187 alive and its seventh arm
`unfiltered-0-on` running under supervisor3361058. Q2 neither stages nor runs
inside the window. This is a verified live controller wait, not inferred activity
from a reservation. The goal remains complete canonical PP/TG parity.

## Active IQ2 WMMA sign-load experiment prepared — 2026-10-04

Source inspection distinguishes the generic MMQ IQ2 tile loader from the selected
Q2 prefill WMMA path. The latter still loads `ksigns64` inside its fused gate/up
kernel. A new candidate replaces those sign lookups with exact integer expansion,
starting from ordered IQ2 decode so its measured gain remains in the parent.
Only `kernels.hip.cpp` differs; both complete 1020-file inventories verify.
At tile64/tile128 device assembly removes eight loads, adds51/60 static
instructions and retains102/148 VGPR with zero scratch. This is a measured
compiler property, not a GPU or model-rate improvement.

The component path now stages fixed sources, builds the direct production kernel
target and retains twenty independent oracle reports plus22 complete output
buffers across existing operators and two full-size cycles. The analyzer checks
the paired source/harness/operands and rejects incomplete timing or output data.
Both device compilations, corrected strict fixture syntax, CMake configure,
five-command dry build graph and five Python AST checks pass locally. Initial
syntax/format failures remain retained; the final source shares exactly the
parent's five untouched formatter failures. Runtime remains pending on `.157`.
See [audit and bounded plan](Q2-DEEPSEEK-AUDIT.md#follow-up-in-the-active-prefill-wmma-loader--2026-10-04).

Core now acknowledges the existing01:33:37 Q2 release and will freshly admit its
18-arm sampled window. Q2 performs no remote staging or execution and will not
interleave that window. The ready/handover receipts persist despite failed
outgoing MCP transport. Whole-curve PP/TG parity and independent model numerical
acceptance remain open; neither source preparation establishes a new model rate.

## Paired PLE host path wired — 2026-10-04

The isolated `ple-cache-first-cpu` mode now stages the full unchanged canonical
parent alongside the candidate, verifying both 1020-file inventories. It runs
the original host suite plus separate control/candidate fixtures, 21 CTest cases
per Debug/ASan configuration, retaining their read counters in verbose logs.
The fixture assigns different data to colliding row identities; the previous
low-bit-only pattern could miss a wrong-key cache answer. Report checks reject
incomplete pairs, false exactness and inconsistent read accounting. Two strict
C++ syntax checks and five Python AST checks pass locally; runtime is pending.
The earlier unapplied wiring recipe and its evidence remain historical records.

Read-only observation at 01:54:45 UTC finds the IQ2 release still latest in the
shared registry and KFD empty. Core has the ceded next window; this observation
is neither a Q2 admission nor a verified wait on a live process. No new staging,
remote test, model access, reservation or restart occurs. Outgoing thread MCP
transport fails; the main ready receipt records the prepared host cohort.
Whole-curve Q2/UD parity and independent model numerical acceptance remain open.

## Canonical IQ2 campaign complete and released — 2026-10-04

All four 0–128K curves validate, with both Q2 complete-history comparisons exact
for 20 requests each. Ordered IQ2 decode is **4.055–5.526% above UD** in all eight
cells and **4.446–5.188% above the unchanged post-candidate Q2 control**. The
initial apparent 67.746% depth-zero PP increase is reproduced by unchanged Q2
and is not credited to the patch. Candidate PP remains **7.348–9.299% below UD
at0–16K**. At32K–128K it exceeds this UD observation, but prior UD observations
were faster: long-context PP parity remains unproven. The goal is not achieved.

The [full report](Q2-IQ2-CANONICAL.md), four-series PNG/SVG and complete 32-row
CSV preserve every rate, physical count, duration and cache timing. Analysis
exits zero and CSV counts/timers agree with verified raw artifacts. Source
audit confirms packed sign arithmetic in the generic IQ2 MMQ tile loader.
The subsequent active-path audit corrects the inference that this covers Qwen
prefill: its dedicated WMMA loader still reads the sign table and is now the
subject of a separate experiment.

At 01:33:37.055967 UTC the window releases after all 26 command exits zero,
127 artifacts verified, 39 owned identities and 26 groups retired, empty KFD,
four unchanged original leases free and five model stat identities unchanged.
Remote/main receipts and the shared registry record closure. Outgoing MCP fails;
no delivery, reservation, waiter or restart is claimed. PLE cache-first remains
prepared with runtime validation pending in a separately admitted window.

## Canonical IQ2: decode gain survives unchanged order control — 2026-10-04

Ordered IQ2 completes the full 0–128K curve, all five commands exit zero and
30 artifacts verify. Its 20 full request/output histories match baseline.
The apparent depth-zero PP jump from 833.320 to 1397.861 token/s prompts an
unchanged Q2 repeat before UD. That control reaches 1398.334 PP, retaining the
same 20 histories; PP improvement is therefore not attributed to the kernel.
Decode increases **4.446–5.188% at all eight depths** against that control,
median 5.143%, with no observed completion changes. The full table and evidence
are in [the canonical IQ2 report](Q2-IQ2-CANONICAL.md).

The extra single control arm has fresh admission at 01:15:08 UTC and finishes
at 01:23:20, all five commands exit zero and 30 artifacts verify. The initial
failed local admission checker is retained; no workload or foreign action
occurred before correcting its ownership set. UD is now running. The analyzer
and plotter retain both baselines, the candidate and UD without replacing
slower observations. Goal parity and independent numerical qualification are open.

## IQ2 model campaign admitted; separate PLE candidate — 2026-10-04

Core releases its integrated window at 00:47:22 UTC with all 28 identities and
13 child groups retired. Fresh Q2 admission at 00:51:48 rechecks those processes,
empty KFD, the unchanged four original lease inodes and CPU 38.75 C. Host guards
pass 19/19 Debug and 19/19 ASan/UBSan; six command exits are zero and seven
artifacts are collected and verified. The canonical Q2 baseline completes at
01:02:10 UTC with all five command exits zero, all eight accepted depths and
30 artifacts collected/verified. Its 20 request histories, outputs and physical
counts replay exactly against the previous Q2 sweep. Rates still vary: depth0
is 833.320 PP / 24.885 TG, and 128K is 1112.411 PP / 24.394 TG, while 4K TG
falls to 20.617. These are baseline observations, not candidate gains. The
ordered IQ2 candidate is running next; pristine UD remains pending. No model
gain is claimed before their complete histories and curves validate.

In parallel source work, the [PLE cache-first candidate](Q2-PLE-CACHE-FIRST.md)
checks all resident rows before publishing misses and removes the redundant
worker lookup. It changes one source file, retaining 1019 others, row bytes
and capacity. An independent BF16/IQ4 fixture counts rereads during colliding
gathers. Local syntax checks pass, while runtime checks remain pending.
Its opt-in host integration is an unapplied patch so the live IQ2 campaign's
qualified harness stays exact. No PLE model arm is admitted.

## Ordered IQ2: canonical model path prepared — 2026-10-04

The measured component candidate now has an isolated full-model HTTP mode,
with its own build identity and explicit source inventory. Q2 baseline,
ordered IQ2 Q2 and pristine UD retain the same frozen C17 core, canonical
prose recipe, all eight context depths, C1 sampling and timing boundaries.
The analyzer compares complete baseline/candidate request histories in
addition to PP/TG and actual physical counts; the plotter supports all three
series and exports complete durations/counts. No new model rate is claimed.

All 333 core and 1020 candidate source files verify. Nine Python AST checks
pass, and the retained second Q2/UD sweep reanalyzes to exactly the same JSON
and CSV. The retained Q2 r1/r2 histories contain 20 requests per model sweep
and replay exactly. The new runtime tests remain pending on `.157`: core owns
its integrated qualification window, and Q2 will not enter gaps between arms.
[Prepared path, evidence and remaining checks](Q2-IQ2-SIGNS.md).

## IQ2 packed signs: exact component gain measured — 2026-10-04

The isolated runner now builds reference/candidate MMQ from their complete
inventories and runs the existing independent GPU operators followed by an
exhaustive codebook/sign fixture and a 512-expert rotating gate/up cycle.
The fixture retains full outputs, independent FP64 samples, guards and all
warmup/measured intervals. The initial candidate saves 41.495% component time
but fails byte-exact replay because fast-math reassociates the scale product.
That analyzer exit 1 remains retained. An explicit gfx1151 scale multiply
restores exact replay for all 110 buffers while retaining **41.364% less
complete-cycle time: 85.352 to 50.047 µs**. Both providers pass the independent
checks; reference r1/r2 outputs also match exactly. These are component
microseconds, not model token/s. [Full evidence and limits](Q2-IQ2-SIGNS.md).

Fresh admission at 2026-10-03T23:46:15.006257+00:00 follows core's released
clocked window and the explicitly scheduled Point copy's VERIFIED completion.
All 30 previous process identities are absent, KFD is empty and the original
four leases are unchanged/free. The bounded window covers host Debug/ASan
and two component arms only. No original model access or hardware changes
are involved. Direct outgoing MCP transport remains unavailable; persistent
main/remote receipts and the shared registry record admission.

Both host cohorts pass 19/19 Debug and 19/19 ASan/UBSan. All six cohorts finish
with 28 command exits zero and 474 artifacts verified. Fresh closure at
2026-10-04T00:07:51.297211+00:00 verifies 34 own processes/groups absent,
empty KFD and all four unchanged original lease identities free. The release
is recorded remotely, in the main worktree and in the registry. No Q2 job,
waiter or restart remains. The ordered candidate is ready for the canonical
whole-model comparison; PP/TG parity and earlier model-quality gates remain open.

## Repeated canonical curve, PLE attribution and DeepSeek audit — 2026-10-04

The second uninstrumented UD→Q2 sweep retains the whole 0–128K workload.
Q2 remains below UD in both metrics at all eight points on the two-sample
means. In the second pair, depth-zero PP is 787.469/1568.491 token/s and
128K PP is 1092.674/1220.249: the first pair's near-parity at 128K does not
repeat. All 40 same-model request payloads and completion hashes replay.
[Both pairs, durations and figures](Q2-CANONICAL-REPEATS.md) remain separate.

The diagnostic pair records 1385 valid Forward intervals per model. Its
40 request/output histories also match the uninstrumented pair exactly.
At depth zero Q2/UD host PLE wait is 1180.492/113.939 ms and process storage
reads are 2046.773/98.359 MiB. At 128K the wait is 138.881/112.701 ms. Q2's
small row-cache hit rate stays near 3%; lower-level storage warming is a
supported hypothesis for the falling read cost. Host waits overlap queued GPU
work and are not a direct critical-path or recoverable-time measurement.
[Complete PP/TG counters, units and figures](Q2-CURVE-PROFILE.md) are retained.
The roughly 2600 prefill figure is milliseconds, not token/s.

The owner's suggestion prompted an audit of official pinned Gufo DeepSeek,
using no sibling DS4 source. The same IQ2/Q2 formats expose two concrete
unmeasured mechanisms: mixed full/tail expert maps and packed integer IQ2
sign decoding. A one-function sign candidate is prepared with 1019 other
provider files exact; device-only syntax passes. No GPU run or performance
gain is claimed. Device assembly reduces the fused vector body from 1036 to
384 static instructions but increases VGPRs from 31 to 68, without private
scratch; runtime must decide that tradeoff. The audit also rejects false leads: histogram MMQ selection
already exists, and HIP D2R and producer-Q8 reuse are stubs. The canonical
PLE cost remains a separate priority. [Audit and provenance](Q2-DEEPSEEK-AUDIT.md).

All five current-window cohorts finish: 19/19 Debug and sanitizer checks,
26 command exits zero, 127 artifacts verified. Fresh closure at
2026-10-03T23:03:30.243030+00:00 verifies 39 process/group identities absent,
KFD empty and all four original leases free. Core explicitly acknowledges
the receipt and takes its follow-up window. No Q2 GPU job, waiter, reservation
or restart remains. Numerical qualification and full-curve parity stay open.

## Canonical PLE attribution prepared; reversed pair running — 2026-10-04

The first whole curve is retained in checkpoint97f4281. Its 1.136713-second
short-context prefill gap now drives attribution on the same HTTP workload.
The diagnostic source adds host Forward intervals and PLE counters only;
all 134 Q2 / 133 UD other kernel-path files remain exact. Every observation
must match its request's monotonic interval, cached frontier and completed
prefill/decode counts. Summed worker times are not GPU wall time and host
waiting is not automatically recoverable GPU idle time.

Five syntax checks pass. The earlier curve reanalyzes to identical JSON data.
The new host cohort passes19/19 Debug and19/19 ASan/UBSan on `.157`, including
parallel counter observation, failed Forward rejection and request-frontier
checks. The profile has a distinct server identity and is rejected by the
ordinary performance analyzer. No numerical kernel improvement is claimed.

Fresh admission at22:26:44 UTC follows two read-only observations without an
intervening core admission, then original four-lease and retired-process
checks. The admitted sequence is uninstrumented UD→Q2 over the complete grid,
then separate Q2/UD profiles. The first UD arm is running at this checkpoint;
the GPU window remains active. [Method and limits](Q2-CURVE-PROFILE.md).

## Full Gufo workload pair measured over C17 HTTP — 2026-10-04

The first corrected campaign measures both original models at all eight
cached-prefix depths 0–128K on `.157`. The client imports the pinned Gufo prose
generator, calibration and ordered depth recipe unchanged; an independent
analyzer reconstructs every accepted request. All 16 continuations have 128
outputs and 128 completed AR calls. Both models share a frozen C17 HTTP core
and completed-executor timer; this is workload equivalence, not a claim that
the published Gufo scheduler timer is identical.

Q2/UD PP is 829.074/1540.945 at depth 0 (-46.197%) and 1107.664/1114.494
at 128K (-0.613%). TG is 25.033/25.737 at depth 0 and 24.406/24.071 at 128K.
Q2 still misses PP parity at every point and TG parity at the first seven.
The [report](Q2-CANONICAL-HTTP.md) includes all rates, physical counts,
durations, cache costs, HTTP wall time, CSV and standalone figures. These are
one warmed observation per point; reversing model order and repeating the
same curve is the next check for cache/order sensitivity. PLE gathering is
a concrete profiling hypothesis, not an established cause from these timings.
The older 1411–1439 counting rates remain outside the curve.

Both host cohorts pass 18/18 Debug and 18/18 ASan/UBSan. All 22 command exits
are0;74 artifacts and4745 source-file instances verify. Initial static exit 1
for omitted feature macros is preserved, followed by successful strict Q2/UD
syntax checks. The HTTP composition introduces no new numerical kernel change;
the Q2 candidate's existing operator/position/KL rejection remains.

Fresh release at 2026-10-03T22:06:58.501157+00:00 verifies 30 recorded processes
and owned groups absent, empty KFD and all four original lease inodes free.
Persistent remote/main receipts and the registry record closure. Direct
outgoing MCP transport failed; delivery is not claimed. No Q2 GPU job, waiter
or restart remains; further remote work requires fresh coordination.

## Canonical whole-curve target restored; ragged diagnostic closed — 2026-10-03

The owner requires parity at every short and long point, in both PP and TG.
The investigation had instead followed the historical C17 decode control
into a ragged HC prefill optimization. That was a priority error: both the
exact-2048 counting fixture and historical 2042-token fixture differ from
Gufo's HTTP prose/cached-prefix sweep. Exact token length alone does not make
a benchmark canonical. [The corrected contract](Q2-CURVE-PARITY.md) pins the
workload, ordered 0–128K depth grid, calibration, HTTP scope and evidence gates.
The canonical Q2/UD curve remains unmeasured; no new run is scheduled.

The completed original-C17 diagnostic gives Q2 control/candidate/UD at physical
2042: **1359.654 / 1386.506 / 1661.359 PP** and **25.527 / 25.513 / 26.036 TG**
token/s. The candidate gains 1.975% PP over its control, with no decode gain;
it still trails UD by 16.544% PP and 2.010% TG. All three prompt sizes,
samples, durations and graphs are in the [full-model report](Q2-HC-LIBRARY-RAGGED-MODEL.md).
Twelve candidate/control output sequences match but 24 logit hashes differ.
All 36 historical UD witnesses replay; arithmetic/quality rejection remains.

The six-cohort campaign retains the actual component exit1 and all model
command exits0. Release at 21:11:50.582832 UTC verifies all 36 recorded process
identities/groups retired, KFD empty and the four original leases free.
Q2 holds no GPU reservation, waiter or restart. Header/source inspection finds
the same nominal 262144 capacity; that is not measured long-context parity.

## Ragged HC component measurement and model admission — 2026-10-03

Core's 20:44:19 UTC release is rechecked under the original four leases at
20:46:48 UTC. The host cohort passes 17/17 Debug and 17/17 ASan/UBSan on `.157`.
All seven ragged library geometries are supported. At n2042, complete-cycle
time falls 47.812% ordinary and 41.147% MoE; n2047 saves 47.267% and 41.026%.
All twenty pairs favor the library. n502 has no useful gain; n2048 is an
existing library control, not a new model gain.

The component's actual exit1 is numerical: all 32 norm checks pass and
all sixteen native down cases pass, while all sixteen library down cases
fail their unchanged FP64 limits. Four library repeated-row probes drift;
all native probes are exact. Full arrays, hashes and all eighty timings are
retained. [Results and graphs](Q2-HC-LIBRARY-RAGGED.md) distinguish arithmetic
rejection from speed. Forty-four component artifacts verify.

The recorded 20:53:05 UTC decision admits only a fresh original-C17 model
comparison with full MMQ builds. Updated launcher guards pass another 17/17
Debug and 17/17 ASan/UBSan. The control completes and verifies at 20:59:15 UTC:
Q2 at 2042 is 1359.654 PP and 25.527 TG token/s. Candidate and pristine UD
subsequently complete; final results and verified release are recorded above.
No .155 work or policy/model/service changes occur in this campaign.

## Scalar decode HC attribution recovered — 2026-10-03

The preceding turn prepared the ragged prefill experiment in `c40f80f`.
Fresh observation at 20:37:19 UTC verifies core PID 3230896/start ticks
162518815 live in `gpu-vision-bec-r3/combined-ssd-write`; Q2 does not enter
that active window. The later SSD and reactive arms become terminal, but no
enclosing release is recorded at 20:43:21 UTC. No Q2 remote work starts.

While awaiting handover, the existing decode traces are reattributed using
the frozen HC launch sequence. All 1455 Q2 and 1455 UD HC-up calls are
identified between SiLU and mix, including UD's preceding quantization.
Q2 costs 2.915551 ms/token versus UD 1.912672 including preparation, a
1.002879 ms difference. HC down adds another 1.296157 ms/token; routed experts
are already faster. The prior symbol-only groups hid HC up in Q2 `other` and
UD generic Q8. Every dispatch and total is preserved, including the unchanged
8.411433 ms net phase difference. This changes optimization priorities rather
than throughput. [Full attribution and limits](Q2-HC-DECODE-ATTRIBUTION.md)
retain database/capsule hashes and every HC dispatch identity.

## Ragged HC library dispatch prepared — 2026-10-03

The previous goal turn completed the original-C17 baseline and scalar-HC
campaign, checkpointed through `0aa6f2a`. That is measured progress, with parity
still unmet. The next experiment targets the larger prefill deficit: the faster
HC library consumer applies only at exactly 2048 rows, while the historical
2042-token request and incomplete chunks fall back to the native consumer.

Only two predicates in `blaslt.cpp` now extend the experimental library choice
to 96–2048 rows. Algorithm 7526 must remain supported with zero workspace.
All 1019 other provider files are byte-identical, including producers and scalar
decode. The new same-process fixture compares original norm/narrowing plus
native/library consumers, with ordinary/MoE cases, tiny inputs, full output
checks, independent FP64 formulas and repeated-row position checks. Five
alternating pairs at four batch sizes rotate 100 MiB of weights.

Changed formatting, strict host syntax, CMake configuration, build-graph dry
run and exact patch reconstruction pass. The initial unused-helper warning
and the same five inherited upstream formatting failures remain recorded.
The launcher and analyzer are prepared, with host CTest/ASan and GPU execution
pending on `.157`. Core's latest arm is terminal but the enclosing campaign
has not handed over; no Q2 remote build/test, waiter or restart is scheduled.
[Source, protocol and limits](Q2-HC-LIBRARY-RAGGED.md) preserve the original
numerical thresholds and separate n2048 control timings from new ragged gains.

## Original UD rate reproduced; scalar HC saving marginal — 2026-10-03

Fresh original C17 timing confirms the historical UD reference. At 2042
physical tokens, UD reaches 26.061 decode token/s versus Q2 25.514;
the historical UD value is 26.049. Q2 remains 2.099% slower in decode and
18.079% slower in prefill (1362.819 versus 1663.579 token/s). At 502/8191,
Q2 decode is 26.184/25.483 and UD 26.865/25.970. All three prompt sizes
use 128 completed steps, one warmup and three retained measured samples.

The byte-frozen historical benchmark/ABI/adapter and both full provider builds
run on `.157`. UD reproduces all 36 historical output/frontier witnesses;
Q2's twelve 2042-token witnesses match the preceding strict diagnostic.
Different host sampling cost explains why these benchmark rates must not be
presented as a new GPU improvement. Exact replay does not clear the existing
operator/KL rejection. [Full results, durations and graphs](Q2-DECODE-BASELINE.md)
keep the strict diagnostic comparison separately scoped.

The scalar HC DPP component passes all eleven independent FP64 cases and
27 complete byte-exact pairs. Despite 123 to 91 static instructions, median
time changes only 30.272281 to 30.171031 microseconds (-0.3345%). All five
alternating pairs favor the candidate, but the projected 0.00982 ms/token
saving is small beside the original-C17 gap of 0.82264 ms/token. The candidate
is not promoted or admitted to a full-model run. [Component evidence](Q2-HC-DECODE-REDUCTION.md)
preserves the samples and limits.

Host Debug and ASan/UBSan each pass 17/17. The campaign verifies 90 unique
artifacts and 4079 source-file instances; all 19 remote commands exit zero.
Final release at 20:00:42.449978 UTC verifies all 23 recorded processes/groups
retired, KFD empty and the original four leases free. Persistent release
receipts record no Q2 workload, waiter or restart. Q2/UD parity remains unmet.

## Original C17 baseline composition prepared — 2026-10-03

The previous goal turn saved the scalar HC experiment in `973b391`. Core's
`gpu-perf-b72-r1` still owns `.157`, so this increment prepares the exact
production timing comparison locally. It does not claim a new throughput gain.

Six first-party files are frozen byte-for-byte from historical clean commit
`7f85ef8090506c32998780a8249aa0e10cd9e091`: the original C17 benchmark, ABI header,
adapter/binding/failure drain and MIT license. A private CMake composition links
them to freshly built pinned Gufo providers. It does not replace the current
server ABI or import a numerical archive. The launcher permits only measured
`library-norm-bound` Q2 and pristine UD, with full MMQ rebuilds. The new HC
reduction remains component-only and requires its separate measured gate.

Strict C/C++ host syntax, CMake configuration and a 46-command build-graph dry
run pass. All six historical files match their Git blobs. Report parsing of the
original twelve samples reproduces UD TG26.851/26.049/25.965 and
PP988.678/1642.652/1607.132 at physical502/2042/8191. These are historical values,
not new measurements. Host CTest/ASan, full linking and GPU runs remain pending.

The original production sampler's treatment of isolated nonfinite logits and
the original full-frontier endpoint checks are explicitly recorded. The strict
diagnostic Argmax and existing operator/KL rejection remain unchanged. Source,
actual command exits and the runtime plan are linked in
[the baseline report](Q2-DECODE-BASELINE.md). The HC-specific target is also
excluded from unrelated default builds because its preserved-control symbol
exists only in that isolated source. No Q2 remote job or restart is scheduled.

## Scalar HC down reduction prepared; runtime pending — 2026-10-03

The previous goal turn made verified progress in e6f425e by correcting benchmark
cost and reproducing the original UD output/frontier hashes. This turn targets
engine decode itself: the historical-prompt deficit is about 0.60 ms/token.

The current HC down load loop already uses vector loads. The candidate instead
replaces two five-stage dynamic wave reductions with immediate XOR16 and row-DPP
XOR8/4/2/1. Explicit RN additions preserve the descending sum tree; original
weights, FMA loop, 16-wave geometry, barrier and cache invalidation remain.
Generated assembly is 123 versus 91 static instructions, with 13 VGPR, 12 SGPR,
64-byte LDS and no private scratch in both. The control assembly and complete
multiply/load loop are exact. Static counts establish no runtime gain.

A component fixture preserves the original GPU control in the same binary,
keeps eleven independent FP64 cases and adds six special-value full-buffer
pairs. Sixteen rotating matrices use 100 MiB; five 128-launch pairs alternate
order. Every matrix and timing endpoint is saved, for 27 complete pairs and
65 data files. Numerical failures remain exit 1 while performance is retained.
The launcher is restricted to this component; no model promotion is admitted.

All 1020 files reconstruct exactly through the patch; two files change and
1018 are unchanged. Device-only compilation, strict host-only fixture syntax,
changed-file formatting and Python syntax pass. Shared formatting retains the
parent's five existing upstream-test violations. The initial reused-main return
warning is preserved and corrected with an explicit successful return.
Runtime CTest/ASan, GPU exactness/oracles and performance are pending on `.157`.

Core explicitly retains the `.157` window for its MTP/cache correction after
its sampler tests. A read-only observation confirms an active core process/KFD
client; the later core message reports its servers retired but explicitly keeps
ownership. Q2 performs local preparation only; no remote job, waiter or restart
is scheduled. The persistent ready file is the coordination fallback while
outgoing thread transport fails. [Source, static evidence and qualification
plan](Q2-HC-DECODE-REDUCTION.md) are recorded. The full goal remains active.

## Corrected decode harness and historical baseline replay — 2026-10-03

The obsolete per-logit string construction is removed with all finite checks,
tie behavior and exception text preserved. Fresh Q2 current2K decode is
25.089 calls/s (+4.120%); UD is 25.475 (+4.757%). This is benchmark overhead
removed, not an inference-kernel improvement. All 21 old saved files match for
each model. Two scopes per model pass 36/36 internal replay checks in total.

The added immutable historical2042 prompt completes 128 forwards per 128 output
tokens, final position 2170. Q2 reaches 25.080 and UD 25.463 calls/s, a 1.505% deficit
or 0.60013ms/token. UD matches all 12 original token/frontier witnesses, but the
full finite scan and sampling boundary still differ from the original 26.049
baseline. That production target is not lowered. Q2 prefill at 2048 remains
1438.975 token/s; UD varies 1611.173–1672.432, so the smaller raw PP deficit is
not a Q2 optimization. Historical2042 PP is 1372.865/1662.672 Q2/UD. Numerical
rejection remains: operator failures and KL 0.002996 >0.002; no task-quality,
HTTP, concurrency or long-context promotion follows.

The paired norm source is bound to n2048 where its actual library consumer
runs; all GPU kernels and 1019 other source files remain unchanged. Each model
receives a full MMQ rebuild. Debug and ASan/UBSan both pass 17/17 tests on `.157`.
All 85 artifacts, 3059 source-file instances and 14 successful command exits
verify. The shared formatter retains exactly the parent's five untouched
upstream-test violations; changed first-party C++ files pass formatting.
Maximum model-run CPU 82.5 C/GPU 74 C. Public ABI and state formats do not change;
experimental evidence adds explicit completed_output and final_position.

[Full samples, durations, hashes, graphs and boundary analysis](Q2-DECODE-BASELINE.md)
are recorded. Closure at 17:37:05.108908 UTC verifies 17 recorded PIDs/groups
retired, KFD empty and four original leases free. Persistent remote/shared/local
release receipts provide the handover while outgoing MCP transport remains
unavailable. No job, waiter or restart remains. The goal remains open.

## Paired norm/library composition improves complete prefill — 2026-10-03

The actual library consumer retains the paired producer's saving: complete
ordinary/MoE cycles take 2.530%/6.120% less time, with 80/80 complete hash pairs
and 18 saved pairs exact. Independent down checks retain 15 failures and exit 1;
the norm checks pass. This supports the separately admitted model trial.

Fresh C1 pp2048/tg128 measures 1411.691 PP control, 1439.264 paired and 1666.902
UD token/s. The addition gains 1.9532%, saving 27.793 ms from prefill. All 21
saved model files match the fresh control, which also matches its preceding
cohort; all 27 internal model replays pass. Decode is 24.086/24.097/24.318
calls/s, an overlapping +0.0434% change for unchanged scalar kernels.
Q2 remains 13.656% below UD PP and 0.911% below decode. Qualified-reference KL
stays 0.002996 > 0.002 and earlier operator failures remain; no numerical
promotion, task-quality or broad parity is claimed. [Every sample, complete
prefill/decode durations, graphs and next decode priorities](Q2-LIBRARY-NORM.md)
are preserved. Candidate ends 16:44:22.617 UTC (18:44 Europe/Rome).

The decode priorities come from the preceding diagnostic trace: HC F16
down/up 5.895 ms per step, dense Q8 17.477 ms (46.71% of kernel time), and
5.607 ms inter-kernel gaps. Down alone adds 1.296 ms per step over UD; target
that measured difference first. HIP graphs already exist. Other gaps cannot
be equated with removable launch overhead or a reactive speedup.

Both host cohorts pass 16/16 Debug and 16/16 ASan/UBSan on .157. All 132
artifacts and 6119 source-file instances verify across six frozen runners.
27 commands finish, retaining the component's exit 1 and local preparation/
collection failures. Maximum CPU/GPU 84.5/73 C. No original weights, public
ABI, state format, service, dependency or core sampler change is introduced.
The incoming core f0f58b3 C17 sampler checkpoint stays outside this campaign.

Verified closure at 16:50:57.568 UTC finds 33 recorded PIDs/groups absent,
KFD empty and the original four leases free. Remote/shared/local receipts
mark release and the main ready record is updated. Outgoing thread delivery
still fails at MCP transport; the durable fallback records the handover.
No Q2 workload, waiter or restart remains. The performance goal remains open.

The owner correctly recalls 26 token/s: verified historical LIE UD baseline
is 26.049386 at 2042 prompt tokens, not 24.318. The current Q2 rate is 7.497%
below that historical rate; the diagnostic UD control is 6.646% below it.
The current harness constructs 248320 temporary strings per token during
finite-logit checking inside decode timing. A separate .157 host-only probe
confirms 248320 allocations versus 0 with identical finite/argmax checks,
and 2.579 to 0.777 ms median per call. Five commands exit 0; every sample and
both program variants are retained. This is benchmark overhead, not a GPU
optimization, and no old model timing is adjusted by subtraction. The prepared
harness-only patch needs fresh model qualification and historical-prompt
alignment next. The original 26-token/s target remains; then revisit HC decode.

## Composed profile changes the next optimization target — 2026-10-03

Fresh scaled-library and pristine UD pp2048/tg16 traces reproduce 28/28 saved
controls and measure 1468.039 / 1258.872 ms prefill kernel work. Extra Q2 time
is now led by activation preparation +86.151 ms and HC down +60.870 ms,
together 70.29% of the 209.167 ms net difference. Expert down is comparable,
192.213 / 194.073 ms. Inter-kernel gaps are only 5.695 / 4.423 ms; scheduling
alone cannot recover the measured kernel deficit. [Complete attribution and
graphs](Q2-SCALED-LIBRARY-PROFILE.md) retain every kernel and both phases.
These diagnostic values do not replace the 1412.563 / 1660.059 unprofiled PP
comparison or establish numerical/task-quality acceptance.

The next isolated `library-norm` source applies the previously exact paired
F32/F16 norm patch to the current scaled/library source. The new library
consumer could respond differently from the native HC kernel that erased the
producer's earlier saving. Five local static commands pass; three source files
change and 1017 stay exact. No new GPU qualification or gain is claimed. The
source is not enabled for remote launch; a complete producer/library-consumer
comparison with unchanged oracles is required before a model trial.

Both host cohorts pass 16/16 Debug and 16/16 ASan/UBSan on `.157`. A rejected
launcher invocation (exit 2, no remote start) and an early offline read (exit 1)
are preserved and corrected. Four remote runners and all 26 commands exit zero;
66 artifacts and 4079 source-file instances verify, CPU/GPU maxima 89.375/71 C.
Closure at 16:14:41.510 UTC verifies 30 recorded processes/groups absent, KFD
empty and original four leases free. Durable remote/shared/local release is
recorded; direct MCP handoff fails and the fallback is updated. No GPU job or
restart remains. The parity goal and full quality comparison remain open.

## Scaled and HC-library composition measured — 2026-10-03

The two arithmetic experiments now run together, changing only `blaslt.cpp`
in the cumulative scaled source. HC-down M320/K10240/n2048 uses the previously
measured zero-workspace library algorithm 7526; the other 1019 source files
stay exact. The additional vector-conversion/PLE paths from the preceding
screen are excluded because they showed no useful warm gain.

Fresh same-fan C1 pp2048/tg128 full-MMQ builds measure scaled Q2 1386.762,
scaled + HC library 1412.563 and pristine UD 1660.059 prefill token/s. The
composition gains 1.8605%, saving 26.974 ms of prefill, and remains 14.9089%
below UD. Decode measures 24.081 / 24.117 / 24.273 calls/s; the composition
remains 0.6421% below UD. This is a C1 2K result, not parity at other contexts,
concurrency or HTTP. See [all rates, durations, samples and graphs](Q2-SCALED-LIBRARY.md).

Component HC-down time falls 1196.711 to 988.426 us (-17.4047%). Both unchanged
22-case fixtures complete with actual exit 1 and four/five numerical failures.
Only the selected shape changes; all 22 candidate hashes match the prior library
experiment. All nine token files match the fresh scaled base, eight logit files
change, and every compared frontier has matched token history. Maximum KL
against the historical qualified Q2 reference falls 0.003771 to 0.002996 but
still exceeds 0.002. This narrow diagnostic proves no task-quality improvement;
inherited scaled operator failures remain. No source is promoted.

Host Debug/ASan each pass 16/16 on `.157`. Six capsules verify 181 artifacts,
6119 source-file instances and all frozen fixtures; models and built binaries
keep their witnesses. Observed CPU/GPU maxima are 84.625/74 C. Model candidate
finishes at 15:43:12 UTC (17:43 Europe/Rome), UD at 15:47:49 UTC.

Fresh closure at 15:54:18.022 UTC verifies 30 recorded processes/groups absent,
KFD empty and original four leases free, then records remote/shared/local
release. Direct core-thread delivery again fails at the MCP transport; the
persistent coordination fallback is updated. No Q2 job or restart is queued.
The performance objective and full quality comparison remain open.

## Cumulative optimizations measured — 2026-10-03

The owner asks to combine improvements. The previously measured scaled source
already includes the expert/HC/packed/palette work. Two isolated compositions
add exact vector narrowing and the prepared hook for C17 PLE, preserving all
146/150 existing kernel bodies and fully rebuilding MMQ on `.157`.

Five fresh C1 pp2048/tg128 arms use the same fan82 policy. Adding the new paths
changes retained PP 1344.795 to 1341.148 (-0.271%) and scaled PP 1388.492 to
1383.503 (-0.359%, overlapping ranges). All 21 files match each addition's own
base; all 45 within-arm replay checks pass. Fresh UD reaches 1659.557 PP /
24.304 decode calls/s. Combined scaled remains 16.634% below UD PP and 0.834%
below decode, with inherited numerical rejection unchanged. No new source is
selected. See [complete rates, durations, samples and graphs](Q2-COMBINED.md).

On the cumulative scaled source at 8K, C17 lookahead overlaps 170.863–178.520 ms
of preparation with preceding forward/drain callbacks. It improves 2.3225%
versus explicit prepared-serial, but only 0.1220% versus native: 1324.119 to
1325.734 PP, with overlapping ranges. All 432 frontiers and complete arrays
match; slot ordering and real cancellation/drain pass. First ordered observations
have different cache histories and do not establish a cold-access speedup.

Host Debug/ASan each pass 16/16. Each source passes 192 GPU conversion cases
and two complete consumers. All nine runners exit 0; 176 artifacts and 9181
source files verify, with CPU/GPU maxima 88.125/84 C. Public C contracts, the
original C17 flow and the serving deployment remain unchanged. These are C1
2K and synthetic-varied 8K results, not long-context or task-quality acceptance.

Fresh 15:12:14.894 UTC closure retires 45 recorded processes/groups, verifies
KFD empty and original four leases free, then records remote/shared/local
release. Direct thread messaging again fails at the MCP transport; the fallback
is updated. No Q2 workload or automatic restart remains. Full Core-19 and the
Q2/UD parity objective remain open.

## HC160 instruction reduction measured — 2026-10-03

The owner clarifies that the160-row geometry should remain under investigation
while its algorithm is simplified. Exposing dispatch-proven M320/K10240 and
hoisting invariant fetch-lane zero initialization reduces the loop's emitted
instructions136 to116 (-14.706%), without changing16WMMA operations, buffers,
640threads or either ordered K16 sum. All145 unrelated kernel bodies stay exact.
GPU timing gives no useful improvement: first1187.047 to1232.229us (+3.806%),
repeat1216.704 to1223.279us (+0.540%, overlapping ranges). All22 complete output
hashes and44 saved coordinate/value files stay exact; four inherited independent
failures remain actual exit1. No model promotion follows. See
[algorithm, every sample and graphs](Q2-HC-ROW160-INSTRUCTIONS.md).

Earlier in this window, phase compiler barriers reduce VGPR251 to155 but add
59.15% HC-down time. Free scheduling changes only-0.48%, overlapping, and the
original160x128 geometry adds0.97%. Their [full report](Q2-HC-DOWN-PHASED.md)
retains the actual failed numeric verdicts. The K32 compiler-boundary candidate
is compiled only and deferred following the owner's clarified direction.

Seven GPU arms and four host cohorts yield364 collected/hash-verified artifacts.
All updated host checks pass16/16 Debug and16/16 ASan/UBSan on `.157`.
Fresh14:17:19 UTC closure verifies56 recorded processes/groups absent, KFD empty
and all original leases free; the durable/shared/local receipts release the
window. No model/Core-19 restart is queued. The last full-model candidate gain
remains scaled-input's+3.15825% measured at09:43 UTC (11:43 Europe/Rome), still
not numerically accepted and18.102% below UD in PP. Q2/UD parity remains open.

## Conversion and scaled-tile GPU measurements — 2026-10-03

Under the owner's persistent fan82 policy, `q2-narrow-vector-r1` completes
with exits 0/0/0, all 192 conversion cases passing and both complete consumer
outputs exact. Conversion-only time falls 3.609–3.888%; complete consumer
cycles only fall 0.812–1.375%, with overlapping ranges and mixed paired signs.
No model dispatch is justified. See [every sample and graph](Q2-NARROW-VECTOR.md).

`q2-scaled-tiles-r1` completes all six paired cohorts and preserves exits 0/0/1.
Tile128 regresses 18.090–22.176%; tile64 changes +0.396%, +3.507%, -4.491%
for 512/128/64 active experts respectively. All tile outputs agree exactly;
the 16 original-input cases still fail for all three widths (48 failures).
No global selector is promoted. See [timing and numerical results](Q2-SCALED-TILES.md).

Offline analysis verifies all 94 collected artifacts, both source capsules,
2041 source files, frozen fixtures and saved shaped FP64 errors. Complete JSON,
CSV and SVG/PNG reports retain every cohort and the failed numerical verdict.
Observed CPU/GPU maxima are 69.5/40 C for conversion and 68.625/52 C for tiles,
including builds; these short components do not measure cooling's benefit.

Fresh closure at 13:25:01 UTC finds eight owned processes and their groups
retired, KFD empty and all four original lease identities free, CPU37.25 C/
GPU36 C. The remote/shared registry and local `run/` receipt record release.
The direct core-thread update fails at the local MCP transport; no delivery
is claimed. No model/Core-19 restart is queued. The full quality comparison,
historical numerical failures and Q2/UD performance requirement remain open.

## Fan policy corrected and conversion experiment prepared — 2026-10-03

The owner clarifies 98 C as a CPU limit and requests maximum fans at 82 C.
All three `.157` curves are applied and read back through existing `axb35-ctl`:
up 40/50/60/70/82 C and down 35/45/55/65/78 C. The JSON and enabled boot service
retain them through a fan-only loader, correcting installed apply's fixed-curve
behavior. Actual performance/120 W power mode is unchanged. See
[configuration, backup and validation](Q2-FAN-CURVE.md). The corrected monitor
keeps CPU 98 C inclusive and exposed hardware limits, without assigning that
CPU cap to GPU edge. CPU Debug/sanitizer checks pass 16/16 on `.157`.

The [narrow-vector component](Q2-NARROW-VECTOR.md) compiles locally, preserves
all 150 original kernel instruction bodies and adds a 10-VGPR vector conversion
with no LDS/scratch. The prepared 192-case fixture includes independent F16
rounding, misalignment/tail guards and two complete projection consumers with
rotating buffers and mapped weights. Profile motivation is 193 scalar narrow
calls / 61.239 ms. No GPU component or model arm has run; performance and
numerical acceptance remain unproven. Fan setup and host checks do not complete
the interrupted Core-19 cohort or close the Q2/UD throughput gap.

## Interrupted Core-19 and engine feature audit — 2026-10-03

Qualified full Core-19 stops at 12:25:27 UTC after the GPU reaches 99 C,
exceeding the then-shared 98 C guard, later corrected to CPU-only as above.
The owned session exits -15;
container cleanup exits 0. Two first attempts finish: HTML-filter reward 0 and
Cython reward 1. COBOL is interrupted after 31 agent steps; the other 16 tasks,
conditional second attempts and retained/scaled full arms remain unmeasured.
All 11 supervisor artifacts and 34 partial task files are collected/hash verified.
Fresh closure at 12:30:15 confirms owned processes/containers absent, readable
KFD empty and all four original leases free. No GPU restart is queued.

The [engine audit](../config/q2-terminal-engine-audit.json) confirms thinking
is fixed off in the frozen adapter and cannot be enabled through its API.
This may affect absolute quality; it needs a separate matched comparison.
The failed HTML task did receive its shell results through Terminus JSON.
The agent invoked a pytest module as a plain script, executing no test, and
mistook silence for success. The actual verifier observed no browser alert.
Upstream instructions ambiguously suggest running that file directly. Neither
this baseline failure nor the later thermal stop establishes scaled-input harm.
See [diagnosis and limits](Q2-TERMINAL-BENCH.md#engine-feature-audit-and-interrupted-full-campaign).
The dated observations below describe the earlier live campaign.

## Scaled-input gain and real task qualification — 2026-10-03

The one-plane scaled Q2 component reduces measured packing/down time 20.97–22.25%
but fails all 18 targeted independent operator checks. Full original-model
C1 pp2048/tg128 gives 1336.120648 → 1378.318646 PP (+3.15825%), with decode
24.09013277 → 24.10368965 calls/s. Fresh UD reaches 1682.975427 PP and
24.32964050 decode calls/s: remaining candidate gaps are 18.10227% and 0.92871%.
All nine token files match but twelve logits differ; maximum qualified-reference
KL is 0.003770894 against the unchanged 0.002 limit. No numerical promotion.
A separate profile confirms 48 scaled-down and 48 packing calls. See
[complete values, failures and plots](Q2-SCALED-INPUT.md).

The owner selected pinned Terminal-Bench Mini/Core-19 for actual task quality
and approved isolated Harbor/container dependencies. C17 LIE endpoint admission
with original Q2 weights and the upstream doctor passes. Shared context metadata
and default-output corrections pass 25/25 Debug and sanitizer checks. The real smoke
task passes on all three variants, five verifier checks each. Candidate uses
nine steps/2159 output tokens versus retained eight/1792. Full Core-19 is
started sequentially under persistent supervision; its scores remain pending.
See [protocol, limits and job paths](Q2-TERMINAL-BENCH.md). Existing numerical
rejection, long-context/concurrency work and Q2/UD parity remain open.

The live serving audit records body/message ceilings alongside output/context
limits and separates POST success from unattributed GET errors. Full-run
evidence collection now has a finite 2 GiB per-archive bound and streaming
hashes, preserving long telemetry without whole-file allocations. Its `.157`
CPU guards pass 15/15 Debug and sanitizer cases; seven artifacts verify. The
then-active full baseline remained unchanged; it later stopped as recorded above.

A [scaled Q2 tile128 component experiment](Q2-SCALED-TILES.md) is now prepared
while Core-19 runs. Static compilation adds one kernel and preserves all 150
existing instruction bodies after documented label/comment normalization.
The `.157` host guards pass 14/14 Debug and sanitizer cases. No new GPU/model
arm is launched or queued; tile performance and numerical replay are pending.

Read-only analysis of the retained scaled trace now records all 48 routed
dispatch pairs: tile48 down uses 512–712 descriptors, while gate/up selects
64 rows in 29 layers and 128 in 19. The pending down fixture now compares
both widths against tile48, including 63/64/65-row boundaries. Tile64 uses
104 VGPR versus tile128's 169 and tile48's 96. Kernel source remains unchanged;
the expanded fixture passes local syntax/format checks, with no GPU result.
Packing/down is only 14.056% of the diagnostic kernel sum, so the 18.102%
unprofiled wall reduction needed for UD parity also motivates other stages.
These distinct timing scopes do not constitute a throughput prediction.

## C17 GPU fork/join is real but regresses prefill — 2026-10-03 UTC

The [shared/routed experiment](Q2-SHARED-OVERLAP.md) adds a C17 one-branch
lifecycle and a HIP stream/event adapter while retaining all numerical kernel
sources and tensor allocations. Input readiness, consumer joins, partial
launch errors and cancellation have explicit ownership boundaries. CPU Debug
and ASan/UBSan each pass 13/13; all 32 synthetic GPU cases compare 315,498,496
bytes exactly. Failed device synchronization/hardware recovery is unqualified.

Fresh complete MMQ builds and original-model C1 pp2048/tg128 runs measure
1336.259526 to 1322.513714 PP (-1.02868%) and 24.08694614 to 24.09063990 TG
(+0.01534%). All 21 model files, eighteen within-arm replay checks and the
retained checkpoint comparison are exact. The candidate records 192 clean
starts/joins. Prefill ranges do not overlap; decode ranges do. No promotion
or new UD arm follows. The selected source, earlier numerical qualification
gap and full Q2/UD parity objective remain unchanged.

A separate pp2048/tg16 profile proves 201.937 ms of distinct-stream overlap,
with 1763 parent and 192 shared dispatches. All fifteen profile files reproduce
the retained diagnostic. Sum of kernel durations is 1754.841 ms, union busy
time 1552.903 ms and span 1557.448 ms; these are diagnostic quantities, not
the unprofiled benchmark result. Readiness alone is insufficient for resource
admission; hardware-counter attribution of the wall regression remains open.
The report retains rates, durations, every sample, graphs and a stream timeline.

Five runners, 24 zero command exits and 89 artifacts verify. Every capsule
matches 1019/1022 source files and 50 guard/fixture files. GPU/CPU maxima are
79/94.375 C. Release at 09:01:58 and independent observer retirement at
09:02:30 verify all owned jobs absent, KFD empty and four leases free.
No core-thread/DS4 source, deployment or publication changes occur.

## GPU dataflow audit and rejected F32 scatter — 2026-10-03 UTC

The owner's reactive-GPU/code-organization inquiry now has a
[dependency and buffer map](Q2-GPU-DATAFLOW.md). It identifies current CPU/GPU
route-map overlap, largely sequential internal GPU work, the C dispatcher
boundary and concrete scratch lifetimes. Busy GPU time is not saturation.
The isolated 741-line routed-module extraction retains all 146 kernel bodies
and metadata exactly except for the HIP compilation-unit identifier; 1020
source files reconstruct. No internal GPU scheduler is claimed implemented.

The [padded F32 scatter screen](Q2-DOWN-SCATTER.md) follows the exposed F16/F32
epilogue asymmetry. It preserves all 62 saved operator buffers and 52,428,800
shaped output values, with unchanged independent limits, but packed-Q2 median
time rises 5375.014 to 5502.722 us (+2.376%); unchanged raw input shifts +0.906%.
Only two of 28 routed assembly bodies change. No model run or promotion follows.
The selected Q2 source and unmet full Q2/UD parity objective remain unchanged.

Debug/ASan each pass 12/12. Four runners, fifteen zero command exits and 83
artifacts verify; every capsule matches 1019 source and 42 guard/fixture files.
GPU/CPU maxima are 49/80.75 C. Release at 08:12:19 and independent observer
retirement at 08:12:57 verify empty KFD, original leases free and owned jobs
absent. The next reactive investigation must isolate shared/routed scratch
before introducing concurrent GPU regions; no core-thread source is modified.

## Row80 reduces component time without a confirmed model gain — 2026-10-03 UTC

The [80-row HC down experiment](Q2-HC-ROW80.md) retains 128-token tiles and
both ordered K16 sums, reducing logical input staging 200 to 160 MiB without
increasing weight staging. Paired waves use 137 VGPRs and 26 KiB LDS, with no
scratch; eleven other dense bodies stay assembly-identical. All 22 operator
hashes are exact, with the four inherited fallback failures unchanged.
Component down median time falls 5.71%; the plain up control changes +0.475%.

Fresh full MMQ builds and complete-model tests measure 1335.933710 to
1337.325450 PP (+0.104%) and 24.09672252 to 24.08888365 TG (-0.0325%), both with
overlapping ranges. All 21 model files match, the reference reproduces the
retained checkpoint, and eighteen within-arm replay checks pass. No useful
model gain is established, so row80 is not selected and no fresh UD arm follows.
The retained paired-HC-up source and unresolved Q2/UD target stay unchanged.

Debug and ASan/UBSan each pass 12/12. Five runners, twenty command exits and
155 artifacts verify; the two inherited component exits remain one. GPU/CPU
maxima are 82/92.75 C. Release at 07:40:59 UTC and observer retirement at
07:42:53 confirm empty KFD, original leases free and owned jobs absent. The
shared registry/ledger preserve handover while outgoing thread transport fails.

## Deferred HC norm rejected after complete-cycle measurement — 2026-10-03 UTC

The [deferred-normalization screen](Q2-HC-DEFERRED-NORM.md) stores four scales
per token instead of an 80 MiB F32 norm at 2048 rows; both mix and injection
reconstruct values. The complete ordinary cycle becomes 10.29% slower. MoE
median time decreases 1.89% with overlapping ranges, but all 26 complete
replays have new differences. Initial residual/F16/down outputs match; F32
reconstruction and later consumers differ. All sampled normalization/consumer
oracles pass unchanged limits; the known independent tiny-down failure remains.
Actual numerical exit 1 is preserved after every timing. No variant is selected.

Twenty original control assembly bodies remain identical, 1019 source files
reconstruct, and Debug plus ASan/UBSan each pass 12/12 on `.157`. Two runners,
nine command exits, 55 artifacts and twenty timings verify. No model is opened;
runner guards refuse model modes for this source, which has no executor wiring.
GPU/CPU maxima are 52/81.25 C. Release at 07:14:59 UTC and independent observer
retirement at 07:15:31 confirm empty KFD, original leases free and owned jobs
absent. Direct thread transport fails; the shared ledger preserves handover.
The retained 1335.84 PP / 24.09 TG result and Q2/UD gap remain unchanged.

## Complete HC sequence rejects paired norm materialization — 2026-10-03 UTC

The [producer/consumer experiment](Q2-HC-SEQUENCE.md) closes the missing scope
between the previous norm-only component gain and full-model regression.
At 2048 rows with 100 MiB rotating weights, paired F32/F16 norm output adds
26.69% ordinary / 9.31% MoE sequence time. Combining it with the previous
half-row geometry still adds 26.86% / 13.38%. Original control kernels remain
available and assembly-identical, with order and output allocations alternated.
No variant is selected and no original-model benchmark is admitted.

All 128 within-arm complete-output hash pairs, 64 cross-geometry pairs and
36 saved file pairs match. Independent full-norm checks pass; ordinary n97
tiny-input down exceeds the unchanged peak-scaled limit at 2.16019e-5 on both
identical outputs. Both actual component exits 1 are retained. Two host cohorts
pass 12/12 Debug and 12/12 ASan/UBSan. Forty timing samples and 94 artifacts
verify, with sixteen other command exits 0. The new isolated fixture, source
generators, patches, analyzer, complete results and graphs are retained.

The memory-lifetime review answers the owner's reactive question: F32 norm
must survive down until fused up/mix/injection consumes it. The F16 scratch is
already reused by the next producer on the same stream. Removing a launch
does not remove either allocation. A next hypothesis is to avoid materializing
the F32 norm and reconstruct its exact values in the later consumer, retaining
residual/scales and every rounding boundary. This is unimplemented; a complete
mix/injection comparison is required. No reactive benefit is claimed here.

Q2/UD parity remains unmet; the selected 1335.84 PP / 24.09 TG result is unchanged.
Fresh closure at 06:35:11 UTC verifies all four runners/eighteen commands absent,
KFD empty and four original leases free. Independent observer retirement is
verified at 06:35:35 UTC. No model was opened, and no GPU job, waiter or retry
remains. GPU/CPU observed maxima are 61/79.625 C. The shared ledger records the
release while direct thread transport is unavailable.

## HC row reuse has no confirmed speed benefit — 2026-10-03 UTC

The [row-reuse campaign](Q2-HC-ROW-REUSE.md) tests original-F16 HC down with
320x32 and 160x64 tiles while preserving both K16 accumulation chains. The
first lowers logical input replication fivefold but raises weight staging
fourfold; component median time increases 3.18%. The second balances those
costs at 28 KiB LDS and 210 VGPRs: its first -1.33% time change becomes +0.44%
in an explicit reverse-order pair. Unchanged controls vary +1.01%, +0.24% and
+0.23% respectively. No consistent useful gain admits a model benchmark.

All 22 complete operator output hashes remain exact across five component arms.
The same four fallback cases fail unchanged independent limits in each arm;
their actual exits 1 are retained. Both CPU cohorts pass 12/12 Debug and
12/12 ASan/UBSan. Seven runners, 27 commands, 254 artifacts and fifty timing
samples verify. The 320-row final epilogue and its 160-row derivative preserve
all eleven other dense assembly bodies, after an earlier generic version
changed control code and was isolated before GPU execution.

Neither variant is selected; the retained 1335.84 PP / 24.09 TG result and
Q2/UD gap remain unchanged. The next scope is producer/consumer interaction:
the earlier exact norm-copy change shifted saved narrowing time into its
following projection. A zero-fuzz dry run confirms source compatibility, with
no combined GPU run or promotion. Both this HC fixture and production HC
weights use `hipMalloc`. This confirms the same allocation API, without proving
equal placement or cache history.

Release at 05:54:12 UTC and independent observer retirement at 05:55:21 verify
empty KFD, four original leases free and every owned identity absent. GPU/CPU
maxima are 49 / 81 C; no model is opened. No GPU job or automatic retry remains.

## Shared Q2 palette is exact without a speed gain — 2026-10-03 UTC

The [shared-palette experiment](Q2-STAGED-PALETTE.md) computes four rounded
weights once in the LDS producer, retaining them in the former eight-byte
scale/bias slot. Static mixed-half FMA instructions fall from 12 to 6; tile48
keeps 144 VGPRs, 24,832 LDS bytes and no scratch. Original activation precision,
WMMA order, residual correction and model storage remain intact. The raw-input
control's compiled instructions are unchanged.

GPU operators pass thirty independent cases and all 62 saved buffers exactly
match the retained palette. The shaped benchmark preserves all 52,428,800
outputs and 1024 FP64 checks, but median packed time rises from 5342.604 to
5395.196 us (+0.98%); the control changes -0.37%. All twenty samples, graph
and CSV are retained. The changed-path sample ranges do not overlap. The
candidate is not selected and no model benchmark follows; the existing
1335.84 PP / 24.09 TG reference remains unchanged and parity is unmet.

The host cohort passes 12/12 Debug and 12/12 ASan/UBSan on `.157`. Four runners,
fifteen command exits 0 and 83 artifacts verify; no model is opened. Release at
05:26:44 UTC and observer retirement at 05:27:14 confirm empty KFD, original
leases free and all owned identities absent. The experiment narrows the next
optimization: removing this duplicate affine conversion at the same memory
footprint is insufficient; any further change needs a different measured
dataflow benefit, not an assumed gain from fewer arithmetic instructions.

## Single HC chain rejected; bit conversion inspected — 2026-10-03 UTC

The [single-chain HC experiment](Q2-HC-SINGLE-CHAIN.md), independently derived
from the retained source after consulting historical DS4 reports, reduces
static down VGPRs from 251 to 219 but increases component median time
**14.14%**, from 1161.768 to 1326.033 us. The unchanged up control changes
-0.17%. Eight changed down cases newly exceed the original FP64 limits;
failures rise from 4 to 12. Both numerical exits 1 and all twenty timing
samples are preserved, with graph and CSV. No complete-model benchmark follows
this rejection; paired HC up and the prior 1335.84 PP / 24.09 TG remain selected.

Fresh retained Q2/UD diagnostic traces pass 28/28 replay checks. Their prefill
kernel-time difference is 319.490 ms: HC down +89.885, routed down +84.604,
explicit packing/narrowing +64.949, HC up +25.762 and gate/up +23.995 ms.
The offline classifier now handles appended template flags and distinguishes
F16 HC up from Q8 correctly. Trace artifacts are unchanged. Both `.157` host
cohorts pass 12/12 Debug and 12/12 ASan/UBSan, including the new classification
regressions in the second cohort. Six runners, 32 commands and 162 artifacts
verify; release at 05:04:19 UTC and independent observer retirement at 05:05:39
confirm no owned process, GPU job or lease remains. Model stat witnesses agree.

At the owner's suggestion, the [static bitfield probe](Q2-BIT-CONVERSION.md)
compares shift extraction, union/bitfield representation and direct floating
construction for gfx1151. Extraction compiles identically; bounded packed-half
construction uses five data instructions versus seven for scalar conversions.
The union/bitfield FP32 construction equals explicit integer construction in
assembly. These findings neither measure speed nor reject bit manipulation as
a technique. The retained executor already uses mantissa construction and the
Q2 affine palette; further replacement requires an actual hot-path benefit.

## Reassessment and routed tile rejection — 2026-10-03 UTC

The owner requests a recap and points to historical DS4 results. The
[reassessment](Q2-REASSESSMENT.md) verifies that Q2's historical DS4 2K rate
was 1053.50 tokens/s after adapting Gufo's packed routed kernel; later
1100–1194-class HC measurements primarily concern Q4. No DS4 source, binary
or artifact is imported. Its documented F16 SwiGLU boundary and single-K16 HC
chain differ from this workstream's compensated expert input and two-chain
HC arithmetic. Those are explicit numerical hypotheses, not accepted ports.

Offline marked-trace analysis confirms twelve fused attention calls per model,
44.252 ms Q2 versus 45.696 ms UD, and all 48 expert-down calls at tile48 in
both models. Attention or missing tile64 selection does not explain the recorded
gap. The current source still measures 1335.84 PP / 24.09 TG against fresh UD
1671.71 / 24.33; no new model measurement occurred. The independent PLE
lookahead benefit on first-access 8K inputs remains separate from that warm gap.

The new synthetic 48/64 comparison preserves all 52,428,800 outputs per routing
and passes 3072 FP64 sampled dots, but tile64 costs 4.40–7.51% more time.
Thirty samples, SVG/PNG/CSV and the verified complete reports are saved. The
tile16 GPU arm was withdrawn before launch for the reassessment. Two CPU guard
cohorts pass 12/12 Debug and 12/12 ASan/UBSan on .157. Three runners, fifteen
command exits (all 0) and 21 collected artifacts verify; no original model was
opened. Release at 04:17:41 UTC and observer retirement at 04:18:26 verify empty
KFD, original leases free and all owned identities absent. The selected engine,
public C ABI and qualified runtime remain unchanged; no GPU job is queued.

## Wider HC down variants add no useful gain — 2026-10-03 UTC

The [wider HC down screen](Q2-HC-DOWN-WIDE.md) preserves the original two
ordered K16 chains while changing the tile from 64x128 to 128x128. At 2048
tokens, 48 blocks replace 80 and each input stripe is staged three times
instead of five, with 20% extra padded matrix work. Separate variants reduce
stage depth to BK1 or distribute contiguous 16-byte stage reads across lanes.
Static down VGPR counts are 204 / 161 / 135, all without private scratch.

The reference median is 1149.699 us. Wider BK2 reaches 1140.452 us (-0.80%),
with overlapping samples and a +2.19% difference in the unchanged plain-up
control. BK1 regresses to 3382.034 us (+194.17%); contiguous BK2 regresses to
1261.692 us (+9.74%). None is selected or followed by a complete-model run.
The retained paired-up candidate and its prior +1.75% full-prefill gain remain
unchanged. Lower register use alone has not improved HC down. The next
diagnostic priority returns to routed-expert down and activation packing.

All 22 complete operator hashes and 44 saved value/coordinate files agree
for each candidate. The same four independent FP64 library controls fail in
all four arms at the original limits, retaining actual exit 1. Timed samples
complete with finite/checksum checks; no full timed-buffer hash is claimed.
Three host guard cohorts each pass 12/12 Debug and 12/12 ASan/UBSan on `.157`.
Seven runners, 30 command exits and 213 artifacts verify: four expected
component exits 1 and 26 exits 0. All three generators reproduce their complete
1019-file trees and patches exactly. Maximum GPU/CPU temperatures are
50 C / 81.375 C. Three graphs, CSVs and all 40 unique timing values are saved.

Closure at 03:29:32 UTC and independent observer retirement at 03:36:11 verify
all own processes absent, empty KFD and four original leases free. No original
model was opened, and no remote Q2 job or retry remains. Source, capsules and
evidence stay in persistent project directories. These experiments change no
reactive scheduling or public C contract; broader performance and quality
acceptance remain open.

## Paired HC up improves complete prefill with exact outputs — 2026-10-03 UTC

The [paired HC up experiment](Q2-HC-UP-CHAINS.md) assigns the existing two
K16 accumulator chains to physical wave pairs. This enables 256x128 tiles
without the earlier larger-tile spills, reducing blocks from 2560 to 640 at
2048 rows. Original F16 weights, ordered sums, mixing and half conversion
remain intact. Static gfx1151 resources are 242 VGPR / 24 KiB LDS / zero
private scratch. No reactive, scalar decode or public C ABI change is made.

The 100 MiB rotating-weight component falls **1163.686 -> 842.188 us (-27.63%)**.
All eleven independent FP64 cases per source pass the unchanged limits, 62
saved cross-source files match and all five timed replays per source are exact.
The unchanged separate-path control differs +0.58%. Complete-model prefill
rises **1312.915 -> 1335.837 tokens/s (+1.75%)**, saving 26.766 ms. All 21
Q2 model files match, as do 21 fresh/retained reference files. Decode changes
24.111117 -> 24.091526 calls/s (-0.0813%, overlapping ranges); the unchanged
scalar source does not establish a zero-margin guarantee. Fresh UD reaches
1671.709 / 24.332835, leaving Q2 behind 20.09% PP / 0.99% TG. The paired-up
source is retained for further prefill development, without runtime promotion.
All samples, rates, durations, two graphs and CSV files accompany the report.

Host fixtures pass 12/12 Debug and 12/12 ASan/UBSan on `.157`. Six runners,
24 commands and 217 artifacts verify, all exits 0. The first device-only
compile mistakenly selected the previous source; its receipt remains evidence
and the corrected command qualifies this candidate. Maximum observed GPU/CPU
temperatures are 81 C / 90.125 C. Closure at 02:52:18 UTC and independent
observer retirement at 02:53:03 verify all own processes absent, empty KFD,
four original leases free and five model witnesses unchanged. No Q2 remote
job or retry remains. Broader contexts/concurrency, independent model quality
and the Q2/UD parity goal remain open.

## HC consumer narrowing rejected on the complete model — 2026-10-03 UTC

The [consumer-side narrowing experiment](Q2-HC-INPUT.md) moves the existing
F32-to-F16 rounding into HC down input loads. It preserves original weights,
both ordered sum chains, buffer lifetimes and all 21 saved model output files.
Ten new complete synthetic output pairs and five timed replays are byte-exact;
all 22 original component controls are unchanged. One added tiny-input case
fails the independent FP64 error/peak threshold on both identical paths, with
the four original library-control failures retained. No limit is relaxed.

The complete narrowing-plus-projection component saves **6.34%** time, but
model prefill falls **1316.149 -> 1289.116 tokens/s (-2.05%)**. Decode is
24.121957 -> 24.152722 calls/s (+0.13%) on an unchanged scalar path; this is
not a causal decode improvement. Fresh UD reaches 1660.690 / 24.336113,
leaving the selected palette reference 20.75% / 0.88% behind. The candidate
is rejected and palette stays selected. Full rates, durations, all nine
measured sessions and a graph are linked from the report.

Fresh diagnostic profiles replay all 28 checks exactly. Removing 96 narrowing
launches saves 60.191 ms, but HC down adds 90.674 ms. Total prefill kernel time
increases 28.708 ms; inter-kernel gaps fall slightly. This locates the loss
inside the projection without proving a cache or bandwidth explanation.

The host capsule passes 12/12 Debug and 12/12 ASan/UBSan on `.157`. Seven
runners, 35 commands and 205 hash-verified artifacts finish. One synthetic
command retains numerical-failure exit 1; the other 34 commands exit 0.
Maximum observed GPU/CPU temperatures are 83 C / 94.125 C. Closure at
02:02:35 UTC and independent observer retirement at 02:03:10 verify all own
processes absent, empty KFD, four original leases free and five model witnesses
unchanged. No Q2 remote job or retry remains. The experiment changes no
reactive scheduling, HTTP contract or model file; parity remains open.

## HC library algorithm improves speed, numerical gates remain open — 2026-10-03 UTC

The [bounded HC library screen](Q2-HC-LIBRARY.md) evaluates the seven unique
algorithms returned at both 0 and 64 MiB workspace caps; all require zero
workspace. The fastest down algorithm saves 14.66–17.94% time against bracketed
native controls. Its isolated model dispatch saves 16.97% component time,
while changing only the expected n2048 down output. Original F16 weight bytes,
fused HC up and scalar decode paths remain intact.

Complete-model prefill improves **1314.354 -> 1341.371 tokens/s (+2.06%)**;
decode is 24.099112 -> 24.121551 calls/s (+0.09%, overlapping ranges). Fresh UD
reaches 1665.648 / 24.340198, leaving the candidate 19.47% / 0.90% behind.
All nine input/output token files agree across all three arms, and the fresh
reference replays its 21 retained files. However, the candidate changes eight
2K logit files: prefill relative L2 is 0.195035 and KL 0.00100189. Its synthetic
FP64 and position-invariance checks also fail at the unchanged limits. The
performance lead is retained for investigation; palette stays selected.

Both host versions pass 12/12 Debug and 12/12 ASan/UBSan on `.157`. Nine runners,
38 commands and 322 hash-verified artifacts finish. Four synthetic commands
retain numerical-failure exit 1; all other commands exit 0. The first sweep's
rounded error logging and two local analysis failures remain evidence; a
logging-only correction reproduces all 62 saved component files exactly.
Maximum observed GPU/CPU readings are 85 C / 92.125 C. Closure at 01:03:41 UTC
and independent observer retirement at 01:04:24 verify all own processes
absent, empty KFD, four original leases free and five model witnesses unchanged.
No Q2 remote job or retry remains. Full samples, durations, two graphs and
source/validation receipts are linked from the report; parity is still open.

## HC data reuse rejected after complete-model comparison — 2026-10-03 UTC

The [three HC down experiments](Q2-HC-DATA-REUSE.md) retain all 22 synthetic
outputs per candidate. Direct global fragments regress component time 78.02%;
paired low/high accumulation waves regress 4.59%. Combining paired waves with
coalesced stage reads saves 5.04%, while the unchanged up control also improves
1.68%. Static VGPR falls from 251 to 129 without changing F16 weights or the
ordered sums. The component gain warrants a model comparison, not adoption.

Fresh complete-model prefill changes 1314.803 -> 1310.904 tokens/s (-0.30%),
with decode 24.065021 -> 24.096790 calls/s (+0.13%, unchanged decode path).
All 21 reference/candidate files match exactly, as do all 21 fresh/retained
palette files. No model benefit is demonstrated; all three candidates are
rejected and palette remains selected. Fresh UD reaches 1658.287 / 24.314854,
leaving the retained source 20.71% / 1.03% behind. The full report and new
graph include all prefill/decode rates, durations and measured samples.

Three source-guard arms each pass 12/12 Debug and 12/12 ASan/UBSan on `.157`.
Ten runners and 42 commands finish; four component commands retain the same
four original library numerical failures and actual exit 1. All 291 artifacts
verify. Device-only compilation and exact reconstruction pass; three inherited
upstream formatting exits 1 remain evidence. Verified closure at 00:04:15 UTC
and observer retirement at 00:04:44 confirm all own processes absent, empty KFD,
four original leases free and five original model witnesses unchanged. No Q2
remote job, waiter or automatic retry remains; no runtime promotion occurs.

The source audit identifies a separate hypothesis: the hipBLASLt fallback
selects the first supported zero-workspace algorithm. The current large-HC
path uses native WMMA, so that limit does not describe the selected kernel.
A future bounded-workspace comparison needs independent output checks and the
existing 100 MiB weight rotation; the official helper alone supplies neither
that rotation size for HC nor a numerical oracle. No library gain is claimed.

## Fresh prefill gap profile and rejected HC barriers — 2026-10-02 UTC

The [current Q2/UD profiles](Q2-PREFILL-GAP.md) reconcile 321.095 ms extra
prefill kernel time, primarily recognized HC down (+87.062), expert down
(+69.570), activation packing (+65.212) and HC up (+52.785). Each profile
replays its own unprofiled control exactly in 14 checks. Profile spans include
overhead and do not replace the retained model throughput comparison.

Two isolated compiler barriers before HC token/K32 fragment loads increase
static VGPR from 251 to 253. The fresh component medians regress 7.93% and
6.12%, with all 22 complete outputs per candidate exact. Both are rejected;
no new model arm or runtime promotion follows. Four existing numerical library
control failures and actual exit 1 remain in all three component arms.

Host guards pass 12/12 Debug and 12/12 ASan/UBSan. Six runners/29 commands
finish, all 203 artifacts verify, and source reconstruction/device compilation
pass. Inherited formatting and corrected assembly-parser failures remain in
evidence. Closure at 23:11:56 UTC and observer retirement at 23:12:27 confirm
empty KFD, all own processes absent, original leases free and original-model
witnesses unchanged. No Q2 remote job, waiter or automatic retry remains.
Palette/HC16 remains the measured candidate; full-model parity is still open.

## Q2 affine-value reuse improves complete prefill — 2026-10-02 UTC

The [affine palette](Q2-AFFINE-PALETTE.md) evaluates the four possible weights
once per Q2 affine group and selects their rounded F16 bytes in registers.
Original storage, activation compensation and accumulation order remain intact.
The shaped down component saves 7.10% time; its unchanged raw control also
improves 1.84%. All 62 operator buffers and 52,428,800 shaped outputs are exact,
with the original independent FP64 limits satisfied.

The complete fresh comparison retains a 1.35% prefill gain: HC16 1295.823 ->
palette 1313.327 tokens/s. Decode stays near 24.10 calls/s (-0.00062% median).
All twelve logit frontiers and nine token files match exactly; the HC16
reference reproduces its retained checkpoint. Fresh UD is 1660.101 / 24.309297,
leaving Q2 behind by 20.89% PP and 0.86% TG. Palette becomes the development
candidate, preserving HC16; no qualified-runtime or parity promotion occurs.
Broader contexts/concurrency, independent quality and earlier drift remain open.

Host fixtures pass 12/12 Debug and 12/12 ASan/UBSan. Seven runners and 27 remote
commands exit 0, and all 161 artifacts verify. The inherited formatting failure
and corrected local report exit 1 remain evidence. [Closure](../config/q2-affine-palette-validation.json)
at 22:34:30 UTC and observer retirement at 22:34:58 verify all own processes
absent, empty KFD, unchanged/free original leases and unchanged model witnesses.
No Q2 remote job, waiter or automatic retry remains. Full samples and graphs
are retained with the report.

## HC scalar parallelism improves complete decode — 2026-10-02

The [four/eight/sixteen/32-wave comparison](Q2-HC-DECODE-WAVES.md) finds useful
additional row parallelism without changing F16 weight bytes. Component medians
are 47.796 / 42.644 / 30.240 / 30.758 us; sixteen waves save 36.73% time.
All eleven independent operator cases pass per arm and all eight unaffected
buffers replay exactly. The three scalar frontiers change within the original
FP64 limits. Thirty-two waves are slower than sixteen and receive no model run.

The complete original-weight screen retains the gain: Q2 decode rises
23.170514 -> 24.055478 calls/s (+3.82%) with identical token trajectories.
Prefill changes 1294.041 -> 1291.808 tokens/s (-0.17%, overlapping samples).
All six prefill frontiers are exact; final-frontier KL is at most 3.15e-6.
Fresh UD measures 1650.348 PP / 24.136370 TG. The candidate trails by 21.73%
and 0.34%; this UD arm is itself below the earlier 1682.761 / 24.326 control.
Sixteen waves become the development candidate, not a qualified runtime or
zero-margin parity claim. The prefill gap and broader quality/context gates
remain open. Full ranges, durations, raw sample CSVs and graphs are retained.

Two host arms pass 12/12 Debug and 12/12 ASan/UBSan. Nine runners/36 commands
exit 0 and all 152 artifacts verify. Three inherited formatting exits 1 and
two corrected local validation exits 1 remain evidence. [Verified closure](../config/q2-hc-decode-validation.json)
at 21:48:33 UTC and observer retirement at 21:49:31 confirm empty KFD, all own
processes absent, unchanged/free leases and unchanged original model witnesses.
No Q2 remote job, waiter or automatic retry remains.

## Packed Q2 code reuse measured — 2026-10-02

Retaining the original Q2 code bytes across two K64 stages halves their source
fetches, but the [shaped component](Q2-CODE-REUSE.md) slows 5688.152 -> 5835.681
us (+2.59%). The unchanged raw-input control changes -0.13%. The candidate
is rejected, with no original-model run or runtime promotion. Additional
register lifetime may offset fetch savings; this comparison does not isolate
that mechanism. The complete-model Q2/UD performance gap remains open.

Thirty independent GPU cases, 32 packed/chain checks, all 62 saved buffers and
52,428,800 shaped output values pass unchanged limits/exact replay. The benchmark
also verifies 1024 independent FP64 dot products. Source guards pass 12/12
Debug and 12/12 ASan/UBSan on `.157`. Four runners/15 commands exit 0 and all
83 artifacts verify. [Release](../config/q2-code-reuse-validation.json) at
21:09:00 UTC and independent observer retirement at 21:09:36 verify empty KFD
and all four original leases free. No Q2 remote job or automatic retry remains.

## Reactive PLE first-access benefit measured — 2026-10-02

The [eight-set ABBAABBA comparison](Q2-PLE-FIRST-ACCESS.md) now measures the
larger I/O case missing from the warm experiment. Four first-position samples
per mode give 10.982155 -> 7.791053 s for 8K prefill: -29.06% elapsed time /
**+40.96% throughput**. Observed median page residency is 30.58% / 30.11%;
mean physical reads are 9093.921 / 9017.233 MiB. Lookahead hides 3.380 s of
preparation, while both paths still incur substantial I/O. On replay at about
99.95% page residency the rate changes only +0.57%; forced decode is unchanged.
All 576 frontier hashes and complete pair buffers are exact and finite.

This is a positive isolated scheduling result on synthetic varied inputs,
not a controlled identical-state storage trial, natural-language quality
qualification, production integration or warm Q2/UD parity. The original
BF16 PLE rows, arithmetic and default row-cache capacity remain unchanged.
Read-only inode checks do not find a current compression override or
NOCOMPRESS flag on either Q2 or the UD PLE shard; other sampled model regions
also show mixed extent encoding. Filesystem causality remains unisolated.

The same window completes [HC coalesced stage reads](Q2-HC-DOWN-COALESCED.md):
all 22 output hashes match, but down latency only changes 1177.428 -> 1169.698
us (0.66% rate gain), with broad overlap and unchanged up control +0.96% time.
Both numerical-control exit 1 results are retained, with no model sweep.

Three CPU fixture arms each pass 12/12 Debug and 12/12 ASan/UBSan. The extra
collector check follows a retained collection exit 1 at the old 128-MB cap;
the 318-MB complete output set is recovered without model rerun, under a bounded
mode-specific allowance and stricter path/duplicate checks. Six runners and
28 remote commands are complete: 26 exits 0, two known HC numerical exits 1.
All 170 artifacts verify. [Closure](../config/q2-coalesced-ple-validation.json)
at 20:50:13 UTC and independent retirement at 20:50:40 verify empty KFD and
four original/free leases. No Q2 remote job, waiter or automatic retry remains.

## Half-wave and HC scheduling measured — 2026-10-02

The returned `.157` window completes both [half-wave variants](Q2-HALF-WAVE.md)
and all three pending [HC scheduling probes](Q2-HC-DOWN-TILES.md). Half-wave
shuffle preserves every operator buffer and all 52.4 million shaped output
values but costs +1.44% time; direct row permute is effectively unchanged at
+0.05%. Their raw-input controls are about 0.9% faster. Neither candidate
warrants a full-model comparison. The reduction in static decode work did not
produce a measured component benefit.

All three HC variants retain the 22 complete output hashes and the same four
known unchanged-library numerical failures. Fresh down latency is 1172.898 us;
four row waves take 1278.868 us, four K blocks 2110.809 us, and the wide
four-row-wave tile 1623.730 us. These are +9.03%, +79.97% and +38.44% regressions,
with the unchanged up control between -2.36% and +0.20%. All are rejected for
performance; actual exit 1 and failure details remain evidence. The graphs
show all samples, zero-based axes, matched controls and component-only scope.

Updated host admission fixtures pass 12/12 Debug and 12/12 ASan/UBSan.
The [campaign receipt](../config/q2-half-wave-hc-validation.json) verifies ten
runners, 33 commands and 346 artifacts. Twenty-nine commands exit 0 and four
retain their numerical exit 1. No original model is opened. Release is verified
at 20:16:14 UTC, with independent observer retirement at 20:16:35 UTC, empty
KFD and all four original leases free. No Q2 remote job or retry remains.
The retained complete-model Q2/UD gap is unchanged; reactive PLE's earlier
+0.36% warmed result remains separate from these numerical-kernel probes.

## Q2 shared weight staging — 2026-10-02

The prepared staging kernel passes 30 independent GPU cases and 32 exact
packing/down/chain checks on `.157`. All 62 saved buffers and 52,428,800 shaped
synthetic output values match the retained packed baseline. Performance does
not improve: packed down time rises 5682.759 -> 5963.628 us (+4.94%), with the
unchanged raw-input control at -0.12%. The candidate is rejected without an
unjustified full-model sweep. [All samples, checks and graph](Q2-STAGED-WEIGHTS.md)
are retained; three runners/nine command exits are 0 and 76 artifacts verify.
The window is returned to core after verified process/lease closure. Local
work now prepares paired half-wave decoding with the original LDS footprint.
The Q2/UD performance goal remains unmet.

Both [half-wave variants](Q2-HALF-WAVE.md) compile device-only and reconstruct
all 1019 source files. They reduce static mixed-half FMA instructions 64 -> 32
without increasing LDS. The tile48 shape uses 146 VGPRs with HIP shuffle or
145 with explicit cross-row permute, versus 144 in the measured baseline.
Exchange instructions are extra work; no numerical or performance benefit is
implied by those static counts. Their subsequent runtime results and updated
source-admission guard qualification are recorded above. No variant improves
the measured component and no remote job or waiter is active.

## Reactive PLE lookahead — 2026-10-02

The owner asks whether reactive inference can hide n-gram stalls. An isolated
C17 producer/consumer now owns two bounded pinned input slots, readiness,
backpressure, cancellation and callback metrics. The transitional executor
validates prepared row IDs against live session history and retains each input
until HIP drain. Kernel arithmetic, table capacity and model bytes are unchanged.
Debug and ASan/UBSan each pass 12/12 CTest checks on `.157`; static executor and
full-model harness compilation pass. After core's verified R12 release, the
original-Q2 8K GPU comparison verifies all 432 frontiers byte-exact and real
in-flight cancellation/drain. Lookahead hides 174–187 ms of row preparation,
but native already overlaps much of that cost: median prefill is 1236.75 ->
1241.15 tokens/s (+0.36%), too small to establish a robust gain in three samples.
Prepared serial reaches 1209.85; decode is effectively unchanged. The first
ordered native run is 14.109 s; following arms use warmer pages and cannot
qualify a cold-input speedup. See the [full comparison and graph](Q2-PLE-LOOKAHEAD.md).
Two runners/ten command exits are 0, all 38 artifacts verify, and the window
is released with independent observer retirement. Production integration,
controlled first-access benefit and Q2/UD parity remain unqualified.

## Current state — 2026-10-02

The original antirez Q2 GGUF executes through a minimal patch to official Gufo
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`. It passes independent synthetic GPU
operators, parser/sanitizer checks and the bounded full-model semantic/C1 screen.
**The performance gate still fails relative to UD-Q4.** The latest retained isolated
[F32 MoE/HC fusion](Q2-HC-MOE-FUSION.md) measures 1297.80 PP/23.17 TG at C1 2K,
against a fresh UD control at 1682.76/24.33: deficits of 22.88%/4.76%. It retains
all saved packed-checkpoint logits and tokens, but is not accepted for integration.
This Q2 experiment does not qualify 128K/256K. The initial runtime screen was
48–66% slower in PP and 16–17% in decode; [initial results](Q2-RESULTS.md) retain
those values and failures. [Implementation](Q2-IMPLEMENTATION.md) records the
unchanged qualified runtime patch.

UD before/after the patch has 47/47 identical token/frontier files. Its median
PP changes by +0.22/+0.19/+0.30%, TG by +0.02/-0.19/-0.09%. The small measured
losses remain explicit; this is not a formal zero-margin no-regression pass.
Q2/UD physical prompts and generated trajectories match across these samples.
No independent full-model Q2 teacher or general model-quality score is claimed.

## Earlier Q2 weight-staging preparation — 2026-10-02

The [isolated staged-weight path](Q2-STAGED-WEIGHTS.md) decodes original Q2
weights once in LDS for the packed activation consumer. The retained profile
places 288.934 ms in this down projection. Static compilation halves the
mixed-half decode instructions, but VGPR/LDS requirements rise, so runtime
benefit remains unproven. All 1,019 files reconstruct exactly; changed-source
formatting and the new original-shape benchmark's host syntax pass. Existing
operators, numerical replay and GPU performance checks remain pending while
core owns `ssd-gpu-r12`. User-directed reactive PLE lookahead is examined as a
separate hypothesis with unchanged kernels and bounded buffer lifetimes.

## PLE I/O and cache capacity — 2026-10-02

The [bounded I/O comparison](Q2-PLE-CACHE.md) measures about 2,847 MiB physical
reads for 136 MiB returned on first-position Q2 row sets, versus about 131/131
MiB for UD. Page residency is recorded and policies are order-balanced; no
shared cache is evicted. Descriptor-local RANDOM advice does not help and is
rejected. The compression hypothesis now has measured read amplification,
but a controlled compressed/uncompressed comparison remains unperformed.

Increasing BF16 capacity from 16K/5 MiB to 64K/20 MiB halves repeated row-gather
latency, 43.123 -> 21.148 ms. Complete varied 2K prefill changes only
1,578.660 -> 1,561.402 ms (-1.09%), despite host blocked wait dropping from
27.401 to 3.288 ms. Forced decode is unchanged. All 264 compared model-frontier
hashes, 16 gather hashes and 18 saved complete files replay exactly. These are
instrumented diagnostics against the experimental baseline, not a runtime
promotion, independent quality teacher or solution to the warm GPU deficit.

I/O fixtures pass 12/12 Debug and 12/12 ASan/UBSan on `.157`; the fixed-capacity
source passes 11/11 each. Source reconstruction, changed-file formatting and
syntax pass. Full-tree formatting exits 1 on two unchanged upstream test files
in both bases and candidates; the actual failures remain recorded. All six
remote arms complete with 26 command exits 0 and 68 artifacts verified. The
window returns to core at 18:25:33 UTC; fresh KFD/lease closure and independent
observer retirement at 18:26:08 pass. No Q2 job, waiter or retry remains.

## N-gram/PLE diagnosis and HC down probes — 2026-10-02

[Direct PLE counters](Q2-PLE-ANALYSIS.md) isolate a first-access host I/O
bottleneck: Q2 varied 2K prefill 4,927 ms, blocked row wait 3,374 ms; UD
1,355/169 ms. Hashing is below 0.08 ms. Repeated-padding row waits are negligible,
so PLE does not explain the existing warm GPU deficit. The previous padding
prompt has only 664 distinct rows versus 32,766 in the synthetic varied input.
Q2 retains 16,384 encoded rows against UD's 65,536. Read-only extent metadata
finds compressed 128-KiB Q2 PLE samples and unencoded UD samples; Btrfs can
buffer compressed reads despite O_DIRECT. The report separates that supported
storage hypothesis from an unperformed controlled compression experiment.

Both model arms finish with all command exits 0, 46 hash-verified artifacts,
exact repeated frontier hashes and eight exact prefill replays against the
uninstrumented models. Host hash/I/O tests pass 11/11 Debug and 11/11 ASan/UBSan.
The fixture, counters, source patches, JSON report, graph and storage observer
are retained; no model data or runtime arithmetic changes. Long-context,
natural-language/cache-cold and C17 serving qualifications remain open.

The first [HC down tile probe](Q2-HC-DOWN-TILES.md) is byte-exact and 5.93%
slower despite fewer static registers. Both arms preserve the same four known
library-control numerical failures and exit 1. No full-model trial follows.
Three follow-up tiles compiled/reconstructed statically, with two prior
compilation failures retained. Their later runtime regressions are recorded
in the measured scheduling entry above.

The combined window is released at 17:43:35 UTC: seven runners and 32 command
identities/groups/sessions retired, KFD empty, four exact leases EX|NB/free,
163 artifacts verified. Independent observer retirement passes at 17:44:18.
See `config/q2-hc-down-ple-window-release.json`; no Q2 job or waiter remains.

## HC norm producer experiment — 2026-10-02

The paired F32 norm/F16 consumer copy passes 33 complete GPU buffer pairs,
eight independent FP64 cases, six narrowing cases and ten repeated full-buffer
checks after correction of two compiler rounding changes. The initial GPU
exit 1 and all failed buffers are retained. Debug and ASan/UBSan pass 10/10 each
on `.157`. The matched model pair retains all saved logits/tokens but prefill
falls 1294.135 -> 1289.123 tok/s (-0.39%); decode measures 23.202 -> 23.221.
Fresh UD is 1683.841/24.327. This variant is not accepted for performance;
fresh profiles show 37.223 ms saved in combine/narrowing offset by 40.501 ms
more in unchanged HC down kernels. Cache locality is a hypothesis, not measured
hardware-counter evidence. All 277 artifacts and 38 command exits are retained;
the GPU window is released with eight runners retired. See [report, complete samples and graph](Q2-HC-NORM-FUSION.md).

## Work preserved

Branch `feature/antirez-compat-audit` started from empty `develop`
`ce3ce59aaa8234c2c5aeadc328fead85c5999822`. Audit checkpoint `a0c61f3` and
implementation checkpoint `caf60eb` remain. The source is persistent in this
worktree; the official archive plus `patches/gufo-q2.patch` reproduces all 1019
candidate files byte-for-byte. Original licenses and vendor provenance are kept.
No antirez Qwen engine, withdrawn patch or sibling project source/artifact was
imported. The server/cache worktree was not merged or modified.

The user approved independent operator oracles plus existing UD control in place
of the original pre-implementation requirement for an already runnable exact-Q2
engine. The missing full-model comparator remains a quality limitation. Historical
model metadata and hashes retain their original dated provenance; current runs
check stat identity before/after without rehashing the entire model payload.

## Completed verification

- `.157` CPU: four debug and four ASan/UBSan CTests pass in both host rounds;
  final round includes strict legacy RoPE metadata compatibility.
- `.157` GPU: IQ2/Q2 independent synthetic operators and exhaustive finite F16
  widening pass; maximum RMS 0.000159285 under the predeclared 0.002 threshold.
- `.157` model: Q2 plus pristine/patched UD each complete semantic smoke and
  12 C1 samples (one warmup + three measured per 512/2048/8192 profile).
- 52 artifacts per model arm collected and SHA-256 verified; actual child,
  supervisor and transport outcomes retained. Source/build failures stay visible.
- Local repository checks: official formatting passes 486 files; exact archive
  reconstruction and report/plot generation pass. No local inference tests.

All GPU runs acquire the four existing EX|NB leases separately. The core thread
returned the coordinated window after core-gpu-r2 retired at 02:13:52.976 UTC.
Q2 completed the bounded campaign and handed the window back to core after
fresh retirement at 03:14:56.579 UTC; see `COORDINATION.md`.

## Measured diagnostic and next candidate

The profiler supervisor now passes six Debug and six ASan/UBSan CTests on `.157`.
Q2 and pristine UD traces both complete successfully, with 24 verified artifacts
and 11 exact baseline replay checks per arm. [Q2-PROFILING.md](Q2-PROFILING.md)
records all phase totals: Q2_K down dominates PP; dense F16 projections explain
a separate decode cost. These are diagnostic kernel times, not new performance
numbers. The unprofiled gate above is still failed.

The compacted Q2_K down experiment passed independent operators after retaining
a scaled F16 activation residual. Its C1 prefill improved by 34/50/64%, but the
model-frontier KL reached 0.002809 against a 0.002 limit. All generated tokens
matched; the numerical gate still failed. [Full experiment](Q2-DOWN-EXPERIMENT.md)
retains values, graphs, rejected source, operator failures and actual exits.
Checkpoint `a4a2b8b` restored the runtime patch exactly to SHA-256
`3029cd490bc75d045e9dcf696ac6c1b23092684ad25641c93d500cb9f2727473`.
No new UD control or long-context sweep was run after rejecting this candidate.

The next PP hypothesis must preserve baseline activation quantization while
improving layout/reuse. F16 HC down/up are a separate measured decode target.
No deployment, merge, publication or full performance acceptance occurred.

## Integer scheduling qualification completed — candidates rejected

[Q2-REGISTER-EXPERIMENT.md](Q2-REGISTER-EXPERIMENT.md) records the register-pressure
investigation, static screens and target operator runs. Bounded K unrolling
eliminates static scratch instructions in local assembly, but only 20/44 target
operator files match the original bytes. The token barrier with original unroll
policy and unchanged tile16 has 24/44 exact. Both pass independent operator
limits (maximum relative RMS about 0.000164) but fail the stricter declared replay
gate; maximum absolute change is 4.76837158203125e-7. No model profile or benchmark
was run for either candidate. A forced-full-unroll variant was rejected earlier
because its static scratch allocation increased.

Host checks pass 6/6 Debug and 6/6 ASan/UBSan on `.157`. Four arms retain 150
SHA-verified artifacts and actual zero command/transport exits; the separate
acceptance failures are explicit. Runtime patch SHA 3029cd49... and all 1019 source
files are restored exactly to the qualified original-Q2 reference. The expanded
44-output operator harness, resource report and rejected source remain reviewable.
Checkpoint `cfe7931` preserves the initial candidate before qualification.

Fresh closure at 2026-10-02 04:22:17.419 UTC verifies four runners and 15 command
identities/groups retired, KFD empty and four expected leases free. Core received
the handover; no Q2 job or retry remains. The performance target is still unmet.
A next implementation must bound register lifetimes while controlling the actual
FP32 contraction/reduction order. The separate F16 HC decode cost remains.

## Owner-authorized performance exploration

The owner requested measuring candidate speed before fixing small numerical
differences. [Q2-PERFORMANCE-EXPLORATION.md](Q2-PERFORMANCE-EXPLORATION.md) defines
a new exploratory campaign, preserving all prior failures and the qualified
runtime. Both isolated candidate trees match their operator source capsules
exactly. Fresh Q2/UD controls and numerical drift will accompany C1 timings.
The exploratory campaign completed after explicit core handover. All four
model arms pass semantic smoke and finish with command/transport exit 0; 208
artifacts are collected and SHA verified. Fresh Q2/UD controls reproduce all 47
prior input/output/frontier files exactly and have median rates within 0.3%.

At 512/2K/8K, bounded K median PP is 618.72/776.24/791.88 tok/s, versus original
548.15/606.16/559.55: gains 12.87/28.06/41.52%. The barrier reaches
554.15/695.27/718.09: gains 1.09/14.70/28.33%. Both remain below fresh UD
1047.70/1650.06/1628.67. TG is essentially flat but its measured small decreases
remain explicit; this is not a zero-margin no-regression pass. Full observed
ranges, durations, CSV and graph are in the linked report.

Token files remain exact for both candidates. Maximum full-frontier KL is
0.002494217876 for bounded K and 0.001866698415 for the barrier. The latter lies
within the historical WMMA diagnostic limit 0.002, but both still fail exact
replay. No variant is promoted. The runtime patch remains restored and the
experimental sources stay isolated. Observed model-process temperature maxima
rise 92/95/97/98°C across the sequential arms; small timing differences must not
be attributed confidently without a controlled follow-up.

Fresh release at 2026-10-02 06:14:39.647 UTC verifies four runners absent, 16 command
identities/groups retired, KFD empty and four expected leases free. Core received
the explicit handover; no Q2 job or retry remains. Checkpoint 714bac0 preserves
the isolated experiment setup before completion.

## F16 HC decode exploration

The owner confirms performance may be measured before numerical correction.
[Q2-HC-EXPERIMENT.md](Q2-HC-EXPERIMENT.md) records a four-wave F16 HC down
candidate against the original 320x10240 one-token projection. Original weights
and F32 activations are preserved. Isolated GPU medians improve from 135.4764
to 47.3383 us, 2.86188x, rotating 100 MiB beyond cache. Both arms pass 11
independent operators; eight controls remain byte-exact, three targeted cases
change rounding with maximum absolute delta 1.90735e-6. This is component
evidence, not model parity. The active qualified runtime remains unchanged.

CPU/GPU thermal guards stop owned process groups at 85 C or lower exposed
thresholds. Latest host checks pass 8/8 Debug and 8/8 ASan/UBSan on `.157`.
Two complete rebuilds stop thermally; a reduced micro target succeeds after a
recorded missing-wave64 link failure. Bounded model compilation now reuses only
the verified unchanged MMQ archive from this workstream's own qualified runs,
checking all 1019 source files except the changed HC kernel and archive/binary
identities. A CMake visibility failure was corrected and retained.

The uncooled original-model screen stops at CPU 85.750 C after one measured
request. A matched protocol with explicit 15-second idle intervals then retains
two measured Q2 reference requests before CPU 85.250 C interrupts the third.
Both remain FAILED, not completed comparative benchmarks. No continuous-serving
throughput or model parity is inferred from these partial observations.

The candidate and matched UD model arms complete all three requested samples.
At 2K, candidate PP/TG medians are 609.762/22.9246, versus fresh UD
1684.619/24.3159. Candidate TG is 12.25% above the two partial reference samples
and 5.72% below UD; PP remains 63.80% below UD. All nine Q2 token files match;
6/12 saved logits are exact, maximum KL3.2777e-6. Nine repeated candidate
frontiers/output checks are exact; fresh UD matches 21 historical files.
No runtime is promoted and no full comparison pass is claimed.

Twelve arms retain 153 verified artifacts and 42 command exits. Fresh closure
2026-10-02 07:13:11.718 UTC verifies all owned processes retired, KFD empty and
four expected leases free. GPU48 C/CPU49.5 C. Handover is recorded persistently
in remote run/q2-hc-window-release.json and the shared coordination registry;
direct thread-message delivery currently fails with an HTTP transport error.
No Q2 load or automatic retry remains. Overall PP/TG parity with UD stays open.

## F16 HC prefill exploration

[HC prefill WMMA](Q2-HC-PREFILL.md) ports the existing official raw-half pipeline
to original HC down/up shapes without quantizing weights. Component speedups
are 2.04x/2.59x. Fresh matched C1 2K/128 model samples complete: PP 608.800 to
658.837 tok/s (+8.22%), TG 22.929 to 22.989 calls/s (+0.26%, no claimed TG gain).
Historical UD remains 1684.619 PP/24.316 TG; full Q2 parity is unmet.

The original hipBLASLt synthetic baseline fails 12/22 checks at the unchanged
2e-5 oracle limits; WMMA fails 4/22, all unchanged fallback controls. All 16
modified cases pass and all six controls retain full-output hashes. Timings
complete despite numerical exit 1, per explicit owner authorization. Nine
model token files are identical, four of 12 logit frontiers exact, maximum
KL 0.003925764262; candidate remains experimental. No false-positive conclusion
is inferred from identical greedy tokens. Full values, plots, raw failures and
source identities are retained in the report and config manifests.

The owner changes the thermal ceiling to 98 C inclusive; focused Debug 8/8 and
ASan/UBSan 8/8 pass on .157, including admission at 98000 mC and rejection at 98001 mC.
Lower exposed hardware limits remain strict. No physical device policy changes.
Seven arms, 168 collected/hash-verified artifacts, 29 commands; fresh closure
07:57:31.513 UTC verifies all runners/groups retired, KFD empty and four leases
free. Direct message transport is unavailable; coordinated release is recorded
in docs/COORDINATION.md and persistent remote/shared registry receipts.

## Combined expert kernels and native paired IQ2

[Q2-EXPERT-STACK.md](Q2-EXPERT-STACK.md) records two complete original-model
arms. HC4 + HC prefill + compensated Q2 down reaches 1037.258 PP/22.9725 TG.
Adding native paired IQ2 gate/up reaches 1240.516 PP/23.0103 TG, another 19.60%
prefill gain and 88.29% above the prior HC checkpoint. Decode is effectively
unchanged. Historical UD remains 1684.619 PP/24.3159 TG: the best candidate is
still 26.36% below PP and 5.37% below TG. The no-regression goal remains open.

Both isolated sources reconstruct byte-exactly across 1019 files; the qualified
runtime patch is unchanged. Full MMQ rebuilds avoid reusing archives after
executor/header changes. Paired IQ2 uses original packed weights, existing
upstream tables, routing and buffers, FP32 accumulation and F32 SwiGLU output
feeding compensated Q2 down. No new persistent allocation or model conversion.
Static assembly shows no private segment for the four IQ2 templates; no new
profile yet establishes their actual phase costs. Reactive policy is unchanged.

Twelve independent Q2 down and 18 paired IQ2 GPU cases pass. The IQ2 full outputs
are byte-exact across 12 tile-width comparisons. Host Debug 9/9 and ASan/UBSan 9/9
pass on .157. Nine saved model token files match the qualified Q2 reference for
each candidate, but 0/12 saved logit frontiers are exact. Maximum KL is 0.00181461
for combined down and 0.00274255 for paired IQ2; the latter exceeds the historical
0.002 diagnostic. No numerical false-positive or broad quality claim is made.

Five arms, 97 SHA-verified artifacts, 20 successful command exits. Original model
stat and binary identities remain unchanged; build/model arm maxima stay below
the 98 C inclusive ceiling. Fresh closure 08:33:20.974 UTC verifies runners/groups
retired, KFD empty and four leases free. The window is handed to core for its
14-arm SSD R2 campaign; no Q2 job or automatic retry remains. Reporting and
source work continue locally. Next runtime work needs a fresh candidate profile
and eventual matched UD control after coordinated handover.

## Prepared compensated activation layout

[Q2-PACKED-ACTIVATIONS.md](Q2-PACKED-ACTIVATIONS.md) prepares one mechanism:
produce the existing Q2 high/residual F16 pair in the IQ2 SwiGLU epilogue,
then extract it in down instead of repeating conversion in every output-row
block. Four bytes per slot and all persistent allocations remain unchanged.
The isolated patch reconstructs all 1019 files exactly; official formatting
passes 486 files. Device assembly and fixture/executor host syntax checks pass,
with the initial syntax and include-path failures retained. This is static
evidence only, not a GPU correctness or performance result.

Prepared operators reuse 30 independent cases, require exact packed-word and
down-output replay, and add two complete IQ2→Q2 chains. Full saved model
frontiers must match the paired-IQ2 checkpoint for this move. The remote wrapper
supports the isolated packed source, operator target and full model rebuild;
updated CPU guard fixtures await `.157` with the GPU checks. No new tests were
run on the occupied remote host. Core still owns the SSD window; the next
Q2 action after handover is a current baseline profile, followed by this
candidate only if the measured phase costs support it. UD parity remains open.

## Saved-logit diagnostic while the core owns the GPU

The [offline audit](Q2-EXPERT-STACK.md#offline-probability-audit) rules out a
pure constant-offset explanation for the paired-IQ2 model differences: at 2K,
centering removes only 10.68% of squared logit error. Maximum probability change
is 0.313803 percentage points, total variation 0.004114854 and KL 0.002742551.
The reference's top1 probability is at least 98.979% at all retained frontiers;
unchanged greedy output on these cases is weak evidence for close decisions.
No numerical pass/failure is rewritten. This is analysis of retained F32 files,
not additional GPU inference, performance evidence or independent teacher quality.

Fresh 09:09:51 UTC observation confirms earlier SSD R2/R3 processes absent and
KFD empty. Core has explicitly retained its enclosing window for SSD R4, so Q2
does not enter the idle gap. Prepared runtime checks remain unexecuted; the
performance goal is still active and unmet.

After core releases SSD R4, q2-packed-host-r1 completes on `.157` at 09:43:34 UTC:
Debug 9/9 and ASan/UBSan 9/9, six command exits 0, seven SHA-verified artifacts.
The updated packed-source admission/refusal fixtures pass; no model or GPU is
opened. All seven runner/command process identities are absent before handover.
Q2 records the next GPU/heavy-I/O slot for Point's read-only UD copy in persistent
remote run/q2-point-copy-handover.json and the shared registry. This precedes
Q2's current IQ2 profile and packed GPU checks. The performance goal remains
unmet; GPU-dependent work awaits the coordinated return.

## Packed activations measured against fresh UD — 2026-10-02

The arithmetic-preserving producer/consumer packing move completes on `.157`.
Thirty independent GPU operator cases pass unchanged limits; 18 exact packed
word checks, 12 exact down-output checks and two complete chains pass. All 30
original synthetic buffers reproduce the retained references. Fresh Q2 baseline
and candidate reproduce all 21 saved model files exactly, and the fresh baseline
also matches all 21 retained IQ2 checkpoint files. UD's 21 saved files replay its
retained control exactly. Both profiles pass 14 baseline checks and their 15
saved buffers match each other exactly.

Fresh unprofiled C1 pp2048/tg128 medians, one warmup plus three measured sessions:
Q2 reference 1240.505 PP/22.9755 TG; packed Q2 1250.451/22.9695;
UD 1685.150/24.3229. All use full MMQ rebuilds and 15 s idle outside timing.
Packing improves PP 0.802%, leaves TG unchanged, and preserves every saved
logit/token versus IQ2. Q2 still trails fresh UD 25.80% PP and 5.56% TG.
The earlier qualified-Q2 KL difference 0.00274255 is unchanged; its task-quality
impact remains unresolved. No diagnostic threshold is relaxed.

The diagnostic Q2 down sum falls 311.965→286.173 ms (-8.27%), but the full model
saves only 13.131 ms median prefill. HC projections, F32 combine/mix passes and
narrowing remain concrete follow-up targets. Decode trace variation on unchanged
code is not treated as a throughput gain. See the complete samples, graph/CSV,
replay checks and disposition in [Q2-PACKED-ACTIVATIONS.md](Q2-PACKED-ACTIVATIONS.md).

Six arms finish with 29 command exits zero and 196 collected/hash-verified
artifacts. Six runners and 29 commands/groups/sessions are retired; KFD empty,
all four expected leases freshly verified free at 10:29:49 UTC. No Q2 GPU job,
waiter or automatic retry remains. The candidate stays isolated and the parity
goal is **not met**. The coordinated next copy/core windows are recorded in
COORDINATION.md; local reporting does not reserve `.157`.

## HC up/mix fusion prepared — 2026-10-02

The next isolated candidate adapts the official UD fused HC template to the
original Q2 F16 up weights and unchanged F32 normalized streams. The gate
buffer's unused prefix stores the same narrowed low-rank input; mixed F32/F16
outputs share one projection epilogue, while inject preserves its F32 partials.
No persistent allocation, weight conversion, KV policy or scalar decode change.

The initial 256x128 tile shows 492 private bytes/work item. The prepared 128x64
tile has zero private bytes, 181 VGPRs and 18,432 LDS bytes; this is compiler
evidence only. All 1019 source files reconstruct exactly, official formatting
passes 486 files, and device assembly/host syntax pass. Seven synthetic GPU
cases, exact complete output replay and independent FP64 oracles are prepared.
GPU correctness, full-model replay and PP/TG remain unmeasured for this candidate.

The bounded `.157` CPU capsule completes at 10:59:50 UTC, all six commands zero,
Debug 9/9 and ASan/UBSan 9/9, seven artifacts collected/hash verified. Point's
copy retains the GPU/heavy-model-I/O window; CPU mode disables GPU visibility,
opens no model and takes no GPU lease. Core follows Point's return. No new Q2
GPU job or waiter is queued. See [Q2-HC-UP-FUSION.md](Q2-HC-UP-FUSION.md).
The measured checkpoint remains 1250.45 PP/22.97 TG and parity is still unmet.

## HC down prefetch prepared independently — 2026-10-02

The measured packed decode trace spends 69.603 ms in 1455 scalar HC down calls.
A separate candidate anticipates each next four-element group while retaining
original F16 weights, F32 activations, the observed 3/1/2/0 FMA sequence and the
existing four-wave reduction. It derives from packed, excluding the unmeasured
HC up fusion. Only the one-token 320x10240 dispatch changes.

Initial assembly shows LLVM removed the overlap; that version remains evidence.
A scheduling boundary restores loads before current arithmetic. Current static
resources are 20 VGPR, 12 SGPR, zero private bytes and 16 LDS bytes. Both source
reconstruction methods cover all 1019 files, baseline matches the measured
capsule exactly, and official formatting checks 486 files. Static compilation
and fixture syntax pass; none of this establishes numerical correctness or speed.

The `.157` CPU capsule finishes 11:31:22 UTC with six command exits zero,
Debug 9/9 and ASan/UBSan 9/9. Seven artifacts are hash verified and owned process
retirement is checked. The existing eleven-case GPU fixture and rotating-weight
microbenchmark are ready; fresh packed/model/UD comparisons await core's
verified return. No GPU job or automatic waiter is queued, and parity remains
unmet. See [Q2-HC-PREFETCH.md](Q2-HC-PREFETCH.md).

## Complete HC fusion output audit prepared — 2026-10-02

The HC up report reader now checks all seven planned cases and nineteen full
buffer pairs, including F16 output, F32 mixed rows and F32 inject partials.
Artifact hashes, lengths, finite values, oracle sample coverage and unchanged
thresholds must agree with the retained process outcome. Complete numerical
failures remain FAILED with exit 1; interruption, missing output, corruption or
runtime/postflight failures cannot be reclassified as numerical-only evidence.

Five CPU reader fixtures cover exact replay, a recorded numerical mismatch,
artifact truncation, non-finite values, signed-zero byte differences, missing
oracle coverage and runtime interruptions. Python syntax is checked locally;
target runtime execution remains pending. They are included in the next `.157`
CPU capsule, to run after core's R5 return. At 11:46:48 UTC the R5 controller
2496414/start150632787 is still alive and seven of nine arms have completed;
Q2 has no remote workload. This is preparation and verified waiting, not a new
Q2 performance result or completion of the parity goal.

## HC up GPU fusion and scalar vector decode — 2026-10-02

After core's verified R7 return, Q2 took the coordinated `.157` window with
fresh four-lease admission for each arm. The [HC up/mix fusion](Q2-HC-UP-FUSION.md)
passes seven synthetic GPU cases, nineteen byte-exact complete output pairs and
independent FP64 checks. Both full-model arms use a complete MMQ rebuild, one
warmup plus three C1 pp2048/tg128 samples and 15 s idle outside timing. Fresh
packed Q2 reaches 1250.823 PP/22.967 TG; fused Q2 reaches 1287.188/22.948.
All 21 saved model files and all replay checks are exact. Prefill improves
2.91%; decode is unchanged. [Complete evidence](../config/q2-hc-up-fused-results.json)
retains every sample, duration and thermal observation.

The independent HC down one- and two-group prefetch variants pass eleven
byte-exact GPU operator cases, but their 100 MiB rotating-weight medians are
47.601 and 51.153 µs versus 47.390 µs for the packed reference. They are
0.44% and 7.35% slower and were not promoted to full-model runs. Both negative
results, the first compile-failed HC up fixture attempt, all real exit codes
and their logs remain in persistent `evidence/`. The
[prefetch report](Q2-HC-PREFETCH.md) distinguishes static and runtime evidence.

The packed decode trace identifies 1,455 scalar F16 HC up calls at 50.793 ms
across fifteen decode steps. A first vector-load variant cuts the isolated
median from 34.474 to 30.432 µs, but changes 7,350/10,240 synthetic values by
up to 1.1921e-7 and produces decoded-logit drift after 127 steps. It is retained
for performance evidence, not called a false numerical flag. The ordered-FMA
variant is byte-exact on all eleven synthetic buffers and all twelve saved Q2
model F32 frontiers; tokens and replay checks also match. It reaches 29.919 µs
per HC up call, 1287.119 PP and 23.214 TG. Full decode improves 1.16% over
fused Q2; prefill is unchanged within measured spread. A fresh same-window UD
control reaches 1682.768 PP/24.301 TG. Q2 still trails 23.51% PP and 4.47% TG.
See [full results, graph and source evidence](Q2-HC-UP-VECTOR.md). Context and
concurrency qualification plus the Q2/UD no-regression goal remain open.
The final `.157` host capsule passes 10/10 Debug and 10/10 ASan/UBSan, with
six zero-exit commands and seven hash-verified artifacts. Q2 releases its
enclosing window at 13:37:03 UTC after retiring 15 runners and 55 commands,
observing KFD empty and verifying all four leases EX|NB/free; see the
[tracked release receipt](../config/q2-hc-vector-window-release.json).

## HC reader CPU fixtures pass; core retains GPU for R6 — 2026-10-02

R5 completes 9/9 at 11:57:08 UTC. Fresh observation verifies its controller and
last GPU processes absent, but core explicitly retains the enclosing window
for R6 byte-plane/Zstd checkpoint work. This prevents Q2 GPU admission; completed
R5 arms do not constitute a handover.

At 12:02:42 UTC the five Python reader fixtures pass a focused CTest on `.157`
in 0.10 s. Configuration and CTest exits are zero; two artifacts are collected
and hash verified, tested sources match the checkpoint, and both command
identities and the runner are retired. Pre/post KFD is empty. This small CPU
check runs while core prepares R6, opens no model and builds no C/C++ code.
[The receipt](../config/q2-hc-report-host.json) is separate from earlier native
Debug/ASan/UBSan evidence and from the still-pending GPU operators.

No further independent preparation is needed before testing the two isolated
HC candidates. Their GPU operator, model replay and performance measurements
await the external window return. Q2 remains at the measured packed checkpoint
1250.45 PP/22.97 TG versus UD 1685.15/24.32; the full parity objective is unmet.
