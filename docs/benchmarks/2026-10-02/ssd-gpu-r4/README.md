<!-- SPDX-License-Identifier: MIT -->
# SSD R4 evidence

[Readable result](../../../SSD-GPU-COMPLETION.md).
`evidence.tar.gz` contains the complete 106-file remote collection plus its
SHA-256 inventory. It excludes model weights, executables and checkpoint payloads.
`archive.json` binds compressed and original tar hashes; `artifact-sha256.json`
binds this derived artifact directory. Raw archive state deliberately retains
`COMPLETED_PENDING_OFFLINE_REGRESSION_ANALYSIS`; `verification.json` is the
subsequent offline PASS, not an alteration of that raw state.

To reproduce offline, extract the archive into a new private directory, verify
every entry against `collection-sha256.json`, then run:

```sh
python3 analyze-ssd.py /path/to/extracted/campaign /path/to/new/analysis
gzip -dc thermal-samples.jsonl.gz > /path/to/thermal-samples.jsonl
python3 analyze-thermal.py /path/to/thermal-samples.jsonl /path/to/new/thermal-analysis
```

Python with Matplotlib is needed only for exports. Analysis never contacts a
GPU host. The observer source is retained for provenance; do not launch it as
part of offline reproduction. Full raw observer records are compressed without
modification; their uncompressed SHA-256 is in `thermal-summary.json`.

`jobs.csv` contains all 24 core jobs (20 measured, 4 warmups). Core tables use
the complete benchmark stream. `thermal-jobs.csv` has 23 observed completions,
because the read-only observer missed one event at an arm transition. Its
temperatures/clocks are 1 Hz observations, not a thermal throttle detector.
