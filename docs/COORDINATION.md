# DS4 / synapse-lie coordination

## Clocked root window released — 2026-10-03 UTC

R3 completes ten arms and the SSH controller exits 0. Root closes at
**23:30:28.038945 UTC**: 26 owned PID/start identities from R2/R3 are retired,
KFD is empty, four original leases are unchanged/free via EX|NB, four model stats
and both capsules remain unchanged. The release is
`run/gpu-perf-clocked-window-release.json`, SHA256
`a062e4e3b6662d242b6c084b90a169faeff3f215841c3f9eb0d63a6a02f2da8a`.
All 90 collected remote artifacts verify; root continues offline analysis only,
with no observer, automatic restart or waiter. R2's previous GPU-guard failure
remains preserved and is not converted to a pass.

Point receives the next read-only predictor-copy window with fresh original
leases. It subsequently reports a verified 2,786,568,256-byte `.157`→`.161` copy,
matching receiver SHA and unchanged source stat. Source/receiver/controller
exits are 0, while a nested generic receipt incorrectly retained an initialized 1;
that bookkeeping failure remains explicit. New root GPU work still requires
independent handover/lease/identity checks, not the thread report alone.

## CPU guard correction and clocked continuation — 2026-10-03 UTC

The owner clarifies: **the CPU needs the guard, not the GPU**. New local and
remote supervisors retain the selected CPU ceiling (98 C on qualified Strix
Halo 395), lower exposed CPU bounds and the separate NVMe 85 C or lower bounds.
GPU sensor values and peaks remain recorded with a null software temperature
limit. No fan, power, clock, firmware or hardware protection setting changes.
Three synthetic sensor/lifetime tests verify GPU 101 C continues, CPU98 C refuses,
SSD limits and termination of owned children only. Historical capsules retain
their original policies and results.
Two additional legacy-manifest sensor checks pass; the old observation flag
cannot disable the CPU guard when interpreted by new helpers.

Root's `gpu-perf-clocked-r2` starts after Q2's release at
**23:03:30.243030 UTC** and fresh admission at **23:06:11.225623 UTC**. The C17
12288-depth arm passes; its C++ control stops under the earlier GPU98 guard,
sampling GPU 101/CPU96.125 C. Child/supervisor exits are 1/1; this is a software
stop, with no observed hardware crash. R2's controller and four worker identities
retire, KFD is empty and original leases remain unchanged/free.

Root retains the coordinated window for explicitly prepared R3, repeating all
ten frozen-`15c6082` arms with the corrected guard. Runtime binaries are unchanged.
Each arm reacquires the original four leases and verifies CPU at or below 60 C
before model loading, with a bounded 240 s read-only cooldown. GPU temperature
does not gate admission or termination. The Point thread owns `.161`; after
verified root release it receives a separate predictor-copy window on `.157`.

## Shared C17 integration and Point continuation — 2026-10-03 UTC

Root combines `ba054bd` sampler optimization with `d42ac47` vision decoding
locally on `.155`. Native sanitizer and host-reference checks perform no model
forward or GPU execution; providers will be compiled locally with GPU visibility
masked. Existing qualified binaries and receipts remain unchanged.

The later vision/MTP window below closed at **20:44:19.723712 UTC** and returned
`.157` to Q2. Root's read-only observation at **22:44:21.143843 UTC** verifies
Q2 supervisor `3277171`/start `163236329` and KFD server
`3279093`/start `163254848` live. Root acquires no lease or GPU admission and
does not stage its prepared ten-arm performance follow-up.

At the owner's request, the existing Strix Point thread continues its isolated
`.161` campaign. It reports old-source fresh256 LIE closure at
**22:52:07.965628 UTC**, then starts the separately admitted Gufo control.
Root does not access or change that target; newer-runtime GPU qualification
must remain distinct from these old-source baseline measurements.

## Completed root GPU window and local thermal test — 2026-10-03

Root's `.157` functional/state/performance window closes at **19:41:04.028239
UTC**. `run/gpu-functional-c17-window-release.json` and the shared register
record all 28 owned supervisor/child identities retired, SSH controller exit 0,
empty KFD and all four original lease identities unchanged/free via EX|NB.
Six model stat witnesses and every used source capsule are unchanged. All
thirty files from the six performance arms are collected and SHA-verified.
There is no observer, automatic restart or waiter. Q2 receives the release;
future admission remains fresh. The seven-arm `gpu-vision-bec-r1` continuation
is prepared locally only, not staged or run.

The owner explicitly requests a local `.155` thermal benchmark and has already
authorized maximum fan curves from 60 C. These instructions supersede the
earlier local non-performance-only scope and the historical no-fan-tuning
statement below. This run changes no hardware setting. The verified host is
the ASUS ROG Flow Z13, distinct from `.157`'s Bosgame despite matching hostnames.
Existing local `/tmp/ds4.lock` **dev54/inode22093645** is held EX|NB, with FD/path
identity checks, afresh for each of eight sequential synthetic GEMM trials.
Other threads are notified of the local window; no DS4 ACK or universal
exclusivity is claimed. No model payload, hash or conversion is performed.

All eight child/helper exits are 0; the 201.79 s campaign completes at
**19:41:56 UTC** without a 98 C guard stop. Sampled peaks are CPU93.5/GPU97 C.
Postflight verifies sixteen owned identities retired, empty KFD and unchanged,
free local lease. Temperature/fan/frequency/thread data and actual exits remain
in `evidence/gpu-thermal-155-20261003T1940Z`, bound by the
[local thermal receipt](development/validation/local-thermal-155-2026-10-03.json).
No original-weight inference performance is inferred from this operator test.

