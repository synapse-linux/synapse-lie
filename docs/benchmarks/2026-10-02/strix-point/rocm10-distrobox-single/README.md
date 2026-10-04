<!-- SPDX-License-Identifier: MIT -->
# ROCm 10 LIE `single` benchmark in Docker-managed Distrobox

On `.161`, Pop!_OS kernel `7.1.5-76070105-generic`, Distrobox 1.7.0 used the
pinned Fedora 43 ROCm 10 image and previously compiled `synapse-lie-bench`.
The original four-shard UD model was mounted read-only. The C1 direct reactive
profile used PP2048/TG128 at occupied-prefix depths 0, 4096, 8192, 12288,
16384, 32768, 65536 and 131072, one warmup and one measured sample per point.
All 16 samples completed 128 output tokens. The child and supervisor exited 0,
model file identities stayed unchanged, and the private GPU lease was released
after `llama-router.service` was restored. Maximum sampled CPU/GPU temperatures
were 91.125/90 C, below the operator's 100 C ceiling and lower sensor limits.

| Occupied prefix | ROCm 10 prefill tok/s | ROCm 10 decode tok/s | Earlier ROCm 7.2 prefill tok/s | Earlier ROCm 7.2 decode tok/s |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 479.936 | 10.433 | 472.581 | 10.292 |
| 4,096 | 439.211 | 10.414 | 433.310 | 10.261 |
| 8,192 | 427.143 | 10.411 | 415.064 | 10.251 |
| 12,288 | 420.799 | 10.394 | 419.773 | 9.891 |
| 16,384 | 418.574 | 10.397 | 434.701 | 10.203 |
| 32,768 | 407.723 | 10.343 | 425.131 | 10.173 |
| 65,536 | 394.419 | 10.241 | 404.108 | 10.045 |
| 131,072 | 357.117 | 9.227 | 389.786 | 9.862 |

At 128K, the observed ROCm 10 rates are 8.38% lower for prefill and 6.44%
lower for decode than the earlier ROCm 7.2 run. This is a **cross-stack
observation**, not a controlled ROCm-only effect: the host kernel changed from
6.16.3 to 7.1.5 and the container method changed from direct Docker to
Distrobox. Physical input IDs match at all eight depths, but prefill/decode
frontier hashes and generated output IDs differ at every depth. Neither a
quality-equivalent performance ranking nor a reactive speedup follows from
this comparison. One measured sample per depth gives no variability estimate.

The first Distrobox attempt, R1, failed before running the model because an
extra `--network none` flag conflicted with Distrobox's network namespace.
Its failed exit and logs remain under `input/r1/`. R2 removed that flag and
passed under a fresh GPU lease; `input/r2/` contains the complete raw benchmark,
telemetry, supervisor result and Distrobox logs. The R1 runner optimistically
records `model_attempted=true` before entry, but no measurements file exists;
the source runner now sets that field only after the benchmark starts. The
[ROCm 10 qualification report](../../../../STRIX-POINT-ROCM10.md) records
the kernel and runtime gates.

The [standard comparison plot](generated/benchmark.svg),
[zero-axis plot](generated/benchmark-zero.svg),
[full CSV](generated/comparison.csv) and [resource peaks](generated/resources.json)
are generated from the included raw files. Reproduce them offline with existing
Matplotlib, without a GPU or model files:

```sh
python3 -B docs/benchmarks/2026-10-02/strix-point/rocm10-distrobox-single/make-report.py \
  run/rocm10-point-distrobox-reproduced-new
```

Use a new output directory. The generator verifies recorded exits, model file
identities, service/lease restoration, hashes of the included raw files, full
outputs and physical prompt equality before plotting. The original local
collection additionally verified all 27 remote files, including container
home/cache files omitted from this portable bundle.
