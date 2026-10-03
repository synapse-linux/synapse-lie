# Experimental transitional execution ABI 2

The adapter delegates to Gufo Model/Session. **This is permitted for bootstrap,
not proof of an autonomous LIE backend.** [BACKEND.md](../BACKEND.md) defines the
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

## Vision branch extension

[VISION](../development/VISION.md) now has an additive, model-neutral C
contract in `include/lie/vision.h`. Executor ABI 2 scalar AR entry points retain
their meanings. The shared request advances to `LIE_CORE_REQUEST_ABI=3` for owned image spans.
New capability structures have ABI 1 and an exact struct size;
upstream model types stay inside the provider adapter. This is CPU-contract
validation and provider linking, not original-weight qualification.


## Additive state components

State ABI 2 gains `LIE_STATE_KVC_AUX` and the `LIE_STATE_AUXILIARY` boundary
role without changing existing structure layouts or enum values.
`lie_state_kvc_parts` validates the complete component map and returns separate
DS4-payload and auxiliary lengths. Invalid descriptors refuse before allocation
or transfer. Old AR files retain footer version 1; new auxiliary files use
version 2, require checksum admission and retain a fresh destination sampler.
The vision binding now advertises complete prefix state only with the verified
DS4 complete-history provider. Legacy providers advertise zero and require
explicit cache-off configuration. The additive `LIE_STATE_CACHE_SCOPE` role and
`lie_vision_prompt_cache_scope` function do not change existing structure layouts
or enum values. Generic cache/SSD APIs gain scoped variants; existing wrappers
continue to select text-only state. Scope extraction is nonmutating and requires
an uncompressed U8[32] component. Generic layout validation rejects duplicate,
misplaced or malformed scope sections. GPU qualification remains separate.

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
  violation. Reported token-text size must fit its caller buffer. MTP is not
  advertised; native AR multirow submission uses the additive contract below.
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

The C17 parser owns normalized JSON and message content. The HTTP shim copies
normalized input into the core and frees/zeros the parsed request on successful
admission; refusal preserves caller ownership. The UI retains a deep, independent
schema copy. No admitted core job retains a json-c object. Adapter translation bounds aggregate spans/strings
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
completed to enqueue-only silently. See [INFERENCE-REACTIVE.md](../INFERENCE-REACTIVE.md).

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

## Implemented component-state extension (state ABI 2)

The additive store function `lie_store_write_prompt` accepts the original prompt
length/key kind to protect a reusable prefix during generated-state persistence.
It preserves existing struct layouts and file formats. See
[prompt-retention admission](../development/CACHE-PROMPT-RETENTION.md).

`lie/state.h` is an additive C17 contract; executor ABI-2 structs stay unchanged.
`describe(NULL)` plans capture; `describe(source)` validates a prospective restore
into an empty sequence without mutating it. Sections carry role/layer, dtype,
rank, dimensions, checked size and offset. `format=ALIGNED` keeps 8-byte section
alignment; `format=KVC` partitions the exact model payload without padding and
requires 4-byte token alignment. ABI 2 adds format, model-id and quantization-label
fields plus header/scalar roles; all static clients must rebuild together. Model
id and quantization labels never authenticate weights or indicate KV precision.
Generic C code validates
length arithmetic, unique components, physical-token/logit sections and complete
layout equality before allocating/copying or admitting a restore. Immutable
handles expose read-only descriptions/tokens. SSD reads verify stable identity,
framing and integrity before creating a live-domain state; providers validate
model payload semantics before device mutation. Unbound foreign KVC input remains
offline. `lie_backend_state_format` declares the compiled provider format, with
explicit synthetic labels for fixtures.

`lie_state_plan/capture/restore/destroy` own host storage and lifecycle;
`lie_sequence_state_describe/read/write` are provider bindings invoked only by
the device owner at a completed frontier. Read/write returns only after transfers
finish, including cancellation/error cleanup. A mutating failure is fatal and
never triggers fallback prefill. `LIE_RESOURCE_LIMIT` is a nonmutating optional
capture allocation/budget refusal. Existing executor status values retain their
numbers. The C17 Qwen layout module supplies the model-specific components;
Gufo types, private-field access and HIP copy operations stay inside the adapter.

`lie_core_options_init` defaults RAM retention to 4 GiB. The appended
`prefix_cache_bytes` option is an explicit byte budget; zero disables retention.
All consumers of this experimental static core API must be rebuilt together.
Backend state capability is explicit; missing support with RAM enabled refuses
readiness. Model-open domains prohibit cross-instance/restart restores. SSD
uses a separate stable identity and versioned component codec.
See [STATE.md](STATE.md) for compatibility, budgets, exact prefix/chunk eligibility
and independent sampler semantics. The two new executor phases are `capture`
and `restore`; their wall durations are separate from executed PP/TG.

