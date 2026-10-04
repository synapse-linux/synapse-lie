<!-- SPDX-License-Identifier: MIT -->
# Changelog

User-visible changes are recorded here. This branch is under development; no
stable release is declared. Detailed validation history is in
[development progress](docs/PROGRESS.md).

## Unreleased

### Fixed

- Retained background responses accept closed output demand while numerical
  teardown is pending, preserving generation after a stream disconnect instead
  of cancelling at the final token.
- Optional qualification staging can explicitly verify a filesystem device
  renumbering after reboot against boot ID and filesystem UUID, preserving
  pinned model receipts and all other file identity checks.
- Strict JSON function frames now stream exact argument fragments once the
  complete function name is known, including nested and escaped JSON values.
- Explicit smaller prefill chunks now bound provider scratch allocation while
  preserving space for admitted decode and MTP rows. The default stays 2,048.

- The Point GPU supervisor recognizes an already observed owned process while
  its `/proc/fd` entry retires before the kernel KFD list, checking PID start
  tick and container cgroup before allowing the short retirement gap.

- The direct-core reactive probe waits for aggregate retirement counters after
  job completion, avoiding a race between independently published snapshots.

- Shared-core benchmark reports refuse zero-time executed phases, inconsistent
  dispatch counts and phase durations outside the job's wall time, including warmups.

- Benchmark comparisons keep both series visible in every category when their
  values coincide; data and vertical scales are unchanged.

- Qualification supervisors apply temperature stops to the CPU and SSD;
  GPU temperatures remain recorded without a software temperature stop.
- Removed the retired LZ4 checkpoint codec and its build/link dependency;
  current compressed checkpoints use Zstandard. Historical reports retain
  their original codec label as provenance.

- Combined benchmark CSV duration columns now explicitly use seconds.

- Qwen prefix-cache geometry now includes an explicitly loaded MTP predictor
  when the trunk GGUF metadata has no embedded predictor block.

### Added

- Native core benchmark progress on stderr with `--progress-ms`, reporting
  completed prefill, cache reuse and confirmed/consumer-observed output. Paired reports
  require matching progress policy; benchmark samples remain separate.
- Optional original-weight HTTP qualification controls for 2/8 choices,
  probabilities, structured output and retained Responses lifecycle, with
  pinned helpers and independently recorded AR/MTP outcomes. All 34 corrected
  AR GPU checks pass; the MTP gate remains pending after foreign-client refusal.
- Shared-core incremental function starts and argument fragments, projected
  into Chat/Responses SSE and retained stream replay. Calls commit only after
  full validation; cancellation preserves borrowed payloads until release.
- Function `allowed_tools` subsets for Chat and Responses, with explicit
  rejection of unknown or duplicate references.

- Explicit native/YaRN2/YaRN4 context profiles in the shared C17 core, HTTP
  server and direct benchmark, with capacity up to 1,048,576 physical tokens
  and profile-specific cache identity. Extended GPU fit and quality are pending.

- A supervised Strix Point cold HTTP context campaign compares original-weight
  LIE and official Gufo AR/MTP through near 256K with two full-prefill
  repetitions per engine, physical-token/cache validation, draft acceptance,
  TTFT/wall timing, resource samples, sealed raw evidence and offline
  regeneration of CSV/JSON/SVG comparisons.
- Native `http-curve` benchmark reproduces the pinned Gufo cached-conversation
  depth protocol: exact seeded prompts, token calibration, actual prefix replies
  and bounded retries. Execution and validated CSV/JSON/SVG/PNG reports require
  no Python; failed or incomplete curves cannot produce averages.

- Native C `http-multi` benchmark for prepared C1/2/4/6/8 HTTP cohorts, with
  pinned Gufo prose/repetition prompts, complete-stream validation and four
  graph panels separating prefill, server decode rates, wall throughput and TTFT.

- Direct-core `--reactive-probe` checks peer progress during a held output loan,
  full loan stability across cancellation, and retirement. It is a functional
  check, separate from throughput benchmarks.
  Strix Point AR and 8K MTP gates pass; the short zero-acceptance MTP gate
  remains a recorded failure. Direct AR and MTP+vision retain exact token parity.

