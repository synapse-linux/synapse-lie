<!-- SPDX-License-Identifier: MIT -->
# Paired Q2 half-output stores

The new candidate derives from the retained half-storage model at
1547.273268 PP /25.17198641 TG. It applies the same F32 inverse scale and
RN-even F16 conversion while each accumulator is still in registers, then
transposes halves in wave-private scratch and stores adjacent values together.
One slot-scale fetch feeds eight accumulator values. Four paired scatter
rounds replace eight scalar rounds; odd output widths retain scalar tails.
There are no new block barriers, allocations, streams or consumer changes.
Scratch used by the epilogue halves8192 to4096 bytes; LDS allocation stays fixed.
This is distinct from the older negative block-wide F32 scatter experiment.

The single changed provider file is `q2_down_half_storage.inc`; all1026 source
files are recorded in the [source manifest](../config/q2-down-half-pair-source.json).
The [static comparison](../config/q2-down-half-pair-static.json) proves158 of161
kernel bodies retain exact instructions, operands and resources. Only the
three half-down specializations change. BN16 instructions1040→1153 and
VGPR86→85; BN48 instructions2577→2321 and VGPR96 unchanged; BN64
instructions3259→2921 and VGPR104 unchanged. LDS stays14464/18560/20608
bytes, private scratch stays zero and block-barrier counts are unchanged.
These static counts are not timings; bank conflicts and extra scalar-tail
branches can offset the narrower traffic and fewer scatter rounds.

The fixture contains the literal measured1547 parent template, renamed only
for coexistence. It compares513 complete guarded down-output pairs, including
BN16/48/64, narrow/even/odd output rows and partial token tiles, plus99 ordered
consumer pairs. An independent integer RN-even conversion of the unchanged
F32 down output provides an additional format check. Guards and unwritten
required outputs stop device work; safe numerical differences retain arrays
and all timing samples. Half-parent and half-pair timing alternates inside
one process over six full distributions, two scopes and three rotated weight
sets exceeding cache capacity:168 samples including warmups. No old cohort
or qualified model binary is rerun or rebuilt.

The [frozen plan](../config/q2-down-half-pair-plan.json) contains66 fixture and
four manifest hashes. The original exact2048 input, context9216, chunk2048,
tg128/127 timed calls, MTP-off, one warmup and three measured samples remain
unchanged. The original-model candidate is measured even after safe component
numerical or timing rejection. Q4 and full curves remain deferred.

The half-storage parent introduces a real precision change versus its F32
parent: eight logit files differ despite matching benchmark token histories.
Exact agreement with1547 cannot close that inherited independent-quality gap.
No runtime default, model quality or Q2/UD parity is promoted by preparation.

Local assembly, host/device fixture syntax and119 launcher guards pass.
The .157 CPU-only gate passes27 Debug and27 ASan/UBSan checks, all six
commands exit0 and seven artifacts verify. Initial local SSH sandbox refusal
(exit255) and the exclusive-directory retry refusal (exit1, before SSH) are
preserved; neither started remote work. Their local capsule remains under
`evidence/q2-down-half-pair-host-r1-sandbox-denied`.
GPU and original-model results are pending. Remote GPU work requires a fresh
window after release `f2e1504f82efe4f118ab687272735ac761b2f9c27be590b88c308bedd12483bf`;
the preparation itself holds no reservation. Persistent source and evidence
remain in the owned worktree; no cleanup is scheduled.
