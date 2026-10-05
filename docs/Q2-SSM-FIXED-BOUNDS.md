<!-- SPDX-License-Identifier: MIT -->
# SSM checks implied by fixed dimensions

This prepared candidate retains the fixed M16384/K2560 specialization and
removes only row/K checks implied by the unchanged launch geometry. Token-tail
checks remain. Static instructions decrease from 3882 to 3864 versus fixed-M/K,
but 24 additional LDS loads appear; GPU improvement is not inferred.

The plan binds 90 unchanged fixtures, 14 manifests and a separate admission
helper. Host27 Debug/27 ASan gates are reused after raw artifact and fixture
verification. New component/model output will be compared with fixed Q2/UD,
construction parent1580 and the separately saved best1582.845143. No saved
model is rebuilt or rerun. The extra-reference analyzer reproduces all21
saved self-comparison files, keeps the earlier references unchanged and rejects
altered report/fixture bindings. All1027 candidate files verify.

Fresh .157 observation at22:38:24UTC confirms release81d7fcbb remains latest,
Core's original processes/groups are retired, its original CPU lease is free
and KFD is empty. New four-lease admission is required. No Q4, full-curve,
dependency, tuning, cleanup or other-model change is included.

[Source and bounds proofs](../config/q2-ssm-fixed-bounds-source.json),
[static comparison](../config/q2-ssm-fixed-bounds-static.json),
[frozen plan](../config/q2-ssm-fixed-bounds-plan.json),
[host reuse](../config/q2-ssm-fixed-bounds-host-results.json).
Actual commands are retained in
`evidence/q2-ssm-fixed-bounds-runtime-preparation/`.
