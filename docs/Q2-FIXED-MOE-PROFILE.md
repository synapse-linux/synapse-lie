<!-- SPDX-License-Identifier: MIT -->
# Saved MoE candidate kernel diagnosis

The current best fixed model is 1496.830907 PP tokens/s, compared with saved
Q2 1443.672867 and UD 1685.777092. Parity still requires 12.623081% more
candidate throughput; the complete PP/TG context curve remains gated.

This separate diagnosis runs the saved MoE-only candidate executable under
installed rocprofv3 without compiling it or rerunning a qualified comparator.
It verifies the original result receipt, binary, all 1025 provider files,
counting fixture, marker fixture and 51 runtime library hashes.
The original built-in profile mode uses the same physical2048 input,
capacity9216/chunk2048, one16-output warmup and one16-output marked request
(15 timed decode calls). Its kernel timings are diagnostic and do not replace
the original unprofiled pp2048/tg128 benchmark or its one-plus-three samples.
Model loading, small smoke prompts, warmup and boundary kernels are excluded
from the marked stage costs. No new throughput headline or quality verdict.

The launcher rejects rebuild, detached execution, alternate source, control
replay and curve options. Local launch tests pass79/79; replay guards7/7 and
the existing trace/resource parser pass. On `.157`, 24/24 Debug and24/24
ASan/UBSan CPU tests pass; all six commands exit0 and seven artifacts verify.
The frozen source/runtime contracts are retained before fresh GPU admission.
The first admission helper incorrectly named its own nonexistent release as
the previous receipt and exited1 before admission. Its source/log remain;
v2 corrects only that previous path and retains the same runtime/host fixtures.

[Frozen diagnostic plan](../config/q2-fixed-moe-profile-plan.json),
[corrected window binding](../config/q2-fixed-moe-profile-plan-v2.json),
[saved binary identity](../config/q2-fixed-moe-profile-binary.json),
[host results](../config/q2-fixed-moe-profile-host-results.json).
