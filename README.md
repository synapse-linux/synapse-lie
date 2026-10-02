<!-- SPDX-License-Identifier: MIT -->
# Synapse LIE

Synapse LIE is a local GPU inference engine with an OpenAI-compatible HTTP API
and a command-line benchmark tool. Its shared C17 core manages reactive
scheduling, concurrent requests, cancellation, metrics and prompt caching.
The current numerical backend is an embedded Gufo adapter using C++ and HIP.

**Development status:** text inference is tested with Qwen3.8 Flash Next
(Unsloth UD-Q4_K_XL) on AMD Strix Halo (`gfx1151`). The HTTP server supports
contexts up to 262,144 tokens and up to eight active sequences. MTP, vision and
other model/platform combinations are not yet supported on this branch.

[Build](docs/guides/BUILD.md) · [Usage](docs/guides/USAGE.md) ·
[Benchmarks and graphs](docs/benchmarks/README.md) · [Changelog](CHANGELOG.md)

## Features

- Chat Completions and stateless Responses, with JSON and SSE output.
- Function calls and tool results through the standard OpenAI protocol; Pi can
  connect directly over HTTP.
- Native GPU decode batching, driven by sequence readiness and output credits.
- Shared RAM prefix cache, enabled by default with a 4 GiB budget. SSD persistence
  is optional and uses an explicit directory and quota.
- `synapse-lie-bench` for prefill, generation, context-depth and concurrency
  measurements, with CSV, JSON, SVG and PNG exports.

See the [usage guide](docs/guides/USAGE.md) for API limits and configuration.

## Requirements

| Component | Requirement |
| --- | --- |
| System | Linux, a C17 compiler, CMake 3.21 or newer, and pkg-config. |
| C libraries | OpenSSL Crypto, json-c, llhttp and libcurl development files; LZ4 and Zstandard for the default checkpoint build. |
| Event loop | **libuv 1.52.1 is included** and linked statically. A system-library option is available. |
| GPU backend | AMD Strix Halo, C++20, ROCm/HIP, hipBLAS, hipBLASLt, rocBLAS, hipCUB/rocPRIM, ICU, PNG and JPEG. |
| Build/test tools | Python 3 verifies the optional Gufo build and runs test harnesses. |
| Optional benchmark tools | Python 3 for HTTP benchmark suites; Matplotlib for graph export. |

The server and shared core do not require Python at runtime. `libsynapse-core`
is not currently linked. Detailed dependencies and build options are in the
[build guide](docs/guides/BUILD.md).

## Build

From a fresh checkout, with the dependencies above installed:

```sh
python3 -B tools/fetch-gufo.py
python3 -B tools/build-gufo.py qwen-hip --qwen-only --state-access --ds4-state
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
