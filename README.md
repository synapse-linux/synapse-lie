<!-- SPDX-License-Identifier: MIT -->
# Synapse LIE

Synapse LIE is a local GPU inference engine with an OpenAI-compatible HTTP API
and a command-line benchmark tool. Its shared C17 core manages reactive
scheduling, concurrent requests, cancellation, metrics and prompt caching.
The current numerical backend is an embedded Gufo adapter using C++ and HIP,
with owned [C17 sampling, grammar and schema components](docs/development/C17-SAMPLING.md).
Gufo still owns model execution and controller state. The current
[backend roadmap](docs/BACKEND.md#current-roadmap--2026-10-06-utc) covers the
sampler integration and qualification; full executor ownership is the
architectural destination.

**Development status:** text inference is tested with Qwen3.8 Flash Next
(Unsloth UD-Q4_K_XL) on AMD Strix Halo (`gfx1151`) and Strix Point (`gfx1150`).
The HTTP server supports native contexts up to 262,144 tokens and up to eight
active sequences.
Explicit [YaRN profiles](docs/guides/CONTEXT.md) extend the configured limit to
1,048,576 tokens. Strix Point completes **1,048,448 physical prefill tokens and
128 output tokens** with the native core bench's explicit fixed-token EOS policy.
The [1M results and reproduction command](docs/benchmarks/models/qwen3.8-flash-next/strix-point/README.md#physical-1m-context-and-fixed-generation)
include prefill, decode, durations and memory. Long-context recall quality and
matched performance comparisons remain under qualification.
Experimental [MTP](docs/development/MTP.md) and
[vision](docs/development/VISION.md) share model-neutral C core contracts and
can be configured together. Recorded original-weight functional checkpoints
cover HTTP, RAM/SSD checkpoints and reactive cancellation. The integrated
sampler/vision runtime passes the recorded GPU functional checks; quality and
performance gates remain open.

The [original-weight OpenAI control gates](docs/benchmarks/models/qwen3.8-flash-next/strix-point/README.md#original-weight-http-ar-and-mtp-gates)
pass 37 checks in both AR and MTP on Strix Point, including tools, automatic
output budgets and retained Responses lifecycle. The corrected integer validator
also passes [66 additional JSON/SSE checks in each mode](docs/development/validation/output-schema-integer-point-gpu-2026-10-06.json).
The receipts identify the tested runtime and limits.

The unchanged [Terminal Bench Core-19 smoke](docs/benchmarks/models/qwen3.8-flash-next/strix-point/README.md#terminal-bench-core-19)
passes 1/1 task on Strix Point. The full 19-task evaluation is deferred until
the functional modifications are finished.

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
  Text-prefix reuse preserves saved token boundaries in both RAM and SSD.
  [SSD text-restart checks](docs/benchmarks/models/qwen3.8-flash-next/strix-point/README.md#ssd-text-reconstruction-across-processes)
  cover original-weight AR/MTP histories longer than fresh tokenization.
- `synapse-lie-bench` for prefill, generation, context-depth and concurrency
  measurements, including separate prefill/decode durations, with CSV, JSON,
  SVG and PNG exports, reproducible shared-core sampling controls and optional
  live prefill progress on stderr.

See the [usage guide](docs/guides/USAGE.md) for API limits and configuration.

An omitted or null output limit uses the available context up to the engine's
advertised 4,096-token output ceiling. `/v1/models` reports both limits;
explicit positive output budgets remain exact.

## Requirements

| Component | Requirement |
| --- | --- |
| System | Linux, a C17 compiler, CMake 3.21 or newer, and pkg-config. |
| C libraries | OpenSSL Crypto, json-c, llhttp, libcurl and libpng development files; Zstandard for the default checkpoint build. |
| Event loop | **libuv 1.52.1 is included** and linked statically. A system-library option is available. |
| GPU backend | AMD Strix Halo or Strix Point, C++20, ROCm/HIP, hipBLAS, hipBLASLt, rocBLAS, hipCUB/rocPRIM, ICU, PNG and JPEG. |

Build, server, benchmarks, graphs and the default tests run without Python.
`libsynapse-core` is not currently linked. Detailed dependencies and build options are in the
[build guide](docs/guides/BUILD.md).

## Build

From a fresh checkout, with the dependencies above installed:

```sh
cmake -P cmake/provider/Fetch.cmake
lie_target_arch=gfx1151 # Strix Halo; use gfx1150 for Strix Point.
cmake -DLABEL=qwen-hip -DLIE_HIP_ARCHITECTURE="$lie_target_arch" -P cmake/provider/Build.cmake
cmake -DLABEL=qwen-reference-hip -DLIE_C17_SAMPLING=OFF \
  -DLIE_HIP_ARCHITECTURE="$lie_target_arch" -P cmake/provider/Build.cmake
cmake -S . -B build/release -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_TESTING=OFF -DLIE_GUFO_RUNTIME=ON -DLIE_GUFO_STATE_ACCESS=ON \
  -DLIE_HIP_ARCHITECTURE="$lie_target_arch" \
  -DGUFO_SOURCE="$PWD/.deps/gufo-state-access-qwen-hip" \
  -DGUFO_BUILD="$PWD/build/qwen-hip" \
  -DGUFO_REFERENCE_BUILD="$PWD/build/qwen-reference-hip"
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

| Model | Platform | Results and graphs |
| --- | --- | --- |
| Qwen3.8 Flash Next, UD-Q4_K_XL | AMD Strix Halo (`gfx1151`) | [Complete tables and graphs](docs/benchmarks/models/qwen3.8-flash-next/strix-halo/README.md). |
| Qwen3.8 Flash Next, UD-Q4_K_XL | AMD Strix Point (`gfx1150`) | [Complete tables, graphs and physical 1M](docs/benchmarks/models/qwen3.8-flash-next/strix-point/README.md). |

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
