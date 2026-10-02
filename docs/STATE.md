# C17 prefix state and RAM cache

RAM prefix retention is **enabled by default**, with a lazy 4 GiB budget shared
by consumers of each core instance. HTTP and `synapse-lie-bench --suite core`
use the same implementation; separate processes do not share a RAM store.
`--prefix-cache-mib N` changes the budget; `0` explicitly disables retention for fresh-work comparisons. The normal
per-sequence KV/recurrent working state is still required when retention is off.
Only optional SSD persistence defaults off. SSD is not implemented yet: no
persistent-state directory is created, scanned, read or written by this cache.

The generic C17 `lie_state` component contract owns section validation, overflow
checks, host allocation, immutable payloads and capture/restore coordination.
`src/models/qwen_flash_state.c` owns Qwen AR component geometry independently
of the device platform. `src/prefix_cache.c` owns lookup, admission, lifetime,
LRU eviction and accounting. The transitional adapter only binds model fields
and performs completed host/HIP copies; it does **not** call Gufo's snapshot
serializer or store an opaque Gufo snapshot. Its explicitly selected access
variant changes three friend declarations in two independently fetched headers,
with separate source/build hashes. Active execution storage and forward math
remain delegated; this does not claim an autonomous C model executor.

## Implemented RAM contract

- Eight immutable checkpoint slots, bounded by the configured total bytes.
  Account the allocation containing descriptor and payload; allocator/driver
  overhead and active sessions are separate. Allocation is lazy. Evict idle LRU
  entries before capture, so retained plus in-progress capture fits the budget.
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

## Optional SSD persistence — required feature, explicit opt-in

The user requires an optional SSD save/restore facility in addition to in-memory
prefix reuse. The ordinary per-sequence attention KV already used by inference,
retaining a reusable frontier across requests, and persisting that frontier across
process restarts are distinct capabilities. RAM reuse is implemented as described above; restart persistence remains pending.

- SSD persistence is **disabled by default**. In-memory reuse must work without
  it. Disabled means no persistent-state directory creation, scanning, reading or
  writing; no implicit spill to disk when RAM becomes scarce.
- Enabling the persistent store requires an explicit server option. Expose its
  directory and disk quota, independently of the RAM-cache budget. CLI spelling
  and config schema are not frozen yet; there is no working SSD flag today.
- Use only a LIE-owned private directory (proposed default when enabled:
  `$HOME/.local/state/synapse-lie/sessions`), never discover or reuse DS4 caches.
  State is sensitive conversation-derived data; use private directory/file
  permissions. Persistence does not imply encryption at rest.
- Save/restore complete compatible hybrid state, not an attention-KV-only dump.
  Restart reuse, bounded staging/I/O, atomic writes, eviction and admission retain
  the lifecycle and validation gates below. SSD reads/writes must not block the
  HTTP loop; no per-token disk writes or unbounded background queue.
- Disabling persistence stops using the store; it must not implicitly delete
  existing files. Explicit cleanup may affect only eligible LIE-owned entries,
  never an in-flight/pinned payload or another application's state.
- Benchmark RAM reuse, SSD restore and recomputation separately. SSD support is
  a required capability, not a promise that restoring is always faster or that
  active-state paging/weight streaming is supported.

Required configuration semantics, with spelling to be frozen during implementation:

| Control | Required behavior |
|---|---|
| RAM prefix budget | Enabled by default, 4 GiB; explicit byte limit; zero disables retention; eligible idle entries can be evicted before admission refusal |
| SSD enable | Explicit opt-in, default off, independent of RAM retention |
| SSD directory and byte quota | Private LIE-owned path, validated quota; no implicit discovery of another engine's store |
| Capture/read staging and queue budgets | Bound resident bytes and concurrent I/O jobs; reserve space before capture/read and retain buffers until completion |

The implemented C cache manager is shared by HTTP, direct benchmark and future
chat/eval clients. SSD will consume the same C-owned components through a new
versioned disk codec, with bounded staging and explicit identity admission.
It must not reintroduce a backend-owned opaque serializer.

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
current RAM representation has no file reader or byte import API.

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

## Proposed on-disk framing (must be frozen and tested before writer code)

Little-endian envelope with magic, envelope version, fixed header length,
kind, total length, metadata length, token count, payload length and checksum
algorithm. Bounded canonical metadata and LE int32 token array precede a
LIE-owned, versioned component payload with an explicit layout contract. It
needs its own stable identity and qualification, not reinterpretation of upstream
bytes or a dump of the in-process C struct. Unsupported cross-engine state is refused before mutation, unless
an explicit versioned migration is implemented and qualified. SHA-256 covers the
declared metadata + tokens + payload; lengths, coverage and identity must validate
before restore admission.

Compatibility identity must cover full weight/shard identities and quantization,
model config, tokenizer vocabulary/normalization, actual template/reasoning mode,
physical/rotary positions and RoPE settings, context/prefill/execution policy,
state dtype/representation, backend payload version and relevant arithmetic
build identity. No promise of cross-HIP/CUDA, quantization, capacity or build
portability. Model publisher terms remain separate from the state format.

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

## Required validation before enabling

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
