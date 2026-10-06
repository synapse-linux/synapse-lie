<!-- SPDX-License-Identifier: MIT -->
# C17 sampling and grammar runtime

The first model-executor extraction on `feature/c17-sampling` replaces dense
token selection and random draws with `src/sampling.c`, shared through
`include/lie/sampling.h`. HTTP and the direct benchmark keep their existing
core/worker path. The numerical model forward remains the transitional Gufo
provider; this does not complete the autonomous C executor.

Original-weight continuation on `.157` now passes the AR HTTP controls and
fifteen C17/C++ output/usage/logprob comparisons. MTP prefix continuation also
passes complete-logit replay after correcting separately admitted predictor
geometry. [Functional evidence](validation/c17-gpu-functional-2026-10-03.json)
records the failures and limits. The
[matched performance campaign](validation/c17-gpu-performance-2026-10-03.json)
now compares 46 measured pairs plus 12 warmup pairs through 128K occupied context,
eight users and a full 258794-token prompt. Input/output/counter/frontier witnesses
agree exactly. TG medians differ by less than 1% except the retained un-warmed
1500-token fresh point, which loses 16.64% and still requires investigation.
Ordinary greedy retains GPU argmax and does not isolate C dense-filter cost.

The newer integrated grammar/history/distribution checkpoint `1bff953` passes
37 original-weight HTTP controls in both AR and MTP on `.161`. Greedy AR and
the DS4 temperature-1/top-p-1/top-k-0/min-p-0.05 profile in AR/MTP each complete
two PP1500/TG128 sessions with exact per-profile same-seed token replay.
[GPU evidence](validation/c17-sampling-point-gpu-2026-10-05.json) records the
source/binaries and two retained build failures. This exercises selected
structured-output/tool paths; it does not qualify every grammar branch,
independent GPU probability behavior, faults, allocation-exact resources or
matched cost. Finite-value/visitor extraction remains outside that checkpoint.

The later matching `6a48da3` build includes the 57-file C17 schema memo,
dispatch, Visit and body inventory. It passes 37 original-weight OpenAI
controls in each AR/MTP mode on `.161`
([GPU receipt](validation/c17-schema-body-point-gpu-2026-10-05.json)). This qualifies
selected tool/grammar/output paths; individual branches, faults, independent
probabilities, allocation-exact resources and matched cost remain open.

The later 60-file numeric leaf increment moves schema constraint preparation,
scalar acceptance, exact LCM representability and numeric literal construction
to `lie/schema_number.h`. Its
[host checks](validation/c17-schema-number-host-2026-10-06.json) pass 13 Release,
13 sanitizer and 37 pristine/ON/OFF controls. All 20 earlier complete witnesses
retain their hashes. The later matching `a24875f` build below passes selected
AR/MTP controls; individual numeric GPU gates remain open. `6a48da3` excludes it.
Binary64 conversion and immutable composition are extracted in the later
host-qualified increments below; typed storage/model/controller remain private.

The later 63-file format increment also moves pinned format selection/patterns
and schema expansion to C17. Its
[host checks](validation/c17-schema-format-host-2026-10-06.json) pass 14 Release,
14 sanitizer and 38 pristine/ON/OFF controls with all 21 prior complete hashes
unchanged. The later matching `a24875f` build below passes selected AR/MTP
controls; individual format GPU branches remain pending. Later increments
below extract composition and the codec; typed storage/model/controller remain private.

The later 66-file increment moves the reasoning/tool composition cache policy
to `lie/ordered_cache.h`. Its
[host checks](validation/c17-composition-cache-host-2026-10-06.json) compare
retained program identities, language/prefix decisions and concurrent reuse.
The matching `a24875f` sealed provider/application build now passes 37
original-weight OpenAI controls in each AR/MTP mode on `.161`
([GPU receipt](validation/c17-schema-policy-point-gpu-2026-10-06.json)). Selected
integrated paths are qualified; individual numeric/format branches, new SSD BPE,
independent probability/fault/private resource/matched cost remain open. Both
modes observe a maximum of 44 whole-process threads, including runtime helpers;
the source adds no inference worker or measured speedup. Immutable grammar
composition is now extracted in the later host-qualified increment below.
Opaque typed key/value storage remains private; binary64 conversion is extracted below.

The later 69-file increment moves the full immutable reasoning/tool algorithm to
`lie/grammar_composition.h`: marker transitions, ordered alternatives, name
quoting, identity imports/remapping and stop policy. Its
[host checks](validation/c17-composition-host-2026-10-06.json) compare complete
ordered states and token masks against pristine/OFF algorithms. All 23 earlier
witness hashes are unchanged; independent paired-allocation failure and core
byte accounting checks pass. Typed predicate storage/templates remain private.
The later matching `20777005` build below covers selected original-weight
AR/MTP paths; the older `a24875f` receipt excludes this increment. Typed storage/model/controller ownership and
broader qualification remain open.

The later 83-file increment moves JSON binary64 conversion to `lie/binary64.h`.
Its [host receipt](validation/c17-binary64-host-2026-10-06.json) records 17 focused
Release, 17 sanitizer and 42 complete pristine/ON/OFF controls. All 24 previous
complete witness hashes are unchanged. Three exact recipe edits keep both
original OFF conversion bodies; the ON JSON and numeric schema paths call the
same C codec. The inventory includes 71 first-party files and 12 vendor/provenance
files. The matching `20777005` sealed provider/application build now passes
37 unchanged original-weight OpenAI controls in each AR/MTP mode on `.161`
([GPU receipt](validation/c17-binary64-point-gpu-2026-10-06.json)). Selected
integrated paths are qualified; individual branches, independent probability,
faults, quality, private allocation-exact resources, matched cost and new SSD BPE
remain open. Both modes observe 44 whole-process threads, including runtime
helpers; no new inference thread or speedup is claimed.

## Ownership and behavior

The C library owns finite greedy argmax, token-ID tie ordering, repetition /
frequency / presence arithmetic, dense bias, bounded top-k selection, top-p,
min-p, softmax normalization and xorshift64* draws. Filters retain the pinned
order and rounding: penalties/bias, temperature, top-k, top-p, min-p. The
ordinary greedy path needs no workspace. The unfiltered path retains vocabulary
order; ranked paths retain descending logits and ascending token IDs for ties.
Large top-p rows use the same 256-candidate first pass and full-selection fallback
as the pinned control, including its 1024-entry threshold.

The contract is model-neutral C17 ABI 1. Logits, already-compiled grammar masks,
sorted penalty counts, bias and RNG are borrowed from the caller. A growth
callback supplies bounded scratch storage and preserves live entries. The dense
selection module creates no threads, performs no device call, allocates no memory itself
and retains no input pointer. Failed builds publish a zero result count;
invalid draws leave RNG unchanged. The caller owns workspace cleanup.

`adapters/gufo_sampling.hpp` translates the provider's controls and containers.
`adapters/gufo_history.hpp` and `adapters/gufo_distribution.hpp` supply storage
and exception glue for the owned C17 components. Gufo still supplies vector
deep copies, deferred draws, entropy acquisition,
provider container storage, model/session and
speculative-controller state, and selected GPU numerical
kernels. Reporting logits still use the provider transform before the existing
C probability normalizer. The sampler as a whole is not yet autonomous C.
Existing eligible GPU argmax shortcuts remain delegated and preserved.
Immutable reasoning/tool composition and complete JSON syntax/decoding now
belong to the C17 core. Typed JSON values, key/string bytes and ordered child
storage now also belong to C17. Immutable primitive ownership, ordered predicate
tables, construction-only identity memo and runtime predicate dispatch now use
C17 as described below. Request grammar snapshots now also stay in C17 across
byte/token transitions, masks and speculative copies. Model/controller storage
and private C++ facades, schema/regex compilation and template projections remain
transitional.

Reactive readiness, per-row credits, cancellation, native batching and MTP
controller ownership are unchanged. There is still one device-owner worker. The C
selection call is synchronous; it does not add an asynchronous GPU forward or
establish a throughput improvement.

## Root schema admission

`lie/schema_root.h` adds model-neutral ABI 1. C17 follows root `$ref` chains,
detects repeated identities and checks that the resolved root has string type
`object` and no `anyOf`. It then admits the original schema, including reference
siblings, to Visit at depth zero and composes whitespace/body/whitespace. The
JSON-object mode skips reader/visitor calls and reuses the C17 generic builder
at depth 16. Prompt text and exception/value views remain private adapter glue.

A lazy C memo owns temporary identities and retires every allocation before
Visit or return. Defaults allow at most 262,144 identities and 64 million work
units shared across the complete root chain. Input nodes/spans are immutable
and stable; paired allocators/callback contexts outlive the call. Refusal
preserves the result, while prior private visitor/builder changes require
retiring the failed compilation. Builder finalization and predicate ownership
keep their existing contracts. There is no worker, RNG, cache or device call.

Two exact guarded edits retain the complete original OFF root algorithm under
`LIE_C17_SAMPLING`. The provider binds 96 files, including the new C source,
public header and private adapter, plus a `schema_root_edits_sha256` gate.
[Host checks](validation/c17-schema-root-host-2026-10-06.json) retain complete
original/ON/OFF states, byte masks, prompts, refusals and preceding witnesses.
This increment needs its own sealed HIP build and original-weight qualification
on `.161`; the earlier `117cbae6` receipt excludes it. Remaining construction
facades/template projections and the model/controller are transitional.

## Owned request grammar snapshots

The default-ON request state now owns a `lie_grammar_state` directly. Start,
advance, expansion, canonicalization, token acceptance and mask queries use
the C snapshot without repeated vector/string import and export. Existing
request and MTP sampler copies call the additive C17
`lie_grammar_state_duplicate` function. Copies retain complete frame order,
symbol arrays and unsigned lexeme bytes in independent storage; moves transfer
one owned handle and clear retires it. Copy assignment stages before publication.
Refused copies preserve the source, previous destination and borrowed views.

