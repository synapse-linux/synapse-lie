<!-- SPDX-License-Identifier: MIT -->
# Changelog

User-visible changes are recorded here. This branch is under development; no
stable release is declared. Detailed validation history is in
[development progress](docs/PROGRESS.md).

## Unreleased

- Shared C17 JSON binary64 formatting and parsing, preserving number spelling,
  negative zero and nearest-even rounding. Bundled pinned Ryu adds no system
  dependency; MPFR is used only by optional developer tests. The matching
  composition/codec build passes 37 original-weight OpenAI controls in both AR
  and MTP on Strix Point; individual numerical branches and cost remain open.

- Shared C17 immutable reasoning/tool grammar composition, including marker
  transitions, argument imports, JSON name quoting and parallel-call stop policy.
  Original/default-ON/OFF complete states and masks agree in host checks;
  matching original-weight AR/MTP controls pass. Broader branch/resource/cost
  qualification remains open.

- The matching 66-file C17 provider/application build passes 37 original-weight
  OpenAI controls in both AR and MTP on Strix Point. These qualify selected
  integrated paths; individual numeric/format branches, faults and cost remain open.

- Shared C17 ordered cache policy for reasoning and tool grammars, including
  duplicate reuse, synchronization and bounded eviction. Typed provider keys
  remain private. Matching selected AR/MTP controls
  pass; individual branch, resource and cost gates remain pending.

- Shared C17 JSON Schema format expansion for the nine existing formats,
  including ordered IPv6 patterns and hostname bounds. Original/OFF patterns,
  prefix decisions and intersections agree in host checks. The matching build
  passes selected AR/MTP controls; individual format GPU branches remain pending.

- Shared C17 numeric schema control for ordered constraints, scalar acceptance,
  exact `multipleOf` representability and literal construction. Host checks
  preserve original/OFF behavior; the binary64 codec remains private. Matching
  selected AR/MTP controls pass; independent numeric GPU gates remain pending.

### Added

- Optional developer GPU qualification for bounded-integer schemas, with 66
  separate Chat/Responses JSON/SSE membership and refusal checks. HOST wire and
  supervision tests pass; original-weight execution remains pending.

- Shared C17 signed integer-bound compilation, preserving exact large integer
  magnitudes, exclusive endpoints and `-0`. Original/default-ON/OFF HOST grammar
  witnesses agree; matching HIP ON/OFF builds and selected original-weight
  AR37/MTP37 controls pass on Strix Point. Individual branch and cost
  qualification remain open.

- Shared C17 schema compilation publication and immutable prompt ownership.
  Reasoning and tools share the exact prompt bytes; failed compilation publishes
  no output. HOST lifetime, allocation-failure and original/ON/OFF checks pass.
  The matching HIP build passes 37 selected original-weight OpenAI controls in
  both AR and MTP on Strix Point. Typed construction/bootstrap/errors and
  model/controller remain transitional; broader quality and cost stay open.

- Shared C17 ownership and limits for derived schema values and transformation
  staging. Results transfer their exact roots without cloning and survive staging
  retirement. HOST lifetime and complete original/default-ON/OFF comparisons pass;
  the matching HIP build passes 37 selected original-weight OpenAI controls in
  both AR and MTP on Strix Point. Existing C17 option preserves the original
  OFF compiler path; broader quality, resource and cost gates remain open.

- Default-ON immutable grammar programs no longer duplicate C tables into C++
  rule/class containers. HOST state/mask and lifetime checks pass; matching HIP
  ON/OFF builds pass 37 selected GPU OpenAI controls in both AR and MTP on Strix
  Point. Existing public ABI, reactive workers and cache
  formats are retained; original OFF behavior remains available.

- Shared C17 root schema admission, including reference-cycle detection and
  ordered root construction. Bounded temporary identity storage retires before
  compilation callbacks. Original/OFF behavior is retained; the matching
  96-file HIP build passes 37 selected original-weight OpenAI controls in each
  AR/MTP mode on Strix Point. Broader qualification and performance remain open.

