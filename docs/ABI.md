# Experimental transitional execution ABI 1

The adapter delegates to Gufo Model/Session. **This is permitted for bootstrap,
not proof of an autonomous LIE backend.** [BACKEND.md](BACKEND.md) defines the
subsequent requirement-driven replacement gates. It has only been compile-checked,
not linked into the server or hardware-qualified. The eventual owned numerical
ABI is separate and not implemented yet. Keep upstream types inside the adapter.

`include/lie/executor.h` is C17-compatible and contains only fixed-width types,
lengths, opaque handles and caller-owned error buffers. No C++ types are public.
`adapters/gufo.cpp` compiles against upstream `f783fedb` only with the explicit
`LIE_GUFO_ADAPTER_OPT_IN` definition. The following describes the experimental
contract, not a qualified runtime. Permission to link is not evidence of linking.

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
The transitional renderer may use pinned upstream implementation behind the
adapter; an owned or selectively ported replacement must preserve the tested
GGUF template/reasoning/tool semantics. Do not fabricate ChatML, normalize input
to gain cache hits, or leak upstream Model types into the HTTP/scheduler contract.

This experimental layout is not a stability promise. Keep engine selection
(e.g. `lie_gufo_open`) at the composition/binding boundary; neutral runtime clients
must not assume Gufo ownership/layout. Introduce capability/versioned changes for
batching, state and later owned implementations; never relabel delegation.
If reactive inference motivates an asynchronous ABI, add explicit submitted versus
completed outcomes, tickets and retained lifetimes. Do not change `LIE_OK` from
completed to enqueue-only silently. See [INFERENCE-REACTIVE.md](INFERENCE-REACTIVE.md).
