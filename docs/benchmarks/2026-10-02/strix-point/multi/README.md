<!-- SPDX-License-Identifier: MIT -->
# Original UD concurrent direct benchmark on Strix Point

Read the [qualification and complete values](../../../../STRIX-POINT-BENCHMARK-RESULT.md).
On `.161`, the original UD model was run with `synapse-lie-bench --suite multi`
using the C reactive dispatcher, with the direct Gufo reference, and with LIE's
deliberately serial interleaving control. Each arm used identical physical
2048-token prompts for C1/2/4/6/8, 128 output tokens per user, one warmup and
three measured samples per point. All 60 samples completed, with exit 0 and
matching physical inputs, generated outputs and complete prefill/decode frontier
hashes across all three arms. The approved 100 C supervisor ceiling preserved
lower published limits per sensor.

`input/{lie,gufo,serial}/` holds the original seven campaign files per arm and
its SHA-256 collection/retirement receipt. `generated/` holds all three
series with observed min/max, comparative JSON/CSV, sampled resource peaks and
temperature/GTT timelines,
every measured reactive batch counter, normal and zero-axis SVG/PNG plots, and
source/output hashes. The plotted prefill is aggregate new prefill throughput;
this suite pre-fills sequences before the common decode interval. Its decode
rate is confirmed aggregate output tokens divided by that common interval.
It measures direct executor dispatch, without HTTP or a multi-client network.

Reproduce the report offline with existing Matplotlib:

```sh
python3 -B docs/benchmarks/2026-10-02/strix-point/multi/make-report.py \
  run/strix-point-multi-reproduced-new
```

Use a new output directory. The generator checks complete campaign exits,
sample counts and full output budgets, all three input/output/frontier matches,
reactive batch counters, model identity preservation, service restoration,
lease closure and every collected source hash. It never opens a model or GPU.
