<!-- SPDX-License-Identifier: MIT -->
# Scalar HC down and SiLU fusion

The new component joins the original320-by10240 F16 HC down projection and
its following F32 SiLU(scale0.25) in one kernel. It removes one launch and
one1280-byte write/read pair per HC operation. The original16-wave dot and
reduction are retained, including the measured3,1,2,0 FMA operand sequence.
No weight conversion, precision reduction, allocation or prefill-body change.
Official Gufo source pin:f783fedb9bea2ec7de941f6da4e02f4a4596b29e.

The candidate is compiled separately; the fixture's original down/SiLU and
both linked up/mix consumer kernels are byte-exact to native servera4afb757.
Both candidate witness/production variants use13 VGPR and no private scratch.
Static inspection catches fast-math folding scale0.25 into the exponential
coefficient. An explicit multiply alone does not prevent it; a register-only
compiler boundary restores the original sequence without another instruction.
Both preliminary objects and the failed static assertion are preserved; no
GPU run of those preliminary variants occurs.

The GPU fixture checks seven input families, guarded buffers and immutable
inputs. It compares raw down, scaled activation, complete mixed output and
injection; independent FP64 formulas check all320 raw/scaled values (except
F32 subnormals, whose gate is exact native replay). It measures both the
complete down/SiLU operation and its actual up/mix consumer. Each graph has
64 calls with16 rotating weight banks:100MiB down-only/200MiB full chain.
Two warmups and five alternating pairs are retained. Performance still runs
if a numerical comparison fails, with actual exit1 preserved.

Compile/link/changed-file formatting and static checks pass locally. GPU and
model qualification are pending; this is not a model-throughput result.
[Source and static contract](../config/q2-hc-down-silu-source.json).

The .157 component completes exit0 with70 exact comparisons and24 independent
FP64 checks. Down/SiLU latency falls34.535219 to32.575734us (-5.673873%);
the whole HC chain falls68.550906 to66.429563us (-3.094552%). All five pairs
favor the candidate in both modes. All24 artifacts match remote hashes before
release12:54:22.239156UTC/519c89b8,1970 identities/1576 groups retired, empty
KFD, five original leases free and seven original model stats unchanged.
[Complete result](../config/q2-hc-down-silu-results.json).

The private1031-file model provider adds only the separately compiled kernel,
its declaration, build source and scalar HC dispatch. It replaces Dense-down
and SiLU only under the existing scalar eligibility; that F16 Dense route had
no cache-side effects. Common kernels, up/mix, scratch identities and all
prefill-body branches are unchanged. The scalar final logits head can use the
same qualified operation. Full-model throughput remains pending.

The locally built native candidate8e48aa82 retains all922 existing device
functions byte-for-byte, including the isolated up/mix kernels. Both new
down/SiLU kernels exactly match the qualified component. All1031 provider
files verify; common RelWithDebInfo and only scalar -g0 remain. Full build
and corrected added-line formatting pass. Provider-wide formatting retains
unrelated inherited violations; its exit1 and the initially unformatted new
call/declaration are preserved. Only the new lines were corrected.
