<!-- SPDX-License-Identifier: MIT -->
# Original UD load with 256K context capacity

Read the [direct benchmark result](../../../../STRIX-POINT-BENCHMARK-RESULT.md).
The LIE and direct Gufo `--suite loading` arms each open the original UD with
capacity 262144, once. They measure 13.750589557 s and 13.695302901 s,
respectively. They do not prefill a 256K prompt or control the OS file cache.

`input/` contains the seven original LIE files and `input/gufo/` contains the
seven reference files, each with a collection receipt and SHA-256 identities.
`generated/` has the paired loading JSON/SVG/PNG, sampled resource summary
for both arms and artifact/source hashes. The standard loading CSV contains
no workload row; the load durations are in `summary.json` and the plot.

Reproduce offline with existing Matplotlib:

```sh
python3 -B docs/benchmarks/2026-10-02/strix-point/loading-256k/make-report.py \
  run/strix-point-loading-reproduced-new
```

The output directory must be new. The generator verifies complete campaign
exits, source hashes, model preservation, service restoration and lease
closure for both arms. It does not access a GPU or model file.
