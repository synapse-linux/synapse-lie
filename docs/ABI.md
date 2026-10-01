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
- Decode is AR (greedy by default), one confirmed token maximum, per-sequence SamplerState.
  No shared RNG/sampling state. Stop and output count are separate, each 0 or 1;
  a successful return either emits or stops. Position is the previous completed
  position plus emitted count, including un-emitted EOS (no position advance).
  Emitted tokens must be within the model vocabulary. The worker checks these
  invariants before token lookup/publication and fails closed on a contract
  violation. Reported token-text size must fit its caller buffer. MTP and native
  multirow submission are deliberately not advertised in this adapter.
- The inspected upstream Forward completes `hipStreamSynchronize` before
  returning host logits. This is a synchronous completion API, not enqueue.
  It must run off the HTTP loop. There is no exported async ticket/poll API yet.
- Cancellation is an atomic latch, not device preemption. No subsequent step is
  admitted; an already submitted step finishes and its output is suppressed.
  The caller must pin a sequence while any thread can cancel/use it, join/observe
  completion and only then close it. The worker/job gate serializes latch calls
  against sequence detachment, never holding the gate across blocking execution.
  Synthetic tests exercise deterministic lifetime edges. The original-weight
  `t0-model-lifecycle-r1` run also observed cancellation during prefill/decode
  owner dispatch, suppressed further publication and safely retired/reused the
  runtime. It does not prove GPU-kernel preemption or qualify GPU failure paths.
- Invalid parameters are nonmutating refusals. A backend exception/forward
  failure poisons the runtime; it cannot be retried or downgraded to a cache
  miss. Loaded-runtime failure drains HIP work before returning failure; an
  unsuccessful drain exits the process with 70, without retry or core dump.
  Successful operations add no new device-wide synchronization. Model loading's
  internal cleanup remains upstream-owned. Hardware/fault qualification is open.
  Cleanup is the only legal path. No CPU-forward fallback exists.

`lie_model_chat_tokens` retains its ABI-2 signature/layout and now delegates to
the additive `lie_model_chat_tokens_ex` entry point. The latter takes a borrowed
`lie_chat_template`: up to 1024 message spans with optional tool details, typed
argument values, up to 128 declarations and a required-call flag. No executor
struct layout/version change or numerical operation is introduced; older binaries
without the new symbol cannot be linked as the new adapter. The `LIE_CHAT_TOOL`
role is appended; developer messages map to leading system messages in C.

The C17 parser owns normalized JSON and copied message content. Ownership moves
to the worker until retirement; the UI has a deep, independent schema copy, not
cross-thread json-c refcounts. Adapter translation bounds aggregate spans/strings
to 32 MiB (four times the body bound); HTTP requests have a separate 8 MiB cap. The native renderer applies its
context-derived output bound (at least 1 MiB). The adapter validates the GGUF
template before model load, then invokes the pinned Qwen renderer/tokenizer with
thinking disabled, structured calls/results and real tool declarations. Buffer/
physical-context refusal precedes session mutation. Plain formatting remains
byte-identical in the CPU formatter test. Raw tokenization remains distinct.
No tool code executes here. Snapshots and MTP remain absent. Native decode batching uses the additive contract below.
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

## Additive generation configuration

`lie_generation_options` has its own ABI 1 version and exact struct size.
`lie_sequence_configure` runs on the model owner before prefill; a started
sequence or invalid/nonfinite/range-invalid option is refused. Existing ABI-2
model/message layouts are unchanged. Parsed requests own their scalar controls;
there are no upstream types. Temperature, top_p, frequency/presence penalties
and seed bind a per-sequence sampler. Its penalty history is initialized from
the entire completed prompt immediately before first decode, not the first
prefill chunk. Ordinary benchmark callers may retain the default greedy sampler
without calling the additive entry point. Invalid configuration closes only the
new sequence; backend/close failure still poisons the runtime.

## Additive completed batch contract

`lie_backend_open_batch(path, options, width, ...)` explicitly admits width 1..8
and binds upstream workspace policy before model load. The old open and all
ABI-2 layouts retain their original meanings and width 1. Model info reports
the admitted native batch capacity. `lie_sequences_decode` accepts unique
sequence handles from the same model/owner and one outcome per row. Cancelled
rows expose no tokens; cancellation is cooperative and completion-based.
Any non-cancellation execution failure poisons the model, suppresses all outputs
from that call, and is never retried by LIE. The pinned upstream implementation
may internally recover an untouched row; this remains delegated behavior.

`lie_inference_prepare` obtains bounded output reservations from ready rows.
`lie_inference_run` calls scalar decode for one selected row, batch decode for
multiple rows, and performs no work for zero rows. No waiting/coalescing timer,
background GPU thread or per-kernel callbacks are added. All completed frontiers
are validated before any caller can publish: token count/range, EOS and position.
The caller retains handles and commits/aborts every reservation after completion;
on a fatal return it must retire the model, not retry. The worker also validates
all token-text sizes before any batch output publication.

The reusable dispatcher is C17, independent of HTTP, used by both the worker
and `synapse-lie-bench --execution reactive`. Prefill remains completed bounded
chunks. Numerical kernels and upstream synchronization are unchanged. This
implements reactive admission of actual batched inference work; it does not
claim an asynchronous dependency graph inside a single model forward.

HTTP admission now permits 262144 total tokens, an 8 MiB JSON body and 1024
messages. These are bounded frontend limits; existing executor ABI-2 layouts
remain unchanged. `lie_model_tokenize` uses the same 8 MiB input bound. Model
admission and qualification remain specific to context and active sequence count.
