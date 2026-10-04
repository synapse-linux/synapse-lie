<!-- SPDX-License-Identifier: MIT -->
# ROCm 10 multi-user direct inference in Docker-managed Distrobox

On `pop@192.168.5.161`, the original four-shard Qwen3.8 Flash Next UD model
is exercised with the pinned Fedora 43 ROCm 10 image under Pop!_OS kernel
`7.1.5-76070105-generic`. The comparison uses the earlier ROCm 7.2
[three-arm direct benchmark](../multi/README.md), recorded under kernel
`6.16.3-76061603-generic` with direct Docker.

The `synapse-lie-bench --suite multi` profile runs C1/2/4/6/8 identical
2,048-token physical prompts, one warmup and three measured repetitions per
point, with a 128-token output budget per sequence. Its prefill interval is
aggregate new-token preparation before the common decode interval. Its decode
interval counts confirmed output tokens from all concurrent sequences. LIE
reactive, direct Gufo and LIE serial control use separate admitted GPU windows.
This tests concurrency inside the inference engine, not simultaneous HTTP
requests or Pi agent client latency.

All three ROCm 10 arms passed with supervisor and child exit 0. Each arm
completed one warmup and three measured full 128-token outputs at all five
points, for 20 complete samples per arm. Rates below are medians of the three
measured repetitions; observed min/max are preserved in the CSV.

| Sessions | ROCm 10 LIE PP | ROCm 10 Gufo PP | ROCm 10 serial PP | ROCm 7.2 LIE PP | ROCm 7.2 Gufo PP | ROCm 7.2 serial PP |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 479.881 | 476.834 | 476.564 | 465.708 | 466.416 | 464.126 |
| 2 | 477.781 | 476.767 | 475.420 | 462.806 | 463.194 | 461.892 |
| 4 | 475.646 | 475.791 | 475.374 | 467.093 | 469.222 | 469.039 |
| 6 | 473.804 | 475.345 | 474.997 | 491.446 | 491.966 | 498.651 |
| 8 | 474.092 | 474.397 | 474.994 | 497.795 | 498.405 | 498.853 |

| Sessions | ROCm 10 LIE TG | ROCm 10 Gufo TG | ROCm 10 serial TG | ROCm 7.2 LIE TG | ROCm 7.2 Gufo TG | ROCm 7.2 serial TG |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 10.440 | 10.417 | 10.435 | 10.295 | 10.274 | 10.292 |
| 2 | 17.206 | 17.212 | 10.401 | 16.430 | 16.430 | 10.270 |
| 4 | 24.899 | 24.892 | 10.439 | 23.808 | 23.837 | 10.278 |
| 6 | 30.327 | 30.273 | 10.443 | 29.620 | 29.584 | 10.313 |
| 8 | 32.837 | 32.872 | 10.425 | 32.184 | 32.146 | 10.316 |

At C8, ROCm 10 LIE reactive decode is **3.15×** its serial control and
**3.15×** its own C1, and is within 0.11% of Gufo. Every measured C2–C8 LIE
sample recorded zero single-row decode calls, 128 batch calls and 128 × users
batch rows. This confirms that reactive scheduling reaches the GPU inference
executor. Aggregate prefill stays near 474–480 token/s on ROCm 10 because this
profile prepares peer sequences before the common decode interval; it does not
batch their prefill into one fused computation.

Within each stack, LIE, Gufo and serial produce identical physical inputs,
generated IDs and complete prefill/decode frontier hashes at all five points.
Across ROCm 10 and ROCm 7.2, physical inputs match, but output IDs and both
frontiers differ at **every** point for all three arms. At C8, ROCm 10 LIE
decode is 2.03% higher and its prefill is 4.76% lower than the older ROCm 7.2
run. Kernel, ROCm and container mode changed together, so these are observed
cross-stack differences, not an isolated ROCm effect or a quality-equivalent
performance ranking. Three measured repetitions per point give observed
min/max, not a broad statistical confidence interval.

Sampled CPU/GPU maxima were 84.125/86 C for LIE, 84.375/86 C for Gufo and
82.875/86 C for serial, below the authorized 100 C guard and lower sensor
limits. Model file identities remained unchanged. Fresh collection verified
all 63 remote files across the three runs by SHA-256. Final postflight found
`llama-router.service` active, only its PID in KFD, no remaining LIE Distrobox
and the private GPU lease free.

The [comparison graph](generated/benchmark-zero.svg),
[full summary CSV](generated/summary.csv),
[cross-stack CSV](generated/comparison.csv),
[reactive batch counters](generated/reactive-dispatch.json) and
[resource peaks](generated/resources.json) are generated from the original
JSONL and supervisor receipts. Reproduce them offline with existing Matplotlib:

```sh
python3 -B docs/benchmarks/2026-10-02/strix-point/rocm10-distrobox-multi/make-report.py \
  run/rocm10-point-distrobox-multi-reproduced-new
```

Use a new output directory. The generator checks campaign exits, model file
identity, service and lease closure, included raw-file hashes, all output
budgets, physical prompt equality and LIE batch-dispatch counters. The original
local collection also verifies remote files omitted from this portable bundle.
