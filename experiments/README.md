<!-- SPDX-License-Identifier: MIT -->
# Prepared diagnostic, not applied

`q2-profile.patch` adds a bounded 2048-token / 16-output rocprofv3 diagnostic to
the qualification harness. It does not change model kernels. It is preserved
for review and is not part of the tested active runner. Do not use its profiled
wall time as a throughput comparison.

Before applying/running: validate its process-session ownership handling on
`.157` (wrapper plus model descendant, foreign session rejection, cleanup and
real exit propagation), check the installed profiler, then acquire a fresh
coordinated GPU window and the existing four leases. Never install dependencies
or interrupt the other workstream to obtain a trace. Preserve failed attempts.

Use the trace to select one measured optimization, not a broad kernel rewrite.
Any WMMA/F16 arithmetic change requires independent operator validation and
matched model-frontier checks against the preserved Q2 candidate. Existing UD
controls and unprofiled PP/TG measurements remain required.
