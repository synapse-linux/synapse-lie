# Reactive execution pattern

## Decision and present implementation

The runtime is designed as **demand-driven streams with bounded asynchronous
boundaries**, not merely an HTTP server with callbacks. libuv implements the
network Reactor (I/O readiness dispatch); it does not by itself implement
reactive inference. A responsive, resilient, elastic, message-driven system
also needs bounded admission, feedback, isolation and lifecycle ownership.

The first implemented component is `include/lie/flow.h` + `src/flow.c`, a C17
per-sequence subscription/flow-control primitive. It has CPU tests with real
threads, finite storage and Linux eventfd wakeups. It is now connected to the
C worker and HTTP/SSE path, with a linked opt-in Gufo provider. End-to-end CPU
checks use a separate synthetic provider. Separately, the original-weight
`t0-model-lifecycle-r1` GPU run passes bounded HTTP/SSE, dispatch cancellation,
TCP backpressure, peer isolation and retirement. This is **not full numerical/
hardware qualification**, native batching or a reactive performance gain.
No-model startup still returns 503 for chat. The publisher obeys [LIE-owned contracts](BACKEND.md); an explicit
embedded Gufo adapter is permitted initially, followed by requirement-driven
refactoring toward owned execution. It is not claimed as reimplementation.

The later [native tool extension](SERVER-TOOLS.md) uses the same worker/flow but
buffers complete tool-enabled turns before publishing parsed calls. Its CPU
protocol tests do not inherit the older real-model slow-client qualification.

This is not Project Reactor, Rx, a JVM dependency or a Reactive Streams TCK
compliance claim. It adopts demand, serial signals, cancellation and bounded
resource ownership. Credits are **confirmed tokens**, whereas one data signal
may contain a chunk of several tokens; this is deliberately not the formal
Reactive Streams item-count protocol. No reactive wrapper per tensor/kernel.

## End-to-end topology — T0 binding implemented; real-model gate open

```text
HTTP admission -> bounded preparation queue -> device-owner scheduler
                        (CPU metadata only)      | bounded completed GPU step
                                                 v
                                confirmed output -> per-sequence bounded flow
                                                          |
                                                          v
                                                       SSE writer -> socket
                                                          |
                      request(credits), buffer release <--+ write completion
                      cancel/deadline --------------------> stop admission

Disk worker <-> bounded snapshot jobs/completion messages <-> device owner
Management -> snapshots/counters (never waits for model forward or disk restore)
```

- **Publisher:** LIE's device-owner worker with an explicit transitional or
  owned execution implementation, publishing only completed, confirmed output.
  GPU submission is not completion. Drafted MTP tokens never enter the output
  stream before verification. No callback invokes more inference inline.
- **Subscriber:** one ordered output owner. Nonstream JSON and tool-enabled
  turns consume the same flow into a preallocated bounded aggregation buffer,
  not an unbounded sink. Their demand is replenished on aggregation, unlike
  ordinary text SSE's write-callback-driven demand.
- **Subscription:** sequence-local token demand, bounded byte storage, dispatch
  tickets, cancellation and a single terminal outcome. No global hot multicast
  stream and no replay buffer pretending to be recurrent/KV state persistence.
- **Scheduling boundary:** one LIE device-owner scheduler, not one GPU thread
  per request or a second upstream serving scheduler. The transitional engine is
  disclosed and isolated, not hidden or claimed to be the owned numerical layer.
  T0 performs bounded rendering/tokenization on that worker too, a known limit.
  Separate preparation/disk workers remain future work, not implemented queues.
- **Transport boundary:** libuv write completion returns a buffer loan and can
  replenish demand. This means acceptance by the local transport, **not** proof
  that the remote client consumed the bytes. TCP backpressure/socket buffers
  and application buffers must all be included in the transport bound.

## Implemented C flow contract

Creation binds the future producer/consumer roles; the application retains the
handle until **all callers are quiescent**. One producer and one consumer may
operate concurrently. Other threads may add demand, cancel or report failure.
Calls use a short mutex: this is not a lock-free or hard-real-time claim. No API
waits for buffer capacity, demand, device work, network writes or consumer speed.

