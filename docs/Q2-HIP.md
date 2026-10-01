# Q2 routed HIP candidate — initial GPU operators pass, model still blocked

This continues the [host compatibility slice](Q2-COMPATIBILITY.md). The private
candidate implements routed IQ2_XXS gate/up and padded Q2_K down dispatch.
On **2026-10-01**, the first fixed synthetic GPU suite passed **64/64 cases** on
`.157`, after fresh operator handover and all four nonblocking leases.
**Full-format/model numerical qualification, model memory fit and PP/TG remain
NOT RUN.** Model admission remains closed; the production provider is unchanged.

## Hot-path structure

- `q2_plan.h` is C17-compatible, bounded geometry/workspace planning. It accepts
  IQ2 2560/2560 and Q2 logical/physical **640/768**, retaining weight row strides
  660/252 bytes. It is not a whole-model admission or resident-memory estimate.
- `Executor::Create` identifies the Q2 profile and reserves one owner/stream's
  quantization, mapping, rank/count and grouped-vector scratch. Unsupported mixed
  layouts and MTP are refused. Other formats allocate no extra Q2 workspace.
- `q2_routed.hip` selects vector/tiled projection on the host. Inside the dot
  products, quantization type is a **template specialization**, not per-element
  string/format discovery. The existing bounds and ragged-store checks remain.
- IQ2 gate/up uses the existing paired/fused vector arithmetic, grouped for 2–8
  inputs. Wider/prefill work shares one gathered quantization between two tiled
  projections, followed by the existing SwiGLU. Q2 down has vector and tiled
  entries. Prefill keeps the existing `prefill_phase` choice, including one-row
  tails; this is not native serving batching or MTP enablement.

### Padding without an extra float copy

Inputs remain **tightly packed 640-float rows**. The quantizer reads with that
logical width/stride and directly writes a padded quantized row. Dot products
retain the weight's physical 768-column stride. The existing MMQ/vector scratch
alignment rounds that quantized row to **1024 values**; columns 640–1023 are zero.
There is no temporary 768-wide FP32 activation copy and no additional padding
kernel. `RowScratch` still advances the logical gate/up rows correctly.

The new tiled Q2/IQ2 quantizer specializations explicitly handle a zero maximum:
zero values, scales and sums, rather than computing `0 * infinity`. Nonzero
arithmetic and the original formats' default quantizer specializations are
unchanged. The initial GPU suite passes Q2 padding-byte checks, zero-row
arithmetic and output guards; this does not cover every input/production shape.

### Reserved scratch and lifetime

The new route does not use per-call `ggml_hip_pool_alloc` or the legacy ID mapper's
growing global scratch. It supplies owned rank/count storage to the same three
mapping kernels. One allocation is reserved at executor creation, with explicit
nonoverlapping 64-byte-aligned regions, caps of 2048 input tokens, 512 experts,
32 selected experts and 65536 assignment rows. The existing per-device context
is resolved at preparation, not allocated by each new projection call.

Every new dispatch uses the owner's stream. Reuse is stream-ordered; storage
outlives all enqueued work and the existing executor/ABI must drain before
retirement. This internal launch API is **asynchronous** and does not redefine
the synchronous completed-work LIE ABI. Any returned failure propagates to the
existing fail-closed worker; no route retry or fallback is added.

Tiled output is cleared for inactive negative IDs; current quantization tails
are cleared even after a larger previous batch. Both operations have costs;
no speedup is inferred from removing allocations or float padding. Weight uploads
still require the existing **4096-byte zero tail margin**. Internal routing IDs
must be valid expert indices or negative; this is not a public untrusted-ID API.

## Provenance and build isolation

`host-edits.json` still changes six pinned upstream files; this increment only
reformatted two host changes. `hip-edits.json` adds changes to **six disjoint
files**: executor header/implementation, model CMake, MMVQ dispatch, quantizer and
ID-map entry. Three first-party files are added to the generated tree:
`q2_plan.h`, `q2_routed.h`, `q2_routed.hip`. All original licenses/notices remain.

The numerical dot/tile helpers come from independently acquired Gufo
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, including its licensed llama.cpp-derived
MMQ component. No sibling DS4/CachyOS source, configuration or artifact was used.
This extends the transitional provider; it is **not an owned C17 model-forward
reimplementation**. No weight payload was read, converted or downloaded.

`q2_hip_port.py` verifies the host-recipe identity, all pristine/edited/new file
hashes, path rules and runtime refusal before materializing a new source tree.
`LIE-Q2-HIP-SOURCE.json` records all 1022 files. The original `.deps`, qualified
archives and runtime build recipe are untouched. The new HIP TU belongs to the
MMQ target, retaining its **HIP C++17 / gfx1151 / GGML_HIP_NO_VMM / numerical flags**,
not the general model target's C++20 dialect. Other provider dialects stay intact.

```sh
# Editing host only; exclusive label. GPU masked throughout.
python3 -B tools/build-q2-hip.py q2-hip-candidate-example-r1
```

This builds private archives and test executables, never a production server.
The helper runs only `--contract-only` and `--cpu-oracle`, not the GPU test mode.
Both the source receipt's `runtime_link_allowed=false` and the existing model
upload refusal remain. Removing the refusal is **not** a qualification step.

