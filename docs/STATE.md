# C17 prefix state, RAM cache and optional SSD

RAM prefix retention is **enabled by default**, with a lazy 4 GiB budget shared
by consumers of each core instance. HTTP and `synapse-lie-bench --suite core`
use the same implementation; separate processes do not share a RAM store.
`--prefix-cache-mib N` changes the budget; `0` explicitly disables retention for fresh-work comparisons. The normal
per-sequence KV/recurrent working state is still required when retention is off.
Only optional SSD persistence defaults off. With SSD disabled, no persistent-state
directory is created, scanned, read or written. The implemented opt-in is described
in [SSD-PREFIX.md](SSD-PREFIX.md). Original-weight [SSD restart and C1 cache
comparisons pass through 128K](SSD-GPU-COMPLETION.md); HTTP/concurrent SSD and
device fault injection remain separate gates.

The generic C17 `lie_state` component contract owns section validation, overflow
checks, host allocation, immutable payloads and capture/restore coordination.
`src/models/qwen_flash_state.c` owns Qwen AR component geometry independently
of the device platform. `src/prefix_cache.c` owns lookup, admission, lifetime,
utility eviction and accounting. The transitional adapter only binds model fields
and performs completed host/HIP copies; it does **not** call Gufo's snapshot
serializer or store an opaque Gufo snapshot. Its explicitly selected access
variant changes three friend declarations in two independently fetched headers,
with separate source/build hashes. Active execution storage and forward math
remain delegated; this does not claim an autonomous C model executor.

## Implemented RAM contract

- Eight immutable checkpoint slots, bounded by the configured total bytes.
  Account the allocation containing descriptor and payload; allocator/driver
  overhead and active sessions are separate. Allocation is lazy. Evict the lowest-utility
  eligible entries before capture; retained, in-progress capture and explicit
  codec buffers must fit the budget. LRU remains a compile-time alternative.
  Oversized checkpoints or a failed host allocation skip optional retention.
- Capture at most once per request, at its largest completed chunk boundary,
  or the entire prompt if shorter than a chunk. Match exact physical token IDs.
  Reuse the longest stored prefix; never trim a longer recurrent state. A short
  unaligned checkpoint serves only an exact hit, preserving chunk shapes on
  extensions. Similar strings or client conversation IDs are not cache keys.
- Each model open has a process-local domain. Same domain, context/chunk,
  component representation and shapes are checked before restore mutation.
  Because entries never leave the live model instance, they cannot cross model,
  device, build or process reopen. This is not a stable disk compatibility ID.
- A recipient is an empty independent sequence. Sampling, seed/RNG, penalties,
  output parsing and transport state belong to the new request. Only pre-decode
  confirmed text prefixes are captured. MTP/vision states are refused.
- The C model representation includes physical tokens, host logits, n-gram
  history, PLE history, convolution and recurrent state, attention K/V,
  chronological unpooled index keys and pooled block keys plus their frontier.
  Ring wrap is handled by the binding, not exposed in the core payload.
- The existing single device owner performs completed transfers. Owner-only
  entry mutation pins the selected checkpoint until the synchronous call ends;
  cancellation is latched and borrowed storage stays alive through completion.
  There are no extra engine threads. No HIP error may become a cache miss:
  failed mutating restore poisons the runtime and retires affected work.
- Cache policy is shared by every core client. `lie_core_options_init` selects
  the RAM default; explicitly setting `prefix_cache_bytes=0` disables it. A
  provider without component-state support refuses enabled cache at readiness;
  it does not silently ignore the requested policy. Pristine reference builds
  must use explicit RAM-off settings.

The `.157` headless, Debug and sanitizer fixtures exercise ownership, isolated
clones, budgets/eviction, incompatible domains, faulty providers, cancellation,
Chat/Responses usage and direct bench graphs. Device qualification passes the
[predeclared GPU protocol](STATE-GPU-PROTOCOL.md), with [full results](STATE-GPU-RESULT.md)
through 128K and C8. CPU results remain NOT-INFERENCE.

## Optional SSD persistence — explicit opt-in

The C17 store and raw-v1/compressed-v2 component codecs are implemented in the shared core.
Enable with `--prefix-ssd-dir ABSOLUTE-DIRECTORY`, `--prefix-ssd-quota-mib N`
and `--prefix-ssd-staging-mib N`, supported by server and `--suite core`.
RAM remains independently enabled by default. There is no implicit disk spill.

