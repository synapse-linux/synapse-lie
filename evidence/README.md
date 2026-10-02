<!-- SPDX-License-Identifier: MIT -->
# Local evidence

Raw evidence is ignored except for this index. Keep successes, failures and
actual exit codes; never replace absent inference metrics with zeros.

- `reference-audit-r1/source-retrieval.json`: official pinned source fetches,
  including the unsuccessful vendored `LICENSE` path (curl exit 22 / HTTP 404)
  and the earlier sandbox DNS failure (git exit 128). Repository root licenses
  were fetched successfully. These are retrieval failures, not model failures.
- `reference-audit-r1/validation.json`: documentation and manifest checks only.

Historical model metadata was read from the primary LIE checkout's retained
`evidence/antirez-layout-readonly-r2/layouts.jsonl`. That earlier observation,
including its header/full-hash distinctions, is not a new model read or test.

Implementation receipts:

- `q2-host-r1`: four debug and four sanitizer CTests, before legacy RoPE fallback.
- `q2-operators-r1`: retained build failure; `q2-operators-r2`: synthetic GPU pass.
- `q2-model-r1/r2`: retained CMake/link failures; `q2-model-r3`: metadata refusal.
- `format-r1`, `reconstruction-r1`: local official format and exact patch reconstruction.
- Each run directory retains its immutable source capsule, remote log and actual
  transport exit. Collected results include hashes, commands and scoped telemetry.

Final first-stage results:

- `q2-host-r2`: final four debug + four ASan/UBSan passes.
- `q2-bench-r1`, `q2-ud-base-r1`, `q2-ud-patched-r1`: actual original-weight
  runs, exit 0; each 52 collected artifacts verified against remote hashes.
- `q2-comparison-r1/r2`: offline result tables and plots. R1 retains the harmless
  Matplotlib cache-directory warning; r2 uses a task-owned persistent cache.
- `docs/Q2-RESULTS.md`: tracked complete table and failure of the practical Q2
  performance gate. Raw data is never replaced by the concise report.
