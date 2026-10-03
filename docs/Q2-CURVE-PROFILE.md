<!-- SPDX-License-Identifier: MIT -->
# Attributing the Q2/UD gap on the HTTP context curve

The first [complete curve](Q2-CANONICAL-HTTP.md) puts the largest prefill
deficit at depth zero: Q2 takes 2.460576 seconds versus UD 1.323863 for the
same 2040 new tokens. The gap is 1.136713 seconds. At 128K the gap shrinks to
0.011320 seconds. Optimizing the old repeated counting fixture cannot explain
this behavior. The acceptance target remains both PP and TG at every point.

## Controlled follow-up

First repeat the complete uninstrumented curve in reverse model order,
UD then Q2, with unchanged numerical providers and identical HTTP workload,
settings, calibration and depth order. Do not drop system caches or mutate
the original model files. Preserve the previous Q2-then-UD pair separately.
This investigates process/order/cache sensitivity; two observations do not
provide a robust confidence interval for a sub-percent difference.

Then run both models on the same complete workload with diagnostic host
instrumentation. `tools/prepare-q2-curve-profile.py` starts from the measured
providers and changes only `ngram.cpp` and the host `Executor::Forward`
entry/exit. It adds two first-party diagnostic headers; all other 1018 Q2 /
1017 UD files remain exact. No numerical kernel or arithmetic is edited.

Each Forward observation records monotonic start/end, prefill/decode mode,
initial position, token count, successful completion, and PLE counter deltas:
hashing, preparation, waiting, duplicate copying, row decoding, cache hits,
misses, `pread` calls and requested/returned bytes. `/proc/self/io` read-byte
deltas cover all storage I/O by the process during that span, not exclusively
PLE. Process row-cache capacity, worker count and direct-I/O mode are retained.

The analyzer aligns these spans with the retained HTTP request intervals and
checks every cached/new/decode frontier. It rejects missing calls, incomplete
work, crossing request boundaries, reordered phases, incoherent counters and
incorrect source/build identities. Every measured request is independently
reconstructed from the pinned Gufo recipe and its actual prefix reply.

## Timing boundaries

The diagnostic server has a distinct build identity and requires an explicit
profile flag. Its result is marked ineligible for headline performance; the
ordinary curve analyzer rejects it. The uninstrumented control and profile
must never be averaged together.

`blocked_ns` is host time inside the PLE condition-variable wait. Previously
queued GPU work can overlap it; this is not a direct measure of GPU idle time
or recoverable critical-path time. `pread_ns` and row-decode time are sums
across concurrent I/O workers and can exceed wall time. They must not be
added to the Forward duration. Counter atomics, clock reads, process-I/O reads
and JSON output add instrumentation overhead; no speedup claim uses this run.

If PLE wait and storage amplification explain a substantial portion of the
short-context deficit, the next candidate should address that mechanism on
the same curve. If they do not, profile the GPU/CPU remainder. The existing
reactive lookahead and HC stage experiments remain hypotheses to test, not
percentages to add to these measurements.

## Validation and ownership

Five local syntax checks pass for both instrumented providers and the host
fixture. The prior comparison replays with exactly the same JSON data after
the analyzer refactor. On `.157`, the new writer/counter and request-attribution
checks pass with the full **19/19 Debug and 19/19 ASan/UBSan** cohorts.
Fixtures cover parallel counter updates and incomplete Forward rejection;
they are not model inference or performance evidence.

Fresh admission at 2026-10-03T22:26:44.209344+00:00 rechecks the prior 30
processes retired, KFD empty and all four unchanged original leases free.
The shared registry contains no intervening core admission. The bounded
window covers the host cohort, reversed uninstrumented pair and separate
Q2/UD PLE profiles. No dependency installation, tuning, foreign termination,
model mutation or persistent service deployment is included. Final runtime
results and verified closure will be recorded when all arms terminate.
