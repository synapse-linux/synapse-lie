# Historical reference-only Gufo interoperability ABI 1

**Not the production LIE backend or numerical ABI.** The adapter delegates to
Gufo Model/Session, which does not satisfy the autonomous-backend requirement.
The earlier plan to connect it to serving is superseded by [BACKEND.md](BACKEND.md).
It remains an optional reference-only compile experiment, never linked into the
server or hardware-qualified. The new owned backend/operation ABI is not yet
implemented; its boundary must not expose a renamed upstream whole-model engine.

`include/lie/executor.h` is C17-compatible and contains only fixed-width types,
lengths, opaque handles and caller-owned error buffers. No C++ types are public.
`adapters/gufo.cpp` compiles against upstream `f783fedb` only with the explicit
reference build definition. The following describes this experiment, not a
qualified production runtime.

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
LIE's future tokenizer/chat renderer must be independently implemented or
selectively source-ported with provenance and tests, validate the GGUF artifact
template, and preserve reasoning/tool semantics. It must not delegate rendering
or model execution through the reference Model object, fabricate ChatML, or
normalize input to gain cache hits.

This historical experimental layout is not a production stability promise.
Do not silently repurpose these Gufo-backed symbols as an owned implementation;
introduce and qualify the actual numerical/device boundary with its own contract.
