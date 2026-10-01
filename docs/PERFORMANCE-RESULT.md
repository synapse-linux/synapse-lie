# GPU performance result — 2026-10-01

The implemented LIE text/function runtime passed the declared performance matrix
on `.157`, using the original Qwen3.8-Flash-Next UD-Q4_K_XL weights and the
independently pinned embedded Gufo provider `f783fedb`. This measures the
current transitional backend, not an autonomous numerical executor, a DS4
comparison, or a reactive inference speedup. See [protocol](PERFORMANCE-PROTOCOL.md)
and [DS4 coverage gaps](DS4-COVERAGE.md).

## Execution and evidence

Runtime commit `213c91e`; isolated branch `feature/openai-reactive-api`.
The server binary is unchanged from the earlier GPU API qualification. The
only executor benchmark change records padding-line counts. Manifests bind
source file hashes, server/benchmark/helper binaries, DSO identities, read-only
model stat identities, CPU receipt and direct-result receipt. No model hash,
conversion, dependency installation or device tuning was performed.
Context 9216, prefill chunk 2048, greedy, thinking/MTP/vision off; maximum
128 generated tokens, EOS honored. Every counting request generated 128 tokens;
each native function case generated 28 with validated arguments.

HTTP ready `2026-10-01T15:28:21.136423+00:00`; clean finish `2026-10-01T15:43:41.349371+00:00`.
CPU fixtures on `.157`: **17/17 debug and 17/17 ASan/UBSan**, all six command
exit codes 0. CPU results are not model inference evidence.

Evidence directories: `evidence/performance-build-r1`,
`evidence/performance-cpu-r1`, `evidence/performance-executor-r1`,
`evidence/performance-http-r1`. Downloaded evidence collections were SHA-256
verified, and source/CPU/direct bindings checked. Raw outputs, warmups, errors
and transport timestamps are retained. `summary.json`, `summary.csv` and
`performance.svg`/`performance.png` are derived local artifacts.

## Direct completed-call C1 baseline

Three measured repetitions per prompt, following one warm-up. Full finite
logit frontiers and repeated token/logit hashes match the warm-up. Times
include synchronized provider calls and sampling, exclude model loading,
witness copying/hashing and transport. This is repeatability, not comparison
against a pristine independent numerical oracle.

| Physical prompt tokens | PP median token/s | TG median token/s |
|---:|---:|---:|
| 502 | 999.65 | 26.87 |
| 2042 | 1648.11 | 26.07 |
| 8191 | 1608.97 | 25.98 |

## Loopback HTTP

All **110 measured requests** and **22 warm-up requests** passed, across 16
configurations. Five measured groups per configuration; C2 has ten requests.
No retries or outlier removal. Throughput includes prefill and transport;
concurrent throughput uses total output divided by the full group interval.
JSON has no observable TTFT. SSE TTFT means first nonempty visible text,
not the response headers. Five groups do not qualify production tail SLOs.

| API / prompt | Transport | Clients | E2E median s | TTFT median s | Aggregate token/s |
|---|---|---:|---:|---:|---:|
| chat / native_function | JSON | 1 | 1.508 | — | 18.564 |
| chat / native_function | SSE | 1 | 1.507 | — | 18.578 |
| chat / p2048 | JSON | 1 | 6.180 | — | 20.713 |
| chat / p2048 | JSON | 2 | 12.340 | — | 20.708 |
| chat / p2048 | SSE | 1 | 6.177 | 1.295 | 20.723 |
| chat / p2048 | SSE | 2 | 12.355 | 2.588 | 20.717 |
| chat / p512 | JSON | 1 | 5.292 | — | 24.186 |
| chat / p512 | JSON | 2 | 10.557 | — | 24.203 |
| chat / p512 | SSE | 1 | 5.290 | 0.555 | 24.197 |
| chat / p512 | SSE | 2 | 10.553 | 1.089 | 24.210 |
| chat / p8192 | JSON | 1 | 10.069 | — | 12.712 |
| chat / p8192 | JSON | 2 | 20.256 | — | 12.631 |
| chat / p8192 | SSE | 1 | 10.096 | 5.203 | 12.678 |
| chat / p8192 | SSE | 2 | 20.298 | 10.515 | 12.586 |
| responses / p2048 | JSON | 1 | 6.180 | — | 20.714 |
| responses / p2048 | SSE | 1 | 6.179 | 1.295 | 20.717 |

Concurrency two approximately doubles per-request latency while aggregate
throughput stays similar (SSE ratios C2/C1: 1.0006, 0.9997, 0.9928).
The scheduler interleaves single-row sequences; this demonstrates concurrency
and serving responsiveness, with **no measured throughput speedup**. Native
function SSE headers arrive earlier, but structured output is buffered until
the complete validated call: median first structured output 1.507 seconds.

Admission burst: **8 HTTP 200 / 16 HTTP 429** from 24 simultaneous clients.
Refusals are retained separately and excluded from successful request averages.
Lifecycle passed cancellation during prefill/decode, TCP stalled-peer
backpressure, peer isolation and recovery. Final scheduler: active/queued/blocked
zero, failed zero, three expected cancellations. Cancellation is cooperative,
not kernel preemption.

## Sampled resources and retirement

Main telemetry covers load through shutdown. Supplementary read-only clock,
temperature, power and process observer: 693 samples,
`2026-10-01T15:32:08.045582+00:00` through `2026-10-01T15:43:40.831663+00:00`; this begins after warm-up
and does not cover initial loading. Device counters include the whole device.
Observed GPU busy median 100%; temperature
maximum 101.0 °C; driver-reported average power
median 110.2 W, maximum 158.6 W.
Observer GTT maximum 81.12 GiB;
VRAM maximum 361.93 MiB;
process RSS maximum 395.73 MiB.
Main system MemAvailable minimum 36.17 GiB.
Clocks are retained as active driver DPM states in raw telemetry. These sampled
counters are not exact allocation peaks; GTT/VRAM/RSS overlap on shared memory
and must not be summed. Power is not integrated energy.

Postflight at **15:45:00.635726 UTC**: all four existing lock device/inode
identities unchanged and locks free; helper/server/supervisor/observer PIDs
absent; KFD empty. Server and helper exit 0, observer exit 0, model stat
identities and binary unchanged. Direct benchmark separately retired cleanly
at 15:27:59 UTC. Each GPU run acquired its own four nonblocking leases and
registered start/end; no formal DS4 ACK or standing lease is claimed.

This completes the declared current-runtime performance matrix. Longer context,
vision/MTP/native batching, remote network deployment, energy/kernel profiling
and independent numerical/backend comparisons require separate protocols.
