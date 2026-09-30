# Resumption note — CPU control plane and reactive flow primitive

Owner: synapse-lie fork. The original agent continues DS4 independently.
Repository: `/home/paperboy/workspace/projects/synapse-linux/synapse-lie` on .155.
Branch: `feature/initial-runtime`, from `develop` seed `ce3ce59`.
No multi-agent workflow is active inside this fork. No independent review claimed.

## Authoritative backend scope correction

LIE must reimplement its own backend, not proxy or embed Gufo Model/Session.
See `docs/BACKEND.md`: LIE owns loading, model graph, session/state, memory and
executor; selectively port useful numerical kernels with provenance. The earlier
plan to link the Gufo adapter into serving is superseded. That adapter is retained
only as a guarded reference experiment. No autonomous LIE backend exists yet.

## Delivered scope

- Target/account/hardware/OS/toolchain/storage/service/port inventory, model
  metadata and existing receipt identities captured read-only. All five original
  Gufo file stat identities match the inherited sealed receipt; no full rehash.
- Dedicated upstream Gufo source pin and full regular-file SHA manifest. No
  DS4 source/binary/cache import, edits, deployment or dependency installation.
- C17 libuv/llhttp management runtime and separate API listener. Explicit empty
  models/unavailable chat, not fake inference. Health/info/discovery, Actuator
  metric names/details/filters, Prometheus and a small embedded diagnostics page.
- Thread-safe bounded C Counter/Gauge/Timer registry: copied ownership,
  conflict/collision refusal, cumulative histogram buckets, time-window MAX,
  coherent snapshots and finite-value/UTF-8 validation.
- C monitor check/watch/record, offline single-record fixtures, bounded 32-sample
  history, monotonic deltas and reset/layout detection. No Prometheus service.
- Historical C ABI + C++ Model/Session adapter: reference-only compile experiment
  against actual upstream headers, not the production backend/integration path.
  Its worker/cancellation/poisoning behavior has not been hardware-qualified.
  The explicit reference-only build definition prevents unmarked compilation.
- C reactive flow component (`include/lie/flow.h`, `src/flow.c`): demand credits,
  bounded preallocated buffers, dispatch gate, ordered output, loan ownership,
  out-of-band cancellation/error and eventfd work/output wakeups. Component only;
  no HTTP, scheduler or inference-executor binding. Contract in `docs/REACTIVE.md`.
- ABI, persistence design, ownership, metric/HTTP/reactive contracts, provenance,
  coordination and baseline plans documented.

## Verification authority

`tools/verify.py backend-scope-r1` writes actual per-command exit codes, source
hashes, logs and output binary hashes under `evidence/backend-scope-r1/`. Read its
`result.json` for the outcome; do not infer a pass from a plan or build target.
It runs GCC and Clang debug builds, ASan/UBSan tests, the C17 ABI layout test,
reference-only Gufo object compilation and all 1019 source-file identity checks.
Earlier full `cpu-closure-r1`, `cpu-closure-r2` and `reactive-closure-r1` passed and
remain in `evidence/`. r2 includes the portable metric-definition comparison;
the reactive run adds `test-flow`. The new scope run checks the reference-only
compile guard's admitted target. None proves an autonomous backend or GPU run.
The forbidden unmarked compilation is separately checked in
`evidence/backend-reference-refusal-r1/` with its actual compiler exit/diagnostic.

Five test suites are CPU only: reactive flow, registry, independent monitor
parser/rates, C ABI layout, actual loopback HTTP + monitor. Reactive tests cover
credits/refunds/saturation, allocation/ordinal bounds, FIFO, stale/foreign tickets,
full-buffer cancellation, dispatch races, retained loans, terminal ordering,
peer isolation and FD cleanup, including 4,000 synthetic frames across threads.
No synthetic frame is presented as model output. The other suites cover
registration/tag collisions, aggregation/filtering, MAX expiry, histogram
count/sum/Inf, concurrent updates,
malformed/truncated scrape input, HTTP framing/bounds, slow/concurrent clients,
shutdown callbacks, offline corruption, not-ready exit and no log overwrite.
They do NOT prove GPU inference, real SSE token ordering, model cancellation,
native batching, state restore or quality. promtool is absent; internal C and
independent Python subset validators ran, not the official tool.

## Next implementation / separate hardware gate

The next implementation is the LIE C GGUF/model loader and tensor contracts,
with bounded CPU fixtures, not linking the reference adapter. This work does
not require GPU access. Follow the slices in `docs/BACKEND.md`.

For the numerical port/reference runs, hardware access works. Coordination, not credentials, is missing:
`/tmp/synapse-lie-ds4-coordination/synapse-lie-proposal-r1.json` is present on .157,
DS4 acknowledgement was absent at the recorded 2026-09-30T12:23:32Z check.
The local reactive increment does not re-check or assume live GPU availability.
Confirm adoption of a shared lease and register (or explicitly agree to the
existing DS4 protocol) before any GPU run, full hash scan or heavy I/O. No process was stopped for admission.

Under the agreed lease:
1. Build a private immutable upstream Gufo comparator with recorded host runtime;
   verify a real AR request on the original UD-Q4_K_XL shards. Reference only.
2. Implement LIE's owned device/state storage and source-ported numerical slices;
   qualify operators, then its short-context C AR executor against the reference.
   Do not obtain a quick working server by embedding Gufo Model/Session instead.
3. Wire that executor into the device-owner worker, bounded queues and `lie_flow`
   eventfds/credits/cancellation, then real rendering, nonstream/SSE and metrics.
4. Qualify C1 before native C2/4/8, tool continuation, complete RAM/SSD state and
   MTP, with separate gates. No fake memory metrics or serial-loop batching claim.

## Real limitations

v0.1 is NOT ready. No autonomous model loader/backend, loaded model or active inference scheduler,
normal chat generation, token SSE, tool continuation, MTP, RAM prefix reuse,
SSD state writer/reader or CUDA. The state document is a design, not a parser.
GUI is an en_US development fallback; full localization/release work remains.
Registry bounds and network limits are explicit initial implementation limits;
inference memory/sequence budgets must be measured, not copied from them.
No speedup/quality/300K fit claim. Historical DS4 results retain their own scope.
