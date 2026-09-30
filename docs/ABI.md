# Experimental transitional execution ABI 2

The adapter delegates to Gufo Model/Session. **This is permitted for bootstrap,
not proof of an autonomous LIE backend.** [BACKEND.md](BACKEND.md) defines the
subsequent requirement-driven replacement gates. It now links into the optional
HIP server and is connected to the C worker/flow/HTTP path. A bounded original-weight
C1 HTTP/SSE smoke passed on Strix Halo (`t0-model-smoke-r4`); full numerical and
hardware qualification remain open. The eventual owned numerical ABI remains
separate; keep upstream types inside the adapter.

`include/lie/executor.h` is C17-compatible and contains only fixed-width types,
lengths, opaque handles and caller-owned error buffers. No C++ types are public.
`adapters/gufo.cpp` compiles against upstream `f783fedb` only with the explicit
`LIE_GUFO_ADAPTER_OPT_IN` definition. The following describes the experimental
contract, not hardware qualification. `LIE_GUFO_HEADER_CHECK` remains object-only;
`LIE_GUFO_RUNTIME` explicitly links verified private upstream archives. ABI 1
receipts remain historical. `lie_backend_open` is the selected composition binding
(`adapters/gufo_binding.c` for Gufo), not an implicit fallback. Provider name,
source pin and ownership queries expose delegation; the explicit factory
`lie_gufo_open` remains available and is not relabelled as an owned engine.

## Ownership and completion

- `lie_gufo_open` creates a model handle. Output handles must initially be NULL.
- The opening thread is the exclusive device worker. All operations except the
  cancellation latch require this thread. Wrong-owner calls refuse before work.
- Sequences pin the model runtime independently, so closing the public model
  handle cannot destroy a model still referenced by a sequence.
- Arguments are borrowed synchronously. Token/logit/text output is copied into
  caller buffers. Required size is reported on `LIE_BUFFER_SMALL`; token text
  is raw bytes, not NUL-terminated and not necessarily complete UTF-8. HTTP must
  assemble UTF-8 without reordering tokens; the current HTTP path does so with
  a shared streaming/nonstream replacement decoder.
- Prefill takes a cumulative physical prefix, verifies the existing frontier,
  token ranges, context and configured delta before Sync. It cannot truncate a
  recurrent state by merely shortening a token list.
- Decode is greedy AR, one confirmed token maximum, per-sequence SamplerState.
  No shared RNG/sampling state. Stop and output count are separate. MTP and
  native multirow submission are deliberately not advertised in this adapter.
- The inspected upstream Forward completes `hipStreamSynchronize` before
  returning host logits. This is a synchronous completion API, not enqueue.
  It must run off the HTTP loop. There is no exported async ticket/poll API yet.
- Cancellation is an atomic latch, not device preemption. No subsequent step is
  admitted; an already submitted step finishes and its output is suppressed.
  The caller must pin a sequence while any thread can cancel/use it, join/observe
  completion and only then close it. The worker/job gate serializes latch calls
  against sequence detachment, never holding the gate across blocking execution.
  Synthetic tests exercise this lifetime; GPU cancellation-in-flight is still untested.
- Invalid parameters are nonmutating refusals. A backend exception/forward
  failure poisons the runtime; it cannot be retried or downgraded to a cache
  miss. Loaded-runtime failure drains HIP work before returning failure; an
  unsuccessful drain exits the process with 70, without retry or core dump.
  Successful operations add no new device-wide synchronization. Model loading's
  internal cleanup remains upstream-owned. Hardware/fault qualification is open.
  Cleanup is the only legal path. No CPU-forward fallback exists.

`lie_model_chat_tokens` adds bounded text-only chat preparation: 1–32 LIE role/
content spans, at most 64 KiB total content, caller-owned physical token output.
The adapter validates the GGUF template before model load, then invokes the pinned
Qwen renderer/tokenizer with thinking disabled. Buffer/context refusal is before
session mutation. Only system/user/assistant messages are exposed. Raw tokenization
remains distinct. No tools, snapshots, MTP or native batching entry points exist.
An owned or selectively ported renderer must preserve the applicable, separately
qualified GGUF template/reasoning/tool semantics. Do not fabricate ChatML, normalize input
to gain cache hits, or leak upstream Model types into the HTTP/scheduler contract.

The server worker now measures `lie_sequence_prefill`/`lie_sequence_decode`
call wall time using `CLOCK_MONOTONIC`, retaining the completed-work semantics.
No additional device synchronization or executor ABI/version change is made.
Timing fields are internal worker snapshots, not additional fields in executor
ABI 2. The versioned JSON/SSE extension and invalid-clock/null rules are in
[HTTP.md](HTTP.md#per-request-executor-timings). They do not measure HTTP latency
or establish GPU performance qualification.

This experimental layout is not a stability promise. Keep engine selection
(e.g. `lie_gufo_open`) at the composition/binding boundary; neutral runtime clients
must not assume Gufo ownership/layout. Introduce capability/versioned changes for
batching, state and later owned implementations; never relabel delegation.
If reactive inference motivates an asynchronous ABI, add explicit submitted versus
completed outcomes, tickets and retained lifetimes. Do not change `LIE_OK` from
completed to enqueue-only silently. See [INFERENCE-REACTIVE.md](INFERENCE-REACTIVE.md).
