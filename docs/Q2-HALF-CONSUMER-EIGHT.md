<!-- SPDX-License-Identifier: MIT -->
# Eight-value half-input expert consumer

One new candidate derives from the measured1570.106384 PP /25.18915597 TG
provider. It changes only the MoE weighted-sum part of
`HcCombineMoeHalfDeferredNormKernel`: eight hidden values per lane replace
four, leaving every per-value expert FMA chain and shared-expert FMA ordered.
At hidden2560, outer passes change from256/256/128 to256/64 live lanes.
Aligned inputs use one128-bit half payload load; the original Load4 operations
remain the fallback for four-byte-aligned inputs. Existing four-value loads
already compile to64-bit operations. Subsequent HC/residual/norm source,
producer, dispatch, output representation and allocation are unchanged.

The source derives from independently fetched MIT Gufo pin
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e` and the retained LIE lineage.
No sibling DS4/CachyOS source or artifact is imported. The literal measured
parent consumer is included only in the new focused component fixture.

Local compilation finds160 instruction/operand/resource-exact kernel bodies
and one changed consumer. Consumer VGPR84, SGPR32, LDS10368 and zero private
bytes remain unchanged; static instructions rise1729 to1763. This is not
runtime evidence. Alignment branching and longer value ownership can offset
the reduced outer-loop count. An initial CMake wiring script exits1 on a
missing anchor after wiring the launcher; its receipt is preserved and the
remaining CMake change is completed separately.123 launcher guard cases pass.

[Source](../config/q2-half-consumer-eight-source.json),
[static comparison](../config/q2-half-consumer-eight-static.json),
[frozen plan](../config/q2-half-consumer-eight-plan.json),
[staging](../config/q2-half-consumer-eight-staging-results.json).

## Bounded qualification

The new component checks35 shapes with three deterministic input rotations:
16/17/33/129 tokens,1/2/10/32 selected experts, aligned16 and aligned4-only
input bases; additional2048-token shapes use2/10/32 experts. Gate stride1/5
and injection parts1/3/10 are covered. Expert allocations end at the final
valid half. Inputs include signed zero, small/subnormal halves and largest
finite half values. Every residual, norm scale and normalized half output is
compared with the literal parent and an unchanged F32 consumer on exactly
expanded halves. Guards/poison, finite values and input immutability are checked.
These are differential operator checks, not independent task quality.

Only the three2048-token shapes are timed: complete weighted combine,
shared expert, HC/residual, scales and F16 norm; alternating parent/candidate,
two warmups plus five measured samples, three rotating input sets exceeding
32MiB. Input upload/expansion and identical residual reset are outside both
component timers. No unchanged down-producer sweep or old cohort is rerun.
Safe numerical/timing rejection does not cancel the new original-model test;
guard corruption or unwritten output stops further device work.

The original direct executor retains the exact2048/tg128 input, C1 greedy,
MTP off, capacity9216/chunk2048, one warmup and three measured samples.
Saved Q2 PP1443.672867, UD1685.777092 and parent1570.106384 remain fixed;
compilation/loading are excluded. GPU tests run only on .157 following fresh
ownership admission. No Q4, full curve, cleanup, tuning or dependency install.

Host-only .157 checks pass27/27 Debug and27/27 ASan/UBSan, six commands exit0 and seven artifacts verify. The capsule checks all70 frozen fixtures; no GPU/model evidence is implied. [Host result](../config/q2-half-consumer-eight-host-results.json). GPU/model results are pending at preparation. Exact replay against the half-storage
lineage would still not close its inherited independent task-quality gap.
The complete requested context/concurrency curve and UD parity remain open.
