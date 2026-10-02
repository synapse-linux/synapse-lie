<!-- SPDX-License-Identifier: MIT -->
# Paired original UD fresh-prefill benchmark through 128K

Read the [full results and scope](../../../../STRIX-POINT-BENCHMARK-RESULT.md).
On `.161`, LIE and the direct Gufo reference each passed
`synapse-lie-bench --suite fresh` with 1500/8000/8192/32768/131072 new
physical prompt tokens, capacity 262144 and TG128. There were no warmups and
two measured repetitions per point. All 20 samples completed full 128-token
outputs, with exact physical input, output and complete PP/TG frontier parity
across arms. Prefill timing covers the entire new prompt; there is no reused
prefix or RAM/SSD cache hit.

`input/{lie,gufo}/` holds seven original campaign files per arm plus the
SHA-256 collection/retirement receipt. `generated/` contains complete
per-arm medians/min/max in CSV/JSON, normal and zero-axis plots, size estimates,
sampled resource peaks and temperature/GTT timelines, and source/output hashes.
GTT is whole-device accounting, not an allocation-exact model peak. The
100 C supervisor ceiling was explicitly authorized and any lower published
sensor max remained in force.

Reproduce the report offline with existing Matplotlib:

```sh
python3 -B docs/benchmarks/2026-10-02/strix-point/make-paired-report.py \
  fresh-128k run/strix-point-fresh-128k-reproduced-new
```

Use a new output directory. The generator checks all source hashes, exit and
cleanup receipts, complete sample counts, physical inputs, output IDs and
frontier equality without opening a model or GPU.
