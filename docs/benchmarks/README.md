<!-- SPDX-License-Identifier: MIT -->
# Benchmarks

Choose a model and platform. Each results page contains the complete tables,
graphs, measurement conditions and reproduction instructions together.

| Model and weights | Platform | Results |
| --- | --- | --- |
| Qwen3.8 Flash Next, Unsloth UD-Q4_K_XL | AMD Strix Halo, HIP `gfx1151` | **[Tables and graphs](models/qwen3.8-flash-next/strix-halo/README.md)**. |
| Qwen3.8 Flash Next, Unsloth UD-Q4_K_XL | AMD Strix Point, HIP `gfx1150` | **[Direct measurements](models/qwen3.8-flash-next/strix-point/README.md)**, **[served HTTP C1–C8](2026-10-04/strix-point/http-multi/README.md)** and **[cold HTTP to ~256K](2026-10-04/strix-point/http-depth/README.md)**. |
| Qwen3.8 Flash Next | NVIDIA DGX Spark, CUDA | No integrated inference measurements. |

[Run the benchmark and export graphs](../guides/BENCHMARKS.md).

Only measured model inference belongs in these results. Correctness fixtures,
cache implementation checks and superseded experiments are in the
[technical archive](../archive/README.md).