Duplication uses the snapshot's allocator/limits and accesses no program,
predicate, model or device. The allocator context must outlive every copy.
Snapshots may outlive the immutable grammar program for inspection and copying;
runtime transitions still require a live matching program and predicate context.
Immutable reads and copies may run concurrently with a suitable allocator;
release/move/assignment require retiring all borrowers. Views are read-only and
expire on owner replacement or release. There is no shared mutable speculative
state or copy-on-write mechanism.

`gufo_grammar_state.hpp` is a private C++ value/exception/read-only-view facade;
it owns no vector/string payload. Default and moved-from states represent the
same dead prefix as a zero-frame C snapshot. The C API keeps NULL distinct.
An explicit legacy-vector snapshot bridge remains for fixtures/interoperability,
outside the default-ON runtime path. Three guarded exact edits preserve the
complete original OFF state and algorithms. C++ request types require the
provider's selected option; only the vocabulary size/layout fixture checks an
opposite-option header view. Public C layouts and ABI versions are unchanged.
The Gufo benchmark control now requires a coherent complete OFF provider,
including numerical/controller archives. An OFF sampler cannot be interposed
over ON model/controller objects with a different private request-state layout.
The receipt gate rejects ON or mismatched-target control archives. Both
provider builds and the new control pass matching sealed HIP qualification.
Source construction now tracks edit recipes so incremental builds regenerate
their exact variants when a recipe changes.

The [host receipt](validation/c17-request-state-host-2026-10-06.json) records
2,080 independent frame-copy oracles, 68 C allocator and three private assignment
refusals, 306 complete pristine/ON/OFF state-copy witnesses, and four joined
readers completing 256 iterations each. All 50 sanitizer host checks pass;
all 27 earlier complete witness hashes are unchanged. The selected state
borrow/copy/move/advance path makes zero C++ allocations. Three focused C
sanitizer checks pass. Release checks pass cumulatively at 87 unique: 86 in the
initial full run and the corrected provider verifier in one focused rerun.
These host checks cover deep-copy lifetime after program/source retirement,
allocation refusals, copy/move/self-assignment, joined concurrent readers and
complete pristine/ON/OFF states/masks/sampler copies. The matching sealed
`117cbae6` build compiles complete ON/OFF providers and passes selected
original-weight AR37/MTP37 on `.161`
([GPU receipt](validation/c17-request-state-point-gpu-2026-10-06.json)). Actual
Ninja commands verify the primary/reference consumer flags and complete OFF
archive linkage. Two common C1 controls preserve all physical inputs/output IDs
and full prefill/final-decode frontier hashes between LIE and Gufo. All five
windows close with actual exits 0, unchanged model stats and restored service/
lease state. These selected controls do not qualify all grammar/copy branches.
The earlier `688b74c5` 92-file GPU receipt excludes this increment. No inference worker,
RNG, reactive frontier, cache payload or dependency changes. Removing payload
transfers does not establish a measured speedup. Model/controller, private
schema/regex/template construction and broader qualification remain open.
Terminal Bench stays deferred until modifications and qualification finish.

## Owned primitive predicates

`lie/grammar_lexeme.h` exposes ABI 1 for immutable whitespace, numeric and string
predicates. C17 owns their alphabet, tagged dispatch and copied options, retaining
the existing C numeric policy or copied DFA. The ordered table retains leaf
identities across growth, range imports and independent clones. Sealing rejects
mutation and exports C-only callbacks to the byte runtime and vocabulary cache;
hot dispatch no longer calls virtual C++ predicates or stages a `std::string`.
The construction-only memo maps borrowed immutable schema identities to retained
predicates. First publication wins, matching the original compiler cache.

Defaults bound text/state at 64 MiB and table/memo entries at 262,144 with 64 MiB
direct requested storage each. Table/memo accounting includes bodies and growth
overlap; it excludes retained predicates/policies, allocator overhead, stack,
C++ projections and process/device costs. Refusals retain logical contents and
published outputs; diagnostic capacity/peak/allocation counters may advance.
Numeric query work/scratch still belongs to its C policy, including lexically
impossible long prefixes. Numeric advance appends rejected bytes; string and
whitespace rejection preserves encoded state. Canonicalization changes copied
mask keys only. Existing numeric, whitespace, UTF-8, escaping and regex semantics
remain the independently pinned Gufo algorithms.

Atomic retain requires an owned reference and refuses overflow. Final release
retires dependencies. Immutable reads may run concurrently; construction and
release require serialization and retiring borrowed grammar/hooks. Memo keys
are never dereferenced and their owners outlive compilation. No model, HTTP,
RNG, worker or persisted cache format enters this component. Reactive readiness,
output credits, cancellation and the single device-owner worker are unchanged.
More C dispatch does not establish a throughput gain.

Six guarded exact edits preserve the original OFF classes/vector/map. Existing
`LIE_C17_SAMPLING=ON` selects C ownership; C++ facades/errors and schema/regex
construction/template projections remain private glue. Request snapshots use
the later C17 ownership above.
The normal product and default CTest remain Python-free with no new dependency.
The [host receipt](validation/c17-lexeme-host-2026-10-06.json) binds independent
ownership, allocator/capacity refusal and joined-reader checks, complete
pristine/ON/OFF witnesses and the 92-file provider inventory. The matching sealed
`688b74c5` HIP build now passes 37 selected original-weight OpenAI controls in
each AR/MTP mode on `.161`
([GPU receipt](validation/c17-lexeme-point-gpu-2026-10-06.json)). This qualifies
the selected integrated paths; the host receipt keeps its original scope.
Both modes observe 44 whole-process threads, including runtime helpers, with
one device-owner worker and no added inference thread. Model/controller,
broader branches/faults/probabilities/quality/resources and matched cost remain
open. Terminal Bench stays deferred until modifications and qualification finish.

## Owned typed JSON values

`lie/json_value.h` exposes model-neutral ABI 1. C17 owns exact byte strings/keys,
ordered object and array child tables, scalar getters, cloning, transactional
replacement, parsing and serialization. Each root has an allocator/budget domain;
children are borrowed and keep stable identity across sibling insertion. Refused
operations preserve content and output handles. Moves retire source payloads only
after the destination succeeds. Ancestor move assignment refuses; copies stage
before replacing, including descendant/ancestor sources. Duplicate append keeps
order and lookup selects the first exact key; parsing still rejects duplicates.
Inactive child tables are retained only for the pinned private compatibility API.

Defaults are 64 MiB requested heap, 262,144 nodes, 512 value levels and 268,435,456
copy/output work units. Parser limits remain independently bounded at 128 levels.
Clone depth is bounded; destruction and serialization use iterative traversal.
Metrics include allocator headers, context, child tables, facade storage and growth
overlap. They exclude allocator overhead, stack, private projection allocations,
GPU and whole-process costs. No model, HTTP, RNG, runtime thread or cache format
enters this component. Concurrent immutable C reads are allowed; mutations and
release require caller synchronization and retirement of borrowers.

The default-ON adapter now uses this C17 tree directly. `gufo_json_value.hpp`
provides private references, exception translation and lazily copied `std::string`
projections required by existing callers. Projection initialization is locked;
const reads never create or mutate a C tree. These locks add no inference worker
or asynchronous model forward. The full original OFF Value/parser remain guarded
by two additional exact edits at the independently fetched Gufo pin. The normal
product and default CTest remain Python-free and gain no system dependency.

The [host receipt](validation/c17-json-value-host-2026-10-06.json) records the
independent C ownership/cleanup checks, every selected allocator/view/output
refusal, 512-level copying/retirement, complete pristine/ON/OFF value witnesses,
prior unchanged parser/sampler/grammar witnesses and private projection failure
and parallel-reader checks. The 89-file provider inventory includes 77 first-party
and 12 vendor/provenance bindings. The matching sealed `5227bf4f` HIP build now
passes 37 selected original-weight OpenAI controls in each AR/MTP mode on `.161`
([GPU receipt](validation/c17-json-value-point-gpu-2026-10-06.json)). Both modes
observe 44 whole-process threads, including runtime helpers; this component adds
no inference worker or measured speedup. Predicate/model/controller ownership,
broader numerical/fault/private-resource/quality and matched cost remain open.
Terminal Bench stays stopped/deferred until modifications and
matching qualification finish.

## Complete JSON parser

`lie/json_parse.h` exposes model-neutral ABI 1. `lie_json_parse_events` owns
single-root syntax, iterative container traversal, finite number conversion,
strict UTF-8, escapes, surrogate pairs and decoded duplicate-key detection.
The existing `lie_json_parse` tools API keeps its name and contract. The parser
emits ordered typed events; clients copy borrowed spans before their callbacks
return. On any refusal, clients discard their entire staged result. No parser
allocation survives the call, including allocator or callback refusal.

Defaults admit 128 container levels, 64 MiB each of input and owned heap payload,
and 268,435,456 lexical/key work units. Per-object hash tables retire at object
close. Unescaped strings borrow validated input; escaped strings use reusable
decoding storage. Decoded keys compare exact bytes, including NUL. Heap metrics
charge requested C allocation sizes and overlapping growth; they exclude fixed
stack storage, allocator overhead, private sink containers and device/process
memory. Work and byte budgets are admission limits, not timing measurements.

At `904774da`, the private adapter constructs Gufo's typed tree and translates
exceptions. The typed-value extraction described above moves that staging to C17.
Three exact edits at the recorded Gufo pin select C17 under default-ON
`LIE_C17_SAMPLING`, preserving the complete original parser under OFF. The parser
adds no HTTP coupling, dependency, cache-format change, RNG operation or thread.
This parser checkpoint extracts syntax/decoding; its receipt excludes the later
typed-value extraction. Model/controller and predicate ownership remain private.

The [host receipt](validation/c17-json-parser-host-2026-10-06.json) binds 1,301
independent C checks, 368 allocator refusals and 602 callback refusals. The actual
pristine/ON/OFF parser entry points agree on all 34,071 complete witnesses:
ordered trees, string/key bytes, binary64 bits, canonical dumps and exact errors.
All 25 earlier complete witness groups retain their hashes. The 18 focused
Release checks, 18 sanitizer checks and 43 full host reference checks pass;
all 56 public headers compile together in C17 and C++17. Initial fixture failures
and the public-name conflict remain recorded with their actual exits.

