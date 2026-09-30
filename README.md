# synapse-lie — Local Inference Engine

C17 local serving runtime under development, initially targeting Qwen3.8 Flash
Next on AMD Strix Halo. One resident model/device per future inference instance.

**Current increment: working CPU management/observability runtime, not an LLM
server yet.** No model is loaded. Readiness is 503, `/v1/models` is empty and chat
requests return an explicit 503; there are no synthetic completions. The
experimental Gufo C ABI adapter compiles against pinned upstream headers but is
not linked into the server or hardware-qualified. **v0.1 is not ready.**

## Build and verify

Existing development packages: C17 compiler, CMake, pkg-config, libuv, llhttp,
json-c and libcurl. Threads and libm are system dependencies. Python is used only
by the tests/source audit, never the server or monitor. Nothing is installed by
the build. Versions/provenance are in `third_party/README.md`.

```sh
cmake -S . -B build/debug -G Ninja -DCMAKE_BUILD_TYPE=Debug
cmake --build build/debug -j2
ctest --test-dir build/debug --output-on-failure

cmake -S . -B build/sanitize -G Ninja -DCMAKE_BUILD_TYPE=Debug -DLIE_SANITIZERS=ON
cmake --build build/sanitize -j2
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 \
  ctest --test-dir build/sanitize --output-on-failure
```

CPU tests cover registry identities/collisions, filters/aggregation, rotating
MAX, cumulative buckets, escaping, concurrent updates, parsing, real HTTP
framing/limits/slow clients, shutdown lifetimes and all monitor modes. No test
above proves inference, GPU batching, quality, snapshot restore or GPU memory fit.

## Run the management increment

```sh
build/debug/synapse-lie-server --port 19879 --management-port 19880
build/debug/synapse-lie-monitor check --url http://127.0.0.1:19880
# Fails with exit 3 until a real executor is available:
build/debug/synapse-lie-monitor check --url http://127.0.0.1:19880 --require-ready
build/debug/synapse-lie-monitor watch --duration 10 --interval 1
build/debug/synapse-lie-monitor record --duration 10 --output run.jsonl
# One record (not an entire multi-line JSONL stream) can be checked offline:
head -n 1 run.jsonl > sample.json
build/debug/synapse-lie-monitor check --file sample.json
```

Open `http://127.0.0.1:19880/monitor`. The small embedded page has no CDN and
explicitly shows unavailable inference statistics. SIGINT/SIGTERM drains
network handles; no service is installed. Listener hosts are independently
configurable; **keep the defaults on loopback**. No authentication or TLS is
implemented by the server, so do not expose management publicly.

## Experimental Gufo boundary

```sh
python3 tools/fetch-gufo.py  # Explicit ~5.5 MB upstream source fetch, no weights
cmake -S . -B build/adapter-check -G Ninja -DLIE_GUFO_HEADER_CHECK=ON
cmake --build build/adapter-check --target lie_gufo_header_check -j2
```

The fetch verifies the exact archive hash and retains upstream notices. It
refuses an existing destination. This target is deliberately named **header
check**: an object with unresolved Gufo symbols is not a runnable backend.
It preserves upstream Model/Session/ROCm calls; no numerical kernels are rewritten.

## Contracts and next work

- [Architecture/ownership and increment plan](docs/ARCHITECTURE.md)
- [Experimental C ABI](docs/ABI.md)
- [Actuator/Micrometer subset and metric meanings](docs/METRICS.md)
- [HTTP and monitor](docs/HTTP.md)
- [State persistence design, not implemented](docs/STATE.md)
- [Hardware/model/baseline inventory](docs/BASELINE.md)
- [DS4 coordination](docs/COORDINATION.md)
- [Resumption/progress note](docs/PROGRESS.md)
- [Source/dependency provenance](third_party/README.md)

Next gate: independent pinned Gufo build and a real original-model AR request
under the agreed .157 lease, followed by linking the adapter into a dedicated
executor worker and wiring real HTTP/SSE. Native batching, tool-aware turns,
MTP, RAM/SSD snapshots, inference histograms and CUDA remain later increments.