## Evidence and remaining gates

| Gate | Current result |
| --- | --- |
| C17 geometry/capacity RED | `q2-route-plan-red-r1`: successful compile, assertion exit -6 preserved |
| CPU runtime/contracts | `q2-route-cpu-r1/r2`: 17 default suites, GCC/Clang/ASan/UBSan/header checks pass; r2 closes the final inputs |
| Source contracts | Seven host-preparer tests plus eight HIP-overlay tests; no optional checkout needed for default CTest |
| First build failure | `q2-route-linked-r1`: missing C++ chrono pre-include, preserved; fixed to match the existing qualified build flags |
| Intermediate links | `q2-route-linked-r2/r3`: compile/link and masked host checks, never GPU/model execution |
| Formatting | `q2-route-format-r1`: pristine PASS, candidate refusal preserved; `r2` regenerates checked recipes from formatter output, no in-place upstream/build edit |
| Candidate builds | `q2-route-linked-r4/r5`: shared upstream formatting script PASS with installed clang-format, HIP compile/link and masked host refusal/scalar-golden checks PASS; r5 also ensures one-row operator fixtures are nonzero |
| Host binding regression | `q2-route-host-r1`: eight C++ cases on GCC/Clang/ASan/UBSan after host-only formatting changes |
| Delivery | `q2-route-delivery-r2`: final hashes/1022 files/production refusal and saved-header GCC/Clang binding checked; original qualified server unchanged. The preceding audit's binary-fixture UTF-8 diff-rendering failure is retained as r1, not a kernel failure |
| Initial GPU operators | `q2-operator-gpu-r1`: **64/64 PASS**, child/supervisor exit 0, fixed scalar tolerance unchanged |
| Real Q2 / full-format numerics / performance | **NOT RUN**, not zero throughput and not an OOM/fit result |

The shared formatting script runs directly with installed tools; no Nix download,
installation, full upstream release build or independent review is claimed.

`tests/q2_operator_probe.cpp` executed **64 GPU cases**: vector/tiled, IQ2 paired
and fused/grouped gate/up, Q2 physical down, rows 1/2/3/8/9/32/33, odd output rows
3/17, shared/different/duplicate/inactive routing, dirty scratch, exact logical
input allocations, output guards and quantized zero padding. Its independent
scalar expression uses synthetic power-of-two inputs/scales; IQ2 deliberately
covers only **grid code zero** with varied sign/scale fields. Tiled cases request
width 16; other tile widths and full production shapes remain to be covered.
CPU goldens and the GPU suite passed. The fixed absolute/relative error bound is
`0.0002 + 0.00004 * abs(reference)`, recorded before GPU execution. This remains
an initial operator check, not all-codebook or independent full-model parity.

### First GPU receipt

`evidence/q2-operator-gpu-r1/` records the one-shot window at
**07:03:42.563098–07:03:46.073077 UTC** (supervisor/preflight/cleanup scope, **not
kernel timing**). It executed the unchanged `q2-route-linked-r5` probe from source
`dc5ef288c18be0cff4b9c4a8adc81bebe327b013`, SHA-256
`9fbde249089d2be33ff4a37831895ab7a401d4832aa33c26e026ebf076831e7e`.

- IQ2: **36 cases**, largest reported absolute error **4.76837158e-7**.
- Q2: **28 cases**, largest reported absolute error **0** on these deliberately
  exactly quantizable fixtures; this is not a claim of lossless Q2 weights.
- All output canaries/Q2 quantized padding checks passed. The case calls wait
  for completed stream work before copying/comparing output, not just enqueue.
- No retries, fallback, failed cases, weight access, model load, remote build,
  dependency install, tuning, server request or DS4 modification.
- All 130 stdout lines (64 begin/pass pairs plus CPU/final markers), empty stderr,
  nine telemetry records, exact binary/helper/DSO identities, start/end register
  and actual exit codes are retained. **Full raw GPU output arrays were not
  emitted**; sources deterministically describe the fixtures. The offline audit
  passes without rerunning GPU work.
- Binary/DSOs/power settings unchanged. Owned processes absent and KFD empty at
  07:04:44 UTC; four unchanged lock identities had no holders at 07:07:03 UTC.
  Existing desktop clients and 463 denied FD observations limit exclusivity
  claims. No formal DS4 ACK or standing lease is inferred.

Only the direct operator boundary was exercised, not full `Executor`/`RowScratch`
integration. Actual 640/2560 output-row production shapes, full tiles, last-expert
boundaries, 512-expert routing, non-power-of-two activations/scales, other IQ2 grid
codes/tile widths, capacity extremes and matched UD regression remain gates.

Next: broaden codebook/shape/reload checks and matched original-UD regression,
with new coordinated admission for further GPU work. Before any Q2 model load,
finish role-aware PLE/weights/staging/workspace/context admission and an independent
format-specific reference. Then qualify full-model frontiers and measure the
separate [fresh PP/TG and HTTP lanes](ANTIREZ-BENCHMARKS.md). No cache work or
benchmark speedup is claimed by this implementation increment.
