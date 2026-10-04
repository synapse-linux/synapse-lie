<!-- SPDX-License-Identifier: MIT -->
# Technical archive

Historical reports and internal implementation experiments. These are not the main benchmark results; use the [model/platform results](../benchmarks/README.md) for tables and graphs.

- [Antirez Qwen3.8 Flash Next — prefill and decode benchmark gate](ANTIREZ-BENCHMARKS.md).
- [Simplified GPU benchmark results — 2026-10-01](BENCHMARK-RESULTS.md).
- [Benchmark direction and server prerequisites](BENCHMARKING.md).
- [C1 prefill/decode baseline protocol](C1-BASELINE.md).
- [Qwen checkpoint compression: cost, correctness and admission](CACHE-COMPRESSION-GPU.md).
- [DS4-style cache policy: GPU qualification and retention cost](CACHE-DS4-GPU.md).
- [Cache build features and original-weight HTTP SSD — R5](CACHE-FEATURES-GPU.md).
- [Simplified Gufo-style benchmark and comparison](CONTEXT-COMPARISON.md).
- [First shared-core GPU regression result](CORE-GPU-RESULT.md).
- [Full-prefill and served benchmark results on .157](FULL-PREFILL-HTTP-RESULT.md).
- [HTTP 256K capacity and real Pi tools on .157](HTTP-256K-PI.md).
- [DS4 runtime payload on Strix Halo — 2026-10-02](KVC-GPU-RESULT.md).
- [OpenAI reactive original-weight run on .157](OPENAI-GPU.md).
- [GPU performance result — 2026-10-01](PERFORMANCE-RESULT.md).
- [Antirez Q2 compatibility — first host slice](Q2-COMPATIBILITY.md).
- [Extended Q2 operator checks — two arithmetic corrections, 88 controls pass](Q2-EXTENDED.md).
- [First real antirez Q2 test — passed, performance qualification open](Q2-FIRST-MODEL.md).
- [Q2 routed HIP candidate — operator/preflight records](Q2-HIP.md).
- [Reactive inference — measured GPU batching and scalar fallback](REACTIVE-INFERENCE-RESULT.md).
- [Replacement plan — use Unsloth now, measure before another Q2 port](REPLAN.md).
- [Native server tools and Pi with Unsloth](SERVER-TOOLS.md).
- [SSD restart through 128K: GPU completion and thermal observations](SSD-GPU-COMPLETION.md).
- [SSD restart: 512-token pass, 8K thermal stop](SSD-GPU-RESULT.md).
- [C17 RAM prefix state — GPU result, 2026-10-02](STATE-GPU-RESULT.md).
- [T0 serving lifecycle — original-weight GPU protocol passed](T0-LIFECYCLE.md).
- [One-shot original-model smoke — operator window](T0-SMOKE.md).
