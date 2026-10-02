<!-- SPDX-License-Identifier: MIT -->
# Q2 workstream coordination

The owner explicitly authorized direct coordination messages between the Q2
and core/server LIE threads. This authorization persists: do not ask for user
confirmation for each message. GPU ownership still follows current coordinated
windows and the existing four nonblocking leases.

The initial Q2 campaign retired at 2026-10-02 01:31:56 UTC and handed its
window to core/server. Core-gpu-r2 completed at 02:13:52.976 UTC with children
retired, KFD empty, four lease identities unchanged/free and port 8000 empty.
The core thread explicitly returned the window to Q2 until verified release.
Its next prefix-cache implementation is local only while Q2 owns this window.

Q2 profiler CPU validation and both traces completed successfully. The down
optimization passed operators but failed the declared model-frontier limit;
its source is retained as a rejected experiment and the active runtime restored.
Final GPU sampling retired at 03:12:12.768 UTC. Fresh closure at 03:14:56.579 UTC
verified 34 command PID/start identities and owned groups retired, KFD empty,
four expected lease identities acquired EX|NB and released. All eight arms'
results were collected and hash verified, including three operator failures.
The core thread received the explicit handover. No Q2 remote job, waiter or
automatic retry remains; further Q2 GPU work needs a new coordinated window.
The core thread may proceed with its next cache qualification campaign.

The fixed runner acquires existing locks in pipeline/download/qualification/shared
order, EX|NB, checking the recorded device/inode identities. It records current
KFD and readable device/model handles, memory and power observations, source/
binary/model identities, start/end and actual exits. It stops only its own
child process group on failure. Desktop clients and inaccessible processes
limit observation; lease ownership is not universal device exclusivity proof.

No DS4 source, service, build, cache, model or qualified evidence may be changed.
No dependency installation, model conversion, foreign termination or tuning is
authorized. Runtime tests stay on `.157`; source/report checks can be local.

The next integer scheduling candidate is prepared locally while core owns
state-gpu-r1. Device-only assembly analysis executes no GPU code. All new
remote checks (including CPU fixtures) wait for the explicit handover; no
background retry or implicit ownership of an idle gap is scheduled.

Core explicitly returned the window after state-gpu-r1 finished at
2026-10-02 04:06:08.841 UTC. Its reported fresh closure at 04:06:08.842 verified
32 supervisor/child identities retired, KFD empty, expected four leases free,
controller absent and no port8000 listener. Q2 acknowledged ownership for the
integer scheduling qualification; every build/GPU arm still performs its own
fresh admission. Core remains offline for reporting until Q2's verified release.

The integer scheduling campaign finished its final operator arm at
2026-10-02 04:20:13.819 UTC. Both candidates fail exact replay and were reverted;
no full-model run followed. Fresh closure at 04:22:17.419 UTC verifies four
runners absent, 15 command PID/start identities and owned groups retired, KFD
empty and the four expected lease identities acquired EX|NB and released.
All 150 artifacts are collected/hash verified. Core received explicit handover;
no Q2 remote job, waiter or automatic retry remains. Evidence is retained in
`evidence/q2-register-window-release.json` with closure command exit 0.