| Operation | Contract |
|---|---|
| `lie_flow_request(n)` | Add confirmed-token credits; zero terminates with protocol error; overflow saturates to unbounded `UINT64_MAX`. |
| `lie_flow_reserve(step_limit)` | Grant at most available demand and one preallocated chunk slot; zero demand/full pool gives `WOULD_BLOCK`, another outstanding work loan gives `BUSY`. |
| `lie_flow_begin(ticket)` | Dispatch linearization gate. Cancellation before this gate refuses dispatch. A winning gate counts as in-flight work even if hardware enqueue follows later. |
| `lie_flow_commit(ticket, bytes, tokens, finish)` | After work completes, publish only confirmed tokens; refund unused finite credits. An empty final step is legal. Suppress late results after cancellation/error. |
| `lie_flow_next()` | Borrow the next FIFO chunk, or observe a terminal outcome once after all loans retire. At most one borrowed output chunk preserves ordering. |
| `lie_flow_release(ticket)` | Retire the output loan, returning capacity; **does not automatically add demand**. The subscriber controls replenishment. |
| `lie_flow_finish()` | Normal completion with no outstanding work; queued/borrowed data drains before the terminal signal. No token demand is needed for termination. |
| `lie_flow_cancel()` / `lie_flow_fail(code)` | Out-of-band stop latch, even when all data slots are occupied. Drop unread queued data, reject new demand/dispatch, retain work and transport loans. |
| `lie_flow_abort(ticket, code)` | After the work has finished, or was never dispatched, retire its loan and fail unless a prior cancellation/error already owns the terminal outcome. |
| `lie_flow_destroy()` | Refuse active/queued/borrowed/in-flight state. External caller quiescence is mandatory; no force-free or implicit GPU synchronization. |

The work and output directions each expose a nonblocking, close-on-exec eventfd.
Wakeups coalesce: the state/queue is authoritative, not notification counts.
Each direction has one drain owner. **Drain first, then inspect/process level
state until blocked/closed.** Release emits a fresh output wake too, so a consumer
that previously stopped on a borrowed frame cannot lose a pending terminal or
queued chunk. HTTP now watches output with `uv_poll_t`; the worker waits on
work/control readiness with poll. No periodic token busy-wait is used. The
250 ms HTTP timer enforces deadlines and samples counters, not decode readiness.

### Storage and demand invariant

For configured `slots = S`, chunk payload bound `B` and finite demand `D`:

```text
queued + borrowed + reserved_or_running <= S
borrowed <= 1; reserved_or_running <= 1
step_grant <= min(step_limit, D)
confirmed_tokens <= step_grant
payload_bytes <= B
```

Storage (payload pool, slot metadata, FIFO indices and flow object) is allocated
once. `lie_flow_storage()` checks arithmetic and reports the requested heap
bytes; creation refuses a smaller instance budget. There is no allocation on
request/reserve/begin/commit/next/release/stop. This count excludes allocator
bookkeeping, kernel FDs/socket buffers and model state; it is **not RSS or a GPU
memory-fit measurement**. The future admission manager must budget the aggregate
across all live streams plus weights, hybrid state, scratch and I/O staging.

Demand and storage are independent: unbounded token demand does not bypass the
finite byte pool. A borrowed buffer still occupies its slot until the actual
write callback retires it. `WOULD_BLOCK` suspends only this sequence; it is not
permission to allocate an overflow queue, block the HTTP loop, drop tokens, or
busy-spin. Slow-client timeout remains a separate explicit cancellation policy.

The producer must bound worst-case UTF-8/SSE framing bytes for its selected step
**before dispatch**. This transport-neutral primitive cannot calculate tokenizer
or protocol expansion. An oversized/malformed completion is refused without
releasing its work loan: the owner must retire/fail it, not rerun a mutating
forward, truncate data or label proposals as confirmed tokens.

### Cancellation, races and ownership

1. Cancellation competes with `begin`, not just enqueue. If it wins, no new step
   is admitted. If dispatch won first, cancellation cannot preempt that kernel.
2. Queued but unread output is discarded. A worker's writable reservation and a
   network writer's borrowed buffer remain valid until explicit retirement.
   No sequence/batch backing state may be freed while work still refers to it.
3. A late completion retires the work loan but publishes no data. `next` exposes
   the terminal only after the borrowed network loan also retires.
4. Tickets bind to the flow handle and a non-reused generation during its
   lifetime. Duplicate, stale or foreign-flow completion/release is refused.
   Handles/tickets are internal, not untrusted client IDs or lifetime references.
5. Completion drains normally. Cancellation/error can abandon a pending normal
   completion before it is observed. The first abort outcome wins thereafter;
   no second terminal signal is emitted. Cancellation is an **internal retirement
   outcome**, not an `onComplete` pushed to a disconnected subscriber.
6. Already handed-off transport bytes cannot be recalled. The output owner must
   serialize disconnect and write submission, avoid new writes after disconnect,
   and retire outstanding libuv writes/poll handles before destroying the flow.
   Caller quiescence includes the scheduler: a mutex is not a lifetime pin.

This primitive isolates streams' demand, slots and outcomes. The dedicated
scheduler must still implement fairness and per-row completion handling; the
component test with a blocked stream and a progressing peer is **not** a native
GPU batching or end-to-end slow-client qualification. The distinct real-model
slow-client evidence is documented in [T0-LIFECYCLE.md](T0-LIFECYCLE.md), not
inferred from these component tests.

