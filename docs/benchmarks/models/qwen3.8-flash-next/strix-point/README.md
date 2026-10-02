<!-- SPDX-License-Identifier: MIT -->
# Qwen3.8 Flash Next on AMD Strix Point

[Model platforms](../README.md) · [Benchmark index](../../../README.md)

The separate `feature/strix-point-ud` branch targets the HIP `gfx1150` platform.
No original-weight GPU performance result is integrated into this branch.
Compilation and CPU/sanitizer fixtures do not fill PP, TG, capacity or memory
result rows. Strix Halo measurements must not be presented as Strix Point data.

The first integrated UD-Q4_K_XL report must identify the actual device/host,
weight revision, provider/build, numerical qualification, resource admission and
thermal policy, then supply matched fresh PP, decode and concurrency samples.
Use the [common result requirements](../../../README.md#required-result-identity).
