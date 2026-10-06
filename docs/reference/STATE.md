# C17 prefix state, RAM cache and optional SSD

The selected static RoPE profile and the exact frequency/amplitude plan bind
SSD cache identity. Native policy identity is preserved; YaRN2/YaRN4 checkpoints
cannot be reused by native or differently scaled models. RAM stores belong to
one model runtime and likewise cannot cross profiles. DS4 tensor payload framing
does not change. See [context configuration](../guides/CONTEXT.md).

Automatic output budgets are resolved by the core after prompt preparation;
they do not alter prefix identity or DS4 tensor framing. A compatible cached
prompt must still leave room for the resolved output budget. An explicit budget
that exceeds the remaining context, or an automatic request with no output room,
refuses before sequence creation. See the [request contract](ABI.md).

RAM prefix retention is **enabled by default**, with a lazy 4 GiB budget shared
by consumers of each core instance. HTTP and `synapse-lie-bench --suite core`
use the same implementation; separate processes do not share a RAM store.
`--prefix-cache-mib N` changes the budget; `0` explicitly disables retention for fresh-work comparisons. The normal
per-sequence KV/recurrent working state is still required when retention is off.
Only optional SSD persistence defaults off. With SSD disabled, no persistent-state
directory is created, scanned, read or written. The implemented opt-in is described
in [SSD-PREFIX.md](SSD-PREFIX.md). Original-weight [SSD restart and C1 cache
comparisons pass through 128K](../archive/SSD-GPU-COMPLETION.md); raw-state HTTP/concurrent
SSD also passes [R5](../archive/CACHE-FEATURES-GPU.md). Device fault injection remains separate.

The generic C17 `lie_state` component contract owns section validation, overflow
checks, host allocation, immutable payloads and capture/restore coordination.
`src/models/qwen_flash_state.c` owns Qwen AR component geometry independently
of the device platform. `src/prefix_cache.c` owns lookup, admission, lifetime,
utility eviction and accounting. The transitional adapter only binds model fields
and performs completed host/HIP copies; it does **not** call Gufo's snapshot
serializer or store an opaque Gufo snapshot. Its explicitly selected access
variant includes field access and, with default `LIE_DS4_RUNTIME_CACHE=ON`,
complete raw index retention and eager pooled keys. Source/build hashes identify
this separately from the earlier friend-only control. Active execution storage and forward math
remain delegated; this does not claim an autonomous C model executor.

The newer `1bff953` Point grammar/history/distribution GPU controls and seeded
profiles preserve these DS4 payload and cache identities. Their
[receipt](../development/validation/c17-sampling-point-gpu-2026-10-05.json)
is wire/generation qualification with prompt cache disabled, not new original-
weight RAM/SSD continuation, mixed-history lookup or state-fault evidence.

Immutable reasoning/tool grammar composition now belongs to C17. Construction
copies source tables/names and imports ordered lexeme origins by program
identity; the private adapter retains the corresponding immutable predicates.
Construction and imported templates are not model-prefix state, KV cache or
SSD payloads. Grammar stacks remain independently copied request state, including
speculative verification; no mutable reasoning/tool phase enters the model or
cache. The additive description view borrows source tables until program release.
[Host validation](../development/validation/c17-composition-host-2026-10-06.json)
does not qualify new original-weight continuation, correction or restore.

The compiled-schema C17 cache stores opaque grammar programs and copied schema
keys. It is independent of KV/recurrent state, prefix retention and SSD files;
its insertion/eviction never changes model cache identity or DS4 framing. Client
copies outlive eviction. No schema cache is persisted in model checkpoints.

The C17 Unicode context owns construction-only set/input storage. It performs
no model or checkpoint operation and changes no DS4 RAM/SSD payload or cache
identity. Sealed grammar programs copy their runtime tables independently of
that context. ICU/Unicode version diagnostics are not persisted model IDs.

