<!-- SPDX-License-Identifier: MIT -->
# Benchmarks by model and platform

This index covers evidence integrated into `feature/openai-reactive-api`.
Choose a model, platform and weight format before comparing results. A successful
build, a CPU fixture and an original-weight GPU measurement are separate states.
Results from parallel branches require their own source and evidence review.

| Model | Platform and provider | Weight format | Integrated evidence |
|---|---|---|---|
| [Qwen3.8 Flash Next](models/qwen3.8-flash-next/README.md) | [AMD Strix Halo, HIP gfx1151](models/qwen3.8-flash-next/strix-halo/README.md) | Unsloth UD-Q4_K_XL | Original-weight AR performance, HTTP capacity, reactive batching, RAM state, SSD restart/C1 through 128K and raw-state HTTP SSD/C2 |
| Qwen3.8 Flash Next | [AMD Strix Halo, HIP gfx1151](models/qwen3.8-flash-next/strix-halo/README.md#other-weight-formats) | antirez Q2/Q4 | No current qualified result integrated from the separate compatibility branch |
| Qwen3.8 Flash Next | [AMD Strix Point, HIP gfx1150](models/qwen3.8-flash-next/strix-point/README.md) | Unsloth UD-Q4_K_XL | No original-weight GPU measurement integrated |
| Qwen3.8 Flash Next | [NVIDIA DGX Spark, CUDA](models/qwen3.8-flash-next/dgx-spark/README.md) | Must identify the exact checkpoint and format | No LIE CUDA performance measurement integrated |

## Protocol and completeness

[CLI and graph exports](../CONTEXT-COMPARISON.md),
[measurement definitions](../BENCHMARKING.md) and
[remaining benchmark and quality tests](../TEST-COVERAGE-LONG-CONTEXT.md)
apply to every model/platform page. The existing Gufo-style suites are simplified
direct-executor diagnostics, not an exact reproduction of the published HTTP
campaign. The [Gufo coverage table](../BENCHMARKING.md#pinned-reference-methodology)
records each missing feature or protocol step.

Keep three fields distinct for every workload: engine support, benchmark support
and measured evidence. In particular, AR batching is implemented; the matching
Gufo HTTP concurrency protocol is not. MTP is not exposed by the current LIE
contract. Loading uses uncontrolled OS file-cache conditions, and sampled memory
telemetry is not the reference peak HIP measurement.

## Required result identity

Each campaign must identify the exact checkpoint/revision and quantization,
platform/host, runtime/provider and source commit, physical input/output counts,
context capacity, chunk size, concurrency, cache policy, AR/MTP mode, warmups,
repetitions and timing intervals. Link its protocol, numerical checks, failures,
CSV/JSON samples and graphs. Include available thread, memory and temperature
observations with their measurement limits.

Fresh full prefill, incremental prefill at occupied depth and full cache hits
have separate panels. A full hit has no executed PP tokens/s. Pure decode,
sum of request decode rates, cohort output over total wall time and HTTP latency
also remain separate metrics. External published numbers are references until
a matched local experiment establishes comparability.

## Evidence layout

Model/platform pages provide navigation. Dated campaign files under
`2026-10-01/` and `2026-10-02/` keep their existing paths and contents so that
source bindings, links and SHA-256 inventories remain valid. Dated reports
describe the tested snapshot; consult the linked contracts for later features.
Do not reinterpret an old failure, capacity smoke or synthetic chart as a new
performance result.

[Checkpoint compression and benefit admission](../CACHE-COMPRESSION-GPU.md)
records the measured memory/latency tradeoff and exact restored state. The
model/platform index keeps these separate from raw HTTP SSD qualification.

[DS4-style checkpoint policy](../CACHE-DS4-GPU.md) additionally distinguishes
progressive checkpoint correctness from retention performance under RAM pressure.
Never substitute its trimmed/intermediate-prefix timings for a full cache hit.