- Shared C17 ownership of request grammar snapshots and independent speculative
  copies. Runtime transitions and masks use native snapshots directly, removing
  repeated C++ vector/string transfers. Host original/default-ON/OFF states and
  masks agree; the matching 93-file HIP build passes 37 selected original-weight
  OpenAI controls in each AR/MTP mode on Strix Point. Broader qualification
  and performance remain open.
  The original OFF path and existing reactive worker/cache contracts remain.
  The Gufo comparison executable uses a separately verified complete OFF
  provider to preserve its private model/controller layouts.

- Shared C17 immutable primitive ownership, ordered predicate tables and a
  construction-only schema identity memo. Runtime grammar dispatch calls the
  C numeric/string/DFA algorithms directly. Host original/default-ON/OFF
  witnesses agree; the matching 92-file HIP build passes 37 selected
  original-weight OpenAI controls in each AR/MTP mode on Strix Point.
  Broader branch, fault, quality, resource and cost qualification remains open.
  Existing reactive scheduling, cache format and original OFF paths remain.

- Shared C17 typed JSON ownership, including exact string/key bytes, ordered
  object/array storage, transactional copies/moves, parsing and serialization.
  Private C++ references and synchronized string projections preserve existing
  callers. Original/default-ON/OFF host witnesses agree. The matching 89-file HIP
  build passes 37 selected original-weight OpenAI controls in each AR/MTP mode
  on Strix Point. Broader fault/resource/quality/cost gates remain open.
  No dependency or runtime thread is added; the original OFF implementation
  remains available.

- Shared C17 complete JSON parser with ordered events, strict UTF-8/escape
  decoding, decoded duplicate-key detection and bounded allocation/work.
  Original/default-ON/OFF host trees and errors agree. The matching build passes
  37 original-weight OpenAI controls in each AR/MTP mode on Strix Point;
  broader fault/resource/quality/cost qualification remains open.

- Shared C17 JSON Schema body policy for definitions, references, `anyOf` and
  `enum/const`, with preserved validation order and lifetime/refusal checks.
  Default-ON and original OFF host grammars agree. The matching schema
  memo/dispatch/Visit/body build passes 37 original-weight OpenAI controls in
  both AR and MTP on Strix Point; broader branch, fault and cost gates remain open.

- Shared C17 recursive schema Visit sequencing, including identity hits,
  placeholder publication and empty branches. Default-ON and original OFF
  paths retain host grammar behavior; selected matching AR/MTP GPU controls pass.

- Shared C17 JSON Schema type/nullable/keyword validation and ordered branch
  dispatch. The default-ON provider retains original OFF bodies; host language
  and refusal comparisons cover nested schemas. Selected AR/MTP GPU controls pass.

- Shared C17 per-compilation schema reference memo with bounded storage,
  recursive placeholders and allocation accounting. Default-ON and original
  OFF paths pass host recursion/lifetime/refusal comparisons and selected
  matching AR/MTP GPU controls.

- Original-weight Terminal Bench Core-19 smoke qualification on Strix Point:
  1/1 unchanged task passes at the first attempt, with portable score/transcript
  and verified CPU/GPU closure. The full 19-task evaluation is stopped at the
  owner's request and deferred until functional modifications are finished;
  cancelled logs and actual machine closure are retained.

- Original-weight Strix Point 1M capacity/function qualification: complete
  physical prefill and fixed 128-token generation, with raw evidence, phase
  durations, memory and reproduction instructions. Recall and matched
  long-context performance comparisons remain pending.

- Shared C17 compiled-schema cache with copied keys, bounded opaque values and
  concurrent access. Compilation stays outside its lock; the default-ON
  provider retains an OFF reference. Host cache/ownership/refusal comparisons
  and matching GPU OpenAI AR/MTP controls pass; broader branch, fault and
  matched cost checks remain pending.

- Shared C17 finite JSON value filtering/canonicalization, string/key quoting,
  ordered object/array rules and bounded character accounting. The default-ON
  provider retains an OFF reference. Host language/refusal checks and matching
  GPU OpenAI AR/MTP controls pass; broader numerical, fault and cost gates remain
  pending.

