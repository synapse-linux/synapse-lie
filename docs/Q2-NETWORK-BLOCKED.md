<!-- SPDX-License-Identifier: MIT -->
# Q2 target blocked by required machine connectivity

The objective remains Q2 performance parity with UD across the agreed curve.
It is not achieved. The fixed point remains1585.308983 PP /25.16079073 TG for
Q2 versus1685.777092 PP /24.34174251 TG for UD. The required PP improvement is
6.337447%, or76.991736ms. No new model or curve result exists.

The previous goal turn made concrete progress: checkpoint661a6e0e completed
the next HC component's analyzer, capsule dependencies and bounded launch
preparation. Current source and recorded identities remain unchanged. New
host35+35, component runtime/numerics/timing, borrowed-workspace qualification
and the original-model trial are still unexecuted.

The same network blocker spans three consecutive goal turns:

| Goal turn | Evidence | Actual result |
| --- | --- | --- |
| `01a10f88-6f0f-7041-9cdd-56a72791d5cf` | `core-handover-command.json`,04:57:15UTC | SSH255, No route to host before connection |
| `01a10fa0-7ed0-7f82-9781-e671f9418b66` | `core-handover-r2-command.json`,05:12:40UTC; r3,05:21:35UTC | Same SSH255 before connection; offline preparation completed |
| `01a10fb2-8190-77e3-ab2e-41f1552ae3bb` | `core-handover-r4-command.json`,05:32:30UTC | Same SSH255 before connection; process terminal |

All raw commands/stdout/stderr are retained under
`evidence/q2-hc-inject-reuse-component-preparation/`. The latest command exits
at2026-10-06T05:32:30.892575UTC. No observation timeout is treated as process
completion: the local SSH handle actually reports terminal exit255.

The owner's required `.157` test environment cannot be replaced with another
host. The next prepared experiment needs its fresh host checks and GPU timing;
choosing further changes without these measurements would not validate the
target. There is no live job to wait for, no GPU window/lease/reservation and
no scheduled retry. No remote connection, staging, build or model job starts.
Network recovery is required before the next execution can proceed; permission
or additional dependency authorization is not the blocker.

After reconnection: revalidate Core/global closure and original leases; collect
fresh host35+35; freeze/admit and run the prepared HC component; collect/retire/
release before analysis; qualify workspace lifetime and use a separate window
for the new original2048/tg128 model. Preserve all saved controls and benchmark
scope. Full-curve qualification follows fixed-point parity as already agreed.

[Prepared candidate and gates](Q2-HC-QUALIFICATION-PREPARATION.md).