## C17 sampling fallback — 2026-10-03

The owner requests functional GPU tests if `.157` is available, otherwise the
owned-C executor roadmap. Root's read-only observations at 14:46–14:48 UTC find
an idle interval but the shared register subsequently records
`q2-combined-retained-model-r1` starting at **14:46:50.902440 UTC**. Root notifies
Q2 and takes the CPU development fallback; it acquires no lease and does not
enter the campaign gap. No model payload, GPU execution, remote build or model
hash/conversion occurs. The new functional GPU controls/MTP/vision gates remain
open, with fresh coordinated admission required later.

`feature/c17-sampling` owns a persistent worktree from `develop`, advanced to
checkpoint `8992c0b`, and independently fetches the recorded official Gufo pin.
Native fixtures, host reference checks and HIP compilation/linking run locally
with GPU visibility masked. Build groups use one job and sensor telemetry;
initial 95 C guards preserve actual owned-child thermal stops. Later provider
builds run serially with an explicit 98 C CPU allowance and lower exposed
hardware/NVMe limits. No fan, clock, power, service or foreign process is changed.
Thermal stops are software supervision events, not observed hardware shutdown.

## Ownership and observed isolation

Editing host `.155`, target `paperboy@192.168.5.157`, SSH port 22, recovered from
inherited context and verified with SSH configuration/SSH_CONNECTION. Both hosts
report the same hostname, so hostname alone is not identity. Use:

```sh
ssh -o BatchMode=yes paperboy@192.168.5.157 'env SHELL=/bin/bash bash -s'
```

No network scan, service stop, device setting change or package install was used.
The newly created local LIE directory was not visible on .157: filesystems are
not a shared project checkout. However both agents can access the same local
workspace and remote hardware. Filesystem/process/GPU ownership still matters.

LIE owns only `/home/paperboy/workspace/projects/synapse-linux/synapse-lie`.
Default LIE ports: 19879 API / 19880 management; future reference-only Gufo port
19881. Private future session store: `$HOME/.local/state/synapse-lie/sessions`.
Private evidence/build/temp paths under this project; models are read-only.
There is no remote LIE deployment or permanent listener in this increment.

The other agent owns the dirty DS4 `migration/gufo-full-backend-v2` work at
`c05cd8e2...`, the launcher and all DS4 build/cache/results. Do not execute a
mutable DS4 binary as a baseline. Record its sealed historical identity only;
a future fresh comparator must be built in an immutable, test-owned directory
from agreed stable inputs, never racing their build output.

## Local non-performance tests — user authorization update

The subsequent user clarification, `strix halo regge fino a 98 gradi`, revises
the operating guard for explicitly selected Strix Halo 395 tests. Helpers retain
85 C by default, allow explicit 98 C only on the verified 395 host and continue
to respect lower exposed max/critical limits. NVMe stays at 85 C or lower. No
firmware/fan/clock/power setting changes. This does not reopen the completed R1
window or override Q2's current ownership; the next SSD attempt is separately
prepared as described in [the revised protocol](development/protocols/SSD-GPU-PROTOCOL.md).

Q2 subsequently completed HC exploration and recorded explicit release at
2026-10-02 07:13:11.718 UTC in `run/q2-hc-window-release.json` and the shared
register. Read-only SSD preparation verified that record, empty KFD, available
memory/disk and CPU48.125/GPU46 C; no lease or model payload was touched. This
thread takes the next coordinated SSD campaign, with fresh per-arm admission
and thermal guard as specified in [SSD-GPU-PROTOCOL.md](development/protocols/SSD-GPU-PROTOCOL.md).
Q2 continues local preparation. This update supersedes its earlier ownership
of the window described below, without rewriting historical run evidence.

The user now permits non-performance tests on the editing Strix Halo `.155` as
well as `.157`, and explicitly requests temperature care. New local CPU builds
and fixtures use `tools/thermal-run.py`, at most `-j2`, continuous sensor records
and an 85 C ceiling (or lower sensor max/critical threshold). Thermal refusal /
termination preserves actual exits and signals only its owned child group;
no power, frequency or fan tuning. Original-weight performance comparison stays
on `.157` under fresh ownership/leases. This is not GPU-run or heavyweight model
hash authorization on the editing host. The Q2 thread owns the next `.157` window
while this thread implements and CPU-tests the C17 SSD store locally.

## Completed SSD continuation — 2026-10-02

Q2 explicitly reserved the next window after its two expert-kernel model arms.
Its persistent `run/q2-expert-stack-window-release.json` records closure at
08:33:20.974 UTC: five runners retired, no live owned commands, KFD empty and
four expected leases verified free. A fresh read-only observation at 08:38:43
also found KFD empty, CPU48.125/GPU46 C. The core accepted this handover and
staged SSD R2 at 08:39 UTC with 14 remaining arms and explicit 98 C CPU/GPU,
85 C or lower NVMe guards. Every arm still performs fresh four-lease admission.
The earlier prepared capsule/manifest are preserved before the handover update.

R2 closes at 08:51:50.704 UTC with twelve owned identities absent, KFD empty
and four unchanged/free leases, after the 128K reader reaches the 98 C software
ceiling (sample99 C). R3 closes at 08:57:27.576 UTC with two owned identities
absent and the same empty/free observations, after the first 8K core arm samples
98 C. All 67 R2 and 23 R3 files verify. Neither event was a hardware crash.

