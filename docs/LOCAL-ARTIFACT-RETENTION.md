<!-- SPDX-License-Identifier: MIT -->
# Local artifact retention

The owner authorized removing unused or recreatable local artifacts on
2026-10-07. Cleanup applies only to `antirez-compat-audit`; the .157 host,
DS4, model files and other worktrees are unchanged. The worktree decreases
from approximately54.8GiB to19.0GiB, counting hard-linked files once.
This is the local `du` accounting, not exclusive Btrfs storage usage.

664 transport archives were removed only after every contained payload
matched its extracted copy by SHA-256. The payloads, reports, failures and
actual command exits remain. Historical transport-container hashes remain
in their original receipts; rebuilding a gzip container is not promised to
reproduce its original compressed bytes. Do not reinterpret container absence
as loss of its verified payload or change historical qualification results.

55 generated CMake directories were removed. All98 saved executables and
static archives remain byte-exact, including the qualified MMQ archive and
current/control servers. A future rebuild can regenerate intermediates from
the retained recipes; existing model references do not require a rebuild.

246 inactive source snapshots are recoverable from verified source capsules;
current provider/core sources remain expanded.231 assembly/profile files are
stored with lossless compression. The source and diagnostic indexes preserve
original paths, fingerprints and hashes. Recovery refuses existing targets:

```sh
python3 tools/restore-q2-retained-artifact.py .deps/gufo-base
python3 tools/restore-q2-retained-artifact.py evidence/q2-producer-q8-preparation/down-rolled.s
```

Each restored source is checked against its complete file fingerprint. Each
diagnostic is checked against its original byte hash. Round trips succeeded
for an existing source capsule, a newly compacted source and a diagnostic.
Restore a compacted file before running an old analysis that requires its
original uncompressed pathname.

4521 identical numerical files now use hard links to share immutable data.
Every original path and byte hash is preserved. These are frozen evidence:
create a separate copy when deriving a modified input or output. Original
per-path modification times and the sharing map are retained in the cleanup
journal; inference timings continue to come from the original command data.

Final verification checks18423 transport-payload file instances,98 retained
executables/archives,208 recovery capsules and231 compressed diagnostics.
The original full-prefill128K reference is exact. Source/kernel/model formats,
benchmark contracts and model measurements are unchanged by this maintenance.

The remaining space retains source capsules, unique numerical evidence,
qualified executables, original command logs and active development inputs.
Git commits retain tracked source, patches, recipes, reports and recovery
indexes; ignored binary/raw artifacts are stored separately in this worktree.
New trials should collect files directly and avoid retaining a second transport
archive after payload verification.

[Cleanup receipt](../config/worktree-cleanup-20261007.json),
[source recovery index](../config/q2-retained-source-index.json),
[diagnostic recovery index](../config/q2-compacted-diagnostics-index.json).
