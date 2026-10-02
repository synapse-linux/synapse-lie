<!-- SPDX-License-Identifier: MIT -->
# Documentation index

This documentation describes `feature/openai-reactive-api`. Dated reports retain
their tested source and conditions; work in other feature branches is not
implicitly integrated. Start with the [project README](../README.md) for current
capabilities and build commands.

## Benchmarks by model and platform

The [benchmark index](benchmarks/README.md) separates model, platform and weight
format, with links to results, graphs, raw values and unmeasured combinations.
[CLI usage](CONTEXT-COMPARISON.md), [methodology](BENCHMARKING.md) and
[remaining tests](TEST-COVERAGE-LONG-CONTEXT.md) distinguish engine support from
an implemented test and a completed measurement.

## Engine and clients

- [Architecture and shared core](ARCHITECTURE.md), [extraction](CORE-EXTRACTION.md)
  and [backend ownership roadmap](BACKEND.md).
- [Execution ABI](ABI.md), [reactive contracts](REACTIVE.md),
  [inference scheduling analysis](INFERENCE-REACTIVE.md) and [metrics](METRICS.md).
- [RAM and hybrid state](STATE.md), [optional SSD persistence](SSD-PREFIX.md)
  and [prefill analysis](PREFILL-ANALYSIS.md).
- [HTTP and SSE](HTTP.md), [OpenAI API scope](OPENAI-REACTIVE.md),
  [function tools and Pi](SERVER-TOOLS.md).

## Qualification and coordination

- [Hardware ownership and leases](COORDINATION.md).
- [Shared-core GPU protocol](CORE-GPU-PROTOCOL.md),
  [RAM state protocol](STATE-GPU-PROTOCOL.md),
  [SSD restart protocol](SSD-GPU-PROTOCOL.md),
  [SSD HTTP/restart/concurrency client and protocol](SSD-HTTP-PROTOCOL.md),
  [executor and HTTP performance protocol](PERFORMANCE-PROTOCOL.md).
- [Initial model serving](T0-SMOKE.md), [lifecycle](T0-LIFECYCLE.md),
  [OpenAI GPU checks](OPENAI-GPU.md), [256K and Pi checks](HTTP-256K-PI.md).
- [DS4 coverage inspection](DS4-COVERAGE.md), [baseline](BASELINE.md)
  and [third-party provenance](../third_party/README.md).
- [Completed SSD restart/C1 measurements and temperature timeline](SSD-GPU-COMPLETION.md).
- [Cache build comparisons and HTTP SSD GPU results](CACHE-FEATURES-GPU.md).
- [Checkpoint compression cost, exact restore and benefit admission](CACHE-COMPRESSION-GPU.md).

## History and parallel work

[PROGRESS.md](PROGRESS.md) is an append-only development history rather than a
current capability matrix. Earlier Q2 investigations remain in
[compatibility](Q2-COMPATIBILITY.md), [HIP](Q2-HIP.md),
[first model](Q2-FIRST-MODEL.md), [extended checks](Q2-EXTENDED.md),
[benchmark gates](ANTIREZ-BENCHMARKS.md) and [the historical replan](REPLAN.md).
Their withdrawal does not describe the state of a later parallel feature branch.

- [Shared DS4 cache policy, options and remaining interoperability gates](CACHE-DS4-POLICY.md)
