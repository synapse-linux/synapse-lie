# Experimental executor ABI 1

`include/lie/executor.h` is C17-compatible and contains only fixed-width types,
lengths, opaque handles and caller-owned error buffers. No C++ types are public.
`adapters/gufo.cpp` compiles against upstream `f783fedb`; linking, real model
loading and runtime lifetime guarantees still require hardware qualification.
The adapter is NOT connected to `synapse-lie-server` yet.

## Ownership and completion

- `lie_gufo_open` creates a model handle. Output handles must initially be NULL.
- The opening thread is the exclusive device worker. All operations except the
  cancellation latch require this thread. Wrong-owner calls refuse before work.
- Sequences pin the model runtime independently, so closing the public model
  handle cannot destroy a model still referenced by a sequence.
- Arguments are borrowed synchronously. Token/logit/text output is copied into
  caller buffers. Required size is reported on `LIE_BUFFER_SMALL`; token text
  is raw bytes, not NUL-terminated and not necessarily complete UTF-8. HTTP must
  assemble UTF-8 without reordering tokens when this gets wired.
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
  completion and only then close it. The server does not exercise this yet.
- Invalid parameters are nonmutating refusals. A backend exception/forward
  failure poisons the runtime; it cannot be retried or downgraded to a cache
  miss. Cleanup is the only legal path. No CPU-forward fallback exists.

No chat-template, tools, snapshot, MTP or native batching entry points are
implemented in this first ABI. Raw text tokenization is not chat rendering.
The next integration must use Gufo's bounded Qwen renderer, validate the GGUF
artifact template, and preserve reasoning/tool semantics rather than fabricate
ChatML or normalize input to gain cache hits.

This is a developmental ABI, not a stability promise across v0.1 increments.
Changing public layout/semantics requires an ABI bump and renewed tests.