Request-local [C17 sampler history](../development/C17-SAMPLING.md#request-history)
tracks prompt repetition and committed generated counts. It is rebuilt for each
request and is not serialized into DS4 model-prefix payloads. Model RAM/SSD cache
identity, predictor state and tensor framing remain unchanged. Copies retain
independent history; RNG/deferred draws and grammar keep their existing owners.

The owned C17 compact/speculative probability component uses borrowed rows and
caller-owned scratch only. It retains no proposal, model state or pointers, and
changes no DS4 RAM/SSD format, cache identity or predictor/controller checkpoint.
Verification refusal does not publish its acceptance draw or a correction token.
Rollback, pending/deferred corrections and confirmed model frontier remain with
the existing inference owner; host probability checks do not qualify GPU restore.

Owned C17 byte-grammar snapshots are request-local and independently copied
while sampling or verifying speculation. Programs/mask-cache predicates are not
serialized in DS4 RAM/SSD model-prefix payloads. Failed expansion/advance or
canonicalization does not change the request's live state. The provider still
supplies typed predicate/container storage and the remaining binary64 codec. Concrete
rule/primitive construction and productive/nullable/cycle validation now use
the C17 builder. Unicode registry/input and snapshot read/write planning/copies
now use shared C17 contracts, with ICU retained for set/property/conversion
semantics. Its private layout requires matching source, archive and application
rebuilds.
Original-weight grammar/correction/cache continuation remains pending.

C17 schema transformations borrow immutable typed JSON views and publish only
private staging results. Equality/pointer/pattern scratch retires on every path;
the provider retires its deque/container staging at the exception boundary.
Conjunction refusal leaves input trees and the published result unchanged.
Typed JSON/predicate/storage and the binary64 codec
remain transitional. These construction objects add no inference state, DS4
payload, RAM/SSD identity, RNG transition or reactive frontier.

Finite-value normalization owns only private construction results and temporary
scratch. Ordered canonical objects preserve schema property order, followed by
permitted extra members; array order remains unchanged. Exclusion publishes no
value and refusal preserves the previous result. Literal and object/array
rules copy spans into the C builder. Nested visitor callbacks share one private
property/character counter object; partial successful increments are retired
with failed construction. Sixteen inline frames and bounded stack/quote/symbol/
required-name buffers retire on success and refusal. These objects add no model
or sampler checkpoint, DS4 RAM/SSD payload, cache identity or reactive frontier.
The newer source still requires matching provider/application rebuild and its
own original-weight continuation/resource/cost qualification.

C17 numeric policies own their copied canonical bounds and multiple, including
integer-grid reduction. Prefix checks own and retire private arithmetic scratch;
refusal changes neither the policy nor the caller's match/value outputs. These
policies are not serialized in DS4 model-prefix payloads and change no cache
identity. The JSON value bridge, JSON Schema compiler and Unicode-set/property
identity remain transitional; host exact-decimal checks do not qualify GPU
continuation or cost.

C17 string state retains exactly the five native uint32 fields used by the
provider: DFA/count/value/extra/mode. It keeps partial UTF8/escape/surrogate state
across tokens and independently clones mask keys; canonicalizing a mask key does
not change the live character count. Programs deep-copy DFA tables, derive and
prune their own graph, and release query scratch on all paths. Schema/regex
construction vectors are retired after sealing. Refusal leaves request state
and match unchanged. These transient objects are not DS4 model-prefix payloads.

The C17 vocabulary slice owns copied immutable bytes/trie and per-query interned
snapshot/transition storage. Query scratch retires on success and refusal.
Caller-synchronized shared mask caches own cloned canonical C state keys and
opaque retained payloads. Vector/shared_ptr projection remains adapter glue;
retained snapshots survive cache eviction. Canonical keys never mutate live
request counters. Hashes are internal accelerators, not DS4 RAM/SSD identities.
No model state serialization or reactive frontier changes in this slice.

Regex construction now owns C17 expression DAGs, nullable context bits,
derivative memo tables and temporary Unicode partition/BFS graphs. A sealed
program deep-copies its data and survives compiler release; refusal preserves
published output and programs. Internal successful memo entries may remain after
a refused construction call. No compiler tables enter DS4 RAM/SSD checkpoints
or change model-prefix scope or the reactive frontier. Parser AST and iterative
assertion expansion scratch are now owned and retired in C17; UTF16 input and
opaque set callbacks are borrowed for one synchronous call. The Unicode context
owns full-set registry, range translations and UTF8 buffers through ICU C APIs;
ICU remains the property/set/conversion dependency. JSON Schema compilation and
provider container storage remain transitional. The C17 builder owns concrete
rule/primitive construction and iterative validation, while schema dispatch/
reference memo and provider composition templates remain transitional.
Structural transformations and finite-value/container algorithms now use C17.
Snapshot bridge planning, validation and payload copies now use C17.

## MTP development boundary

The [MTP binding](../development/MTP.md) captures DS4 predictor K/V, full raw
index and completed pooled keys, plus Gufo-required residual/kept target hidden
rows and adaptive-controller state in the shared typed auxiliary trailer. Only
completed verified frontiers are admitted; pending speculation, missing hidden
history and incompatible draft limits refuse before transfer. Controller,
geometry, token/ngram history and positions are validated before GPU upload.
Successful restore commits predictor/trunk positions and hidden-base together,
resets per-request statistics, and preserves the destination sampler/RNG.

RAM retains its default budget. SSD is opt-in; identity pins descriptors from
the **actual readers used by the admitted model**, then hashes target and predictor
files in order with draft limit, concurrency and provider arithmetic policy.
Pathname replacement cannot bind a different metadata reader to SSD.
Preload/postload stat witnesses reject file replacement or modification during
loading; immutable-file checks continue through SSD hashing. No weight hashing
occurs in RAM-only mode. A model without complete MTP state must explicitly disable caches;
otherwise the core refuses readiness. Original-weight cache continuation and
GPU numerical behavior remain unqualified. Combined image state now follows
the prepared scope/MRoPE binding described below.

## VISION development boundary

This branch exposes [VISION inference inputs/output](../development/VISION.md),
and its live complete-history provider now binds semantic image identity and
MRoPE positions to shared RAM/SSD lookup and restore. `LIE_STATE_CACHE_SCOPE`
is a model-neutral U8[32] component (layer zero), containing the full prepared
image-prompt SHA-256 when steering is unused. Legacy unsteered text state has no
scope section and uses the zero key; steered text has an explicit policy scope.
KVC scope resides after the AUXILIARY boundary; the DS4 tensor payload remains
unchanged. Old AR files/names retain their existing framing.

The independent [C17 steering policy](../development/STEERING.md#session-policy-and-transactional-history)
derives bank/scale/history scopes and can compose them with semantic image
identity. Its versioned 192-byte metadata codec and staged restore are tested
through the shared RAM/SSD envelope with synthetic host state. The optional
layer-zero U8[192] `LIE_STATE_STEERING_POLICY` role requires a cache-scope section
and, for KVC, resides after the auxiliary boundary. Its contents and combined
scope must be validated before model transfer; layout validation alone is
insufficient. The DS4 tensor body and leading client extension remain unchanged.
The owned C17 model-state binding now couples policy history and actual model
positions in provider capture/restore source. The underlying model codec validates
the unchanged model prefix, while policy/scales/combined scope are admitted
before transfer. Matching initial prefix histories are required; mixed or switched-off
histories cannot be reused as initially unsteered state. Inactive unused directions
preserve legacy framing. Shared-worker scoped lookup and live-job capture have
host qualification. The core refreshes scope after every completed changed-policy
forward, preserving the separate image identity and refusing uniform-history
reuse of mixed state. Actual GPU continuation remains pending. Existing opens
without a bank retain their RAM/SSD path.
Scheduled jobs select token-key candidates bounded by the first unapplied
physical step. Position-zero settings are applied before lookup; a longer
uniform cached prompt cannot skip a future change. Captures retain actual
mixed-history scopes. The initial lookup does not yet seek a mixed-history
checkpoint beyond that first boundary. No state framing or DS4 tensor body
changes for schedule metadata, which is a copied client control rather than
model state.
HTTP creation-time plans and the shared choices factory use these same rules.
Each child has independent model state, steering history and cache scope;
changing one choice does not change another or relabel its completed prefix.
Stored choice references preserve control snapshots after the foreground closes,
with retention charged to the record budget when a direction bank is present.
See the [format and restore contract](../development/STEERING.md#state-metadata-and-staged-restore).

Lookup, deduplication, supersession and protected prefixes all compare scope.
SSD indexes read only a bounded provisional scope; complete file digest/layout
validation and scope revalidation still precede returning a usable state.
Text-prefix restore reconstructs the saved physical tokens and tokenizes only
the suffix before checking the prompt frontier. A saved spelling can contain
more tokens than a fresh tokenizer pass. Scope validation precedes reconstruction;
geometry validation still precedes upload. Scheduled steering uses token-prefix
lookup and disables reconstruction to preserve its physical token indices.
Image jobs never use text-prefix reconstruction. Original images must be
resupplied after restart; neither pixels nor embeddings are persisted. Changing
future images conservatively prevents earlier-prefix reuse. The live Qwen
binding checks prepared positions/scope before upload and preserves the fresh
destination sampler. Default RAM is enabled for admitted complete-state vision;
only SSD defaults off. Original-weight vision qualification remains open.

## Multi-model requirement

RAM and optional SSD prefix caching must serve every supported model family
through the same C17 core. Qwen is the first implemented component binding and
KVC payload codec; its geometry must not become a requirement of the cache.

- The shared core owns lookup, priorities, eviction, budgets, immutable lifetime,
  optional lossless packing, persistence, cancellation and metrics. HTTP, bench
  and future chat/eval clients consume that same implementation.
- Each model binding describes its complete reusable frontier: ordinary K/V,
  recurrent or hybrid state, positions and any required auxiliary history.
  Model-defined components use versioned roles/representations; models without
  PLE, n-grams or pooled indices must not allocate or invent those components.
- Each interoperable model payload has its own C codec/mapping under
  `src/models/`. The KVC envelope and file I/O remain shared; model dispatch and
  identity checks belong at the loaded-model boundary, outside cache policy and
  HTTP. A KVC model id alone never selects a trusted live binding. Preserve each
  supported upstream payload exactly instead of encoding other models as Qwen.
- Active device KV layout and numerical compression remain model/provider
  capabilities. Shared checkpoint packing does not promise the same compression
  ratio or representation for every architecture or device. A new model must
  declare its state support before cache readiness.

Supporting several models does not authorize sharing checkpoints between
different weights, tokenizers, positional configurations or incompatible
representations. Validate identity and layout before any device mutation;
unsupported model payloads may remain opaque for offline copying but cannot be
restored. RAM stays enabled by default; SSD stays explicit opt-in.

Before extending live KVC integration, preserve these boundaries in model
selection, identity binding and auxiliary-history capture. Qualification of a
second family must exercise the same RAM/SSD policy and lifecycle with a
different component layout, refusal of incompatible identities/versions, and
independent cold-versus-restored logits/tokens on each supported device path.
Synthetic layout fixtures can validate the generic boundary but do not establish
inference support for another family. No second-family live KVC support is
claimed by the current Qwen implementation.

## Implemented RAM contract

The [KVC runtime binding](KVC.md#runtime-payload-and-ssd-binding) selects exact
DS4 Qwen text-AR payloads by default. Generic `lie_state` allocation and policy
remain model-neutral; the Qwen C codec describes its wire offsets and the loaded
provider binds model geometry and identity. Native aligned components remain an
explicit build-time control. CPU fixtures cover both; [GPU checks](../archive/KVC-GPU-RESULT.md) establish exact restore
through 128K with a reported memory/latency increase. Foreign unbound records are
not live states.

- A dynamically growing immutable checkpoint index, separately bounded to
  `min(cache budget, 16 MiB)`; payloads remain bounded by the configured total bytes.
  Account the allocation containing descriptor and payload; allocator/driver
  overhead and active sessions are separate. Allocation is lazy. Evict the lowest-utility
  eligible entries before capture; retained, in-progress capture and explicit
  codec buffers must fit the budget. LRU remains a compile-time alternative.
  Oversized checkpoints or a failed host allocation skip optional retention.
- Default policy captures cold/continued/complete-prompt/retirement/shutdown frontiers and can
  match rendered byte prefixes while retokenizing only the suffix. Exact saved
  physical history is preserved. `--cache-policy legacy` retains the earlier
  single aligned physical-prefix capture schedule. See
  [policy settings and qualification](CACHE-DS4-POLICY.md).
  Generated captures preserve the longest prefix reusable by the original
  prompt when both checkpoints cannot fit, without permanently pinning it.
  [Admission rules and qualification](../development/CACHE-PROMPT-RETENTION.md).
- Each model open has a process-local domain. Same domain, context/chunk,
  component representation and shapes are checked before restore mutation.
  Because entries never leave the live model instance, they cannot cross model,
  device, build or process reopen. This is not a stable disk compatibility ID.
- A recipient is an empty independent sequence. Sampling, seed/RNG, penalties,
  output parsing and transport state belong to the new request. Completed prompt and generated-token
  frontiers may be captured; request-local sampling state is not resumed. Complete MTP checkpoints use the
  extension above; vision and joint MTP/vision also bind prepared positions and
  the semantic image scope before device mutation.
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
[predeclared GPU protocol](../development/protocols/STATE-GPU-PROTOCOL.md), with [full results](../archive/STATE-GPU-RESULT.md)
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
| `LIE_CHECKPOINT_COMPRESSION` | Bounded lossless byte-plane/Zstandard checkpoint packing, raw fallback | Raw checkpoints; no codec dependencies |

Utility now follows the six-hour wall-clock DS4 score and purpose weighting;
SSD creation/use timestamps and saturating hit counts persist in native v3.
Dynamic index memory is accounted separately. Compile-time
`LIE_DS4_CACHE_POLICY` is default ON alongside utility and compression; runtime
`--cache-policy legacy` selects the previous capture schedule. Full contracts,
CLI options and CPU/GPU status are in [CACHE-DS4-POLICY.md](CACHE-DS4-POLICY.md).

Packing operates only on a uniquely owned immutable state. Physical tokens stay
uncompressed; all remaining bytes, including floating-point bit patterns, use
independent 1 MiB Zstandard/raw blocks. Four-byte words are reversibly split
into byte planes before level-1 compression, without interpreting their values.
Static codec contexts keep all explicit workspace inside admission. The removed
LZ4 codec 1 is rejected; existing raw and Zstandard codec 2 files remain
readable. Payloads below 64 KiB stay raw. At least 50%
saving of the complete retained allocation (descriptor plus stored payload) is
required. Three deterministic samples totaling at most 48 KiB reject low-benefit
inputs before allocating or scanning the full candidate. This is a conservative
heuristic: it may skip compressible inputs; passing it does not bypass the final
size gate. Insufficient budget, allocation failure or an inadequate saving leaves
the original unchanged. The earlier 12.5% gate is retained only in dated R5/R6
measurement capsules, not in the current admission policy. The budget includes the source, candidate
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
weight quantization; it is not KV precision. LIE now implements its utility formula and progressive policy; binary format
and cross-quantization interoperability remain separate pending work.

The Qwen3.8 path in [DS4's model engine](https://github.com/antirez/ds4/blob/main/ds4.c#L59813-L59929),
reviewed 2026-10-02, writes live K/V and pooled block keys as 16-bit tensors,
recurrent/history/index data as 32-bit tensors, plus tokens and logits. Its
`qwen4_session_save_payload` uses bounded tensor copies, not a generic compressed
stream. LIE already retains live text-state rows with these numerical precisions;
it additionally keeps only the unpooled index tail. The two binary formats are
not interchangeable. DS4 Qwen support must not be conflated with the separate
DeepSeek learned-compressor path, and LIE's Zstandard codec is not a port of an
antirez compression algorithm. Qwen active K/V and block keys remain F16,
with the required F32 recurrent/other components. Checkpoint packing does not
reduce the active device allocation. Low-bit active KV still needs a distinct
model representation, matching attention/prefill/batch kernels and long-context
quality/performance qualification; it is not implemented by the lossless codec.

CPU fixtures cover exact special floating bits, mixed/raw blocks, valid-checksum
malformed frames, budgets, pins, utility aging/eviction, core restore and SSD
restart. These are NOT-INFERENCE. [R6](../archive/CACHE-COMPRESSION-GPU.md) additionally
qualifies exact original-weight compressed SSD restart at 128K, while measuring
an unfavorable 15–16% saving/latency tradeoff. Its old admission threshold is
preserved in the evidence; the stricter current benefit gate is qualified
separately. Active KV precision remains unchanged.


## Requested DS4 representation parity — clarification, 2026-10-02

The required target is DS4-compatible state representation in both RAM and SSD.
The owner subsequently clarified that high-ratio compression may be deferred
when absent from antirez's implementation. For the reviewed Qwen path below,
an additional high-ratio codec is therefore outside the current task; a large
memory reduction is not an acceptance gate for format parity. An unrelated
lossy Q4/Q8 checkpoint codec would not establish DS4 format compatibility.

The reviewed upstream RAM path `ds4_session_save_snapshot` calls the same
`ds4_session_save_payload` dispatcher used for persistence; its Qwen branch is
`qwen4_session_save_payload`. The inspected Qwen path stores live F16 K/V and
F32 recurrent components. It does not add a high-ratio compressed stream.
References: [RAM snapshot](https://github.com/antirez/ds4/blob/main/ds4.c#L61007-L61074),
[family dispatch](https://github.com/antirez/ds4/blob/main/ds4.c#L60043-L60060),
[Qwen payload](https://github.com/antirez/ds4/blob/main/ds4.c#L59813-L59929).
These are read-only upstream-main observations dated 2026-10-02, not a pinned
cross-runtime interoperability qualification or an audit of every fork.

The existing LIE v1/v2/v3 envelope remains its own format. Identical scalar
precisions do not mean binary interoperability. KVC import/export still needs
a model-specific converter and independent qualification. A future compression
extension should identify the corresponding antirez function/version before
claiming parity; it does not block current format and cache-policy work.
No DS4-owned source, cache, model, service or evidence has been changed.

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
[BACKEND.md](../BACKEND.md).

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

The [frozen component envelope](SSD-PREFIX.md#legacy-identity-and-version-1-framing)
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

## Joint MTP/vision state

The Qwen joint layout uses one `LIE_STATE_AUXILIARY` boundary: the existing
100-byte MTP controller, residual/kept hidden rows, then U8[32] `CACHE_SCOPE`.
The DS4 base and MTP-only/vision-only framing retain their existing meanings.
Joint finish/check require independently prepared MRoPE positions and semantic
scope; the ordinary text and vision-only entry points reject a joint state.
Predictor catch-up requires retained hidden rows covering every missing position.
The adapter commits trunk, predictor, controller and vision layout only after
completed transfers. Cancellation/failure cannot publish a usable frontier.

## Response history is separate from KV retention

`lie_records` retains normalized request history, validated output, a bounded
semantic event journal and target-token witnesses in C17. This supports stored
Chat/Responses, continuation, background cancellation and stream replay for any
provider using the neutral contracts. Its independent record-count, RAM-byte
and TTL bounds use `--response-store-*`; no record is persisted to SSD.
The byte quota reserves worst-case output and job witness capacity before
attachment. Deleted/expired records become invisible immediately; existing
reactor pins remain charged until released. Worker scratch and numerical
sequence state are released at device retirement; immutable witnesses remain
until the final job reference. This store is separate from model weights,
active KV state and the RAM/SSD reusable prefix cache.

Final output can close reactive demand before numerical sequence teardown
publishes `retired`. The retained consumer accepts CLOSED demand and continues
until semantic TURN_END; it neither treats that interval as a collection error
nor declares the response complete early. This rule also applies after the
creating background stream disconnects. Invalid credit operations remain errors.
