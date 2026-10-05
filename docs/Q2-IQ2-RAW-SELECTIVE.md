<!-- SPDX-License-Identifier: MIT -->
# Best IQ2 raw prefetch with retained selective Q2 down

This new composition combines the measured IQ2 raw-prefetch base at
PP1505.152258/TG25.15493858 with the preserved C17 Q2 down48/64 selector.
That selector previously measured PP1497.606050 on the earlier MoE parent
PP1496.830907. Its marginal result remains preserved; its throughput change
cannot be added to the later IQ2 improvement without a model measurement.

The selector assigns a complete expert to64 rows only when its16-padded
bucket has at least256 rows and its reserved64 rows do not exceed its
reserved48 rows. Other experts retain48. Both down spans fit the existing
map reservation; the original IQ2 gate/up spans follow them unchanged.
Activations, original quantized weights, scaled F16 packing/inverse scales,
K accumulation, SwiGLU and per-output routing remain unchanged. No GPU
allocation, stream, model-state precision or public ABI/metrics change is added.

All five changed provider files are byte-exact to the previously measured
selector composition: executor source/header, provider CMake and the two C17
policy files. All117 numerical HIP/MMQ source files are byte-exact to the
current best IQ2 parent. The1027-file inventory combines those two retained
sources. These are source-identity checks, not another assembly or GPU result.
Local executor/C17 syntax and93 matched-launch guards pass. Source generation,
patch and provider inventory remain durable inside this worktree.

The existing C17 fixture checks exact capacities, live/padded row coverage,
disjoint width ownership, sentinel guards and untouched outputs on rejection.
The existing scaled-tile GPU component and its recorded independent numerical
failures are reused without a rerun or tolerance change. The new model runs
after a fresh coordinated admission regardless of safe numerical rejection.
There is no new component cohort or qualified Q2/UD control build/run.

The comparison remains original exact2048/tg128,127 timed decode calls,
capacity9216/chunk2048,MTP off,one warmup and three measured sessions, with
15-second waits outside PP/TG. Fixed Q2 PP1443.672867/TG25.09595499, fixed UD
PP1685.777092/TG24.34174251 and the saved best IQ2 parent are reused. Source
records are emitted only after the original complete event at executor
teardown; map preparation and bounded record copies remain in actual PP time.
Independent task quality and complete context-curve parity remain open.

The frozen plan binds40 fixtures and seven manifests. Local capsule staging
verifies all40 fixture files and1027 provider files and stops before SSH.
The first launcher-edit attempt failed locally because its text anchor also
matched a nested branch; it wrote no launcher/provider files. The corrected
indentation-delimited edit passes93 guards and staging. That preserved
preparation failure is neither a GPU fault nor a model rejection.

Fresh core handover confirms no root .157 GPU job/build/eval/client/lease/
waiter/reservation/restart/interleaving after the previous Q8 K16 release.
This is not admission; the new checkpoint still requires the bounded helper's
lease/KFD/process/registry/model-stat/thermal checks. No deployment, dependency
installation, tuning, cleanup or full context curve is authorized by this plan.

New .157 host qualification passes25/25 Debug and25/25 ASan/UBSan with six
zero command exits. Seven artifacts,40 frozen fixture files and the1020-file
CPU provider capsule verify. This gate opens neither the model nor the GPU;
it is not model performance or independent numerical quality evidence.

[Source inventory](../config/q2-iq2-raw-selective-source.json),
[composition patch](../experiments/q2-iq2-raw-selective.patch),
[source identity/syntax checks](../config/q2-iq2-raw-selective-static.json),
[local capsule receipt](../config/q2-iq2-raw-selective-staging-results.json),
[host qualification](../config/q2-iq2-raw-selective-host-results.json),
[frozen plan](../config/q2-iq2-raw-selective-plan.json),
[prior selector measurements](Q2-SCALED-SELECTIVE.md) and
[retained IQ2 parent](Q2-IQ2-RAW-PREFETCH.md).