## T0 binding and remaining obligations

T0 admits eight jobs, with one active sequence by default or two explicitly
configured interleaved single-row sequences. Eight 256-byte slots and initial
eight-token credit window per job. Ordinary text SSE retains a loan until write
completion, then releases it and explicitly replenishes token demand. Nonstream
and tool-enabled turns reserve a bounded aggregate sink before admission. Unknown/unsupported requests fail; overflow
is 429. No fake provider is linked into the production executable.

Worker and transport job references are independent. Cancellation calls only
the backend's atomic latch under a short gate; the worker detaches its sequence
under the same gate before destruction. Blocking backend calls run outside the
gate. Prefix preparation/prefill are pinned by the worker reference; decode also
has a flow reservation. A flow terminal alone is not proof all worker cleanup
has completed. Network write/poll retirement and the worker reference jointly
control destruction. See HTTP.md/ABI.md for error and shutdown semantics.

With max-active=1 a blocked active request retains the sole session slot; queued
peers wait for completion/cancellation/deadline. The CPU peer-progress tests use
max-active=2. This is a bounded policy, not qualified native concurrency, optimal
fairness or adaptive memory admission. Completed generation can later be abandoned
by transport; those are distinct outcomes.

Remaining work:
- Measured aggregate model/state/workspace admission and separate CPU/disk queues.
  Never hide overload in an unbounded buffer or drop normal confirmed output.
- Dispatch C1 promptly, then use real shared batch APIs with fair per-sequence
  budgets. Suspend an output-blocked sequence without stalling peers. Adapt
  concurrency/prefill/MTP budgets within measured capacity, not by spawning more
  device owners. Elasticity on one GPU is bounded admission/budget adaptation,
  not a claim of hardware scaling or instantaneous kernel preemption.
- Qualify the implemented cancellation bridge on the real device. Flow stop does
  not preempt GPU work or free its state. Keep nonmutating refusals separate from
  model-poisoning failure; loaded-runtime failure requires quiescence before
  retirement, or process exit if quiescence cannot be established.
- Structured tool ordering/ID correlation is implemented with full history
  re-prefill. Retained-state continuation is still future work: a completed
  output turn could retain a session waiting for a tool result; it needs a new
  subscription at a verified state frontier, not a dangling SSE stream or a
  blind replay/retry of previous side effects.
- SSD work returns immutable completion messages. Only the device owner may
  apply a verified restore. Never perform filesystem I/O under the flow mutex or
  restore model state from a client/disk callback. See [STATE.md](STATE.md).
- Queue/active counts and executor outcome counters are now wired. Add credits,
  output-pause duration and cancellation retirement latency measurements. `published_tokens` here counts chunks
  accepted into the flow (including later abandoned queued data), **not** GPU
  generated-token or remote-delivery metrics. Do not export invented live values.
- Qualify real SSE ordering/UTF-8, fragmented writes, disconnect races, terminal
  behavior, fairness and bounded RAM with each selected original-weight execution
  path. Record transitional versus owned results; do not transfer qualification
  automatically between them.
  Component tests do not close this gate or the DS4 hardware lease gate.

## Reactive inside the numerical executor

The requirement also includes investigating pure-inference benefits, not only
output backpressure. [INFERENCE-REACTIVE.md](INFERENCE-REACTIVE.md) defines trace-
driven hypotheses about dependency waits, launch gaps, overlap and buffer liveness,
with separate C1 PP/TG, concurrency and serving measurements. Moving a blocking
forward to a worker, or adding callbacks, does not establish a faster forward.
An inner scheduler must preserve autoregressive/recurrent dependencies and avoid
per-tensor event overhead. No GPU experiment or improvement is claimed yet.

## Current evidence boundary

`tests/test_flow.c` exercises zero demand, partial credit refund, saturation,
size/ordinal overflow, capacity including borrowed buffers, FIFO offsets,
normal/empty completion, invalid demand, stale/foreign tickets, cancellation
before dispatch and during work, full-buffer stop, first-error retention, safe
retirement, independent peers, FD cleanup, and 4,000 ordered synthetic frames
between real threads woken by eventfd. These are **CPU flow-control tests**.
They do not validate token generation or GPU kernels. `test_worker.c` and
`test_serving.py` additionally exercise the actual worker/libuv binding with a
synthetic provider: overload, stalled-peer progress with two active slots, actual
TCP backpressure, UTF-8, terminal/error ordering, disconnect/deadline, in-flight
lifetime and shutdown. No fixture establishes real-model correctness, GPU
fairness, SSD restore or performance. See [PROGRESS.md](PROGRESS.md).
