<!-- SPDX-License-Identifier: MIT -->
# Grouped Q8 decode/store experiment

The saved MoE provider remains1496.830907 PP /25.17435733 TG, compared with
fixed Q2 1443.672867 and UD1685.777092 on the original2048/tg128 tester.
The new trace identifies293.725 ms of Q8-weight/F16-activation dense work;
this candidate changes only that kernel's Q8 stage commit schedule.

Each32-code weight block originally expands16 half2 registers before committing
four16-byte LDS groups. The candidate expands four half2 at a time, commits
one group and inserts a compiler scheduler boundary. Original byte permutation,
half add/FMA (including its zero bias), LDS addresses, macro/wave tile geometry
and K16 accumulation order remain. This compiler boundary is not a GPU stream
barrier or reactive scheduling. No allocation, stream or persistent weights
change. One of1025 provider files differs from the measured parent.

Local gfx1151 compilation passes; the standalone operator compiles for device
and host. The main SSM instantiation retains222 VGPRs,49152 LDS bytes and zero
private bytes. Static instructions increase4027 to4067. Those counts establish
no gain; runtime performance will be retained even if numerical checks fail.
The shared formatter check exits1 with11 violations; the new test is formatted.
No formatting success is claimed for the generated numerical provider.

The new component uses a literal test-only extraction of the parent dense
kernel and SSM wrapper, bound to its exact source digest. It compares complete
outputs for the actual2048x16384x2560 SSM projection/convolution and
2048x2560x6144 dense output, plus ragged129x257x96. Both initialization and
launches use one owned nonblocking stream. All inputs must remain immutable.
Three weights rotate133693440/50135040 bytes beyond32 MiB MALL; complete-cycle
timings alternate reference/candidate with two warmups and five measurements.
Copied numerical control is a differential operator check, not independent
model task-quality qualification or a rerun of a qualified model comparator.

The frozen window permits exactly this new component and one new original-weight
model arm, retaining operator/numerical failures separately from performance.
The model uses original counting input SHA75343e606f5b815fe01f69ddc6ce50a997e2de96d8a20304a82a7f24f1180b35,
capacity9216/chunk2048, one warmup/three measured sessions,128 outputs/127 timed
decode calls and15-second waits outside timers. Qualified Q2/UD/parent controls
are read from saved evidence without rerunning them. Full-curve parity and
independent task quality remain open.

The first source extractor matched a default-argument brace instead of the
function body and exited1 before staging; it is corrected. The first launcher
edit found an ambiguous anchor and wrote no launcher. The first guard cohort
rejects one error-text expectation; final80/80 pass. All actual failures remain
in preparation evidence. Source/plan are prepared offline; no GPU result follows
from compilation or host fixtures.
The `.157` host capsule now passes24/24 Debug and24/24 ASan/UBSan; all six
commands exit0, seven artifacts and26 frozen fixtures verify. No model/GPU
is opened by that host gate. Fresh admission remains required for the new
component and candidate-only model.

[Source and exact numerical control](../config/q2-q8-grouped-source.json),
[static results](../config/q2-q8-grouped-static.json),
[host results](../config/q2-q8-grouped-host-results.json),
[frozen runtime scope](../config/q2-q8-grouped-plan.json).
