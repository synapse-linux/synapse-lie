<!-- SPDX-License-Identifier: MIT -->
# Profiling preparation history

`q2-profile.patch` adds a bounded 2048-token / 16-output rocprofv3 diagnostic to
the qualification harness. The original proposal remains here as history.
The active working tree now extends it with a process supervisor and CPU
fixtures, plus explicit GPU markers after a complete shape warmup to separate
prefill and decode from loading, smoke and setup. No model kernel is changed.
This work is awaiting `.157` validation; do not treat source preparation or
profiled wall time as a throughput comparison.

Before running the GPU profile: validate its process-session ownership handling on
`.157` (wrapper plus model descendant, foreign session rejection, cleanup and
real exit propagation), check the installed profiler, then acquire a fresh
coordinated GPU window and the existing four leases. Never install dependencies
or interrupt the other workstream to obtain a trace. Preserve failed attempts.

Use the trace to select one measured optimization, not a broad kernel rewrite.
Any WMMA/F16 arithmetic change requires independent operator validation and
matched model-frontier checks against the preserved Q2 candidate. Existing UD
controls and unprofiled PP/TG measurements remain required.
