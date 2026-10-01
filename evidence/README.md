# Local verification evidence

Generated evidence is retained here but excluded from publication by default
(private machine paths and environment observations). Source/provenance/model
identity manifests needed for development are separately versioned.

- `inventory-157-r1.json`: read-only hardware/metadata/receipt inventory; script
  `tools/inventory.py`. No GPU probe, no tensor payload hash.
- `coordination-check-r1.txt`: dated isolation/service/lease/binary-stat probe.
- `contracts-receipt.json`, `reference-inspection-r1.json`,
  `prometheus-source-receipt.json`: upstream doc pins/content hashes and failures.
- `configure-*/build-*/test-*r1.log`: early CPU build/test outputs retained.
- `cpu-closure-r{1,2}/{result,inputs-before}.json`, numbered logs: verification
  commands and actual exit codes, GCC/Clang/sanitizer/adapter checks. r2 follows
  the final portable semantic-comparison review; r1 is preserved.
- `reactive-initial-r1/`: first focused CPU flow build/test, commands and exits.
- `reactive-closure-r1/`: all five CPU suites with GCC/Clang and ASan/UBSan,
  adapter header check, source/provenance and binary hashes. Inspect result.json
  before claiming success. Reactive tests are synthetic byte-frame/lifetime
  checks, not HTTP/SSE inference or GPU scheduling tests.
- `backend-scope-r1/`: CPU suite and guarded reference-only object compilation
  after the autonomous-backend scope correction; not backend implementation.
- `backend-reference-refusal-r1/`: unmarked adapter compilation must fail with
  the explicit reference-only diagnostic; original compiler status is retained.
  The earlier adapter receipts are historical, not reimplementation evidence.
- `backend-evolution-r1/`: CPU suites and adapter header check after permitting
  explicit transitional integration and adding the pure-inference investigation
  plan. Not an inference implementation or benchmark.
- `adapter-opt-in-refusal-r1/`: current guard rejects unmarked compilation; raw
  compiler status/diagnostic retained. Superseded reference-only receipts remain
  unchanged, not retroactively reinterpreted under the new policy.

- `gufo-host-r1/`: complete upstream CMake configuration failed on missing
  rocWMMA; exit 1 retained, no dependency installed.
- `gufo-qwen-host-r{1,2}/`: private, serial, local HIP archive builds over unchanged
  source; Qwen-only scope, not upstream release binaries or inference. r2 adds
  the real upstream sample unit missing from the initial link closure.
- `t0-runtime-r1/`: first eight-suite GCC/Clang/ASan/UBSan CPU/synthetic pass.
- `t0-linked-r1/`: link failure (upstream argmax/sample unit and curl dependency),
  with exit 1 preserved. No stub was substituted for the missing functionality.
- `t0-linked-r2/`: actual HIP-linked executable, no-model smoke and synthetic
  transport checks; no weights or GPU work. Before final refinements.
- `t0-runtime-r2/`, `t0-linked-r3/`: refined runtime CPU/synthetic/link checks
  passed 18:11–18:12 UTC; source/binary/build-info identities retained. No model run.
- `t0-runtime-r3/`, `t0-linked-r4/`: final closure labels after documentation update;
  inspect actual result/command exits/input/binary hashes, never infer pass from names.
- `t0-coordination-readonly-r{2,3}.json`: 17:23/18:13 UTC rechecks, DS4 ACK absent;
  no GPU work.
- `t0-model-smoke-r1/r2/`: original-model admissions refused on a DS4 lease,
  before model open; historical operator window, not a model-load failure.
- `t0-node-activity-r2/`: fresh 20:01 UTC read-only probe after operator handover.
- `t0-model-smoke-r3/`: all leases/target DSO preflight passed; runner module-name
  collision failed immediately after child launch. No inference observed; helper
  exit 1/child exit -15, retained unchanged.
- `t0-smoke-http-red-r1/`, `t0-smoke-http-green-r1/`: focused synthetic HTTP
  regression reproduces the name collision, then passes four cases after alias fix.
- `t0-smoke-runner-fix-r1/`: nine-suite GCC/Clang/ASan/UBSan/header verification;
  no model execution during this CPU verification.
- `t0-smoke-closure-r1/`: final runner/documentation CPU-only closure; actual
  commands/exits and final input hashes are authoritative.
- `t0-model-smoke-r4/`: actual original-weight GPU serving smoke at 20:07 UTC;
  six JSON/SSE requests, exact predeclared outputs, consistent usage/accounting,
  clean exit and unchanged binary/model identities. Not pristine numerical,
  broad quality, concurrency, cancellation-in-flight or performance qualification.
  `remote-results/result.json`, `process-exit.json` and `assessment.json` define
  scope; one-second whole-device/system samples are not exact LIE peak accounting.

- `t0-perf-activity-r1/`: read-only idle-node observation before C1 preparation.
- `t0-perf-cpu-r1/r2/r3/`: CPU-only benchmark contract, compiler/sanitizer/header
  closures; r3 includes explicit unavailable optional power metadata.
