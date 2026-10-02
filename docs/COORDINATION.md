# DS4 / synapse-lie coordination

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
prepared as described in [the revised protocol](SSD-GPU-PROTOCOL.md).

Q2 subsequently completed HC exploration and recorded explicit release at
2026-10-02 07:13:11.718 UTC in `run/q2-hc-window-release.json` and the shared
register. Read-only SSD preparation verified that record, empty KFD, available
memory/disk and CPU48.125/GPU46 C; no lease or model payload was touched. This
thread takes the next coordinated SSD campaign, with fresh per-arm admission
and thermal guard as specified in [SSD-GPU-PROTOCOL.md](SSD-GPU-PROTOCOL.md).
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
[R4 declaration](SSD-GPU-PROTOCOL.md#owner-requested-thermal-observation--r4-2026-10-02).

R4 completes all ten arms at **09:39:08.072 UTC**, each child/helper exit 0.
Postflight records all twenty owned identities absent, empty KFD and four
unchanged/free leases; independent status confirms the controller absent.
The observer retires at 09:39:24.129 UTC, SSH exit 0, with 1,743 samples saved
locally. All 106 collected files verify by SHA-256. Root returned the window
to Q2 and notified Strix Point after collection; further work here is offline
analysis on `.155`. No permanent reservation or DS4 ACK is implied.
Offline checks pass all output/cache-count comparisons; the [complete result](SSD-GPU-COMPLETION.md)
includes prefill/decode/restore timings and sampled temperature durations.

## HTTP SSD preparation and other-thread window — 2026-10-02

Core work following R4 is local CPU implementation and ASan/UBSan checks of
`--suite http-ssd`, under the user's `.155` non-performance authorization and
explicit 98 C guard. No model payload or remote GPU work is performed. The
[protocol](SSD-HTTP-PROTOCOL.md) and source-bound receipts distinguish this
preparation from original-weight evidence.

After Q2's work, the Strix Point thread reports starting the owner's direct
`.157` to `.161` model copy at 10:36:05 UTC, holding the four established `.157`
leases. Root acknowledged this window and requested verified closure before
the next core campaign. This is coordination reported by that thread, not a
fresh root exclusivity observation. No gap interleaving or automatic GPU waiter
is scheduled; next admission still requires completed handover and fresh leases.

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
retry remains. Full [result and limitations](SSD-GPU-RESULT.md) are retained.

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
[complete RAM result](STATE-GPU-RESULT.md), including the retained CPU failures.

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
[GPU result and retained failure](CORE-GPU-RESULT.md).

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
See [the model-test report](Q2-FIRST-MODEL.md). This one-shot window is complete,
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
See [Q2-EXTENDED.md](Q2-EXTENDED.md), including the explicitly retained stale
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
GPU tuning or DS4 modification occurred. See [Q2-HIP.md](Q2-HIP.md) for the narrow
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
See [C1-BASELINE.md](C1-BASELINE.md). Neither attempt is permanent admission approval.

The operator handover is not an ACK or permanent shared-runner adoption; no
`ds4-ack.json` was forged. See [T0-SMOKE.md](T0-SMOKE.md). Never opportunistically
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
See [the original-weight protocol evidence](OPENAI-GPU.md). Source and results
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
[PERFORMANCE-RESULT.md](PERFORMANCE-RESULT.md). Further GPU work needs a new
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
deployment or publication. See [BENCHMARK-RESULTS.md](BENCHMARK-RESULTS.md).

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
[REACTIVE-INFERENCE-RESULT.md](REACTIVE-INFERENCE-RESULT.md).
