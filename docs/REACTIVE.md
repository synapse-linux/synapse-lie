# Reactive execution pattern

## Decision and present implementation

The runtime is designed as **demand-driven streams with bounded asynchronous
boundaries**, not merely an HTTP server with callbacks. libuv implements the
network Reactor (I/O readiness dispatch); it does not by itself implement
reactive inference. A responsive, resilient, elastic, message-driven system
also needs bounded admission, feedback, isolation and lifecycle ownership.

The first implemented component is `include/lie/flow.h` + `src/flow.c`, a C17
per-sequence subscription/flow-control primitive. It has CPU tests with real
threads, finite storage and Linux eventfd wakeups. It is **not connected to
Gufo, the scheduler or HTTP/SSE yet**. The server still returns 503 for chat.

This is not Project Reactor, Rx, a JVM dependency or a Reactive Streams TCK
compliance claim. It adopts demand, serial signals, cancellation and bounded
resource ownership. Credits are **confirmed tokens**, whereas one data signal
may contain a chunk of several tokens; this is deliberately not the formal
Reactive Streams item-count protocol. No reactive wrapper per tensor/kernel.

## End-to-end topology — target, not a working inference graph

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

- **Publisher:** device-owner worker, publishing only completed, confirmed output.
  GPU submission is not completion. Drafted MTP tokens never enter the output
  stream before verification. No callback invokes more inference inline.
- **Subscriber:** one ordered output owner for a sequence. Nonstream JSON will
  also consume this flow, but must reserve a bounded aggregation buffer; it must
  not become an unbounded sink that hides backpressure.
- **Subscription:** sequence-local token demand, bounded byte storage, dispatch
  tickets, cancellation and a single terminal outcome. No global hot multicast
  stream and no replay buffer pretending to be recurrent/KV state persistence.
- **Scheduling boundary:** one device-owner scheduler, not one GPU thread per
  request and not a second serving scheduler hidden behind the C adapter.
  CPU preparation and disk I/O use separate bounded work/completion queues.
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
queued chunk. The future HTTP binding can watch output with `uv_poll_t`; the
worker waits on work/control readiness. No periodic busy-wait loop is required.
These libuv/scheduler bindings themselves are not implemented yet.

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
GPU batching or end-to-end slow-client qualification.

## Remaining integration obligations

- Bound HTTP admission, preparation, scheduler/control and disk queues. Refuse
  overload explicitly (API contract to define before enabling inference), not
  through an unbounded `onBackpressureBuffer`. Never drop normal confirmed output.
- Dispatch C1 promptly, then use real shared batch APIs with fair per-sequence
  budgets. Suspend an output-blocked sequence without stalling peers. Adapt
  concurrency/prefill/MTP budgets within measured capacity, not by spawning more
  device owners. Elasticity on one GPU is bounded admission/budget adaptation,
  not a claim of hardware scaling or instantaneous kernel preemption.
- Bridge executor cancellation and flow cancellation. Flow stop does not itself
  cancel Gufo or free a sequence. CPU/storage failures and nonmutating admission
  refusal are distinct from a backend failure that poisons the shared model.
- Preserve tool-call ordering and logical continuation. A completed output turn
  can retain a session waiting for a tool result; the continuation is a new
  subscription at a verified state frontier, not a dangling SSE stream or a
  blind replay/retry of previous side effects.
- SSD work returns immutable completion messages. Only the device owner may
  apply a verified restore. Never perform filesystem I/O under the flow mutex or
  restore model state from a client/disk callback. See [STATE.md](STATE.md).
- Wire live queue occupancy, credits, output-pause duration and cancellation
  retirement latency into observability. `published_tokens` here counts chunks
  accepted into the flow (including later abandoned queued data), **not** GPU
  generated-token or remote-delivery metrics. Do not export invented live values.
- Qualify real SSE ordering/UTF-8, fragmented writes, disconnect races, terminal
  behavior, fairness and bounded RAM with the linked original-weight executor.
  Component tests do not close this gate or the DS4 hardware lease gate.

## Current evidence boundary

`tests/test_flow.c` exercises zero demand, partial credit refund, saturation,
size/ordinal overflow, capacity including borrowed buffers, FIFO offsets,
normal/empty completion, invalid demand, stale/foreign tickets, cancellation
before dispatch and during work, full-buffer stop, first-error retention, safe
retirement, independent peers, FD cleanup, and 4,000 ordered synthetic frames
between real threads woken by eventfd. These are **CPU flow-control tests**.
They do not validate token generation, SSE, GPU kernels, scheduler fairness,
SSD restore or performance. See [PROGRESS.md](PROGRESS.md) for verification runs.
