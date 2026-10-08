<!-- SPDX-License-Identifier: MIT -->
# Profiling preparation history

`q2-profile.patch` adds a bounded 2048-token / 16-output rocprofv3 diagnostic to
the qualification harness. The original proposal remains here as history.
The active working tree now extends it with a process supervisor and CPU
fixtures, plus explicit GPU markers after a complete shape warmup to separate
prefill and decode from loading, smoke and setup. No model kernel is changed.
The supervisor fixtures and both Q2/UD traces now pass on `.157`; see
[phase results](../docs/Q2-PROFILING.md). Profiled wall time is not a throughput
comparison.

Before running the GPU profile: validate its process-session ownership handling on
`.157` (wrapper plus model descendant, foreign session rejection, cleanup and
real exit propagation), check the installed profiler, then acquire a fresh
coordinated GPU window and the existing four leases. Never install dependencies
or interrupt the other workstream to obtain a trace. Preserve failed attempts.

Use the trace to select one measured optimization, not a broad kernel rewrite.
Any WMMA/F16 arithmetic change requires independent operator validation and
matched model-frontier checks against the preserved Q2 candidate. Existing UD
controls and unprofiled PP/TG measurements remain required.

## Rejected Q2 down WMMA

`q2-down-wmma.patch` is a historical diff against the restored worktree's
`patches/gufo-q2.patch` and `tests/q2_operators.cpp`. It reconstructs the
compensated candidate and its focused operator checks; it is not applied.
Its operator gate passed, but the model-frontier KL was 0.002809 > 0.002.
[Results and graphs](../docs/Q2-DOWN-EXPERIMENT.md) retain the measured PP gain
without promoting the failed candidate. To reconstruct in a separate audit
copy, apply this diff at the worktree root, then use `prepare-gufo.py` with
the pinned archive. New remote runs still require the coordinated leases.
