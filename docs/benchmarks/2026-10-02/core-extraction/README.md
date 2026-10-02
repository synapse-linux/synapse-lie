# Shared-core GPU regression artifacts

See [the result](../../../CORE-GPU-RESULT.md) and the predeclared
[protocol](../../../CORE-GPU-PROTOCOL.md). Dates/times in receipts are UTC.

- `summary.json`: offline audit, complete measured rate distributions, numerical
  comparison, dispatch counts, thread census and closure. This is the final
  interpretation; raw controller `state.json` intentionally still says
  `COMPLETED_PENDING_OFFLINE_REGRESSION_ANALYSIS`.
- `executor.csv`, `core.csv`, `http.csv`: machine-readable values. Timing scope is
  part of each column; per-job completed calls and cohort total wall are different.
- `comparison.svg/png`, `core-*/benchmark.svg/png`: scientific plots; error bars
  are observed minimum/maximum around medians, not confidence intervals.
- `core-*/summary.json`: all core samples/jobs and their input/output witnesses.
- `receipts/*/result.json`: unmodified per-arm helper receipts, actual exit codes,
  model stats, runtime DSO identities, settings and observations.
- `suite-manifest.json`, `state.json`, `drive.py`: immutable input identities,
  run order/retained baseline, exact campaign controller source. This private
  controller is a historical receipt, not a standing authorization to run it.
- `postflight.json`, `controller-retirement.json`: child/supervisor closure and
  later read-only controller/port observation. Final telemetry in raw status is
  historical, not evidence of continued GPU activity.
- `failed-r1-*`: the retained unsuccessful first attempt and its preflight error.
- `build-receipt.json`, `cpu-commands.json`, `cpu-source.json`: compile-only binary
  identities and separate `.157` CPU test exits/source identity.
- `collection-sha256.json`: hashes of all 121 collected raw campaign files.
  These paths are relative to the full raw evidence directory, not this reduced
  committed artifact directory. `artifact-sha256.json` hashes this directory.

Full raw inputs, measurements, HTTP transcripts, register observations, process
telemetry and logs are preserved locally under `evidence/core-gpu-r2/` and on
`.157` under `/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run/core-gpu-r2/`.
The separate failed `core-gpu-r1` collection is also retained. Files are persistent;
none of these source/evidence directories live under `/tmp`.

From the repository root, reproduce the offline audit/plots with the original
collected evidence (no GPU/model execution):

```sh
python3 docs/benchmarks/2026-10-02/core-extraction/analyze.py \
  evidence/core-gpu-r2 run/core-gpu-report-reproduced
```

The script checks collection hashes, successful/complete arms, matched dependency
sets, executor tokens/frontiers, core input/output/settings, HTTP finish/usage,
model stat preservation and process/lease closure before reporting the sampled
5% performance gates. It uses repository `tools/bench-report.py`; the exact tested
version is also in the raw collection and identified by the source manifest.
No GPU or remote test is needed to reproduce these derived artifacts. Standard
Matplotlib is required for offline plotting; no dependency was installed here.
