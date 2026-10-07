<!-- SPDX-License-Identifier: MIT -->
# Performance evidence excluding quality-reducing changes

The owner excludes quality-reducing optimizations from the performance goal.
Original GGUF weights alone do not establish unchanged inference quality:
intermediate precision, accumulation order and state representations also matter.
The lossy Q5 overlay is rejected and contributes no accepted gain.

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
The current fixed decode25.12414406 versus original25.09595499 is essentially
unchanged; no material C1 decode improvement at preserved original quality
is established. The30TG/1500-long-prefill goal remains open.

Sources: [shared Q8](Q2-SHARED-Q8-FIXED-MODEL.md),
[raw prefetch](Q2-IQ2-RAW-PREFETCH.md),
[live-stage composition](Q2-IQ2-LIVE-COMPOSE.md),
[half-storage differences](Q2-DOWN-HALF-STORAGE.md),
[fixed and full-prefix observations](Q2-FULL-PREFILL128.md).
New experiments must record both their own arithmetic changes and inherited
quality limitations; an exact child cannot remove an unqualified parent change.
