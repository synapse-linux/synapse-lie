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

## Latest completed run — initial Q2 synthetic GPU operators

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
the completed operator window is not a standing lease.** CPU tests are on .155.
Read-only reconnaissance reads small receipts/sysfs/proc and bounded metadata,
not tensor payloads. The separately authorized r4 model run did read original
weights and execute HIP on .157; it passed a bounded serving smoke, not a numerical
or performance qualification. The later separately admitted C1 measurement is
an embedded-provider timing baseline, not an independent numerical or speedup
qualification. Local compilation/no-model/synthetic receipts retain their original
scope. No remote compilation, dependency installation or model conversion occurred.
