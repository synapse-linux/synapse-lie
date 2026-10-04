# Full-prefill and served benchmark results on .157

> Historical technical record. See [current usage](../guides/USAGE.md) and
> [benchmark tables and graphs](../benchmarks/README.md). Results below retain
> their original build, protocol and limitations.

Original Unsloth UD-Q4_K_XL, pinned embedded Gufo, AR greedy, thinking/MTP off,
capacity 262144, chunk 2048, C1. Benchmark source `fe061d8`, server source
`9725832`. All tests/model forward ran on `.157`; CPU prerequisite is 21/21
debug plus 21/21 ASan/UBSan. No model conversion, installation or host tuning.

## Full prompt from empty state

`reactive-suite-r5/fresh`: two measured repetitions, **no discarded warm-up**,
ascending sizes, 128 actual output tokens in every sample. Complete physical
inputs, output IDs and full prefill/final-decode frontier hashes are retained;
repeatability holds at all six points. Calibration, load, vocabulary hash and
file output are outside the completed PP/TG intervals. The first small-prompt
observation remains in the table despite being slower.

| Prompt tokens | PP median tok/s | PP min–max | PP median s | TG median tok/s | TG min–max | TG128 median s |
|---:|---:|---:|---:|---:|---:|---:|
| 1500 | 1446.20 | 1361.54–1530.86 | 1.041 | 26.66 | 26.64–26.68 | 4.801 |
| 8000 | 1528.70 | 1524.69–1532.71 | 5.233 | 26.00 | 25.98–26.01 | 4.924 |
| 8192 | 1531.83 | 1527.24–1536.42 | 5.348 | 25.85 | 25.77–25.94 | 4.951 |
| 32768 | 1457.88 | 1455.04–1460.71 | 22.477 | 25.77 | 25.77–25.77 | 4.968 |
| 131072 | 1354.82 | 1334.15–1375.50 | 96.767 | 24.73 | 24.68–24.77 | 5.177 |
| 258794 | 1270.51 | 1269.40–1271.62 | 203.693 | 23.89 | 23.89–23.90 | 5.357 |

These are full-prefill averages, unlike `single`'s 2048-token suffix at an
already occupied prefix. The model stays loaded but each repetition starts a
fresh sequence. Model-load page-cache state is uncontrolled; neither cold-file
loading nor exact peak GPU allocation is claimed. Two observations provide
observed ranges, not statistical confidence intervals. Ordered points do not
separate thermal/session drift from context-dependent cost.

[Graph](../benchmarks/2026-10-01/comparable/fresh/benchmark.svg),
[summary CSV](../benchmarks/2026-10-01/comparable/fresh/summary.csv),
[all samples](../benchmarks/2026-10-01/comparable/fresh/samples.csv).

## HTTP scope

The separate Python client sends standard Chat Completions SSE and uses actual
usage. The API binds the operator-selected `.157:8000`; management stays on
loopback. HTTP fixtures and the real Pi cycle are separate from the timed runs.
Prefill uses repeated maintenance notes; direct prompts use varied project notes.
Do not subtract these two suites to estimate transport overhead. Per-request
executor timings are retained alongside client wall/first-output times.

HTTP PP is prompt tokens divided by the **complete** request wall, including one
generated token. HTTP TG is actual output tokens divided by complete wall,
including prefill. It is not pure decode, a count of chunks, or a speculative
acceptance metric. Cache is absent in LIE; no warm prefix is passed between
requests, including the conversation test.

The ten built-in decode shapes are independently authored short tasks; even
`tool-dialogue` is text-only. Actual read/edit/read execution is the separately
qualified Pi test, not one of these throughput prompts. All ten generated the
full 256-token budget. This is one observation per shape: variation across shapes
is not a repeatability confidence interval or an independent quality score.

## HTTP prefill, two observations per size

| Physical prompt | Client wall median s | First output median s | Prompt / HTTP wall mean tok/s | Executor PP median tok/s |
|---:|---:|---:|---:|---:|
| 8183 | 5.415 | 5.415 | 1511.20 | 1567.90 |
| 32759 | 22.045 | 22.045 | 1485.99 | 1500.37 |
| 131063 | 94.264 | 94.264 | 1390.39 | 1394.17 |

