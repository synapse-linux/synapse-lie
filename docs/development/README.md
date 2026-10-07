<!-- SPDX-License-Identifier: MIT -->
# Development documentation

Implementation planning and validation, separate from user benchmarks.

[Backend roadmap](../BACKEND.md) · [Coordination](../COORDINATION.md) ·
[Progress](../PROGRESS.md) · [Reactive inference](../INFERENCE-REACTIVE.md)

- [MTP development: usage, shared-core contract and remaining gates](MTP.md).
- [VISION development: usage, shared-core contract and remaining gates](VISION.md).
- [Environment and baseline admission](BASELINE.md).
- [Complete prompt retention under cache pressure](CACHE-PROMPT-RETENTION.md).
- [Shared reactive C core — first extraction](CORE-EXTRACTION.md).
- [C17 dense sampler — ownership, build controls and qualification](C17-SAMPLING.md).
- [DS4 directional steering — bank, policy, provider operators and pending GPU gates](STEERING.md).
- [Shared core semantic event contract](../reference/EVENTS.md).
- [Read-only DS4 coverage comparison](DS4-COVERAGE.md).
- [Long-context prefill: measurements and optimization boundaries](PREFILL-ANALYSIS.md).
- [Benchmark closure and the 1M context gate](TEST-COVERAGE-LONG-CONTEXT.md).

## Validation protocols

- [Long-context recall and continuation through 1M](protocols/LONG-CONTEXT-RECALL-GPU-PROTOCOL.md).
- [CORE-GPU-PROTOCOL](protocols/CORE-GPU-PROTOCOL.md).
- [KVC-GPU-PROTOCOL](protocols/KVC-GPU-PROTOCOL.md).
- [PERFORMANCE-PROTOCOL](protocols/PERFORMANCE-PROTOCOL.md).
- [SSD-GPU-PROTOCOL](protocols/SSD-GPU-PROTOCOL.md).
- [SSD-HTTP-PROTOCOL](protocols/SSD-HTTP-PROTOCOL.md).
- [STATE-GPU-PROTOCOL](protocols/STATE-GPU-PROTOCOL.md).