`lie_state_compress` optionally replaces a uniquely owned handle without changing
its model representation or any payload bit. `lie_state_bytes` reports retained
storage, `lie_state_expanded_bytes` its raw equivalent, and
`lie_state_restore_workspace` the temporary expansion requirement. The opaque
handle keeps physical tokens directly readable. Providers continue to receive
fully expanded typed payloads. KVC payloads bypass optional extra compression
and have zero expansion workspace. Executor ABI 2 remains unchanged.
Core/store snapshot structs grow in this experimental static API, requiring
all consumers to rebuild together. See [the codec contract](SSD-PREFIX.md#compressed-version-2).

## Planned state, MTP, vision and owned execution contracts

The remaining items below are requirements for future contracts. RAM prefix
state is implemented by the separate extension above; SSD/exact resume, MTP
and vision use separate capability contracts, outside scalar executor ABI 2. Keep completed scalar/batch semantics.
Negotiate state, MTP, vision, format/dtype, native batch capacity and context/RoPE
profiles explicitly; refusing an unsupported capability must precede mutation.

The client-facing core API is distinct from this provider/executor ABI. The
shared core owns jobs/sessions, scheduling and resource/cache policy; HTTP,
direct benchmark and future chat/eval consume owned normalized inputs and typed
events. Input paths must include physical tokens as well as messages, with
explicit capability-gated scoring/logit operations for evaluation when added.
Core headers and admitted jobs must not depend on HTTP parser trees, socket
types, SSE options or wire status codes. The implemented copy/release rules
below replace the former worker ownership of `lie_chat_request.json_owner`.
Historical low-level executor diagnostics remain labelled separately from full
core lifecycle tests. See [the core extraction contract](ARCHITECTURE.md#shared-core-and-client-boundary).

- State: exact model/input identity, kind and payload version, bounded immutable
  capture, pure validation before mutating restore and explicit component
  completeness. Only the device owner captures/uploads model state; C cache and
  disk workers consume immutable host payloads with pinned lifetimes. A failed
  mutating restore poisons the session/runtime according to the execution failure
  contract, never becomes an ordinary cache miss. See [STATE.md](STATE.md).
- MTP: bounded ordered vectors of verified committed output plus actual token
  count, completed position, stop status and per-row outcomes. Reserve output
  capacity for the maximum admitted burst, then commit actual tokens and release
  unused credit. Do not reinterpret scalar `emitted` (0/1), expose drafts, share
  RNG or let a blocked row consume a peer's credit. Separate draft/accept/reject
  accounting from committed token usage; represent pending accepted output and
  rollback lifetime explicitly.
- Vision: bounded owned/prepared image inputs, encoder/preprocessing identity,
  image placement and physical positions. Parsing/upload preparation is separate
  from device-owner encoder/forward work. Refuse unsupported modality before
  opening a mutable sequence; declare byte/pixel/patch/context/workspace budgets.
  Text-only token IDs cannot identify image state.
- Owned numerical boundary: versioned C buffer/tensor descriptors with dtype,
  packing, shapes/strides/alignment, residency, lifetime and arithmetic identity;
  explicit workspace and fused/native-batch capability. The C model layer owns
  topology/state and invokes qualified operations. Keeping an opaque whole Gufo
  Model/Session behind an operation table is still delegation.
- Async evolution: distinct submission/completion handles and per-row outcomes,
  device completion/failure, cancellation and retained buffers. Add only when an
  actual overlap implementation needs it; `LIE_OK` remains completed today.

Each contract must have a real producer/consumer and focused lifetime/parser
sanitizer checks before integration, followed by original-weight GPU gates.
Language/build ownership and feature qualification remain separate; see the
[separation assessment](../BACKEND.md#separation-assessment--2026-10-02).


## Shared core client API 1

`lie/core.h` is an experimental C client contract, distinct from executor ABI 2.
`lie_core_request_init` sets required version/size tags, greedy generation
(`temperature=0`, `top_p=1`, `seed=-1`) and output limit 128. The caller chooses
exactly one input: normalized messages/tools, physical token IDs, or raw UTF-8
text (no implicit chat template). Initialize `*out` to NULL before submit.

`lie_core_submit` borrows input only during the call and deep-copies nested
arrays/strings into one bounded arena. Successful submission never steals caller
storage. Return codes are 0 admitted, 1 not ready/stopping, 2 admission full,
3 invalid input/allocation failure. Copy reservations plus queued/active jobs are
bounded to eight, with at most 32 MiB normalized input per admission. Vocabulary,
formatted physical context and provider checks precede sequence mutation on the
owner; asynchronous refusal is reported through the job terminal. No queue or
provider call runs on a protocol-owned JSON tree.

The core grants eight initial output credits. Clients release each output loan,
then return demand through `lie_flow_request`; without more credit a row cannot
advance. A job has one consumer reference plus the core's in-flight reference.
`lie_job_release` cancels unfinished consumption; release outstanding output loans
first. After `lie_core_stop`, wait for STOPPED, release all consumer references
and quiesce every client API call (including concurrent submit) before destroy.
STOPPED alone does not authorize racing destruction against client calls.

`lie_job_prompt_tokens` requires a prepared job. Both it and
`lie_job_output_tokens` copy a metadata-protected snapshot and return
`LIE_BUFFER_SMALL` with the required count when capacity is insufficient. No
partial copy or provider call occurs. Output IDs describe validated generation,
not delivery; cancellation may discard an undelivered generated token. Physical
prompt storage (up to context times four bytes) and output IDs (up to output limit
times four bytes) remain until the last job reference. Retired jobs held by a
client therefore retain memory; clients must release them. These witnesses are
not reusable KV checkpoints. Request-copy storage is freed at retirement.

The HTTP legacy submit shim preserves its transfer-on-success interface by
freeing the parsed request after the core accepts its independent copy. The
core and its public headers have no JSON, libuv, llhttp or socket dependency.
`lie_flow` retains Linux eventfd/pthread dependencies; this extraction does not
claim cross-platform portability. CPU acceptance is in [CORE-EXTRACTION.md](../development/CORE-EXTRACTION.md).


## Optional C17 SSD store contract

`lie/store.h` owns a versioned prefix file representation and one asynchronous
I/O operation at a time. `lie_core_options.ssd` is zero-initialized by
`lie_core_options_init`; enabling requires an absolute directory and independent
quota/staging limits. Recompile consumers of this experimental options struct.
The provider identity hook is called only for explicit SSD admission, before READY.
It supplies full bound-file identity and the current live domain; no upstream
snapshot types enter the common store. The C core now links OpenSSL Crypto for
SHA-256 even in the HTTP-free composition.

`lie_state_retain` pins immutable host data across writer execution. A successful
`lie_store_take` transfers the result payload, keeping its operation slot and
staging reservation pinned. Call `lie_store_result_release` after upload or
discard; optionally retain the state into RAM first. Release taken results before
closing the store. Cancellation latches affect reads between bounded transfers;
no filesystem syscall or GPU operation is forcibly preempted. Provider calls
still run only on the device owner, and mutating failures never become misses.
See [SSD-PREFIX.md](SSD-PREFIX.md) for framing, durability and qualification limits.

## Cache-policy client extension (request ABI 2)

`lie_core_request` now carries `lie_cache_metadata cache`: bounded byte text,
opaque trailer, purpose and extension/key-kind flags. Submit deep-copies these
bytes within the normalized-input arena. Callers must rebuild and use
`lie_core_request_init`; old request version/size tags are refused.
`lie_job_cache_metadata` returns an independent metadata copy after a successful
restore; initialize the output to zero and release it using
`lie_cache_metadata_clear`. A miss returns empty metadata. Do not reuse a live
owned output struct without clearing it first. Store results similarly own
metadata until `lie_store_result_release`.

`lie_core_options.cache_policy` controls shared capture/reuse behavior; snapshots
expose it and separate RAM/SSD index budgets. Consumers of these experimental
structs must rebuild together. `lie_model_chat_anchor` is an additive provider
query for the stable model-specific chat prefix; unsupported providers can
return no anchor. It performs no forward inference and exposes no upstream type.
State component ABI and executor ABI 2 are unchanged. Context growth must pass
the provider's layout checks before mutation; cross-weight/quantization restore
remains refused. [Policy and format details](CACHE-DS4-POLICY.md).

Capture may follow completed autoregressive generation or an EOS boundary;
`lie_sequence_state_describe(source == NULL)` validates the live token frontier
and component geometry. Restore continues to require a fresh, unstarted target.
Capturing a source with an active sampler does not copy that sampler or its RNG.
A capture failure publishes job error metadata before waking the flow consumer.

## KVC wire interchange API

`lie/kvc.h` and `lie/kvc_qwen.h` expose additive shared C17 codecs, built by the
default-ON `LIE_KVC_INTERCHANGE` option. Existing executor, request and state ABIs
are unchanged. The library owns envelope framing, byte budgets and Qwen wire
layout; it does not own or borrow an executor session. Byte views are immutable
and unaligned; owned records must outlive their borrowed views. Outputs publish
only on success, except caller-owned encode/write buffers, which must be discarded
after any error. No implicit file publication, model identity binding or restore
occurs. See [format, cancellation and lifetime contract](KVC.md).

`lie/kvc_qwen_map.h` adds completed host component projection/export. Projected
layouts have domain zero and cannot be admitted as live states. Byte output is
caller-owned; conversion never mutates a sequence or binds model identity.
Export requires complete auxiliary index/pool spans where native retention has
discarded them, with exact overlap checks against known native slices. Ordinary
state, request and executor ABIs are unchanged. State layout helpers were moved
unchanged to `state_layout.c` so offline mapping links without provider stubs.
