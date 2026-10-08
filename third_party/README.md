<!-- SPDX-License-Identifier: MIT -->
# Provenance and dependency boundaries

The native paired-prompt builder, activation observer, collector and direction
learner are owned MIT C17 code. `activation-observer-edits.json` records four
exact diagnostic hooks against the independently pinned official Gufo executor;
the generated upstream source retains Gufo's notices. The private bridge keeps
upstream/device types inside the adapter. It copies only selected last-token
trunk rows for explicit diagnostic prefill calls. No DS4 source or sibling
workspace artifact is imported. The
[matching HIP build](../docs/development/validation/steering-build-point-build-2026-10-07.json)
binds the recipe, ten owned steering files, both full providers and seven
consumers. Original activation/learned-quality execution remains unqualified.

The model-neutral attention observer (`src/dispatch.c`, `lie/dispatch.h`) is
owned MIT C17 code. `attention-dispatch-edits.json` records exact host hooks and
bounded sparse-WMMA workspace specializations
against official Gufo pin `f783fedb9bea2ec7de941f6da4e02f4a4596b29e`; Gufo notices
remain applicable to derived source. The owned recipe keeps the short workspace
and instantiates a separate 8,192-word workspace for long sparse frontiers.
Compact selection thresholds, key order and WMMA/softmax arithmetic are retained;
there is no weight, tensor-format or DS4-source change. Provider receipts bind
the C17 extent policy, exact recipe, observer option and default-ON
`LIE_LONG_CONTEXT_WMMA` selection. Complete private producers/consumers must
rebuild coherently. The long specialization's original-weight numerical,
resource and performance qualification remains pending.

First-party runtime, tools, tests, ABI and adapter use MIT (`../LICENSE`). The
owned dense sampler is an attributed C17 port of independently fetched official
Gufo, with its [MIT notice](gufo-NOTICE) and [license](gufo-LICENSE) retained.
The request-history C17 component implements the same pinned Gufo semantics
against independently fetched source. `history-sampling-edits.json` records exact
integration; `gufo_history.hpp` only adapts vector storage and exceptions. Provider
receipts bind the selected owned sampler/grammar source/header/glue files and the
dense, history, compact-distribution and byte-runtime recipes. The latter ports official ordered
probabilities, residual correction and host MTP proposal/verification arithmetic
from the same pin; vector/error glue remains transitional. Gufo notices remain applicable; no DS4 cache code is copied.
The C17 byte runtime in `src/grammar.c` ports rule expansion, byte transitions,
completion and canonical-state ordering from official `json_constraint.cpp` at
the same pin. Immutable primitive ownership, ordered predicate tables and the
construction-only identity memo now use `src/grammar_lexeme.c`. Its dispatch
calls the existing attributed C numeric/string/DFA algorithms directly; C17
retains their immutable policies. Six exact guarded edits in
`adapters/gufo-state/grammar-lexeme-edits.json` preserve the original OFF
classes/vector/map. `gufo_grammar_lexeme.hpp` supplies private C++ facades and
error translation. Request grammar snapshots now stay in C17 through runtime
transitions and independent speculative copies, with private read-only/value
glue in `gufo_grammar_state.hpp` and three exact guarded edits in
`adapters/gufo-state/grammar-state-edits.json`. The original OFF vectors and
algorithms remain available. Explicit legacy-vector transfer remains outside
the default-ON runtime path. C++ schema/regex construction, template projections
and model/controller remain transitional. Construction, schema
policies, vocabulary masks and grammar composition use shared C17 contracts;
`gufo_grammar.hpp` adapts construction/state/errors. No sibling
code is imported by this extraction.
The native Gufo conversation benchmark port has its own
[pinned source and fixture provenance](gufo-bench-source.json).
The complete C17 JSON parser in `src/json_parse.c` ports syntax, UTF-8/escape
decoding and decoded duplicate-key semantics from independently fetched official
Gufo `src/core/json.hpp` at `f783fedb9bea2ec7de941f6da4e02f4a4596b29e`
(source SHA-256 `abe26aa93f76be30d07aeef1a4aa5875ae6312689f499a5b53f8a6e7fae5368d`).
Its iterative traversal, bounded workspace and per-object key tables are owned
C17. Three exact edits in `adapters/gufo-state/json-parser-edits.json` preserve
the original OFF parser. The later `src/json_value.c` independently implements
C17 scalar/string/key/ordered-table ownership, copies/moves and serialization
against the same pinned ordered-value semantics. Two additional exact edits in
`json-value-edits.json` preserve the complete original OFF Value class.
`adapters/gufo_json_value.hpp` supplies private C++ references and synchronized
string projections; `gufo_json_parse.hpp` only translates status/publication.
The later model-neutral ownership-slot API moves the facade's root/borrowed,
lazy-initialization, copy/move and moved-scalar policies into C17 against the same
pinned semantics. Typed C++ projections and exception translation remain private;
the original OFF Value class remains guarded and unchanged.
The retained Gufo MIT notice/license apply.
No extra dependency or sibling project code is introduced.
No sibling DS4/CachyOS project sources, recipes,
configs or binaries were imported. Read-only inventory/qualification observations are
historical evidence, not a copied backend. Model files remain external/read-only
under their publisher's terms. A C API wrapper does not relicense its dependencies.
The C17 direction-bank loader is independently implemented against DS4's flat
f32 format. Only read-only official source identities and reference observations
are retained for its binding audit; no DS4 implementation enters the product.
It uses the existing OpenSSL Crypto dependency and adds no model-forward code.
The subsequent C17 session-policy controller is also independently implemented.
Its versioned history/cache domains, bounded transactions, owner checks and
resource snapshots are LIE contracts, not a DS4 serializer or executor port.
It uses existing pthread/OpenSSL dependencies without creating runtime threads;
no DS4 source, artifact, model or qualified evidence is modified or imported.

The sampling-observer recipe wraps three existing pinned Gufo engine call sites
and adds a read-only sampler mask accessor. Its numerical functions remain the
pinned original/verified C17 variants. `gufo_sampling_observer.hpp` only projects
borrowed diagnostics through a C17 contract; no sibling code or new dependency
is imported. The retained Gufo license/notice and exact source provenance apply.
The native MTP capture writer uses this borrowed C17 contract; its offline replay
checks the original/C17/OFF samplers plus independent mass, integer-proposal,
residual/RNG and grammar byte-walk oracles. The copied callback configuration
changes diagnostic lifetime only. These clients add no product dependency,
sampling policy or model-forward implementation. Their HOST fixtures are
explicitly separate from original-weight GPU qualification.
The [matching Point compilation receipt](../docs/development/validation/mtp-capture-point-build-2026-10-07.json)
binds the 42 exact recipes, both complete provider variants and all six linked
consumers. Compilation does not establish original-weight numerical acceptance.
The [subsequent selected text receipt](../docs/development/validation/sampling-mtp-text-point-2026-10-07.json)
binds actual Q4/Q8 MTP observations and complete original/C17/OFF numerical
replays. Required-tool MTP and broader qualification remain separate.
The [subsequent required-tool MTP receipt](../docs/development/validation/sampling-mtp-tools-point-2026-10-07.json)
also qualifies selected full-mask and complete-call probability/RNG/controller
witnesses. The original unconstrained proposal policy is retained; wider
quality/fault/resources and matched performance remain open.