- `t0-perf-linked-r1/`: actual HIP-linked benchmark, build-info/DSOs and CPU tests;
  no model during this local build verification.
- `t0-c1-perf-r1/`: leases/DSO preflight passed but absent optional sysfs attribute
  aborted before model launch; failure preserved, no discarded GPU timings.
- `t0-perf-power-red-r1/green-r1/`: missing metadata regression before/after fix.
- `t0-c1-perf-r2/`: completed C1 PP/TG baseline, three warmups plus nine measured
  samples, physical/output IDs and finite/repeatable frontier hashes. See
  `docs/C1-BASELINE.md` for timing scopes and limits; not a reactive speedup,
  pristine comparison, HTTP-throughput or owned numerical-backend claim.
- `t0-perf-closure-r1/`: final source/documentation CPU closure, separate from
  actual hardware samples and from earlier unchanged receipts.

- `gufo-bench-method-r1/`: independently fetched upstream documentation, recipe,
  model identities and methodology source at `fd1710b5`, plus license/notices;
  retrieval timestamps/HTTP status/hashes. Research only, no script execution.
- `t0-request-timings-red-r1/`: new HTTP assertion on the prior CPU fixture binary
  fails with missing `lie_timings`, actual exit 1. No GPU/model activity.
- `t0-request-timings-green-r1/`: initial eleven-suite compiler/sanitizer/header
  verification of C per-request timing and deterministic clock tests.
- `t0-request-timings-closure-r1/`: final CPU closure including partial-prefill
  failure and zero-output-rate cases; actual logs/exits/input hashes define pass.
  Timing metadata does not imply GPU throughput measurement or Gufo-suite parity.
- `t0-request-timings-linked-r1/`: new private HIP adapter link, build-info,
  no-model/synthetic tests, with GPU visibility masked. Model access and GPU
  execution are false; source inputs unchanged and binary identities retained.

- `ssd-option-contract-r1/`: documentation-only commit making default-off,
  explicit SSD persistence independent of RAM reuse; no storage implementation.
- `t0-lifecycle-activity-r1/`: 22:09 UTC read-only target observation of active DS4
  benchmark and four held leases. No LIE model/lock/GPU attempt or retry follows.
- `t0-worker-frontier-red-r1/`: synthetic invalid-position result escaped the old
  worker; assertion failure exit -6 (no core dump), retained as RED evidence.
- `t0-worker-frontier-green-r1/`: twelve-suite GCC/Clang/ASan/UBSan/header pass for
  executor guards, dispatch/blocked diagnostics and controlled cancellation.
- `t0-lifecycle-helper-r1/`: initial thirteen-suite CPU pass including the new
  HTTP lifecycle library against the separate synthetic TCP server. Not GPU
  inference, a real-model lifecycle result or a benchmark/performance claim.
- `t0-lifecycle-closure-r1/r2/`: final thirteen-suite compiler/sanitizer/header
  passes, including metadata, missed-window and helper identity refusal checks.
- `t0-lifecycle-linked-r1/`: masked HIP link/build-info/no-model and synthetic pass;
  model access/GPU execution false; source inputs unchanged during verification.
- `t0-lifecycle-activity-r2/`: fresh 22:42 UTC operator window, read-only idle/KFD/
  known-lock observation. No model execution or admission granted by the probe.
- `t0-lifecycle-source-r1/`: local source commit `efcb7fb`, compiled-source identity
  against the HIP-linked artifact and final CPU closure; no GPU run in this receipt.
- `t0-model-lifecycle-r1/`: actual original-weight GPU JSON/SSE timing, prefill/
  decode dispatch cancellation, TCP pressure/isolation/recovery, 23:01 UTC. Nine
  completed / three cancelled / zero failed; clean exit/stat identities, 228
  lifecycle records and 29 telemetry samples. All raw observations retained,
  hash-verified collection and offline audit exit 0. Not independent numerical,
  performance, kernel-preemption or native-batching qualification. Later read-only
  postflight confirms owned PIDs absent, known leases free and KFD empty.

- `antirez-layout-red-r1/`: draft inspector CPU regressions (invalid bool/alignment
  accepted, FIFO blocks), exit 1. Draft source and failure logs preserved.
- `antirez-layout-green-r1/r2/`: fourteen-suite compiler/sanitizer/header passes;
  final GGUF suite contains fifteen synthetic cases. NOT-INFERENCE.
- `antirez-layout-readonly-r1/r2/`: protected antirez Q2/Q4 bounded metadata/layout
  observations on .157, stat identities unchanged, no tensor payload/HIP/model
  execution. Initial type 39 unknown; final storage-only MXFP4 geometry validated
  without changing either header identity. This is not runtime format support.
- `antirez-format-reference-r1/`: official upstream antirez/ds4 c05cd8e2 LICENSE,
  ds4.c and ds4.h acquired independently by URL/hash; static format facts only,
  no source from the sibling project and no model/kernels executed or imported.
