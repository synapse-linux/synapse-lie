<!-- SPDX-License-Identifier: MIT -->
# Historical counting regression control

The retained 1439.264 Q2 and 1666.902 UD prefill rates use the exact-2048
counting workload and its direct-executor timer. The lower rates on the
canonical prose curve do not establish a regression on that older workload.
This bounded replay checks preservation of the historical result while keeping
the full canonical 0–128K curve as the optimization priority.

The tester is recovered byte-for-byte from the retained historical source
capsule: [harness identity](../config/q2-counting-harness.json),
[source](../experiments/counting-baseline/q2_model.cpp). Its marker translation
unit is also unchanged. All 1020 historical Q2 provider files and 1019 pristine
UD files match their retained source archives. The two additional arms use the
already measured ordered-IQ2 and mixed-map canonical providers through that
same frozen tester. No numerical kernel is edited for this replay.

All four arms use context 9216, chunk 2048, greedy generation, MTP off,
2048 physical prompt tokens and 128 outputs with 127 timed decode calls.
One warmup precedes three measured sessions; each 15-second pause stays outside
PP/TG timing. Every arm rebuilds MMQ. Rates, complete saved logits and token
sequences, replay differences, command exits and thermal telemetry are retained.
They cannot be combined with HTTP-curve rates or substitute for the broader
[acceptance contract](Q2-VALIDATION.md).

The new source-selection and frozen-tester guards pass 22/22 Debug and 22/22
ASan/UBSan on .157, with six zero command exits and seven verified artifacts.
These are host checks without a model or GPU lease. The fixed GPU order is old
paired norm/library Q2, ordered-IQ2 Q2, mixed-map Q2 and pristine UD. Fresh
coordinated admission is required before any of these model builds/runs.

[Four-arm plan](../config/q2-counting-regression-plan.json),
[host qualification](../config/q2-counting-regression-host-results.json).
No historical evidence is overwritten and no cleanup occurs on .157.