## Actual external dependencies

| Component | Observed version/pin | License / use |
|---|---|---|
| libuv | 1.52.1 | MIT and component notices; event loop/network lifecycle |
| llhttp | 9.3.1 | MIT; HTTP/1 parser |
| json-c | 0.19 | MIT; JSON serialization/parsing |
| libcurl | 8.21.0 | curl license; native HTTP benchmark clients, monitor and upstream image helpers |
| Ryu | 4c0618b0e44f7ef027ebae05d2cc7812048f7c8f | Bundled C binary64 conversion; BSL-1.0 selected, upstream dual notices/licenses retained in [ryu-NOTICE](ryu-NOTICE) |
| Gufo | f783fedb9bea2ec7de941f6da4e02f4a4596b29e | MIT + upstream component notices; opt-in HIP-linked transitional Model/Session adapter; bounded original-weight smoke passed, numerical qualification open |
| ROCm / HIP | 7.2.53211 compiler/runtime observed locally | AMD/upstream component licenses; hipBLAS, hipBLASLt, rocBLAS, hipCUB/rocPRIM; already installed |
| ICU / OpenSSL / PNG / JPEG | selected installed development libraries, CMake/ELF receipts authoritative | their respective upstream licenses; tokenizer/crypto and coupled upstream helpers |

libuv and Ryu are bundled. The other production libraries are system dependencies.
Build receipts record compiler/pkg-config versions. A distributable package will
need its normal dependency-license audit; this increment installs/publishes none.
CMake verifies the provider sources and archives. HTTP benchmark clients and
CSV/JSON/SVG/PNG exports are first-party C17 code; PNG encoding links libpng.
Python is used only by explicitly selected legacy test oracles and historical
development/qualification scripts, outside the normal build and runtime.
Terminal Bench Mini is an optional external evaluation harness under Apache-2.0,
independently fetched at `07034484346dc724d0e2c47c821fd196add1d6fb` in a private
source directory, with its license and notice retained. It and Harbor are not
linked, bundled or required by the native product. Its
[source preparation receipt](../docs/development/validation/terminal-bench-source-preparation-2026-10-04.json)
does not claim task evaluation or model quality.
Incremental function events, retained fragment journals and `allowed_tools`
parsing are first-party C17 implementations against published OpenAI protocol
documentation. No OpenAI SDK implementation or runtime dependency is imported.
Top-k/min-p public controls are first-party C17 parser/client additions mapped
to the existing pinned provider sampler. They introduce no dependency or copied
DS4 code. The [CPU receipt](../docs/development/validation/ds4-sampling-controls-2026-10-04.json)
binds independent source composition and adapter header checks; original-weight
qualification of the newly exposed filters remains pending.
The optional `tests/sampling` cost/allocation project compares the pristine
official sampler with generated LIE ON/OFF variants, without HIP or model
forward. Its first-party C++20 QA probes link ICU and libm; the binary64 oracle
also uses installed MPFR/GMP, without adding a production dependency. Allocation hooks
belong only to separate untimed probes. Runtime dependency scope is unchanged.
The new first-party C17 SSD codec/identity/store also uses installed OpenSSL
Crypto SHA-256. No upstream snapshot codec or disk-cache code was imported;
upstream source/archive pins are unchanged by this increment.

## Gufo source acquisition

