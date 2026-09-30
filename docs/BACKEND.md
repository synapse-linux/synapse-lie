# Owned inference backend — authoritative scope correction

Synapse LIE must **implement its own inference backend**, primarily in C. It is
not an HTTP/IPC proxy, a launcher for Gufo, or a new serving frontend whose model
execution is delegated to Gufo's Model/Session/Executor/DeviceModel objects.
Linking those objects in-process behind a C ABI would still be delegation, not
the requested reimplementation. This supersedes the earlier embedded-adapter
integration plan; historical source and qualification receipts are preserved.

## Ownership boundary

```text
LIE HTTP/SSE and management
             |
LIE demand-driven scheduler / resource admission
             |
LIE C model + session + executor + state management
             |
small numerical/device C ABI
             |
selected, source-ported HIP kernels and numerical helpers -> GPU

Gufo upstream -> isolated reference tests only; never a production request hop
```

| Responsibility | Required owner / implementation |
|---|---|
| GGUF discovery, parsing, shard/tensor validation and binding | LIE C loader, reusing the original read-only weight files without conversion |
| Model topology and layer execution order | LIE C model/executor, not a call to upstream whole-model forward |
| Physical token positions, attention KV, recurrent/SSM/convolution state | LIE-owned session storage and explicit frontiers |
| Weight residency, scratch, per-session allocations and transfer staging | LIE resource/memory planner; narrow device allocation/transfer calls may use HIP |
| Prefill, decode, native batching, admission and completion | LIE executor/scheduler; real shared GPU operations, not a serial-loop batching claim |
| Tokenization, chat rendering, sampling/RNG, stop/tool transitions | LIE-owned behavior, independently implemented or selectively ported with provenance and tests; no delegation to an upstream Model object |
| MTP proposals, verification, acceptance and rollback | LIE execution/state lifecycle with selectively ported numerical operations |
| Prefix reuse, complete hybrid-state snapshot and SSD persistence | LIE-owned format, identities, capture/restore and I/O lifecycle |
| Numerical primitives, GEMM/quantization, attention, recurrent and MoE kernels | Selectively port useful upstream source behind the numerical C ABI, preserving representation/arithmetic until verified |
| HTTP/SSE, reactive credits/cancellation, Actuator and monitor | Existing/new LIE C components; never forward chat to a Gufo service |

C++/HIP is permitted where useful for numerical kernels and device-library
integration. It must not hide a complete upstream engine/session implementation
behind renamed opaque handles. The C ABI is a language and device boundary,
not evidence that backend ownership has changed.

## Reuse and provenance

Reimplementation does not mean unnecessarily rewriting verified GPU mathematics.
Port the useful Gufo numerical path into this project's own source/build, with
per-component source pin/path/hash, license/notice, local changes and an operator
contract. Keep the independently fetched pristine `.deps/gufo-f783fedb` tree
immutable as a reference. Do not import the other agent's DS4 fork/artifacts.
No numerical source port is claimed as implemented by this document.

A copied whole Model/Session/Executor renamed as LIE is not this separation.
Separate scheduling, storage, model topology and lifecycle from reusable kernels;
LIE's own executor must invoke the ported operations and own their state.
No hidden upstream service, subprocess, runtime fallback or CPU model forward.
Retain third-party notices rather than relabel imported code as first-party MIT.

## Status of the existing adapter

`adapters/gufo.cpp` delegates to upstream Model/Session. It is therefore a
**reference-only interoperability experiment**, not the LIE backend or a
production integration candidate. It has only been compile-checked, never linked
into the server or qualified with real inference. Its header-check target remains
optional and requires the reference-only build definition. Its experimental
`include/lie/executor.h` ABI is historical, not the new numerical ABI.

The existing control plane, metrics, monitor and `lie_flow` remain useful.
**No autonomous LIE model loader, session engine or GPU executor exists yet.**
Changing documentation or excluding the wrapper does not implement one.

## Next implementation slices and gates

1. **C GGUF/model loader and explicit tensor contracts.** Start with the original
   Qwen Flash Next shard set, metadata-only first shard, tensor types/shapes,
   offsets/alignment, overflow/range validation and model binding. Bounded CPU
   fixtures and malformed-input tests first. Metadata acceptance is not loading
   the full model or executing inference; heavy real-file I/O remains leased.
2. **Owned device/state storage plus one numerical slice.** Define and implement
   the narrow C device/operation boundary needed by that slice; port selected HIP
   source with provenance. Qualify shapes/types, completion, cancellation lifetime,
   representation and numerical error before building on it. No unused universal
   backend abstraction or placeholder whole-model `forward` implementation.
3. **Owned short-context AR executor.** Extend the proven operations to the full
   model graph. LIE owns per-layer state, prefill/decode and logits. Under the
   shared lease, compare physical inputs, operator/frontier outputs and generated
   tokens with an independently built pristine Gufo reference. Declare tolerances
   and matching execution settings before comparing; retain failures.
4. **Wire the LIE executor into the reactive HTTP path.** One device owner,
   bounded queues and `lie_flow` credits/retirement, real chat rendering and
   nonstream/SSE. Establish C1 end-to-end before native C2/4/8 and fairness claims.
5. **Complete continuity and optimization.** Tool continuations, RAM prefix
   reuse, full-state SSD/restart, native batching and MTP each require dedicated
   ownership/correctness gates; measure performance only on qualified paths.
   CUDA/DGX Spark follows the AMD backend, through the same LIE-owned contracts.

An independent upstream build is a comparator gate, not permission to bypass
these steps by serving requests through it. GPU/heavy-I/O work still requires
DS4 coordination; this scope correction does not change leases, weights,
operational profiles, installation or deployment permissions.
