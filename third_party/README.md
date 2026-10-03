# Provenance and dependency boundaries

First-party runtime, tools, tests, ABI and adapter use MIT (`../LICENSE`). The
owned dense sampler is an attributed C17 port of independently fetched official
Gufo, with its [MIT notice](gufo-NOTICE) and [license](gufo-LICENSE) retained.
No sibling DS4/CachyOS project sources, recipes,
configs or binaries were imported. Read-only inventory/qualification observations are
historical evidence, not a copied backend. Model files remain external/read-only
under their publisher's terms. A C API wrapper does not relicense its dependencies.

## Actual external dependencies

| Component | Observed version/pin | License / use |
|---|---|---|
| libuv | 1.52.1 | MIT and component notices; event loop/network lifecycle |
| llhttp | 9.3.1 | MIT; HTTP/1 parser |
| json-c | 0.19 | MIT; JSON serialization/parsing |
| libcurl | 8.21.0 | curl license; monitor and optional upstream image-helper link dependency (images not exposed) |
| Gufo | f783fedb9bea2ec7de941f6da4e02f4a4596b29e | MIT + upstream component notices; opt-in HIP-linked transitional Model/Session adapter; bounded original-weight smoke passed, numerical qualification open |
| ROCm / HIP | 7.2.53211 compiler/runtime observed locally | AMD/upstream component licenses; hipBLAS, hipBLASLt, rocBLAS, hipCUB/rocPRIM; already installed |
| ICU / OpenSSL / PNG / JPEG | selected installed development libraries, CMake/ELF receipts authoritative | their respective upstream licenses; tokenizer/crypto and coupled upstream helpers |

libuv is bundled as described below. The other libraries are system dependencies.
Build receipts record compiler/pkg-config versions. A distributable package will
need its normal dependency-license audit; this increment installs/publishes none.
CMake verifies the provider sources and archives. HTTP benchmark clients and
CSV/JSON/SVG/PNG exports are first-party C17 code; PNG encoding links libpng.
Python is used only by explicitly selected legacy test oracles and historical
development/qualification scripts, outside the normal build and runtime.
The optional `tests/sampling` cost/allocation project compares the pristine
official sampler with generated LIE ON/OFF variants, without HIP or model
forward. Its first-party C++20 QA probes link ICU and libm; allocation hooks
belong only to separate untimed probes. Runtime dependency scope is unchanged.
The new first-party C17 SSD codec/identity/store also uses installed OpenSSL
Crypto SHA-256. No upstream snapshot codec or disk-cache code was imported;
upstream source/archive pins are unchanged by this increment.

## Gufo source acquisition

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
and tests; none is implemented yet. Keep the pristine reference separate from
instrumented/forked experiments and ports. First-party ownership of orchestration
does not relicense numerical code or make embedded Model/Session a reimplementation.

## Native server tools

`src/chat_tools.c` and `src/tools.c` are first-party C17 protocol code, not copied
from DS4 or Gufo's serving frontend. `adapters/gufo_chat.hpp` translates LIE data
into the existing independently fetched Qwen template API at `f783fedb`; no new
ChatML/tool prompt or numerical implementation is substituted. Upstream template
provenance/notices remain applicable. Pi is an optional external client, using its
standard OpenAI provider and normal JSON configuration; no extension or Pi source
is bundled/modified. Tool-frame tests and CPU/Pi fixtures are not model qualification.

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


The optional default-ON checkpoint codec links installed C libraries: Zstandard
under its [BSD-3-Clause option](zstd-NOTICE), plus [LZ4 BSD-2-Clause](lz4-NOTICE)
for legacy decoding. No library source is copied or installed by LIE. Disabling
`LIE_CHECKPOINT_COMPRESSION` removes both dependencies. The byte permutation,
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
