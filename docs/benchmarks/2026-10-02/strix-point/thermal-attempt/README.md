<!-- SPDX-License-Identifier: MIT -->
# Incomplete eight-depth direct benchmark — thermal guard

Read the [direct benchmark result](../../../../STRIX-POINT-BENCHMARK-RESULT.md).
This is a **FAILED** `synapse-lie-bench --suite single` attempt, not a
passing partial eight-depth campaign. Depths 0 and 4096 each produced a
warmup and one measured sample; the supervisor stopped at CPU 85 C during
the 8192 warmup. No completion values are reported above 4096.

`input/` contains the exact original seven files from .161 plus collection
receipt: manifest, runner, result, final measurements JSONL, 114 raw telemetry
records and stdout/stderr. The collection receipt validates final source hashes.
Its final measurement file is larger than the `bench_partial` snapshot in the
supervisor result because the child wrote `failed` during owned cleanup.

`generated/samples.csv` retains all four completed samples without averaging
the incomplete campaign. `telemetry.csv`, `summary.json` and
`diagnostic.svg/png` show the thermal trajectory and only the completed
diagnostic points. `artifact-sha256.json` records generated file hashes.

Reproduce offline with existing Matplotlib:

```sh
python3 -B docs/benchmarks/2026-10-02/strix-point/thermal-attempt/make-report.py \
  run/strix-point-thermal-reproduced-new
```

The output directory must be new. The generator requires the recorded thermal
failure and closure, and never accesses .161 or a GPU.
