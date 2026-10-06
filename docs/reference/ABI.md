# Experimental transitional execution ABI 3

Executor ABI 3 adds `rope_profile` to `lie_model_options` (20 bytes, offset 16).
ABI 2 callers must rebuild: version and size checks reject the old structure.
The shared C17 `lie/rope.h` contract supplies immutable native/YaRN2/YaRN4
plans, frequency tables and cache identities. The adapter uploads the selected
plan for attention and indexer rotary lanes. Scalar AR, sampling, MTP and
vision operations keep their existing meanings.
See [context configuration and qualification](../guides/CONTEXT.md).

The additive `lie_backend_dense_sampling()` diagnostic identifies dense selector
ownership independently of request ABI 8 and generation ABI 3.
`lie/sampling.h` defines the separate model-neutral C17 sampling ABI 1:
borrowed rows/masks/counts, caller-owned bounded workspace and explicit RNG.
See [ownership and remaining delegated state](../development/C17-SAMPLING.md).

JSON value ABI 1 adds initialized `lie_json_value_slot` operations for owning
roots and borrowed nodes, including lazy initialization, copy/move, assignment,
root transfer and scalar queries. An owning move preserves the source's scalar
kind/value and transfers its exact root; a borrowed move preserves source identity
and clears payload only after success. Slots require caller synchronization and
cannot be copied with struct assignment. Later move refusal may materialize a
lazy pointer without changing logical values. Existing tree descriptions,
engine/state/cache/event/metric layouts are unchanged. HOST lifecycle/parity
checks pass; matching new-source GPU qualification remains pending. See
[owned JSON values](../development/C17-SAMPLING.md#owned-typed-json-values).

`lie/schema_integer.h` adds standalone C17 ABI 1 calls for exact integral
binary64 magnitude, exact integer comparison and signed grammar compilation.
`lie_schema_integer_compare` borrows a complete JSON number span and compares
its mathematical integer to a represented finite binary64 boundary, returning
`-1`, `0` or `1`. Integral decimal/exponent forms are accepted; fractional or
malformed spans, nonfinite boundaries and input/output aliasing refuse without
changing the result. Work is linear in input length, with constant stack and
no allocation or exponent-sized intermediate. The shared final output validator
uses this comparison for integer classification and numeric bounds. It reuses the
existing borrowed schema reader and caller-owned private builder; failures
preserve results and failed builder mutations require retirement. Existing
engine, sampling, grammar, state and HTTP layouts are unchanged. Original/ON/OFF
HOST witnesses pass; the `050ae826` correction's matching HIP ON/OFF build and
37 general plus 66 integer checks in each original-weight AR/MTP mode pass. See
[signed integer bounds](../development/C17-SAMPLING.md#signed-integer-bounds).

The `1bff953` Point build keeps these layouts and versions unchanged. Its
private adapter include-path and full snapshot-initialization fixes add no
public ABI. [Original-weight AR/MTP controls](../development/validation/c17-sampling-point-gpu-2026-10-05.json)
qualify that frozen integrated build within the stated wire/profile scope;
they do not qualify an unfinished finite-value ABI or a complete owned executor.

The matching `20777005` source/provider/application passes selected
original-weight AR/MTP controls with the existing engine/state/worker/HTTP
layouts unchanged. The [receipt](../development/validation/c17-binary64-point-gpu-2026-10-06.json)
does not qualify individual branches, private resources/cost or a fully owned
model executor.

`lie/binary64.h` adds separate ABI 1. The synchronous, model-neutral C codec
formats finite IEEE754 binary64 into caller storage without a NUL and parses
full strict JSON number spans with nearest-even rounding. Signed zero survives;
overflow/nonzero underflow, invalid syntax, aliasing, insufficient capacity and
tagged text/work budgets refuse without publishing outputs. Defaults cap text
at UINT32_MAX bytes and work at 64 million units. No pointers are retained,
heap allocator is called, locale/FENV is changed or model/device/worker is
created by these public calls. Bundled pinned Ryu retains its separate license.
Existing engine/sampler/grammar/state/HTTP ABI and DS4 framing remain unchanged.
See [host validation](../development/validation/c17-binary64-host-2026-10-06.json).

`lie/json_parse.h` adds separate ordered-event parser ABI 1 through
`lie_json_parse_events`; the existing `lie_json_parse` tools API is preserved.
Callbacks copy borrowed spans before returning and discard all staging on any
refusal. Parser allocations retire before return. Defaults bound input and
owned heap at 64 MiB each, container levels at 128 and lexical/key work at
268,435,456 units. Complete syntax, decoded duplicate-key checks and strict
UTF-8/escape handling are C17; no upstream type enters this header.

`lie/json_value.h` adds separate typed-value ABI 1. Opaque roots own allocator
domains, scalar/string/key bytes and ordered array/object children. Borrowed
children keep their identity across sibling growth; payload replacement or root
release invalidates borrowed spans/views. Release accepts roots only. Copies
stage before replacement; moves retire the source only after success. Refusal
preserves content and output handles, while diagnostic counters may advance.
Duplicate append retains order and lookup selects the first exact byte key;
parsing rejects duplicate keys. Defaults are 64 MiB requested heap, 262,144 nodes,
512 value levels and 268,435,456 copy/output work units. Allocator and optional
aligned private-view hooks are paired, nonthrowing and outlive their roots.
Immutable reads may run concurrently; mutations/release require caller
synchronization. Serialization callbacks can receive partial staging, which
must be discarded on failure. Private C++ reference/string/error projections
remain adapter glue. Existing engine/request/generation/state layouts, DS4
framing and reactive worker contracts are unchanged. See
[ownership and limits](../development/C17-SAMPLING.md#owned-typed-json-values)
and the matching selected
[AR/MTP qualification](../development/validation/c17-json-value-point-gpu-2026-10-06.json).

`lie/json_store.h` adds independent root-collection ABI 1. C17 adopts exclusively
caller-owned live JSON roots and transfers them back unchanged with `take`.
Child and duplicate adoption refuse; cross-collection double ownership violates
the caller contract. Roots, child identities and private views survive table
growth. Refusal preserves caller ownership and outputs; release retires every
root still held. Defaults bound cumulative successful adoptions at 262,144
(taking a root does not refund this budget) and collection heap at 16 MiB,
including table growth overlap. Root domains retain separate allocators/budgets;
all allocator/view contexts outlive their respective collections and taken roots.
Operations require caller synchronization and non-reentrant hooks. The additive
`lie_json_value_is_root()` query changes no typed-value structure or version.
Existing execution/request/state/HTTP layouts and cache framing are unchanged.
See [derived value ownership](../development/C17-SAMPLING.md#derived-schema-value-ownership).

`lie/schema_compile.h` adds independent compilation ABI 1. Its descriptor binds
the native root/visitor, paired allocator and nonthrowing predicate callbacks.
Success publishes an independently owned prompt, immutable program and root;
refusal leaves the result untouched. The builder/input may retire after success;
predicate and allocator contexts have the documented longer lifetimes. Defaults
bound serialized schema bytes at 2 MiB and prompt heap at 8 MiB including growth
overlap. Existing public layouts/versions and cache framing are unchanged.
The private default-ON prompt getter/storage changes require complete matching
ON/OFF providers and frontend consumers to rebuild together. HOST checks and
matching selected HIP/original-weight AR37/MTP37 controls pass for private
LIE/model/reference consumers; the official Gufo HTTP frontend is not built.
See
[publication contract](../development/C17-SAMPLING.md#schema-compilation-and-prompt-publication).

`lie/grammar_lexeme.h` adds model-neutral primitive/table/memo ABI 1. Immutable
tagged predicates own their alphabet/options and retain C numeric/DFA policies;
the additive `lie_number_retain` and `lie_regex_retain` calls extend opaque
ownership without changing existing public structures or versions. Retain
requires an already-owned reference; final release retires dependencies.
Predicates default to 64 MiB text/state. Tables and construction-only identity
memos default to 262,144 items and 64 MiB direct requested bytes, including
their bodies and overlapping growth buffers. Retained predicates/policies,
allocator overhead, stack, C++ projections and process/device costs are excluded.
Refusals preserve logical contents and published outputs; table/memo capacity,
peak and allocation diagnostics may advance. Input/output payloads may overlap;
length/match metadata must be disjoint.

Sealed ordered tables reject mutations and export C-only grammar hooks. Clone
produces an independent mutable table retaining the same immutable predicates.
Memo keys are borrowed identities, never dereferenced, and first publication
wins. Memo reads require quiescent mutations. Mutation/release require caller
serialization and retiring all borrowers. Paired aligned allocators outlive
references and support caller concurrency. No worker, RNG, model or persisted
cache enters these calls. Existing engine/state/HTTP layouts and DS4 framing
remain unchanged. See [ownership and limits](../development/C17-SAMPLING.md#owned-primitive-predicates)
and the matching selected
[AR/MTP qualification](../development/validation/c17-lexeme-point-gpu-2026-10-06.json).

The additive `lie_grammar_state_duplicate()` call deep-copies an opaque snapshot
using its saved allocator and limits. No grammar program or predicate is accessed;
frame order/bytes are exact and successful copies have independent storage.
Refusals preserve input and output handles. The allocator context must outlive
all copies; borrowed frame spans expire on owner release. Existing public
structures and ABI versions remain unchanged. The default-ON private C++ request
type now owns this C snapshot and must match the provider's selected compile
option; it is not a public C ABI. See
[request snapshot ownership](../development/C17-SAMPLING.md#owned-request-grammar-snapshots).

`lie/schema_root.h` adds independent ABI 1 for synchronous root admission and
construction. The caller supplies immutable node readers, a body visitor and a
builder. Schema mode validates resolved local-reference root identities but
visits the original root; object-only mode uses initialized generic JSON
primitives and may receive a NULL schema. Temporary identity storage uses the
reader's paired allocator and retires before Visit/return. Defaults bound
identities at 262,144 and whole-chain reader work at 64 million units. Refusal
preserves outputs; earlier visitor/builder mutations require retiring failed
compilation. No pointer/device/worker/RNG or persisted state is retained.
Existing public structures and versions stay unchanged. See
[root ownership](../development/C17-SAMPLING.md#root-schema-admission).

`lie/grammar_composition.h` adds independent composition ABI 1. The synchronous
core constructs immutable reasoning/tool marker automata, quotes arbitrary name
bytes, reuses argument-program identities and remaps ordered tables/predicate
slots. `lie_grammar_program_describe()` additively exports a borrowed description
until program release. Source origins remain alive until imported predicates
are retained by the caller; the composed view itself owns tables/name copies.
Caller-bound predicates and an independent runtime program outlive construction
retirement. Paired allocators, bounded work/tables and refusal preserve published
outputs and retire partial work. Defaults retain 262144 rule/class/lexeme limits
and 64 million work units. The C17 predicate table now retains imported leaf
identities; the adapter still projects templates and translates exceptions.
Existing engine/sampler/grammar/state/HTTP
layouts, DS4 framing and reactive worker contracts remain unchanged. See
[host validation](../development/validation/c17-composition-host-2026-10-06.json).

`lie/grammar_cache.h` adds separate compiled-schema cache ABI 1: copied byte
keys, bounded entries, opaque retained values and explicit release. Concurrent
calls serialize internally; retain/copy callbacks run under the lock and release
runs after unlock. Hooks must not throw or reenter; release/allocator contexts
support concurrency and outlive retired operations. Refusal preserves outputs
and entries. Destruction requires quiescence; client copies survive eviction.
No request/generation/engine, worker, RNG or persisted DS4 layout changes. See
[cache ownership and ordered eviction](../development/C17-SAMPLING.md#compiled-schema-cache).

`lie/sampling_history.h` adds separate model-neutral history ABI 1: tagged options,
caller-owned token/penalty storage and growth callbacks. Reset counts prompt tokens
only for repetition; accept counts all committed generated tokens independently
of the repetition window. Refusal preserves logical state; capacities/scratch may
change. Independent copy leaves RNG and grammar to their owners. The transitional
provider keeps its ON/OFF vector layout, with storage/exception glue only. No
executor, request, generation or persisted-state layout changes.

`lie/sampling_distribution.h` adds separate distribution ABI 1 for tagged ranked
rows, mutable proposal output and immutable proposal views. Caller-owned storage
and growth supply all workspace; borrowed sources stay disjoint. Builder refusal
publishes count zero, while normalization/proposal/verification refusal preserves
published input/result and RNG. Sparse duplicate IDs accumulate in source order;
compact positions are explicitly remapped to raw model IDs. Proposal creation
always consumes one draw; target singleton draws do not. Host verification owns
probability arithmetic only; model/controller state stays with its existing owner.
Provider ON/OFF layouts and executor/request/generation/persisted-state ABIs do
not change. See [exact numerical/draw rules](../development/C17-SAMPLING.md#ordered-distributions-and-mtp-probabilities).

`lie/grammar.h` adds separate grammar ABI 1: immutable copied program tables,
opaque owned snapshots, borrowed exported frame views and explicit release.
Tagged limits bound state/stack/work/primitive scratch; paired allocator hooks
must return fresh aligned storage and outlive program/state use. Predicate
contexts are immutable borrowed callbacks, not a claim that their algorithm is
C17. Advance supports exact input/output alias in predicate scratch; mask
application supports exact in-place logits but refuses other overlap. Refusal
preserves output ownership; empty snapshots are valid dead language prefixes.
Private provider grammar layout/source changes require matching archive/application
rebuilds and the current 45-file receipt. Executor/request/generation and DS4 payload
ABIs are unchanged. See [ownership and remaining compiler/predicates](../development/C17-SAMPLING.md#byte-grammar-and-logit-masking).

The additive snapshot-reader/writer ABI 1 in `lie/grammar.h` moves frame
traversal, construction, span/overlap checks, payload copies and temporary
planning into C17. Reader views remain valid until the next callback or call
completion. Writers allocate private staging containers; C validates every
capacity and input/output/plan overlap before copying any payload. Their storage
may change on refusal; publish only after OK and retire staging on every failure.
Callbacks are synchronous, nonthrowing and never retained. Successful read states
own their data; program/input release does not invalidate an exported snapshot.
Paired program/state allocator hooks retire import/plan storage on all paths.
Default frame/stack/lexeme limits remain 8192/16384/4160; counted heap-sort work
uses the state work budget. Provider vector/State layout remains unchanged,
with only view/growth/exception glue, and requires a matching 45-file rebuild.
No executor/request/generation or DS4 persisted layout changes. See
[snapshot bridge ownership](../development/C17-SAMPLING.md#snapshot-readwrite-bridge).

`lie/grammar_builder.h` adds construction ABI 1: opaque mutable copied rules/
classes, tagged limits and paired allocator hooks. It supplies byte JSON
primitives, repetition, generic values and decimal-prefix intervals. Finish
computes productive/nullable sets, uses iterative cycle validation, removes
dead alternatives and seals dense tables. The output description borrows tables
until builder release; `program_create` copies them. Predicate/allocator contexts
must outlive their use. Failure preserves output, latches mutation status and
requires builder retirement; successful earlier primitives may remain. An invalid
output argument can refuse before mutation. The default construction budget is
64 million counted units, distinct from runtime state work. This adds no engine,
request/generation, worker/event or persisted-state layout. The current 45-file
inventory and extended runtime recipe require matching sealed provider/application
builds. Typed provider templates/predicates remain transitional. See
[construction ownership](../development/C17-SAMPLING.md#grammar-construction-and-validation).

`lie/schema_transform.h` adds separate schema-transformation ABI 1. Tagged
limits and paired allocators bound synchronous structural equality, local JSON
pointer resolution, keyword validation and conjunction. Readers borrow stable
typed views; writers copy spans into caller-owned private staging. Refusal
preserves result arguments; retire staging on success or failure. Object keys
are unique and ordered. Output/error storage is disjoint from views/context;
error detail borrows the input tree. Equality is iterative; conjunction has a
64-level reference budget. Typed JSON payloads and child storage now belong to
the separate C17 value contract; private projections stay in the adapter. No model,
worker, RNG, engine or DS4 layout changes. Matching
provider/application rebuilds are required for changed private sources. See
[schema ownership](../development/C17-SAMPLING.md#json-schema-conjunction-and-reference-resolution).

`lie/schema_values.h` adds separate finite-value/container ABI 1 using the same
stable borrowed reader and private staging contracts. C17 owns type matching,
reference/branch filtering and ordered canonicalization, JSON string/key
quoting, finite-value traversal, object suffix states, array bounds and counted
characters. Defaults are 256 value/reference levels, 120,000 counted characters
and the transform's 64-million-unit work budget. Counts consume a private
construction state shared across nested visitor callbacks. Normalization and
other result arguments publish only on success; exclusion publishes
`{false, NULL}`. Refusal requires retirement of staging/builder/counts. Leaf
predicates, binary-double serialization and schema dispatch/reference memo
remain synchronous provider hooks. No engine, worker, event, RNG or persisted
DS4 layout changes. See
[finite-value ownership](../development/C17-SAMPLING.md#finite-values-and-container-rules).

`lie/grammar_number.h` adds separate numeric-grammar ABI 1: copied immutable
numeric policies, borrowed exact decimal spans and transactional match/value/LCM
outputs. Lower/upper bound selection, integer-grid reduction, prefix interval
intersection and decimal LCM belong to C17. Runtime prefixes retain 4096 bytes
and 1024 integer shifts; complete values additionally support exponents.
Bounded arithmetic/refusal and allocator lifetime rules are declared in the
header. JSON numeric representability checks stay in the adapter. Each call
owns a bounded workspace and adds no inference worker or persisted state.
See [numeric ownership](../development/C17-SAMPLING.md#exact-decimal-numeric-grammar).

`lie/grammar_vocabulary.h` adds vocabulary ABI 1: copied byte pieces/trie,
iterative token masking/acceptance and exact transition interning. Grammar ABI 1
adds snapshot clone, lexical comparison and internal hashing plus distinct
vocabulary/no-token/mask-work refusal codes without changing existing layouts.
A caller-synchronized bounded mask cache owns C snapshot keys and opaque retained
payloads; successful publication consumes incoming ownership, refusal consumes
nothing. Provider private vocabulary/cache layouts change in both ON/OFF arms;
matching archive/application rebuild and the 45-file source-bound receipt are
required. No executor/request/generation or DS4 persisted layout changes.

`lie/grammar_regex.h` adds separate Unicode-DFA ABI 1: tagged descriptions,
immutable copied scalar-class/transition/acceptance tables, owned successor
construction, accepting distances and bounded reachability/cycle queries.
`lie/grammar_string.h` adds string-policy ABI 1: immutable caller-owned options
borrow the DFA. State remains 20 native bytes for five uint32 fields; no wire or
persisted endian format is implied. UTF8/escape/surrogate/pending and whitespace
predicates and copied mask-key canonicalization are C17. Refusals preserve live
state/matches; caller-owned policies/allocator contexts outlive calls. See
[ownership and budgets](../development/C17-SAMPLING.md#string-and-unicode-dfa-runtime).
Private provider construction layout/source requires matching builds and the
45-file receipt; executor/request/generation/DS4 persisted layouts do not change.

`lie/grammar_regex_compile.h` adds separate compiler ABI 1. A mutable,
caller-synchronized construction context owns copied scalar classes, normalized
expression DAGs, nullable context bits and memoized iterative derivatives. Seal
builds the Unicode partition and BFS graph, copies an immutable runtime program
and retires temporary tables. Explicit expression/derivative/state/range/work
budgets refuse without publishing outputs; successful internal memo entries can
remain after a refused operation. Published programs never change. Syntax parsing
and assertion expansion now use C17. The Unicode context owns registry/input
storage using ICU C APIs; ICU remains the actual set/property/conversion dependency. This adds no executor/request/generation or persisted-state
layout; matching provider/application
builds and the 45-file inventory plus compiler recipe are required.

`lie/grammar_regex_parse.h` adds separate parser ABI 1. It borrows UTF16 units
and a model-neutral opaque Unicode-set callback table for one synchronous call.
C17 owns syntax parsing, bounded AST lifetimes and iterative assertion expansion.
Fresh set handles retire on every path; no callback exception may cross the C ABI.
The reusable `lie/grammar_unicode.h` context supplies UTF8 decoding and set
storage/full-set identity using ICU C APIs; ICU owns the actual property, set
and conversion semantics.
Syntax refusals have deterministic English reasons; resource/work/node/compiler
refusals preserve root and published programs. Successful compiler entries may
remain after a refused parse. Default AST/work limits are 65,536 nodes and
32 million work units; original 16,384-byte and 32-level group limits remain.
Matching provider/application builds and the 45-file inventory/parser recipe
are required; no executor/request/generation or persisted-state layout changes.

`lie/grammar_unicode.h` adds separate Unicode-context ABI 1. The context owns
its compiler, private copied full sets, range translations and temporary handles.
Its borrowed compiler permits expression construction/query/sealing; only the
context publishes classes. Calls are synchronous and caller-serialized. No ICU
or upstream type enters the public header. UTF8 replacement decoding preserves
explicit NUL lengths, with disjoint buffers/length output and a 16,384-byte limit.
Paired allocator hooks cover owned C storage, not ICU's internal allocations;
ICU C mutators do not expose complete internal OOM detection. The context retires
outstanding handles and compiler storage; sealed programs have independent
storage and retain the allocator-context lifetime. Diagnostic ICU/Unicode versions
are not model/cache identities. See
[Unicode-set and input ownership](../development/C17-SAMPLING.md#unicode-set-registry-and-input).

`lie/steering.h` defines bank ABI 1 and separate session-policy ABI 1.
The policy owns finite scales, bounded prepared transactions, owner-only commits,
confirmed retained-target history and locked metadata snapshots. Its scope hashes
are independent of chunk size and preserve steered history when scales become
zero. Bank/session references and plan resources remain shared C17 concerns;
there is no numerical operation or transport dependency in these interfaces.
This additive library does not change executor ABI 3 or generation ABI 3.
The current request ABI 8 budget semantics are documented below. Additive owner-only encode,
prepare-restore and staged cache-scope functions use explicit 192-byte version-1
metadata; they retain the existing policy ABI and structures. Captured capacity,
revision and runtime counters are not serialized. Restore validates the matched
bank and independently confirmed model frontier before live mutation, and requires
an exact completed transfer to commit. Host RAM/SSD fixtures qualify this protocol;
the actual GPU model-cache continuation remains unqualified.
See [format, policy and actual binding requirements](../development/STEERING.md).

Independent steering model ABI 1 adds bounded model options, an explicit C
factory composing predictor/projector admission, and model/sequence queries.
Initial scale configuration and C17 retained-forward prepare/complete are wired
into provider source; an independently observed frontier mismatch or failed
post-mutation commit poisons the model. Existing model opens keep their absent-bank
path. These additive functions do not change existing executor/request/generation
structures. Additive `lie_core_create_steered` copies the tagged options and file
path before return, admitting on the existing owner. `lie_core_steering_snapshot`
copies a READY-only admission record under the core gate; failure preserves the
tagged output. Existing unversioned core options/info layouts remain unchanged.
Server and native core bench use the same factory, scopes and CLI parser.
Additive job steering ABI 1 admits one copied asynchronous change and exposes
ticket completion and owner-confirmed policy snapshots. The owner-only direct
live operation preserves the retained frontier and sampled correction while
invalidating private graphs/controller state. Existing request/generation/state
and core option/info layouts remain unchanged. Stored-request HTTP controls
project this asynchronous API. Original-weight GPU qualification remains open.
Additive schedule ABI 1 admits 1–64 copied, strictly increasing physical
position/scale steps through `lie_core_submit_steering`, without changing request
ABI 8. A separately tagged `lie_job_steering_schedule_snapshot` records each
attempt/application, actual frontier and terminal unattempted cancellations.
Scheduled jobs refuse unscheduled changes; NULL schedule preserves normal submit.
Only planned jobs allocate the bounded schedule record, included in retention
accounting. The original device owner splits prefill and caps each row's AR/MTP
advance; no callback, thread or client polling chooses an application boundary.
`lie_core_submit_choices_steering` copies the same optional plan into independent
child jobs, preserving seed offsets and rollback. HTTP `dir_steering_plan` is
normalized before admission; JSON does not enter core contracts. Per-choice
controls and retained snapshots use the same job APIs, with extra retained bytes
charged only when a bank is present. Existing public layouts are unchanged.
See [direct binding](../development/STEERING.md#direct-modelsession-binding).

`lie/steering_activation.h` defines separate C17 activation ABI 1: bounded row
geometry, finite scale, checked span capacities and caller-owned output. Every
refusal preserves that output. It is not a model executor or a persisted state
format. The owned HIP operator and private provider hooks have host/syntax
validation only. Initial scales are immutable after numerical work. Native
provider snapshots refuse active steering; the owned typed state path below
validates history and scope before model transfer.
Executor ABI 3, generation ABI 3, request ABI 8 and DS4 payloads are unchanged.

`lie/steering_state.h` defines separate C17 binding ABI 1: canonical auxiliary
layout/view, actual-frontier capture and staged prefix restore. The model binding
revalidates actual geometry and numerical payload independently. Restore requires
matched initial scales/history/semantic scope before upload and commits exactly
the observed completed model frontier. Inactive unused directions preserve legacy
framing. Host RAM/SSD and real model-codec fixtures qualify this protocol with
synthetic tensors; actual GPU continuation remains pending.

`lie/weight_decode.h` defines independent C17 weight-decode ABI 1. F16/Q8_0
encoded bytes are borrowed, lengths are exact, and BF16 output is caller-owned.
There is no allocation or device dependency; overlap and nonfinite input are
rejected before output mutation. Existing inference/state contracts are unchanged.
See [vision upload and resource limits](../development/VISION.md#core-and-reactive-behavior).

The adapter delegates to Gufo Model/Session. **This is permitted for bootstrap,
not proof of an autonomous LIE backend.** [BACKEND.md](../BACKEND.md) defines the
subsequent requirement-driven replacement gates. It now links into the optional
HIP server and is connected to the C worker/flow/HTTP path. A bounded original-weight
C1 HTTP/SSE smoke passed on Strix Halo (`t0-model-smoke-r4`); full numerical and
hardware qualification remain open. The eventual owned numerical ABI remains
separate; keep upstream types inside the adapter.

`include/lie/executor.h` is C17-compatible and contains only fixed-width types,
lengths, opaque handles and caller-owned error buffers. No C++ types are public.
`adapters/gufo.cpp` compiles against the pinned `f783fedb` composition only with the explicit
`LIE_GUFO_ADAPTER_OPT_IN` definition. The following describes the experimental
contract, not hardware qualification. `LIE_GUFO_HEADER_CHECK` remains object-only;
`LIE_GUFO_RUNTIME` explicitly links verified private upstream archives. ABI 1
receipts remain historical. `lie_backend_open` is the selected composition binding
(`adapters/gufo_binding.c` for Gufo), not an implicit fallback. Provider name,
source pin and ownership queries expose delegation; the explicit factory
`lie_gufo_open` remains available and is not relabelled as an owned engine.

The default-ON private grammar layout now contains program/table handles instead
of duplicate C++ rule/class containers. Provider identity includes the exact
storage recipe; matching providers and consumers must rebuild together. Public C
structures/versions are unchanged. See [ownership](../development/C17-SAMPLING.md#immutable-grammar-table-ownership).

## MTP branch extension

[MTP](../development/MTP.md) now has an additive, model-neutral C
contract in `include/lie/mtp.h`. Executor ABI 2 scalar AR entry points retain
their meanings. Capabilities have ABI 1 and an exact struct size. Upstream
model types remain inside the adapter.

## Vision branch extension

[VISION](../development/VISION.md) now has an additive, model-neutral C
contract in `include/lie/vision.h`. Executor ABI 2 scalar AR entry points retain
their meanings. Request ABI 3 introduced owned image spans; current
`LIE_CORE_REQUEST_ABI=8` owns parallel-tool policy, output format, schema, stop
sequences, oldest-turn truncation, the embedded generation ABI 3 and the explicit
EOS policy for raw benchmark requests and automatic output budgets. ABI 7 and
earlier callers must rebuild.
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
MTP advertises `prefix_state_supported=1` only with the verified complete-history
DS4 provider. The legacy state variant advertises zero for MTP. Cache admission
checks this per-model capability before readiness; unsupported models require
RAM zero and no SSD directory. Joint admission through `lie_backend_open_mtp_vision`
requires both feature contracts on the same model; no extra inference worker or
HTTP-owned continuation state is introduced.
The vision binding now advertises complete prefix state only with the verified
DS4 complete-history provider. Legacy providers advertise zero and require
explicit cache-off configuration. The additive `LIE_STATE_CACHE_SCOPE` role and
`lie_vision_prompt_cache_scope` function do not change existing structure layouts
or enum values. Generic cache/SSD APIs gain scoped variants; existing wrappers
continue to select zero-scope legacy state. Steered text requires its checked
policy scope. Scope extraction is nonmutating and requires
an uncompressed U8[32] component. Generic layout validation rejects duplicate,
misplaced or malformed scope sections. GPU qualification remains separate.

`LIE_STATE_STEERING_POLICY=15` is an additive layer-zero U8[192] metadata
component with one required U8[32] cache scope. It follows the auxiliary boundary
in KVC and does not change any earlier role values, state ABI 2 structures,
DS4 tensor payload or existing envelope version. The generic validator checks
size/type/placement; the trusted provider must decode policy content and validate
the combined scope before transfer. Legacy state with no metadata is explicitly
unsteered and requires zero scales. [Wire and restore contract](../development/STEERING.md#state-metadata-and-staged-restore).

## Ownership and completion

Shared-core job/output notification and aggregate retirement counters have
separate publication points. Clients must wait for the required core counter
delta through core notifications within their deadline; observing job terminal
state alone does not make a cross-object snapshot atomic. The benchmark probe
checks full borrowed-byte stability during this bounded wait and cancellation.

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
  violation. Reported token-text size must fit its caller buffer. MTP is admitted through its separate capability and burst entry point;
  native AR multirow submission uses the additive contract below.
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
admission; refusal preserves caller ownership. Schema strings and parallel-tool
policy belong to the core copy; HTTP retains only projected output. No admitted
core job retains a json-c object. Adapter translation bounds aggregate spans/strings
to 32 MiB (four times the body bound); HTTP requests have a separate 8 MiB cap. The native renderer applies its
context-derived output bound (at least 1 MiB). The adapter validates the GGUF
template before model load, then invokes the pinned Qwen renderer/tokenizer with
thinking disabled, structured calls/results and real tool declarations. Buffer/
physical-context refusal precedes session mutation. Plain formatting remains
byte-identical in the CPU formatter test. Raw tokenization remains distinct.
No tool code executes here. Exact-session snapshots remain absent;
MTP uses its separate admitted contract. Native decode batching uses the additive contract below.
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

## Shared direction-bank ABI 1

`lie/steering.h` owns an immutable C17 bank with independent version/size checks.
Geometry has model-derived layer count, hidden width and an explicit host byte
budget; no model/platform type crosses the contract. Exact flat little-endian
f32 values and file/geometry digests are exposed only while an owned reference
is held. Failed loads/queries preserve output handles and fields. Reference
operations are thread-safe under the documented existing-pin lifetime rule.

This host primitive does not activate provider steering, change request or
executor ABIs, or alter state/KVC framing. Model-derived admission and session
history and typed model-state are now bound in provider and shared-worker source;
dynamic client controls and numerical GPU qualification remain required.
[Format, ownership and binding requirements](../development/STEERING.md).

## Additive generation configuration

`lie_generation_options` has its own ABI 3 version and exact struct size.
ABI 3 appends `top_k` (nonnegative signed 32-bit integer) and `min_p` (finite
double in 0..1); zero disables each filter. Request ABI 6 embeds this expanded
structure. Callers must rebuild and initialize both tags: request ABI 5 or
generation ABI 2, including truncated structures, is rejected before provider
mutation. Earlier ABI receipts retain their historical meaning.
`lie_sequence_configure` runs on the model owner before prefill; a started
sequence or invalid/nonfinite/range-invalid option is refused. Existing ABI-2
model/message layouts are unchanged. Parsed requests own their scalar controls;
there are no upstream types. Temperature, top_k, top_p, min_p, frequency/presence penalties
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
and vision use additive capability contracts outside scalar executor ABI 2.
Keep completed scalar/batch semantics.
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

[Semantic event ABI 2](EVENTS.md) is the common output contract for HTTP, Responses
and direct benchmarks. Current request ABI 8 retains `parallel_tool_calls=true` by
default; using initialization and exact version/size checks remains required.

`lie/core.h` is an experimental C client contract, distinct from executor ABI 3.
`lie_core_request_init` sets required version/size tags, greedy generation
(`temperature=0`, `top_p=1`, `top_k=0`, `min_p=0`, `seed=-1`) and output limit 128. The caller chooses
exactly one input: normalized messages/tools, physical token IDs, or raw UTF-8
text (no implicit chat template). Initialize `*out` to NULL before submit.

Request ABI 8 changes `max_tokens=0` to an explicit automatic-budget sentinel.
HTTP omission/null uses it; HTTP numeric zero remains invalid. The C initializer
retains its explicit 128-token default, and direct clients can choose zero.
Admission reserves at most min(configured context minus one, 4096) output IDs
and optional logprob entries. The copied reservation remains immutable once
published, so metadata/semantic consumers never race a changed request.
After preparing the full prompt on the single device owner, a separate limit
becomes min(admitted reservation, context minus physical prompt). Empty room
refuses before sequence creation. Explicit positive budgets retain their exact
meaning, including context refusal; automatic truncation reserves one output
position and preserves any history that still fits. Final MTP bursts use the
resolved remaining budget. No output beyond the existing advertised engine
ceiling or new thread is introduced.

`lie_job_info.output_token_limit` is zero before preparation and the resolved
limit after preparation. Natural EOS/stop/cancellation can produce fewer tokens.
Retained Responses reserve bounded text/events for an automatic request using
the existing 4096 ceiling, rather than a zero-byte buffer. Quotas and lifetime
charges still refuse without admitting unbounded retained storage.

`lie_core_submit` borrows input only during the call and deep-copies nested
arrays/strings into one bounded arena. Successful submission never steals caller
storage. Return codes are 0 admitted, 1 not ready/stopping, 2 admission full,
3 invalid input/allocation failure. Copy reservations plus queued/active jobs are
bounded to eight, with at most 32 MiB normalized input per admission. Vocabulary,
formatted physical context and provider checks precede sequence mutation on the
owner; asynchronous refusal is reported through the job terminal. No queue or
provider call runs on a protocol-owned JSON tree.

The core grants eight initial output credits. Clients release each output loan,
then return demand through `lie_job_event_request` (or `lie_flow_request` for
legacy raw clients); without more credit a row cannot
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
not reusable KV checkpoints. Request-copy storage remains until the last job reference too, because semantic
validation can follow numerical retirement.

The HTTP legacy submit shim preserves its transfer-on-success interface by
freeing the parsed request after the core accepts its independent copy. The
core and its public headers have no JSON, libuv, llhttp or socket dependency.
`lie_flow` retains Linux eventfd/pthread dependencies; this extraction does not
claim cross-platform portability. CPU acceptance is in [CORE-EXTRACTION.md](../development/CORE-EXTRACTION.md).

### Fixed-token benchmark completion

Request ABI 7 introduced `eos_policy`, retained in current ABI 8.
Initialization selects `LIE_EOS_STOP`.
`LIE_EOS_IGNORE` is allowed only for raw tokens/text, without stop strings or
constrained output; message, tool and vision requests refuse it before admission.
Unknown policies and ABI 6 requests also refuse before sequence creation.
HTTP clients retain the default policy; no HTTP request option enables this mode.

The additive `lie_sequence_set_eos_policy` must run on the device owner before
prefill, restore or sampling. It leaves existing executor ABI 3 structures and
generation ABI 3 unchanged. Invalid values or an already started sequence refuse
before mutation. Gufo stores the policy per sequence and passes it to scalar,
native batch and verified MTP calls; constraints cannot be combined with ignore.
EOS is sampled normally and, in ignore mode, is a confirmed token with its actual
ID, position and text bytes. Its text may be empty. No masking, retry or replacement
draw is introduced. A provider that reports EOS stop despite ignore poisons the
runtime under the existing failed-call rule and suppresses that shared result.
The token budget, credit, cancellation and context bounds still apply.

`synapse-lie-bench --suite core --ignore-eos` selects this mode explicitly.
The CLI and report both require the complete output budget with a length finish;
`eos_policy` is part of the result and comparison identity. Missing historical
fields mean `stop`. Current host checks do not qualify original-weight fixed
TG128 or change the retained physical 1M failure.


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
## Strix Point device admission

The optional Gufo composition selects one verified HIP build architecture,
`gfx1151` or `gfx1150`. Model loading refuses a mismatched device or a configured
`HSA_OVERRIDE_GFX_VERSION` with `LIE_UNSUPPORTED`; inability to query HIP device
properties is `LIE_BACKEND_FAILED`. Validation precedes numerical weight upload.
No executor struct, ABI version, device-owner rule or reactive scheduling contract
changes. The [Strix Point report](../STRIX-POINT.md) separates CPU admission tests
from pending original-weight device qualification.

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

## OpenAI generation and response records

Generation ABI 3 retains ABI 2's bounded token bias and optional target
log-probability reporting and adds top-k/min-p. Request ABI 6 retains ABI 5's
neutral JSON/schema controls, stop sequences and optional complete-turn
truncation, with the expanded generation options.
All borrowed strings and bias entries are copied at admission. Executor ABI 3
and DS4 state payloads retain their existing layouts. Schema/regex compilation
stays inside the explicitly selected transitional provider; byte predicates, token trie and mask-cache policy use the shared C17
grammar module. Snapshot read/write planning, validation and copies use C17;
provider vector storage stays private typed translation.

`lie_core_submit_choices` owns independently seeded jobs on the same device
worker. Failure cancels and releases its own admitted children. `lie_records`
owns typed input/history, validated text/calls and bounded retention. One client
reactor consumes each job, either through `lie_record_next` or background
`lie_record_pump`. No HTTP type enters either interface. Acquired records must
be released before destroying their store, and records before destroying the
core. `lie_record_attach` transfers a job reference only on success.

Logprob witnesses are copied under the job metadata gate. They correspond to
the completed target frontier, not drafts or transport receipts. Ordinary
requests allocate no scoring arrays and retain their existing burst width.

Replay uses `lie_record_event_count` / `lie_record_replay`: immutable borrowed
semantic views without loans or additional consumers. A pinned record retains
the journal and owned text/calls. Observer disconnect releases that pin and
never cancels the job. Live collection remains exclusively foreground or
background; only that collector releases loans and grants confirmed-token
credits. Stop-filtered probability copies omit hidden bytes while preserving
physical token witnesses and token usage. Automatic truncation changes only the
job-owned admission copy; the client retains the originally submitted history.
