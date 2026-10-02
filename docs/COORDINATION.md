<!-- SPDX-License-Identifier: MIT -->
# Q2 workstream coordination

The owner explicitly authorized direct coordination messages between the Q2
and core/server LIE threads. This authorization persists: do not ask for user
confirmation for each message. GPU ownership still follows current coordinated
windows and the existing four nonblocking leases.

The last Q2 workstream run, `q2-ud-patched-r1`, completed at 2026-10-02 01:31:56
UTC: child/supervisor/transport exit 0, KFD empty, lease path identities unchanged,
owned children reaped and leases released. Sources and evidence are persistent
under this project. No Q2 GPU job, service, waiter or automatic retry remains.

The coordinated core/server thread was notified of release and took the next
CPU/GPU campaign window. Q2 profiling remains a prepared, unapplied experiment;
do not enter gaps between that campaign's individual jobs. Obtain its completed
handover before new Q2 GPU work, then repeat current in-lease admission.

The fixed runner acquires existing locks in pipeline/download/qualification/shared
order, EX|NB, checking the recorded device/inode identities. It records current
KFD and readable device/model handles, memory and power observations, source/
binary/model identities, start/end and actual exits. It stops only its own
child process group on failure. Desktop clients and inaccessible processes
limit observation; lease ownership is not universal device exclusivity proof.

No DS4 source, service, build, cache, model or qualified evidence may be changed.
No dependency installation, model conversion, foreign termination or tuning is
authorized. Runtime tests stay on `.157`; source/report checks can be local.
