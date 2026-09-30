# synapse-lie — Local Inference Engine

Primarily C17 local inference engine under development, initially targeting Qwen3.8
Flash Next on AMD Strix Halo. LIE must own its model loader, sessions, memory and
executor, selectively porting useful Gufo numerical kernels. **Not a Gufo proxy,
launcher or frontend over Gufo Model/Session**, even in-process behind a C ABI.
See the authoritative [backend ownership contract](docs/BACKEND.md).

**Current increment: working CPU management/observability runtime, not an LLM
server yet.** No model is loaded. Readiness is 503, `/v1/models` is empty and chat
requests return an explicit 503; there are no synthetic completions. The
reference-only Gufo interoperability adapter compiles against pinned headers but
is not linked into the server, hardware-qualified or the planned production
backend. The autonomous LIE backend is not implemented. **v0.1 is not ready.**

## Reactive pattern

The intended inference path is **demand-driven**, not just asynchronous I/O:

```text
subscriber demand -> device-owner scheduler -> confirmed output -> bounded stream -> SSE writer
        ^                                                                            |
        +---------------- credits / buffer release / cancellation ------------------+
```

`lie_flow` is the first implemented C component: per-sequence token credits,
preallocated bounded byte buffers, an explicit dispatch/cancel gate, FIFO output,
pinned in-flight/transport loans and out-of-band terminal signals. Linux eventfd
provides coalesced wakeups; there is no polling-for-tokens loop. A slow stream
exhausts its own capacity instead of creating an unbounded output queue.

**The component is CPU-tested but not wired into HTTP or an inference executor.**
libuv currently supplies the network Reactor, not reactive inference. No Project
Reactor/JVM dependency or Reactive Streams certification is claimed. The concrete
contract, feedback loop and remaining integration are in [REACTIVE.md](docs/REACTIVE.md).

## Build and verify

Existing development packages: Linux, C17 compiler, CMake, pkg-config, libuv, llhttp,
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
framing/limits/slow clients, shutdown lifetimes and all monitor modes. The reactive
flow suite tests credits, bounded storage, dispatch/cancel races, ordered synthetic
frames, loans, peer isolation and eventfd wakeups between real threads. No test
above proves inference, GPU batching, SSE token delivery, quality, snapshot restore
or GPU memory fit.

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

## Reference-only Gufo interoperability experiment

```sh
python3 tools/fetch-gufo.py  # Explicit ~5.5 MB upstream source fetch, no weights
cmake -S . -B build/adapter-check -G Ninja -DLIE_GUFO_HEADER_CHECK=ON
cmake --build build/adapter-check --target lie_gufo_header_check -j2
```

The fetch verifies the exact archive hash and retains upstream notices. It
refuses an existing destination. This target is deliberately named **header
check**: an object with unresolved Gufo symbols is not a runnable backend.
It delegates to upstream Model/Session and is retained as a reference experiment,
**not to be linked into production**. No numerical kernel port is implemented yet.

## Contracts and next work

- [Autonomous backend ownership and reimplementation gates](docs/BACKEND.md)
- [Architecture/ownership and increment plan](docs/ARCHITECTURE.md)
- [Reactive pattern, implemented C flow and integration obligations](docs/REACTIVE.md)
- [Reference-only experimental ABI; not the production backend](docs/ABI.md)
- [Actuator/Micrometer subset and metric meanings](docs/METRICS.md)
- [HTTP and monitor](docs/HTTP.md)
- [State persistence design, not implemented](docs/STATE.md)
- [Hardware/model/baseline inventory](docs/BASELINE.md)
- [DS4 coordination](docs/COORDINATION.md)
- [Resumption/progress note](docs/PROGRESS.md)
- [Source/dependency provenance](third_party/README.md)

Next implementation: the LIE C GGUF/model loader and tensor contracts, then
owned state/device storage and selectively ported numerical operations toward a
real AR executor. Build pristine Gufo only as an isolated reference under the
agreed .157 lease. Wire HTTP/SSE to **LIE's own executor**, not the legacy adapter.
Native batching, tool-aware turns, MTP, RAM/SSD snapshots and CUDA follow their
own correctness gates. The previous embedded-Gufo integration plan is superseded.
