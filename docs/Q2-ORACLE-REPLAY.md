<!-- SPDX-License-Identifier: MIT -->
# Independent Q8 saved-array replay

On 2026-10-04 the `.157` replay confirms a stream-ordering defect in the independent format fixture. All 40 outputs initialized on the oracle's nonblocking stream are byte-exact to the original production Q8 arrays. The legacy default-stream initialization corrupts 39 of 40 outputs. The independent GPU kernel is byte-identical to R3; no arithmetic, tolerance or input changes.

The old fixture allocated and filled its oracle output after the production result had been copied back, then immediately launched the oracle on a nonblocking stream. The default-stream fill had no ordering dependency on that kernel. The paired replay uses identical allocations, guards and GPU computation, changing only whether initialization is on the kernel's stream. Repetition order alternates.

| Tokens | Pattern | Historical different bytes | Ordered exact / runs | Legacy exact / runs | Legacy different bytes, all 8 repetitions |
| ---: | ---: | ---: | ---: | ---: | --- |
| 96 | 0 | 0 | 8/8 | 1/8 | 0, 2616, 2457, 2250, 2437, 2320, 2476, 2248 |
| 97 | 1 | 0 | 8/8 | 0/8 | 723, 1092, 2332, 2395, 686, 2347, 2257, 1097 |
| 127 | 2 | 107 | 8/8 | 0/8 | 3908, 3852, 3665, 3950, 3687, 4325, 3889, 3620 |
| 129 | 0 | 0 | 8/8 | 0/8 | 3887, 49, 3954, 3871, 21, 3630, 3407, 3996 |
| 2048 | 0 | 64503 | 8/8 | 0/8 | 5853225, 5857660, 78956, 5857824, 73590, 5854716, 62706, 5854817 |

Every byte, including live codes, F32 scales and padded rows, is compared. All 32-byte guards stay exact and the saved input is rechecked after every shape. All 80 binary outputs and per-position mismatch counts remain in evidence. Some legacy 2048 runs lose almost the entire output; their differences are retained separately from the original short-prefix failure.

Configure/build/replay exits are 0/0/0. The 84 artifacts, 15 staged arrays, 10 frozen fixture files, original R3 oracle source, source capsules and binary/input pre/post hashes verify. .157 Debug and ASan/UBSan each pass 23/23. No model forward, production kernel, qualified inference comparator or PP/TG measurement is run.

Two preparation failures remain recorded: R1 rejected the 21 MB saved F32 array at the 16 MB source-file extraction cap; only that exact array now has a verified-size exception. R2 compiled successfully but its reader used 16-token logical tile sizing instead of 128-token physical allocation padding and exited before any GPU allocation or launch. Neither failure was a numerical result. The corrected R3 recipe and all three source capsules remain distinct.

The original producer fixture now supplies its nonblocking stream to oracle output initialization. The independent kernel remains unchanged. HIP syntax compilation passes locally; a separate .157 CPU Debug/ASan run passes 23/23 each and binds both modified fixture files. These host checks do not execute the HIP fixture. The standalone GPU replay qualifies the ordering correction; the complete original producer test is not rerun.

This recovers the shared-Q8 family's independent GPU format verdict at 127/2048. The historical CPU ideal-rounding diagnostics stay recorded. It does not invalidate every other operator oracle or turn 19 report records into 19 independent additive gains. Other source families primarily use the default stream for both initialization and kernels; reuse of the Output helper alone does not reproduce this cross-stream ordering error. A source observation is not a new GPU verdict for those families.

The Q8 producer is already included in the measured 1451.924906 PP exact composition and 1452.143206 PP norm composition. These rates and the fixed 1443.672867 Q2 /1685.777092 UD comparator do not change. The false rejection wasted investigation time, but this replay does not itself close the remaining prefill gap or qualify the complete context curve.

Release at 20:24:46.876665 UTC verifies 486 process identities and 377 groups retired, KFD empty, four original lease files free and six model stat tuples unchanged. Core receives the release. No Q2 GPU job, reservation, waiter, cleanup or model change remains.

[Frozen R3 plan](../config/q2-shared-q8-oracle-replay-r3-plan.json), [all 80 outputs and byte comparisons](../config/q2-shared-q8-oracle-replay-results.json), [fixture correction host receipt](../config/q2-shared-q8-oracle-fixture-fix-host-results.json), [verified release](../config/q2-shared-q8-oracle-replay-r3-window-release.json), [additive re-audit status](../config/q2-rejected-test-reaudit-oracle-update.json).

[Additional source binding](../config/q2-oracle-replay-source-binding.json) verifies all 1022 provider files against the original R3 capsule and the identical target numerical-flag inheritance.