The owner then explicitly requests observing brief high-temperature peaks with
dynamic fans and recording deterioration or shutdown. Root retains the window
for R4, launched at 09:09:58 UTC under fresh per-arm admission. Only the CPU/GPU
software operating ceiling is removed in its explicit observation mode; exposed
hardware bounds and SSD guards remain. There is no hardware-setting change.
A separate owned read-only observer saves 1 Hz samples on the editing host;
its retirement is also required before root returns the window. See the
[R4 declaration](development/protocols/SSD-GPU-PROTOCOL.md#owner-requested-thermal-observation--r4-2026-10-02).

R4 completes all ten arms at **09:39:08.072 UTC**, each child/helper exit 0.
Postflight records all twenty owned identities absent, empty KFD and four
unchanged/free leases; independent status confirms the controller absent.
The observer retires at 09:39:24.129 UTC, SSH exit 0, with 1,743 samples saved
locally. All 106 collected files verify by SHA-256. Root returned the window
to Q2 and notified Strix Point after collection; further work here is offline
analysis on `.155`. No permanent reservation or DS4 ACK is implied.
Offline checks pass all output/cache-count comparisons; the [complete result](archive/SSD-GPU-COMPLETION.md)
includes prefill/decode/restore timings and sampled temperature durations.

## HTTP SSD preparation and other-thread window — 2026-10-02

Core work following R4 is local CPU implementation and ASan/UBSan checks of
`--suite http-ssd`, under the user's `.155` non-performance authorization and
explicit 98 C guard. No model payload or remote GPU work is performed. The
[protocol](development/protocols/SSD-HTTP-PROTOCOL.md) and source-bound receipts distinguish this
preparation from original-weight evidence.

After Q2's work, the Strix Point thread reports starting the owner's direct
`.157` to `.161` model copy at 10:36:05 UTC, holding the four established `.157`
leases. Root acknowledged this window and requested verified closure before
the next core campaign. This is coordination reported by that thread, not a
fresh root exclusivity observation. No gap interleaving or automatic GPU waiter
is scheduled; next admission still requires completed handover and fresh leases.

Point reports completed copy/rehash and verified release at **11:11:58 UTC**:
owned source/receiver/controller and temporary agent retired, KFD empty, four
unchanged/free leases and source model stats unchanged. Root accepted the next
core cache/HTTP SSD window and notified Q2. Fresh root observation at
**11:27:36.764514 UTC** independently finds KFD empty, all four original lease
identities free via nonblocking probes, five model stat witnesses unchanged,
CPU49.375/GPU48 C and installed system LZ4 1.10.0. This lightweight handover
check does not replace per-arm leases or authorize campaign-gap interleaving.


## Cache codec continuation — R5/R6/R7, 2026-10-02

R5 closes nine successful arms at **11:57:08.113025 UTC**: eighteen owned
helper/child identities absent, KFD empty and four unchanged/free leases.
Independent status confirms controller retirement; the observer exits 0 at
11:57:23.792732 UTC. All 98 collected files verify. Root retains the coordinated
window for the numeric-codec follow-up, with fresh admission for every arm.

R6 closes all six arms at **12:30:26.836170 UTC**: twelve owned identities
absent, KFD empty, four unchanged/free leases, controller absent. Observer
exits 0 at 12:30:42.174668 UTC with 951 locally preserved samples. All 68 collected
files verify. The codec is exact but its 15–16% savings have unacceptable cost
for the owner. Root informs Q2 of the brief R7 continuation before staging it.

R7 is staged at 12:31:09 UTC from `71a4599`; each of its four ON/OFF core arms
retains fresh four-lease admission and all model/DSO/resource checks. The new
>=2:1 acceptance gate and bounded probe change only host packing admission;
no numerical kernel, device setting or thread count changes. The independent
observer remains part of required closure before returning the window.

R7 completes 4/4 arms and closes at **12:37:26.556477 UTC**, eight owned identities
absent, KFD empty, four unchanged/free leases and controller absent. Observer
retires at 12:37:42.541409 UTC, SSH exit 0 with 373 samples. All 50 collected files
verify. Root returns the window to Q2 and informs Point after these checks;
no root GPU job or automatic waiter remains. Remaining work is local analysis
and documentation. This completed handover does not waive future admission.



## Earlier completed window — first SSD restart

`ssd-gpu-r1` held fresh four-lease admission for each of three sequential arms.
512-token write and restarted exact-logit/token read pass. The 8K producer
stops during PP at GPU86/CPU84 C under the initial 85 C ceiling; child/supervisor
exit 1/1, no forced kill. Thirteen later arms were not launched. This is a failed,
incomplete campaign, not an SSD performance qualification.

Closure at 2026-10-02 07:39:00.622454 UTC verifies six owned PID/start identities
absent, KFD empty and four expected lease inodes unchanged/free. Independent
status confirms controller retirement. All 39 collected artifacts SHA-verify.
Q2 received the release and resumed its own prefill window; no SSD automatic
retry remains. Full [result and limitations](archive/SSD-GPU-RESULT.md) are retained.

## Earlier completed window — C17 RAM state/cache

After Q2's verified release at 2026-10-02 03:14:56.579 UTC, CPU fixtures ran
sequentially on `.157`, followed by `state-gpu-r1` from 03:36:25.717 to
04:06:08.841 UTC. All 16 arms exit 0. Each reacquired all four established leases
EX|NB with recorded device/inode identities, fresh admission, model stat and
binary/DSO identities, foreign-client observation and owned cleanup.

Postflight at **04:06:08.841823 UTC** records 32 owned supervisor/child identities
absent, KFD empty and all four unchanged leases free. Read-only status afterwards
confirms the controller absent and no listener on 8000 (only six TIME_WAIT
connections). All 153 collected files verify by SHA-256. The verified release
was sent to Q2, which acknowledged taking the next window. Remaining LIE work
was local offline analysis and documentation, not renewed GPU admission.

Persistent raw paths are local `evidence/state-gpu-r1` and remote
`run/state-gpu-r1`; source CPU capsules and all builds also stay under LIE-owned
persistent paths. No source in `/tmp`, foreign termination, deployment, install,
model conversion, remote GPU build or DS4 mutation. Existing desktop/denied-FD
limitations and absence of a formal DS4 ACK remain recorded. See the
[complete RAM result](archive/STATE-GPU-RESULT.md), including the retained CPU failures.

## Earlier completed window — shared-core GPU regression

The operator authorized the first conversion test on `.157`. After the Q2
thread's verified release at 2026-10-02 01:31:56 UTC, CPU fixture verification
and the core GPU campaign ran sequentially. Every GPU arm acquired all four
existing EX|NB leases with fresh admission and identity checks. Failed R1 keeps
its pre-model port refusal; its successful baseline HTTP arm is explicitly
retained in R2. No opportunistic interleaving or automatic admission retry ran.

R2 completes its 13-arm comparison at **02:13:52.975891 UTC**. Postflight at
**02:13:52.976657 UTC** records all 26 supervisor/child PID/start identities absent,
empty KFD and unchanged/free leases. Later read-only status confirms the controller
absent and port 8000 empty. All 121 collected files verify by SHA-256. The release
was sent to the Q2 thread before local offline analysis. These observations do
not assert the machine stays idle once that thread resumes.

Source/build/evidence stay in persistent LIE-owned directories. Local work was
compile/link and analysis only; CPU tests and original-weight execution ran on
`.157`. No permanent service, foreign termination, install, remote GPU build,
model conversion, tuning or DS4 mutation occurred. Desktop/denied-FD limits and
the absence of a formal DS4 ACK remain recorded. See the
[GPU result and retained failure](archive/CORE-GPU-RESULT.md).

## Earlier completed window — first real Q2 model test

The operator explicitly said `autorizzo il test GPU` and then dedicated the
machine to the model. The isolated test removed its proposed cumulative HIP cap
and fixed 32 GiB reserve; the production UD gate was not weakened. Read-only
observation at 10:00 UTC found empty KFD/no model handles, with no formal DS4 ACK.
It was not used as standing admission: the actual run reacquired all four
existing EX|NB leases with expected identities and current in-lease preflight.

`q2-model-first-gpu-r1` ran **2026-10-01 10:14:42.109474–10:15:04.074987 UTC**,
child/supervisor exit 0: actual Q2 load, correct arithmetic/counting output and
finite frontiers. Two fresh-session PP/TG samples are retained, not a matched
benchmark. Artifacts and model stat identity stayed unchanged. At **10:18:10.344270
UTC**, both owned PID/start identities were retired, KFD empty and all four
unchanged lease files free. Start/end register and 20 telemetry samples are kept.
Desktop/denied-FD limits remain; no universal exclusivity is claimed. No permanent
service, waiter, retry, installation, remote build, tuning or DS4 modification.
See [the model-test report](archive/Q2-FIRST-MODEL.md). This one-shot window is complete,
not permanent authorization for more GPU work.

## Earlier completed window — extended Q2 operators and corrections

The operator renewed the window with `ok procedi, hai la finestra GPU libera
quindi prima completi prima riesci a testare`. Read-only checks are retained in
`q2-operator-activity-r2/r3/r4`. Four distinct one-shot GPU runs each acquired the
four existing EX|NB leases and performed current in-lease preflight. Two exposed
arithmetic failures; subsequent corrected source passed **24 extended + 64
original controls**. No unchanged failing binary was retried automatically.

The final runs completed at **08:07:34.989080** and **08:09:45.979849 UTC** on
2026-10-01. Postflight at **08:14:28.029966 UTC** confirms all four attempts'
owned identities absent, empty KFD and unchanged/free lease files. Collections
are hash-verified; start/end register and telemetry are retained. There is no
model access, performance measurement, remote build/install, permanent service,
waiter, tuning or DS4 change. Desktop/observer limitations still apply; formal
ACK was absent, and no universal exclusivity or standing authorization is claimed.
See [Q2-EXTENDED.md](archive/Q2-EXTENDED.md), including the explicitly retained stale
source-receipt manifest field and additive source-binding evidence.

## Earlier completed run — initial Q2 synthetic GPU operators

On **2026-10-01**, the operator supplied a fresh window: `hai la finestra libera`.
The **06:57:06–06:57:10 UTC** read-only check found empty KFD, no observed
inference/model handles or known lease holders, GPU busy 0%, and six existing
desktop DRI clients. The formal DS4 ACK remained absent. No campaign gap was
entered; no waiter/retry was installed.

`q2-operator-gpu-r1` acquired all four existing locks in the documented order,
EX|NB with FD/path/expected identity checks. It ran at **07:03:42.563098–
07:03:46.073077 UTC** (supervisor scope). The unchanged `q2-route-linked-r5`
synthetic probe passed **64/64**, child/supervisor exit 0, with start/end register
records. No model load/payload, benchmark, remote build/install, deployment,
GPU tuning or DS4 modification occurred. See [Q2-HIP.md](archive/Q2-HIP.md) for the narrow
numerical coverage; production model admission remains closed.

No new foreign GPU client was observed in nine telemetry samples. The desktop
baseline and 463 denied FD observations preclude universal exclusivity claims.
Binary/DSOs/power settings stayed unchanged. At **07:04:44 UTC** both owned
process identities were absent and KFD was empty; at **07:07:03 UTC** all four
unchanged lease files had no holders. Exact case/telemetry/exit evidence and the
offline audit are retained in `evidence/q2-operator-gpu-r1/`. There is no permanent
listener, pending run or active LIE lease. This completed window is not standing
authorization for later GPU work.

## Previous original-weight run — lifecycle qualification

The 22:42 UTC operator handover admitted `t0-model-lifecycle-r1` at 23:01 UTC.
All four existing locks were acquired in order, without waiting or recreating
DS4 files. Start/end records are present. The original-weight HTTP/SSE lifecycle
protocol passed; server/helper exit 0, no foreign GPU client observed, binary and
five model stat identities unchanged, KFD empty after retirement. At 23:05:36 UTC
all owned PIDs were absent and known leases had no holders (`postflight.json`).
No permanent deployment, wait/retry, GPU tuning or DS4 modification was performed.
The completed one-shot window is not permanent authorization for later runs.

## Operator window — lifecycle qualification

At **2026-09-30 22:42 UTC**, the operator stated `hai a disposizione gpu`.
`t0-lifecycle-activity-r2` then observed GPU busy 0%, empty KFD, no inference/model
handles and no holders of the four known leases. `ds4-ack.json` remains absent.
This is a fresh one-shot handover, not a formal DS4 ACK or a permanent lease.
All four existing locks must still be acquired nonblocking, with ordinary
preflight, run registration, foreign-client checks and owned cleanup. No new
model inference had occurred at the source receipt; the separate result above
records the later actual run.

## Earlier read-only observation — lifecycle preparation

At **2026-09-30 22:09 UTC**, `t0-lifecycle-activity-r1` observed an active DS4 Q4
benchmark campaign, one KFD client and all four known leases held. The enclosing
pipeline lease remained held independently of the per-job leases. No formal
`ds4-ack.json` was present, despite observed use of the shared lock. No LIE GPU
run/staging, model payload read, lock acquisition or foreign process signal was
attempted. No background wait/retry is scheduled; do not enter campaign gaps.
The new server lifecycle suite is prepared and CPU-tested only. This observation
does not extend the historical operator window below.

## Historical operator window

The 18:49/18:51 UTC attempts were refused before model open, and DS4 was actively
benchmarking at 18:53. Those receipts remain unchanged. At 20:01 UTC the operator
explicitly handed the machines back for LIE development: “ok per ora riprendi lo
sviluppo lie che le macchine sono libere”. A fresh read-only probe found no KFD or
observable inference/model clients and no known lease holders.

Both new attempts acquired pipeline/download/qualification/shared locks in that
order, nonblockingly. `t0-model-smoke-r3` passed DSO preflight but failed immediately
after child launch on a runner defect; `t0-model-smoke-r4`, with its regression-tested
fix, passed the original-weight C1 HTTP/SSE smoke and exited cleanly at 20:07:42 UTC.
The shared register has actual start/end records. Leases were retained through
cleanup and released afterwards. No permanent listener remains.

The later explicit request to measure prefill/decode authorized another bounded
run. `t0-c1-perf-r1` failed on unavailable optional power metadata before model
launch. After a CPU-tested metadata fix, `t0-c1-perf-r2` acquired the same leases,
recorded start/end and completed the C1 baseline at 20:52:07 UTC, child/helper exit 0.
No foreign GPU client was observed and KFD was empty after retirement. The known
model stat identities and staged hashes were unchanged; no power setting was
modified. Missing `pp_power_profile_mode` is recorded as unavailable, not invented.
See [C1-BASELINE.md](archive/C1-BASELINE.md). Neither attempt is permanent admission approval.

The operator handover is not an ACK or permanent shared-runner adoption; no
`ds4-ack.json` was forged. See [T0-SMOKE.md](archive/T0-SMOKE.md). Never opportunistically
enter gaps between another owner's benchmark jobs; fresh work still needs an
actual available campaign window and the same admission controls.

## Shared protocol: proposed, not acknowledged

Remote proposal created exclusively:
`/tmp/synapse-lie-ds4-coordination/synapse-lie-proposal-r1.json`.

Proposed shared lock: `/tmp/synapse-lie-ds4-gpu.lock` (flock, nonblocking).
Proposed append-only register: `/tmp/synapse-lie-ds4-coordination/runs.jsonl`.
DS4 acknowledgement file: `/tmp/synapse-lie-ds4-coordination/ds4-ack.json`, to be
written by the DS4 owner, not forged by this agent. It must identify the adopted
runner/revision and lock path. No acknowledgement was present at the initial
check or the **2026-09-30T18:13:29Z** read-only recheck recorded in
`evidence/t0-coordination-readonly-r3.json` (also absent at the preceding 17:23 check). This is a dated observation, not a
future availability assertion. Creating/acquiring our own lock is not consensus.

Existing DS4 runner uses, in order:
1. `$W/download-gufo-native/download.lock`
2. `$W/.qualification.lock`
with queue coordination at `$D/qualification/.pipeline.lock`.
Here `$W=/home/paperboy/.local/state/ds4-kernel-work/20260927T161150Z-qwen-hip-prefill`
and `$D=/home/paperboy/workspace/projects/cachyos/ai/ds4-gufo`.
Do not alter these scripts/locks or acquire them in a conflicting order. Agree
on the relationship/order of the new lock before using it; legacy leases can
remain in addition. Both agents must honor the same agreed lease for GPU work,
full weight hashing and heavyweight I/O. A released per-job lease does not mean
an enclosing DS4 benchmark campaign wants interleaved cache perturbations.

For each leased run record owner, command (no credentials), PID/start_ticks,
model/content identity, start/end UTC, exit code and contamination observations.
Lock FD lives with the supervisor and is released in finally/error paths. Do
not delete/unlink live lock files or use PID-only stale-lock cleanup. Stop only
own pinned process identities. No killing a foreign holder to gain admission.

A lease is cooperative, not GPU exclusivity proof. Before and during a run also
inspect foreign device FDs/mappings and processes/services, memory/disk, model
and binary identity, and current power/runtime settings. Capture observations
before refusing. Desktop activity and noncooperating clients must be accounted
for. Avoid a fixed assistant-invented RAM floor; choose explicit measured job
budgets with the operator, never interpret a policy stop as OOM/capacity proof.

**Further hardware/heavy-I/O work requires current coordination and admission;
the completed operator window is not a standing lease.** The initial CPU receipts
in this historical section ran on `.155`; the user's later instruction moves
CPU tests as well as GPU execution to `.157` for the isolated reactive branch.
Read-only reconnaissance reads small receipts/sysfs/proc and bounded metadata,
not tensor payloads. The separately authorized r4 model run did read original
weights and execute HIP on .157; it passed a bounded serving smoke, not a numerical
or performance qualification. The later separately admitted C1 measurement is
an embedded-provider timing baseline, not an independent numerical or speedup
qualification. Local compilation/no-model/synthetic receipts retain their original
scope. No remote compilation, dependency installation or model conversion occurred.

## Isolated OpenAI reactive window completed

The user requested GPU tests on `.157` and an isolated worktree/feature branch.
`openai-reactive-gpu-r2` and final `r3` acquired all four existing leases EX|NB
in the established order, with fresh in-lease preflight, start/end register and
observed process ownership. Final r3 completed at 2026-10-01T13:52:14 UTC; server/
helper exit 0. Postflight at 13:54:02 UTC found empty KFD, owned PIDs absent and
unchanged/free locks. No formal DS4 ACK or standing lease is implied.
See [the original-weight protocol evidence](archive/OPENAI-GPU.md). Source and results
remain in the isolated branch; concurrent original-worktree records are not
rewritten by this increment. CPU parser/lifetime/sanitizer checks also ran on
`.157`, with GPU visibility explicitly disabled only for synthetic fixtures.

## Performance operator window — 2026-10-01

The explicit performance request and resume admitted two separate one-shot GPU
runs, `performance-executor-r1` and `performance-http-r1`, each with fresh
pipeline/download/qualification/shared nonblocking locks, in-lease preflight,
model stat/DSO checks, and start/end registration. No formal DS4 ACK, standing
lease, installation, tuning or deployment is claimed.

Direct benchmark retired at 15:27:59 UTC. HTTP retired at 15:43:41 UTC;
postflight at 15:45:00 UTC verified unchanged/free identities for all four locks,
owned supervisor/helper/server/observer PIDs absent, KFD empty, binary and model
stat identities unchanged. The supplementary observer only read sysfs/proc and
has a separate source hash and exit receipt. Results and limitations are in
[PERFORMANCE-RESULT.md](archive/PERFORMANCE-RESULT.md). Further GPU work needs a new
admitted window; this is not permanent shared-runner adoption.

## Simplified Gufo-style campaign — 2026-10-01

The explicit request for Gufo-style comparisons through 128K and a reusable
benchmark authorized one-shot `bench-suite-r1/r2` arms. Each obtained all four
existing nonblocking leases afresh and retained stat/DSO/client checks and
owned cleanup. Single LIE/Gufo depth arms passed; r1 retains its FAILED root
from a small-context rendering-bound calibration failure before any multi sample.
After the bounded-calibration fix passed fresh 18/18 debug and sanitizer suites,
r2 ran only missing multi/memory/loading arms and completed PASS at 17:53:48 UTC.
Every helper/child exit is 0. No DS4 artifacts, processes or services changed.

R1 final postflight at 17:37:09 UTC observed unchanged/free lease paths, all
owned PIDs absent and KFD empty. R2 helper receipts retain unchanged model/file
identities and empty postflight KFD lists; a final read-only SCP observation
shows no holders of the known four lease identities and all thirteen owned
PIDs absent. Final r2 lock-path stat was not independently rechecked. Missing
proc files produce expected SCP exit 1, retained in the retirement receipt.
No persistent lease, tuning, package installation, foreign termination,
deployment or publication. See [BENCHMARK-RESULTS.md](archive/BENCHMARK-RESULTS.md).

## Reactive inference admission refusal — 2026-10-01

The operator requested reactive inference integration with GPU tests retained on
`.157`. A prepared bounded campaign first checked the successful CPU capsule,
then attempted the normal HTTP helper. At 18:51:29 UTC `reactive-suite-r1`
failed the first EX|NB pipeline lease with EAGAIN; all four existing lease
paths were observed unchanged and occupied. No lease was retained, no model
was attempted, and no server/GPU child was launched. The controller/helper
retired; the actual helper/controller exits and postflight are retained under
`evidence/reactive-suite-r1`. No owner was interrupted or contacted.

The next campaign must use a new exclusive directory and a fresh available
operator window, then reacquire all four leases. Empty KFD during a held
enclosing campaign is not permission to enter its gaps. CPU fixtures continue
with HIP/ROCR visibility disabled and no heavyweight model I/O.

## Reactive inference window completed — 2026-10-01

The operator explicitly renewed the available window with `la gpu è libera`.
New exclusive campaign `reactive-suite-r2` ran 19:24:01–19:59:02 UTC, source
checkpoint `0e2bd45`. Each of its five sequential arms independently acquired
all four existing EX|NB leases in the established order and retained in-lease
model stat/DSO/client checks, start/end registration and owned cleanup.
Original-weight HTTP checks and matched serial/reactive multi/context benchmarks
all pass, each helper and GPU child exit 0. No automatic GPU retry occurred.

At 19:59:02 UTC final postflight found all ten owned helper/child processes
absent, KFD empty and all four unchanged lease paths free. A subsequent read-only
SCP of the controller's `/proc/2179491/stat` observed it absent (expected SCP
exit 1, separately retained). All 43 archived files match the remote collection
SHA-256 map. No foreign GPU client was observed; desktop clients and denied-FD
observations still preclude universal exclusivity claims. No DS4 change, foreign
signal, remote build, install, tuning, model conversion, deployment or publication.
No standing lease or formal DS4 ACK is implied. See
[REACTIVE-INFERENCE-RESULT.md](archive/REACTIVE-INFERENCE-RESULT.md).

