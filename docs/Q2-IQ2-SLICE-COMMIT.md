<!-- SPDX-License-Identifier: MIT -->
# Bounded compact IQ2 decode/store commits

Two isolated candidates derive from the measured IQ2 raw-prefetch provider
1505.152258 PP /25.15493858 TG. They decode and publish eight or sixteen
high-byte values per commit instead of retaining all four decoded slices.
Weight fetch ownership, the ten-byte raw prefetch, compact LDS layout, scale
expression/rounding, ordered K16 updates, SwiGLU and packed residual are
unchanged. No expanded weights, new table, allocation or stream is introduced.
This tests temporary lifetime and instruction scheduling, not lane ownership
repartition or a reactive-scheduler gain.

Both production assembly compilations and both host/device fixture
compilations exit0. Each provider has1025 files with one changed numerical
source. All149 unrelated bodies are exact in the retained assembly comparison;
the eight IQ2 bodies change. LDS, allocated VGPR and zero private bytes are
unchanged. Eight-value commits replace two128-bit stores with four64-bit
stores; sixteen-value commits preserve store counts and alter scheduling.
Neither static result establishes a GPU throughput benefit.

The original exact2048/tg128 tester, input, capacity9216/chunk2048, C1 greedy,
MTP-off, one warmup/three measured sessions and127 timed decode calls remain
fixed. Saved Q21443.672867, best1505.152258 and UD1685.777092 are reused without
rebuilding or rerunning their model/component cohorts. Full-context parity
remains the goal; closing this point admits the subsequent curve.

Each new fixture covers81 guarded complete-output pairs and42 alternating
timings with three weight rotations exceeding32MiB. It compares with the
literal measured raw-prefetch parent. Original compact-format evidence is
reused because tables and conversion arithmetic are unchanged. Safe numerical
or timing rejection still proceeds to the complete model performance test;
guard or unwritten-output failures stop further device work. Differential
equality does not establish independent task quality.

The frozen plan binds50 fixtures/four manifests and one host cohort, two new
component cohorts and two new model cohorts.103 local launch guards pass.
The preparation's initial generator and fixture-wiring anchor failures retain
their actual exit1 receipts; corrected preparations exit0. Neither failure
ran on the GPU or changes a numerical verdict.

Source derives from independently fetched official MIT Gufo pin
f783fedb9bea2ec7de941f6da4e02f4a4596b29e and the retained LIE parent. The C17
core ABI, state and metric contracts are unchanged. No DS4 source, build,
cache or qualification evidence is modified. Sources are durable under the
owned worktree and the task-owned remote run directories. No cleanup,
dependencies, tuning, Q4 or full-curve run is included.

The new .157 host cohort passes26/26 Debug and26/26 ASan/UBSan tests. All six
commands exit0 and seven collected artifacts verify, with no GPU/model access.
[Host receipt](../config/q2-iq2-slice-commit-host-results.json).

GPU admission and measured results remain pending. The window helper anchors
the previous canonical release2fa8f9c0e8268dcf44800ad1494faa79eb14723af786b6d7c9f56d893a86a709;
fresh handover, host gates and checkpoint admission are required before GPU
build/run. Local compilation is not model or GPU inference evidence.

The first helper admission exits1 while reading an incorrect self-anchor,
before opening leases or admitting any GPU work. The original helper, plan
and command receipt remain. A distinct v2 helper names the actual previous
Q8-mirror release; its corrected plan preserves all50 fixture/four manifest
hashes and reuses the completed host cohort. Fresh root handover confirms no
root .157 job/build/eval/client/lease/waiter/reservation/restart/interleaving.

[Source inventory](../config/q2-iq2-slice-commit-source.json),
[production assembly comparison](../config/q2-iq2-slice-commit-static.json),
[corrected fixed experiment plan](../config/q2-iq2-slice-commit-plan-v2.json).
