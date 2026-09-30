# T0 serving lifecycle qualification — prepared, target run pending

This increment hardens the C server and prepares a bounded, lease-gated HTTP
protocol. CPU fixture passes are **NOT model inference**, independent numerical
qualification, native batching or performance evidence. The previous successful
GPU smoke/baseline used earlier binaries and remains historical.

## Current admission observation

At **2026-09-30 22:09 UTC**, a read-only target probe observed a DS4 benchmark
campaign (`native-perf`, Q4 model mapped), a KFD client and all four known leases
held. The pipeline lease belonged to the enclosing campaign. The shared lease
was held too; no formal acknowledgement file was present. See
`evidence/t0-lifecycle-activity-r1/{receipt,probe}.json`.

No LIE GPU run, model read, target build, lock acquisition or staging was attempted.
No foreign process was signalled. There is no background retry/waiter; do not enter
between that campaign's jobs. A future run needs a fresh handover and the full
[coordination protocol](COORDINATION.md). This observation is dated, not a live
availability assertion.

A fresh operator window at **22:42 UTC** (`hai a disposizione gpu`) was followed
by read-only probe `t0-lifecycle-activity-r2`: GPU idle, KFD empty, no inference or
model handles, no holders of the known leases. A one-shot attempt may now be
prepared, still conditional on all lease/admission gates. No ACK is fabricated
and no permanent exclusivity inferred.

## Server changes

The worker now validates every successful AR decode result **before token text
lookup, token accounting or flow publication**:

- emitted count is 0 or 1, stop is 0 or 1, and one must indicate progress/stop;
- returned position equals the previous validated frontier plus emitted count,
  including un-emitted EOS, and stays within the configured context;
- an emitted token is nonnegative and inside the loaded vocabulary;
- successful token rendering reports no more bytes than the reserved slot.

Malformed successful returns and unexpected prefill/decode/text failures stop
this worker runtime (`FAILED`), fail existing peers and refuse new requests.
They are not request-local permission to keep using uncertain state. Cancellation
remains a separate, nonpoisoning path; pre-admission invalid chat/context remains
a nonmutating refusal. No retry/fallback or additional HIP synchronization occurs.

Management exposes `scheduler.executor` owner-dispatch counters/phase and
`scheduler.output_blocked`. These make completed versus outstanding calls and a
credit stall observable without prompts or per-token event logging. They do
**not** prove GPU-kernel submission/preemption. See [HTTP.md](HTTP.md).

## Predeclared real-model protocol

The existing one-shot `tools/smoke-model.py` retains its default `http-smoke-v1`
suite. Explicit manifest `suite: "http-lifecycle-v1"` selects the new protocol:

- existing original UD-Q4_K_XL shards; original stat identities, no weight hash/
  conversion/download; no MTP or vision;
- context 4096, chunk 2048, **max_active 2**, greedy, thinking off, fresh sessions;
  this is interleaved single-row execution, **not native batching**;
- API/management loopback 19879/19880; request deadline 120000 ms; existing
  admission, private runtime, foreign-client observation and owned-child cleanup;
- manifest must record the current runner and `serving_checks.py` SHA256, binary/
  build identity, explicit matching `request_settings`, source identity, models,
  locks and fresh one-shot authorization. The helper must be a regular non-symlink
  file staged in the exclusive run directory. Hash/settings drift refuses admission.

First run the existing six predeclared JSON/SSE smoke requests, now also validating
physical counts, timing schema/rates and exactly one SSE timing finish. The
additional `tools/serving_checks.py` library then performs, in order:

1. A fresh nonstream arithmetic peer reference (`2 + 2`, exact stripped `4`,
   max_tokens 16), validating usage and completed-call timing.
2. A 240-line public synthetic-text prompt plus counting instruction; max_tokens
   512. Observe a prefill dispatch, disconnect, require one corresponding first
   cancellation observation and quiescent retirement, with no successful outcome.
3. A counting prompt with max_tokens 512. Receive initial content, observe decode
   dispatch, disconnect and require the same cancellation/retirement invariants.
4. Send a long SSE counting request on a socket with a small receive buffer and
   **do not read**. Require `output_blocked=1`, phase `none`, fewer than 512 emitted
   tokens and stable generated/decode-start counters over five 100 ms observations.
   While it remains stalled, the arithmetic peer must match the fresh reference
   for exact content, usage and finish. Close the stalled client and require
   cancellation/retirement.
5. Repeat the arithmetic peer after cancellation; exact match and final zero
   queued/active/blocked, no outstanding dispatch, delta three completed / three
   cancelled / zero failed for the additional protocol.

Prompts are fixed by `original_profile()` in the hashed helper; the CPU test uses
an explicitly separate synthetic profile. Management polling is bounded (30 s
per wait); HTTP operations have 10 s timeouts and 1 MiB response bounds. No model
request is retried. A missed dispatch/pressure window or early completion is
**INCONCLUSIVE**, not a successful cancellation or a discarded sample. Errors,
all snapshots, partial SSE frames and decisions remain in `results/lifecycle.jsonl`.
The supervisor still retains process exits, full cleanup and identity postflight.

A future successful overall state is
`MODEL_HTTP_LIFECYCLE_PASS_NOT_NUMERICAL_QUALIFICATION`; it is **not recorded for
this increment**. Per-request timing here validates a contract, not a throughput
baseline. Same-backend peer repeatability is not a pristine numerical comparator.
GPU error injection, complete T0 numerical qualification, prefix reuse, SSD
persistence, native batching and MTP remain separate gates.

## Local validation

- `t0-worker-frontier-red-r1`: old worker publishes a synthetic invalid-position
  result; the new regression fails at runtime (exit -6, core dumps disabled).
- `t0-worker-frontier-green-r1`: corrected C guards and dispatch/cancellation tests
  pass twelve suites with GCC/Clang/ASan/UBSan and the adapter header check.
- `t0-lifecycle-helper-r1`: initial thirteen-suite pass, including the real TCP
  client protocol against a visibly synthetic CPU server; no target/GPU execution.
- Final closure and HIP link receipts are recorded in PROGRESS.md / evidence index.

Tests cover thirteen provider faults, no token lookup/publication for malformed
frontiers, no queued-peer dispatch after poison, prefill/decode cancellation with
controlled barriers and consumer release before return, credit stalls, metadata
refusals, helper identity checks and missed-window refusal. No production fault
switch or CPU model forward is added.