The matching sealed `904774da` 86-file provider/application build passes
37 unchanged original-weight OpenAI controls in each AR/MTP mode on `.161`
([GPU receipt](validation/c17-json-parser-point-gpu-2026-10-06.json)). The host
receipt retains its original host-only scope; `20777005` remains the earlier
83-file composition/codec checkpoint. These newer controls qualify selected
integrated paths; individual parser/numeric/format branches, independent
probabilities, faults, private allocation-exact resources, quality and matched
cost remain open. Both modes observe 44 whole-process threads, including runtime
helpers. No new inference thread or speedup is claimed. Terminal Bench
stays deferred until functional modifications and matching qualification finish.

## Ordered composition caches

`lie/ordered_cache.h` exposes model-neutral ABI 1. The core owns ordered lookup,
duplicate-before-eviction insertion, capacity and synchronization. With the
default 16-entry capacity, a new insertion evicts the smallest existing key;
a duplicate returns its existing program without retention or eviction.
Compilation runs outside the cache lock. This differs from the separate
compiled-schema byte-key cache, whose pinned eviction-before-duplicate policy
is preserved by `lie/grammar_cache.h`.

Keys/values are opaque retained handles. The private adapter copies the
original shared-pointer/tuple/vector keys and preserves their original
`std::less` ordering; its immutable program copies outlive cache eviction.
The C core uses a fixed entry array, with caller-selected paired allocation,
and retires evicted handles after unlock. Retain/copy/compare refusal leaves
cache and output unchanged; failed hooks retire their partial work. Keys'
private allocations and size/accounting limits remain the hooks' responsibility.
The new contract reports entries, without claiming private bytes or total
engine cost. No new inference worker, model/HTTP ownership or speedup is implied.

The source-pinned recipe replaces four exact reasoning/tool cache blocks under
default-ON `LIE_C17_SAMPLING`; OFF retains every original block. At this cache
extraction's original host checkpoint, composition stayed private and unchanged.
Independent C ownership/fault
oracles and actual pristine/ON/OFF entry-point tests qualify host behavior;
original-weight matching GPU and allocation-exact private resource/cost gates
remain open.

## Schema body control

`lie/schema_body.h` exposes model-neutral ABI 1. C17 validates schema keys and
schema depth, visits ordered `$defs`, resolves/distributes local `$ref` and
`anyOf`, validates the complete base before finite choices, and applies the
`enum/const` type, equality, character and count rules. It reuses the owned C17
normalizer through the declared callback and composes ordered rule IDs. This
replaces the remaining `VisitBody` control algorithm; it does not move private
JSON storage, scalar numerical leaves or reasoning/tool composition to C.

Immutable reader views stay borrowed. A duplicate-preserving writer supplies
short-lived copies; the keep callback copies visited schemas into stable
per-compilation storage before publishing their identities to the memo. This
preserves cached leaf lifetimes. Canonical values live until the body call
retires. Counters retain depth 16, enum/const count 1,000, global characters
120,000 and the 15,000-character bound for string enums above 250 entries.
The paired transform allocator owns alternatives beyond the 16-entry local
scratch. A refusal preserves the result; prior builder, memo, storage and count
mutations may remain, so retire the whole failed compilation. Calls are
serialized, synchronous and create no thread or device call.

Two exact `schema-body-edits.json` replacements select this path under the
existing default-ON `LIE_C17_SAMPLING` option. OFF retains the original body.
The private provider inventory contains 57 files with a separate
`schema_body_edits_sha256` binding. The
[host receipt](validation/c17-schema-body-host-2026-10-05.json) records 72
independent language/order/limit oracles, all 2,204 selected callback refusals
and all 279 selected construction allocation sites; 16 C++ exception controls
also pass. Ten Debug and ten sanitizer contracts and 35 pristine/ON/OFF checks
pass. The new witness includes 106 cases, 52 successful compilations, 112
accepted complete values and 10,660 transitions. All 19 earlier complete
witness hashes remain unchanged; 50 public headers compile in C17 and C++17.
Local CPU maximum is 94.375 C with GPU devices masked.

Subsequent [Release/cache host qualification](validation/release-cache-host-2026-10-05.json)
initializes body temporaries explicitly for strict optimized compilation and
retains assertions only in test targets. All 79 Release/79 sanitizer/35
three-arm checks pass; all 20 complete witness hashes remain unchanged.
The r17 device-free HIP provider builds, but the older application source fails
on the optimized-local warning; that run is collected and actually retired.
Corrected source now has a matching build and selected original-weight AR/MTP
gates, recorded above; broader branch/fault/resource/cost gates remain open.

Retained failures include incorrect fixture callback declarations, missing
fixture leaves, an EMPTY/CYCLE oracle mismatch and duplicate JSON input
rejected by the wire parser. Corrected opaque duplicate-value tests use the
value API. Earlier native closed-stderr SIGABRT remains undiagnosed. Individual
original-weight branches/faults and allocation-exact resource/cost remain pending.
The earlier GPU checkpoint `2359488` contains none of the newer
memo/dispatch/Visit/body code; the matching later build is recorded above. Terminal
Bench remains stopped and deferred until functional changes and qualification
finish.

## Reference identity memo

`lie/schema_memo.h` defines separate ABI 1. `src/schema_memo.c` owns the
per-compilation opaque-node identity table, lookup, assignment, bounded growth
and storage accounting. Its default limit is 262,144 entries. Node addresses
are stable borrowed identities; the C module never dereferences or retains JSON
values. A placeholder rule ID is published before visiting children, preserving
recursive reference order. This memo is separate from the compiled-schema
cache and RAM/SSD KV retention.

The table grows geometrically at a load factor no greater than one half.
Allocation refusal preserves every published key/value and capacity. Existing
keys can be reassigned without allocation at the entry limit. An unsuccessful
lookup leaves its value output untouched. Operations are caller-serialized;
allocator callbacks and output objects stay disjoint, callbacks cannot reenter,
and destruction follows retirement. `inspect` reports live C allocation bytes,
excluding borrowed JSON/rule storage and private provider allocations.

`gufo_schema_memo.hpp` only translates opaque identities, rule IDs and status/
exceptions. Three exact `schema-memo-edits.json` replacements joined the
48-file provider inventory and `schema_memo_edits_sha256` build binding under
default-ON `LIE_C17_SAMPLING`; OFF keeps the original `std::map` body. The
visitor and its empty-branch behavior retain their order. Visit sequencing now
uses the separate C17 module below; body control uses the C17 module above.
Binary-double leaf policy and private composition/model/controller
storage remain transitional. Shared worker/event/RNG and DS4 persisted formats
are unchanged.

The [host receipt](validation/c17-schema-memo-host-2026-10-05.json) records
1,085,705 independent identity/value checks, all fourteen owned allocation
sites, 32 complete recursive-reference cases / 1,706 transitions, seven Debug
and seven sanitizer contracts, plus 32 pristine/ON/OFF tests. All sixteen prior
complete witness hashes stay unchanged. All 47 public headers compile as both
C17 and C++17. Matching selected GPU controls are recorded above;
individual branch/fault/resource/cost gates remain pending. The stopped Core-19 GPU run
used frozen source `2359488` and did not include this memo slice. Terminal Bench
is deferred until functional modifications and their qualification finish.

## Schema type and ordered branch dispatch

`lie/schema_dispatch.h` defines a borrowed ABI-1 plan with one type or a
nullable pair. The C17 module validates type-array shape, keyword/type
compatibility in source order and selects object, array, bounded integer,
numeric/string lexeme or primitive routes. It retains unknown type names for
the existing primitive/finite-value policy, preserving diagnostic order.
Readers supply immutable node/name views; output plans remain untouched on
refusal. Classification allocates nothing and uses the existing counted work
budget. Keys, schema depth and reference/finite-value orchestration have their
separate contracts.

C17 invokes leaf callbacks in type order and composes their rule IDs through
the shared builder. Successful callbacks write IDs in that same private builder;
they do not retain views or throw. Earlier successful child/builder mutations
may remain after refusal, so retire staging rather than reuse it. The adapter
translates borrowed JSON views, selected route callbacks and exceptions.
VisitBody definitions, references, anyOf and finite-choice orchestration,
binary-double leaf policy and private composition remain transitional.

Three exact `schema-dispatch-edits.json` replacements join the 51-file owned
provider inventory and `schema_dispatch_edits_sha256` binding. The existing
default-ON `LIE_C17_SAMPLING` retains the exact original OFF bodies. No worker,
event, RNG, engine or DS4 RAM/SSD layout changes. The stopped Core-19 GPU run
used frozen `2359488` and included neither this dispatch nor the newer memo.
Matching selected GPU controls are recorded above. Original-weight individual
branch/fault/resource/cost and broader autonomous sampler acceptance remain pending.

The [host receipt](validation/c17-schema-dispatch-host-2026-10-05.json) records
12,936 independent C oracles, reader/leaf/builder-allocation refusal and
complete type/nullable/context states against independently pinned Gufo and
OFF. The corrected fixture nests its tested types in a valid object root and
checks real compilation/acceptance counts; the weak initial root-only witness
is preserved as inadequate evidence. All prior complete witness hashes stay
unchanged; 48 public headers compile as C17 and C++17.

## Recursive Visit sequencing

`lie/schema_visit.h` defines ABI 1 for a caller-owned memo/builder pair and a
synchronous body callback. The C17 sequence first checks opaque identity. A hit
returns the existing rule without invoking the body or checking schema depth.
A miss reserves a rule and publishes its placeholder before visiting children,
preserving recursive references. A successful body supplies a builder symbol;
an EMPTY body commits an empty rule and returns its ID. Shared finalization
decides productivity and cycles. The visitor allocates through the existing
memo and builder and introduces no separate allocation, thread or device call.

