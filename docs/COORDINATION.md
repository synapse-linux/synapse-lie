# DS4 / synapse-lie coordination

## Additional target .161 — Strix Point fork

The latest operator instruction explicitly selects **copying** the existing
original UD shards from .157 to .161, retaining every source file unchanged.
Do not fall back to Internet downloading. WAN R3 was deliberately stopped
through its verified supervisor pidfd at 10:27:42 UTC, child exit -15,
supervisor exit1, llama restored and lease released; the verified first shard
and 31584485376-byte second-shard partial are preserved and fsynced.

Q2's packed window release at 10:29:49 UTC records all owned processes retired,
empty KFD and four unchanged/free leases. Core explicitly yields the next slot
to this copy and waits for its verified closure. `strix-point-ud-copy-direct-r1`
started at 10:36:05 UTC: source controller2479176, sender2479177/start150275949,
outbound SSH2479178; receiver4509/start304908 on .161. All four established
source leases are held EX|NB with start/end registration and thermal/client
guards; the receiver separately holds the private .161 lease and stop/restore
grant. The sender uses read-only/O_NOATIME source FDs, retains source stat
identities, and sends only missing suffixes. The destination rehashes its saved
prefix and verifies every completed shard against the pinned official SHA-256.

Payload bytes flow directly between the two remote hosts. A temporary local
SSH agent is constrained to the initial .157 login and the .157-to-pop@.161
hop, with finite key lifetime and owned-process cleanup. The private key is
never copied to either server; no global SSH configuration or authorized_keys
file changes. Host trust uses the already-known public host keys in a private
run file, with strict host-key checking. Both source and target use persistent
exclusive LIE directories. The copy has a four-hour bound, preserves incomplete
destination bytes on failure, and must publish verified retirement before core
or Q2 can enter. The historical WAN/relay records below remain evidence only.

The operator subsequently explicitly authorized stopping llama:
`llama si può stoppaare`. This grants the previously proposed temporary
`llama-router.service` stop/restore for the .161 diagnostic, pinned UD staging
and tests. The previous no-foreign-stop rule is overridden only for that named
service. Admission must still check current clients, thermal/resource state,
and retain owned cleanup; restore the service if it was active before the window.
A persistent LIE campaign lock under `/home/pop/workspace/synapse-lie` serializes
our own work, with PID/start and inode identity recorded. It is not evidence of
adoption by other applications: the window derives from the operator handover.
The initial .161 phases used no .157/.158 resource. The later read-only .157
copy window is separately recorded below; no .158 resource is used.

`strix-point-gpu-probe-r2` completed at 08:52:45 UTC with real HIP/rocBLAS exit0,
owned container removed, KFD empty before restoration, llama active again and
the unchanged persistent lock released. R1 retains a pre-launch refusal on the
retiring service's transient kernel KFD entry; no foreign client was ignored.
The known process is now given a bounded retirement wait before admission.

At the 09:15 UTC snapshot, `strix-point-ud-download-r2` holds the next admitted
LIE I/O window on .161; service inactive, KFD empty and CPU/GPU near40 C. The
sequential first transfer was deliberately stopped through its verified owned
supervisor pidfd; it restored llama and released the lease before R2 started.
R2 verifies/resumes the partial in a bounded eight-range pipeline. Its cleanup
must restore llama and release the lease on completion/error. A future LAN
copy of original pinned weights was discussed with root/Q2/Spark; .157 is still
owned by the root SSD campaign. No remote source access or payload copy from
.157/.158 has been admitted.

