# Architecture and ownership

**Authoritative scope:** [BACKEND.md](BACKEND.md). LIE reimplements the backend,
including C loading/binding, model execution, session state and memory ownership.
Gufo is a numerical source/reference, not an upstream engine to wrap. The prior
plan to link its Model/Session adapter into serving is explicitly superseded.

## Decisions implemented in increment A + independent observability slice

1. Separate Git repository, `develop` seed and `feature/initial-runtime`.
   Source, temporary files, binaries and evidence stay here. This repository is
   not a worktree of DS4. No deployment, weight download or package installation.
2. C17 for the runtime, registry, HTTP and monitor. libuv owns nonblocking
   listeners/lifetimes; llhttp is the maintained HTTP/1 parser rather than a new
   parser; json-c owns JSON trees; libcurl is used only by the monitor.
   This uses installed libraries and no JVM/Python inference dependency.
3. One registry, short mutex-protected updates/copy, serialization outside the
   mutex. Registration copies names/descriptions/tags. No callbacks into GPU or
   hardware polling during health/metrics. Handles remain valid until destruction.
4. Separate API and management listeners (19879/19880 by default). Both use the
   same loop, strictly bounded connections/request bytes and timeouts. This is
   a functioning control plane, not a promise of latency under all loads.
5. Gufo is independently fetched from upstream, not copied from the DS4 port.
   The C++ adapter delegates to Qwen Model/Session. It is a reference-only,
   compile-checked experiment, absent from the server and excluded from the
   production roadmap. No owned LIE numerical backend has been implemented.

## Reactive pattern: Reactor is only the transport layer

The [reactive contract](REACTIVE.md) is authoritative for demand/backpressure,
stream ordering, dispatch cancellation and buffer retirement. The new C `lie_flow`
component implements these primitives with preallocated bounded storage and two
coalesced eventfd directions. Its tests use CPU frames and actual threads. It is
not yet a connected inference graph or part of the HTTP server.

The target is publisher -> bounded subscription -> output subscriber, with
credits/releases flowing back to the device-owner scheduler and cancellation on
a separate control path. No inference or disk wait on the network loop, no queue
that grows to hide a slow client, no token dropping during normal generation,
no one-thread-per-agent execution, no unbounded operator chain. Resource admission,
fair shared scheduling, state persistence and live metric wiring still need
integration; libuv alone does not satisfy those reactive properties.

## Target execution architecture (not all implemented)

- HTTP loop: admission parsing, request ownership, ordered output and disconnect
  events. It never launches model inference. Bound all queues and output bytes.
- One device-owner worker: the only scheduler and owner of LIE's mutable
  model/session state. Its C executor owns the layer graph and invokes selected,
  source-ported numerical operations through a narrow C device/kernel boundary.
  Completed steps run here, never on the network loop. No embedded Gufo engine
  or competing serving scheduler. Qwen token/template behavior belongs to LIE;
  it is not obtained through a delegated Gufo Model. A later CUDA numerical
  implementation must leave HTTP, the registry and state contracts unchanged.
- CPU workers: bounded token/template preparation; never CPU model forward.
- Disk workers: bounded save/load jobs, immutable frontier payloads and completion
  messages to the owner. No direct GPU restore from a disk/client thread.
- Resource manager: weights + active session state + retained prefixes + workspace
  + speculative rollback + I/O buffers on shared RAM, not independent pools.
  Runtime admission values must come from actual backend/host measurements.

Sequence states will be `queued -> prefill -> ready/decode -> output_paused ->
completed/cancelled/failed`, with a separate retained/tool-waiting state. Agent
count is not ready-row count. A cancelled row admits no new work; references and
buffers remain pinned until its in-flight work completes. Do not cancel peers
in a shared batch or expose speculative tokens before verification.

Scheduling policy to qualify: immediate C1 dispatch, true native shared steps
where supported, decode plus bounded prefill chunks with new-arrival fairness,
backpressure per sequence, controlled deadline expiry, idle-prefix reclamation
before admission refusal. Budgets (active rows, token/chunk/speculation/memory)
are explicit instance settings. Measured step-time targets are not instantaneous
kernel preemption. No such scheduling performance is claimed by this increment.

## Backend inspection

At Gufo `f783fedb`, Qwen's Model owns resident weights and an Executor, and
sessions carry independent history/state. `EvaluateBatch` and `DecodeBatch`
exist, with per-row `BatchOutcome`; a failed call can contain completed peers.
The reference-only adapter exposes **one row** and no MTP. These upstream APIs
are inspected as behavioral references, not production integration points. LIE
must implement native batching in its own executor before a batching claim.
Upstream payload version is **14**, not DS4 native19 and not a LIE state format.

## Increment plan and departure from requested order

- A: inventory, isolated source, provenance, model metadata and inherited baseline
  identities recorded. Fresh pristine baseline verification waits for DS4 lease
  acknowledgement; this gate is not marked complete.
- Independent part of B/E: compiled C management runtime, metric registry,
  monitor and compile-checked adapter delivered while hardware is blocked.
- Reactive CPU slice: implemented bounded demand/stream/lifetime primitive;
  scheduler/HTTP/executor bindings remain open.
- Next B, corrected: implement LIE's C GGUF/binding and state/executor slices,
  selectively port numerical kernels, then qualify original-model short AR
  against an independent pristine Gufo comparator. Do not link the old adapter.
- C: connect the owned executor to `lie_flow` and real nonstream/SSE; qualify
  lifecycle, admission/cancel/chunks, C1/2/4/8 native batching when memory allows,
  then MTP and load/acceptance-aware windows.
- D: RAM prefix snapshots then SSD atomic persistence/restart and failure tests.
- E remainder: actual inference metric wiring, streaming/backpressure metrics,
  percentiles, broader monitor/UI and instrumentation overhead measurements.
- F: CUDA on DGX Spark through the same contracts, after AMD baseline stability.

This ordering delivers reusable tested code without using GPU idleness as an
implicit permission or claiming fixtures establish inference.
