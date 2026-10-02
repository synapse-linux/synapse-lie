<!-- SPDX-License-Identifier: MIT -->
# Progress — Q2 compatibility workstream

## Current state — 2026-10-02

The original antirez Q2 GGUF executes through a minimal patch to official Gufo
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`. It passes independent synthetic GPU
operators, parser/sanitizer checks and the bounded full-model semantic/C1 screen.
**The performance gate fails relative to existing UD-Q4:** fresh PP is 48–66%
slower and decode 16–17% slower. The candidate is not accepted for integration.
No 128K/256K expansion follows this failure. [Results](Q2-RESULTS.md) retain all
values, failures, limits and plots; [implementation](Q2-IMPLEMENTATION.md) records
the exact runtime changes.

UD before/after the patch has 47/47 identical token/frontier files. Its median
PP changes by +0.22/+0.19/+0.30%, TG by +0.02/-0.19/-0.09%. The small measured
losses remain explicit; this is not a formal zero-margin no-regression pass.
Q2/UD physical prompts and generated trajectories match across these samples.
No independent full-model Q2 teacher or general model-quality score is claimed.

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