Body callbacks retain schema-specific recursion, depth/work policy and borrowed
diagnostics. Failure leaves the result unchanged but can leave private
placeholders or children; retire the entire compilation pair after refusal.
Calls are serialized; node identities stay immutable and alive throughout
compilation, and destruction waits for callbacks to finish. Callback exceptions
remain in `gufo_schema_visit.hpp`: ordinary exceptions are rethrown after the
C return, while `JsonSchemaEmpty` becomes the intentional empty-body status.
Failure committing that empty body still propagates from the builder.

Two exact `schema-visit-edits.json` replacements and the build receipt's
`schema_visit_edits_sha256` bind the default-ON path and exact original OFF
body. The owned provider inventory now has 54 files; 49 public headers compile
as C17 and C++17. Worker/event/RNG, model and DS4 RAM/SSD contracts are unchanged.
Definitions, references, anyOf and finite-choice body policy now use the separate
C17 module above. Binary-double leaves and private model/controller/composition
remain C++.

The [host receipt](validation/c17-schema-visit-host-2026-10-05.json) records
independent publication, recursion, empty/cycle, identity-hit and refusal
oracles. Its 112 three-arm cases include first visits at invalid depth and hits
at depth17/SIZE_MAX: 61 compilations, 156 accepted values and 7,503 complete
transitions agree. All eighteen prior witness hashes remain unchanged.
Matching selected GPU controls are recorded above; original-weight individual
branch/fault/resource/cost qualification remains pending. Terminal Bench stays deferred.

## Compiled-schema cache

`lie/grammar_cache.h` defines separate ABI 1; `src/grammar_cache.c` owns ordered
copied byte keys, bounded entries, lookup/insertion, mutex synchronization and
retirement. Defaults are 16 entries and 2 MiB per key. Values are opaque retained
handles with caller-provided retain/copy/release hooks. The cache performs no
schema compilation, model forward, HTTP operation or worker scheduling.

The private adapter only copies `shared_ptr` handles and translates errors.
`JsonConstraint::Compile` checks the key, queries the cache, compiles outside its
lock and inserts the result. A hit allocates no holder. Successful insertion
preserves the pinned Gufo policy: at capacity, evict the lexicographically
smallest key before resolving a duplicate. A surviving duplicate returns the
old program and leaves one fewer entry; replacing the smallest key installs the
new program. This is ordered eviction, not an LRU policy.

Allocation/hook refusal preserves published output and resident entries.
Insertion prepares its key/holder/output before eviction; the transient footprint
can include one extra key and value handle. Removed entries retire after unlock,
so release hooks/allocators must support concurrent calls. Retain/copy run under
the lock and must not throw or reenter it. Destruction requires all calls retired;
client-owned copies remain valid across eviction. Key accounting excludes opaque
value allocations and is not whole-process memory accounting.

This is a compiled-grammar cache, separate from RAM/SSD KV and prefix retention.
The existing default-ON `LIE_C17_SAMPLING` selects it; OFF preserves the exact
original compilation-cache body. Two exact edits and `grammar_cache_edits_sha256`
join the 45-file provider inventory. The
[host receipt](validation/c17-grammar-cache-host-2026-10-05.json) binds policy,
concurrency, real private-holder failure, C refusals and unchanged earlier
pristine/ON/OFF witnesses. A matching `2359488` provider/application rebuild
passes selected original-weight AR37/MTP37 controls
([GPU receipt](validation/c17-finite-cache-point-gpu-2026-10-05.json)).
Individual branches, faults, allocation-exact resources and matched cost remain
pending. That frozen build excludes the newer reference memo. Schema
VisitBody and private reasoning/tool composition caches remain
transitional; the per-compilation memo and Visit sequencing use C17 above.
Shared reactive execution and RNG are unchanged.

## Request history

`include/lie/sampling_history.h` and `src/sampling_history.c` own the bounded
prompt tail, sorted unique penalties, boolean repetition flags and committed
generated-token counts. Prompt tokens never increase frequency/presence counts;
accepted generated tokens count even after leaving the repetition window.
Reset clears those counts, and independent copying changes neither RNG nor grammar.

The caller owns storage and enforces growth budgets. Options remain fixed until
reset; borrowed inputs must be disjoint from workspace allocations. Refusals,
including overflow and growth failure, preserve published entries/counts, while
capacity and unpublished scratch may grow. Single-token acceptance stages no
scratch. Bulk generation stages at most the input count; repetition-only input
stages just the retained tail. No memory allocation, device call, retained input
pointer or inference thread belongs to the C module.

The provider's `SamplerState` keeps the same vector layout in ON/OFF builds.
The exact `history-sampling-edits.json` recipe routes construction, reset,
acceptance and free-distribution history through C; its glue only grows live
vector entries, shrinks unpublished scratch and translates errors. Grammar is
staged before acceptance and published after C success. Free distributions do
not acquire entropy merely to construct penalty counts. Numerical forward,
schema compilation, provider container storage
and speculative model/controller
state remain transitional.

Host qualification passes 14,400 independent FIFO/count transitions, refusal,
copy and overflow fixtures, 1,728 complete history transitions across 48 profiles,
and the existing complete numerical/MTP/grammar witnesses against pristine Gufo
and OFF. Seventeen Debug and seventeen sanitizer shared-contract checks, fifteen
sanitizer reference-project checks and 33 public C++ headers pass. The unsupported
root-schema fixture and the sandbox LeakSanitizer failures are retained in the
[receipt](validation/c17-history-host-2026-10-05.json). Original-weight GPU
continuation, allocation-exact resources and matched cost remain unqualified;
earlier dense-selector GPU receipts do not cover this source increment.

## Ordered distributions and MTP probabilities

`lie/sampling_distribution.h` adds model-neutral ABI 1 for caller-owned ranked
rows, sparse draft masses and exact proposals. `src/sampling_distribution.c`
owns normalization, duplicate-key rejection, deterministic ranking/lookup,
compact penalty mapping, p-q residual correction and discrete host MTP
proposal/verification arithmetic. The core and native clients can use it without
HTTP, Gufo types, model weights or device calls.

The ranked path preserves the pinned free/compact algorithm, including its
second normalization and filter rounding. It is distinct from the dense linear
fast path. Compact output IDs index the logits; proposal creation remaps them to
raw model token IDs. Dense bias remains a dense target operation; compact
sampling retains the pinned bias-free behavior. Compiled grammar can mask the
borrowed logits before these operations; mask generation still uses the
transitional vocabulary trie/cache with the owned byte runtime described below.

Sparse repeated IDs accumulate in original occurrence order. Residual rows keep
target order and fall back to the target when p-q has no positive mass. Ordinary
singleton draws consume no RNG. Proposals quantize to F32 integer masses summing
to 2^24, assign the rounding remainder to their first entry, and always consume
one draw, including singletons. Verification validates masses before constructing
the target, draws once for acceptance, and draws the residual only on rejection.
Resource or malformed-input refusal preserves the published result and RNG.
History, rollback, stop handling and deferred corrections keep their existing
inference-controller ownership.

All storage and growth budgets belong to the caller; no allocator, retained
pointer, inference thread or device call belongs to this module. Borrowed sources
must be disjoint from mutable workspaces/output, and growth must preserve them.
The exact `distribution-sampling-edits.json` recipe selects C17 by default and
compiles the legacy numerical helpers only for OFF. Provider receipts bind all
twelve sampling/grammar source/header/glue files and all four extraction recipes.

Independent C oracles cover 2,048 residual draws and 768 proposal/verification
draws, plus mapped penalties, zero/duplicate/nonfinite masses, buffer aliasing,
first/second growth refusal and unchanged RNG/output on refusal. Complete host
witnesses compare compact/target FP64 rows, F32 proposals, token decisions and
RNG states against pristine Gufo and OFF across 1,728 profiles and 6,912 MTP
decisions, with additional raw residual and grammar-masked cases. Qualification
and limits are recorded in the
[source-bound receipt](validation/c17-distribution-host-2026-10-05.json).
Original-weight GPU continuation, resource fit and matched performance remain
pending; existing dense-selector GPU receipts do not qualify this increment.

## Byte grammar and logit masking

`lie/grammar.h` adds model-neutral ABI 1; `src/grammar.c` owns immutable compiled
tables and bounded byte-state snapshots. C17 expands rule alternatives, handles
terminal/lexeme branches, preserves complete-and-prefix continuations, sorts and
deduplicates full stacks/encoded lexemes, and computes completion and canonical
cache-key states. Applying an already resolved token mask to dense/compact
logits is also C17, retaining allowed NaN/Inf bits and refusing bad IDs or overlap
before output mutation. UTF-8 and JSON escapes may span token boundaries.

Programs deep-copy rule/sequence/symbol/terminal tables; source mutation cannot
change them. They borrow immutable predicate and allocator contexts whose owner
must outlive all program/state uses. Snapshots own their frame data and callers
release them explicitly. Paired allocation hooks support fault injection; NULL
hooks select malloc/free. Default limits retain Gufo's 8,192 states, 16,384 stack
symbols and 2,000,000 expansion operations, with 4,160 bytes of primitive scratch.
Refusal preserves caller inputs and output ownership; an empty state denotes a
dead language prefix rather than a resource failure. This module allocates
bounded state/table storage and creates no thread, RNG, model or device operation.

The provider seals an independent C program after schema compilation and after
reasoning/tool composition, binding callbacks to the composed grammar's own
immutable primitive list. ON/OFF provider layouts agree, but private grammar
layout/source changes require a matching provider/application rebuild. The
`grammar-runtime-edits.json` recipe routes expansion, start, byte advance,
completion, canonicalization and logit masking to C; OFF retains Gufo's runtime.
Storage/error/predicate translation stays in `gufo_grammar.hpp`.

This is a byte-runtime extraction, not a complete C grammar compiler. JSON
Schema compilation remains delegated; the later Unicode-context section
describes the C17 set registry/input buffers and retained ICU dependency. Vocabulary/transition/cache and expression/DFA compiler ownership are
described in their sections below.
The snapshot bridge below now owns import/export planning, validation and copies
in C17. Provider vector/string storage stays private translation; its measured
whole-provider cost and original-weight continuation remain open.
The direct Gufo reference now selects legacy byte-grammar methods as well as
legacy sampler methods before the shared archive; inline model/controller
arithmetic remains shared. New GPU compilation/continuation/performance gates
must validate that reference composition; host checks do not qualify it.

