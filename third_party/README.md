# Provenance and dependency boundaries

First-party runtime, tools, tests, ABI and adapter: independently written for
synapse-lie, MIT (`../LICENSE`). No DS4/CachyOS project sources, recipes, configs
or binaries were imported. Read-only inventory/qualification observations are
historical evidence, not a copied backend. Model files remain external/read-only
under their publisher's terms. A C API wrapper does not relicense its dependencies.

## Actual external dependencies

| Component | Observed version/pin | License / use |
|---|---|---|
| libuv | 1.52.1 | MIT and component notices; event loop/network lifecycle |
| llhttp | 9.3.1 | MIT; HTTP/1 parser |
| json-c | 0.19 | MIT; JSON serialization/parsing |
| libcurl | 8.21.0 | curl license; monitor HTTP client only |
| Gufo | f783fedb9bea2ec7de941f6da4e02f4a4596b29e | MIT + upstream component notices; optional compile-checked C++ boundary |

Libraries are already installed system dependencies, not vendored/repackaged.
Build receipts record compiler/pkg-config versions. A distributable package will
need its normal dependency-license audit; this increment installs/publishes none.
Python is a development/test helper, not an inference dependency.

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

The first attempted codeload URL did not match the recorded GitHub API tarball
hash and was rejected without extraction. The exact API URL then matched the
expected archive. That refusal was not worked around by relaxing the hash.

## Research only — no code imports or assumed compatible checkpoints

- DS4: inherited stable reference `c05cd8e2bd35047196d95709f89d0ea2aff96df2`;
  modified port numerical baseline `982bffea86fd5568759a420c4808c5b2123161c8`.
  Cache/session/conversation lessons only. The DS4 agent owns integration there.
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
