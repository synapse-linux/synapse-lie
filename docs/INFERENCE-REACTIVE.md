# Reactive execution inside pure inference — investigation, not a speed claim

The user asks whether reactive execution can improve **model inference itself**,
not only networking, multi-agent scheduling or responsiveness. This is a separate
experimental track feeding the requirement-driven [backend evolution](BACKEND.md).
A first direct-ABI C1 timing baseline is recorded separately in
[C1-BASELINE.md](C1-BASELINE.md). The C readiness/credit dispatcher now drives scalar or native batch decode
from both worker and benchmark. Numerical kernels and their synchronization
are unchanged; an internal-forward optimization or profiler-derived speedup
is not established.

## Three different questions

1. **C1 inference:** can the same completed prefill/decode work become faster or
   use less live memory without HTTP, SSE, token rendering or slow consumers?
2. **Concurrent inference:** can readiness/resource-driven dispatch improve true
   shared batching, aggregate completed-token throughput and per-sequence latency?
3. **Serving:** can admission, fair scheduling, streaming and cancellation improve
   TTFT, queueing and behavior under slow clients?

Measure and report them separately. A gain in aggregate throughput or HTTP TTFT
is not proof of a faster C1 decode step or faster numerical kernels. `lie_flow`
implements output flow control; its CPU tests answer none of these GPU questions.

## What reactive can mean within the executor

Use explicit readiness, completion dependencies and resource ownership at useful
execution-region boundaries, not an allocation/callback object for every tensor
or tiny kernel. Admit a region when its inputs and buffer budget are ready;
release/reuse storage only after all GPU/host consumers have completed. Keep the
number of outstanding operations bounded.

The intent is to remove avoidable critical-path stalls and schedule genuinely
independent work, **not** to make the mathematics faster by calling it reactive.
Autoregressive token t+1 depends on the confirmed frontier at t. Recurrent state,
attention positions, residual joins, shared scratch and MTP verification impose
additional dependencies. Changing dispatch must preserve these edges and any
required numerical reduction order. Reactive execution cannot preempt a running
kernel or manufacture independent decode work in a single AR sequence.

| Hypothesis | Evidence needed before changing code | Candidate experiment / main risk |
|---|---|---|
| Avoidable host/device or stream-wide synchronization leaves GPU bubbles | API/kernel timeline identifies a wait broader than its real dependency, including any downstream host read | Replace one proven redundant wait with a precise completion dependency; risk of stale logits/state or premature reuse |
| Host dispatch/launch overhead is on the critical path | CPU submission spans and GPU gaps, separated from kernel service time | Bound/coalesce ready work; consider a prebuilt command plan or HIP graph only where supported; extra scheduler/event overhead can erase the gain |
| Independent branches, staging or work from other sequences could overlap | Explicit dependency/resource graph, measured device/library capability and contention | Schedule only independent regions/copies with events; shared-memory bandwidth, scratch and occupancy can make overlap slower |
| Buffer liveness is unnecessarily conservative | Completed-consumer frontier and actual peak allocation/live-range trace | Retire/reuse scratch on proven completion; memory reduction alone is not a throughput gain and cannot reclaim recurrent state still needed |
| Ready rows miss a native batching opportunity | Arrival/readiness trace and real batch API/operation behavior | Bound batching windows and schedule ready rows; waiting for peers can regress C1 and tail latency |

Graph capture, stream concurrency and fewer launches are techniques to evaluate,
not requirements or benefits inherent to a reactive design. Do not split an
already efficient fused kernel into callbacks. If existing execution already
queues work efficiently, the result may be **no gain or a regression**.

## Why the bootstrap adapter is not enough to prove an internal gain

The current experimental Gufo ABI exposes synchronous completed operations.
Moving them off the HTTP thread improves isolation, not necessarily the time
spent executing the same forward. An outer callback cannot remove barriers
hidden inside upstream Model/Session/Executor.

First obtain the working, pinned T0 baseline. If a trace identifies an internal
opportunity, isolate that execution region in the refactoring path or a clearly
versioned test fork; retain pristine Gufo separately. Do not silently edit the
reference tree or present an instrumented/modified engine as pristine. A future
async ABI must distinguish admitted/enqueued work from **completed** outcomes,
with tickets, retained buffers and failure/partial-batch rules; do not silently
change the meaning of the current ABI's successful return.

## Bounded experimental sequence

1. **Working correctness baseline.** Original immutable weights, real short AR,
   pinned sources/binary/runtime/settings and explicit engine ownership. Pristine
   Gufo remains an independent comparator; a wrapper and its direct API are not
   two independently implemented numerical backends.
2. **Trace, separately from timing runs.** Under the agreed lease, inspect CPU
   dispatch, GPU operations, synchronization, transfers, allocation lifetimes and
   idle gaps. Attribute the completed-step critical path, not the sum of spans
   that may overlap. Capture enough context to distinguish launch starvation,
   compute saturation and shared-memory bandwidth contention. No profiler/tool
   installation or machine tuning is implied.
