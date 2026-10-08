<!-- SPDX-License-Identifier: MIT -->
# HC qualification preparation

The fixed comparison remains Q2 **1585.308983 PP /25.16079073 TG** versus
UD **1685.777092 PP /24.34174251 TG**, exact2048/tg128. The PP target needs
**76.991736ms** less time or **6.337447%** more throughput. No new GPU result
or performance increment is available.

## Priority and realistic opportunity

| Priority | Mechanism | Reason to test | Limit |
| --- | --- | --- | --- |
| 1 | Reuse HC normalized inputs and stage injection coefficients in existing LDS. | Removes a specific repeated input pass; complete42-case fixture is prepared. | Historical injection39.548835ms alone is below the77ms gap. Producer work and40MiB dot write/read traffic must be charged. |
| 2 | Four owner threads compute and publish the final RMS scales. | Both compiler probes reduce VGPR84→65 without private spills. | Only the finishing scale calculation changes. The145.803160ms combine region is not a saving estimate; an extra barrier may erase the gain. Compiler occupancy stays16. |
| 3 | Preserve whole640-value row scaling while improving IQ2 producer/packing ownership. | Targets239.499759ms gate/up and17.096259ms packing in the saved profile. | Requires a larger redesign. Naive per-consumer conversion adds traffic; no implementation or measured win exists. |

These ranks are engineering judgments, not measured probabilities. The saved
profile is the1571 lineage, not a fresh1585 trace. Its5.090460ms inter-kernel
gap cannot account for the77ms target; increasing C1 callbacks or threads is
therefore a weaker candidate than changing GPU work. Existing qualified
comparators and rejected experiments remain intact.

## Completed analysis and launch tooling

[The analyzer](../tools/analyze-q2-hc-inject-reuse-component.py) requires collection
and a released, matching window before accepting the component. It verifies
all200 outputs,57 logged scratch checks,19 logged Q8 checks,42 timings, complete
case coverage, payload sizes, guards, capsule inventories, original leases and
command exit codes. Safe numerical rejection retains full differing arrays
and all timings. Exit2 device/guard/unwritten-output faults are not adopted.
The fixture's additional post-timing scratch/Q8 finite checks remain labeled
as completion checks rather than invented per-output records.

The timing parser checks actual arm order and both binary32 raw identities and
printed durations. Zero/nonfinite HIP durations remain invalid. Independent
positive complete-cycle wall durations remain labeled as including event
submission and terminal synchronization, not pure GPU time or model throughput.
Two warmups and five alternating measurements preserve all samples. This does
not change the frozen headline model benchmark or its saved comparison.

[The freezer](../tools/freeze-q2-hc-inject-reuse-plan.py) refuses to create a plan
without actual collected35/35 Debug and35/35 ASan/UBSan host checks on `.157`.
It binds the unchanged1027-file parent, current tested fixtures, original Core
closure and supplemental retired CPU identity. No plan has been frozen yet.
[The controller](../tools/q2-hc-inject-reuse-window.py) rechecks the original CPU
lease and four GPU lease inodes, historical process groups, registry, KFD,
model stat tuples and existing thermal policy. It retires this window's actual
host/component groups at release. It performs no process termination or cleanup.
[The phase launcher](../tools/q2-hc-inject-reuse-phase.py) rejects changed or
released admissions, existing cohorts and model arms before launching a
component. A failed remote check cannot invoke the GPU runner.

Ten focused parser/phase regression methods are registered in the new
`q2_hc_inject_reuse_analysis` CTest. They have **not run locally or remotely**;
only syntax/source checks have run. Their dependencies are now included in
the remote capsule. New host checks and controller runtime qualification remain
pending; the prior34+34 results do not qualify this changed wiring.

## Borrowed workspace boundary

Source review of the retained executor places each HC mix after the previous
combine and before the next MoE down writer, on the existing ordered stream.
`down_e` is allocated as `max_batch * top_k * hidden` F32 values. At2048 rows,
top10 and hidden2560, it has209,715,200 bytes; compact injection dots need
20,971,520 bytes. Capacity and source order make it a plausible borrow, but
do not establish safe lifetime in every path. The current component owns
independent buffers and production has not adopted the borrow.

Production integration must reject pending MoE consumers, validate the actual
scratch view/capacity and aliases, preserve same-stream producer/reducer order,
and invalidate output identities on launch failure or unsupported routes.
Cancellation, row scratch views and predictor paths need explicit coverage.
This component-only plan has no model arm. Analyze it after collection and
release; qualify the borrow before freezing a separate original-model trial.

## Current external blocker

The third consecutive Core handover check fails before SSH connection with
exit255 and `No route to host`. All three command/exit/stderr records remain in
`evidence/q2-hc-inject-reuse-component-preparation/`; the newest is
`core-handover-r3-command.json`. Core separately confirms its own non-use of
`.157`; this is not a fresh global availability observation. No staging,
host/build/model job, GPU window, lease, reservation or waiter starts.

Last verified release remains2026-10-06T04:27:46.757600UTC,
SHA e64145d666ce7ebcd470a7587a54979d6b11c8c909b073cc639c3d8071a652db.
Reconnection must precede fresh coordination, host checks, plan freeze and
component execution. Saved controls, Q4 and the full curve remain deferred.