One bounded I/O worker, one operation slot, an explicit staging reservation,
private paths, exclusive ownership, quotas, atomic commits and full identity /
checksum validation preserve the owner-thread restore boundary. Immutable RAM
states use reference pinning for asynchronous writes; completed reads remain
reserved until upload/release. Neither HTTP nor the numerical worker performs
serving-time disk syscalls. Startup identity and index admission occur before
READY. The [exact format, accounting, tests and remaining device gates](SSD-PREFIX.md)
are authoritative. Active KV paging and PLE/weight streaming are separate features.

## Retention policy and compression boundary

The shared C17 core now implements these independent default-ON CMake options:

| Option | Enabled behavior | OFF behavior |
|---|---|---|
| `LIE_CACHE_UTILITY` | Decaying reuse, tokens per retained byte, anchor/continuation weighting | LRU |
| `LIE_CHECKPOINT_COMPRESSION` | Bounded lossless LZ4 checkpoint packing, raw fallback | Raw checkpoints; no LZ4 dependency |

Utility is `(1 + decayed_hits) * tokens / retained_bytes`, doubled for an anchor
and multiplied by 0.125 for a superseded continuation. Hit weight halves every
64 logical cache accesses; ties use oldest access. A newly captured prefix that
extends an existing prefix is a continuation. SSD uses the larger of file and
allocated-block bytes. This is internal automatic prioritization, not an API
for arbitrary client priority. Pins, valid prefix geometry and admission limits
remain authoritative. Utility metadata resets on restart; a persistent priority
index is not implemented. The algorithm is independently written, with no DS4
source imported.

Packing operates only on a uniquely owned immutable state. Physical tokens stay
uncompressed; all remaining bytes, including floating-point bit patterns, use
independent 1 MiB LZ4/raw blocks. Payloads below 64 KiB stay raw. At least 12.5%
saving is required; insufficient budget, allocation failure or incompressible
input leaves the original unchanged. The budget includes the source, candidate
and explicit codec scratch; allocator internals/overhead and device memory are
separate. Restore reserves the complete expanded payload and may evict other
entries first. A checkpoint that cannot fit with its restore workspace is not
promoted from SSD into RAM. No fixed compression ratio is promised.

Captures and RAM expansion remain completed calls on the single device owner;
packing does not add a thread or GPU overlap. These CPU passes can increase
capture/restore latency and delay peers. SSD import packing runs on the existing
bounded I/O worker, checks cancellation between blocks, and stays inside its
staging reservation. Serving credits, bounded queues and cancellation ownership
remain in the core. Measure C1 timings and C2 responsiveness separately; the
presence of a codec does not prove a reactive speedup.

