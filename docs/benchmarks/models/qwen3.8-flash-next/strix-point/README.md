<!-- SPDX-License-Identifier: MIT -->
# Qwen3.8 Flash Next on AMD Strix Point

[Model platforms](../README.md) · [Benchmark index](../../../README.md)

Original Unsloth UD-Q4_K_XL weights, four verified shards, run on
`pop@192.168.5.161` with Radeon 890M (`gfx1150`). The current ROCm 10
campaign uses Pop!_OS kernel `7.1.5-76070105-generic`, a pinned Fedora 43
image through Docker-managed Distrobox and the older Point runtime. It is
**pre-integration evidence**: the newer C17 MTP/vision/phase-clock branch has
not yet been qualified on this GPU. Each completed campaign used a fresh
private lease, retained the exact raw files and restored the authorized
`llama-router.service` afterwards.

| Direct benchmark | LIE prefill | LIE decode | Same-stack Gufo decode | Scope |
| --- | ---: | ---: | ---: | --- |
| Occupied prefix 0, C1 | 479.936 tok/s | 10.433 tok/s | — | PP2048/TG128, one measured sample |
| Occupied prefix 128K, C1 | 357.117 tok/s | 9.227 tok/s | — | PP2048/TG128, one measured sample |
| Parallel C1 | 479.881 tok/s | 10.440 tok/s | 10.417 tok/s | PP2048/TG128, median of three |
| Parallel C8 | 474.092 tok/s | 32.837 aggregate tok/s | 32.872 aggregate tok/s | PP2048/TG128, median of three |

The [eight-depth single-session report](../../../2026-10-02/strix-point/rocm10-distrobox-single/README.md)
contains every 0–128K value, prefill/decode graphs, telemetry, raw JSONL and
reproduction commands. The [three-arm multi-session report](../../../2026-10-02/strix-point/rocm10-distrobox-multi/README.md)
contains LIE reactive, direct Gufo and LIE serial results at C1/2/4/6/8,
including every prefill/decode median, min/max, GPU batch counter and graph.
LIE and Gufo within ROCm 10 produce identical physical prompts, output IDs
and full prefill/decode frontiers in the three-arm campaign. Earlier ROCm 7.2
frontiers differ at every point, so the cross-stack rates are observations
across changed kernel/runtime/container configurations, not a controlled
quality-equivalent comparison.

The [full Strix Point report](../../../../STRIX-POINT-RESULT.md) and
[direct benchmark report](../../../../STRIX-POINT-BENCHMARK-RESULT.md)
cover the earlier ROCm 7.2 fresh physical prompts through 258,794 tokens,
capacity, cache reuse, resources and failures. ROCm 10 fresh-prompt matched
LIE/Gufo measurements and served HTTP multi-client measurements are pending.
Neither the direct C8 result nor the synthetic HTTP fixtures establish Pi
agent throughput. The old runtime has no newly added benchmark phase clocks;
new-runtime performance must be measured separately.
