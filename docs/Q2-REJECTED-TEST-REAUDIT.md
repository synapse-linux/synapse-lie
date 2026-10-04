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
median PP1446.083285/TG25.10338822. The independent GPU oracle's unwritten0xff
pattern has a possible initialization race: guarded allocation calls default
stream hipMemset immediately before a nonblocking stream writes its codes.
The GPU race hypothesis remains untested. Current official HIP implementation
allows device-memory memset to be asynchronous; this supports investigating
an explicit stream dependency, not declaring the installed runtime faulty.
[Official runtime source](https://github.com/ROCm/clr/blob/develop/hipamd/src/hip_memory.cpp).

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
| Fixed norm | Same fixed model already measured; logits change | Retain marginal candidate; composition remains untested |
| Library norm | Both control/candidate independent down failures; complete timings saved | Recheck the independent arithmetic contract and retained model evidence |
| Library ragged | Component and model reports exist | Keep actual outputs and historical timing scope distinct |
| Ragged norm |2040row paired time−2.658% ordinary/−6.772% MoE;2048pairing already in executor | Its added dispatch does not add this benefit at the fixed2048point |
| Scaled input | Complete timings and changed output bytes saved | Actual changed arithmetic needs model replay and quality evidence |
| Scaled library | Component and model reports exist | Check composition and what is already in the fixed reference |
| Scaled row reuse | Complete component outputs exact; pack/down timings saved; native curves already recorded | A fixed-input model composition can test the remaining marginal mechanism |
| Scaled tiles | Tile128regresses every measured routing; tile64 helps only highly shared routing | Revisit a bounded shape dispatch, not an unconditional tile change |
| HC sequence | Measured complete cycle+26.686% ordinary/+9.313% MoE | Oracle rejection did not prevent measuring the slowdown |
| Deferred HC norm | Measured+10.292% ordinary/−1.894% MoE; feedback outputs change | A MoE-only composition may merit testing; preserve true byte differences |

Further fixed-model tests remain pending for candidates needing new integration
or composition. Existing qualified controls will not be relaunched. Each new
candidate needs a source manifest, unchanged timer/input contract, fresh .157
lease admission and saved complete outputs, with performance measured separately
from independent quality. All source, failures and marginal candidates remain
retained; no context curve is admitted before fixed-point UD parity.
