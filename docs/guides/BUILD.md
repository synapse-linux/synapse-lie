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
| Zstandard | Lossless checkpoint blocks. | `LIE_CHECKPOINT_COMPRESSION=ON` (default). |
| pkg-config, json-c and llhttp (`libllhttp.pc`) | HTTP parsing, protocol and tools. | Full build. |
| libcurl | Monitor, native HTTP benchmark clients and provider helpers. | Full build. |
| libpng | Native benchmark PNG exports and provider components. | Full build. |
| libuv 1.52.1 | Event loop and network lifecycle. | Bundled by default; no system package required. |
| C++20, ROCm/HIP, hipBLAS, hipBLASLt, rocBLAS and hipCUB/rocPRIM | Transitional GPU provider. | `LIE_GUFO_RUNTIME=ON`. |
| ICU and JPEG | Coupled provider components. | GPU provider build. |

`libsynapse-core` is not currently a dependency. Source/archive verification
uses CMake. All benchmark clients, CSV/JSON reports and SVG/PNG exports use C17.
The default build and CTest suite do not discover or require Python.

libuv is included as unmodified upstream sources at version 1.52.1 and built as
a static library. Configure `-DLIE_SYSTEM_LIBUV=ON` to use system libuv ≥ 1.52.1.
Other dependencies remain system libraries. See [provenance](../../third_party/README.md).

## GPU inference build

Run from the repository root. Choose unused labels when preserving an existing
build; the source fetcher refuses to replace an existing source directory.

```sh
cmake -P cmake/provider/Fetch.cmake
cmake -DLABEL=qwen-hip -P cmake/provider/Build.cmake
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
`synapse-lie-bench-report` is also available for offline reporting. The benchmark
executables do not need adjacent scripts or a Python interpreter.

To build the native HTTP benchmark client without a GPU provider or model files:

```sh
cmake -S . -B build/bench -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_TESTING=OFF -DLIE_GUFO_RUNTIME=OFF
cmake --build build/bench --target synapse-lie-bench synapse-lie-bench-report -j2
build/bench/synapse-lie-bench --suite http-curve --help
```

This client talks to an already running server. Canonical Gufo prompt generation,
depth calibration, request collection and CSV/JSON/SVG/PNG export are C17.
The same binary also retains direct/core benchmarks when built with a provider.
Historical Python launch supervisors and opt-in test oracles are development
tools; neither is invoked by the native client or required to run its reports.

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

For the shared C core alone, without HTTP dependencies:

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
| `LIE_C17_SAMPLING` | `ON` | Use owned C selection/history, speculative probabilities, byte/numeric/Unicode/vocabulary grammar runtimes; OFF selects the provider control. Provider and application builds must agree. |
| `LIE_VISION_WEIGHT_DECODE` | `ON` | Decode F16/Q8_0 projector weights once for the BF16 GPU encoder. OFF accepts BF16 dense weights only; provider and application builds must agree. |
| `LIE_DIRECTIONAL_STEERING` | `ON` | Build experimental activation operators; requires the verified state-access provider variant and matching archive selection. Public controls/GPU qualification remain pending. |
| `LIE_CORE_ONLY` | `OFF` | Build the engine without HTTP or provider integration. |
| `LIE_DS4_CACHE_POLICY` | `ON` | Use progressive checkpoints and text-prefix matching by default. |
| `LIE_DS4_RUNTIME_CACHE` | `ON` | Use DS4 model payloads for runtime checkpoints; requires KVC interchange. |
| `LIE_KVC_INTERCHANGE` | `ON` | Build KVC codecs and the offline inspection tool. |
| `LIE_CACHE_UTILITY` | `ON` | Select utility-based retention; `OFF` selects LRU. |
| `LIE_CHECKPOINT_COMPRESSION` | `ON` | Enable Zstandard checkpoint blocks; DS4 payloads bypass this extra codec. |
| `LIE_SANITIZERS` | `OFF` | Instrument CPU code with ASan and UBSan. |
| `BUILD_TESTING` | `ON` | Build and register native development tests. |
| `LIE_MTP` | `ON` | Build the model-neutral MTP feature; predictor/encoder admission remains explicit. |
| `LIE_VISION` | `ON` | Build the model-neutral vision feature; predictor/encoder admission remains explicit. |
| `LIE_LEGACY_PYTHON_TESTS` | `OFF` | Additionally run independent historical Python test oracles; requires Python only when explicitly enabled. |

KV disk persistence is selected at runtime, using an explicit directory and quotas.
It is disabled by default. RAM caching is enabled by default in state-capable
inference builds.
