<!-- SPDX-License-Identifier: MIT -->
# Synapse LIE

Synapse LIE is a local GPU inference engine with an OpenAI-compatible HTTP API
and a command-line benchmark tool. Its shared C17 core manages reactive
scheduling, concurrent requests, cancellation, metrics and prompt caching.
The current numerical backend is an embedded Gufo adapter using C++ and HIP,
with owned [C17 sampling, history and grammar runtime](docs/development/C17-SAMPLING.md).
Dense sampling has recorded GPU checks; the new history, speculative probability
and byte/numeric grammar extractions have host checks and still require GPU
correctness and performance qualification. Schema compilation and string/regex
predicates remain transitional.
[Directional steering](docs/guides/USAGE.md#directional-steering) has shared-core
and server/bench controls with host validation, including scheduled benchmark
changes, HTTP creation-time plans and live updates to individual stored choices.
Numerical GPU qualification remains pending.

**Development status:** text inference is tested with Qwen3.8 Flash Next
(Unsloth UD-Q4_K_XL) on AMD Strix Halo (`gfx1151`). The HTTP server supports
native contexts up to 262,144 tokens and up to eight active sequences.
Explicit [YaRN profiles](docs/guides/CONTEXT.md) extend the configured limit to
1,048,576 tokens. Strix Point verifies allocation at that capacity and completes
1,048,448 physical prefill tokens. The required 128-token generation gate remains
failed on early EOS; long-context quality and performance remain under qualification.
The [native core bench](docs/guides/BENCHMARKS.md#shared-engine-and-cache) can
explicitly continue past EOS for fixed-token measurements; its GPU gate is pending.
Experimental [MTP](docs/development/MTP.md) and
[vision](docs/development/VISION.md) share model-neutral C core contracts and
can be configured together. Recorded original-weight functional checkpoints
cover HTTP, RAM/SSD checkpoints and reactive cancellation. The integrated
sampler/vision runtime passes the recorded GPU functional checks; quality and
performance gates remain open.

The [original-weight OpenAI control gates](docs/benchmarks/models/qwen3.8-flash-next/strix-point/README.md#original-weight-http-ar-and-mtp-gates)
pass 34 checks in both AR and MTP on Strix Point, including tools and retained
Responses lifecycle. The receipts identify the tested runtime and limits.

[Build](docs/guides/BUILD.md) · [Usage](docs/guides/USAGE.md) ·
[Benchmarks and graphs](docs/benchmarks/README.md) · [Changelog](CHANGELOG.md)

## Features

- Chat Completions and Responses, with JSON/SSE, multiple choices, token
  probabilities, constrained JSON output and configurable temperature/top-k/top-p/min-p.
- Stored Responses, conversation continuation and cancellable background jobs;
  history and resource limits live in the shared C core.
- Function calls, incremental arguments and tool results through the standard
  OpenAI protocol; [agent clients](docs/guides/AGENT-CLIENTS.md) can connect
  directly over HTTP.
- Shared C17 [output events](docs/reference/EVENTS.md) for HTTP and direct clients:
  text, incremental function arguments, validated tool calls and typed turn
  completion, with output credits and cancellation.
- Native GPU decode batching, driven by sequence readiness and output credits.
- Experimental [MTP verified bursts](docs/development/MTP.md),
  with explicit model configuration and complete predictor checkpoints.
  Original-weight checkpoint and cancellation checks pass; paired MTP/AR
  measurements are available in the [Strix Point benchmarks](docs/benchmarks/models/qwen3.8-flash-next/strix-point/README.md).
  Broader quality and replicated performance gates remain open.
- Experimental [vision image inputs](docs/development/VISION.md),
  with explicit model configuration and semantic RAM/SSD cache binding.
  F16/Q8_0 projector weights are decoded once in C for the BF16 GPU encoder.
  MTP and vision can run together through the same core and cache.
  Original-weight image/cache and combined checkpoint checks pass; quality and
  performance qualification remain open. Strix Point direct-core AR and MTP
  vision gates also pass with the copied Q8 projector and exact output IDs.
- Shared RAM KV cache, enabled by default with a 4 GiB retention budget.
  Optional KV checkpoint persistence uses `--kv-disk-dir` and explicit budgets.
- `synapse-lie-bench` for prefill, generation, context-depth and concurrency
  measurements, including separate prefill/decode durations, with CSV, JSON,
  SVG and PNG exports, reproducible shared-core sampling controls and optional
  live prefill progress on stderr.

See the [usage guide](docs/guides/USAGE.md) for API limits and configuration.

An omitted or null output limit uses the available context up to the engine's
advertised 4,096-token output ceiling. `/v1/models` reports both limits;
explicit positive output budgets remain exact.

## Strix Point port

The [ROCm 10 comparison gate](docs/STRIX-POINT-ROCM10.md) records the
Fedora Minimal 44 image provenance found on `.157` and independently built
Fedora 44 and AlmaLinux 10.2 `gfx1150` RPM candidates on `.161`. Both RPM
images build. With the original `.161` kernel 6.16.3, native HIP, Python and
LIE probes failed on primitive ROCm 10 memory operations while ROCm 7.2 passed.
After updating to Pop!_OS kernel 7.1.5, the unchanged ROCm 10 probes pass and
short original-weight LIE/Gufo direct tests complete. Their ROCm 10 results
match each other but differ numerically from ROCm 7.2 at 0/4K. The
[Docker-managed Distrobox `single` report](docs/benchmarks/2026-10-02/strix-point/rocm10-distrobox-single/README.md)
now includes the complete eight-depth LIE occupied-prefix run to 128K, with
prefill, decode, telemetry and graphs. The
[three-arm Distrobox multi-user report](docs/benchmarks/2026-10-02/strix-point/rocm10-distrobox-multi/README.md)
compares LIE reactive, Gufo and serial C1/2/4/6/8 with the earlier ROCm 7.2
results: at C8 ROCm 10 LIE reaches 32.837 aggregate decode token/s, 3.15× its
serial control. These are direct engine sessions, not HTTP clients. The earlier
ROCm 7.2 output IDs and numerical frontiers differ at every tested point, so
the cross-stack throughput comparison does not establish quality equivalence.
The paired ROCm 10 [fresh full-prompt comparison](docs/benchmarks/models/qwen3.8-flash-next/strix-point/README.md#fresh-full-prompt-prefill-through-128k)
now passes through 128K and separately near 256K. The
[modern GPU MTP/AR comparison](docs/benchmarks/models/qwen3.8-flash-next/strix-point/README.md#modern-c17-core-mtp-vs-ar-on-the-gpu)
passes four matched direct-core pairs through 128K. The new
[served HTTP AR/MTP report](docs/benchmarks/2026-10-04/strix-point/http-multi/README.md)
adds complete original-weight LIE/official Gufo comparisons at C1/2/4/6/8,
with fixed eight-session and fresh sessions=C lifecycles, prefill accounting,
telemetry, graphs and sealed raw evidence. It measures 4K context; longer
served-context performance is in the separate
[cold HTTP depth report](docs/benchmarks/2026-10-04/strix-point/http-depth/README.md):
LIE and official Gufo AR/MTP pass paired, cache-disabled C1 GPU measurements
at 8K, 32K, 128K and near 256K, with prefill, decode, TTFT, resource samples
and offline-verifiable raw archives. These measurements use native context
through 262,144 tokens; they do not qualify YaRN, 1M or long-context multi-client throughput.
The [r5 direct reactive and vision gates](docs/benchmarks/models/qwen3.8-flash-next/strix-point/README.md#direct-reactive-core-and-q8-vision-gates)
exercise held output credit, peer completion, cancellation and Q8-projector
AR/MTP parity on the original GPU weights; they are functional, not a new
throughput claim.

The isolated `feature/strix-point-ud` increment adds explicit gfx1150 build and
device admission, preserving the shared C17 reactive core and default gfx1151
target. CPU architecture checks and headless ASan/UBSan tests pass on
`pop@192.168.5.161`; the gfx1150 numerical archives and executables compile/link,
and no-model startup passes in the existing target container/runtime. The full
local sanitizer suite passes 34/34. After the operator's temporary service-stop
grant, the real gfx1150 HIP allocation/copy/rocBLAS diagnostic passes and llama
is restored. All four original UD shards are now copied and SHA-256 verified;
source files on .157 remain intact. The first original-weight shared-core GPU
smoke on .161 passes: nine prompt tokens, 32 generated tokens, identical output
across one warmup and three repetitions. Warm decode averages 10.56 token/s;
this short-prompt result does not qualify long-context performance or parity.
The additional C17 HIP/rocBLAS diagnostic is compiled; its synthetic fault
controls pass ASan/UBSan locally and on .161, and its no-device help path loads
on the target. Pinned four-shard staging uses complete SHA-256 verification.
The operator-authorized TTM change and reboot increased actual HIP memory from
61.72 to **96 GiB**; the post-boot HIP/rocBLAS probe passes. This raises the
allocation limit; the bounded UD smoke fits. The subsequent direct executor
benchmark exercises occupied prefixes through 128K.
The [full Strix Point report](docs/STRIX-POINT-RESULT.md) includes every sample,
fresh prefill versus RAM reuse, decode and client latency, memory/temperature/thread
graphs, portable CSV/JSON and an offline reproducer. Its coverage matrix identifies
the long-context, concurrency, HTTP and comparative checks still required on .161.
The follow-up [direct benchmark report](docs/STRIX-POINT-BENCHMARK-RESULT.md)
uses `synapse-lie-bench` with the earlier PP2048/TG128 method. The new
operator-approved 100 C campaigns complete all eight occupied-prefix depths
0–128K for both LIE and direct Gufo, with matching physical prompts, outputs
and prefill/decode frontiers. Paired 256K-capacity loading also passes. The
earlier 85 C stop and its partial/cleanup evidence remain a failed attempt;
the separate three-arm C1/2/4/6/8 direct benchmark also passes with exact
frontier parity. At C8 reactive/native Gufo decode is 32.18/32.15 aggregate
token/s versus 10.32 for serial LIE; all measured reactive C2–C8 dispatches
use native inference batches. The paired direct fresh-prompt suite also passes
1.5K/8K/32K/128K physical prompts at capacity 256K, with two measured samples
per point and exact output/frontier parity. The direct near-256K pair also passes
with 258794 physical prompt tokens, two full 128-token outputs per arm and
exact frontiers. These direct benchmarks do not establish HTTP performance;
see the separate [served HTTP report](docs/benchmarks/2026-10-04/strix-point/http-multi/README.md).
See also [implementation, receipts and remaining qualification](docs/STRIX-POINT.md).


## Requirements

| Component | Requirement |
| --- | --- |
| System | Linux, a C17 compiler, CMake 3.21 or newer, and pkg-config. |
| C libraries | OpenSSL Crypto, json-c, llhttp, libcurl and libpng development files; Zstandard for the default checkpoint build. |
| Event loop | **libuv 1.52.1 is included** and linked statically. A system-library option is available. |
| GPU backend | AMD Strix Halo, C++20, ROCm/HIP, hipBLAS, hipBLASLt, rocBLAS, hipCUB/rocPRIM, ICU, PNG and JPEG. |

Build, server, benchmarks, graphs and the default tests run without Python.
`libsynapse-core` is not currently linked. Detailed dependencies and build options are in the
[build guide](docs/guides/BUILD.md).

## Build

From a fresh checkout, with the dependencies above installed:

```sh
cmake -P cmake/provider/Fetch.cmake
cmake -DLABEL=qwen-hip -P cmake/provider/Build.cmake
cmake -S . -B build/release -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_TESTING=OFF -DLIE_GUFO_RUNTIME=ON -DLIE_GUFO_STATE_ACCESS=ON \
  -DGUFO_SOURCE="$PWD/.deps/gufo-state-access-qwen-hip" \
  -DGUFO_BUILD="$PWD/build/qwen-hip"
cmake --build build/release -j2
```

The helpers fetch a pinned upstream source and build the HIP provider. They do
not download model weights. See [build instructions](docs/guides/BUILD.md) for a
CPU-only development build, sanitizer checks and the system-libuv option.

## Run

Download all four **UD-Q4_K_XL** GGUF shards from the
[pinned model revision](https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF/tree/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL)
into one directory, then pass the first shard:

```sh
build/release/synapse-lie-server \
  --model /path/to/Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf \
  --model-id qwen3.8-flash-next \
  --host 127.0.0.1 --port 8000 --context 262144 --max-active 1
```

In another terminal:

```sh
curl http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3.8-flash-next","messages":[{"role":"user","content":"Hello!"}],"max_tokens":128,"temperature":0}'
```

Use the [usage guide](docs/guides/USAGE.md) for streaming, Responses, Pi,
concurrency, RAM/SSD cache settings and troubleshooting.

## Benchmarks

**[Qwen3.8 Flash Next / AMD Strix Halo: results, complete tables and graphs](docs/benchmarks/models/qwen3.8-flash-next/strix-halo/README.md)**

The results page brings together context-depth, multi-user and full-prefill
measurements. Each section states what was measured and how it relates to
Gufo's protocol. Use the [benchmark guide](docs/guides/BENCHMARKS.md) to reproduce
workloads or generate graphs from existing results.
The native `http-curve` client reproduces Gufo's calibrated cached-conversation
curve through 128K; `http-multi` measures prepared concurrent sessions. Both
save complete request evidence and generate CSV, JSON, SVG and PNG in C.
See [commands and measurement scopes](docs/guides/BENCHMARKS.md).

## Documentation and support

[Documentation](docs/README.md) includes user guides, API/core references and the
development roadmap. Report problems or request features in
[GitHub issues](https://github.com/synapse-linux/synapse-lie/issues), including
the build, platform, model format and command used.

Maintained by [Synapse Linux](https://github.com/synapse-linux).
First-party code is [MIT licensed](LICENSE); bundled and linked components retain
[their own licenses and attribution](third_party/README.md).
