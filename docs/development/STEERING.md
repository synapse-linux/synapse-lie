<!-- SPDX-License-Identifier: MIT -->
# Directional steering implementation

The C17 shared library owns direction-bank loading, bounded host allocation,
immutable values, session policy transactions, history/cache identities and
explicit state metadata. Owned HIP activation operators and target-provider
hooks are qualified only by host contracts and syntax checks. Direct C model and
session binding is present in provider source; shared-worker/cache integration,
public HTTP/bench controls and GPU qualification remain open.
Loading a bank or advancing policy metadata is not model inference and does
not qualify steering quality or performance.

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
separate semantic domain. These are identity primitives: current core jobs do
not yet attach them to live model RAM/SSD lookup/capture or HTTP controls.
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

Per-session scale changes must run on the exclusive device owner, preserve past
KV state, and invalidate incompatible captured graphs and pending speculative
proposals/correction assumptions. Define and retain the effective scale history
when capturing RAM/SSD state; a token-only prefix must not reuse state produced
under different steering. No extra provider/HTTP thread is introduced.

Remaining work in roadmap item 5 is qualification of the HIP binding,
shared-worker admission/accounting, policy integration into model cache, live scale
changes, HTTP and native bench exposure. GPU gates on
`.161` must prove unchanged output with steering absent/zero, malformed input
refusal before model mutation, prompt/decode edits, scale transitions, independent
AR/MTP checks and measured quality/cost. The user-visible naming follows DS4's
`--dir-steering-file`, `--dir-steering-ffn`, `--dir-steering-attn` once those
controls are implemented; they are not available CLI flags yet.

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
bytes; public core resource/metrics projection is still pending. Absent directions
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
binding refuses state transfer for every admitted bank, including zero scales,
until history-aware state compatibility is wired. Existing model opens without
a bank retain their RAM/SSD path. These private provider hooks are not a working
HTTP/bench steering feature.

`steering-edits.json` records 25 exact replacements against independently fetched
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

`prefix_state_supported` is false for this increment. All direction-enabled model
state/SSD identity requests refuse before transfer or heavyweight hashing,
including zero scales, so restore cannot silently desynchronize the two
frontiers. The shared worker, HTTP and native bench do not yet call this factory.
History-aware cache binding and resource admission must be completed before
exposing the feature through those clients.

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
