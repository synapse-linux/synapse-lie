<!-- SPDX-License-Identifier: MIT -->
# Synapse LIE

Synapse LIE is a local GPU inference engine with an OpenAI-compatible HTTP API
and a command-line benchmark tool. Its shared C17 core manages reactive
scheduling, concurrent requests, cancellation, metrics and prompt caching.
The current numerical backend is an embedded Gufo adapter using C++ and HIP,
with an owned [C17 dense sampler](docs/development/C17-SAMPLING.md).

**Development status:** text inference is tested with Qwen3.8 Flash Next
(Unsloth UD-Q4_K_XL) on AMD Strix Halo (`gfx1151`). The HTTP server supports
contexts up to 262,144 tokens and up to eight active sequences.
Experimental [MTP](docs/development/MTP.md) and
[vision](docs/development/VISION.md) share model-neutral C core contracts and
can be configured together. CPU checks and HIP linking do not qualify its
original-weight behavior or performance; other real model bindings remain open.

[Build](docs/guides/BUILD.md) · [Usage](docs/guides/USAGE.md) ·
[Benchmarks and graphs](docs/benchmarks/README.md) · [Changelog](CHANGELOG.md)

## Features

- Chat Completions and Responses, with JSON/SSE, multiple choices, token
  probabilities and constrained JSON output.
- Stored Responses, conversation continuation and cancellable background jobs;
  history and resource limits live in the shared C core.
- Function calls and tool results through the standard OpenAI protocol; Pi can
  connect directly over HTTP.
- Shared C17 [output events](docs/reference/EVENTS.md) for HTTP and direct clients:
  text, validated tool calls and typed turn completion, with output credits and cancellation.
- Native GPU decode batching, driven by sequence readiness and output credits.
- Experimental [MTP verified bursts](docs/development/MTP.md),
  with explicit model configuration and complete predictor checkpoints.
  Original-weight prefix continuation passes; wider correctness and performance
  qualification remain pending.
- Experimental [vision image inputs](docs/development/VISION.md),
  with explicit model configuration and semantic RAM/SSD cache binding.
  MTP and vision can run together through the same core and cache.
  Original-weight vision and combined qualification remain pending.
- Shared RAM KV cache, enabled by default with a 4 GiB retention budget.
  Optional KV checkpoint persistence uses `--kv-disk-dir` and explicit budgets.
- `synapse-lie-bench` for prefill, generation, context-depth and concurrency
  measurements, with CSV, JSON, SVG and PNG exports.

See the [usage guide](docs/guides/USAGE.md) for API limits and configuration.

## Requirements

| Component | Requirement |
| --- | --- |
| System | Linux, a C17 compiler, CMake 3.21 or newer, and pkg-config. |
| C libraries | OpenSSL Crypto, json-c, llhttp, libcurl and libpng development files; LZ4 and Zstandard for the default checkpoint build. |
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

## Documentation and support

[Documentation](docs/README.md) includes user guides, API/core references and the
development roadmap. Report problems or request features in
[GitHub issues](https://github.com/synapse-linux/synapse-lie/issues), including
the build, platform, model format and command used.

Maintained by [Synapse Linux](https://github.com/synapse-linux).
First-party code is [MIT licensed](LICENSE); bundled and linked components retain
[their own licenses and attribution](third_party/README.md).
