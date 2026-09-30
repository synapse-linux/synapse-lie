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

The first codeload archive attempt was refused for identity mismatch before
extraction (raw first response was not saved); the pinned API tarball matched.
Live Prometheus/Micrometer doc fetches returned 403 and the first Prometheus
raw source path returned 404; later official pinned source doc retrievals
succeeded. These failures are not rewritten into successes.

No raw KV/snapshot, weights, copied DS4 binary or backup is stored here.
All CPU fixtures and measured HTTP timings must stay distinct from inference.
