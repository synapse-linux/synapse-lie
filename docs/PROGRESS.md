# Resumption note — CPU control plane and reactive flow primitive

Owner: synapse-lie fork. The original agent continues DS4 independently.
Repository: `/home/paperboy/workspace/projects/synapse-linux/synapse-lie` on .155.
Branch: `feature/initial-runtime`, from `develop` seed `ce3ce59`.
No multi-agent workflow is active inside this fork. No independent review claimed.

## Authoritative backend evolution policy

The user permits an initial in-process Gufo adapter, followed by refactoring
against the other requirements and new developments. `docs/BACKEND.md` defines
T0 bootstrap, T1 responsibility-by-responsibility replacement and T2 owned-backend
exit criteria. This supersedes the earlier blanket exclusion, not the autonomy
goal. Disclose delegated versus owned behavior; do not let the prototype narrow
the requirements. Neither linked inference nor an autonomous backend exists yet.

Also investigate reactive execution inside pure inference, not only HTTP or
concurrency. `docs/INFERENCE-REACTIVE.md` separates hypotheses about critical-path
waits, dispatch, overlap and buffer liveness from measured results. No such GPU
experiment or speedup has occurred; C1 PP/TG and serving/concurrency are distinct.

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
- Experimental C ABI + C++ Model/Session adapter: compile-check against actual
  upstream headers, now eligible for explicit transitional integration. It is
  not linked or hardware-qualified; worker/cancellation/poisoning behavior remains
  unverified on a real model. An explicit opt-in definition guards compilation.
- C reactive flow component (`include/lie/flow.h`, `src/flow.c`): demand credits,
  bounded preallocated buffers, dispatch gate, ordered output, loan ownership,
  out-of-band cancellation/error and eventfd work/output wakeups. Component only;
  no HTTP, scheduler or inference-executor binding. Contract in `docs/REACTIVE.md`.
- ABI, persistence design, ownership, metric/HTTP/reactive contracts, provenance,
  coordination and baseline plans documented.

## Verification authority

`tools/verify.py backend-evolution-r1` writes actual per-command exit codes, source
hashes, logs and output binary hashes under `evidence/backend-evolution-r1/`. Read its
`result.json` for the outcome; do not infer a pass from a plan or build target.
It runs GCC and Clang debug builds, ASan/UBSan tests, the C17 ABI layout test,
opt-in Gufo object compilation and all 1019 source-file identity checks. Earlier
`cpu-closure-r1`, `cpu-closure-r2`, `reactive-closure-r1` and `backend-scope-r1`
passed and remain historical evidence. The old reference-only refusal is retained
in `backend-reference-refusal-r1`; it records the policy/guard of that revision.
The new unmarked-compilation refusal is recorded in `adapter-opt-in-refusal-r1`.
Neither guard/compile check nor the CPU suites establish working inference,
pure-inference reactive speed, or an owned backend.

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

Next: the T0 vertical slice, not a mandatory big-bang backend rewrite. Prepare
one device-owner worker, bounded queues, the adapter binding and real renderer/
HTTP path; retain truthful unavailable status until the model actually works.
CPU fixtures remain synthetic. Subsequent refactoring and pure-inference tests
follow `docs/BACKEND.md` and `docs/INFERENCE-REACTIVE.md`.

For real model/reference runs, hardware access was verified; coordination was
outstanding at the last recorded check:
`/tmp/synapse-lie-ds4-coordination/synapse-lie-proposal-r1.json` is present on .157,
DS4 acknowledgement was absent at the recorded 2026-09-30T12:23:32Z check.
These local changes do not re-check or assume live GPU availability.
Confirm adoption of a shared lease and register (or explicitly agree to the
existing DS4 protocol) before any GPU run, full hash scan or heavy I/O. No process was stopped for admission.

Under the agreed lease:
1. Build a private immutable upstream Gufo comparator with recorded host runtime;
   verify a real AR request on the original UD-Q4_K_XL shards. Reference only.
2. Link/qualify the explicitly transitional adapter through LIE's worker/contracts,
   then real nonstream/SSE, cancellation/backpressure and event-based metrics.
3. Trace the pure-inference critical path separately from benchmark timing; test
   one reactive hypothesis at a time against matched completed work and numerics.
4. Refactor toward owned execution according to requirements and evidence; qualify
   C1 before C2/4/8, tool continuation, complete state and MTP. Do not transfer
   results between transitional/owned paths or call serial loops native batching.

## Real limitations

v0.1 is NOT ready. No autonomous model loader/backend, loaded model or active inference scheduler,
normal chat generation, token SSE, tool continuation, MTP, RAM prefix reuse,
SSD state writer/reader or CUDA. The state document is a design, not a parser.
GUI is an en_US development fallback; full localization/release work remains.
Registry bounds and network limits are explicit initial implementation limits;
inference memory/sequence budgets must be measured, not copied from them.
No speedup/quality/300K fit claim. Historical DS4 results retain their own scope.