## DS4 policy continuation — 2026-10-02

Q2 records explicit HC-vector release at **13:37:03.673156 UTC**. Root accepts
the next policy/context-growth window and notifies Q2 and Point. Fresh root
handover at **13:57:00.664436 UTC** finds empty KFD, four unchanged/free leases,
five unchanged model stat witnesses, CPU47.375/GPU46 C. The first read-only
helper attempt had a Python quoting error and performed no remote action; its
exit is retained. No model was launched by these observations. Every ensuing
arm requires fresh admission; no interleaving, remote build or model conversion.

R8 stages at 14:01:18 UTC from `80b6273`. Its first three arms pass; the fourth
finds the retained adapter pre-generation capture restriction. Campaign closure
14:06:00.539460 UTC verifies eight owned identities absent, KFD empty and four
unchanged/free leases. Observer retires at 14:06:16.094468 UTC, SSH exit 0, 269 samples.
All 49 collected files verify. Root informs Q2 and retains the window for the
local repair and R9 with a dedicated generated-frontier qualification.

R9 frozen source `f11ab7f` completes nine device arms, all child exits 0. Its
controller fails an expected-cache-depth assertion at 128K/4 GiB; the observed
28672-token prefix reflects eviction pressure. Closure 14:42:10.456303 UTC
verifies 18 owned identities absent, empty KFD and four unchanged/free leases.
Observer exits 0 at 14:42:26.574409 UTC;95 files verify. R10's one raw-text legacy
child exits 0, while its controller assumes an unaligned full hit incorrectly.
Closure 14:44:49.080054 UTC verifies two owned identities absent and the same
lease/KFD conditions; observer exits 0 at 14:45:05.154928;22 files verify.

