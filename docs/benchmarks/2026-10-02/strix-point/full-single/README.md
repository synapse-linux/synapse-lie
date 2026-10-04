<!-- SPDX-License-Identifier: MIT -->
# Full eight-depth original UD direct benchmark on Strix Point

Read the [comparison and qualification result](../../../../STRIX-POINT-BENCHMARK-RESULT.md).
The original UD model was run on `.161` using `synapse-lie-bench --suite single`
and the direct Gufo reference binary. Both used occupied prefixes 0, 4096,
8192, 12288, 16384, 32768, 65536 and 131072, PP2048/TG128, one warmup and
one measured sample per point. Both completed all 16 samples with exit 0 and
full 128-token outputs. Exact physical inputs, generated outputs and complete
prefill/decode frontier hashes match at every point. The operator-approved
100 C supervisor ceiling still honored lower published limits per sensor.

`input/lie/` and `input/gufo/` contain the seven original campaign files per
arm plus SHA-256 collection/retirement receipts. `generated/` contains the
validated comparison CSV/JSON, standard and zero-axis plots, sampled resource
peaks and source/output hashes. One measured sample per point is an observation,
not a confidence interval. The two campaigns started at different temperatures;
small speed differences cannot establish a ranking.

Reproduce the report offline with existing Matplotlib:

```sh
python3 -B docs/benchmarks/2026-10-02/strix-point/full-single/make-report.py \
  run/strix-point-full-single-reproduced-new
```

Use a new output directory. The generator checks complete campaign exits,
sample counts, exact input/output/frontier parity, model identity preservation,
service restoration, lease closure and every collected source hash. It never
accesses a model file or GPU.
