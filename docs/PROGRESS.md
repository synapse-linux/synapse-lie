<!-- SPDX-License-Identifier: MIT -->
# Progress — Q2 compatibility workstream

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
Three follow-up tiles now compile/reconstruct statically, with two prior
compilation failures retained; none is GPU or performance qualified.

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
