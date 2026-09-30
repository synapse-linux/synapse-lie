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

The first codeload archive attempt was refused for identity mismatch before
extraction (raw first response was not saved); the pinned API tarball matched.
Live Prometheus/Micrometer doc fetches returned 403 and the first Prometheus
raw source path returned 404; later official pinned source doc retrievals
succeeded. These failures are not rewritten into successes.

No raw KV/snapshot, weights, copied DS4 binary or backup is stored here.
All CPU fixtures and measured HTTP timings must stay distinct from inference.
