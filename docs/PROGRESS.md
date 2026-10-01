# Resumption — original-weight serving smoke and C1 baseline, numerical gate open

Owner: synapse-lie fork; DS4 remains the other agent's project.
Repository: `/home/paperboy/workspace/projects/synapse-linux/synapse-lie` on `.155`.
Branch: `feature/initial-runtime`, from `develop` seed `ce3ce59`.
The runtime increment starts at `79625ce`; the resumed smoke/runner fix starts
at `b7de609`. No workflow or independent review is claimed.

## Q2 preflight change closed — local build/tests only

The private `Executor::Create` now validates the entire Q2 descriptor profile
before construction or HIP calls. All gate/up/down expert counts and nonempty
storage must match, alongside geometry, layer count and workspace capacity;
up-only mixed formats are also detected. The C17 planner has 720 single-field
rejection fixtures. No kernel arithmetic, `RowScratch`, upload refusal or
production provider change is included.

`q2-admission-linked-r1`: serial masked HIP build/link and host checks pass.
`q2-admission-close-r1`: all 17 CTest suites pass under GCC, Clang and ASan/UBSan;
source identity uses base commit `82df5dd` plus `source.patch`. Earlier RED logs
remain in `q2-admission-dev-r1`. Closure is deliberately limited to the existing
change: no additional memory subsystem or qualification campaign was started.

