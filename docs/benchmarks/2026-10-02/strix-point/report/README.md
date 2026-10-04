<!-- SPDX-License-Identifier: MIT -->
# Strix Point UD report bundle

Read the [full report](../../../../STRIX-POINT-RESULT.md) for protocol, every
sample, hardware/build/model identity, timings, cache, resources, reactive scope,
failures, closure and remaining qualification. This is the completed **C1
9-token prompt / 32-token output smoke**, not a long-context benchmark campaign.

## Artifacts

| File | Contents |
|---|---|
| [measurements.jsonl](input/measurements.jsonl) | Unchanged input/output IDs, identity, timing and cache/dispatch counters |
| [telemetry.jsonl](input/telemetry.jsonl) | Unchanged 27 timestamped observations, all sensors and owned process status |
| [manifest.json](input/manifest.json) | Original source checkpoint, executable/library hashes and model/settings |
| [samples.csv](generated/samples.csv) | All four samples; integer ns, counters and calculated rates |
| [statistics.csv](generated/statistics.csv) | Mean, median, observed min/max for the three measured RAM hits |
| [summary.json](generated/summary.json) | Metrics, first fresh sample, all distributions and resource observations |
| [telemetry.csv](generated/telemetry.csv) | Flattened memory/GPU/process observations; missing status remains blank |
| [temperatures.csv](generated/temperatures.csv) | Every individual sensor reading and its campaign limit |
| [timings.svg](generated/timings.svg), [PNG](generated/timings.png) | All four timing/throughput samples, with fresh warmup labelled |
| [resources.svg](generated/resources.svg), [PNG](generated/resources.png) | Temperature, GTT, RAM, RSS, VRAM, process threads and GPU busy |
| [standard core chart](generated/core/benchmark.svg), [PNG](generated/core/benchmark.png) | Existing shared-core benchmark view |
| [core summary.json](generated/core/summary.json), [CSV](generated/core/summary.csv) | Existing benchmark validator export; complete-wall throughput |
| [report-manifest.json](generated/report-manifest.json) | Input/generator/validator/receipt hashes and derived artifact hashes |
| [verification.json](verification.json) | Report generation exit, hash/reproduction checks and visual review |

The input files are byte-for-byte copies of local
`evidence/strix-point-core-ud-r1/`, verified against the previously committed
[core receipt](../core-receipt.json). That receipt includes campaign result,
commands, model preservation, actual exits, stderr and fresh postflight.
The report generator also binds observations to the owned PID/start ticks/cgroup.
Temperature CSV keeps individual NVMe sensors; the figure uses their maximum
at each observation. Process gaps are not zero values. Memory series overlap.

## Offline reproduction

From the repository root, with Python and existing Matplotlib:

```sh
python3 -B docs/benchmarks/2026-10-02/strix-point/report/make-report.py \
  run/strix-point-report-reproduced
```

The output directory must be new. The generator validates the input hashes,
complete benchmark accounting, output repeatability, successful campaign and
cleanup, unchanged model identities, service restoration and thermal samples.
It then uses `tools/bench-report.py` for the standard view and creates the
additional per-sample/resource exports. No remote host, GPU or model weights
are accessed; there is no package installation or benchmark rerun.

Numeric CSVs and the report summary are deterministic for these inputs. The
standard core summary includes its source path, and the standard SVG includes
renderer metadata; path/renderer changes may therefore change artifact hashes
without changing measured values. The manifest records the actual outputs of
each reproduction. Matplotlib's private cache is disposable and is not tracked.
