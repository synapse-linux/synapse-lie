<!-- SPDX-License-Identifier: MIT -->
# Paired memory-estimate workload on Strix Point

The `.161` original UD `synapse-lie-bench --suite memory` and direct Gufo
reference both passed at capacity 133121, with d0/PP2048 and d16384/PP4096,
TG128, one warmup and one measured sample per point. Both paths completed
all outputs and matched physical inputs, outputs and PP/TG frontier hashes.

The common model resident estimate is 82384141824 bytes and the per-session
estimate is 3517025300 bytes. They are upstream estimates, **not exact peak
GPU allocations**. `generated/resources.json` and `generated/resources.svg`
separately give sampled whole-device GTT and temperature peaks/timelines.
`input/{lie,gufo}/` retains the seven
original campaign files and each SHA-256 collection/retirement receipt.
`generated/` contains validated comparison CSV/JSON and plots.

Reproduce offline with existing Matplotlib:

```sh
python3 -B docs/benchmarks/2026-10-02/strix-point/make-paired-report.py \
  memory run/strix-point-memory-reproduced-new
```

Use a new output directory. The generator checks complete exits, exact source
hashes, numerical frontiers, unchanged model stats, restored service and lease
closure. It never opens a model or GPU.