Q2 model loading and PP/TG are still **NOT RUN**; executor/model integration and
necessary memory admission remain unfinished. The previous 24+64 GPU results
belong to their recorded binaries, not this newly compiled candidate. No remote
work, GPU run, model access, DS4 change or publication occurred in this closure.
Details: [Q2-HIP.md](Q2-HIP.md#latest-source-closure--executor-profile-preflight).

## Q2 extended operators — two fixes, 24 + 64 controls pass

The renewed GPU window exposed two genuine arithmetic losses: IQ2 vector
integer division discarded fractional eighths; Q2 MMA rounded scale/minimum
products back to half. Both RED failures and raw outputs are retained. The
private, hash-guarded fixes preserve the original tolerance, bounds, workspace
allocation and production refusal.

`q2-operator-extended-green-r3` passes **24/24** (15 IQ2, 9 Q2), including all IQ2
grid entries, varied weight half mantissas, 640/2560 output widths, last expert
511, requested tile widths 16–80, capacity extremes and workspace reuse.
The offline audit checks **1,725,239 raw outputs**, zero mismatches, maximum
absolute error **3.0517578125e-5**. `q2-operator-legacy-green-r1` additionally
passes the **64 original grid-zero controls** on the corrected candidate.
These are operator fixtures, not original-UD model regression or model inference.

A stale source-receipt SHA field in three cloned manifests is explicitly retained
and documented, with additive verified build/source bindings; the audit is not
an unqualified manifest-consistency PASS. See [Q2-EXTENDED.md](Q2-EXTENDED.md).
At 08:14:28 UTC the four GPU attempts' process identities were retired, KFD empty
and all four unchanged leases free. No model payload, benchmark, deployment,
remote build, tuning or DS4 change occurred. Executor integration, arbitrary
activations, memory admission and independent full-model numerics still block
Q2 model loading; antirez and updated-server PP/TG remain NOT RUN.

## Earlier Q2 initial GPU operators — 64/64 pass, model admission still closed

After the fresh `hai la finestra libera` handover, `.157` passed the fixed
`q2-operator-gpu-r1` synthetic suite at **2026-10-01 07:03:42–07:03:46 UTC**
(supervisor scope, not timing/throughput). All four existing leases were held
nonblockingly. The unchanged r5 probe from `dc5ef28` completed 36 IQ2 and 28 Q2
cases with maximum reported absolute errors 4.76837158e-7 and 0 respectively,
within the predeclared tolerance. Padding/output guards pass; no retries.

Raw case records, empty stderr, nine telemetry samples and start/end registration
are retained and pass offline audit. Child/supervisor exit 0, binary/DSOs/power
settings unchanged; owned PIDs absent/KFD empty at 07:04:44, known leases free at
07:07:03 UTC. Desktop clients/denied FD observations remain visibility limits,
not proof of universal exclusivity. No model access, remote build, deployment,
install, tuning or DS4 changes. Full GPU output arrays were not emitted.

**Scope is limited:** grid-zero IQ2, synthetic power-of-two scales/activations,
small ragged output shapes and tiled width 16. Full codebook/shape qualification,
Executor/RowScratch integration, matched UD regression, role-aware memory
admission and independent full-model parity remain. Model upload/runtime gates
stay closed; antirez and new-server PP/TG remain not run. See [Q2-HIP.md](Q2-HIP.md).

## Earlier Q2 HIP implementation — compiled, before the GPU run

The private candidate now routes IQ2_XXS gate/up (vector, paired/grouped and
prefill tiled) and Q2_K down (vector/tiled). Logical 640-float rows are read with
stride 640 directly into zero-padded quantized storage, while weight stride
remains physical 768. No additional FP32 padded copy/kernel is introduced.
C17 planning reserves one executor-owned workspace for quantization, ID maps,
rank/count and grouped-vector scratch; the new projections do not grow a pool
or global ID-map allocation during forward. Shape/format choices stay on the
host, with specialized dot-product kernels and necessary GPU tail guards.

`q2-route-linked-r5` passes HIP compile/link, the shared upstream formatting
script and masked host refusal/scalar-golden checks. The MMQ TU retains the
upstream C++17/gfx1151/NO_VMM flags. The host recipe received formatting-only
changes; eight host cases still pass all compiler/sanitizer variants.
Seventeen default CPU suites pass in `q2-route-cpu-r2`. Delivery audit r2 checks
all final hashes, production refusal and saved-header GCC/Clang binding again.
Its earlier diff-rendering error on an unchanged binary fixture is retained.
All original sources/builds remain intact.

At this implementation receipt, GPU work was still **not run**. The later
64-case run above advances only the initial operator gate; its scalar expression
covers Q2 affine blocks and IQ2 grid-zero sign/scale cases, not the full codebook.
Runtime admission remains disabled pending broader format/shape checks,
full-model memory admission/reference qualification and PP/TG. See
[Q2-HIP.md](Q2-HIP.md). No reactive speedup or cache capability is claimed.

## Q2 compatibility started — private host path passes, GPU path remains closed

The requested Q2-first implementation now has a private, hash-guarded
transitional provider variant: IQ2_XXS/Q2_K storage and binding, F16 HC inject,
physical 768/logical 640 down-input separation, and MXFP4 descriptor recognition
for the unused stored predictor. No `.deps`, model or qualified build was changed.
This extends delegated Gufo; it is not an autonomous LIE C17 model executor.

A full actual-header-derived binder test uncovered another concrete blocker:
missing `rope.dimension_sections`. The failure is preserved. A narrowly identified
text-AR Q2 rule uses canonical [11,11,10,0] sections from the independently fetched
official pinned Qwen config, without replacing malformed explicit metadata or
editing weights. Source/configuration licenses and identities remain separate.

The same actual **11025350 header bytes / 1256 descriptors** now bind all **48 AR
layers** through `ModelWeights::Bind` with GCC and Clang. Declared payload regions
are PROT_NONE in an anonymous virtual view: no weight values or model forward.
Eight synthetic host contract cases also pass GCC/Clang/ASan/UBSan; the source
materializer has seven contract tests. The original source remains pristine.

**This is not yet GPU Q2 compatibility, full-model loading, numerical
qualification or a benchmark.** Runtime linkage is expressly forbidden for this
host variant and device upload has a pre-allocation Q2 refusal. The subsequent
HIP candidate above implements the routing/padding; GPU qualification,
role-aware memory admission and numerical/model/performance gates remain. See
[Q2-COMPATIBILITY.md](Q2-COMPATIBILITY.md). Cache work stays behind this path.

## Antirez prefill/decode benchmark — format admission work

The operator explicitly requires **full prefill and decode benchmarks for the
antirez model**, not substituted UD-Q4_K_XL numbers. Both protected Q2/Q4 files
were inspected read-only at 2026-10-01 03:35/03:42 UTC, bounded to 24 MiB of
metadata/descriptors per file. All inherited stat identities match; no tensor
payload, model load, GPU execution, weight hash/conversion or DS4 modification.

Concrete layout: Q2 has 96 IQ2_XXS AR gate/up tensors and 48 Q2_K down tensors
with physical input 768 versus logical 640. Q4 has Q4_K gate/up and MXFP4 down,
not uniform Q4_0. Both carry one predictor layer and a 102400491520-byte BF16
PLE table; file size is not a measured all-resident GPU budget. MXFP4 geometry was
identified from independently fetched official upstream source, not a sibling
project import. Initial unknown-type observations are preserved.

The pristine pinned Gufo reader rejects MXFP4 in a CPU in-memory fixture probe;
it occurs in both actual files. Binder restrictions (including F16 HC inject),
padded geometry and routed PP/TG dispatch need additional implementation and
qualification. **Antirez LIE PP/TG remains NOT RUN / blocked**, not zero and not
inherited from a DS4 run. No GPU attempt was made against a known parser blocker.
The [per-format benchmark gate](ANTIREZ-BENCHMARKS.md) specifies full fresh PP
512/2048/8192 targets and TG128, C1 direct-ABI and separate HTTP/server lanes,
matched references, numerical/admission gates and all-sample retention.

The formerly untested `tools/gguf-layout.py` draft now has fifteen synthetic
storage/parser tests and a registered CTest suite. RED reproduced invalid bool/
alignment acceptance and FIFO blocking; the corrected reader is bounded,
regular-file-only, identity checked and explicit about incomplete unknown-type
geometry. `antirez-layout-green-r1/r2`: fourteen suites pass GCC/Clang/ASan/UBSan
and Gufo header checks. These are not inference. Native provider/server numerics
and the C17 executor benchmark were not changed by this discovery increment.
RAM prefix reuse and optional/default-off SSD persistence remain unimplemented.

## Latest GPU result — original-weight lifecycle passed

`t0-model-lifecycle-r1`, **23:01:13–23:01:44 UTC**, used source `efcb7fb` and the
HIP-linked `t0-lifecycle-linked-r1` server. All four actual leases, DSO/model/
binary preflight, start/end registration and owned shutdown passed. It is
`MODEL_HTTP_LIFECYCLE_PASS_NOT_NUMERICAL_QUALIFICATION`.

Six JSON/SSE cases preserve READY/4/caffè 🙂, usage and EOS, with valid per-request
PP/TG timings and one timing finish per SSE. Additional cases observed first
cancellation in prefill/decode dispatch, clean retirement, an unread TCP client
stalled at 65 generated tokens for at least 0.511 s, an unaffected arithmetic peer
and matching post-cancellation recovery. Final: **9 completed, 3 cancelled,
0 failed, 79 generated**, no queued/active/blocked jobs; 12 prefill and 89 decode
calls all returned. Server/helper exit 0; binary and five model stat identities
unchanged; no full weight hash. No foreign client observed, KFD empty after exit.
At 23:05:36 UTC, owned processes were absent and all known leases had no holders.

All 228 lifecycle events, raw responses and 29 telemetry samples are retained;
offline audit exit 0. This is a scoped real-model server result, **not** kernel
preemption, native batching, independent numerical equivalence, capacity testing
or a fresh performance baseline. Neither RAM prefix reuse nor SSD is implemented.
Details/identities: [T0-LIFECYCLE.md](T0-LIFECYCLE.md). No deployment or retry left.

## Source increment — executor guards and lifecycle protocol

A fresh read-only target check at **22:09 UTC** observed an active DS4 Q4 benchmark
campaign, KFD activity and all four leases occupied, including the enclosing
pipeline lease. No formal ACK was present. Receipt: `t0-lifecycle-activity-r1`.
No LIE GPU attempt, staging, lock acquisition, heavyweight I/O or foreign process
intervention followed; no background wait/retry. This is a dated observation,
not permission to enter gaps in that campaign.

The C worker now validates returned positions, token/count/stop ranges and text
sizes before publication. Unexpected provider errors or malformed successful
returns fail the runtime and its peers without retry, rather than allowing
uncertain state to remain ready. Controlled CPU fixtures expose the old invalid-
position bug (RED runtime exit -6, `t0-worker-frontier-red-r1`), then test thirteen
fault modes and prefill/decode cancellation with consumer release before return.
Dispatch counters/phase and output-credit stalls are now visible via management;
these are owner intervals, not proof of GPU-kernel preemption.

`tools/serving_checks.py` is intermediate Python qualification tooling, not the
planned C17 benchmark. The explicit `http-lifecycle-v1` suite in the existing
lease-gated supervisor validates JSON/SSE timings, disconnects during observed
prefill/decode dispatch, sustained TCP backpressure, matching fresh/interleaved
peer responses and clean recovery/accounting. Missed windows are INCONCLUSIVE;
all observations and failures are retained. Hash/settings gates precede model
launch. CPU synthetic coverage passes; the subsequent real-model result is
recorded separately above. Protocol and exact boundaries: [T0-LIFECYCLE.md](T0-LIFECYCLE.md).

The default-off optional SSD requirement is retained in commit `7f6a32`, with
RAM reuse independent of persistence. Neither prefix reuse nor SSD is implemented
by this server-hardening increment. Antirez Q2/Q4 and the independent pristine
numerical comparator remain open. The GGUF inspector was an untested draft at
this lifecycle source commit; its later validation is recorded above.

Initial local receipts: `t0-worker-frontier-green-r1` (twelve suites) and
`t0-lifecycle-helper-r1` (initial thirteen suites), GCC/Clang/ASan/UBSan/header only.
Final CPU closures `t0-lifecycle-closure-r1/r2` pass all thirteen suites;
`t0-lifecycle-linked-r1` links HIP and passes masked/no-model/synthetic checks.
Server SHA256: `f71dbe74f95415bbfe1880a2de1804b73adc3ea24eaab371a6308eaaf8b5db0a`.
The second CPU closure additionally covers exact-verified-byte helper loading.
All of these remain separate from GPU qualification.

At **22:42 UTC**, the operator supplied a new GPU window (`hai a disposizione
gpu`). A fresh read-only probe `t0-lifecycle-activity-r2` observed empty KFD,
GPU busy 0%, no inference/model handles and no holders of the four known leases.
No formal ACK was present. This permits preparing a one-shot attempt, not bypassing
nonblocking lease acquisition/admission or claiming global exclusivity.

## Previous source increment — request timing, no new GPU run

User direction: definitive `synapse-lie-bench` in C17; Python may serve intermediate
development/graphs while server functionality takes priority. Pinned Gufo method
review: `fd1710b5fd090880722e0681a868df2006595c73`, separate from the unchanged
provider pin. [BENCHMARKING.md](BENCHMARKING.md) records exact experiment semantics
and current gaps. No upstream benchmark script was run; the complete named tool
is not implemented. Antirez Q2/Q4 discovery remains unqualified and separate;
the previously written `tools/gguf-layout.py` is still an untested draft.

C worker snapshots and JSON/SSE now expose versioned per-request PP/TG executor-
call timing. Physical input deltas are counted once; EOS detection consumes time
but not an output token. Queue, other-session and credit stalls are not phase
compute time. Invalid clocks latch null duration/rates without retrying inference.
Timing/accounting precedes terminal publication; failure/cancellation cannot
produce a successful timing record. No numerical/adapter/executor ABI changes,
new GPU barriers, prefix reuse, MTP, native batching or aggregate latency metrics.

The HTTP regression failed against the prior qualified CPU fixture binary with
`KeyError: 'lie_timings'` (`t0-request-timings-red-r1`, exit 1). Initial eleven-suite
GCC/Clang/ASan/UBSan/header verification passed (`t0-request-timings-green-r1`).
Final eleven-suite GCC/Clang/ASan/UBSan/header closure passed, additionally checking
partial prefill failure and zero-output rates (`t0-request-timings-closure-r1`).
The new private `t0-request-timings-linked-r1` also passed HIP adapter linking,
build-info, no-model and all synthetic tests, with GPU visibility masked.
Server SHA256: `cf6da02e33b6f8c840bbd5693daf9ec74d8cbb2b287e9cead4f9857f194a16f5`.
Test-only link-time clock wrapping
covers completed counts, queue/credit exclusion, in-flight cancellation, EOS,
clock failure/regression/overflow and zero-resolution division. No model access
or GPU execution; previous measured binaries/baselines remain unchanged. This
source-only increment had no new GPU run at its commit. The later lifecycle
run above exercises these timings on the GPU; a new performance baseline remains
unmeasured.

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

Seventeen current default CPU suites: `chat-parser-wire`, `worker-synthetic`, `worker-timing-contract`,
`worker-executor-contract`, `reactive-flow`, `metrics`, `monitor-parser`,
`executor-c-layout`, `http-monitor`, `http-synthetic`, `model-smoke-helper`,
`serving-lifecycle-helper`, `executor-bench-contract`, `gguf-layout-contract`,
`q2-source-contract`, `q2-route-plan`, `q2-hip-source-contract`.
The eight Q2 host C++ cases are a separate optional suite,
not part of the linked production provider. All contract/helper checks
use CPU clock/HTTP/executor fixtures only, never GPU/model execution.
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
   frontiers and output against the independent reference. Bounded HTTP/SSE,
   UTF-8, cancellation, pressure/isolation and retirement now pass in the lifecycle
   run above; this does not replace the numerical comparator or GPU failure gates.
   Define any extended protocol and oracle before execution. No rollout.
4. Only with a correct baseline, collect separate pure-inference traces and test
   a falsifiable internal-reactive change. Completed PP/TG, concurrency and serving
   improvements remain separate; no benefit has been measured yet.
5. T1/T2 refactoring, native C2/4/8, tool continuity, complete RAM/SSD state and
   MTP remain separate gates; CUDA follows qualified AMD work. SSD save/restore is
   a required **optional, default-off** feature with explicit enable, private
   directory and quota controls; RAM prefix reuse must work independently. The
   clarified [state contract](STATE.md) is design only, not a working CLI flag.

Do not reintroduce the historical assistant-imposed 32 GiB reserve as a user
requirement, call the DS4 300K stop an OOM, or import DS4's benchmarks/quality into
LIE. The monitor/UI is still development en_US; v0.1 is not release-ready.
