<!-- SPDX-License-Identifier: MIT -->
# HC library dispatch for incomplete prefill batches

The original-C17 comparison confirms Q2 at 1362.819 prefill token/s versus UD
1663.579 for 2042 physical prompt tokens: an 18.079% deficit. The current
experimental library consumer and paired producer are restricted to exactly
2048 rows. A 2042-row request and a 2047-row final chunk use the native HC-down
consumer. This source fact identifies an unmeasured dispatch boundary; it does
not explain the entire model deficit or establish a speedup.

This next component experiment extends only the existing HC-down library
selection to **96 through 2048 rows**, M320/K10240, F16 weights/input and F32
output. It still requires algorithm 7526 to pass the installed library's
support check with zero workspace. Selection still examines the original
sixteen heuristic results; refusal means the requested algorithm is unavailable
through this selection policy, not proof that no library algorithm could work.
Refused shapes are reported explicitly, with no silent substitution or live
tuning. Algorithm identity remains
installation-specific. All 1019 other provider files are unchanged, including
the executor, native GPU kernels and the producer's n2048 restriction.

The [source manifest](../config/q2-hc-library-ragged-source.json) and
[two-predicate patch](../experiments/q2-hc-library-ragged.patch) preserve the
measured parent. This is a component-only source; its remote guard refuses
model runs, MMQ reuse options, persistent launch and other experiment modes.
No public C ABI, state format, allocation or reactive-scheduling policy changes.
Scalar decode is outside the new dispatch range and receives no speed claim.

## Controlled experiment

The same binary compares the original native consumer with the actual
`BlasLt::Gemm` candidate. Both paths retain the same original F32 norm producer
and separate narrowing pass. Broadening the paired producer would be a separate
change, considered only after this consumer comparison.

- Ordinary and MoE correctness cases use 96, 97, 129, 502, 2042, 2047 and
  2048 rows, with an additional tiny-input case at 2042: 16 cases in total.
  Native and library outputs each receive the original sampled FP64 down
  check; full residual/norm/F16 arrays must agree. Both producers receive
  independent full-row FP64 norm checks. Limits remain 2e-5.
- Every output has guards and complete finite/write checks. All case down
  arrays are saved, with complete hashes of intermediate arrays. Original
  inputs and weights are checked unchanged.
- Repeated identical F16 rows at 97, 2042, 2047 and 2048 expose differences
  caused by a row's position. Every output row is compared and saved for both
  consumers. Position drift remains an explicit failure.
- Complete ordinary/MoE norm → narrowing → down cycles are timed at 502,
  2042, 2047 and 2048 rows. Each uses sixteen original-layout weight matrices
  occupying 100 MiB, matching production `hipMalloc` placement. Both paths
  and allocations warm first. Five pairs alternate order and allocation
  roles; each arm contains sixteen cycles timed with HIP events.
- Copies, plan creation and output validation stay outside timing. Numerical
  failures retain exit 1 while timings continue; runtime/resource failures
  stop the experiment. There are no substituted successful golden values.

At n2048 the current model already uses the library plus paired producer.
The native comparison there is a control, not evidence of a new model gain.
Ragged library arithmetic can differ from native arithmetic, including by
row position. Existing library/scaled operator failures and Q2 KL rejection
remain; a component speedup cannot clear them.

The bounded saved down arrays occupy 62,054,400 bytes if all shapes are
supported, within the unchanged 128 MB collection bound. The runner allows
300 seconds for this expanded component only; thermal and lease policy are
unchanged. No dependency installation or hardware tuning is involved.

## Current validation and next gate

Strict library and HIP host-only fixture syntax, changed-file formatting,
CMake configuration and the five-command build-graph dry run pass locally.
The complete 1020-file source reconstructs through the patch with zero fuzz.
No new binary has been linked or run. The first strict fixture syntax check
found two unused helpers inherited through the existing fixture includes;
explicit address references resolve the warning without running those helpers.
The failed and corrected commands are retained. The shared upstream formatter
retains the same five untouched failures as the measured parent, with identical
logs. [Static evidence](../config/q2-hc-library-ragged-static.json) distinguishes
these checks from pending runtime qualification.

Core owns the next `.157` campaign (`gpu-vision-bec-r1`). Its latest observed
arm was terminal at 20:16:49 UTC; that does not release the enclosing window.
Core subsequently explicitly confirms that it retains the window for the
remaining SSD and reactive checks. Q2 has no GPU job, reservation, waiter or restart. Host CTest/ASan and this
component require core's verified handover and fresh original four leases.
The [runtime plan](../config/q2-hc-library-ragged-plan.json) records that boundary.

After handover, use fresh labels and preserve actual exits, including exit 1:

```sh
python3 tools/q2-remote.py cpu q2-hc-library-ragged-host-r1
python3 tools/q2-remote.py collect q2-hc-library-ragged-host-r1
python3 tools/q2-remote.py hc-library-ragged-bench q2-hc-library-ragged-component-r1 --source-variant hc-library-ragged
python3 tools/q2-remote.py collect q2-hc-library-ragged-component-r1
python3 tools/analyze-q2-hc-library-ragged.py evidence/q2-hc-library-ragged-component-r1 --host evidence/q2-hc-library-ragged-host-r1 --output config/q2-hc-library-ragged-results.json
```

The analyzer checks original leases, source/fixture identities, all collected
artifacts, both host configurations, complete output arrays, numerical verdicts,
position drift, every sample and the alternating order. It reports numerical
rejection separately from any measured timing benefit. A useful complete-cycle
result is required before admitting a model comparison. Such a comparison must
reuse the unchanged original-C17 Q2/UD benchmark and retained physical inputs;
the historical 26.049 UD decode reference is not lowered.

Official Gufo pin remains `f783fedb9bea2ec7de941f6da4e02f4a4596b29e`.
Upstream licenses/notices are preserved; first-party delta and fixture are MIT.
No antirez engine or sibling-workspace source/artifact is imported. Q2/UD parity
and numerical/task-quality acceptance remain unproven.