3. **One falsifiable change.** State the dependency or idle gap to eliminate,
   expected effect and adverse cases. Preserve kernels, dtype/quantization,
   dimensions, physical tokens and operation order where the experiment allows.
   If these also change, record a combined experiment, not a pure reactive gain.
4. **Correctness before throughput.** Check complete finite frontier logits,
   expected token sequences, positions, recurrent state, tails/chunk boundaries,
   isolation and future continuation/restore where supported. Require exactness
   when only scheduling independent operations changes; any permitted numerical
   tolerance needs a predeclared justification, not relaxation after a failure.
   Add cancellation-during-flight and poisoned/partial-outcome tests for new
   asynchronous behavior. MTP requires its own acceptance/rollback checks.
5. **Matched unprofiled A/B.** Same model, precision, context/capacity, chunking,
   MTP mode/budget, sampling, physical inputs, completed output work and runtime.
   Fix warmup, run/pair order, repetition count, stop/EOS policy and timing scope
   before measurement; preserve all observations. Do not compare a fresh prefill
   with a cached-prefix delta, alter clock/power settings, or omit slow samples.
6. **Accept or reject by scope.** Report C1, concurrency and serving outcomes
   independently, with variability and memory/overhead costs. A useful C2/4/8
   improvement may remain a concurrency optimization even if C1 is unchanged;
   a C1 regression cannot be hidden by an aggregate throughput gain. Keep failed
   experiments/evidence, and retain the simpler path when added scheduling costs
   are not justified. Architectural need and speed claims are separate decisions.

## Required measurement boundaries

- **Pure PP:** completed processing of a recorded physical prompt/delta to a usable
  frontier. State fresh versus cached explicitly. Exclude model loading, input
  preparation, HTTP, text rendering and artifact writes from the interval.
- **Pure TG:** completed generation for recorded output work/context, including
  the required sampling and dependency transfers at the agreed step boundary.
  Publish actual completed tokens and EOS policy. Do not time enqueue-only work.
  GPU-only operation time is a separate diagnostic, not the same TG metric.
- **Async paths:** final completion synchronization is mandatory. Do not insert
  a global barrier after every candidate operation just for timing; that would
  destroy the behavior being tested. Both arms must reach the same usable output
  boundary. Use compatible host/device timers and avoid mixing their clocks.
- **C1 metrics:** PP/TG rates, completed-step latency distribution, CPU dispatch
  cost, launch/synchronization counts and actual peak/live memory accounting.
  No CPU model forward. Sampling/metadata/scoring on CPU must be identified.
- **Concurrency/serving metrics:** common-window confirmed-token throughput,
  per-request/sequence latency, queue time, fairness and blocked-output behavior;
  TTFT/SSE spacing are not kernel throughput. Decode/prefill interference matters.
- **Strix Halo memory:** RAM/GPU allocations share physical memory; do not add
  VRAM aperture and GTT as independent capacity or infer fit from an available
  byte counter. Track measured allocations/staging and system pressure without
  reintroducing an arbitrary 32 GiB reserve as a user requirement.

A concrete manifest must pin workload points, timing boundaries, safety/ownership
checks and acceptance rules before a hardware run. The initial investigation can
begin with a small C1 workload; concurrency and long contexts follow correctness
and measured admission. Existing DS4 results, synthetic frames and upstream
published performance cannot serve as measured LIE reactive-inference results.

## Ready-row implementation (2026-10-01)

The explicit operator request admitted the shared C inference dispatcher. It
uses existing output reservations as readiness/resource gates and never waits
for peers. `--execution serial` retains the prior direct benchmark path for
matched A/B; default `reactive` records scalar/batch dispatch and selected rows.
CPU fixtures cover zero credit, scalar fallback, different row positions,
cancellation in flight, invalid peer frontiers, all eight worker slots and
seeded heterogeneous HTTP requests against serial results. GPU validation is
recorded separately after fresh lease admission. This is the concurrent-inference
hypothesis above, not evidence of faster single-sequence numerical kernels.

The completed `reactive-suite-r2` comparison on `.157` now provides that evidence:
three measured repetitions per point, exact physical/output IDs and PP/TG frontier
hashes across arms, 4.11× C8 aggregate decode and C1 median differences within
0.35% through occupied 128K. Production HTTP also observes native batch dispatch
with seeded per-sequence output equality. Prefill remains sequential; no internal
kernel/graph or HTTP latency speedup is inferred. Full timings, variability and
retirement receipts are in [REACTIVE-INFERENCE-RESULT.md](REACTIVE-INFERENCE-RESULT.md).

## Implementation audit: how far the reactive flow reaches

The implemented flow reaches **selection and execution of ready decode rows**,
inside pure inference as well as the HTTP worker. It does not yet reach the
operator dependency graph inside a forward. Spring-style responsibilities are
implemented in C17; there is no Spring/JVM runtime or Reactive Streams TCK claim.

