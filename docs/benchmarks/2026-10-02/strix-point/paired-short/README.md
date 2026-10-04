<!-- SPDX-License-Identifier: MIT -->
# Paired .161 direct executor, original UD, occupied 0 and 4K

Read the [direct benchmark result](../../../../STRIX-POINT-BENCHMARK-RESULT.md).
Both full campaigns pass: one measured sample per point, no warmup,
PP2048/TG128, 133760 capacity, exact physical prompts and equal generated
tokens plus prefill/decode frontier hashes. These two points are a bounded
same-device LIE/Gufo comparison; the eight-depth campaign is separate.

The `input/lie` and `input/gufo` directories each retain the original seven
files returned from .161: immutable `manifest.json` and `runner.py`,
`result.json`, `measurements.jsonl`, `telemetry.jsonl`, stdout/stderr and the
source-hashed `collection.json`. The model was read-only and its stat identity
unchanged; child/supervisor exits were zero, the service was restored and the
lease was free at each collection.

`generated/summary.json` and `summary.csv` are the existing benchmark
validator's exact-input comparison, with every measured value. The standard
`benchmark.svg/png` uses auto-scaled axes; `benchmark-zero.svg/png` uses
zero-based axes for an easier visual reading of the small decode difference.
`resources.json` records sensor/GTT peaks. `artifact-sha256.json` hashes the
source files and generated artifacts.

Reproduce offline from the repository root with existing Matplotlib:

```sh
python3 -B docs/benchmarks/2026-10-02/strix-point/paired-short/make-report.py \
  run/strix-point-paired-reproduced-new
```

The output directory must be new. The tool verifies both remote collection
hashes, complete exits, output and frontier equality, model preservation and
retirement before exporting. It never accesses a GPU, a model file or .161.
The standard summary includes the local input path, so output hashes may
change if the worktree is relocated; numeric values and source hashes remain
the reproduction criteria.