R11 uses the identical frozen binary and five unlaunched arms: raw text, core
SSD producer/reader and matched 128K/8 GiB controls. The R10 text reference is
bound by SHA256. All five arms complete, and independent offline analysis
validates all five paired core comparisons and six state pairs across R9/R10/R11.
Final closure **14:56:30.025088 UTC** verifies ten owned identities absent,
empty KFD and four unchanged/free leases. Independent status observes controller
retirement. Observer exits 0 at **14:56:45.219419 UTC**; all 58 files verify.
Root explicitly returns the window to Q2 and notifies Point after collection
and closure verification. No owned GPU process, automatic waiter or next GPU
job remains. This is not a standing lease; future arms need fresh admission.
No remote build, model conversion, DS4 mutation, installation or tuning occurred.
See [policy results and retained failures](archive/CACHE-DS4-GPU.md).

## KVC runtime qualification handover — 2026-10-02

Q2 explicitly returns the PLE-cache window at **18:25:33.765424 UTC** with
six runners and26 command identities/groups absent; observer retirement is
independently verified at **18:26:08.303468 UTC**. Its persistent receipt is
`run/q2-ple-cache-window-release.json` on .157, also tracked in the Q2 worktree.
Root accepts and notifies Q2/Point. Fresh root observation at
**18:41:12.661319 UTC** finds empty KFD, four original leases EX|NB/free, five
unchanged model stat witnesses, CPU48/GPU47 C. Receipt:
`evidence/kvc-runtime-handover`. No model payload was read by that check.

