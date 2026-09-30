# Resumption note — increment A / CPU control plane

Owner: synapse-lie fork. The original agent continues DS4 independently.
Repository: `/home/paperboy/workspace/projects/synapse-linux/synapse-lie` on .155.
Branch: `feature/initial-runtime`, from `develop` seed `ce3ce59`.
No multi-agent workflow is active inside this fork. No independent review claimed.

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
- Experimental C ABI + C++ Model/Session adapter: compile-check only against
  actual upstream headers, append-only prefill, greedy AR, explicit worker
  ownership, cancellation latch and poison-on-backend-failure. No runnable
  model integration or runtime verification claimed.
- ABI, persistence design, ownership, metric/HTTP contracts, provenance,
  coordination and baseline plans documented.

## Verification authority

`tools/verify.py cpu-closure-r2` writes actual per-command exit codes, source
hashes, logs and output binary hashes under `evidence/cpu-closure-r2/`. Read its
`result.json` for the outcome; do not infer a pass from a plan or build target.
It runs GCC and Clang debug builds, ASan/UBSan tests, the C17 ABI layout test,
Gufo adapter object compilation and all 1019 source-file identity checks.
Earlier Debug/sanitizer runs and full `cpu-closure-r1` passed and remain in
`evidence/`. A final portability review replaced struct-padding comparison with
semantic metric-definition comparison; r2 reruns all gates after that change.

Test suites are CPU only: registry, independent monitor parser/rates, C ABI
layout, actual loopback HTTP + monitor. They cover registration/tag collisions,
aggregation/filtering, MAX expiry, histogram count/sum/Inf, concurrent updates,
malformed/truncated scrape input, HTTP framing/bounds, slow/concurrent clients,
shutdown callbacks, offline corruption, not-ready exit and no log overwrite.
They do NOT prove GPU inference, stream-token ordering, model cancellation,
native batching, state restore or quality. promtool is absent; internal C and
independent Python subset validators ran, not the official tool.

## Immediate blocker / next executable gate

Hardware access works. Coordination, not credentials, is missing:
`/tmp/synapse-lie-ds4-coordination/synapse-lie-proposal-r1.json` is present on .157,
DS4 acknowledgement is not yet present. Confirm adoption of a shared lease and
register (or explicitly agree to the existing DS4 protocol) before any GPU run,
full hash scan or heavy I/O. No process was stopped for admission.

Then:
1. Build a private immutable upstream Gufo comparator with recorded host runtime;
   verify a real AR request on the original UD-Q4_K_XL shards before optimizing.
2. Link the adapter and implement the single device-owner worker + bounded queues,
   model-specific chat rendering, real nonstream/SSE and terminal event accounting.
3. Qualify frontiers/tokens and C1 before C2/4/8, chunks/cancel/client backpressure,
   then MTP and full state/prefix SSD. No silent native-batch claims for a loop.
4. Wire inference metrics from those events, add percentile estimates and remaining
   monitor/UI work. No fake values for unimplemented memory/cache/speculation.

## Real limitations

v0.1 is NOT ready. No loaded model, linked backend, active inference scheduler,
normal chat generation, token SSE, tool continuation, MTP, RAM prefix reuse,
SSD state writer/reader or CUDA. The state document is a design, not a parser.
GUI is an en_US development fallback; full localization/release work remains.
Registry bounds and network limits are explicit initial implementation limits;
inference memory/sequence budgets must be measured, not copied from them.
No speedup/quality/300K fit claim. Historical DS4 results retain their own scope.
