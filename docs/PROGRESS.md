# Resumption — original-weight serving smoke and C1 baseline, numerical gate open

Owner: synapse-lie fork; DS4 remains the other agent's project.
Repository: `/home/paperboy/workspace/projects/synapse-linux/synapse-lie` on `.155`.
Branch: `feature/initial-runtime`, from `develop` seed `ce3ce59`.
The runtime increment starts at `79625ce`; the resumed smoke/runner fix starts
at `b7de609`. No workflow or independent review is claimed.

## Latest target result — C1 baseline, 2026-09-30 20:52 UTC

The user's explicit prefill/decode request produced a new C17 direct-executor
harness and leased supervisor, without changing the adapter or numerical sources.
`t0-c1-perf-r2` completed one warmup and three measured fresh-session runs for each
actual prompt size 502/2042/8191, all TG128, common context9216/chunk2048. Median
PP: **988.68 / 1642.65 / 1607.13 tok/s**. Median TG: **26.851 / 26.049 / 25.965 tok/s**.
Full finite PP/TG frontier logits and outputs matched warmup exactly. All nine
measured samples are retained; no profile/tuning/HTTP or outlier removal.

Child/helper exit 0, original stats and artifact hashes unchanged, no foreign GPU
client observed, KFD empty after retirement. Existing governor `powersave`, EPP
`balance_performance`, GPU DPM `auto` were retained. This is a C1 embedded-provider
baseline, not independent numerical qualification or a reactive speedup. Exact
scope, ranges and all conditions: [C1-BASELINE.md](C1-BASELINE.md).

`t0-c1-perf-r1` had failed before model launch on an absent optional sysfs power
attribute, not a GPU/model error. Its failure and the focused CPU RED/GREEN are
preserved; unavailable telemetry is now explicit null/error. No workload or
admission control was weakened. Code commits `cbb06fc` (harness) and `7f85ef8`
(supervisor fix); ten CPU suites pass, including eleven benchmark contract cases,
with GCC/Clang/ASan/UBSan (`t0-perf-cpu-r3`). HIP/no-model receipt:
`t0-perf-linked-r1`; final documentation/source CPU closure: `t0-perf-closure-r1`.

## Previous target result — serving smoke, 2026-09-30 20:07 UTC

A fresh operator handover (machines free, resume LIE) and read-only observation
preceded successful acquisition of all four existing leases. `t0-model-smoke-r3`
passed target binary/DSO preflight but hit a Python runner name collision directly
after server launch; no inference was observed, helper exit 1/child exit -15.
That failure is retained. `http_client` now avoids the collision, with four
CPU-only HTTP regression cases added as the ninth CTest suite. Focused RED/GREEN
and GCC/Clang/ASan/UBSan/header checks passed (`t0-smoke-runner-fix-r1`).

`t0-model-smoke-r4` then passed **all six original-weight requests**: READY, 4 and
`caffè 🙂`, each nonstream and SSE with identical content/usage/stop, one DONE,
clean retirement and server/helper exit 0. Totals: six completed requests, ten
emitted tokens, zero failed/cancelled. No foreign GPU clients were observed;
KFD was empty after shutdown, and binary/model identities were unchanged.
Executed build remains `t0-linked-r4`; no C/C++ runtime source changed.
See [T0-SMOKE.md](T0-SMOKE.md) and its exact receipts. No pristine numerical,
broad quality, concurrency, cancellation-in-flight or performance qualification follows.

## Previous target admissions — 2026-09-30 18:53 UTC

Following the operator's explicit go-ahead after the idle-node inspection,
`tools/smoke-model.py` and the unchanged `t0-linked-r4` binary were staged under
private LIE run directories on `.157`. Two attempts at 18:49 and 18:51 refused
admission on a busy DS4 download lock, exit 1, **before any LIE model open**.
No target model/DSO smoke or inference was performed. At 18:53 a DS4 `native-perf`
warm-up was using the GPU at 98%, with download/qualification/shared locks held.
Do not enter between its benchmark phases. No background retry is scheduled.