The operator subsequently answered `procedi con il tuning` to the concrete
96 GiB TTM + current-kernel initramfs + reboot proposal. This authorizes that
specific .161 maintenance operation, with backup/rollback, post-boot HIP
verification and resumption of the preserved download. It does not authorize
clock, fan, power, page-pool or other-host changes. R2 was deliberately retired
through its verified supervisor pidfd at 09:38:50 UTC: child exit -15,
supervisor exit 1, llama restored active, lease released, no cleanup failure.
Its 17129537536-byte second-shard partial and verified first shard were fsynced
before maintenance. The preparation receipt will retain the old boot identity,
initramfs backup and exact new file identity; a written config alone is not
evidence that HIP sees the requested memory limit. Maintenance completed:
initramfs rebuild exit0, reboot command exit0/SSH255, new boot ID observed;
the post-boot HIP/rocBLAS probe passes with total103079215104 bytes (96 GiB).
Its own lease retired at 09:46:29 UTC and llama was restored.

After root's SSD R4 release and Q2's explicit handover, the read-only source
window `ud-copy-r1` ran on .157 from 09:52:28 to 09:57:00 UTC under all four
established EX|NB leases, identity-checked and registered start/end. The source
opened only the four official pinned trunk shards read-only/O_NOATIME; it did
not import sibling project source or build artifacts. Sender PID2463485,
start_ticks150014282, was deliberately retired through verified pidfd because
the all-Wi-Fi SSH relay sustained only about10 MB/s. The .161 receiver retained
the additional partial bytes, exited1 on EOF and restored llama at 09:57:01 UTC.
Sender/controller exit1 and the interrupted result are preserved, not PASS.
Postflight found the source process absent, KFD empty, all four model stat
identities unchanged and all four unchanged leases reacquirable nonblocking.
Q2 received the release message before its next slot. No Point job/waiter
remains on .157. Only the independent .161 WAN resume R3 is active at09:59 UTC;
its eight-hour deadline, thermal/client supervision and stop/restore rules apply.

The owner requested the UD port and tests on `pop@192.168.5.161`; this fork owns
only its `feature/strix-point-ud` work and persistent test directories under
`/home/pop/workspace/synapse-lie`. Read-only inspection at 07:41 UTC on 2026-10-02
found `llama-router.service` PID2211125 with `/dev/kfd` and renderD128 open.
The service can autoload models. It was not stopped, signalled, reconfigured or
queried for inference. An owner-release question remains pending; no GPU lease,
model payload access, remote GPU build or implicit waiter was started.

Synthetic CPU tests are authorized by the test request. The target runner masks
GPU visibility, and headless container tests expose no GPU device nodes. All
private children retire; the existing service and unrelated containers remain
untouched. Recorded temperatures and actual exits are retained, including the
first container sensor-discovery failure. These tests do not consume a GPU window.

Any later GPU, model hash/download or remote HIP build requires an actual
.161-specific handover/lease agreement and fresh admission with resource and
foreign-client checks. Do not copy .157 DS4 lock paths to .161 or infer ownership
from a newly created private lock. No .157/.158 resource is used by this fork.
See [the target inventory and qualification gates](STRIX-POINT.md).

Follow-up at 08:24 UTC again observes the same KFD holder; the 08:36:57 UTC
service status remains active/running, with no observed established 8080
connection. This is not an ownership release. The operator was asked whether
to authorize a temporary `llama-router.service` stop and restoration; no explicit
answer is recorded. The service has not been changed. Additional synthetic
diagnostic controls and no-device startup passed, and only 1391 bytes of official
model repository metadata were fetched. No model payload, GPU initialization,
device probe `--run`, lease acquisition or implicit background waiter occurred.

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

The user now permits non-performance tests on the editing Strix Halo `.155` as
well as `.157`, and explicitly requests temperature care. New local CPU builds
and fixtures use `tools/thermal-run.py`, at most `-j2`, continuous sensor records
and an 85 C ceiling (or lower sensor max/critical threshold). Thermal refusal /
termination preserves actual exits and signals only its owned child group;
no power, frequency or fan tuning. Original-weight performance comparison stays
on `.157` under fresh ownership/leases. This is not GPU-run or heavyweight model
hash authorization on the editing host. The Q2 thread owns the next `.157` window
while this thread implements and CPU-tests the C17 SSD store locally.

## Latest completed window — C17 RAM state/cache

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
