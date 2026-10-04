<!-- SPDX-License-Identifier: MIT -->
# Fixed-shape norm: exact2048 complete-model comparison

The owner explicitly requests the full model now after the component rejection.
This admits an exploratory performance measurement; it does not change the
failed component gate or numerical thresholds. The candidate remains exactly
the source already measured in [the component](Q2-NORM-FIXED-SHAPE.md).

Four sequential original-weight arms on `.157` compare the fixed mixed-map Q2
provider, fixed-shape norm candidate, original Q2 again and pristine UD. Every
arm rebuilds all MMQ sources. The [frozen plan](../config/q2-norm-fixed-model-plan.json)
binds sources, fixtures, host qualification and the existing reference.

The original direct-executor tester is unchanged: exact2048 physical input,
context capacity9216, chunk2048, C1 greedy, MTP off,128 outputs and127 timed
decode calls, one warmup and three identical-input measurements, with15-second
pauses outside timers. Input SHA256 remains
`75343e606f5b815fe01f69ddc6ce50a997e2de96d8a20304a82a7f24f1180b35`.
The historical measured reference remains1443.672867 Q2/1685.777092 UD token/s;
fresh controls will be shown alongside it. No new context curve is admitted.

Host launcher checks pass22/22 Debug and22/22 ASan/UBSan on `.157`, with six
zero command exits and seven verified artifacts. The scoped candidate mode
requires its exact provider and full MMQ rebuild; native-curve, point-only,
detach and unrelated provider combinations are rejected before staging.
[Host receipt](../config/q2-norm-fixed-model-host-results.json).

Saved input/output tokens and complete logits will distinguish exact replay
from arithmetic differences. KL at later decode frontiers is meaningful only
when token histories match. Greedy agreement alone does not qualify quality.
The existing independent numerical rejection remains. Sources and evidence
are persistent; `.157` cleanup, tuning and deployment are outside this run.
