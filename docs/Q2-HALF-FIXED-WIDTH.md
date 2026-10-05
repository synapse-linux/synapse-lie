<!-- SPDX-License-Identifier: MIT -->
# Fixed integer geometry for the half-input expert consumer

The wrapper already accepts hidden2560 and streams4 only, but its consumer
kernel still uses the runtime hidden argument for row/stream indexing and
bounds. This isolated candidate makes those integer operations constant2560.
It retains the runtime float(hidden) normalization divisor to preserve the
original floating operation. The eight-value expert accumulation, shared
expert FMA, residual update, square contraction, wave reduction, ordered total,
rsqrt and normalized F16 rounding keep their source arithmetic. Wrapper,
producer, dispatch, output representation and allocation are unchanged.

The measured parent is1571.716479 PP /25.20732109 TG. Source derives from
independently fetched MIT Gufo pin f783fedb9bea2ec7de941f6da4e02f4a4596b29e
and the retained LIE lineage; no sibling DS4/CachyOS source or artifact is
imported. The literal parent consumer is included only in the new component.

Local assembly comparison finds160 other kernel bodies instruction/operand/
resource exact. The changed consumer has1763 to1093 static instructions
(-38.003403%), VGPR84 to91, SGPR32 to26, unchanged LDS10368 and zero private
bytes. These counts are not dynamic timing. Constant propagation can change
scheduling and register demand, so complete GPU outputs and model timing
remain necessary.125 launcher guard cases pass.

[Source](../config/q2-half-fixed-width-source.json),
[static comparison](../config/q2-half-fixed-width-static.json),
[frozen plan](../config/q2-half-fixed-width-plan.json),
[staging](../config/q2-half-fixed-width-staging-results.json).

## New candidate qualification

The new fixture retains the previous complete-consumer protocol but binds the
new candidate and literal1571 parent.35 shapes/three rotations yield105 checks
of all residuals, scales and half-normalized outputs against parent and the
unchanged F32 consumer on exactly expanded halves. Tokens16/17/33/129 cover
experts1/2/10/32 and aligned16/aligned4-only input bases; additional2048-token
shapes cover2/10/32 experts. Gate stride1/5, injection parts1/3/10, signed zero,
subnormal and extreme finite halves, allocation-end tails, output guards/poison
and immutable inputs remain covered. This is differential operator evidence,
not an independent task-quality oracle. Old cohorts are not rerun.

Only three2048-token shapes are timed, with two warmups/five measured samples,
alternating arms and three rotated expert inputs exceeding32MiB. Complete
MoE/shared sum, HC/residual, scales and half norm are timed; upload/expansion
and identical residual reset are outside both arms. Safe numeric or timing
failure does not suppress new model performance. Guard/unwritten-output
failure stops further device work.

Original direct-executor exact2048/tg128 input/timers remain fixed: C1 greedy,
MTP off, capacity9216/chunk2048, one warmup/three measured samples. Saved
Q2 PP1443.672867, parent1571.716479 and UD1685.777092 are reused. Loading and
compilation stay outside model PP/TG. .157 GPU admission is fresh; no Q4,
full curve, cleanup, tuning or dependency installation is scheduled.

Host-only .157 Debug27/27 and ASan/UBSan27/27 pass; six command exits0 and seven artifacts verify. All72 fixtures and the host source capsule are bound. [Host results](../config/q2-half-fixed-width-host-results.json). GPU/model results are pending at preparation. The inherited F16 task-quality
gap and full context/concurrency parity remain open even if parent replay is
exact. No production promotion or predicted gain is claimed.
