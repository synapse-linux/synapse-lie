<!-- SPDX-License-Identifier: MIT -->
# Last fixed-point HC-down attempt

The owner requests that fixed-point Q2/UD parity be paused after this last
attempt. Subsequent optimization prioritizes prefill and decode through128K,
favoring implementation effort and meaningful complete-request contribution.
Retained1587.893545 PP/25.12414406 TG and fixed UD1685.777092/24.34174251
remain historical references. No benchmark input or timer is changed.

The private numerical include derives from the retained original-F16 HC-down
port. It removes weight LDS storage and loads each consumer wave's original
F16 fragments directly. BM64/BN32/BK256, activation staging, two ascending K16
accumulation chains, final addition and dispatch bounds remain. Logical weight
loads double; activation loads do not. This is a traffic tradeoff to measure,
not an assertion that lower resource use yields speed.

Device compilation succeeds, preserving all164 original device bodies and
resources exactly. The one added body uses16896 LDS bytes and86 descriptor
VGPRs, with zero scratch. No model selector or allocation is introduced.

The new component measures HC-down followed by the existing SiLU(dot/4) and
F16 narrowing. Four shapes96/97/129/2048 include tiny and cancellation inputs.
Eight independent original-F16 matrices span50MiB, with separate output states
for every arm/rotation. Every timed output is checked before overwrite.
The160 complete pairs and160 sampled FP64 reports retain the original2e-5
limits and exact F16 narrowing boundary; finite disagreements retain timing.
Guards, nonfinite/unwritten outputs or device failures stop with exit2.
Completed monotonic wall time and raw HIP-event validity remain separate.
Normalization producer and model cache history are outside this component.

The initial source review caught a test-formula placement error before any GPU
execution: the production kernel applies scale before SiLU. The corrected FP64
formula computes SiLU(dot/4). Both local compile receipts and the initial source
are retained; no GPU failure or threshold relaxation is hidden.

Actual .157 host tests pass39/39 Debug and39/39 ASan/UBSan, all six exits0,
and all seven artifacts are collected. Only the new component awaits fresh
checkpoint/admission. The offline freezer is bound separately as preparation
tooling; all tested runtime files remain exact to the host capsule.

[Source generator](../tools/prepare-q2-hc-down-direct-weight.py),
[compiler evidence](../config/q2-hc-down-direct-weight-static.json),
[fixture](../tests/q2_hc_down_direct_weight.hip),
[provenance](../third_party/gufo/LIE-Q2-HC-DOWN-DIRECT-WEIGHT.md).
