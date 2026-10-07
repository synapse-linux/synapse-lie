<!-- SPDX-License-Identifier: MIT -->
# Performance evidence excluding quality-reducing changes

The owner excludes quality-reducing optimizations from the performance goal.
Original GGUF weights alone do not establish unchanged inference quality:
intermediate precision, accumulation order and state representations also matter.
The lossy Q5 overlay is rejected and contributes no accepted gain.

The initial HC model comparisons also have a build-mode confound, discovered
after the original128K follow-up: saved controls are RelWithDebInfo, while
the new fixed/native HC binaries are Release. The compiler revision matches,
but147 common device functions change size and132 change recorded resources.
Exact replay remains valid numerical evidence; model timing deltas cannot yet
be attributed to HC alone. The component's same-build paired result is separate.
A newly rebuilt matching candidate preserves every common device function's
size/resources;907 of920 functions are byte-exact and the remaining13 differ
only in address literals in disassembly. Its original128K run now completes
with all four responses/token streams exact:1335.257764 PP (+1.860068%) but
24.825466 TG (-2.046807%) versus saved1310.874605/25.344213. The native decode
benefit is not confirmed with matching builds; do not promote it as an overall
improvement. One observation and eight output calls do not establish sustained
performance or inherited task quality. No reference is rebuilt or rerun.

The current1587.893545 fixed-point prefill and1310.874605 full128K prefill
are experimental observations, not demonstrated quality-preserving gains
over the original fixed-Q2 baseline. Their lineage includes F32-to-F16
expert-output storage and earlier numerical changes whose task-quality
qualification remains open. The storage trial itself changes eight saved
logit files (maximum parent KL0.002693241666), despite identical greedy tokens.
That difference does not prove task degradation; identical tokens do not
prove unchanged quality. Preserve all existing measurements and references.

Some individual changes do have exact differential replay evidence:

| Isolated comparison, fixed2048/tg128 | Prefill token/s | Observed change | Numerical evidence and limit |
|---|---:|---:|---|
| Shared-Q8 vs original fixed Q2 | 1443.672867 to1446.083285 | +0.166964% | All21 saved files, including logits, exact to fixed Q2. Marginal historical timing difference, repeatable gain unproven. |
| IQ2 raw prefetch vs compact parent | 1498.799455 to1505.152258 | +0.423859% | All21 parent files exact. Earlier inherited differences to original fixed Q2 remain. |
| IQ2 live-stage composition vs four-lane parent | 1509.852296 to1511.097261 | +0.082456% | All21 parent files exact. Overlapping timing ranges and inherited numerical differences remain. |

These gains must not be added or treated as an end-to-end quality acceptance.
The previously retained fixed decode25.12414406 versus original25.09595499
was essentially unchanged. The initial HC scalar rate increases below are
observed with the build confound documented above; the matching128K result
does not confirm an overall C1 improvement. No child removes the parent's
inherited quality qualification gap.
The30TG/1500-long-prefill goal remains open.

Sources: [shared Q8](Q2-SHARED-Q8-FIXED-MODEL.md),
[raw prefetch](Q2-IQ2-RAW-PREFETCH.md),
[live-stage composition](Q2-IQ2-LIVE-COMPOSE.md),
[half-storage differences](Q2-DOWN-HALF-STORAGE.md),
[fixed and full-prefix observations](Q2-FULL-PREFILL128.md).
New experiments must record both their own arithmetic changes and inherited
quality limitations; an exact child cannot remove an unqualified parent change.

The new [scalar HC up/mix component](Q2-HC-SCALAR-UP-MIX.md) supplies a
quality-preserving local result:64 byte-exact comparisons,50 independent
checks and19.408613% less operation time with injection (4.764143% without).
It changes no weight or intermediate precision. Its subsequent original-model
trial measures26.24707057 decode versus saved25.12414406 (+4.469512%), with
all21 saved parent files and nine internal replays byte-exact. This is a
quality-preserving measured increment relative to that parent on this workload.
It does not qualify the inherited earlier numerical changes. Prefill in the
same new run is1571.380247 versus saved1587.893545 (-1.039950%). The native32K
follow-up now reaches26.825569 decode versus same-sequence saved26.250492 /
26.253731 (+2.19%/+2.18%), with all four streamed responses/token sequences
exact. Its prefill1419.137366 versus1426.532712/1422.901121 regresses0.52%/0.26%.
These are eight output calls, not sustained TG128; native128K remains open.
Both binaries and all earlier references remain retained.
