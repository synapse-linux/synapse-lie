<!-- SPDX-License-Identifier: MIT -->
# Recheck of rejected test records

The owner requests revisiting candidate failures after questioning the Q8
format oracle, and asks to run only new candidates against already collected
controls. The exact2048 original-executor input and Q2/UD reference stay fixed.
The [classified inventory](../config/q2-rejected-test-reaudit.json) preserves
nineteen original reports with hashes, their failed fields/command exits,
and every existing result. This scan is not an exhaustive compile-error audit.

Those nineteen reports represent eleven candidate families, two host guard
failures and two baseline quality-status reports. Q8 has three failed
iterations of the same candidate. The library-norm and library-ragged families
each have both component and model reports. No count of nineteen distinct
false failures, independent improvements or composable gains is established.

The shared-Q8 candidate now completes the fixed model test despite the original
oracle rejection. All21 Q2 replay files, including full logits, are exact;
median PP1446.083285/TG25.10338822. The later
[unchanged-kernel saved-array replay](Q2-ORACLE-REPLAY.md) confirms an
initialization race in the independent fixture:40/40 ordered outputs match
every production byte while39/40 legacy cross-stream outputs corrupt codes.
The independent GPU kernel arithmetic stays exact. The fixture now orders
initialization on its nonblocking stream. Original failures remain immutable;
the Q8 performance increment is already in the measured compositions.

The HC norm/library tests use default-stream launches and device synchronization;
they do not share that nonblocking-oracle ordering. Their independent library
down checks may exceed the strict limits even when both whole outputs are exact.
The fixed norm model has eight changed logit files with unchanged greedy tokens;
those observed arithmetic changes do not disappear if an oracle is corrected.
The [fixed norm model report](Q2-NORM-FIXED-MODEL.md) remains retained.

Performance was already collected after numerical failures for several families:

| Family | Existing observation | Recheck relevance |
|---|---|---|
| Shared Q8 | New fixed-model21-file exact replay; small PP advantage | Completed candidate-only model recheck; diagnose format oracle separately |
| Fixed norm | Same fixed model already measured; logits change | New Q8+row+norm composition measured; exactly retains prior norm replay |
| Library norm | Both control/candidate independent down failures; complete timings saved | Both paired norm bodies and the2048 dispatch are already in fixed Q2 |
| Library ragged | Component and model reports exist | Entire library dispatch file is already exact in fixed Q2 |
| Ragged norm |2040row paired time−2.658% ordinary/−6.772% MoE;2048pairing already in executor | Its added dispatch does not add this benefit at the fixed2048point |
| Scaled input | Complete timings and changed output bytes saved | Original packing include is already exact in fixed Q2; quality remains separate |
| Scaled library | Component and model reports exist | Packing and original-F16 HC library route are already in fixed Q2 |
| Scaled row reuse | Complete component outputs exact; pack/down timings saved; native curves already recorded | New fixed-model Q8+row composition measured with all21 files exact to Q2 |
| Scaled tiles | Tile128regresses every measured routing; tile64 helps only highly shared routing | Revisit a bounded shape dispatch, not an unconditional tile change |
| HC sequence | Measured complete cycle+26.686% ordinary/+9.313% MoE | Oracle rejection did not prevent measuring the slowdown |
| Deferred HC norm | Measured+10.292% ordinary/−1.894% MoE; feedback outputs change | A MoE-only composition may merit testing; preserve true byte differences |

The [two new compositions](Q2-REAUDIT-COMPOSITION.md) measure1451.924906
and1452.143206 PP, with all samples retained and historical controls never
relaunched. The first is exact to Q2; the second reproduces the prior norm
logits exactly and adds no further observed numerical difference. This
recovers an observed0.57–0.59% over the fixed reference, not point parity.
The original nineteen-report inventory remains an immutable historical scan.

The [follow-up source audit](../config/q2-rejected-test-reaudit-progress.json)
verifies all nineteen original report hashes and both the1022-file fixed Q2
and1020-file retained HC-library providers. The scaled-input include, both
paired norm bodies and the entire HC-library dispatch file exactly reproduce
mechanisms already in the fixed reference. The latter still selects7526 for
the bounded original-F16 M320/K10240 projection. These are retained gains,
not additional gains lost solely through the nineteen recorded failures.
Source presence does not establish independent numerical acceptance.

The subsequent [original-F16 HC-down port](Q2-HC-DOWN-BK256.md) demonstrates
why numeric and performance results are retained independently: strict byte
replay fails but the bounded kernel saves9–13% of complete component time,
and its new model measures1477.969324 PP (+2.375639% versus fixed Q2).
No qualified controls are rerun. All128 greedy tokens match; logits change.
Recovered small-shape FP64 errors are roughly half the library's errors,
passing5/6 cases against0/6 under unchanged limits. Later unchanged-output
[BK128](Q2-HC-BK128.md) and [BN64](Q2-HC-BN64.md) fixtures restore printed
precision and recover 2048 FP64 errors: all aligned native cases pass the
original limits while library cases fail. The 97 ordinary native case remains
outside the peak limit. Both geometry families preserve all parent outputs but
regress complete-cycle performance. Numerical rejection did not suppress their
timing. This operator evidence does not establish independent model quality.
This is additional measured progress, not nineteen additive gains or full parity.
The [additive HC audit update](../config/q2-rejected-test-reaudit-hc-update.json)
binds these new reports without rewriting the original nineteen failures.

The [current recovery-status receipt](../config/q2-rejected-recovery-status.json)
verifies all nineteen original hashes again and binds the subsequent reports.
It classifies recovery of performance mechanisms, separately from numerical
acceptance or proof that an original rejection was false:

| Recovery disposition | Candidate families | Implication at the fixed point |
| --- | ---: | --- |
| Mechanism already in fixed Q2 | 5 | No additional gain can be counted again |
| New composition measured | 3 | Q8, row reuse and norm have retained full-model results |
| Complete performance measured and slower | 1 | HC sequence timings were collected despite rejection |
| Selective integration still pending | 2 | MoE-only deferred norm and routing-specific tile64 need new integration |

The four host/status records are outside this eleven-family count. The shared-Q8
race is the only confirmed false format-rejection family; no blanket verdict on
all nineteen reports is established. The current best PP 1477.969324 remains
12.327120% below UD 1685.777092, requiring 14.060357% more throughput from the
candidate to reach that rate. These numbers retain the original fixed input and
historical comparator, with all individual samples available in the model report.
Component improvements must not be added together as model throughput gains.
The [family CSV](figures/q2-rejected-recovery-status.csv) records each disposition.

The later [MoE-only deferred-norm composition](Q2-HC-MOE-DEFERRED.md) recovers
one of the two pending integrations and measures1496.830907 PP,1.276182% above
the saved best parent and3.682139% above fixed Q2. All128 tokens match while
logits change; independent task quality remains open. The original tester/input
and qualified references are reused. The [additive recovery update](../config/q2-rejected-recovery-moe-update.json)
verifies all19 original report hashes and changes the disposition counts to
five already-present families, four new measured compositions, one measured
regression and one pending routing-specific tile64 integration. It does not
rewrite the earlier recovery receipt or infer nineteen independent gains.
Fixed UD point parity is still unachieved; no full curve runs.

Further fixed-model tests remain pending for candidates needing new integration
or composition. Existing qualified controls will not be relaunched. Each new
candidate needs a source manifest, unchanged timer/input contract, fresh .157
lease admission and saved complete outputs, with performance measured separately
from independent quality. All source, failures and marginal candidates remain
retained; no context curve is admitted before fixed-point UD parity.
