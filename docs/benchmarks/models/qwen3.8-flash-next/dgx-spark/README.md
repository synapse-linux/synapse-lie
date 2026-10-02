<!-- SPDX-License-Identifier: MIT -->
# Qwen3.8 Flash Next on NVIDIA DGX Spark

[Model platforms](../README.md) · [Benchmark index](../../../README.md)

Platform development is isolated on `feature/dgx-spark`. No LIE CUDA numerical
or performance result is integrated into this branch. Existing external-server
measurements, readiness checks and platform reconnaissance remain reference
evidence and must identify their actual provider.

The first integrated report must declare the exact checkpoint and weight format;
do not treat a different 4-bit format as the Strix Halo UD-Q4_K_XL checkpoint.
Record model/backend admission and numerical checks before PP, TG, concurrency,
memory and cache results. Cross-platform comparisons require a matched workload
and explicitly recorded differences in quantization and speculative execution.
Use the [benchmark guide](../../../../guides/BENCHMARKS.md).