See [T0-SMOKE.md](T0-SMOKE.md) for the exact operator-window scope, predeclared
requests, observations and preserved `t0-model-smoke-r1/r2` receipts. Staging a
private test binary is not a service installation or a working-model result.

## Policy and actual status

The user permits embedded Gufo for T0, followed by requirement-driven T1/T2
refactoring toward an autonomous C backend. The older reference-only prohibition
is superseded, not the autonomy goal. See BACKEND.md and INFERENCE-REACTIVE.md.

**The HIP-linked executable has now performed bounded original-weight GPU
inference through C HTTP/SSE, worker, flow and provider binding.** The first real
serving smoke passed, while the complete T0 acceptance gate (including pristine
numerical comparison and real cancellation/backpressure) remains open. Separate
synthetic tests are still distinct from this actual-model evidence.

## Implemented in this increment

- `src/worker.c`: one pthread device owner, eight bounded admissions, one active
  sequence by default or two explicitly configured interleaved single-row
  sequences. Round-based chunk/step scheduling; never native batching by claim.
- Independent worker and consumer references keep jobs alive after disconnect.
  Short metadata gates protect publication and cancellation-latch versus
  sequence detachment. No GPU wait is held under these gates or on the HTTP loop.
- Eight token slots per job, 256 bytes each. Decode reserves/begins before work;
  SSE releases/replenishes credits only after uv_write completion. Nonstream
  reserves a bounded aggregate sink. Active admission is not a measured RAM fit.
- Text request validation and copied ownership; pinned Qwen renderer, thinking
  disabled, context admission before session creation/forward, greedy AR only.
  Streaming UTF-8 replacement decoding is independent of token boundaries.
- Real nonstream JSON and SSE formatting, usage/finish/error terminals, queue
  refusal, disconnect, request deadline and shutdown lifetime handling.
- ABI 2 adds chat preparation and provider metadata/selection. Gufo types remain
  inside the adapter. The neutral worker opens the selected composition binding;
  `lie_gufo_open` remains explicitly Gufo, not renamed into an ownership claim.
- For loaded-runtime backend failure, adapter drains device work before returning
  failure/allowing retirement. Undrainable device failure exits 70 without retry
  or core dump. This exceptional hardware path is compile/link checked, not GPU
  fault-tested. Successful calls have no added device-wide barrier.
- Diagnostics disclose engine, source pin, build label, delegated/synthetic/none
  ownership and unsupported capabilities. `--build-info` opens no model.
  Hardware qualification is false. Worker counters are not remote-delivery ACKs.
- Opt-in `LIE_GUFO_RUNTIME`; real libraries from independently fetched upstream.
  A LIE-owned Qwen-only CMake scope uses the upstream model target and unchanged
  source. It is not the full upstream release build. No numerical port exists.

No tools, native batching, MTP, vision, prefix reuse, RAM/SSD restore or CUDA is
exposed. Unknown memory/latency/throughput/cache metrics remain null. Default
no-model startup still has readiness 503, empty models and chat 503. The synthetic
provider is only in test executables and reports `NOT-INFERENCE`.

## Preserved build/verification evidence

All paths below are local `evidence/` directories; labels are occupied. Receipts
record actual process exit codes, logs and source/binary identities.

| Label | Observed result / scope |
|---|---|
| `gufo-host-r1` | Full upstream configure failed, exit 1: missing rocWMMA header. No install or fake header. |
| `gufo-qwen-host-r1` | Qwen subset archives built, no execution. |
| `t0-runtime-r1` | Eight CPU/synthetic suites passed with GCC, Clang, ASan/UBSan; Gufo header object passed. Before final cancellation/error refinements. |
| `t0-linked-r1` | Link failed, exit 1: omitted upstream sample/argmax translation unit and curl link dependency. Failure preserved. |
| `gufo-qwen-host-r2` | New private subset build includes real upstream sampling unit and curl dependency; original source unchanged. |
| `t0-linked-r2` | Real HIP adapter linked; eight CPU/synthetic suites and no-model smoke passed. No weight/model/GPU execution. Before final refinements. |

