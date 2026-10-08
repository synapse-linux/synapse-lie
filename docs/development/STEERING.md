<!-- SPDX-License-Identifier: MIT -->
# Directional steering implementation

The C17 shared library owns direction-bank loading, bounded host allocation,
immutable values, session policy transactions, history/cache identities and
explicit state metadata. Direct C model and session/model-state binding is
present in provider and shared-worker source. Selected original-weight AR/MTP
GPU cases qualify exact scheduled physical indices and compatible SSD reuse
([receipt](validation/steering-physical-index-point-gpu-2026-10-06.json));
independent numerical/graph/correction/fault oracles remain open.
Separate GPU windows also qualify selected original-model malformed-bank refusal
and absent/zero-scale/fresh-core output parity in AR/MTP
([receipt](validation/steering-admission-point-gpu-2026-10-06.json)).
Server/native core bench share initial model-wide controls and scoped RAM/SSD
lookup. The shared core supports asynchronous live job changes, native benchmark
schedules, HTTP creation-time plans and individual stored-choice controls.
Broader GPU qualification remains open.
Loading a bank or advancing policy metadata is not model inference and does
not qualify steering quality or performance.

## Preparing a learned direction

The shared C17 [capture](../../include/lie/steering_capture.h) and
[direction learner](../../include/lie/steering_direction.h) accept model-derived
geometry. The additive [observer](../../include/lie/activation_observer.h) captures
the last physical prompt token from the existing prefill path, including a
one-token tail. It selects ordinary trunk attention output or completed FFN
residuals; FFN branches are averaged before learning. The predictor is excluded.
This follows the model-dependent capture and flat-bank method described in
[DS4's steering documentation](https://github.com/antirez/ds4/blob/main/dir-steering/README.md).
The implementation is independent C17 code; it does not import DS4 source.

For each paired target/contrast prompt, collect every selected layer and confirm
successful completion of the full prefill. Refused, cancelled, duplicate,
wrong-token, nonfinite or incomplete captures cannot publish learning input.
Accumulate target-minus-contrast with compensated FP64 sums and normalize each
layer to unit L2; final vectors are binary32. A zero layer refuses publication
without inventing a direction. The mathematical contrast/normalization method
and runtime file format match; bitwise equality with another extractor is not
claimed. Encode the result as headerless little-endian `.f32` for the existing
bank loader below. Both helpers have explicit byte/pair bounds and allocate no
threads; no HTTP layer or model family is embedded in them.

The opt-in provider recipe now contains last-prompt-token HIP row copies only
when a diagnostic observer is supplied. It copies configuration for one call,
limits the row allocation before submission and removes the observer on all
returns. Rows can precede full-call completion, so clients must preserve partial
failure evidence and separately confirm success before learning. Diagnostic
copies, stream waits and callbacks are excluded from throughput comparisons.
The existing inference scheduler and model kernels are retained.

Nine focused CTest checks plus the private borrowed-row fixture pass in each
normal/sanitizer build. Exact pinned recipe composition and both sampler-mode
adapter syntax checks pass. These are HOST checks, not original activation or
quality evidence. The native builder is now integrated as described below.
Coherent HIP compilation and the first original short-prompt capture cohort
pass; learned-bank quality and matched cost remain pending.

## Native bank builder

`lie-steering-build` is a C17 diagnostic client over the same model-neutral
executor/capture/learner APIs. Its [usage command](../guides/USAGE.md#directional-steering)
accepts two prompt files and a new output directory. Files must be regular,
unchanged during reading, at most 32 MiB each and contain no NUL or invalid UTF-8.
Each nonblank line is one prompt, at most 65,536 bytes. Corresponding line counts
must match, with at most the configured pair limit (4096 maximum). CRLF and a
missing final newline are accepted; the exact original bytes are retained and
SHA-256 identified. All dataset admission precedes model opening.

The client opens an unsteered model once, then a fresh sequence for each target
and contrast. `chat` uses the model's template with thinking disabled; `raw`
uses plain tokenization. It retains physical IDs, sends cumulative prefill
chunks on the existing owner and observes only the final chunk, including a
one-token tail. No decode, predictor, HTTP request, cache reuse, independent
thread or CPU model forward is added. Observer rows are copied during their
borrowed lifetime. Full prefill status, completed prefix and complete unique
layer/component rows must all succeed before a pair can enter the learner.
Callback writer/refusal errors are latched and checked after numerical return;
they cannot veto or retry inference. Bounded raw rows from failed captures remain
diagnostic evidence and never become accepted learning input.

`--components ffn` is the default; `attention` selects projected attention rows,
and `both` prepares two separate banks from the same captures. Each bank is
headerless little-endian binary32, layer-major, with target-minus-contrast
compensated FP64 accumulation and unit L2 per layer. Zero layers refuse the
whole run. Banks are staged exclusively, fsynced and published without replacing
files after all pairs, normalization and executor retirement succeed. A failure
during multi-file publication may retain a final name as evidence; neither a
file's presence nor its hash is acceptance. Use banks only with actual process
exit 0 **and** the final `complete` journal event. Failure preserves owned
partial files; existing output directories are refused without modification.

| Output | Meaning |
| --- | --- |
| `target-prompts.txt`, `contrast-prompts.txt` | Exact admitted source bytes. |
| `build.jsonl` | Source hashes, backend/build identity, geometry, controls, physical IDs, row offsets, actual completion/refusal and terminal status. |
| `activations.f32le` | Completed borrowed branch-major rows, in recorded callback order; FFN branch means are computed separately by the C17 collector. |
| `direction.ffn.f32`, `direction.attention.f32` | Selected normalized banks, each exactly `layers * width * 4` bytes. |
| `*.partial` | Owned staging artifacts; not accepted banks. |

The explicit host bound covers prompt/index/token/encoding buffers, learners,
both simultaneous captures and the provider's observer-row reservation. It
excludes JSON/crypto/stdio and allocator overhead, model/executor resources and
device allocations. The output bound covers admitted source copies, journal,
raw rows and staged banks, reserving 8192 bytes for a failed terminal event.
Hard-linked staging/final names do not double-charge bytes. These are requested
owned-byte limits, not measured process RAM or device memory.

Four focused native CTest checks pass in normal and unsuppressed sanitizer
builds, including analytic bank bytes independently loaded by the existing
DS4-format loader, borrowed-buffer reuse, target/contrast counts, finite and
incomplete-row refusals, failure after all rows, close failures, and input/host/
output bounds. Twelve mocked build-coordination checks require the new consumer
and refuse missing or changed artifacts. The
[HOST receipt](validation/steering-build-host-2026-10-07.json) retains failures and
portable raw artifacts. CPU fixtures are explicitly `NOT-INFERENCE`; the new
production target now passes the matching
[coherent HIP build](validation/steering-build-point-build-2026-10-07.json) on `.161`,
including both complete providers and all seven consumers. Collected commands
verify the builder and both shared helpers as C17 with the primary-provider link.
The first original short-prompt activations pass the independent capture gate
below; wider activation cases, generation parity and learned quality remain open.

## Original-weight capture gate

The optional development coordinator selects `bench_profile: "modern-steering-build"`.
Stage the SHA-bound `tools/strix-point-steering-build-gate.py` as
`steering-build-gate.py` in an exclusive persistent job directory, alongside
`target-prompts.txt` and `contrast-prompts.txt`. Bind their exact bytes/SHA-256 as
`steering_build_inputs`, the helper SHA as `steering_build_gate_sha256` and the
compiled `runtime_build_id`/`runtime_source_pin`. The complete `steering_build`
settings object is:

```json
{
  "context": 8192,
  "prefill_chunk": 256,
  "components": "both",
  "rope": "native",
  "prompt_format": "chat",
  "max_pairs": 8,
  "max_host_bytes": 268435456,
  "max_output_bytes": 67108864,
  "timeout_seconds": 1200
}
```

This bounded gate admits at most 32 pairs, an 8K context and 64 MiB of outputs.
It runs the native C17 builder directly on the existing owner, with no decode,
predictor, HTTP server or extra inference thread. Fresh `.161` peer/boot/lease/
thermal/model admission is still required. Dataset/helper drift, invalid settings
and existing capture directories refuse before model verification. Model stats
are checked after native success or failure; partial journals retain their hash.

Acceptance requires the actual native exit 0 and complete successful per-prompt
prefill, unique layer/component rows, exact token positions, contiguous raw
offsets, finite LE-F32 values and final `complete`. The reviewer independently
averages FFN branches, rounds means to F32, uses `math.fsum` for paired contrasts
and `math.hypot` for per-layer normalization. Compare each published coordinate
with relative tolerance 2e-6/absolute 2e-8 and each layer's norm within 1e-6.
These fixed bounds allow binary32 rounding; a matching file hash alone is not an
oracle. Preserve source copies, full physical IDs, raw rows, banks, native and
container exits, model stats and exact closure. Report observed one-token tails;
ordinary captures do not qualify tails absent from the actual inputs.

Python is optional development coordination/oracle code. The builder, learner,
collector and default products/build/tests remain native and Python-free.
Eighteen HOST checks pass with both Debug and unsuppressed ASan/UBSan/LSan C17
fixtures; 89 existing supervisor checks pass. The
[HOST receipt](validation/steering-build-gate-host-2026-10-07.json) binds commands
and preserves the initial fixture setup failure. These fixtures are not original
weights. The first original short-prompt cohort now passes, as recorded below.
Even a passing original capture gate leaves held-out steering quality,
generation parity, graph/correction/fault/vision and matched cost open.

### First original capture qualification

On `.161`, the frozen `4c703b3d`/r70 native builder captures eight formal/casual
prompt pairs, sixteen fresh prefills and 1536 original attention/FFN rows.
Geometry is 48 layers, width 2560 and four FFN branches. The 37.5 MiB raw file
retains all branch values; each final DS4-format bank is 480 KiB. Both remote
and local independent reconstruction match every serialized coordinate, with
maximum observed absolute error 0 and layer norm error below 3.6e-9.
The [receipt and portable raw archive](validation/steering-build-original-point-2026-10-08.json)
bind the actual native/controller exits 0, all 19 collected artifact hashes,
unchanged model stats, exact process/container/cgroup retirement and restored
service. CPU/GPU/NVMe peaks are 59/56/69.85 C; GPU is observed only.

These prompts contain 28–35 physical tokens, with native capacity 8192 and
chunk 256. They qualify original single-chunk capture and direction construction;
no multiple chunks, one-token tails, generated responses or performance are
tested. Held-out learned direction quality and the remaining runtime/fault/cost
gates stay open. An initial local checking wrapper supplies a relative path and
exits 1; the corrected wrapper resolves the same collected directory and passes,
without changing checks or repeating GPU work.

## Shared bank contract

[`lie/steering.h`](../../include/lie/steering.h) defines independent ABI 1.
Callers supply the loaded model's trunk-layer count, hidden width and an explicit
host vector budget. No model family or platform is hardcoded. The loader requires
exactly `layers * width * 4` bytes of headerless little-endian IEEE754 binary32,
matching DS4's flat `.f32` direction files on the supported little-endian targets.
Each layer occupies one contiguous hidden-width row. Values are copied exactly;
the loader does not normalize, quantize or compress them. Finite zero directions,
negative zero and subnormals are preserved.

Malformed sizes, overflowing geometry, invalid ABI tags, nonfinite values,
symlinks and nonregular files are refused. FIFO admission is nonblocking.
Read-only descriptor stats are witnessed before and after bounded reads; a file
change refuses admission. Failure leaves the caller's output handle unchanged.
The original file is never modified or retained as a mutable mapping.

The loaded bank is immutable and has explicit thread-safe owned references.
A borrowed float span remains valid while its owner holds a reference, including
after the source file is changed or unlinked. Reference operations do not create
threads; numerical operations remain on the eventual device owner.

`file_sha256` identifies exact file bytes. `scope_sha256` is SHA-256 over:

```text
ASCII "synapse-lie.steering.v1" + NUL
uint32 little-endian layer count
uint32 little-endian hidden width
original file bytes
```

Identical bytes interpreted with different tensor geometry have different
scopes. The session policy below also binds effective scales/history. The
provider/storage integration must additionally bind model identity and the
complete retained state; these helpers do not themselves implement cache
restore compatibility. Existing state and DS4 KVC payload formats are unchanged.

## Session policy and transactional history

Independent `LIE_STEERING_POLICY_ABI=1` introduces an owned policy with explicit
target-position capacity. Defaults are FFN 1 and attention 0 when a bank is
present, or both zero otherwise. Scales are finite floats in [-100, 100]; a
nonzero scale requires a bank. Negative zero is canonicalized in settings while
file values remain exact. No Qwen layer count or platform is embedded here.

Only the creating device owner prepares or commits mutations. Clients may read
locked snapshots while holding an owned reference. A prepared update pins its
policy, and each policy retains its immutable bank. At most two updates may be
outstanding. Snapshot accounting reports policy and staged bytes separately
from the shared bank's vector bytes. No extra runtime thread is created.

The provider must prepare an update **before** numerical mutation, perform its
work, then commit the completed **retained target-forward** frontier or discard.
Sampling a deferred output token, executing the predictor and evaluating rejected
drafts do not advance that frontier. A reserved burst may commit fewer positions
than its maximum; a zero advance leaves history unchanged. Failures never commit.
Scale changes commit at the same frontier and affect future work; they do not
relabel past work. A stale/wrong-owner commit refuses without consuming the plan;
if device mutation already happened, the integrating core must poison that model.

History appends a SHA-256 node only when completed work changes effective scales:

```text
ASCII "synapse-lie.steering-history.v1" + NUL
previous history SHA-256 (32 bytes)
bank geometry/content scope SHA-256 (32 bytes)
uint64 little-endian start position
float32 little-endian FFN scale, attention scale
```

An initially inactive history uses the all-zero identity. Uniform settings have
the same identity across different prefill chunks or accepted burst sizes.
Before the first forward, cache scope anticipates its uniform initial node so
prefix lookup agrees with capture. The cache hash has its own versioned domain,
bank scope, effective history and current scales; revision and chunk boundaries
are not hashed. Switching steering off preserves a nonzero history if earlier
retained work used steering. An unused on/off toggle does not invent such history.

Inactive steering with no steered history preserves the exact existing text or
image scope. Otherwise, nonzero steering and image scopes combine under a
separate semantic domain. Core jobs compose this identity on the device owner
before any RAM/SSD text or token candidate is selected. The same scope is checked
again by physical restore/capture; image identity is preserved when combined.
The metadata codec below serializes the required history/scales/frontier without
dumping C padding; the provider must bind it to complete validated model state.

## State metadata and staged restore

`lie_steering_policy_encode` writes exactly 192 bytes on the device owner and
refuses outstanding updates. The format is independent of native structure
padding, context capacity, revision, counters and model/platform types.
All integers and IEEE754 binary32 scales are little-endian; negative zero in
settings has one canonical positive-zero representation.

| Byte offset | Size | Field |
| --- | --- | --- |
| 0 | 8 | `LIESTP1` followed by NUL |
| 8 | 4 | Format version 1 |
| 12 | 4 | Encoded length 192 |
| 16 | 4 | Flags: bit 0 bank present, bit 1 completed work, bit 2 steered history |
| 20 | 4 | Reserved zero |
| 24 | 8 | Completed retained target-forward position |
| 32 | 8 | Completed effective scale epochs |
| 40 | 8 | Current FFN and attention scales |
| 48 | 8 | Last completed FFN and attention scales; current scales before any work |
| 56 | 32 | Bank geometry/content scope |
| 88 | 32 | History hash head; zero if no completed steered history |
| 120 | 32 | Steering cache scope |
| 152 | 8 | Reserved zero |
| 160 | 32 | SHA-256 of `synapse-lie.steering-state.v1` + NUL + bytes 0–159 |

The history head preserves future epoch composition without storing an unbounded
event log. Its checksum detects corruption; it does not authenticate an arbitrary
file or independently prove that the earlier numerical work occurred. The
containing state still validates model/build/RoPE identity, input identity,
complete tensor payload, layout and checksum before any device mutation.

`lie_steering_policy_prepare_restore` accepts only an idle pristine destination,
an exactly matching bank and an independently validated target frontier within
the destination's own capacity. It validates flags, scales, history consistency
and recomputed cache scope before allocating an owned prepared update. The
caller may release the input bytes after preparation. The owner compares the
staged combined image/steering scope using `lie_steering_update_cache_scope`
before transfer, then commits **exactly** the restored frontier after completed
model transfer, or discards. Refusals leave live metadata unchanged. Destination
capacity and revision remain local; stale or failed post-mutation commits require
the existing runtime poisoning rule.

An absent metadata span (`NULL`, zero bytes) denotes unsteered legacy state and
requires both current scales to be zero. It restores an unsteered completed
frontier while preserving the exact legacy text/image scope. This path avoids
inventing steered history for unused directions; future bindings must keep
unsteered legacy payloads compatible rather than require new metadata everywhere.

The additive `LIE_STATE_STEERING_POLICY` role (15, state ABI 2) is layer-zero
U8[192] and requires one U8[32] `LIE_STATE_CACHE_SCOPE`. KVC stores it after the
existing `LIE_STATE_AUXILIARY` boundary, in the already checksummed LIE extension;
the DS4 model payload and the leading client extension bytes remain unchanged.
The generic validator bounds the section geometry. A trusted model binding must
also decode and validate its content and combined scope before transfer.

The native host fixture exercises this protocol through the actual shared
`lie_state` RAM capture/restore and SSD KVC envelope with synthetic model bytes.
It is not a live model binding, original-weight continuation or GPU evidence.

## Recorded provider binding requirements

Read-only official DS4 source at `0aaea5a238fb41a35106a551e73c8409dfb751ac`
places Qwen attention edits on the projected hidden-width block output before
the HC residual combine. FFN edits act on every HC residual branch after the
FFN combine. The separate MTP predictor is unsteered; drafts are verified by the
steered target. The documented positive scale removes a direction and negative
scale amplifies it. [Upstream description](https://github.com/antirez/ds4/blob/0aaea5a238fb41a35106a551e73c8409dfb751ac/dir-steering/README.md).

The pinned Gufo HIP provider fuses residual combine and the following grouped
normalization. Editing its residual after that combine invalidates the prepared
normalization. The binding must refresh that normalization, including quantized
and half-precision cached views, before the following mixer. An edit on only the
MoE block output is not the required per-HC-residual FFN edit.

Per-session scale changes run on the exclusive device owner and preserve past
KV state and retained boundary logits. The source binding invalidates captured
graphs and MTP controller/proposal scratch at an idle verification boundary.
It preserves an already sampled residual correction for those retained logits;
discarding that committed draw and sampling again can bias the next token.
No outstanding verification is forcibly discarded. Define and retain the effective scale history
when capturing RAM/SSD state; a token-only prefix must not reuse state produced
under different steering. No extra provider/HTTP thread is introduced.

Remaining work in roadmap item 5 is qualification of the HIP binding and dynamic
HTTP/bench controls. Initial admission/resource projection, scoped RAM/SSD text lookup
and server/native core bench controls have host qualification. GPU gates on
`.161` must prove unchanged output with steering absent/zero, malformed input
refusal before model mutation, prompt/decode edits, scale transitions, independent
AR/MTP checks and measured quality/cost. The user-visible naming follows DS4's
`--dir-steering-file`, `--dir-steering-ffn`, `--dir-steering-attn` for fixed initial
model-wide scales. See the [usage guide](../guides/USAGE.md#directional-steering).

## Provider activation operators

`lie/steering_activation.h` defines independent C17 activation ABI 1. It bounds
token/branch geometry, address arithmetic and the available activation/direction
spans before launch. Rows are token-major with one independent hidden-width
slice per branch. This descriptor does not allocate memory or execute inference.

The independently written `adapters/hip/steering.hip` operator applies:

```text
dot = sum_j(direction[j] * row[j])
row[i] -= scale * direction[i] * dot
```

It uses one workgroup per row, a shared F32 reduction and the existing owner
stream. It does not normalize directions. Its source disables fast-math and
contraction explicitly; floating-point agreement with DS4 still needs numerical
GPU oracles. A validated zero scale bypasses all GPU calls.

The exact pinned-source variant adds initial immutable provider-only admission:
direction geometry and finite values are checked before the model's first GPU
upload, then one bank copy is owned by the executor. Borrowed host spans are
cleared after loading. Its separate `LieSteeringBytes()` diagnostic reports bank
bytes; the core and clients expose those vector-data counts separately. Absent directions
allocate nothing. `LIE_DIRECTIONAL_STEERING=ON` is the default compile selection;
it requires the verified state-access variant and matching application/archive
receipts. With it disabled, nonempty direction admission refuses before upload.

Target scalar prefill/decode/verification and native batches have both edit
points described above. Batch slices retain each session's own scales and every
HC branch. Active FFN steering skips the now-stale fused next normalization and
invalidates cached F16/Q8 views; the following mixer recomputes from the edited
residual. The separate MTP predictor loop is unchanged. An entirely inactive
batch keeps the existing numerical launches and normalization route. A mixed
batch with active FFN rows refreshes normalization for all rows; inactive rows
skip the direction edit but still need separate output and cost comparisons.

The private scale setter accepts only a pristine session with no prior mutation,
warm shape or graph. No live scale transition is exposed. This leaves graph
scalars immutable and introduces no worker, HTTP state or scheduling thread.
Active steering refuses both private provider snapshot APIs. The direct LIE
state binding below uses owned C17 metadata admission instead of those APIs.
Existing model opens without a bank retain their RAM/SSD path. These private
provider hooks alone do not qualify HTTP/bench numerical steering on GPU.

`steering-edits.json` records 29 exact replacements against independently fetched
Gufo `f783fedb`; owned kernels retain MIT markers and no DS4 source is imported.
Every affected source hash, owned primitive file and compile selection is
required in a new provider receipt. Old libraries cannot be accepted as this
new composition. No remote build or GPU run was performed for this increment.

## Direct model/session binding

Independent model ABI 1 adds `lie_steering_model_options` and explicit
`lie_backend_open_steered`, composing optional predictor/projector admission in
the same provider. Existing executor ABI 3, request ABI 8 and generation ABI 3
are unchanged. The borrowed file path is used only through synchronous open;
defaults are a 16 MiB host vector budget, FFN scale 1 and attention scale 0.
The C17 loader validates the actual model geometry before device validation or
upload. The provider then rechecks the admitted reader geometry and owned device
bank bytes. Disabled steering or missing verified DS4 state access refuses
admission before upload; the unavailable executor has no model fallback.

The runtime owns the immutable host bank. Each sequence creates a C17 policy
before its GPU session allocation and applies initial scales before numerical
work. Initial owner-only configuration is supported; live changes are not.
`lie_steering_forward_prepare` compares the independently observed model frontier
with the policy and reserves bounded work before submission. Prefill, AR and
batch AR/MTP complete against actual retained `Session::Position()`, including
completed work whose client delivery is cancelled. Sampling, predictor work and
rejected drafts do not invent retained positions. Divergence or a failed
post-mutation commit poisons the model rather than retrying it.

C++ retains only model calls and lifetime glue; C17 owns admission, reservations,
history and completion validation. No thread is added. Without a bank the new
path allocates no policy/update and skips their cleanup calls; the remaining
branches have not been performance-qualified. Model queries separate host/device
vector bytes; sequence queries expose policy metadata and composed cache scope.
Vector bytes do not include allocator overhead or model workspace.

The direct query now advertises the source binding's prefix-state support when
the verified provider is compiled; this is not hardware qualification. The shared
worker and both clients now use the explicit factory, validate the admission
record, and refuse cache-enabled admission without complete prefix-state support.
SSD model identity still binds actual admitted weight descriptors and
arithmetic/device policy; bank/scales/history belong to the checked prefix scope.

## Shared core and initial client controls

`lie_core_create_steered` copies options and the path before returning. The
existing worker loads the bank against model geometry, validates its bounded
host bytes/capabilities and publishes READY. Client snapshots copy this admission
under the core gate without provider calls; no new inference thread is created.
An absent bank retains the original model-open path and zero semantic scope.
Existing unversioned core options/info layouts and legacy zero-scope cache
wrappers are retained.

The shared CLI parser validates finite [-100,100] scales. Both server and native
core bench require a file for explicit scales and reject duplicates. Defaults
with a file are FFN 1, attention 0 and a 16 MiB host vector budget. Changing the
file or initial scales between starts selects a distinct prefix scope; an unused
zero-scale bank can reuse exact unsteered legacy state. Text and token lookup
both copy/check their full scope before selection and before transfer.

Native JSONL records requested settings and the actual READY bank hashes/data
bytes. Reports validate request/admission agreement and reject matched
comparisons whose bank identity or scales differ. Historical records without
either steering object retain their unsteered meaning. These host checks do not
establish actual output equivalence, neural quality or performance.

## Live job changes in the shared core

`lie_job_change_steering` copies one bounded pending request and returns an
admission ticket immediately. The client holds a job reference; it never calls
the provider or waits for GPU completion. The existing owner applies the change
at a scheduling boundary after any already selected call and applicable cache
work. `lie_job_steering_snapshot` copies the latest completion, applied retained
position and last confirmed policy under the metadata gate, including after
retirement. Admission is separate from successful application; pending capacity,
invalid input, cancellation and provider failures have explicit outcomes.

The additive direct model operation prepares the C17 policy, validates the
independently retained frontier, invalidates private captured graphs and MTP
controller/proposal scratch, then commits at the same position. Past tensors,
target logits, predictor KV and already sampled residual corrections remain
unchanged. A scale no-op does not invalidate graphs or reset the controller.
Pure refusals preserve the job; a failure after provider mutation poisons the
shared model, without retry. This source binding has syntax checks, not GPU proof.

The core retains the original image scope separately and refreshes combined
identity after the change and every completed forward. The first forward at a
different scale adds a history epoch. Mixed history must not reuse a uniform
token-only prefix or masquerade as its initial scale. The actual host tests cover
AR/MTP, images, RAM/SSD capture, concurrent isolated policies, cancellation,
one-slot saturation, copied inputs, no-ops and mutating failure. Fixed CLI flags
still select initial model-wide scales. Actual GPU continuation, graph rebuilding,
deferred-correction oracles, quality and
performance remain open.
[Host qualification](validation/steering-live-host-2026-10-05.json).

## Deterministic schedules and HTTP controls

Additive schedule ABI 1 copies 1–64 position/settings steps before job publication,
without changing request ABI 8 or existing option/info layouts. Its separate
snapshot preserves attempted/applied results and terminal unattempted outcomes.
The prepared prompt and resolved output budget bound every requested position.
Position zero applies before cache selection; prefill chunks split at later
boundaries. Decode selection excludes a row whose due change has not yet applied,
including the last-prefill/first-decode transition. Each selected AR/MTP row caps
its advance at the next step. Other rows continue independently; no new thread,
callback or client polling determines the boundary.

The owner confirms both retained position and effective scales. A planned pure
refusal ends that job explicitly; mutation failure poisons the model without retry.
Natural EOS/cancellation records unreached steps without calling them successful.
Planned jobs reject asynchronous changes to preserve their declared identity.
Only these jobs allocate the bounded plan record; retention accounting includes it.

Scheduled cache lookup uses token keys and cannot restore past the first
unapplied step. Compatible shorter prefixes remain eligible; subsequent captures
use actual mixed history. This does not implement lookup of later planned mixed
histories by replaying declared control metadata. Existing absent-plan lookup,
state framing and numerical paths remain in use.

Selected original-weight AR/MTP cases now pass on `.161`
([receipt](validation/steering-physical-index-point-gpu-2026-10-06.json)). Three
changes apply at indices 128/273/279; a divergent saved spelling is refused,
while a compatible 128-token prefix restores before the first step. All three
scheduled outputs and policies match within and across modes; MTP accepts real
drafts. The owned sparse nonzero vector fixture qualifies this regression.
Learned DS4 direction quality, independent graph/correction/fault oracles,
vision, later mixed-history lookup and matched cost remain open.

The native bench accepts `--dir-steering-plan`, records canonical binary32
settings and actual results, and refuses mismatched/unfulfilled plan comparisons.
The HTTP GET/POST `/v1/responses/{id}/steering` and
`/v1/chat/completions/{id}/steering` routes are LIE extensions for retained
requests. Multi-choice requests require `/steering/{choice}`, with a canonical
zero-based integer index. POST returns 202 admission; GET projects the confirmed
ticket/policy and any immutable schedule. Finished jobs refuse further changes. This
asynchronous path promises an available retained boundary rather than an exact
output index. All numerical work remains on the shared owner.
Both HTTP creation routes accept `dir_steering_plan`. Parsing validates the full
array and duplicate keys before admission; the additive shared choices factory
copies one plan into each independent child, preserving seed offsets and existing
rollback on admission failure. Protocol JSON never enters the core. Stored extra
choice references exist only with an admitted bank; their retained bytes are
charged before attachment and released on disposal. Snapshots survive foreground
connection retirement without keeping that connection or creating a thread.
[Host receipt](validation/steering-http-plan-host-2026-10-05.json) ·
[Commands](../guides/BENCHMARKS.md#scheduled-steering).

## Model-state cache binding

[`lie/steering_state.h`](../../include/lie/steering_state.h) defines independent
C17 binding ABI 1. It plans canonical metadata tails, inspects a model-prefix
view and validates capture/restore without model types, device calls or a second
tensor allocation. The trusted provider supplies its independently expected
model format and re-describes the returned prefix against actual model geometry.
Layout validation alone is not complete model admission.

An active or previously steered prefix appends U8[192] policy metadata and a
U8[32] combined scope. Existing vision scope is reused at its original offset.
A plain KVC model adds the eight-byte `LIEDIR1` plus NUL auxiliary boundary;
existing MTP/vision auxiliary bytes remain in place. The original DS4 tensor body
and leading client extension stay unchanged. No active scales and no steered
history preserve the exact legacy layout, scope and filenames even with an
admitted but unused bank.

Prefix restore stages decoded policy metadata, validates the bank and retained
frontier, and compares both initial scales and combined scope with the requested
destination policy before any model transfer. A mixed history or steering later
switched off cannot masquerade as an initially unsteered prefix. This contract
supports matching prefix reuse with fresh sampler state, not arbitrary resume
under newly substituted scales. The underlying model codec independently checks
tensor framing, positions and predictor/controller state before GPU mutation.

The source binding passes the validated combined scope to the original model
codec, retaining image-position and MTP validation without copying the tensor
payload again. After successful transfer it commits the independently observed
model position before suppressing cancelled delivery. Interrupted transfers
discard the plan and retire the private destination; a failed commit after
mutation poisons the model. Native Gufo snapshots still refuse active steering.
The shared RAM/SSD budgets charge the typed tail through ordinary retained-state
accounting; no additional runtime thread is created.

## Validation

Four focused Debug checks and the same four ASan/UBSan/LSan checks pass.
The bank fixture covers exact little-endian values and independent known SHA
oracles, alternative geometry, partial/trailing/nonfinite data, allocation bounds,
ABI/output preservation, multichunk reads, file types, concurrent references and
snapshot lifetime after source mutation/unlink. The other checks exercise shared
core context admission, lifecycle and semantic events with CPU fixtures.
[Commands and scope](validation/steering-bank-host-2026-10-04.json).

The subsequent session-policy increment passes five focused Debug checks and
five ASan/UBSan/LSan checks. Independent fixed SHA oracles, chunk/burst invariance,
mixed/off histories, stale/discarded/partial updates, wrong-owner refusal, bounded
plans, image scope composition, retained references and concurrent snapshots
are covered. The initial compiler exit 2 from a formatting warning is retained.
[Policy validation receipt](validation/steering-policy-host-2026-10-04.json).

The provider increment passes six focused Debug checks and the same six
ASan/UBSan/LSan checks, including activation bounds and provider inventory/drift
refusals. The composed source verifies all 1,019 pristine files. Engine, executor,
batch and complete-adapter syntax checks pass with the feature enabled/disabled;
kernel syntax passes for `gfx1150` and `gfx1151`. These produce no device objects
and are not original-weight execution. The initial sanitizer exit 8 under sandbox
ptrace and syntax exit 1 from a missing `ENGINE_ENABLE_HIP` compile definition are
preserved; the corrected checks pass. CPU telemetry and current `.161` occupancy
are retained in the [provider receipt](validation/steering-provider-host-2026-10-05.json).

The metadata increment passes eight Debug and eight ASan/UBSan/LSan checks.
Independent full wire oracles, all-byte corruption, valid-checksum malformed
frames, mixed/off history continuation, bank/geometry/frontier refusal,
owner/pin/discard/stale transactions and RAM/SSD payload compatibility are covered.
Public C++ headers and the complete adapter syntax pass; no device objects are
created. The first two Debug failures are test errors (transcribed oracle length
and an unlinked SSD fixture rejected by the codec); their exits remain recorded.
[Metadata validation receipt](validation/steering-state-host-2026-10-05.json).

The direct-admission increment passes nine Debug and nine ASan/UBSan/LSan checks.
Its native fixture uses actual tiny host bank files and synthetic retained
frontiers, covering malformed options, bounds, independent history SHA, partial
completion, discard, EOS/no-advance, cancelled delivery, foreign/stale plans and
wrong-owner refusal. All 31 public C++ headers and complete-adapter syntax with
steering enabled, disabled and without state access pass. No device object,
linked GPU runtime, original-weight session or steering cost is qualified.
[Admission validation receipt](validation/steering-admission-host-2026-10-05.json).

The model-prefix binding passes ten Debug and ten ASan/UBSan/LSan checks. Its
native fixture exercises aligned/KVC/auxiliary layouts, actual shared RAM/SSD,
all-byte policy corruption, scope/bank/scale/history refusal, independent model
admission and wrong-owner/retained-plan lifetimes. Actual C Qwen AR/MTP/vision
state codecs accept the combined scope while preserving their component bytes;
these are synthetic tensors, not model inference. All 32 public C++ headers
and complete adapter syntax enabled/disabled/without state access pass. Initial
build exit 2 from a fixture field-name typo and test exit 8 from expecting INVALID
for an unsupported magic are retained; corrected checks pass. No linked GPU
runtime or original-weight state continuation is qualified.
[Binding validation receipt](validation/steering-binding-host-2026-10-05.json).
