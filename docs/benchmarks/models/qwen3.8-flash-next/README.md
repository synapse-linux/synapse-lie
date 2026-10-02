<!-- SPDX-License-Identifier: MIT -->
# Qwen3.8 Flash Next benchmarks

[All models and platforms](../../README.md)

| Platform | Results and scope |
|---|---|
| [AMD Strix Halo](strix-halo/README.md) | UD-Q4_K_XL AR measurements on the designated `.157` host |
| [AMD Strix Point](strix-point/README.md) | Separate platform work; GPU performance not measured in this branch |
| [NVIDIA DGX Spark](dgx-spark/README.md) | Separate platform work; no integrated LIE CUDA performance result |

The measured LIE HIP provider uses the independently fetched Gufo `f783fedb`
source. Each campaign records its actual build and weight identity. The model
family name alone does not make antirez Q2, Unsloth UD-Q4_K_XL or another weight
format equivalent, and a reference server's result is not a LIE measurement.

Native LIE context capacity is 262144 total tokens. The HTTP client can prepare
larger workloads, but no 512K/768K/1M LIE result is established by that capability.
See the [extended-context gates](../../../TEST-COVERAGE-LONG-CONTEXT.md).
