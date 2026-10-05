<!-- SPDX-License-Identifier: MIT -->
# IQ2 live-store suppression on the compact producer

This new composition starts from the retained four-lane IQ2 provider,
1509.852296 PP / 25.20625148 TG. It applies the exact existing live-stage
predicate once during activation-slot preparation. Each K stage then omits
stores only for complete 16-row fragments that the matrix loop never reads.
Padding inside the final live fragment, weights, scale rounding, WMMA order,
barriers, epilogues and routing remain unchanged. The source derives from
independently fetched official Gufo at
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e` and keeps its notices.

The [source inventory](../config/q2-iq2-live-compose-source.json) verifies
1025 provider files with one changed file. Local production assembly changes
six IQ2 bodies and preserves all151 others. LDS, VGPR allocation, arithmetic
instruction counts, barriers and zero private bytes are unchanged. BN128 uses
two additional scalar registers. These facts do not establish runtime safety
or a performance gain. [Static accounting](../config/q2-iq2-live-compose-static.json).

The old live-stage component already preserves all102 output arrays and passes
51 independent checks in each of three arms, with105 retained timing samples.
Its four recorded-routing medians improve0.817–2.081% versus the final control;
two cases missed the historical advancement threshold. That original verdict
is preserved. The owner requests testing new compositions even when an old
component result is marginal. A read-only audit verifies318 saved artifacts
and their original fixture capsules; it does not rerun or qualify the new
composition. [Retained evidence](../config/q2-iq2-live-compose-retained-results.json).

The [frozen plan](../config/q2-iq2-live-compose-plan.json) admits only one new
original-model run: exact2048 input, chunk2048, capacity9216, tg128 with127
timed decode calls, C1, greedy, MTP off, one warmup and three measurements.
Saved fixed Q2 1443.672867 /25.09595499, UD1685.777092 /24.34174251 and the
1509.852296 parent are reused without rebuild or rerun. All samples and saved
logits must be reported; compilation/loading stay outside PP/TG.

Launcher113 guards and local source-capsule checks pass. The .157 host cohort
passes27/27 Debug and27/27 ASan/UBSan; six commands exit zero and seven
collected artifacts verify. [Host receipt](../config/q2-iq2-live-compose-host-results.json).
GPU model performance,
independent task quality and PP/TG curve parity remain unproven at preparation.
The `.157` GPU window requires a fresh handover, original-lease admission and
verified retirement. No full curve, Q4, cleanup, tuning or deployment is part
of this experiment. Core ABI, model state and metrics contracts are unchanged.

Reproduce only with a fresh admitted window and a new exclusive label:

```sh
python3 tools/q2-remote.py q2-counting-iq2-live-compose q2-iq2-live-compose-model-NEW --source-variant iq2-live-compose --rebuild-mmq
```