Each request generated exactly one token. Calibration uses three separate
requests outside the measured set and retains the actual count (target minus
nine tokens at these sizes). [Graph/CSV](../benchmarks/2026-10-01/comparable/http-prefill/summary.csv) and
[all observations](../benchmarks/2026-10-01/comparable/http-prefill/samples.csv).

## HTTP decode, ten shapes

| Shape | Prompt | Output | First output s | Complete wall s | Output / wall tok/s |
|---|---:|---:|---:|---:|---:|
| prose | 32 | 256 | 0.365 | 9.886 | 25.90 |
| code | 34 | 256 | 0.387 | 9.893 | 25.88 |
| proof | 37 | 256 | 0.349 | 9.903 | 25.85 |
| chat | 32 | 256 | 0.343 | 9.850 | 25.99 |
| analysis | 29 | 256 | 0.344 | 9.899 | 25.86 |
| structured | 38 | 256 | 0.356 | 9.864 | 25.95 |
| translation | 36 | 256 | 0.351 | 9.890 | 25.89 |
| debug | 38 | 256 | 0.364 | 9.947 | 25.74 |
| review | 33 | 256 | 0.345 | 9.863 | 25.96 |
| tool-dialogue | 45 | 256 | 0.377 | 9.918 | 25.81 |

Equal-weight mean across shapes: **25.88 tok/s**,
range 25.74–25.99. All outputs reached the budget; none was
replaced by a nominal count. [Graph](../benchmarks/2026-10-01/comparable/http-decode/benchmark.svg),
[summary](../benchmarks/2026-10-01/comparable/http-decode/summary.json).

## Actual conversation replay at 100K

| Turn | Physical prompt | Actual output | Complete wall s | Executor prefill s |
|---:|---:|---:|---:|---:|
| 1 | 99995 | 1 | 69.758 | 69.524 |
| 2 | 100419 | 1 | 71.789 | 71.546 |

The second request contains the actual first assistant reply and 424 additional
physical prompt tokens overall. It still prefills all 100419 tokens: no state
cache is present. This is the concrete agent-latency gap that batching alone
does not solve. One observation per turn, two actual turns; the CLI's default
20-turn workload is available but is **not claimed measured** in this campaign.
[Graph](../benchmarks/2026-10-01/comparable/http-conversation/benchmark.svg),
[raw sample columns](../benchmarks/2026-10-01/comparable/http-conversation/samples.csv).

## Integrity, retirement and limits

Campaign **PASS**, 2026-10-01 **21:57:54–22:19:05 UTC**. Both arm supervisors,
the direct benchmark, the HTTP server and all three HTTP client processes exited
0. All four owned helper/model PIDs in postflight were absent; the controller
and three clients were additionally checked via `/proc` (expected SCP exit 1,
ENOENT). KFD was empty and all four unchanged leases were free. Both model-stat
snapshots and staged binaries remained unchanged. No permanent server is left.

The collected archive has **33 hash-verified files**. Raw requests, physical IDs,
output IDs, finite frontiers, all SSE chunks, corpus exports, model/DSO/source
identities, command exits, GPU-client watch and sampled telemetry remain in
`evidence/reactive-suite-r5/`. Full source hash inventory binds the CPU capsule;
report plots/CSV are offline projections, not additional GPU measurements.
[Receipt](../benchmarks/2026-10-01/comparable/receipt.json).

Published external rows are reference observations with different checkpoints,
prompt sets, precision, releases, chunking and host conditions. This campaign
runs LIE only and makes no matched speedup claim against them. The executable
can export/replay the exact corpus on another authorized endpoint; missing MTP,
prompt lookup, cached-state restore and 1M/YaRN are not simulated. The complete
reactive/serial comparison remains a separate matched experiment in
[REACTIVE-INFERENCE-RESULT.md](REACTIVE-INFERENCE-RESULT.md).
