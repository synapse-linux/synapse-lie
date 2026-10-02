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