Root prepares `ssd-gpu-r12` for the [DS4 runtime comparison](development/protocols/KVC-GPU-PROTOCOL.md),
with fresh admission per arm and no gap interleaving. Local CPU fixtures and
both HIP builds are complete; no remote build, dependency installation, model
conversion or DS4 mutation. Owner-requested thermal observation retains exposed
hardware bounds and NVMe guard, plus independent1Hz samples on .155. This
handover is not a standing lease or a cross-engine qualification claim.

`ssd-gpu-r12` completes all 15 arms at **19:16:14.347739 UTC**, every child/helper
exit 0. Observer retires at **19:16:30.127576 UTC** with 1747 locally persisted
samples. All 152 collected artifacts SHA-verify. Fresh closure at
**19:18:19.131870 UTC** verifies 30 owned identities, controller and observer
absent, empty KFD and all four original leases EX|NB/free. Record:
`run/kvc-runtime-window-release.json` on .157, with matching shared
`window_release` entry. Root returns the window to Q2 and notifies Point;
no owned GPU job, waiter or automatic retry remains. Further work is local
analysis/documentation. [Results and latency regression](archive/KVC-GPU-RESULT.md).

## Local functional GPU authorization — 2026-10-03

The owner now explicitly allows short, non-performance GPU checks on the editing
Strix Halo `.155`, and reports that its fans still need configuration. New local
functional GPU preparation uses an 85 C guard, lower exposed hardware limits and
owned child cleanup. No fan/clock/power tuning is authorized or performed.
Benchmark campaigns remain on `.157` with fresh coordinated ownership. Q2 reports
no GPU or model-file reservation on `.155`; it continues its own `.157` campaign.
The source may be inspected in DS4 as reference, per the owner's clarification,
while numerical changes are evaluated against the independently pinned Gufo
provider and the relevant measured workload.