- Explicit `gfx1150` Strix Point support, with provider target verification and
  paired GPU benchmark results grouped on the platform page.

- Shared-core benchmark controls for temperature, top-p, a reproducible seed and
  frequency/presence penalties, with parameter validation and matched-report checks.

- Native benchmark prefill/decode durations in CSV and JSON, with monotonic
  phase bounds for telemetry correlation and validation of incomplete or
  contradictory clocks. Retained evidence without clocks remains readable.
- Shared C17 F16/Q8_0-to-BF16 weight decoding and Qwen vision upload support.
  The default-ON build option preserves the BF16 GPU kernels and leaves model
  files unchanged. Original-weight HTTP, image/cache and combined RAM/SSD
  checkpoint checks pass; quality and performance qualification remain open.

- Shared C17 dense sampler for greedy selection, penalties/bias, top-k/top-p/min-p
  and reproducible random draws, with a default-ON build option and a separate
  Gufo control. Original-weight functional controls pass at the recorded
  checkpoint; optimized sampler performance qualification remains open.

- OpenAI generation controls: stop sequences across token boundaries, multiple
  Chat choices, token bias, log-probabilities, JSON object/schema constraints
  and strict function arguments.
- Shared C response records, bounded RAM retention, Responses retrieval/deletion,
  conversation continuation, background cancellation, stored Chat operations
  paginated/filterable input/message lists, automatic conversation truncation
  and resumable Responses streams.

- Shared C17 semantic output events for text, progress, validated function calls
  and typed turn completion, consumed by HTTP, Responses and the direct benchmark.
  Tool policy and UTF-8 decoding now belong to the core; confirmed-token credits
  and cancellation apply to the same output loans.

- Typed auxiliary checkpoint components in the shared C17 RAM/SSD store, with
  budgets, integrity checks and unchanged DS4 payload bytes.
- Qwen MTP predictor tensors, residual/kept hidden state and adaptive-controller
  codec and device binding; RAM/SSD admission uses complete model capabilities
  and an identity covering the actual target/predictor files and draft policy.

- Experimental model-neutral [MTP core and HTTP path](docs/development/MTP.md),
  with explicit predictor admission, bounded verified output and default-ON build support.
- Vision cache reuse through the shared core: image semantics and MRoPE validation,
  default RAM retention and optional SSD restart with caller-supplied matching images.
  Original-weight image/cache and process-restarted checkpoint checks pass;
  quality and performance qualification remain open.

- Joint MTP/vision admission in the shared core, HTTP server and benchmark client,
  with predictor/controller, prepared image scope and MRoPE in one RAM/SSD checkpoint.
- Experimental model-neutral [vision core and HTTP path](docs/development/VISION.md),
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

- Retired the LZ4 checkpoint reader and dependency. Raw checkpoints, Zstandard
  compression and the exact DS4 runtime payload format remain supported.

- C17 ranked sampling uses bounded introsort, and linear selection avoids a
  repeated maximum scan. Mask-free greedy and probability compaction have
  separate loops. Host witnesses match the controls; remaining cost
  regressions and sampled GPU qualification are documented in the sampler guide.

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

- MTP text output uses a UTF-8 buffer sized for the admitted burst, including
  full-size token pieces, rather than a single-token HTTP buffer.
- Semantic completion waits for numerical/cache retirement. Parallel-tool policy
  is copied into the shared request and invalid turns fail before publishing calls.
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
  AMD Strix Halo. MTP, vision and their combined RAM/SSD path have native
  sanitizer coverage and link to HIP; original-weight qualification remains open.
  Additional real model families and 1M context remain future work.
- The numerical backend still uses the embedded Gufo C++/HIP provider.
- Published benchmark coverage does not yet include the exact Gufo HTTP
  concurrency protocol, cold-file readiness or allocation-exact peak HIP memory.
- Arbitrary DS4-produced checkpoint imports and cross-quantization reuse are
  not independently qualified.