Independent C checks cover 134,402 byte transitions, every construction/start/
advance allocation refusing without leaks, bounded cycles/state/stack expansion,
immutable tables, prefix-and-complete primitives, canonical clone independence
and bit-preserving dense/mapped masks. Complete pristine/ON/OFF witnesses cover
20 grammars, 23 texts, 13,700 byte transitions and 7,089 masks, including Unicode,
recursive schemas, numeric/string constraints, reasoning and tool composition.
Final 19 Debug, 19 sanitizer, 17 host-reference checks and 35 public headers pass.
[Executed commands, source and complete witnesses](validation/c17-grammar-runtime-host-2026-10-05.json)
retain their host-only limits. Original-weight AR/MTP/structured-tool continuation,
allocation-exact resources and matched cost remain pending on `.161`.

## Exact-decimal numeric grammar

`lie/grammar_number.h` adds model-neutral ABI 1. `src/grammar_number.c` owns
canonical decimal parsing/comparison, exact long division/product, strongest
inclusive/exclusive bounds, empty interval/grid refusal, integer `multipleOf`
reduction, prefix interval intersection and exact LCM for combined `multipleOf`.
It preserves the pinned ordering of interval checks before integer-grid reduction.
Plain runtime prefixes retain the 4096-byte scalar budget and 1024 integer shifts;
complete JSON values additionally admit exponent spelling. Negative zero and
trailing decimal zeros normalize exactly. No binary floating-point remainder
participates in divisibility or LCM.

Policies copy all supplied values; calls own/release bounded arithmetic scratch.
Allocator hooks support failure injection and caller-synchronized sharing.
On the measured x86_64 host a policy occupies 24,680 bytes and each call
allocates/retires 114,856 bytes of arithmetic scratch; digit copies touch only
the live prefix. These fixed capacities do not constitute measured GPU cost.
Resource/work refusal preserves output ownership and matches. The header declares
explicit decimal/exponent/digit/work limits; bounded workspace cost remains a GPU
acceptance gate. No HTTP/model/device operation, RNG or inference thread belongs
to this component. Numeric leaf control and representability now use the
separate modules below, including the shared binary64 codec. Typed exceptions
remain private; provider container/model/controller storage still needs
extraction within the same task. The
Unicode registry/input context below now uses public ICU C APIs.

The four exact `grammar-number-edits.json` edits select C17 by the existing
`LIE_C17_SAMPLING=ON` default and retain the legacy numeric implementation with
OFF. The provider receipt now binds 21 C sampling/grammar source/header/glue files
and all extraction recipes; archive/application rebuilds are mandatory. The direct
Gufo reference also compiles legacy numeric predicates before the shared archive.
This source composition still requires admitted original-weight qualification.

[Source-bound host commands and witnesses](validation/c17-grammar-number-host-2026-10-05.json)
record independent rational/LCM oracles, pristine/ON/OFF complete prefix/value/LCM
comparisons, failures and temperatures. These are synthetic host checks;
original-weight AR/MTP/tool/grammar continuation, resources and matched cost
remain unqualified on `.161`.

## Numeric schema leaf control

`lie/schema_number.h` adds model-neutral ABI 1. Its C17 implementation reads
`minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum` and `multipleOf`
in pinned order, validates finite/positive values, prepares copied exact-decimal
policies, selects scalar acceptance and checks that the combined LCM survives
binary64 conversion exactly. Numeric finite-value literals publish rule IDs
through the C17 builder. Non-numeric acceptance remains a successful false;
refusals preserve output arguments and retire temporary arithmetic workspaces.
The added `lie_number_equal_with_allocator` keeps the original comparison API
and lets these calls share the declared paired allocator.

The private adapter supplies borrowed views, callbacks to the shared C17
binary64 codec and typed exception translation. It holds only an exception
pointer and no staging container. A separate untimed probe records zero C++
heap allocations for selected bridge construction/acceptance/small-LCM/literal
paths. C arithmetic workspaces are separate; this is not allocation-exact
whole-engine qualification or a performance measurement. The later C17
codec and composition increments are host-qualified; typed storage/model/controller
remain private. No worker/event/RNG, DS4 RAM/SSD layout or inference thread changes.

The [host receipt](validation/c17-schema-number-host-2026-10-06.json) records
65 independent control/literal oracles, 22 callback refusals, nine selected
allocation refusals, four typed C++ callback exceptions and 578 complete
pristine/ON/OFF numeric cases. The 20 earlier complete witness hashes remain
unchanged. All 51 public headers compile as C17/C++17, and the provider binds
60 owned files. Release and ASan/UBSan/LSan tests retain assertions; strict
optimized C warnings remain errors. Initial failed Release/provider checks
are preserved with their actual exit codes. A matching new GPU build and
original-weight gates remain pending. Terminal Bench stays deferred until
functional modifications and matching qualification finish.

## JSON binary64 codec

`lie/binary64.h` exposes separate ABI 1 with no model, HTTP, C++ container or
allocator type. Formatting writes no NUL and matches the pinned provider's
shortest default spelling, including fixed/scientific selection, exact closest
integer spelling, signed exponents and negative zero. Parsing validates the
entire JSON number span, with optional JSON whitespace, and rounds to nearest
with ties to even. Nonfinite overflow and nonzero underflow to zero refuse.
Refusal preserves bytes/length/value; output must be disjoint from inputs.

The bundled [Ryu provenance](../../third_party/ryu-source.json) fixes eleven
unchanged C/header/license files to `4c0618b0e44f7ef027ebae05d2cc7812048f7c8f`.
BSL-1.0 is selected and both upstream license alternatives are retained. The
short parser receives at most 17 significant digits; the independently written
exact fallback uses bounded base-2 integer workspaces, 800 significant decimal
digits and a sticky tail. Binary64 rounding midpoints have at most 768 significant
decimal digits, so later nonzero input still resolves exact ties. No locale or
floating-environment change, mutable cache or heap allocation occurs in the
public formatter/parser. Defaults admit at most UINT32_MAX text bytes and
64 million counted work units; these are refusal limits, not timings.

The [host receipt](validation/c17-binary64-host-2026-10-06.json) binds independent
bit/rounding and refusal fixtures, all four floating rounding modes, all 55 C17/
C++17 public headers, 106,273 actual pristine/ON/OFF JSON cases and all 24 earlier
unchanged witness hashes. The independent QA probe combines installed MPFR
decimal comparisons with shortest-spelling/bit roundtrips: 1,013,356 checks in
total, including exact subnormal midpoint tails. It observes
zero allocator calls while selected public codec calls execute. It is QA-only:
MPFR/GMP are required only by the optional `tests/sampling` developer project,
not by ordinary core/server/bench/default CTest. The codec object still contains
Ryu's unused allocating convenience entry point; its malloc import does not
describe the tested public paths. The later typed-value extraction above owns
JSON storage; immutable predicates and model/controller remain private. The matching composition/codec
build passes the selected original-weight AR/MTP controls above; individual
branches/faults/resources/cost and SSD BPE gates remain pending. No inference
speedup is claimed.

## Pinned string format expansion

`lie/schema_format.h` adds ABI 1. Its C17 implementation selects `date`, `time`,
`date-time`, `uuid`, `ipv4`, `ipv6`, `hostname`, `email` and `duration`, retains
the pinned patterns and constructs IPv6 alternatives in original order.
Construction uses bounded stack scratch without a heap or global cache.
Pattern publication is transactional, validates input/output overlap and writes
no NUL. Schema expansion uses the existing copied-span writer contract and
adds hostname `maxLength:253`. Callers retire private staging on any refusal;
no scratch view escapes. Input/error/output and budget rules are in the header.

The private adapter supplies strings/JSON staging and typed errors. Three
`schema-format-edits.json` replacements select C17 under default-ON sampling
and preserve exact original OFF bodies. `SchemaArena` also routes conjunction
format hooks directly through the C function. No worker/event/RNG/state layout,
model or inference thread changes. This preserves the original format repertoire
and limitations; it does not claim all JSON Schema formats or broader RFC coverage.

The [host receipt](validation/c17-schema-format-host-2026-10-06.json) binds 89
independent publication/capacity/budget oracles, all 29 selected writer refusals,
exact nine-format schemas, 45 language examples, 616 prefix decisions and 81
format conjunctions. All 21 earlier complete witnesses keep their hashes.
Strict optimized C and all 52 C17/C++17 public headers pass. Provider inventory
is 63 files with recipe hash/missing/drift rejection. Initial synthetic-recipe
fixture failures are retained. Matching original-weight GPU qualification,
private staging allocation-exact resources and matched cost remain pending.
Later host-qualified increments extract the codec/composition; typed storage/model/controller remain private.
Terminal Bench remains deferred until functional changes and qualification finish.

## String and Unicode-DFA runtime

`lie/grammar_regex.h` and `src/grammar_regex.c` own immutable copied Unicode
classes, raw DFA tables and accepting flags. C17 builds sorted unique successor
and predecessor graphs, computes shortest accepting distances, prunes unreachable
edges and derives maximum suffix. Runtime range lookup, exact length reachability
and Brent cycle skipping are C17. This is a real DFA runtime extraction; the
Unicode property/set/conversion semantics remain supplied by ICU; the C17
context described below owns the registry/input storage through its C API. Syntax, expression
derivatives and class partitioning now use the C17 compiler described below.
Default budgets retain 4096 states and 262144 transitions/ranges; 256 million
counted work units explicitly bound construction and queries. Constructor scratch
is retired; queries allocate at most 12 bytes per state, only when their minimum
requires reachability beyond the shortest accepting distance. No global cache or
inference worker is introduced. Caller allocator contexts outlive programs/queries.