- Shared C17 JSON Schema conjunction, local reference resolution, structural
  value equality and keyword validation. The default-ON selection retains an
  OFF reference. Provider JSON storage and format/binary-double leaf policy
  remain transitional; GPU correctness, resources and cost remain pending.

- Shared C17 grammar construction, JSON byte primitives, decimal-prefix
  intervals, productivity/cycle validation and dead-alternative pruning.
  Schema dispatch/caching and provider composition templates remain transitional;
  host language/lifetime checks pass, while GPU resources/cost remain pending.

- Shared C17 snapshot read/write bridge with bounded import, staged export,
  capacity and overlap validation. Provider container views/growth preserve
  its existing private layout; callbacks retain no input/context. Host
  copy/refusal comparisons pass; original-weight resources/cost remain pending.

- Reusable C17 Unicode-set registry and UTF8 input handling through public ICU
  C APIs. The default-ON module preserves full-set identity, supplementary/NUL
  input and replacement decoding. ICU remains the set/property/conversion
  dependency; minimal core builds can omit the module. Host comparisons pass;
  original-weight resources/cost and ICU internal faults remain unqualified.

- Shared C17 string/Unicode-DFA runtime: UTF8, JSON escapes, surrogate pairs,
  pending ranges, length reachability, cycle skipping, copied mask keys and
  bounded whitespace. Temporary compiler tables are retired after C sealing.
  Default ON retains an OFF reference; original-weight resources/cost remain pending.

- Shared C17 exact-decimal numeric grammar policies, prefix matching and
  `multipleOf` intersection. The default-ON sampler selection retains an OFF
  reference. Host rational and complete prefix/value/LCM checks qualify the
  algorithm; original-weight continuation/resources/cost remain pending.

- Shared C17 byte-grammar runtime and dense/compact mask application, with copied
  immutable tables, bounded owned snapshots and allocation/refusal checks. The
  default-ON sampler option selects it; OFF retains Gufo runtime methods. Host
  state/mask comparisons pass. Schema/predicate/trie/cache extraction and GPU
  correctness/resources/cost remain pending.

- Shared C17 compact probability distributions, p-q residual correction and exact
  host MTP proposal/verification arithmetic. Caller-owned storage and refusal
  checks preserve RNG/results. The default-ON sampler option selects the port;
  OFF retains Gufo numerical behavior. GPU correctness and cost remain pending.

- Shared C17 sampler history for prompt-tail repetition and full committed-token
  frequency/presence counts, with independent copying and transactional refusals.
  The default-ON sampler option selects it in the provider; OFF retains Gufo
  bookkeeping. Host/reference checks pass; GPU correctness and cost remain open.

- Experimental initial directional-steering controls shared by server and native
  core bench: `--dir-steering-file`, `--dir-steering-ffn`, `--dir-steering-attn`.
  Admission and bank resources stay in the C17 core; reports refuse matched
  comparisons with different banks/scales. Host tests pass; numerical GPU
  quality/performance qualification remains pending.
- Native `--dir-steering-plan` changes at exact retained physical positions,
  prefill/MTP boundary enforcement and strict applied-plan report identity.
  HTTP requests accept `dir_steering_plan`; stored requests expose asynchronous
  `/steering` controls with admission tickets, confirmed policy and plan results.
  `/steering/{choice}` controls independent choices and retains charged snapshots.
  Host qualification only.
- Asynchronous per-job steering changes in the shared C17 core, with bounded
  admission, completion tickets and mixed-history RAM/SSD scopes. The provider
  source invalidates graphs and MTP controller/proposal scratch while preserving
  retained state and sampled corrections. Host tests pass; GPU gates remain open.
- C17 history-aware steering prefix-state binding for RAM/SSD, including scoped
  text lookup and predictor/vision composition. Direction history is validated
  before model transfer; inactive unused directions keep legacy DS4 framing.
- Optional original-weight output-budget qualification checks model limits and
  actual generation past 128 tokens with omitted/null limits in JSON and SSE.
  The server and native benchmark gain no Python dependency.