`t0-runtime-r2` passed all eight suites in GCC/Clang/ASan/UBSan at
18:11:53–18:12:10 UTC, including the final binding/error/lifetime refinements.
`t0-linked-r3` passed real linking, `--build-info`, no-model and synthetic tests at
18:12:19–18:12:26 UTC, with no model access/GPU execution. Its binary SHA256 is
`b7b42150d070bf91915d2859ce66b71fed2d386f4a7f12682d5e1736309fd1d6`.

The runtime closure labels are **`t0-runtime-r3`** and **`t0-linked-r4`**.
The resumed runner/documentation closure is **`t0-smoke-closure-r1`** (CPU only).
Their `result.json` and delivery receipts, not a label or build target, establish
success and exact source identity. Label-owned build directories preserve earlier artifacts. Local link verification
masks GPU visibility, isolates HOME/cache/temp, records ELF dependencies and
never supplies `--model` to the real server.

Ten current suites: `chat-parser-wire`, `worker-synthetic`, `reactive-flow`,
`metrics`, `monitor-parser`, `executor-c-layout`, `http-monitor`, `http-synthetic`,
`model-smoke-helper`, `executor-bench-contract`. The last two use synthetic
HTTP/executor fixtures only, never GPU/model execution.
The synthetic suites exercise in-flight cancellation with a barrier, owner-thread
checks, context refusal, queue saturation, a stalled peer, real TCP backpressure,
UTF-8 split/invalid bytes, JSON/SSE equivalence, deadline, poison, error terminal,
FD cleanup and shutdown. They are not GPU/numerical/quality evidence. ASan/UBSan
covers first-party CPU paths and the fixture, not the GPU kernels.
No TSan, independent review or promtool pass is claimed.

Earlier `cpu-closure-r1/r2`, `reactive-closure-r1`, `backend-scope-r1`,
`backend-evolution-r1`, guard refusals and their delivery receipts remain historical
and unchanged. The old policy/guard result is not reinterpreted retrospectively.

## Coordination: resumed window

The 20:01 UTC observation (`t0-node-activity-r2`) followed the operator's fresh
handover. No DS4 ACK was present; none was written for its owner. Both r3 and r4
held pipeline/download/qualification/shared leases, with actual start/end records.
The successful serving r4 exited at 20:07:42 UTC and released its leases.
A later explicit measurement request admitted `t0-c1-perf-r2`, with its own
start/end records and clean exit at 20:52:07 UTC. No foreign process, DS4
source/build/cache/service/profile, model or qualified artifact was modified.
No deployment or background retry is left running.

This operator window is not permanent shared-runner adoption. Further GPU work
requires a current handover/lease, fresh preflight and register entries; idle
hardware or SSH alone is not authorization. See COORDINATION.md.

## Next work under a fresh admitted run

1. Fresh identity/memory/storage preflight; stat the original five read-only files
   against inventory, without assuming old values are live or rehashing weights.
2. Build a private independently pinned pristine comparator; retain compiler,
   flags, source, binary and target DSO identities. Prefer local serial compilation;
   remote GPU compilation needs separate coordination. Full upstream configure's
   missing rocWMMA dependency remains a blocker, not permission to install it.
   Local workspace visibility on `.157` must not be assumed.
3. Original-weight C1 short-context AR: validate physical prompt IDs, completed
   frontiers and output against the reference, then nonstream/SSE equivalence,
   UTF-8, cancellation, backpressure and quiescent retirement. Define settings
   and oracle before execution. No rollout.
4. Only with a correct baseline, collect separate pure-inference traces and test
   a falsifiable internal-reactive change. Completed PP/TG, concurrency and serving
   improvements remain separate; no benefit has been measured yet.
5. T1/T2 refactoring, native C2/4/8, tool continuity, complete RAM/SSD state and
   MTP remain separate gates; CUDA follows qualified AMD work.

Do not reintroduce the historical assistant-imposed 32 GiB reserve as a user
requirement, call the DS4 300K stop an OOM, or import DS4's benchmarks/quality into
LIE. The monitor/UI is still development en_US; v0.1 is not release-ready.