- `antirez-reader-refusal-r1/`: actual pristine Gufo f783fedb storage parser tested
  with generated memory images: Q8_0/Q2_K/Q4_K/IQ2_XXS recognized, MXFP4 refused.
  CPU-only, no HIP linkage/real model; source/compiler/hash/exit logs retained.
- `antirez-bench-admission-r1/`: offline closure hashes, unchanged verified code,
  exact per-format blockers and null PP/TG results; no GPU admission/model attempt.

- `q2-host-red-r1/`: pristine source compiles; six of seven synthetic host CTest
  cases fail (MXFP4, IQ2/Q2 binding, padded shape, F16 inject), legacy control passes.
- `q2-port-authoring-r1/`: initial exact-byte recipe authoring inputs/exit retained;
  later config rule is in the versioned recipe, not rewritten historical output.
- `q2-host-source-r1` (build-only): initial private host variant, not runtime-ready.
- `q2-host-green-r1/r2/`: initial seven-case host binding/compiler/sanitizer checks.
- `q2-header-readonly-r1/`: exact 11025350-byte protected Q2 header capture;
  unchanged historical header/stat identity, no payload/hash/GPU operation.
- `q2-header-binding-r1/`: actual-header-derived bind fails on omitted mRoPE
  section metadata, exit 1; no tensor values/model forward were present.
- `q2-config-reference-r1/`: pinned official Qwen config and Qwen Community License
  1.0, URL/status/SHA256; canonical mRoPE parameter facts, no code execution/import.
- `q2-host-green-r3/`: fixture compilation warning promoted to error, preserved.
- `q2-host-green-r4/`: eight host CTest cases pass GCC/Clang/ASan/UBSan, plus source
  contracts/production-source refusal; no HIP/model execution.
- `q2-host-green-r5/`: final eight-case host compiler/sanitizer checks; seven source
  tests no longer depend on the optional upstream checkout during default CTest.
- `q2-host-closure-r1/`: all fifteen default CPU suites/compiler/sanitizer checks
  and original adapter header check, serial builds, unchanged source inputs.
- `q2-header-binding-r2/`: GCC and Clang bind all 48 AR layers from the actual saved
  header in a payload-PROT_NONE anonymous view. NOT-MODEL-LOAD / NOT-INFERENCE;
  virtual reservation is not physical capacity or memory-fit evidence.
- `q2-host-delivery-r1/`: reviewed six-file port diff and source/closure hashes;
  r4/r5 provider bytes identical, actual-header observations remain attributed
  to r4 binaries. Original qualified server hash unchanged. Earlier RED and
  warning-failure fixture sources were reconstructed with exact agreement to
  their previously recorded hashes, explicitly labeled as later recovery.

- `q2-route-plan-red-r1/`: C17 layout/capacity fixture compiles, assertion exits -6;
  exact RED fixture/header and actual exits retained, NOT-INFERENCE.
- `q2-route-authoring-r1/r2/`: exact HIP overlay generation; first attempt refuses
  a nonexistent pragma anchor, second succeeds. No pristine/in-place build edits.
- `q2-route-linked-r1/`: build failure from omitted C++ chrono pre-include; fixed
  by retaining the established local build flag, not patching upstream headers.
- `q2-route-linked-r2/r3/`: private HIP links/masked host checks, no GPU/model work.
- `q2-route-format-r1/r2/`: shared format script pristine PASS/candidate failure;
  checked formatting-only recipe regeneration, previous recipes retained.
- `q2-route-linked-r4/r5/`: shared format script PASS, MMQ-target C++17/gfx1151/NO_VMM
  build/link, masked host refusals/scalar fixture goldens; GPU cases NOT RUN.
  Final r5 also checks nonzero one-row operator fixtures.
- `q2-route-host-r1/`: all eight host compiler/sanitizer cases after format-only
  host recipe changes; no model payload or GPU operation.
- `q2-route-cpu-r1/r2/`: seventeen default CPU suites across GCC/Clang/ASan/UBSan
  and the original adapter header check; r2 covers final inputs.
- `q2-route-delivery-r1/`: audit error decoding an unchanged binary fixture for
  the text diff; preceding formatting/header/refusal exits preserved, no PASS.
- `q2-route-delivery-r2/`: corrected audit, 1022 source files/final inputs/artifacts
  checked, combined source diff, expected production refusal and saved-header
  GCC/Clang binding; qualified original server unchanged, no GPU/model run.

The first codeload archive attempt was refused for identity mismatch before
extraction (raw first response was not saved); the pinned API tarball matched.
Live Prometheus/Micrometer doc fetches returned 403 and the first Prometheus
raw source path returned 404; later official pinned source doc retrievals
succeeded. These failures are not rewritten into successes.

No raw KV/snapshot, weights, copied DS4 binary or backup is stored here.
All CPU fixtures and measured HTTP timings must stay distinct from inference.
