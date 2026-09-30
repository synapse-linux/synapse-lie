# Architecture and ownership

**Authoritative evolution policy:** [BACKEND.md](BACKEND.md). An explicit embedded
Gufo adapter is permitted for bootstrap, then refactored toward LIE-owned model,
session, memory and execution according to requirements and new developments.
The earlier blanket exclusion of an in-process adapter is superseded; delegation
must still never be presented as an autonomous backend.

## Implemented decisions through the T0 candidate

1. Separate Git repository, `develop` seed and `feature/initial-runtime`.
   Source, temporary files, binaries and evidence stay here. This repository is
   not a worktree of DS4. No deployment, weight download or package installation.
2. C17 for the runtime, registry, HTTP and monitor. libuv owns nonblocking
   listeners/lifetimes; llhttp is the maintained HTTP/1 parser rather than a new
   parser; json-c owns JSON trees; libcurl is used by the monitor and is a link
   dependency of unexposed upstream image helpers in the optional Gufo build.
   This uses installed libraries and no JVM/Python inference dependency.
3. One registry, short mutex-protected updates/copy, serialization outside the
   mutex. Registration copies names/descriptions/tags. No callbacks into GPU or
   hardware polling during health/metrics. Handles remain valid until destruction.
4. Separate API and management listeners (19879/19880 by default). Both use the
   same loop, strictly bounded connections/request bytes and timeouts. This is
   a functioning control plane, not a promise of latency under all loads.
5. Gufo is independently fetched from upstream, not copied from the DS4 port.
   The C++ adapter delegates to Qwen Model/Session. It now links optionally into
   the C worker/flow/HTTP path; default builds still have no numerical provider.
   No loaded-model/GPU result or owned numerical backend is established.

## Reactive pattern: Reactor is only the transport layer

The [reactive contract](REACTIVE.md) is authoritative for demand/backpressure,
stream ordering, dispatch cancellation and buffer retirement. The new C `lie_flow`
component implements these primitives with preallocated bounded storage and two
coalesced eventfd directions. Worker and HTTP bindings now use them. CPU tests
exercise real threads and sockets with a separate synthetic provider; actual
GPU/model correctness remains an independent open gate.

The target is publisher -> bounded subscription -> output subscriber, with
credits/releases flowing back to the device-owner scheduler and cancellation on
a separate control path. No inference or disk wait on the network loop, no queue
that grows to hide a slow client, no token dropping during normal generation,
no one-thread-per-agent execution, no unbounded operator chain. T0 bounds eight
admissions and one or two active single-row sequences, without native batching.
SSE write completion returns demand; disconnect latches cancellation with pinned
lifetimes. Measured memory admission, advanced fairness, persistence and broader
inference instrumentation remain open; libuv alone is not those properties.

A separate [pure-inference investigation](INFERENCE-REACTIVE.md) evaluates whether
readiness/dependency-driven execution can reduce GPU idle gaps, overly broad
synchronization, launch overhead or conservative buffer lifetimes. These are
hypotheses, not benefits guaranteed by the architecture. Moving a synchronous
forward into a worker is not itself a faster forward; C1, concurrency and HTTP
results must remain separate. No per-tensor callback framework is required.

## Target execution architecture (not all implemented)

- HTTP loop: admission parsing, request ownership, ordered output and disconnect
  events. It never launches model inference. Bound all queues and output bytes.
- One device-owner worker: the only LIE admission/scheduling authority for
  mutable execution. Initially it may invoke pinned Gufo Model/Session through
  the isolated transitional adapter, never a second Gufo serving scheduler.
  Subsequent slices move model/state/layer-graph ownership into LIE C code and
  invoke selected numerical operations through a narrow device/kernel ABI.
  Work never blocks the network loop. Qwen rendering may initially be adapted
  upstream code, with tested semantics and no upstream types leaking to clients.
  Evolve the LIE contracts explicitly for requirements/CUDA, not around hidden
  assumptions of the bootstrap implementation.
- Future CPU preparation workers: T0 currently renders/tokenizes on the device
  owner, off the HTTP loop. Splitting this requires a thread-safe contract;
  no CPU model forward.
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
The experimental adapter currently exposes **one row** and no MTP. Native Gufo
batching may be exposed in the transitional phase only after actual integration
and per-row/lifetime qualification; a loop over single-row calls is not batching.
Owned batching follows the replacement gates. Upstream payload version is **14**,
not DS4 native19 or an automatically portable future LIE state format.

## Increment plan and departure from requested order

- A: inventory, isolated source, provenance, model metadata and inherited baseline
  identities recorded. Fresh pristine baseline verification waits for DS4 lease
  acknowledgement; this gate is not marked complete.
- Independent part of B/E: compiled C management runtime, metric registry,
  monitor and compile-checked adapter delivered while hardware is blocked.
- Reactive/T0 software slice: primitive and worker/HTTP/executor bindings are
  implemented, HIP-linked and CPU/synthetic-tested. Not real-model qualification.
- Next B / T0: under the lease, qualify the pinned pristine comparator and the
  linked candidate on original-model short AR, nonstream/SSE and cancellation/
  backpressure. Do not transfer synthetic results to GPU correctness.
- C / T1: refactor one responsibility at a time against requirements and evidence;
  qualify lifecycle, admission/chunks, C1/2/4/8 and MTP on their actual paths.
  Trace and test reactive pure-inference hypotheses separately from serving gains.
  T2 removes whole-engine delegation from the qualified owned path; no big-bang
  rewrite or permanent-wrapper claim is implied.
- D: RAM prefix snapshots then SSD atomic persistence/restart and failure tests.
- E remainder: actual inference metric wiring, streaming/backpressure metrics,
  percentiles, broader monitor/UI and instrumentation overhead measurements.
- F: CUDA on DGX Spark through the same contracts, after AMD baseline stability.

This ordering delivers reusable tested code without using GPU idleness as an
implicit permission or claiming fixtures establish inference.
