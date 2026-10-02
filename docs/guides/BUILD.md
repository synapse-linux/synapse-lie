<!-- SPDX-License-Identifier: MIT -->
# Building LIE

[Documentation](../README.md) · [Run the server](USAGE.md)

LIE currently targets Linux. The supported inference configuration on this
branch is Qwen3.8 Flash Next, Unsloth UD-Q4_K_XL, on AMD Strix Halo (`gfx1151`).
Weights are external; a successful CPU build does not provide CPU inference.

## Dependencies

Install development headers and libraries using your distribution's package
manager. Package names vary; CMake checks the dependencies below.

| Dependency | Used by | Required when |
| --- | --- | --- |
| C17 compiler, CMake ≥ 3.21, Threads and libm | Shared engine and tools. | Always. |
| OpenSSL Crypto | State identity, integrity and KVC interchange. | Always. |
| LZ4 and Zstandard | Legacy checkpoint codecs. | `LIE_CHECKPOINT_COMPRESSION=ON` (default). |
| pkg-config, json-c and llhttp (`libllhttp.pc`) | HTTP parsing, protocol and tools. | Full build. |
| libcurl | Monitor client and coupled provider helpers. | Full build. |
| libuv 1.52.1 | Event loop and network lifecycle. | Bundled by default; no system package required. |
| C++20, ROCm/HIP, hipBLAS, hipBLASLt, rocBLAS and hipCUB/rocPRIM | Transitional GPU provider. | `LIE_GUFO_RUNTIME=ON`. |
| ICU, PNG and JPEG | Coupled provider components. | GPU provider build. |
| Python 3 | Source/build verification and test harnesses. | GPU build helpers or `BUILD_TESTING=ON`. |
| Matplotlib | PNG/SVG benchmark exports. | Graph generation only. |

`libsynapse-core` is not currently a dependency. The server and shared C core
run without Python. Direct benchmark suites run in C; `--suite http`,
`--suite http-ssd` and graph export invoke Python helpers.

libuv is included as unmodified upstream sources at version 1.52.1 and built as
a static library. Configure `-DLIE_SYSTEM_LIBUV=ON` to use system libuv ≥ 1.52.1.
Other dependencies remain system libraries. See [provenance](../../third_party/README.md).

## GPU inference build

Run from the repository root. Choose unused labels when preserving an existing
build; the source fetcher refuses to replace an existing source directory.

```sh
python3 -B tools/fetch-gufo.py
python3 -B tools/build-gufo.py qwen-hip --qwen-only --state-access --ds4-state
cmake -S . -B build/release -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_TESTING=OFF -DLIE_GUFO_RUNTIME=ON -DLIE_GUFO_STATE_ACCESS=ON \
  -DGUFO_SOURCE="$PWD/.deps/gufo-state-access-qwen-hip" \
  -DGUFO_BUILD="$PWD/build/qwen-hip"
cmake --build build/release -j2
```

The fetcher acquires official Gufo sources at the recorded pin. The build helper
creates a separate state-access variant for the default DS4 runtime cache;
source and archive hashes are verified before linking. The resulting programs
are `build/release/synapse-lie-server`, `synapse-lie-bench`,
`synapse-lie-bench-gufo-reference`, `synapse-lie-monitor` and `synapse-lie-kvc`.
Keep the benchmark Python helpers beside the executable when copying a build.

No service is installed or started. Continue with the [usage guide](USAGE.md).
On the project's shared GPU host, use the [coordination protocol](../COORDINATION.md)
before a GPU build or model run.

## CPU development and tests

This configuration builds the server without a model provider and exercises
synthetic fixtures. A server without a model reports readiness 503.

```sh
cmake -S . -B build/debug -DCMAKE_BUILD_TYPE=Debug -DLIE_SANITIZERS=ON
cmake --build build/debug -j2
env HIP_VISIBLE_DEVICES=-1 ROCR_VISIBLE_DEVICES=-1 CUDA_VISIBLE_DEVICES=-1 \
  ctest --test-dir build/debug --output-on-failure
```

For the shared C core alone, without HTTP dependencies or Python test harnesses:

```sh
cmake -S . -B build/core -DCMAKE_BUILD_TYPE=Release \
  -DLIE_CORE_ONLY=ON -DBUILD_TESTING=OFF
cmake --build build/core -j2
```

## Build options

| Option | Default | Effect |
| --- | --- | --- |
| `LIE_SYSTEM_LIBUV` | `OFF` | Select system libuv instead of the bundled static library. |
| `LIE_GUFO_RUNTIME` | `OFF` | Link the explicitly selected HIP provider. |
| `LIE_GUFO_STATE_ACCESS` | `OFF` | Enable the verified provider state-access variant. |
| `LIE_CORE_ONLY` | `OFF` | Build the engine without HTTP or provider integration. |
| `LIE_DS4_CACHE_POLICY` | `ON` | Use progressive checkpoints and text-prefix matching by default. |
| `LIE_DS4_RUNTIME_CACHE` | `ON` | Use DS4 model payloads for runtime checkpoints; requires KVC interchange. |
| `LIE_KVC_INTERCHANGE` | `ON` | Build KVC codecs and the offline inspection tool. |
| `LIE_CACHE_UTILITY` | `ON` | Select utility-based retention; `OFF` selects LRU. |
| `LIE_CHECKPOINT_COMPRESSION` | `ON` | Enable legacy checkpoint codecs; DS4 payloads bypass this extra codec. |
| `LIE_SANITIZERS` | `OFF` | Instrument CPU code with ASan and UBSan. |
| `BUILD_TESTING` | `ON` | Build and register development tests. |

SSD persistence is selected at runtime, using an explicit directory and quotas.
It is disabled by default. RAM caching is enabled by default in state-capable
inference builds.
