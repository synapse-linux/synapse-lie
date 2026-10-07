<!-- SPDX-License-Identifier: MIT -->

# Validate GPU profiling timestamps before another model diagnostic

The original128K rocprof trace records178605 kernel dispatches and4187 copies
with zero device duration. Its host API/dependency intervals remain useful,
but those device values cannot rank kernels or establish utilization. The
continuous selector component after the reboot has48 positive HIP event
intervals. This does not establish that rocprof timestamps are now valid.

This bounded diagnostic reuses the exact saved selector component72f824dc.
It invokes the installed `/opt/rocm/bin/rocprofv3` with kernel, HIP and memory
copy tracing and both CSV and ROCPD output. The profiler script hash remains
ecae3de7, matching the previous model diagnostic. No numerical code, model,
compiler, dependency, service, tuning or model benchmark input changes.

The process normally exits after the synthetic fixture, allowing inspection
of complete exporter output without the long-running HTTP server's shutdown
path. Compare valid kernel/copy durations in both representations, HIP event
intervals, whole-process completion and trace schema. A clean short-process
result alone does not qualify the model server's profiling/shutdown path.
All instrumented timings are diagnostic and ineligible as throughput results.

The runner uses the current persistent boot epoch and five existing leases.
It checks the installed profiler identity, retains actual process/command exits,
owns only its child group, and requires collection/hash verification before
release. The CPU fixture replaces the profiler with an exec-only shim and
checks profiler identity refusal, argument construction, successful/finite-error/
unsafe-error completion, timeout retirement and release semantics on .157.

[Source binding](../config/q2-profiler-clock-source.json),
[runner](../tools/q2-profiler-clock-window.py),
[CPU fixture](../tests/q2_profiler_clock_window_test.py).
At preparation there is no GPU result or reservation; a fresh admission is
required. The30TG/1500PP model objective remains unchanged and unachieved.
