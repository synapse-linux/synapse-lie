<!-- SPDX-License-Identifier: MIT -->
# C17 sampling and byte-grammar runtime

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
deep copies, deferred draws, entropy acquisition, schema compilation, string/regex predicates, vocabulary trie/mask cache, model/session and
speculative-controller state, and selected GPU numerical
kernels. Reporting logits still use the provider transform before the existing
C probability normalizer. The sampler as a whole is not yet autonomous C.
Existing eligible GPU argmax shortcuts remain delegated and preserved.

Reactive readiness, per-row credits, cancellation, native batching and MTP
controller ownership are unchanged. There is still one device-owner worker. The C
selection call is synchronous; it does not add an asynchronous GPU forward or
establish a throughput improvement.

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
schema/string/regex predicates, vocabulary mask cache and speculative model/controller
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
Schema compilation, string/Unicode-DFA predicates and the
vocabulary trie, transition interning and shared mask cache remain delegated.
The provider still marshals snapshots between vector storage and C state. Those
algorithms/storage and their cost remain explicit work in the same grammar task.
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
to this component. JSON library numeric conversion/representability and exception
translation remain in `gufo_grammar_number.hpp`. String/Unicode-DFA/regex and
schema compilation, vocabulary trie/transition/cache algorithms and provider
snapshot marshalling still need extraction within the same identified task.

The four exact `grammar-number-edits.json` edits select C17 by the existing
`LIE_C17_SAMPLING=ON` default and retain the legacy numeric implementation with
OFF. The provider receipt now binds 15 C sampling/grammar source/header/glue files
and the numeric recipe; archive/application rebuilds are mandatory. The direct
Gufo reference also compiles legacy numeric predicates before the shared archive.
This source composition still requires admitted original-weight qualification.

[Source-bound host commands and witnesses](validation/c17-grammar-number-host-2026-10-05.json)
record independent rational/LCM oracles, pristine/ON/OFF complete prefix/value/LCM
comparisons, failures and temperatures. These are synthetic host checks;
original-weight AR/MTP/tool/grammar continuation, resources and matched cost
remain unqualified on `.161`.

## Build selection and observability

`LIE_C17_SAMPLING=ON` is the default for the verified state-access provider.
An explicit OFF build retains legacy provider selection, history bookkeeping
and compact/speculative probability arithmetic, byte-grammar runtime and numeric predicates. Use the same
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
sampler, byte-grammar and numeric predicate methods before the provider archive, with the same
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

The final native, headless and host-reference suites pass **43/43**, **18/18**
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