`lie/grammar_string.h` and `src/grammar_string.c` own UTF8 validity, ASCII and JSON
escapes, surrogate pairs, decoded length, pending scalar ranges, completion and
mask-key canonicalization. Immutable caller-owned policies borrow a DFA. The
`scalar_only` flag is a compiler assertion for an unconstrained scalar language;
it must not bypass a restrictive DFA. State retains the five native uint32 fields
DFA/count/value/extra/mode, exactly 20 bytes; it is not a persisted endian format.
Refused byte transitions preserve encoded state, and allocation/work/capacity
refusals also preserve outputs. Closing quote changes only completion. Canonical
count reduction applies to a copied mask key, leaving the live request intact.
Formatting whitespace retains the 32-byte budget through a separate C predicate.

Eleven exact regex edits and three string/whitespace edits preserve the existing
default-ON/OFF selection and matching provider/application builds. JSON options,
formats, regex compilation and storage/exception translation remain in the
adapter. C copies and seals the graph, then the adapter retires the temporary C++
state/alphabet vectors. The direct legacy reference also compiles regex methods
before the shared archive. The 21-file inventory and both recipes require a new
source-bound provider build; frozen GPU receipts do not qualify this increment.

[Complete host evidence](validation/c17-grammar-unicode-host-2026-10-05.json)
compares every encoded state and canonical key across pristine/ON/OFF, alongside
independent finite-language and Unicode spelling oracles, allocator/budget faults,
malformed states and existing complete numerical/grammar witnesses. These checks
perform no model forward. Remaining schema/set/property compilation and
snapshot marshalling, original-weight AR/MTP/tool continuation, allocation-exact
resources and matched cost remain open on `.161`.

## Vocabulary trie, transition interning and mask cache

`lie/grammar_vocabulary.h` adds model-neutral ABI 1. C17 owns copied token bytes,
stop flags and an insertion-ordered immutable trie. Empty and stop pieces never
enter the trie. Limits retain 1,048,576 tokens, 64 MiB total text, 4096 bytes per
non-stop token and four million nodes. The provider retires temporary C++ pieces
and trie vectors once C storage is sealed.

Mask traversal is iterative, with scratch depth bounded by token length. Exact
C snapshot hashing/comparison interns reached states; hash buckets grow with
actual occupancy, and 256-entry transition tables allocate only when used.
The 8192-state limit bounds an optimization, not the language: new states beyond
it take the direct path. Noncacheable numeric predicates also take that path.
A query can disable interning without changing masks. The work budget counts
at most two million visited trie nodes; allocation/work refusals preserve output
and stats. Token acceptance operates on owned C byte pieces and C snapshots.

The shared cache owns copied canonical C state keys and opaque retained mask
snapshots. The provider supplies mutex and vector/shared_ptr lifetime translation;
C owns lookup, duplicate publication and lexical eviction. Its 16-entry policy
preserves the reference's eviction-before-insertion behavior, including raced
duplicates. Mask computation happens outside the lock. Publishing consumes the
incoming snapshot only on success; a refused key copy changes neither cache nor
caller ownership. Live request counts are never reduced by key canonicalization.

Ten exact provider edits use the existing default-ON/OFF selection. The strict
receipt binds 24 C source/header/glue files and the new vocabulary recipe; both
provider archive and application must rebuild together. No model geometry,
thread, device, RNG, HTTP or persisted KV format enters this module.

[Complete host commands and witnesses](validation/c17-grammar-vocabulary-host-2026-10-05.json)
cover independent byte languages, every allocation refusal, direct/cached/full
interning, 4096-byte paths, cache order/races and retained snapshots. Pristine,
ON and OFF arms compare every token mask and accepted encoded state, including
Unicode fragments, numeric and tool/reasoning branches. These are synthetic
host checks. Remaining schema/set/property compilation and provider snapshot
marshalling, new
original-weight AR/MTP continuation, allocation-exact resources and matched GPU
cost remain open on `.161`.

## Regex expression and DFA compilation

`lie/grammar_regex_compile.h` and `src/grammar_regex_compile.c` own model-neutral
compiler ABI 1. Callers supply copied scalar classes and expression operations;
C17 interns immutable expression DAGs, normalizes union/intersection/concatenation
and repetitions, and precomputes nullable results for eight assertion contexts.
Memoized derivatives use an explicit heap stack. Unicode membership partitioning
and BFS state construction retain the pinned provider's insertion/state order.
Seal copies an immutable runtime program and retires all temporary graph tables.
Published programs survive compiler release.

Default limits are 32,768 expressions, 1,048,576 derivatives, 4,096 states,
262,144 transitions/ranges and 256 million counted work units. Refusals preserve
outputs and previously published programs; successful internal memo entries may
remain after a refused operation. Paired fresh aligned allocator hooks outlive
the compiler and published programs. Construction is caller-synchronized and
creates no inference thread, RNG, device call or HTTP operation.

`gufo_grammar_regex_compile.hpp` retains C context RAII, normalized operation
and exception translation. Syntax/assertion expansion now use C17; the Unicode
context below preserves insertion-ordered full-set identity through ICU C APIs.
JSON Schema compilation and provider container storage remain open. The three exact `grammar-compiler-edits.json` edits select the C
compiler with default ON; OFF keeps the entire original compiler. The current
45-file provider inventory and recipes require matching archive/application
rebuilds. Provider snapshot marshalling remains separate work.

[Source-bound host evidence](validation/c17-grammar-compiler-host-2026-10-05.json)
records independent finite-language, all-scalar, allocator/refusal, eight-context
and deep-DAG tests without a model. Source-pinned pristine/ON/OFF
witnesses compare state IDs, Unicode transitions, acceptance, length queries,
suffix bounds and refusals. These checks do not establish original-weight
continuation, GPU memory fit, allocation-exact provider cost or a speedup.

## Regex syntax and assertion expansion

`lie/grammar_regex_parse.h` and `src/grammar_regex_parse.c` own parser ABI 1.
The C17 implementation parses groups, alternatives, repetitions, anchors,
lookaheads, word boundaries, character classes and escapes. It builds a bounded
AST and expands assertions into the owned expression compiler with an explicit
heap stack. Group parsing retains the source's 32-level bound; input retains
the 16,384-byte limit. Default AST/work budgets are 65,536 nodes and 32 million
counted units. Refusals preserve the root and published programs; successful
internal expression entries may remain after a refused parse.

UTF16 input and model-neutral opaque Unicode-set callbacks are borrowed for one
synchronous call. Fresh set handles and all AST/expansion storage retire on
every path. `gufo_grammar_regex_parse.hpp` now keeps a synchronous borrowed
input view and status-to-exception translation. The C17 Unicode context below
owns decoding buffers and full-set registry through ICU C APIs. The JSON Schema
compiler and provider container storage still need extraction. No upstream type enters the public C header. No inference worker,
RNG, device call, HTTP operation or DS4 RAM/SSD state is added.

Two exact `grammar-parser-edits.json` edits select the C17 parser with default
ON; OFF retains the original syntax/expansion implementation. The 45-file
provider inventory and recipes require matching source/archive/application
builds. [Host evidence](validation/c17-grammar-parser-host-2026-10-05.json)
records independent C language/refusal/allocator tests and pristine/ON/OFF
syntax/state witnesses are host evidence, without a model. Original-weight
AR/MTP/tool continuation, fault/fit, allocation-exact resources and cost remain
separate GPU gates.

## Unicode-set registry and input

`lie/grammar_unicode.h` and `src/grammar_unicode.c` add a reusable C17 context,
with no ICU or provider type in its public header. The context owns its compiler,
insertion-ordered full-set registry, private copied sets, scalar-range translation,
temporary handles and UTF8/UTF16 input storage. Full set identity includes string
members even when two sets have identical scalar ranges; scalar publication
removes surrogate ranges. Sealed programs survive context release. Only the
context publishes compiler classes; callers may build expressions, query and seal
through the borrowed compiler. Construction is synchronous and caller-serialized.