`adapters/gufo-state/context-edits.json` adds exact, hash-guarded integration
edits to the separately derived state-access variant of `f783fedb`. The edits
also bind C17 prefill capacity to scratch allocation, preserving a floor
for admitted concurrent decode and MTP rows; default capacity stays 2048.
Eight files bind the LIE C17 static RoPE frequency/amplitude plan to existing Qwen attention,
indexer and vision-coordinate kernels and grow configured session/scratch
bounds. The pristine source and its upstream MIT/third-party notices remain
unchanged. The numerical plan in `src/rope.c` is independently implemented C17,
using the published Qwen YaRN settings and the
[Transformers parameter specification](https://github.com/huggingface/transformers/blob/main/src/transformers/modeling_rope_utils.py).
No Transformers code or Python dependency is imported. Build receipts derive
and verify these edits with all existing state/sampler/vision edits before link.

Official repository: https://github.com/gufo-org/gufo

`tools/fetch-gufo.py` explicitly fetches only the pinned GitHub API tarball,
verifies SHA256, checks member paths/types and creates a new `.deps` directory.
`gufo-source.json` records the archive and every extracted regular-file hash
(1019 files). Only the two editor symlinks `.claude/skills` and `CLAUDE.md` are
omitted; numerical/build source files are unmodified. No moving `main`, source
from the other agent's checkout, model download or binary redistribution.

Keep `gufo-LICENSE`, `gufo-NOTICE`, `gufo-THIRD_PARTY_NOTICES.md` and, when actually
redistributing Gufo components, their full upstream `licenses/` notices. Those
notices cover the llama.cpp/ggml, DS4, AMD, Qwen template and other ancestry;
Gufo's MIT license does not replace third-party terms. This repository's own
adapter currently uses upstream headers/API; it does not copy/rewrite kernels.
The [backend evolution contract](../docs/BACKEND.md) now permits an explicit
embedded adapter for bootstrap, then requirement-driven refactoring toward an
owned backend. Numerical ports need per-component provenance, retained notices
and tests; current C support components do not complete model-forward
ownership. Keep the pristine reference separate from
instrumented/forked experiments and ports. First-party ownership of orchestration
does not relicense numerical code or make embedded Model/Session a reimplementation.

## Native server tools

`src/chat_tools.c` and `src/tools.c` are first-party C17 protocol code, not copied
from DS4 or Gufo's serving frontend. `adapters/gufo_chat.hpp` translates LIE data
into the existing independently fetched Qwen template API at `f783fedb`. The
renderer remains unmodified. Strict functions receive first-party JSON format
guidance following upstream `ConstrainChatRequest` in
`src/cli/serve/inference_backend.cpp`, aligning the template with the JSON call
grammar rather than forcing names, values or counts. This applies to text and
vision after image attachment; no numerical implementation is substituted. Upstream template
provenance/notices remain applicable. Pi is an optional external client, using its
standard OpenAI provider and normal JSON configuration; no extension or Pi source
is bundled/modified. Tool-frame tests and CPU/Pi fixtures are not model qualification.
The corrected guidance now compiles in both private HIP providers and all six
consumers ([build receipt](../docs/development/validation/tool-prompt-guidance-point-build-2026-10-07.json));
this device-hidden build does not qualify original-weight tool behavior.
The subsequent [original-weight AR observation](../docs/development/validation/tool-transitions-ar-point-r3-2026-10-07.json)
passes the selected two-call question but fails its reversed-results follow-up.
The pinned renderer omits call IDs and emits results in received order;
first-party `src/chat_history.c` now builds an ID-correlated render index without
JSON, model or transport dependencies. LIE's model binding applies it to whole
owned messages after image attachment, without changing upstream source or the
frozen client workload. Local core/formatter Release and sanitizer checks pass
([HOST receipt](../docs/development/validation/tool-result-correlation-host-2026-10-07.json));
the matching `64fa7c2a` [coherent HIP build](../docs/development/validation/tool-result-correlation-point-build-2026-10-07.json)
passes both providers and all six consumers, including verified C17 helper
linkage. The later [original AR observation](../docs/development/validation/tool-transitions-ar-point-r4-2026-10-07.json)
passes the fixed reversed-result Chat JSON/SSE checks. It stops at a separate
Responses parser refusal of `seed`; wider AR/MTP acceptance remains required.
The earlier model-quality failures remain unchanged historical evidence.
The separate Responses parser correction is first-party C17 normalization of
seed and penalties through the existing shared generation contract; stored
response options preserve supplied values. Upstream numerical/template source
is unchanged. Eight Release and eight unsuppressed sanitizer parser/HTTP
fixture checks pass ([HOST receipt](../docs/development/validation/responses-generation-controls-host-2026-10-07.json)).
The [matching coherent HIP build](../docs/development/validation/responses-generation-controls-point-build-2026-10-07.json)
binds both unchanged numerical providers and the corrected C17 parser/server
objects. The [original-weight AR gate](../docs/development/validation/tool-transitions-ar-point-r5-2026-10-07.json)
passes the unchanged 71 transitions and five baseline controls. The
[matching MTP gate](../docs/development/validation/tool-transitions-mtp-point-r2-2026-10-07.json)
also passes with actual draft activity and unchanged original Q4/Q8 files.
Broader qualification remains required; these checks do not change provenance
or establish executor ownership.

## Archived private Q2 experiment

The owner withdrew this experiment. Active overlays/tools are removed; the
following provenance applies to preserved historical evidence and build artifacts,
not to current source or runtime support. See [the new plan](../docs/archive/REPLAN.md).

`adapters/gufo-q2/host-edits.json` contains first-party, exact hash-guarded edits
against six existing Gufo files, materialized only in a fresh private build source
tree. The source copier retains all upstream files/licenses/notices. This modifies
storage/configuration/binding and adds an explicit device-upload refusal; it does
not import or reimplement the GPU kernels/model forward. Pristine `.deps` and the
original archives stay unchanged. The variant is not accepted by the production
link checker; [Q2 host scope](../docs/archive/Q2-COMPATIBILITY.md) is not GPU support.

Official `Qwen/Qwen3.8-Flash-Next` configuration at
`de4b8e4d43b917e7706784d8bb445c9af86a3540` and its **Qwen Community License 1.0**
were independently fetched into ignored evidence to resolve missing mRoPE section
metadata. Only architectural parameter facts are used, not model-forward code.
The assets retain their separate license (including commercial-service conditions);
MIT runtime code does not relicense model/configuration assets or authorize release.
No model values were fetched, converted or redistributed.

The subsequent [Q2 HIP candidate](../docs/archive/Q2-HIP.md) adds a separately hashed
eight-file overlay and three first-party boundary files. It instantiates the
licensed Gufo/llama.cpp MMQ IQ2/Q2 helpers, with scoped IQ2 fractional-eighth and
Q2 MMA FP32-product corrections documented in [extended evidence](../docs/archive/Q2-EXTENDED.md).
The test codebook generator retains the pinned MMQ table's MIT attribution.
Other first-party work
covers routing, reserved workspace, source geometry and zero-safe quantization
specializations. No sibling code/artifact or independent antirez numeric code
was imported. The helpers and their notices retain upstream provenance. This is
not a standalone C17 model engine. The corrected candidate passes 24 extended
and 64 original operator controls, with the reported manifest metadata erratum;
these do not establish full-format or model qualification.

## Private Qwen-only build scope

`cmake/gufo-runtime` is a LIE-owned build recipe over the unchanged upstream
source, using the original `qwen38_flash_next` target and its numerical compile
flags/dialects/wave-size settings. Selected core/tokenizer/template/sampling and
coupled HIP/vision helper units complete its link closure. CPU model-forward
reference targets are not built or linked. No source/kernel is patched or copied.

This is not the complete upstream release build: that configure failed on a
missing rocWMMA dependency (`gufo-host-r1`). The selected Qwen units do not use
rocWMMA, so the subset requires their actual dependencies, not a fabricated
include path. The first subset link exposed missing upstream argmax/sample and
curl dependencies (`t0-linked-r1`); these were added properly in a new build.
Historical archives/receipts remain intact. No package/dependency was installed.

`tools/build-gufo.py` uses private HOME/cache/temp, serial local compilation and
source verification before/after. `tools/check-gufo-build.py` verifies source,
archive identities, cache and subset recipe before explicit linking. Link/smoke
receipts record ELF dependencies; these are not numerical or target-runtime
qualification. A distributable package still needs its complete license/DSO audit.

The first attempted codeload URL did not match the recorded GitHub API tarball
hash and was rejected without extraction. The exact API URL then matched the
expected archive. That refusal was not worked around by relaxing the hash.

## Research only — no code imports or assumed compatible checkpoints

- DS4: inherited stable reference `c05cd8e2bd35047196d95709f89d0ea2aff96df2`;
  modified port numerical baseline `982bffea86fd5568759a420c4808c5b2123161c8`.
  Cache/session/conversation lessons; the DS4 agent owns integration there.
  For the [antirez model format gate](../docs/archive/ANTIREZ-BENCHMARKS.md), LICENSE,
  `ds4.c` and `ds4.h` at c05cd8e2 were independently retrieved from official
  `raw.githubusercontent.com/antirez/ds4/` into ignored local evidence, with URL,
  HTTP status and SHA256 receipts. Only storage facts (MXFP4 id 39, 32 elements /
  17 bytes) were used in the inspector; no numerical code/decoder or build recipe
  is imported into LIE. Upstream MIT authors/notices remain with the sources.
- vLLM README inspected at `72e7874fa669617fd20c716e08cb486032f542c1`:
  continuous batching/chunked prefill/prefix cache are design references. Paged
  attention alone is not a serialization solution for recurrent Qwen state.
- llama.cpp server docs at `8df332de1b7d036952631ef9d0a25d8aa60aeea3`:
  GGUF/API/slot save-restore and batch-dependent numerical caveats. No generic
  model-format support is claimed by LIE yet.
- TensorFold README at `9cd52ab4daba68ddd09be89be8f23ad43175e821`:
  Flash Next has model/backend-specific MLX/CUDA paths and constraints. Shared
  CUDA rounds are explicitly enabled for selected families/rank counts; MLX
  spill/checkpoint flags are not implemented on CUDA. MLX affine/NVFP4/EXL3
  checkpoints in that table are NOT the local GGUF and will not be substituted.
  No TensorFold backend was built, imported or benchmarked here.

Documentation-level inspection is not a verified capability or speed result.
Revisit the actual model/backend code before integrating any technique, and
measure combined behavior rather than adding published gains.

Actuator v3 JSON is checked against the official Spring REST documentation.
Micrometer timer semantics were checked against source documentation at
`e5969e02c215be6b3b92887e38e5faee5d007964`. Live URLs and fetch hashes are in the
local evidence manifest. Prometheus web docs returned 403 and an initial source
path returned 404; the official format was then retrieved/read from
`prometheus/docs` at `d55526977b8a6355482c14db9474e43083275cf0`, path
`docs/instrumenting/exposition_formats.md`. Those failed fetches remain recorded.
The implemented export subset has independent CPU parser checks. promtool was
absent: its official validation remains an explicit additional gate, not PASS.

The reactive-inference candidate adds a first-party C17 readiness/credit
dispatcher and a small C++ binding to the pinned public `Session::DecodeBatch`.
No upstream numerical source/archive or model was modified or imported from
DS4. Native batch execution and its internal recovery remain delegated to
Gufo at the recorded pin; this is not an owned numerical reimplementation.


The shared `lie_core` extraction, bounded normalized-input copier, token witnesses
and direct core benchmark are first-party C17 under MIT. UTF-8 code is moved from
LIE's existing parser; no external implementation is imported. The provider ABI,
Gufo adapter, numerical source pin and model files are unchanged. json-c/OpenSSL
remain benchmark/protocol dependencies, not dependencies of the headless core.


## Explicit component-state access variant

`adapters/gufo-state/access-edits.json` records three exact friend declarations in
two official `f783fedb` headers. `tools/gufo_state_source.py` validates the pristine
1019-file inventory, materializes a separate copy and derives the variant hashes.
`build-gufo.py LABEL --qwen-only --state-access` rebuilds all selected archives;
`check-gufo-build.py ... --state-access` checks the edit/source/archive/recipe
identities. Pristine builds reject variant receipts without the explicit option.
No Q2 patch, sibling project source, numerical edit or opaque snapshot serializer
is imported. Original Gufo files retain their upstream licenses/notices.

`src/state.c`, `src/prefix_cache.c`, `src/models/qwen_flash_state.c` and the narrow
`adapters/gufo-state/access.hpp` binding are first-party MIT. The state component
coverage and geometry were audited against the pinned Qwen engine/executor fields
and snapshot implementation; the representation and cache policy are C17-owned.
HIP field transfers remain platform-specific and active forward execution remains
delegated. This variant is not the pristine upstream source/build. The RAM default
requires an explicitly state-capable composition; pristine baselines use RAM off.
## Strix Point composition

The `feature/strix-point-ud` fork independently fetched the same official Gufo
archive at `f783fedb`, matching the recorded archive and 1019 file hashes. Its
LIE-owned Qwen-only CMake recipe can select real gfx1150, with a target-bound
receipt and runtime admission. Numerical files, licenses, wave64 translation
unit flags and the optional state-access variant retain their existing
provenance. This is experimental platform support, not upstream release or
original-weight GPU qualification; see [STRIX-POINT.md](../docs/STRIX-POINT.md).

The KV disk HTTP client and report exporter in `tools/native/` are first-party
MIT C17, linked to libcurl, json-c, OpenSSL Crypto and libpng. SVG primitives and
PNG display glyphs are generated by first-party code without an external renderer.
The test-only `pread` barrier and independent native KVC fixture generator are
also first-party MIT. Historical Python supervisors/oracles remain optional
development tools. The 2026-10-02 cache-policy comparison reads
official `antirez/ds4` upstream code as a behavioral reference; no implementation
or local DS4 artifact is imported. It does not claim DS4 cache-policy or
compression equivalence. LIE retains its existing component representation.


The optional default-ON checkpoint codec links installed Zstandard under its
[BSD-3-Clause option](zstd-NOTICE). The [LZ4 notice](lz4-NOTICE) remains only
for historical validation provenance; current source does not link LZ4 or
read codec 1. No library source is copied or installed by LIE. Disabling
`LIE_CHECKPOINT_COMPRESSION` removes the Zstandard dependency. The byte permutation,
framing and retention policy remain first-party MIT C17. OpenSSL Crypto is now
a shared state-store dependency, including core-only builds.

## DS4 cache-policy behavior reference — 2026-10-02

Official `https://github.com/antirez/ds4/blob/main/ds4_kvstore.c` and its header
were read as public behavioral specifications for purpose codes, default
checkpoint limits, six-hour utility, prefix matching and optional extensions.
The implementation in `cache_policy.c`, `retention.c`, `prefix_cache.c` and
`store.c` is first-party MIT C17. No DS4 source or artifact was imported and no
local DS4 checkout was modified. This is a dated moving-main review, not an
immutable upstream source dependency. DS4 binary payload compatibility and
cross-quantization reuse are not claimed; native metadata remains LIE-owned.

## DS4 wire interoperability reference — 2026-10-02

`src/kvc.c` and `src/models/kvc_qwen.c` are first-party MIT C17 codecs written
against observed wire facts; no DS4 source/artifact was imported. Qwen payload
and public constants were read in official upstream revision
`0aaea5a238fb41a35106a551e73c8409dfb751ac`, obtained with read-only `git ls-remote`.
The outer envelope was separately inspected at
`6289c516273979173abbc062209a81dd3706b804` and in the dated main review for extended
quantization values. The older pin contains no Qwen path. OpenSSL's EVP SHA-1
supplies text filenames; no upstream digest implementation was copied.
[Exact scope, source links and remaining integration gates](../docs/reference/KVC.md).

`src/models/kvc_qwen_map.c` is an original MIT host-layout transformation, not
a model forward or upstream source port. DS4's public Metal Qwen source was
reviewed read-only via the dated main web view on 2026-10-02; the pinned fetch
was unavailable. GPU GDN layout is value-major, unlike the CPU reference.
Gufo destination facts come from the existing independently fetched `f783fedb`
source. Synthetic mapping checks are not cross-engine numerical qualification.
No local DS4 source, cache or qualified artifact was imported or modified.

## Complete-history runtime KVC variant — 2026-10-02

`adapters/gufo-state/kvc-edits.json` layers exact edits on the existing friend
manifest at independent upstream pin `f783fedb9bea2ec7de941f6da4e02f4a4596b29e`.
The resulting four-file variant retains full raw index arrays, includes their
capacity in `SessionBytes`, and pools completed AR keys before sparse selection
in scalar and batch paths. It reuses upstream kernels but changes scheduling
and memory usage, requiring independent GPU regression tests. `build-gufo.py`
and `check-gufo-build.py` require explicit `--state-access --ds4-state`, source
variant `lie-ds4-state-v1` and both manifest hashes. Previous source/archive trees
are preserved. No DS4 implementation is copied.

`src/models/kvc_qwen_state.c`, `src/state_kvc.c` and generic integration remain
original MIT C17. Public DS4 constants at `0aaea5a238fb41a35106a551e73c8409dfb751ac`
identify Qwen Flash Next as model id 5; the dated official store/server review
accepts opaque trailers after the model payload. LIE adds its own identity and
integrity extension there. This layout does not itself prove DS4 will restore a
LIE checkpoint; bilateral device qualification remains pending.


## Bundled libuv 1.52.1

The HTTP event loop links the bundled static `uv_a` target by default. Configure
`-DLIE_SYSTEM_LIBUV=ON` to use system libuv instead. Headless core builds do not
link either version.

Sources come directly from [official libuv](https://github.com/libuv/libuv/tree/1cfa32ff59c076ffb6ed735bbc8c18361558661f),
commit `1cfa32ff59c076ffb6ed735bbc8c18361558661f` (tag `v1.52.1`). The
[acquisition manifest](libuv-source.json) records the archive SHA-256, every
retained file hash and every omission. The 127 retained files are unmodified:
CMake, all platform sources and public headers, package templates, version metadata, authors,
changelog and notices. Upstream tests, documentation, CI and alternative build
systems are omitted. LIE's CMake wrapper lives outside the upstream directory.

The original [LICENSE](libuv/LICENSE), [additional notices](libuv/LICENSE-extra)
and [AUTHORS](libuv/AUTHORS) are retained. LIE's first-party MIT license does not
replace those terms. The wrapper preserves upstream compiler settings while
inheriting LIE's requested sanitizer instrumentation.

## Complete MTP state binding — 2026-10-03

The MTP branch extends `adapters/gufo-state/kvc-edits.json` with eager completed
predictor pooling in scalar/batch paths and a narrow `Model` friend declaration.
`LieStateAccess` borrows the actual model-owned target/predictor readers for
identity pinning, binds predictor components to HIP storage, and translates the
adaptive controller to/from LIE's C codec. Source variants are independently
materialized from the same official pin; old qualified source/archives remain
untouched. CMake provider helpers are the current build/verification path.
The numerical kernel implementations are unchanged, but launch scheduling has
changed and needs original-weight GPU qualification. No DS4 source or sibling
workspace artifact is imported. Shared storage/cache policy stays first-party
MIT C17; upstream types remain confined to the adapter.
## Vision cache reader binding — 2026-10-03

The current `feature/vision` KVC variant adds Model friend access plus a const
projector-reader getter to the independently pinned official source. These
access-only additions expose the actual retained target/projector descriptors
inside the transitional adapter; no numerical kernels or encoder arithmetic are
changed by them. The complete-history pooling edits remain separately visible
in `adapters/gufo-state/kvc-edits.json`. Existing provider trees are preserved.
New source materialization and archive hashes are recorded by the CMake helper
in `build/provider-vision-cache-r1/BUILD-RECEIPT.json` and the
[validation receipt](../docs/development/validation/vision-cache-2026-10-03.json).
No sibling DS4/CachyOS source or artifacts were imported.

Semantic hashing and image preprocessing still use the official pinned Gufo
vision implementation. LIE owns the generic scoped cache/SSD lifecycle and the
C17 DS4 tensor/auxiliary framing. This is a transitional binding and host build,
not an autonomous encoder or numerical/performance qualification.

## Joint MTP/vision provider — 2026-10-03

The integration independently fetches official Gufo at the same recorded pin and
materializes the union of complete predictor-history and projector-reader edits.
`ModelReaders` exposes the actual target, predictor and projector only inside the
adapter. No source/artifact from DS4 or another workspace is imported; numerical
kernels remain upstream. Launch scheduling changes still require original-weight
qualification. The new private provider receipt and archive/source hashes are
bound by the [integration receipt](../docs/development/validation/mtp-vision-integration-2026-10-03.json).

## C17 vision weight decoding — 2026-10-03

`src/weight_decode.c` and its public header are first-party MIT buffer code.
The format contract is GGML Q8_0 (32 signed bytes with a little-endian F16
scale) and F16; the implementation is checked against independently fetched
official Gufo `f783fedb` quantization and vision rounding code. No DS4 project
source or artifacts are imported. Existing upstream licenses/notices apply to
the pinned C++/HIP encoder and its unchanged GPU kernels.

`adapters/gufo-state/vision-weight-edits.json` describes exact upload/admission
edits in a fresh source variant. Provider receipts bind this manifest, owned
decoder files, build selection and archives. The pristine source remains intact;
models are external and read-only. BF16 expansion occurs in memory on explicit
vision admission and does not recreate unquantized model values.

## Experimental Q2 qualification provenance

<!-- SPDX-License-Identifier: MIT -->
# Gufo provenance

`patches/gufo-q2.patch` modifies independently downloaded official Gufo
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`; its archive receipt is
`config/gufo-source.json`. Gufo's original MIT license, notice and full third-party
notice are retained here. The quantized HIP kernels retain their upstream
llama.cpp notices and formatting. Antirez material was consulted for the file
format; no antirez Qwen engine source is incorporated. No sibling project's
source, binary or cache was imported.

The patch keeps quantized expert weights, separates logical and physical down
widths, and exactly widens the small F16 HC injection matrices at load. The
standalone qualification harness is first-party MIT. Its IQ2 oracle uses the
official format codebook generated from the pinned source at build time, with
independently evaluated unpacking and dot-product arithmetic.

`experiments/q2-hc-four-wave.patch` is first-party MIT numerical work against
the same independently fetched official pin. It changes F16 HC down work
distribution without importing another engine or changing weight precision.
Its qualification harness inherits upstream numerical flags; bounded model
checks may reuse this workstream's unchanged, identity-verified MMQ archive.
The original upstream and llama.cpp notices remain applicable to that archive.

`experiments/q2-hc-prefill-wmma.patch` specializes the same official Gufo raw-F16
WMMA template for the two original Q2 HC prefill projections. It is a separate
experimental delta after the HC4 decode patch, with first-party MIT synthetic
checks and unchanged upstream arithmetic/weight formats. The source receipt
records both modified translation units and all 1019-file inventory coverage.
No antirez engine or sibling workspace source/artifact is incorporated.

`experiments/q2-compensated-down-source.patch` is the source-level delta of this
workstream's retained compensated Q2 down experiment, composed after the HC
patches. `experiments/q2-iq2-pair.patch` extends the same official routed WMMA
template to IQ2_XXS paired gate/up. It uses the codebook and parity sign tables
already present in official `mmq/ggml-common.h`; all upstream/llama.cpp notices
remain applicable. The independent synthetic fixtures and orchestration are
first-party MIT. Source reconstruction verifies every file against the actual
measured trees; hashes are in `config/q2-expert-stack-source.json`. Neither
experimental patch replaces the qualified runtime patch or imports an antirez
engine, sibling source or sibling compiled artifact.

`experiments/q2-packed-activations.patch` moves this workstream's existing
compensated activation representation into its IQ2 producer, using the same
independently fetched official Gufo templates and buffers. It introduces no
external code or new weight format. Existing upstream and llama.cpp notices
remain applicable; prepared synthetic replay fixtures are first-party MIT.
GPU operator, exact full-model replay and fresh Q2/UD performance evidence
are explicit in `docs/Q2-PACKED-ACTIVATIONS.md`. This does not promote the
experimental patch into the qualified runtime or replace its provenance.

`experiments/q2-hc-up-fused.patch` adapts the same official Gufo HC WMMA mixer
to original F16 weights and F32 normalized streams. The numerical work and
independent synthetic fixtures are first-party MIT; existing upstream notices
remain intact. The prepared source reconstructs exactly from this workstream's
packed checkpoint. No antirez engine, DS4 source or KV codec is imported.
Runtime qualification is recorded in `docs/Q2-HC-UP-FUSION.md`.

That isolated fusion has since passed GPU operator and full-model replay on
`.157`; its collected timing and identity evidence are linked from
`docs/Q2-HC-UP-FUSION.md`. `experiments/q2-hc-up-vec.patch` and
`experiments/q2-hc-up-vec-exact.patch` are separate first-party MIT deltas
against the measured fusion. They vectorize original-F16 HC up scalar reads;
the latter fixes the generated FMA order to retain exact Q2 output. Both use
the same independent official Gufo pin and existing upstream/llama.cpp notices.
The faster reassociating variant's numerical drift is retained as evidence in
`docs/Q2-HC-UP-VECTOR.md`. No antirez engine, DS4 source, sibling artifact or
external KV codec is imported.

`experiments/q2-hc-prefetch.patch` independently extends this workstream's F16
HC down kernel on the same official pin. It preserves original weight layout
and uses AMD compiler scheduling/FMA intrinsics; no external engine or artifact
is imported. First-party MIT source and existing upstream notices are retained.
It derives from the measured packed source, not the pending HC up fusion.
Static, host and GPU evidence are in `docs/Q2-HC-PREFETCH.md`.
`experiments/q2-hc-prefetch2.patch` is the separate two-group scheduling delta.
Both HC down prefetch variants are measured and rejected for performance; their
negative GPU results and complete source identity remain in that document.

`experiments/q2-hc-moe-fused.patch` derives its F32 norm mapping and expert
epilogue from the same independently fetched official Gufo source, after this
workstream's measured exact HC up vector checkpoint. It stages the MoE row in
LDS without importing UD activation precision or another engine. The generator,
GPU fixture and orchestration changes are first-party MIT; existing upstream
and llama.cpp notices remain intact. Source/static receipts and the runtime
qualification status are recorded in `docs/Q2-HC-MOE-FUSION.md`.

`experiments/q2-hc-norm-half.patch` independently extends this workstream's
measured F32 MoE/HC fusion on the same official Gufo pin. It emits the existing
F16 consumer copy alongside F32 norm, reuses the existing executor scratch,
and explicitly retains the measured gfx1151 rounding sequence. The generator,
fixture and runner extensions are first-party MIT; upstream notices remain.
No antirez engine, DS4 source/artifact or KV codec is imported. The failed first
round and corrected GPU qualification are retained in `docs/Q2-HC-NORM-FUSION.md`.

`experiments/q2-hc-down64.patch` and the three `q2-hc-down*` scheduling deltas
derive from the same measured MoE/HC source and official pin. First-party MIT
generators retain upstream notices. The 64x64 component and the three scheduling
variants are measured and rejected for performance; exact output hashes and
unchanged numerical control failures remain in `docs/Q2-HC-DOWN-TILES.md` and
persistent evidence. The component plotting tool is first-party MIT.

`experiments/q2-ple-{q2,ud}.patch` add host clocks/counters to `ngram.cpp` plus
a first-party MIT diagnostic header. They independently derive from measured
Q2 MoE/HC and pristine official Gufo, without altering executor/kernels, GGUF
bytes or quantization. Fixtures, analysis/plot tools and bounded storage observer
are MIT. The storage observer uses the independently fetched official GGUF
metadata helper; no CPU model execution or sibling project artifact is imported.
Source identities, observations and limitations are in `docs/Q2-PLE-ANALYSIS.md`.

`experiments/q2-ple-io-{q2,ud}.patch` extend those independently derived PLE
diagnostics with descriptor-local access advice and a BF16 cache-budget control.
`experiments/q2-ple-cache64k-{raw,diagnostic}.patch` isolate only the BF16 capacity
change in the measured MoE/HC source and its instrumented equivalent. All four
patches retain official Gufo provenance and notices; new fixtures, analysis,
plotting and orchestration are first-party MIT. No model data is converted or
copied, and no external engine, DS4 source or sibling artifact is imported.
Source receipts and measured limitations are recorded in `docs/Q2-PLE-CACHE.md`.

`experiments/q2-staged-weights.patch` is first-party MIT work against the same
independently fetched official Gufo pin and measured MoE/HC checkpoint. It moves
the existing Q2 affine decode into shared staging without changing the stored
format or importing another implementation. Existing upstream notices remain.
Its original-shape synthetic benchmark, generator and runner extensions are MIT;
the measured component regression is explicit in `docs/Q2-STAGED-WEIGHTS.md`.

`experiments/q2-half-wave*.patch` independently derive from that same measured
MoE/HC checkpoint and official pin. They distribute the existing affine decode
between paired lanes and exchange already-rounded F16 bits without changing
model bytes or the LDS allocation. The generator and reports are first-party
MIT; upstream notices remain intact. No external project implementation is
imported. LLVM intrinsic documentation informs the alternate exchange primitive;
source links, exact GPU replay and the measured lack of component benefit are
in `docs/Q2-HALF-WAVE.md`. The comparison plotting tool is first-party MIT.

`experiments/q2-ple-lookahead.patch` adds a validated borrowed-input boundary
to the measured official-Gufo-derived executor. Kernels and original model bytes
remain unchanged; upstream notices remain intact. The bounded C17 flow, fixtures,
original-weight harness, generator and analysis are first-party MIT. No external
engine or sibling project artifact is imported. Source and ownership contracts
are recorded in `docs/Q2-PLE-LOOKAHEAD.md`.

`experiments/q2-hc-decode{8,16,32}.patch` are first-party MIT row-partition
changes against the measured MoE/HC checkpoint and the same independently
fetched official Gufo pin. Original F16 model bytes and upstream notices remain
intact. The generator and plotting extensions are first-party MIT; no external
engine or sibling project implementation is imported. Source hashes, changed
reduction order, independent checks and complete-model scope are recorded in
`docs/Q2-HC-DECODE-WAVES.md`.

`experiments/q2-affine-palette.patch` is a first-party MIT delta against the
measured HC16 candidate and the same independently fetched official Gufo pin.
It precomputes the four existing Q2 affine values inside registers, retaining
original model bytes and upstream notices. The generator and admission changes
are MIT; no external engine implementation or sibling artifact is imported.
Source, numerical replay and measured scope are in `docs/Q2-AFFINE-PALETTE.md`.

`experiments/q2-hc-{fragment,stage}-bound.patch` are independent compiler-load
scheduling deltas against the measured affine-palette source and the same
official Gufo pin. Upstream notices, weights and arithmetic remain intact.
The generator, fresh-profile analysis, plot and runner guard changes are
first-party MIT. Both candidates are measured and rejected for performance;
their original numerical control failures remain explicit. No external engine
or sibling artifact is imported. See `docs/Q2-PREFILL-GAP.md` and its source
receipts for provenance, exact replay, limitations and artifact identities.

`experiments/q2-hc-direct.patch` and `experiments/q2-hc-chain-waves.patch`
independently derive from the measured affine palette on the same official
Gufo pin. `experiments/q2-hc-chain-coalesced.patch` applies after the paired-wave
delta. All three retain original F16 values, accumulation chains and upstream
notices. Generators, orchestration and plot tools are first-party MIT; no
external engine, DS4 source or sibling artifact is imported. The first two
candidates fail the component performance gate and the combined path fails
to improve complete-model prefill. Their exact output replays, source hashes,
original numerical-control failures and rejection are in `docs/Q2-HC-DATA-REUSE.md`.
The additional library audit reads only independently fetched official Gufo
`blaslt.cpp` and `dense_blaslt_sweep.hip`; it adds no library implementation or
performance claim.

`tests/q2_hc_pp.cpp` adds a first-party MIT hipBLASLt algorithm diagnostic using
its existing independent FP64 fixture and deterministic synthetic inputs. It
uses the official library extension API; no external benchmark source is copied.
The official Gufo helper at the recorded pin informed the workspace hypothesis,
while this diagnostic retains 100 MiB rotation, all numerical failures and
position-invariance checks. Analysis/plot tools are first-party MIT.
`experiments/q2-hc-library-down.patch` changes only the selected affine-palette
`blaslt.cpp` dispatch for F16 M320/K10240/n2048, preserving upstream notices and
original values. Algorithm index 7526 is installation-specific and exploratory;
it has not passed the declared numerical gate. No antirez engine, DS4 code or
sibling project artifact is imported. Source identity and measured scope are
recorded in `docs/Q2-HC-LIBRARY.md`.

`experiments/q2-hc-input.patch` is an independent MIT delta against the same
measured palette and official Gufo pin. It moves the existing F32-to-F16 input
rounding into HC down's load stage while retaining original F16 model values,
WMMA geometry and both accumulation chains. The source generator, fixture,
runner guards and analysis are first-party MIT. The fixture reuses this
workstream's independent HC oracle; no external test implementation or sibling
artifact is imported. Source identity, preserved numerical failures and the
component/model scope are documented in `docs/Q2-HC-INPUT.md`.

`experiments/q2-hc-up-chains.patch` derives independently from the measured
palette at the same official pin. It distributes the original raw-F16 HC up
K16 sums across wave pairs and combines them in the existing gate LDS, enabling
256x128 tiles without changing stored weights or the arithmetic contract.
The generator, added fixture, guard extensions and analysis/plot tools are
first-party MIT. The fixture reuses this workstream's independent FP64 HC
checks, adds partial tiles and repeated rows, and rotates 100 MiB of synthetic
weights. No external engine, DS4 source or sibling artifact is imported.
Source identities, numerical checks and measured scope are in
`docs/Q2-HC-UP-CHAINS.md`; upstream notices remain intact.

`experiments/q2-hc-down-wide.patch` and its `-k1` companion derive from the
retained paired-HC-up source at the same independently fetched official pin.
They generalize the existing exact wave-pair arithmetic to a wider F16 HC down
tile, with separate one/two-block staging experiments. The additional
`experiments/q2-hc-down-wide-coalesced.patch` derives from the wider BK2 tree
and changes global stage-fetch ownership while retaining the LDS layout and
ordered arithmetic. Its generator adapts this workstream's earlier contiguous
stage-read experiment. No weight conversion, external engine source or sibling
artifact is imported. The generators, source selection guards and component
plotting tool are first-party MIT. Existing
independent HC fixtures retain their original limits and failures. Source
identities and measured scope are in `docs/Q2-HC-DOWN-WIDE.md`; upstream notices
remain intact.

The routed tile fixture extends this workstream's existing MIT packed-Q2
benchmark and calls the retained official-Gufo-derived 16/48/64 dispatches.
No engine source is changed. Its analysis and plotting tools are first-party
MIT; the executed 48/64 component screen and unexecuted tile16 follow-up are
distinguished in `docs/Q2-REASSESSMENT.md`. That report also consults historical
DS4 qualification documents and result metadata read-only, as permitted
reference evidence. Their paths/hashes are in `config/q2-reassessment.json`;
no DS4 source, archive payload, compiled object or test implementation is
imported. The proposed precision-boundary comparisons are hypotheses only.

`experiments/q2-hc-single-chain.patch` independently derives a single ordered
HC down accumulator from the retained paired-up source at the same official
pin. It changes the reduction grouping, with original model bytes and input
narrowing preserved. Historical DS4 reports motivate the hypothesis only;
neither their code nor acceptance result is imported. The candidate is rejected
for component regression and additional FP64 failures, as recorded in
`docs/Q2-HC-SINGLE-CHAIN.md`. The generator, offline classification correction,
regression fixtures and plot-label extensions are first-party MIT. Existing
upstream notices remain intact and the qualified runtime is unchanged.

`experiments/q2-bitfield-isa.hip.cpp` is an independently written first-party
MIT static probe responding to the owner's representation proposal. It compares
unsigned extraction and bounded IEEE floating construction with the installed
HIP compiler; it imports no external implementation and is not a model runtime
or measured GPU benchmark. The documented retained `CodesToHalves` mechanism
belongs to the independently fetched official-Gufo-derived source. Probe
provenance and the distinction from the measured affine-palette optimization
are recorded in `docs/Q2-BIT-CONVERSION.md`.

`experiments/q2-staged-palette.patch` derives independently from this
workstream's retained paired-HC-up source at the same official Gufo pin.
It stores four rounded half weights in the previous affine metadata slot,
preserving original encoded weights, activation precision and matrix arithmetic.
It imports no external implementation, model conversion or sibling artifact.
The generator and source-selection guards are first-party MIT; upstream
notices remain intact. Exact numerical evidence and the component result are
recorded in `docs/Q2-STAGED-PALETTE.md`. The candidate supplies no measured
speed gain and is not promoted to the selected or qualified runtime.

`experiments/q2-hc-full-row.patch` derives from this workstream's retained
paired-HC-up source at the same independent official Gufo pin. It changes
only the original-F16 HC-down geometry and a bounded isolated output epilogue.
`experiments/q2-hc-half-row.patch` is the incremental 160-row geometry change
on that isolated source. Both preserve the two original accumulation chains
and all upstream notices. The generators and source-selection guards are
first-party MIT; no sibling implementation, converted model or external
artifact is imported. Neither geometry is selected after the measured
component comparisons in `docs/Q2-HC-ROW-REUSE.md`.

`experiments/q2-shared-overlap.patch` derives from the retained `hc-up-chains`
source at the same independent official Gufo pin. It changes host dispatch
and lifetime ordering while preserving all eight HIP/MMQ numerical sources.
The C17 lifecycle, HIP callback adapter, synthetic fixture, generator and
saved-evidence readers are independently written first-party MIT files.
Existing upstream notices remain intact. No DS4/core-thread implementation,
converted model or sibling artifact is imported. `docs/Q2-SHARED-OVERLAP.md`
records the bounded experiment, buffer ownership and qualification limits.

`experiments/q2-scaled-input.patch` derives from the retained independently
fetched official Gufo source. Its first-party packing include and test/report
tools are MIT; existing upstream notices remain. It changes activation
arithmetic and is numerically unqualified despite measured prefill gain.

Terminal-Bench Mini is independently fetched from
https://github.com/kyuz0/terminal-bench-mini at
07034484346dc724d0e2c47c821fd196add1d6fb. The unmodified benchmark/tasks retain
their Apache-2.0 license, NOTICE and upstream task attribution. Core-19 task
revision is 5c8eadf1f393183288fa08b8f73ca9a469cc5e00. The task-owned Harbor
0.20.0 environment retains its dependency licenses. No benchmark code is
relabeled first-party MIT. Only first-party orchestration/preparation and the
three-file serving patch use MIT. The serving base is same-repository LIE
commit ae9c34ef26b0bb12ae5c995cb2ec99131da5aefd, archived without modifying
its owner worktree; base and variant hashes are recorded. No sibling CachyOS
project source or artifact is imported. Original upstream example results
staged for runner unit tests are fixtures, never evidence of this Q2 cohort.

The paired HTTP context-curve experiment freezes the same-repository C17 core
at `15c6082152c3df0cb1f40d89ba5329692f307d7b`, including its state adapter and
MIT license. `config/q2-curve-source.json` binds all 333 core files and the
independently fetched official Gufo providers at the pin above. The measured
cumulative Q2 parent and pristine UD parent each receive the identical four-file
friend-access and optional sampling/reporting edits from that frozen core;
their numerical sources remain unchanged from their respective parents.
The optional dense C17 sampler, KVC, SSD, MTP and vision paths are disabled.
No DS4 or sibling CachyOS project implementation is imported.

The first-party composition, HTTP client, evidence analyzer and plotting tools
are MIT. The client imports official Gufo's pinned deterministic prose,
calibration and depth algorithm without copying or relabeling that code.
Original Gufo licenses and notices remain in both private source trees.
The source manifest describes preparation; measured runtime qualification is
separately recorded in `config/q2-canonical-http-results.json`. Neither the
composition nor successful serving changes existing numerical rejection.

The canonical-workload PLE profile derives from those measured provider
compositions. Its new first-party MIT header and tools add host observations
only; the copied `q2_ple_diag.hpp` is this repository's existing MIT diagnostic.
Official Gufo numerical kernels remain byte-identical to each parent. The
two source patches retain upstream licenses and are bound by
`config/q2-curve-profile-source.json`. No external implementation or artifact
is introduced by this instrumentation.

`experiments/q2-reaudit-q8-row.patch` and
`experiments/q2-reaudit-q8-row-norm.patch` compose only this workstream's retained
shared-Q8 dispatch, Q2 row-reuse packing include and two fixed-shape norm bodies
against its independently fetched official Gufo provider at the pin above.
Both preserve upstream licenses/notices and verify all 1022 provider files,
with five changed files per composition. Generators, orchestration and result
readers are first-party MIT. No external engine code or converted model is
introduced. Original numerical rejections remain retained; exact Q2 replay
and the norm composition's preserved prior numerical difference are reported
separately in `docs/Q2-REAUDIT-COMPOSITION.md`.

`experiments/q2-hc-down-bk256.patch` adapts the native vector fragment loader
and `mmb_hcd_kernel` from the independently fetched public MIT GSQHalo.cpp
commit `5fc881b114c1ea130f5df6a30a98be2f8d397de6`. The numerical include retains
the original ggml authors' copyright and full MIT license; the license is also
preserved under `third_party/gsqhalo/LICENSE`. The original public source hash
and exact derivation are bound in `config/q2-hc-down-bk256-source.json`.
LIE's adaptation keeps original F16 model/activation bytes, uses F16 WMMA and
two FP32 K16 chains, and selects only the M320/K10240 HC-down geometry. The
bounded sibling patch changes one unroll pragma. Preparation scripts and
orchestration are first-party MIT. Compilation is not numerical/performance
qualification or a claim of an independently owned model executor.

The `q2-hc-bk256-*-run.patch` runtime siblings format those retained ports
without changing noncomment source tokens. `experiments/q2_hc_blaslt_control.*`
copy the measured official-Gufo library recipe into a test-only renamed class;
the full Gufo MIT license is retained in each file. Their origin/source hashes,
limited renaming and all runtime provider files are recorded in
`config/q2-hc-bk256-run-source.json`. The new component fixture, preparation,
launch guards and orchestration are first-party MIT. Neither this copy nor
successful syntax compilation constitutes a new owned model executor.

The completed HC BK256 component/model results retain those exact source
capsules and public MIT derivation. The offline FP64 tool reconstructs only
deterministic synthetic fixture weights and reads this workstream's saved F16
arrays; it imports no model or sibling project artifact. Analysis and plotting
tools are first-party MIT. GPU performance evidence does not establish owned
executor replacement or independent model quality.

The BK128 candidates change only two launch-template parameters in that same
attributed include; no additional source is imported. Saved device objects,
standalone analysis and plots retain the failed numerical exits alongside
actual performance. Their FP64 checks use synthetic fixture operands and
do not stand in for an original-model teacher.

The compact-expert-chain experiment derives only from the retained scaled-wave-pack
provider and its independently fetched official Gufo pin
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`. It copies the attributed routed HIP
bodies into a private include and changes row addressing, retaining original
quantization and WMMA arithmetic. Its source manifest binds all1028 files and
the four-file patch. New orchestration, fixtures and analysis are first-party
MIT. No sibling DS4/CachyOS source or artifacts are imported; this remains a
transitional numerical port, not an owned C17 executor or quality acceptance.

HC raw-Q8 injection experiment: `tools/prepare-q2-hc-inject-raw-q8.py` derives a private 1030-file provider from the retained independently fetched Gufo pin f783fedb9bea2ec7de941f6da4e02f4a4596b29e and the measured IQ2 fixed-bound parent. It reuses the original numerical bodies in `experiments/q2-hc-inject-reuse-draft-v3.inc`; their recorded finite injection differences remain. The new allocation identity/capacity policy is first-party C17 MIT. No DS4 or sibling-workspace source/artifacts are imported.

Fixed Q2 down experiment: `tools/prepare-q2-down-fixed-bounds.py` derives the guarded m2560/k640 selector and private constant-bound kernels from the retained official-Gufo provider. Original affine/WMMA/inverse/half arithmetic and literal half-output controls are retained. The source binding pins the donor, standalone draft, integrated source and generator; no sibling workspace or DS4 code is imported.
