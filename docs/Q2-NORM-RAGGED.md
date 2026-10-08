<!-- SPDX-License-Identifier: MIT -->
# Paired HC norm at the canonical diagnostic size

The current ordered-IQ2 provider uses the HC library consumer at 96..2048
rows but produces its F16 norm alongside F32 only at exactly 2048 rows.
The retained native canonical depth-zero request has 2040 physical tokens
and one prefill call. It therefore pays a separate narrowing pass.

The isolated patch broadens only that producer predicate to the existing
consumer interval, retaining the max-batch, geometry and gamma checks.
All 1019 other source files are unchanged, including arithmetic kernels,
library algorithm, IQ2 decode, PLE and buffer ownership. Previous half-buffer
identity is invalidated before writing and published only after a successful
paired dispatch. No persistent state, public ABI or timing contract changes.
[Source inventory](../config/q2-norm-ragged-source.json),
[patch](../experiments/q2-norm-ragged.patch).

The earlier exact-2048 norm experiment is already complete. This experiment
qualifies the missing ragged composition on the current ordered provider;
its aligned control cannot be counted as another model speedup.

## Bounded experiment

The existing component fixture now accepts `ragged`. One process alternates
paired and separate production through the actual HC library consumer at
2040 rows, plus the existing 2048 control. Both ordinary and MoE cycles use
five repetitions, sixteen calls per sample, alternating allocation roles and
100 MiB of rotating weights. GPU events cover the complete producer,
reference-only conversion and consumer. This is not model inference.

Correctness includes 96/97/129/2040/2047/2048 rows, small inputs, complete
output comparisons, scalar F16 rounding, independent FP64 checks, invalid
dispatch and unchanged inputs. Original numerical limits remain; inherited
library down-projection failures must remain visible even if output pairs
are exact. Library logging precision is restored outside timed loops so
small errors are no longer displayed rounded to two decimals.

[Frozen plan](../config/q2-norm-ragged-plan.json) selects a focused model test
only if both 2040-row cycles show useful paired savings with identical outputs
and passing norm checks. It does not admit the full curve or clear inherited
quality failures. Static executor and fixture syntax checks pass locally;
runtime tests belong on `.157` with fresh coordinated admission.

The first host cohort preserves CTest exit 8: an invalid source was correctly
refused by an earlier guard, whereas the new test expected this component's
specific diagnostic. The new scope guard now runs first. The failed cohort
is retained. The corrected cohort completes 22/22 Debug and 22/22 ASan/UBSan,
six zero command exits and seven verified artifacts on `.157`.
[Host qualification and preserved failure](../config/q2-norm-ragged-host-results.json).

## Escalation of measurement cost

The owner subsequently fixes the immediate gate to the retained exact-2048
comparison: Q2 1443.672867 against UD1685.777092 token/s. This supersedes the
earlier proposal to use a different canonical point or advance on a cumulative
checkpoint. Start with the affected component and its retained control, then
the fixed model comparison with identical input, settings and timers.
Do not launch another context curve until that comparison matches UD under
the [validation rules](Q2-VALIDATION.md#comparators-and-preparation). No
unrelated workload or baseline-free sweep while the gap remains. The final
target still requires Q2 at least as fast as UD at every required curve point.

## Completed focused component — 2026-10-04

The single `.157` component process completes at 14:39:36 UTC, about 43 seconds
after staging begins, including its build. All 1020 provider files, measured
fixtures against the passing host capsule and 64 result artifacts verify.
All 136 full-output hash pairs and 30 saved array pairs are exact, including
scalar F16 conversion. All fourteen independent norm checks pass.

Median complete-cycle times are microseconds; lower is faster.

| Rows | Cycle | Separate | Paired | Time change | Faster paired repetitions |
|---:|---|---:|---:|---:|---:|
| 2040 | Ordinary | 2983.454 | 2904.161 | -2.658% | 5/5 |
| 2040 | MoE | 3878.914 | 3616.249 | -6.772% | 5/5 |
| 2048 | Ordinary control | 2994.438 | 2895.596 | -3.301% | 5/5 |
| 2048 | MoE control | 3911.086 | 3648.786 | -6.707% | 5/5 |

All paired samples are below their corresponding unpaired sample ranges.
The frozen component criterion selects **one canonical model point** as the
next experiment. No full-model run or full context curve starts in this window.
The 2048-row benefit is already available in the original executor and is not
a new model gain. [All forty samples and verified outputs](../config/q2-norm-ragged-results.json).

Independent down-projection checks still fail in all 34 replays: maximum
relative RMS 3.33425e-5 and peak-scaled error 4.16361e-5 exceed the unchanged
2e-5 limits. Identical paired/control output means both paths have those
failures. The component retains command exits 0/0/1; exact output does not
clear the independent rejection or earlier model-quality gap. Peak observed
CPU/GPU temperatures are 69/56 C, with no thermal stop.

Collection initially rejects the already downloaded archive at the generic
128 MB bound. Saving the new 2040/2047-row outputs, in addition to small cases,
produces 1,106,304,168 uncompressed bytes. The collector now permits at most
1,120,000,000 bytes for this mode only; all prior limits and path checks remain.
Its focused boundary/path test passes on `.157`. The same downloaded archive
is revalidated and extracted locally, without another GPU run, download or
remote cleanup. Both failed collection and correction are retained.
[Collector check](../config/q2-norm-ragged-collection-host.json).

Release at 14:40:39 UTC verifies 298 prior process identities and 227 groups
retired, KFD empty, four original lease inodes free and six unchanged model
stat tuples. Main/remote active/release/ready records and the shared registry
retain closure, and core is notified. No GPU job, reservation, waiter or restart
remains. [Release](../config/q2-norm-ragged-window-release.json), SHA256
`97a6a71b33891f4680d1cd63c37295ac2ebe7d57ecafdc014461f3b1c6773642`.
