<!-- SPDX-License-Identifier: MIT -->
# Building LIE

[Documentation](../README.md) · [Run the server](USAGE.md)

LIE currently targets Linux. The supported inference configuration on this
branch is Qwen3.8 Flash Next, Unsloth UD-Q4_K_XL, on AMD Strix Halo (`gfx1151`)
and Strix Point (`gfx1150`). Recorded GPU results remain tied to their runtime.
Weights are external; a successful CPU build does not provide CPU inference.

## Dependencies

Install development headers and libraries using your distribution's package
manager. Package names vary; CMake checks the dependencies below.

| Dependency | Used by | Required when |
| --- | --- | --- |
| C17 compiler, CMake ≥ 3.21, Threads and libm | Shared engine and tools. | Always. |
| Make and Ninja | Single-command GPU build. | `make strix-halo` or `make strix-point`. |
| OpenSSL Crypto | State identity, integrity and KVC interchange. | Always. |
| Zstandard | Lossless checkpoint blocks. | `LIE_CHECKPOINT_COMPRESSION=ON` (default). |
| pkg-config, json-c and llhttp (`libllhttp.pc`) | HTTP parsing, protocol and tools. | Full build. |
| libcurl | Monitor, native HTTP benchmark clients and provider helpers. | Full build. |
| libpng | Native benchmark PNG exports and provider components. | Full build. |
| libuv 1.52.1 | Event loop and network lifecycle. | Bundled by default; no system package required. |
| C++20, ROCm/HIP, hipBLAS, hipBLASLt, rocBLAS and hipCUB/rocPRIM | Transitional GPU provider. | `LIE_GUFO_RUNTIME=ON`. |
| ICU `uc` | Reusable C17 Unicode-set registry and UTF8 input decoding. | `LIE_UNICODE_ICU=ON` (default). |
| ICU `i18n` and JPEG | Coupled provider components. | GPU provider build. |

`libsynapse-core` is not currently a dependency. Source/archive verification
uses CMake. All benchmark clients, CSV/JSON reports and SVG/PNG exports use C17.
The default build and CTest suite do not discover or require Python.

libuv is included as unmodified upstream sources at version 1.52.1 and built as
a static library. Configure `-DLIE_SYSTEM_LIBUV=ON` to use system libuv ≥ 1.52.1.
Other dependencies remain system libraries. See [provenance](../../third_party/README.md).

## GPU inference build

With the dependencies above installed, run from the repository root:

```sh
make strix-halo
```

Use `make strix-point` for `gfx1150`. These targets fetch and verify the pinned
provider source, compile the default state-access HIP provider and build the
server, benchmark, report, monitor, KVC tool and steering preparation tool.
Executables are in `build/strix-halo/` or `build/strix-point/`. They need no
Python interpreter. The command does not download weights, install packages or
start a server.

Application compilation uses two jobs by default; `make strix-halo JOBS=4`
changes it. Provider compilation uses one job. Repeating the command reuses
the provider only after verifying source, build options, archives and GPU
target. A changed provider gets a new build directory; old build and failure
logs remain intact in `build/` and `evidence/`. Run logs and actual child exit
codes are in `evidence/strix-halo-build/` or `evidence/strix-point-build/`.

The normal build omits the separate Gufo comparison executable. To build that
control or select other CMake options, use the advanced recipe below.

### Advanced CMake build and comparison control

Run from the repository root. Choose unused labels when preserving an existing
build; the source fetcher refuses to replace an existing source directory.

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

The fetcher acquires official Gufo sources at the recorded pin. The build helper
creates a separate state-access variant for the default DS4 runtime cache;
source and archive hashes are verified before linking. The benchmark control
uses a complete OFF provider, including its numerical/controller archives;
mixing an OFF sampler with ON request-state layouts is rejected. Configure
`-DLIE_GUFO_REFERENCE_BENCH=OFF` to build only LIE without this comparison control.

Original IQ2/Q2 Qwen storage support is default ON in the owned provider
(`LIE_QWEN_Q2_FORMATS`). To disable it, pass `-DLIE_QWEN_Q2_FORMATS=OFF` to both
provider commands and the application configure command. The verifier binds
the exact format recipe and patch and refuses mismatched selections or older
receipts. This adds original IQ2_XXS experts, padded Q2_K down storage and exact
F16 HC injection widening. Recognizing the unused MXFP4 predictor descriptor
does not enable its MTP execution. The [format contract](../Q2-FORMAT-CONTRACT.md)
states the supported geometry; current-provider GPU quality/performance remain
under qualification.

Prefill attention observation is default ON. To disable it, pass
`-DLIE_ATTENTION_DISPATCH_STATS=OFF` to **both provider build commands and the
application configure command**. Rebuild the complete private providers and
clients; the verifier rejects mismatched options, non-boolean identities or older
observer-free receipts. The optional Point coordinator uses these same complete
CMake provider recipes for both variants.
Sparse WMMA prefill through 1,048,576 visible tokens is default ON in the owned
variant (`LIE_LONG_CONTEXT_WMMA`). Short visible spans keep the existing workspace;
long spans use a separately compiled larger workspace. To retain the 262,144-token
WMMA limit and its scalar fallback, pass `-DLIE_LONG_CONTEXT_WMMA=OFF` to both
provider builds and the application configure command. The receipt verifier
rejects mismatched or missing selections. This option changes numerical dispatch;
original-weight correctness, resource use and performance at long depths remain
under qualification. Both comparison arms must keep this option equal unless it
is the declared variable being measured.
The resulting programs
are `build/release/synapse-lie-server`, `synapse-lie-bench`,
`synapse-lie-bench-gufo-reference`, `synapse-lie-monitor` and `synapse-lie-kvc`.
The opt-in provider also builds the native diagnostic `lie-steering-build` for
[paired-prompt direction preparation](USAGE.md#directional-steering).
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
| `LIE_UNICODE_ICU` | `ON` | Build `lie_grammar_unicode`, using public ICU C APIs. OFF omits it for a minimal core; C17 provider sampling requires ON. ICU remains a third-party dependency. |
| `LIE_C17_SAMPLING` | `ON` | Use owned C selection/history, speculative probabilities, grammar runtimes, regex syntax/assertion/expression/derivative/DFA construction and Unicode-set/input handling; OFF selects the provider control. Provider and application builds must agree. |
| `LIE_VISION_WEIGHT_DECODE` | `ON` | Decode F16/Q8_0 projector weights once for the BF16 GPU encoder. OFF accepts BF16 dense weights only; provider and application builds must agree. |
| `LIE_DIRECTIONAL_STEERING` | `ON` | Build experimental activation operators; requires the verified state-access provider variant and matching archive selection. Public controls/GPU qualification remain pending. |
| `LIE_LONG_CONTEXT_WMMA` | `ON` | Enable a separate sparse-WMMA workspace through 1M visible tokens. Requires the owned source variant and matching provider/application selection. OFF retains the 262k WMMA limit and scalar fallback. Long-depth GPU qualification remains pending. |
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