| Layer | Implemented mechanism | Established benefit / remaining measurement |
|---|---|---|
| HTTP reactor (`src/server.c`) | libuv callbacks, bounded admission, write completion and disconnect notifications | Network handling remains independent of synchronous model calls; correctness/lifecycle tested. No matched p99/TTFT speedup measured. |
| Flow ownership (`src/flow.c`) | Explicit demand, eight bounded token loans per job, cancellation and completion | A slow consumer bounds outstanding storage and cannot expose a cancelled token. Correctness/resource property, not faster arithmetic. |
| Worker (`src/worker.c`, `step`, `decode_ready`, `work`) | One device owner; eventfd/poll wakeups; completed prefill chunks; ready-row collection | Avoids periodic token polling. Backpressured rows are excluded from decode selection. Prefill calls are still sequential. |
| Inference dispatcher (`src/inference.c`) | Reserve output credit before execution; zero rows do no work, one uses scalar decode immediately, multiple use native batch up to eight | Both production serving and direct benchmark use this code. No peer-collection timer penalizes an isolated request. |
| Adapter (`adapters/gufo.cpp`) | Per-sequence state/sampling; `lie_sequences_decode` invokes upstream `DecodeBatch`; complete and validate outcomes before publication | Enables the measured aggregate throughput gain. Numerical code is the unchanged pinned engine; LIE does not own those kernels yet. |
| Inside a forward | Synchronous provider operations and upstream synchronization | No tensor readiness graph, asynchronous ABI, HIP-event lifetime graph, kernel preemption, new fusion or overlapping independent forwards has been implemented. |

### What improved in the measured experiment

`reactive-suite-r2` retained one warm-up and three measurements for every point.
Its serial arm uses scalar interleaving; its reactive arm combines the C dispatcher,
flow reservations **and native GPU batching**. Therefore this is a combined change,
not an experiment isolating the cost/benefit of callbacks alone.

| Concurrent sequences | Serial TG, aggregate tok/s | Ready/batch TG, aggregate tok/s | Ratio |
|---:|---:|---:|---:|
| 1 | 26.05 | 26.02 | 1.00 |
| 2 | 26.06 | 45.67 | 1.75 |
| 4 | 26.07 | 69.17 | 2.65 |
| 6 | 26.06 | 94.76 | 3.64 |
| 8 | 26.08 | 107.15 | 4.11 |

At C8, the older direct upstream observation was 107.03 tok/s. Its agreement with
107.15 is consistent with removing the missing-batch bottleneck, but that older
single observation was from another session and is not a new matched comparison.
At C1, the largest observed median difference through occupied 128K is below
0.35%. This is evidence of no material regression under the predeclared 5% gate,
not statistical equivalence or faster single-sequence mathematics.

Prefill does **not** improve in these measurements. Multi-user PP medians are
0.34–1.87% lower in the ready/batch arm; it still executes each prefill serially.
The arms ran in order, not randomly interleaved, so temperature/clock drift and
other session effects cannot be separated from scheduler overhead by these data.
All physical inputs, output IDs and full PP/final-TG frontier hashes match.

### Important limits of that evidence

The direct benchmark starts decode after all homogeneous prompts are prefilled.
It does not measure arrivals, short/long prompt interference, the HTTP queue,
slow receivers or prompt-cache reuse. The real HTTP pair established native batch
activity and per-sequence seeded output equality, but both prompts happened to
be 32 tokens. Unequal positions have deterministic CPU coverage, not a distinct
original-weight mixed-position GPU qualification in that campaign.

The worker processes up to one prefill chunk for each admitted active job before
collecting decode rows on a loop iteration. Several long prompts can consequently
delay already-ready decode by several 2048-token synchronous calls. Reactivity is
at **completed chunk/decode boundaries**, not GPU-kernel preemption. Cancellation
suppresses publication and retires state after the current call completes.
Tool-enabled turns additionally buffer a full valid tool message before emitting
its arguments, so their observed first output differs from ordinary text SSE.
Per-request batch durations overlap; summing them is not total GPU elapsed time.

The next useful experiment is mixed short/long arrivals with a slow consumer:
record queue delay, p50/p95/p99 first output and inter-token gaps, batch occupancy,
credit stalls and time spent in prefill. Only that evidence can justify a new
prefill/decode fairness policy or different chunk size. Operator-level profiling
is separately needed before changing internal synchronization or scratch reuse.
Prefix cache, MTP, PP batching and asynchronous forwards remain distinct missing
features; none is supplied by the current reactive dispatcher.

The later [full-prefill/HTTP campaign](FULL-PREFILL-HTTP-RESULT.md) supplies
absolute serving timings, but no before/after HTTP scheduler comparison. Its
100K follow-up still re-prefills the entire history (71.79s): the implemented
ready-row flow does not confer state-cache reuse.