Read-only host checks find `/dev/kfd` and `renderD128`. The USB mount is
`/run/media/paperboy/models` (exFAT). Metadata-only inspection finds Qwen3.8
Q2/Q4 files, an embedded-MTP IQ2/MXFP4 variant and the Q8 vision encoder.
The 50,343,093,376-byte IQ2/MXFP4 file declares PLE but its 1,255-tensor directory
lacks `per_layer_token_embd.weight`; it cannot qualify the complete loaded model.
The other Qwen trunks need the ongoing quantization compatibility work. No model
weights were hashed, converted or loaded; no GPU was initialized or leased here.
Inventory and stat witnesses remain under local `evidence/usb-qwen-*` on MTP.

## MTP cache CPU checkpoint — 2026-10-03

This slice runs only local CPU fixtures and HIP compilation/linking, with all
GPU visibility variables masked. No GPU/model reservation is consumed; `.157`
benchmark work remains postponed. A status update was sent to the Q2 thread;
no new cross-thread GPU ACK or model compatibility is inferred from silence.

The initial 85 C CPU guard interrupted two provider builds and one fixture
build, and refused two further provider starts. A subsequent 90 C attempt
stopped at 91.625 C. These actual exit-125 records remain in local evidence.
For CPU-only completion, one job and a 95 C guard were used within the owner's
98 C Strix Halo allowance; the provider peak was 94.625 C, final sanitizer suite
69.5 C and final HIP client relink is recorded in the cache receipt. No fan,
clock, power, system setting or foreign process was changed. This does not
raise the separate 85 C functional-GPU preparation ceiling while local fans
remain unconfigured. No shutdown or hardware deterioration was observed.

