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

## Latest one-shot admission

After the operator confirmed DS4 was coding and authorized proceeding following
an idle-node check, a bounded one-shot test was attempted using all known legacy
and shared leases. This did not create an ACK on behalf of DS4 or grant a permanent
admission exception. Both 18:49/18:51 UTC attempts were refused before model open.
At 18:53 UTC DS4 `native-perf` was actively benchmarking and its supervisor held
the download, qualification and shared LIE/DS4 locks. ACK/register remained absent.
See [T0-SMOKE.md](T0-SMOKE.md). Do not opportunistically enter between benchmark
jobs: an actual campaign-window handover is needed before another attempt.

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

**Hardware and heavy-I/O tests remain blocked until this coordination is
confirmed.** CPU tests are on .155. Remote reconnaissance reads small receipts,
sysfs/proc and bounded GGUF metadata only (about 33 MB), not tensor payloads.
No inference was launched on either host by this fork. Local `.155` serial HIP
source compilation/linking and no-model/synthetic tests are recorded separately;
no remote GPU build or model execution is implied by their success.