The implementation calls the public [ICU set API](https://unicode-org.github.io/icu-docs/apidoc/released/icu4c/uset_8h.html)
and [replacement conversion API](https://unicode-org.github.io/icu-docs/apidoc/released/icu4c/ustring_8h.html).
ICU remains the actual property/set/conversion dependency with its C/C++
implementation. These algorithms and databases have not been reimplemented or
removed. Input keeps the 16,384-byte limit, explicit NUL lengths and U+FFFD
replacement behavior. Capacity/overlap/input refusals preserve destination and
length. Own allocator hooks cover context, handles, registry arrays, range/input
buffers and compiler storage; parser hooks independently govern AST storage.
They do not cover ICU's internal allocator. C set mutators do not expose complete
internal OOM detection, so ICU-internal fault qualification remains open.

The provider glue now supplies context RAII, a synchronous borrowed input view,
exception and enum translation. `LIE_C17_SAMPLING` selects this path by default;
OFF retains the pinned C++ path. `LIE_UNICODE_ICU=ON` builds the standalone C
module by default; a minimal core can omit it with OFF. A C17 provider build
requires ICU. The 45-file private inventory and changed compiler/parser/build
recipes require a new matching sealed provider/application rebuild.

[Host evidence](validation/c17-grammar-uset-host-2026-10-05.json) records 26 Debug,
26 ASan/UBSan/LeakSanitizer, 25 pristine/ON/OFF and 5 minimal-core OFF checks,
42 public headers and strict C17/symbol checks. There are 84 explicit language
oracles and 123 owned allocator refusal points. The requested-payload fixture
peak is 15,042 bytes, excluding allocator headers and ICU/provider/GPU storage.
The complete comparison records 1,181,953 decodings: every scalar, every one/two
byte sequence, empty input and 4,096 deterministic arbitrary byte strings.
It also records 38 full-set mutation/identity operations. All eleven previous
complete witness hashes remain unchanged. Two initial fixture failures are
retained: an isolated surrogate escape was incorrectly expected to compile;
the final fixture checks its refusal and uses the supported braced form for the
empty scalar class. No implementation refusal or assertion was removed.

The provider source-list check also detects the previously combined compiler/
parser filename; that recipe is corrected, without claiming a GPU build.
JSON Schema compilation and provider container storage remain open, as do
original-weight continuation/fault/fit, allocation-exact resources and matched
cost. This adds no inference worker or metric and changes no DS4 RAM/SSD format.

## Snapshot read/write bridge

The additive snapshot ABI 1 in `lie/grammar.h` moves provider snapshot traversal,
import construction, writable-span planning, overlap checks, payload copies and
temporary lifetimes into C17. Reader callbacks supply borrowed typed frame views,
valid until the next callback or completion. C immediately copies them into an
owned snapshot and retires partial construction on every refusal. Export plans
all destinations before writing any payload, validates capacities and rejects
input/output/plan overlap. A bounded heap sort checks intervals using the state
work budget; default frame/stack/lexeme limits remain 8192/16384/4160.

Writer callbacks allocate private staging containers. Successful writable views
remain valid until completion. Capacity/storage may change on refusal; the caller
publishes only after OK and retires staging on every
failure. `gufo_grammar.hpp` now supplies container views, resize/allocation and
nonthrowing exception translation. It no longer constructs a C++ descriptor
array, walks exported frames or copies their payloads. Provider `State` remains
the existing vector of symbol vectors and strings, preserving private ON/OFF
layout and the current direct-reference composition. Those containers and model/
controller storage remain transitional; this is not complete C++ dependency or
model-executor removal. No callback or input pointer is retained.

[Source-bound host evidence](validation/c17-grammar-snapshot-host-2026-10-05.json)
records 27 Debug and 27 sanitizer shared-contract tests, 28 pristine/ON/OFF
checks, plus final 2 Debug/2 sanitizer contract checks after adding the maximum
frame case. There are 2080 explicit ordered-frame roundtrip oracles, 8192 maximum-
frame copies, 36 owned C allocation refusal points, 17 callback refusals and four
capacity/NULL/output-output/cross-input overlap cases. All 84 actual C++ staging
allocation points refuse cleanly in both candidate and fallback fixtures, leaving
the source hash unchanged. The complete three-arm witness preserves all payloads
for 65 snapshots/2080 frames, including NUL/arbitrary bytes and independent
copy/source/program-release lifetimes. All twelve earlier full witness hashes
remain unchanged. Three minimal-core checks with ICU OFF also pass. All 42 public
headers and strict C17/symbol checks pass; local CPU maximum is 90.5 C.

The 45-file inventory and changed runtime recipe/glue require matching sealed
provider/application rebuilds. Worker/events, RNG, request/executor/generation
and DS4 RAM/SSD layouts remain unchanged. These synthetic tests are not new
original-weight AR/MTP/tool/grammar continuation, GPU fault/fit, allocation-exact
whole-provider resources or matched performance qualification. Export adds
bounded transient planning storage; no speedup is claimed. Schema traversal,
reference/conjunction and finite-value normalization remain grammar responsibilities.

## JSON Schema conjunction and reference resolution

`lie/schema_transform.h` defines model-neutral ABI 1 over synchronous borrowed
JSON views and a private caller-owned staging arena. `src/schema_transform.c`
owns structural equality (numeric equality, ordered arrays and order-independent
objects), local JSON pointer decoding/index traversal, supported-key validation
and the complete conjunction algorithm. This includes reference expansion,
distribution over `anyOf`, bounds, enum intersection, required-field union,
number/integer type intersection, pattern conjunction, nested items/properties
and closed-object filtering. Equality uses an iterative stack with sixteen
inline pairs and bounded heap growth; conjunction retains the pinned 64-level
reference budget. The default work budget is 64 million counted units.

The C contract borrows stable nodes and spans for the complete call. Writers
copy supplied spans into private staging; input objects have unique ordered
keys and remain immutable. Refusal preserves the result argument; all staging
retires on either outcome. Paired allocator hooks cover C equality/pointer/
pattern scratch. They do not cover private provider containers or ICU.
Callbacks do not retain scratch, cross the C boundary with an exception, own
inference state or add a worker.

`gufo_schema_transform.hpp` supplies typed views, deque staging and exception
translation. Format expansion and binary-double `multipleOf` translation remain
leaf policy in the provider; they do not perform C traversal or merging. The
default-ON sampler selection uses five exact `schema-transform-edits.json`
replacements; OFF retains original function bodies. The 45-file sealed inventory
requires matching provider/application builds. Schema dispatch and model/controller storage remain transitional;
finite-value/container algorithms and the compiled-schema cache now use C17. A conjunction helper is not full schema admission.

The [host receipt](validation/c17-schema-transform-host-2026-10-05.json)
records independent ordered-tree/boundary/refusal oracles and complete pristine/
ON/OFF transformation witnesses, including malformed inputs, JSON pointer
escapes/indices, object order and unchanged source values. New original-weight
AR/MTP/tools/grammar continuation, allocation-exact resources and measured cost
remain open. These host witnesses do not qualify an autonomous C model executor
or a reactive speedup.

## Finite values and container rules

`lie/schema_values.h` defines a separate model-neutral ABI 1 over the shared
stable borrowed JSON views. `src/schema_values.c` owns finite-value type
matching, reference and `anyOf` filtering, enum/const comparison and ordered
object/array canonicalization. C17 also quotes JSON string/key bytes, constructs
finite-value rules, validates required fields, builds ordered objects through
two comma suffix states, constructs bounded arrays and counts string/key
characters. Integer type matching retains the pinned binary-double policy.

Normalization publishes a private canonical value or a successful exclusion;
operational refusal preserves the caller's result. Private writer staging is
retired on all outcomes. Rules copy literal/symbol spans into the C builder.
Property and character counts share one construction state across nested child
visitors; copying the counts around a callback would lose nested accounting.
Refusal can retain earlier private increments/rules, so retire the counts,
builder and callback staging rather than reuse a failed construction.

Character traversal is iterative, with sixteen inline frames and bounded growth
for deeper trees. The default value/reference limit is 256, character budget
120,000 and work budget 64 million counted units. Accounting counts bytes that
are not UTF8 continuation bytes, matching the pinned method; it is not Unicode
validation. Quote, symbol and required-name buffers use paired allocator hooks.
These checks exclude provider JSON/ICU staging and whole-process cost.

`gufo_schema_values.hpp` supplies borrowed views, private JSON staging,
nonthrowing error translation, cached string/number leaf predicates and
binary-double serialization. The child visitor still owns dispatch; reference
memo and compiled-schema cache policy now use C17. Nine unique pinned `schema-values-edits.json`
replacements select the C17 algorithms under the existing default-ON switch;
OFF retains the original bodies. Matching provider/application builds require
the 45-file inventory and `schema_values_edits_sha256`. This adds no inference
worker, engine/event/RNG layout, model state or DS4 RAM/SSD payload field.

The [host receipt](validation/c17-schema-values-host-2026-10-05.json) records
258 independent tree/language/boundary oracles, 115 callback refusals and
16 C allocation refusals. All 628 complete value/type/container witnesses agree
between pristine Gufo, C17 and OFF, and all 14 earlier full witness hashes are
unchanged. Four Debug, four ASan/UBSan/LeakSanitizer, 30 reference-project and
four ICU-OFF checks pass, with 45 public C++ headers. The sandbox's `ptrace`
prevents LeakSanitizer from operating; failed attempts are preserved and reruns
outside that constraint keep every sanitizer enabled. The newer matching
`2359488` provider/application build passes selected original-weight AR37/MTP37
controls ([GPU receipt](validation/c17-finite-cache-point-gpu-2026-10-05.json)).
Private provider allocation faults, individual numerical branches,
allocation-exact resources and matched cost remain open, including the
preserved reactive scheduling path. Frozen `1bff953` GPU receipts do not cover
this finite-value source; `2359488` excludes the newer reference memo.

## Grammar construction and validation

`lie/grammar_builder.h` exposes a model-neutral C17 construction ABI 1. The
builder owns rule alternatives, sequences, terminal classes and dense sealed
tables. It copies inputs and supplies literal chunking, optional/repeated/exact/
bounded repetition, JSON byte primitives, cached depth-bounded generic values
and shared-prefix unsigned decimal intervals. JSON strings retain UTF8 and
surrogate-pair escape rules; normalized decimal bounds support 512 digits.

Finalization computes productive and nullable fixed points, checks every rule
for a cycle before input consumption and removes impossible alternatives.
Cycle traversal uses a heap stack, including the independently tested 4096-rule
chain. The result borrows immutable tables until builder release; the runtime
program copies them and can outlive the builder. Predicate and allocator
contexts remain caller-owned. No provider or ICU type enters the public header.

Default limits preserve 262,144 rules and uint32 table counts, with a 64-million-
unit construction budget. Argument/result publication is explicit. A failed
mutation latches its status; prior successful primitives may remain, and the
caller retires the builder. Invalid output arguments can refuse before mutation.
Finalization publishes only after successful allocation and validation, then
rejects further mutations. Paired allocator hooks retire partial storage.

The selected provider compiler now calls this C builder for these operations;
its original construction and validation bodies execute only with
`LIE_C17_SAMPLING=OFF`. The adapter translates typed inputs/errors and copies
private templates needed by the still-transitional reasoning/tool composition.
The base grammar creates its runtime program directly from the C tables.
Schema dispatch, binary-double leaf translation
and provider template/model/controller storage remain transitional. Structural
transformations and finite-value/container algorithms now use C17. This is not a completed
JSON Schema compiler or autonomous model executor.

[Source-bound host evidence](validation/c17-grammar-builder-host-2026-10-05.json)
records 28 Debug, 28 sanitizer and 28 pristine/ON/OFF tests. There are 11,169
independent language/boundary oracles, 113 owned allocation refusal points,
512/513-digit boundary checks and the 4096-rule chain. All thirteen earlier full
witness hashes are unchanged. The fixture's requested payload peak is 38,090
bytes, excluding allocation headers and the provider/ICU/process/GPU.
Four minimal-core ICU-OFF checks, 43 public headers and strict C17/symbol checks
pass; local CPU maximum is 91.5 C. These are host languages and lifetimes, not
new original-weight correctness, memory fit, allocation-exact whole-provider
cost or performance evidence.

At the builder checkpoint the private inventory grew from 32 to 35 files, with
21 additional exact runtime edits. The schema slice now brings it to 38 files.
Source/header/glue/recipe changes require matching sealed provider
and application rebuilds. Worker/events, RNG, executor/request/generation and
DS4 RAM/SSD layouts remain unchanged. Full JSON Schema ownership and GPU gates
remain part of the existing task.

## Build selection and observability

`LIE_C17_SAMPLING=ON` is the default for the verified state-access provider.
An explicit OFF build retains legacy provider selection, history bookkeeping
and compact/speculative probability arithmetic, byte-grammar runtime, numeric/Unicode
predicates, vocabulary/cache algorithms and regex syntax/assertion/expression/derivative/DFA
construction, Unicode registry/input handling, concrete byte-grammar construction
and productivity/cycle validation. Use the same
selection in the provider build and the linked application; verification refuses
an incompatible receipt. Acquire the pin once using the
[build guide](../guides/BUILD.md#gpu-inference-build), then use unused labels:

```sh
cmake -DLABEL=qwen-c17 -DLIE_C17_SAMPLING=ON -P cmake/provider/Build.cmake
cmake -S . -B build/release -DLIE_GUFO_RUNTIME=ON \
  -DLIE_GUFO_STATE_ACCESS=ON -DLIE_C17_SAMPLING=ON \
  -DGUFO_SOURCE="$PWD/.deps/gufo-state-access-qwen-c17" \
  -DGUFO_BUILD="$PWD/build/qwen-c17"
cmake --build build/release -j1
```

Repeat with unused labels and OFF in both commands for the explicit fallback.
No new HTTP field or runtime switch is required. `dense_sampling` in server
build information, actuator and benchmark identity reports `lie-c17-dense`,
`gufo`, `none` or `synthetic-test-fixture`. Overall backend ownership remains
`delegated` while the Gufo model/session executor is required.

The direct Gufo reference executable resolves a separately compiled legacy
sampler, byte-grammar, numeric and Unicode predicate methods before the provider archive, with the same
verified layouts. Shared inline model/controller arithmetic is unchanged. Its
`dense_sampling` value is `gufo`; comparing LIE to a control that also used the
new C selector would not isolate this extraction.

## Verification and remaining gates

The standalone C fixture checks mathematical normalization, tie ordering,
penalty/bias order, masks, minimum retention, large flat top-p rows, RNG goldens,
categorical frequencies and workspace refusal. It works in a headless C build.

The separate host-only reference project independently verifies the official
Gufo pin, then tests the pristine sampler, C17 variant and OFF variant. It runs
upstream sampling, grammar and MTP-policy fixtures, complete distribution /
draw / residual / RNG witnesses for 1200 cases, another 1200 biased cases
against the same-layout legacy variant, and twelve complete 248320-entry rows.
These are synthetic operator/contract checks, **not original-weight inference**.

At the original 2026-10-03 checkpoint, the native, headless and host-reference
suites pass **43/43**, **18/18**
and **14/14** tests with ASan/UBSan/LeakSanitizer. HIP compilation/linking and
the metadata/symbol audit also pass; they perform no model execution. The
[source-bound receipt](validation/c17-sampling-2026-10-03.json) records exact
source/provider identities, witness hashes, failures, exits and temperatures.

```sh
cmake -S tests/sampling -B build/sampling-host -DLIE_SANITIZERS=ON
cmake --build build/sampling-host -j1
env HIP_VISIBLE_DEVICES=-1 ROCR_VISIBLE_DEVICES=-1 CUDA_VISIBLE_DEVICES=-1 \
  ctest --test-dir build/sampling-host --output-on-failure -j1
```

Reference checks need a C++20 compiler and ICU; the C sampler itself needs C17
and libm. The normal build/test path does not need Python. Shared-hardware GPU
qualification remains subject to [coordination](../COORDINATION.md).

## Host cost and temporary allocations

The optional host probe compares the pristine pinned Gufo sampler, the C17
variant and the same-layout OFF variant on the editing Strix Halo `.155`.
It uses **generated logits**, not weights or model inference: three vocabulary
sizes, three logit shapes and six filter configurations, for 54 cases. Three
balanced process orders supply 21 measured repetition averages per case.
Distribution construction, one draw and destruction are timed; input/history
preparation and result reporting are excluded. Allocation hooks are linked into
separate untimed executables and never into the runtime or cost executables.

All distribution, draw and RNG witnesses match. The expanded reference suite
passes **17/17** with ASan/UBSan/LeakSanitizer, and all three cost probes also
pass a sanitizer smoke. All 162 measured allocation scopes retire completely.
The [receipt](validation/sampling-cost-2026-10-03.json) and
[complete 54-case values](validation/sampling-cost-2026-10-03.csv) retain controls,
raw hashes, exits and observed thermal limits.

The **initial cost gate fails**. Across these cases C17/reference time ratios
range from 0.55 to 3.43, with a median ratio of 1.71. For the 248320-entry sine
shape, per-call medians are:

| Configuration | Pristine Gufo (µs) | C17 (µs) | C17/Gufo time |
| --- | ---: | ---: | ---: |
| Greedy host selection | 50.38 | 136.17 | 2.70 |
| Temperature 0.7, no filters | 1366.33 | 2653.21 | 1.94 |
| Top-p 0.95 | 15138.26 | 26514.31 | 1.75 |
| Top-k 32, top-p 0.8, min-p 0.1 | 414.59 | 456.34 | 1.10 |
| Min-p 0.9, minimum five entries | 13043.86 | 23776.68 | 1.82 |
| Top-k 32 with repetition/frequency/presence penalties | 1165.73 | 1104.28 | 0.95 |

C17 top-k configurations request one 512-byte allocation; the controls request
768 or 1536 bytes across two or three allocations. Unfiltered distributions
still require 3973120 bytes in all arms. These are requested C++ heap bytes
inside distribution construction, excluding prepared inputs, allocator
overhead and unrelated allocations; they are not model residency or GPU peaks.

The measurement runs peak at CPU82.5/GPU55/NVMe34.85 C. CPU affinity and
background load are uncontrolled. These short host loops do not establish
model throughput or explain the separate 1500-token GPU result: ordinary
greedy inference retains the provider's GPU argmax shortcut.

```sh
cmake -S tests/sampling -B build/sampling-cost -DCMAKE_BUILD_TYPE=Release \
  -DLIE_SANITIZERS=OFF -DLIE_SAMPLING_PERFORMANCE=ON
cmake --build build/sampling-cost -j1
build/sampling-cost/reference-cost
build/sampling-cost/candidate-cost
build/sampling-cost/fallback-cost
build/sampling-cost/candidate-allocation
```

This option belongs to the host QA project and defaults OFF. Normal builds and
clients need no new dependency. Private qualification supervision scripts are
outside the product build and benchmark path.

## First cost optimization

C17 now sorts ranked rows with median-pivot partitioning, insertion sort for
small partitions and a depth-bounded heapsort fallback. Only the smaller
partition recurses, keeping stack growth bounded. The total logit/token order,
workspace allocation and filter arithmetic stay the same. The linear path
collects its maximum while preparing candidates instead of scanning them again;
greedy tests a possible improvement before checking the optional mask/finite
predicate. No device call, thread, HTTP field or ABI changes.

Expanded ASan/UBSan/LeakSanitizer checks pass **17/17** host-reference tests,
**1/1** native C contract and three additional cost smokes. Full-vocabulary
witnesses now cover 24 cases, including decreasing, organ-pipe and interleaved
logits. The new 54-case cost matrix matches both controls and the original
baseline exactly in distribution/draw/RNG witnesses; all allocation scopes
retire. New results and original results remain separate:
[optimization receipt](validation/sampling-optimization-2026-10-03.json),
[complete before/current values](validation/sampling-optimization-2026-10-03.csv).

The median case time ratio against Gufo falls from **1.71 to 1.07**, but the
worst case remains **2.00**, so the performance gate remains open. At full
vocabulary with flat logits, top-p costs 5810 µs versus 5786 µs for Gufo;
min-p costs 3714 µs versus 3804 µs. Host greedy and unfiltered distributions
still regress. This is an independent CPU repetition of the same generated-logit
method, with uncontrolled affinity/background load; original-weight sampled
GPU qualification remains pending. Measurement peaks are CPU77.875/GPU52 /
NVMe34.85 C; no software thermal stop occurs.

The second CPU follow-up separates mask-free greedy from optional grammar
handling and separates independent probability division from underflow-only
compaction. All 17 host-reference tests, the native C contract and three cost
smokes pass again with ASan/UBSan/LeakSanitizer. The complete 54-case witnesses
and all 162 allocation retirements agree with both controls and the baseline.
The worst C17/reference time ratio falls from 2.00 to **1.20**; the median case
ratio is **1.07**. Full-vocabulary sine greedy now costs 53.43 µs versus
49.94 µs; unfiltered sampling costs 1549.44 µs versus 1354.22 µs.
The cost gate and original-weight sampled GPU qualification remain open.
The [dense-loop receipt](validation/sampling-dense-loops-2026-10-03.json) and
[complete values](validation/sampling-dense-loops-2026-10-03.csv) preserve this
run separately. Measurement CPU/GPU/NVMe peaks are 84.125/55/33.85 C, without
a thermal stop. API, ABI and reactive scheduling remain unchanged.

Next gates on this branch: original-weight vision/combined continuation and
restarted MTP/vision SSD, the missing 12288 depth, first-prompt regression
diagnosis, dense host-cost optimization, sampled model overhead and HTTP
responsiveness on `.157`. Then extract request-owned sampler state and
compact speculative distributions, followed by tokenizer, loading/binding and
layer control. GPU-kernel replacement has its separate C++ removal gate.

## Provenance

The C numerical algorithm is an attributed port of official Gufo
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, acquired independently in this
worktree. `dense-sampling-edits.json` and `history-sampling-edits.json` record exact
conditional integration replacements; the build receipt binds both manifests,
all six C source/header and adapter glue files,
provider source inventory, compile selection and archive hashes. No DS4 project
code, sibling checkout artifact, model conversion or weight payload is imported.
Retain [Gufo's MIT notice](../../third_party/gufo-NOTICE) and
[license](../../third_party/gufo-LICENSE) with the port.
