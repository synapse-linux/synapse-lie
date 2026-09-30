# synapse-lie — Local Inference Engine

Primarily C17, initially targeting Qwen3.8 Flash Next on AMD Strix Halo. An
**explicit embedded Gufo adapter** bootstraps inference; it is subsequently
refactored toward LIE-owned model/session/memory/execution. Delegation is not
reimplementation. See the [backend evolution contract](docs/BACKEND.md).

## Current build: linked T0 candidate, real-model qualification blocked

The C worker, bounded admission, reactive flow and HTTP nonstream/SSE path are
implemented. The optional HIP executable now **links actual pinned Gufo code**;
it is no longer just an adapter object. CPU and synthetic-transport checks pass.
**No LIE model has been loaded or run on the GPU.** Two operator-authorized target
attempts on 2026-09-30 were refused before model open by busy DS4 leases; at 18:53
UTC DS4 was running a GPU benchmark. See [the smoke record](docs/T0-SMOKE.md).
A linked executable and synthetic frames do not establish working original-weight
inference.

Without a configured model, readiness remains 503, models is empty and chat is
503. No production fake-output switch exists. A separate `test-synthetic-server`
is visibly labelled `cpu-test-fixture-NOT-INFERENCE` and is never model evidence.
**v0.1, hardware performance and deployment remain unqualified.**

## Reactive path

```text
HTTP admission -> bounded queue -> one device-owner worker -> lie_flow -> SSE write
                                          ^                              |
                                          +------ credits / release -----+
disconnect / deadline -> flow stop + executor cancellation latch -> safe retirement
```

Eight admitted jobs; one active sequence by default, optionally two interleaved
single-row sequences. This is **not native GPU batching**. Each flow has eight
preallocated 256-byte token slots. SSE keeps a loan until its write callback;
nonstream drains into a bounded aggregation buffer. Wakeups use eventfd/poll and
libuv, not periodic token polling. Backpressure/UTF-8/cancellation/lifetimes are
exercised with the real C serving path and synthetic CPU data, not GPU kernels.

[REACTIVE.md](docs/REACTIVE.md) specifies ownership and remaining gates. Reactive
scheduling **inside pure inference** is a separate [investigation](docs/INFERENCE-REACTIVE.md):
no C1 PP/TG, concurrency or serving speedup has been measured. Moving synchronous
forward off the HTTP loop does not prove faster forward. No JVM, Project Reactor
or Reactive Streams TCK claim.

## CPU build and verification

Installed dependencies: Linux, C17 compiler, CMake, pkg-config, libuv, llhttp,
json-c, libcurl, Threads and libm. Python is development/test tooling only.
Nothing is installed by the build.

```sh
cmake -S . -B build/debug -G Ninja -DCMAKE_BUILD_TYPE=Debug
cmake --build build/debug -j2
ctest --test-dir build/debug --output-on-failure

# After fetching the pinned source below (header check also needs C++20):
# exclusive evidence/build directories; GCC, Clang, ASan/UBSan and header check.
python3 -B tools/verify.py new-cpu-label
```

Eight suites cover flow, parser/UTF-8/wire, worker, metrics, monitor parser,
C ABI layout, HTTP/monitor and HTTP/SSE with the separate synthetic executor.
They cover bounded overload, stalled consumers, peer progress, disconnect,
in-flight cancellation, poison, error terminals and shutdown. They do not
qualify real model output, numerical equivalence, native batching, GPU faults,
state restore, memory fit or performance. No TSan/independent review claim.

## Explicit HIP build, local compilation only

Additional installed toolchain/libraries: C++20, HIP/ROCm, hipBLAS, hipBLASLt,
rocBLAS, hipCUB/rocPRIM headers, ICU, OpenSSL, PNG and JPEG. Runtime/source
provenance and licensing are in [third_party/README.md](third_party/README.md).

```sh
# Only on a fresh checkout; fetch refuses an existing source directory:
python3 -B tools/fetch-gufo.py
python3 -B tools/build-gufo.py new-gufo-label --qwen-only
python3 -B tools/verify-linked.py new-link-label build/new-gufo-label
build/new-link-label/synapse-lie-server --build-info
```

The Qwen-only build uses unchanged upstream source and the upstream model target;
it is a **LIE-owned build subset, not the complete upstream release build**.
It avoids an unrelated full-tree rocWMMA requirement, without fake headers.
Both source and private archives are verified before linking. Compiler commands,
failures, hashes and logs are retained. Verification masks GPU visibility, uses
private HOME/cache directories, and starts only no-model or synthetic tests.
No weights, kernel execution, remote build or dependency installation occurs.
The independent `LIE_GUFO_HEADER_CHECK` option still builds only an object.

After the coordinated lease, fresh preflight and private runtime setup—not as
part of the local verification—an original-weight candidate can be started with:

```sh
# On the qualified target, with private HOME/XDG_CACHE_HOME and the original
# read-only first shard. MODEL is explicitly supplied by the operator.
build/new-link-label/synapse-lie-server --model "$MODEL" \
  --context 4096 --prefill-chunk 2048 --max-active 1 \
  --port 19879 --management-port 19880
```

Opening succeeds asynchronously on the worker; health becomes ready only after
model/executor open, and goes unavailable on poison. Readiness is not a quality
certificate. `--build-info` never opens a model. Diagnostics disclose source pin,
build label, delegated ownership, capabilities and `hardware_qualified:false`.
A build label locates evidence; it is not self-attestation.

T0 accepts text `system/user/assistant` messages, greedy sampling, thinking off,
1–512 output tokens and context-budget validation. Unsupported controls/tools
are explicit errors, not ignored. See [HTTP.md](docs/HTTP.md) for the exact subset.

## Management and monitor

```sh
build/debug/synapse-lie-server --port 19879 --management-port 19880
build/debug/synapse-lie-monitor check --url http://127.0.0.1:19880
# Exit 3 while model readiness is unavailable:
build/debug/synapse-lie-monitor check --require-ready
build/debug/synapse-lie-monitor watch --duration 10 --interval 1
build/debug/synapse-lie-monitor record --duration 10 --output run.jsonl
```

Open `http://127.0.0.1:19880/monitor`. Missing memory/cache/latency/throughput
values remain null. The page is an en_US development fallback, not a localized
release GUI. SIGINT/SIGTERM waits for owned work/write retirement; cancellation
is not GPU preemption. **Keep loopback defaults:** no TLS/authentication exists.
No service, deployment, merge or publication is implied.

## Further contracts

[Progress/evidence](docs/PROGRESS.md) · [Architecture](docs/ARCHITECTURE.md) ·
[Execution ABI](docs/ABI.md) · [Metrics](docs/METRICS.md) ·
[State design—not implemented](docs/STATE.md) · [Baseline](docs/BASELINE.md) ·
[DS4 coordination](docs/COORDINATION.md)

Next: lease-gated pristine comparison and original-model C1 AR qualification,
then requirement-driven T1/T2 replacement. Tool continuation, RAM/SSD state,
native batching, MTP and CUDA retain separate implementation/qualification gates.