Upstream [DS4's disk eviction score](https://github.com/antirez/ds4/blob/main/ds4_kvstore.c),
reviewed 2026-10-02, also weighs reuse, saved tokens per byte, checkpoint purpose
and superseded continuations. Its header's `quant_bits` identifies routed expert
weight quantization; it is not KV precision. LIE does not claim identical policy.

DeepSeek-specific KV compressors in [DS4's model engine](https://github.com/antirez/ds4/blob/main/ds4.c)
use learned projections and compressor state. Those architectural savings cannot
be transplanted unchanged into Qwen. Qwen active K/V and block keys remain F16,
with the required F32 recurrent/other components. Checkpoint packing does not
reduce the active device allocation. Low-bit active KV still needs a distinct
model representation, matching attention/prefill/batch kernels and long-context
quality/performance qualification; it is not implemented by the lossless codec.

CPU fixtures cover exact special floating bits, mixed/raw blocks, valid-checksum
malformed frames, budgets, pins, utility aging/eviction, core restore and SSD
restart. These are NOT-INFERENCE. Prior [128K GPU results](SSD-GPU-COMPLETION.md)
qualify the earlier raw representation, not the new default policy/codec.

## Two distinct kinds

`prefix_checkpoint`: immutable model frontier at an exact list of processed
physical tokens. A new request gets its own sampler/RNG and parser state.

`resumable_session`: model frontier PLUS exact continuation state: sampler
configuration, RNG/draw state, penalties/history, accepted-but-not-emitted token
bytes/UTF-8 remainder, stop matcher/parser, tool-call state and turn metadata.
Predictor/controller state must be saved or reconstructed by a specified replay.
No exact resume claim if any of these are omitted.

Qwen Flash Next is hybrid. LIE must own and capture its token history, logits,
attention KV, recurrent/SSM and convolution state, positions and, when supported,
MTP carry/history/rollback and controller state. Sampling/RNG must be included
explicitly for resumable sessions. The implemented AR checkpoint uses the C-owned component contract above.
Future modality components require an explicit version and qualification. See
[BACKEND.md](BACKEND.md).

Gufo `SessionSnapshot` and external `SamplerState` were audited as coverage
references. Neither Gufo v14 nor DS4 native19 is an accepted LIE payload. The
version 1 C codec imports only its own validated component representation, never
one of these opaque upstream payloads.

MTP identity includes the predictor weights/configuration and arithmetic policy.
Only verified target tokens define the reusable frontier. Draft/rollback state
and acceptance-controller history must be captured or reconstructed explicitly;
accepted output waiting for network credit belongs to resumable-session state,
not a new request's prefix checkpoint. No unverified draft may enter a checkpoint.

Vision identity includes consumed-image content, preprocessing/encoder identity,
image placement and physical/rotary positions. Text tokens alone are insufficient:
two requests can have identical image placeholder tokens and different pixels.
The inspected Gufo snapshot requires matching images attached at restore and
does not serialize pixels. A resumable SSD session therefore needs bounded owned
image material or an explicit caller-supplied matching-input contract; persisting
the opaque model payload alone cannot promise autonomous multimodal restart.
Choose and qualify this contract before enabling image-state persistence.

## Version 1 disk framing

The [frozen component envelope](SSD-PREFIX.md#identity-and-version-1-framing)
uses a 160-byte little-endian header, a bounded table of 64-byte section records,
and the complete immutable payload. SHA-256 covers all framing and payload bytes
with the checksum field zeroed. A separate complete model/build/execution identity
is checked before the new live model domain is assigned. Layout validation and a
nonmutating provider geometry check precede upload. No cross-backend portability
or exact sampler/session continuation is claimed.

## Write/restore lifecycle

1. Only the device owner selects a completed, confirmed frontier. No in-flight
   kernel may reference captured storage. Retain it until immutable host capture
   completes. Enqueue bounded disk work, not a full write on every token.
2. Write a same-directory exclusive temporary regular file; check ownership,
   reject symlinks/hardlinks, bound lengths and space. Flush data with fsync,
   atomic rename, fsync parent. Intended durability: acknowledged commit survives
   process restart and ordinary power loss subject to filesystem/device guarantees.
3. Read/validate the entire bounded candidate into controlled staging before GPU
   upload. Corruption, incompatible identity or missing file => clean miss then
   prefill. After a mutating restore is admitted, any failure is fatal to that
   session, NOT miss-and-forward. Record read/deserialize/transfer separately.
4. Account logical/allocated SSD bytes and staging memory. Idle-cache eviction
   cannot remove a payload still pinned by an in-flight reader/capture.
5. A longer recurrent state cannot be trimmed to an arbitrary common prefix.
   Reuse only exact checkpoint frontiers, otherwise select an earlier valid
   checkpoint plus replay or recompute. Tool/template boundaries use processed
   tokens, not similar visible strings.

## Required validation before device acceptance

Disabled mode with zero persistent-store I/O, RAM-only reuse independent of SSD,
explicit enable/path/quota validation, private permissions and no deletion on
disable; same-process and restart save/resume, isolated clones, exact future
continuation, AR and then MTP rollback, corrupt/truncated/oversized/foreign files,
atomic-write failure phases, interrupted workers, quota/eviction races and incompatible model,
template, context, dtype and payload versions. Benchmark restore wall time,
transfer and avoided prefill against recomputation; SSD is not assumed faster.
Active-state paging and weight streaming are explicitly outside this version.
For vision include different pixels with identical placeholder tokens,
preprocessing/encoder changes and missing restart inputs. For MTP include
different predictor identity, rejected drafts, rollback and queued accepted
output. Disabled capabilities refuse before restore mutation.

## Responses request state

Stateless Responses requests normalize into the same owned chat history, job
and flow. No new recurrent-state store or parallel model scheduler is created.
The UI independently retains the tool policy; the core owns a bounded normalized
copy, and the HTTP adapter releases its parsed input after admission.
A text stream may hold a bounded final response projection while its current
flow loan stays pinned through write completion. Typed response terminals do
not change the dispatch frontier, accounting or cancellation ownership.
