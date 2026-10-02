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