- The shared C17 steering library prepares bounded scale transactions and
  derives cache identities from retained target history, including steering
  switched off after earlier use. Original-weight qualification remains pending.

- Shared C17 direction-bank loading with geometry/budget checks, immutable
  references and file/shape identities. Provider steering and client controls
  remain under development.
- Shared-core top-k/min-p controls in Chat, Responses and the native benchmark.
  Paired reports reject different filter settings and accept historical disabled
  filters. Generation/request ABI callers must rebuild; greedy defaults remain.
- Optional GPU qualification forwards explicit sampling profiles to the native
  core bench and requires matching typed result settings.
- Native core benchmark progress on stderr with `--progress-ms`, reporting
  completed prefill, cache reuse and confirmed/consumer-observed output. Paired reports
  require matching progress policy; benchmark samples remain separate.
- Optional Point qualification verifies declared native progress intervals and
  matches retired final observations to completed job counts and phase timings.
- Optional original-weight HTTP qualification controls for 2/8 choices,
  probabilities, structured output and retained Responses lifecycle, with
  pinned helpers and independently recorded AR/MTP outcomes. All 34 corrected
  AR and MTP GPU checks pass for the frozen r11 runtime; the earlier
  foreign-client refusal is retained separately.
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

- Regex syntax parsing and assertion expansion now use the shared C17 core,
  retaining lookaheads, bounded nesting and the original refusal messages.
  The default-ON selection keeps an OFF control. Unicode-set/property storage
  and UTF8 decoding remain provider glue; GPU correctness and cost remain pending.

- Regex expression simplification, iterative derivatives, Unicode partitioning
  and DFA construction now use the shared C17 core. The default-ON sampler
  selection retains an OFF reference. Regex syntax/Unicode properties and JSON
  Schema parsing remain in the provider; GPU correctness and cost remain pending.

- Token vocabulary tries, grammar mask traversal, transition interning and shared
  mask-cache policy now use the model-neutral C17 core. Matching provider and
  application rebuilds are required. Default selection remains ON, with the
  provider control available at compile time; GPU cost qualification is pending.

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

- Native HTTP benchmark deadlines now allow up to 24 hours. The long-context
  preset defaults to four hours, covering the recorded 1M prefill that exceeded
  the former two-hour client maximum. Ordinary workload defaults are unchanged.

- Optional steering qualification now accepts valid zero-acceptance MTP runs
  while requiring actual drafting and exact confirmed output parity. Strix Point
  passes selected malformed-bank and absent/zero/fresh-core recovery controls;
  the initial QA failure is retained, with no runtime or dependency change.

- SSD text-prefix restoration when a saved spelling uses more tokens than a
  fresh tokenization. Rebuild the saved history before checking its physical
  frontier, while preserving scheduled steering boundaries and cache scopes.
  Selected original-weight AR/MTP restart cases now restore the exact complete
  prompt with zero prefill and matching outputs
  ([qualification](docs/development/validation/ssd-text-restart-point-gpu-2026-10-06.json));
  selected scheduled SSD cases also preserve physical indices and matching
  AR/MTP outputs ([qualification](docs/development/validation/steering-physical-index-point-gpu-2026-10-06.json)).

- Optimized C17 schema-body compilation with strict warnings. Release test
  executables now retain their assertion checks; production flags are unchanged.

- Gufo adapter compilation with the C17 distribution bridge and live steering:
  provide its private bridge-header include path and fully initialize the
  steering snapshot without relaxing compiler warnings.

- Omitting an HTTP output limit, or passing null, now uses the remaining context
  up to the existing 4,096-token engine ceiling instead of silently defaulting
  to 128. Explicit positive budgets remain exact. Models advertise their context
  and output limits; responses retain the resolved budget. Request ABI 8 callers
  must rebuild; executor and generation ABI 3 are unchanged.

- Native core benchmarks can explicitly continue past EOS with `--ignore-eos`
  for fixed-token measurements. Results retain the EOS policy, refuse unmatched
  policies and reject incomplete fixed-budget output. Normal serving keeps EOS.

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
