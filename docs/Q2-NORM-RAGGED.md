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

Start with the affected component and one control. Next use a single
canonical `synapse-lie-bench` point, with unchanged Q2 before and after and a
matched UD observation. Keep the same prose, calibration, sampling and timing;
do not substitute the historical counting prompt. A medium-depth point is
added only for a context-dependent hypothesis. Repeat to resolve observed
noise, not by default. Full 0..128K qualification follows a representative
model result that closes the UD deficit or a justified cumulative checkpoint.
The final target remains Q2 at least as fast as UD at every required point.
