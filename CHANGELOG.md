<!-- SPDX-License-Identifier: MIT -->
# Changelog

User-visible changes are recorded here. This branch is under development; no
stable release is declared. Detailed validation history is in
[development progress](docs/PROGRESS.md).

## Unreleased

### Added

- Experimental model-neutral [VISION core and HTTP path](docs/development/VISION.md),
  with default-ON build option, explicit model configuration and native client tests.

- OpenAI-compatible Chat Completions and stateless Responses endpoints, with
  JSON/SSE output, function calls and correlated tool results.
- Direct HTTP access for Pi using its standard OpenAI provider.
- A shared C17 engine for the server and benchmark client, with reactive
  scheduling, cancellation, metrics and native GPU decode batches of up to
  eight sequences.
- `synapse-lie-bench` suites for context depth, concurrent users, full prefill,
  shared-core execution and HTTP requests, plus CSV/JSON and SVG/PNG exports.
- RAM prefix caching and optional SSD checkpoint persistence, with bounded
  budgets and DS4-style retention policy.
- DS4 Qwen runtime payloads for RAM and SSD checkpoints, plus KVC inspection
  and interchange codecs.
- Build and usage guides, a benchmark guide, and results grouped by model and
  platform with tables and graphs on the same page.

### Changed

- Build verification, HTTP benchmark clients and CSV/JSON/SVG/PNG reports run
  without Python. Provider helpers use CMake; benchmark tools use C17 and libpng.
- Default tests use native fixtures. Historical Python oracles remain available
  through explicit `LIE_LEGACY_PYTHON_TESTS=ON`.
- Cache options now use an explicit `--kv-*` namespace, including DS4's
  `--kv-disk-dir`, `--kv-disk-space-mb` and checkpoint-boundary controls.
  `--model-*` is reserved for model controls, including future weight storage.
  Existing cache option names remain accepted as aliases.
- The HTTP benchmark declares the remote server's cache configuration with
  `--server-kv-cache off|on|unknown`; the old `--cache-policy` alias still works.
- The HTTP context ceiling is 262,144 tokens for the supported Qwen provider.
- RAM retention defaults to a lazily allocated 4 GiB budget. SSD persistence
  remains an explicit runtime option.
- libuv 1.52.1 is bundled and linked statically by default. Set
  `LIE_SYSTEM_LIBUV=ON` to use a system library instead.
- User documentation now separates setup and usage, benchmark results,
  technical contracts and historical development records.

### Fixed

- Reusable input checkpoints are protected from generated-state captures under
  RAM and SSD pressure. CPU and sanitizer checks pass; the separate GPU
  performance comparison remains pending.
- Benchmark graphs no longer require Matplotlib or adjacent helper scripts.
- Comparison plots align reference values by workload even when the reference
  file lists the workloads in a different order.
- Direct benchmark throughput charts use zero-based axes, preventing large
  prefill rates from appearing close to zero.
- Concurrency results distinguish LIE native batching from the earlier serial
  implementation and identify historical Gufo measurements explicitly.
- Core benchmark samples expose skipped cache captures, SSD eviction and error
  counters, including final drained store accounting.

### Known limitations

- Inference on this branch is qualified for Qwen3.8 Flash Next UD-Q4_K_XL on
  AMD Strix Halo. The new VISION path is CPU-contract tested and HIP-linked,
  but original-weight qualification and complete RAM/SSD state remain open.
  Additional real model families, combined MTP/vision and 1M context remain future work.
- The numerical backend still uses the embedded Gufo C++/HIP provider.
- Published benchmark coverage does not yet include the exact Gufo HTTP
  concurrency protocol, cold-file readiness or allocation-exact peak HIP memory.
- Arbitrary DS4-produced checkpoint imports and cross-quantization reuse are
  not independently qualified.