## Vision semantic cache host validation — 2026-10-03

This step uses CPU fixtures and host HIP compilation only on the editing `.155`.
CPU build/test guards use 95 C under the owner's 98 C CPU allowance, with at most
two simultaneous single-job builds, GPU visibility masked, and lower exposed
hardware/NVMe limits retained. The provider build peaks at CPU92.125 C; the first
full sanitizer suite peaks at CPU74.375 C. No fan/power/clock settings changed.
Actual compiler/test failures and exits remain under `evidence/vision-cache-*`.
There is no model weight hash/conversion/load, GPU execution, remote build,
new lease or benchmark. Functional GPU preparation still uses its separate
85 C gate and requires compatible complete models plus fresh coordinated leases.

## Joint integration host validation — 2026-10-03

`feature/mtp-vision-integration` owns its persistent source, independently fetched
Gufo pin and new provider variant/build. The work is local CPU fixture testing
and host HIP compilation/linking only, with GPU visibility masked. No GPU/model
lease, model load/hash/conversion, remote build, deployment or publication occurs.

Builds use one job each, at most two concurrently, and a 95 C child-only guard
within the owner's 98 C CPU allowance; lower NVMe limits remain in force.
The independently rebuilt provider records CPU90.375 C, the full sanitizer suite
CPU69.875 C and the synthetic combined client CPU88.75 C. No fan, clock, power or
foreign process was changed; no shutdown/deterioration was observed. The separate
functional-GPU gate stays at 85 C with compatible complete weights and fresh
coordinated ownership required. Initial compiler failures and actual exits remain
under local `evidence/integration-*` and the source-bound integration receipt.

## Semantic events host validation — 2026-10-03

`feature/core-semantic-events` starts from `develop` and imports the completed
MTP/vision integration checkpoint. This step is local CPU fixtures and host HIP
compilation/linking only; GPU visibility is masked. The official recorded Gufo
source was independently fetched into this persistent worktree and its provider
rebuilt and verified. No model load/hash/conversion, GPU execution, remote build,
new GPU/model reservation, deployment, installation or publication occurred.

Builds use one job each, at most two concurrently, with a 95 C CPU guard within
the owner's 98 C allowance and lower exposed hardware/NVMe guards. The source
and measured peaks, actual compiler/test failures and exits are retained in the
[event receipt](development/validation/core-events-2026-10-03.json) and local
`evidence/events-*`. No fan, clock, power or foreign process changed; no shutdown
or deterioration was observed. Functional GPU preparation retains its separate
85 C gate and fresh coordinated ownership requirements.

## Original-weight vision/MTP window released — 2026-10-03

Root accepts Q2's HC-window release at **20:00:42.449978 UTC** and records fresh
admission at **20:09:05.752679 UTC**. Each arm acquires the original pipeline,
download, qualification and shared lease identities EX|NB in their established
order. The window covers the frozen `bec0955` runtime, private corrected probes,
and full model-identity hashing for explicitly declared SSD arms. Models and
numerical sources are not converted or modified; no remote build, installation,
tuning or foreign termination occurs.

Seven functional arms pass. Three initial private-verifier failures remain
preserved. Final release at **20:44:19.723712 UTC** verifies 20 owned PID/start
identities retired with empty child process groups, empty KFD, all four original
leases unchanged/acquired nonblocking and released, six unchanged model stats,
four unchanged capsules and 50 collected/hash-verified result files. Sampled
peaks are CPU80.625/GPU82/NVMe66.85 C under the authorized 98 C CPU/GPU allowance
and lower hardware/NVMe guards. No thermal stop, observer or restart remains.

The `.157` receipt is `run/gpu-vision-bec-window-release.json`, SHA-256
`58395a517da73ddf9eaf3e6aa6cb668ffbd350f85d963c0c0639b5b1940429aa`,
with a matching registry `window_release`. Root returns the window to Q2 and
notifies Point after local collection verification. The
[GPU receipt](development/validation/vision-mtp-gpu-2026-10-03.json) binds the
commands and scope. This handover is not a standing lease; later GPU work needs
fresh admission.
