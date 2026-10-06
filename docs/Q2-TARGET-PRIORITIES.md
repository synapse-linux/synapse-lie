<!-- SPDX-License-Identifier: MIT -->
# Q2 fixed-point priorities

Keep the saved comparison: **1585.308983 PP / 25.16079073 TG** for Q2,
**1685.777092 PP / 24.34174251 TG** for UD. The original tester uses exactly
2048 prompt tokens,128 outputs/127 timed decode calls,capacity9216/chunk2048,
C1 greedy,MTP off,one warmup/three measured requests and15-second cooldowns
outside timers. Required PP increase is6.337447%, equivalent to76.991736ms
less prefill. The fixed1443.672867 Q2 reference remains available. No new
performance result changes these values or the eventual whole-curve target.

The saved1571 profile supplies historical cost attribution. It is not a
fresh profile of1585 and does not predict removable time. Rank candidates by
the cost of an actually active path, a specific change to redundant work and
the cost of implementing it; no numerical success probability is claimed.

| Priority | Active historical cost | New mechanism | Current evidence |
| --- | ---: | --- | --- |
| Q2 down register palette |161.558060ms|Remove wave-private weight/affine LDS staging; form the exact half palette once|Isolated production provider and guarded fixture prepared; GPU measurement pending|
| HC mix/injection reuse |39.548835ms injection,96 calls|Compute ordered injection dots while normalized inputs are already loaded by mix; keep the original reduction in the second kernel|Three private compiler probes; no runtime fixture or production selector yet|

The down would need to save47.655769% of its historical region to cover the
whole77ms budget alone. HC injection alone is smaller than that budget even
under the impossible assumption of eliminating its complete cost. Composition
is therefore a plausible route, but neither static resources nor isolated
component gains establish full-model speed. The5.090460ms inter-kernel gap
does not support obtaining77ms from reactive launch scheduling alone.

## Down candidate ready for the first measured trial

The [1028-file source](../config/q2-down-register-palette-source.json) derives
only from retained `ssm-fixed-bounds`, at the recorded official Gufo lineage.
Only BM128/BN48/BK2 changes. A [static audit](../config/q2-down-register-palette-static.json)
verifies161 other production bodies and resources exact against saved ISA:
LDS18560→8320,VGPR96→102,SGPR36→38,private scratch0,instructions2641→2699,
WMMA12/barriers8 unchanged. More registers/instructions are a real tradeoff;
the completed IQ2 register-stage experiment regressed despite lower LDS.

The [fixture](../tests/q2_down_register_palette.hip) compares the literal parent
and production selector across123 full-output pairs and70 alternating timing
samples. It covers BN48 tails, unchanged BN16/64 controls,inverse scales,
three weight rotations beyond32MiB and captured counts from layers0/3/22.
Numeric differences keep exit1 and timing; invalid guards, unwritten outputs
or device faults stop dependent GPU work. Only the new candidate is built/run;
saved Q2/1585/UD controls are reused and original model timing stays unchanged.

The earlier host capsule passed33/33 Debug and33/33 ASan/UBSan on `.157`.
It does not qualify the current phase-helper changes. A new host34+34 capsule
and new r2 labels are required before freezing the new plan. Five prepared
phase tests cover missing/stale scope, transport failure preventing launch,
preserving existing failed evidence and exact successful sequencing. They
have not been run while `.157` is unreachable; syntax parsing is not a pass.

## HC reuse: source and ISA, not measured performance

The [v2 probe](../experiments/q2-hc-inject-reuse-draft-v2.inc) extends private
copies of the current raw-F16/raw-Q8 and deferred-norm mixer bodies. Each
normalized float4 supplies four output dots. Saved injection ISA starts each
dot with one rounded MUL and follows with15 ordered FMAs; the probe preserves
that order. A second kernel retains the original wave sums, eight-wave block
sum, three chunk partials and output layout. It uses no atomic summation or
alternative reduction tree. Runtime equality still needs a complete replay.

Compact dots require20MiB at2048 tokens. Existing `down_e` is allocated as
`slots*hidden` F32 and has adequate capacity; it is a proposed borrowed workspace,
not a new allocation or an implemented executor lifetime. The previous combine
must finish its last expert-output read before reuse, and the dot reducer must
finish before the next MoE writer. Input aliases, pending expert outputs and
failure handling need qualification before production integration. Ordinary
and deferred norms/residuals remain separate and their caches are not replaced.

Device-only compilation passes. The [ISA audit](../config/q2-hc-inject-reuse-draft-static.json)
verifies all162 existing bodies/resources exact and adds three private probes.
Both producers remain at242VGPR/24576LDS/0private,16WMMA/26barriers. SGPR and
producer instructions increase: raw3473→5234,deferred3807→5610. Injection's
standalone405/492-instruction kernels are replaced by a178-instruction reducer
plus the work moved into mix. The whole sequence must be timed: extra dot
traffic and injection-weight reads could outweigh removal of normalized reads.
The initial uncompiled include retained two duplicate parent dispatchers;
source inspection excludes them in v2 before the first compiler invocation.

## Execution status and next measurements

Reconnection at04:09UTC succeeds. Original Core CPU lease/closure, retired
processes/groups, empty KFD and the previous GPU-release registry event
revalidate. Fresh host34+34 passes04:10:50UTC, six exit0 commands/seven verified
artifacts. The [new r2 plan](../config/q2-down-register-palette-plan-v2.json)
binds122 fixtures/13 manifests/1028 provider files; both staging capsules
verify. Original GPU leases/model stats still gate fresh admission. The
pre-recovery descriptions and audit below retain the earlier failed attempt.

`.157` SSH admission timed out; publication then failed locally and the
dependent component SSH returned “No route to host.” Both transports failed
before any remote connection, so no GPU/model/build/window started. The
[failure record](../config/q2-down-register-palette-network-failure.json)
preserves the sequencing mistake and actual exits. Later connectivity probes
also fail. Core freshly confirms non-use of `.157`. Last verified release is
03:31:16.929649UTC/57b67078; no fresh global closure is claimed while unreachable.

On reconnection, revalidate coordination and lease identities, run current
host34+34, then freeze fresh r2 labels and admit only the down component/model.
The new [phase helper](../tools/q2-down-register-palette-phase.py) refuses a
missing/mismatched/released admission, a failed remote check or an existing
evidence cohort. The model also requires a collected device-safe component.
Inspect each terminal result before its dependent action and collect/release
the whole window before analysis. HC needs its own full cycle fixture and
later admission. No qualified comparator, rejected tail/register/SSM trial,
Q4 or context curve is rerun. Existing independent-quality limits stay open.

[Pre-recovery priorities and command audit](../config/q2-target-priorities.json).
