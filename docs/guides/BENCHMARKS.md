<!-- SPDX-License-Identifier: MIT -->
# Running benchmarks

[Results and graphs by model/platform](../benchmarks/README.md) · [Build](BUILD.md)

`synapse-lie-bench` runs repeatable workloads and saves raw JSONL. Its direct
executor suites simplify the AR context-depth and multi-user workloads used by
Gufo. They do not reproduce Gufo's complete published HTTP protocol. The results
page states which measurements exist and which are still missing.

## Choose the measurement

| Suite | Use it to measure | Timing scope |
| --- | --- | --- |
| `single` | Prefill and generation after an occupied prefix, through 128K by default. | New suffix prefill and decode, separately; excludes prefix construction. |
| `multi` | Decode throughput at 1, 2, 4, 6 and 8 simultaneous sequences. | All rows are prefilled before timed decoding; aggregate cohort decode rate. |
| `fresh` | The cost of processing a complete new prompt. | Full prompt prefill from an empty sequence, then decode. |
| `core` | The shared C engine, including admission and cache behavior. | Per-job TTFT, executed prefill, decode and output over cohort wall time. |
| `http` | Client-visible API latency and replayable conversation workloads. | HTTP request wall time and reported executor timings. |
| `http-kv-disk` | KV checkpoint persistence across a server restart, including concurrent consumers. | HTTP latency, actual restored tokens and disk accounting. |

Prefill (PP) is prompt processing; generation (TG) is token decoding. Rates use
**tokens per second**. TTFT is time to first token. A full cache hit has no new
prefill tokens, so its executed PP rate is unavailable, not zero or infinity.
Decode rate and total output divided by request wall time are different metrics.

## Context depth and concurrent users

Use a GPU build and the first model shard. Pick unused output filenames; the
benchmark refuses to overwrite results. On the shared `.157` host, runs must
first follow the [coordination protocol](../COORDINATION.md).

```sh
LIE_BENCH=build/release/synapse-lie-bench
LIE_MODEL=/path/to/Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf
mkdir -p results

"$LIE_BENCH" --model "$LIE_MODEL" --suite single \
  --depths 0,4096,8192,12288,16384,32768,65536,131072 \
  --pp 2048 --tg 128 --warmups 1 --repetitions 3 \
  --execution reactive --output results/single.jsonl

"$LIE_BENCH" --model "$LIE_MODEL" --suite multi \
  --users 1,2,4,6,8 --pp 2048 --tg 128 \
  --warmups 1 --repetitions 3 --execution reactive \
  --output results/multi.jsonl
```

`single` measures approximately 2,048 **new** tokens after the selected depth.
Inspect the recorded physical token counts, since tokenization can differ by
one token. `multi` uses 4,096 tokens of capacity per user. These are direct
executor measurements; the HTTP layer is not involved.

For a paired local Gufo control, run the same suite and workload options with
`build/release/synapse-lie-bench-gufo-reference`, using a different output file.
For a LIE serial control, use `--execution serial`. Keep model files, hardware,
context, output budget and repetitions identical. The report checks physical
inputs, outputs and completion before presenting an eligible comparison.

## Full prompt prefill

```sh
"$LIE_BENCH" --model "$LIE_MODEL" --suite fresh \
  --sizes 1500,8000,8192,32768,131072,258794 \
  --tg 128 --warmups 0 --repetitions 3 \
  --output results/fresh.jsonl
```

This measures the full prompt, including the time needed to fill a new state.
It must not be compared directly with the suffix PP in `single` or a cached
conversation follow-up. The runtime ceiling is 262,144 tokens; 512K and 1M
inference are not supported by the current provider.

## Shared engine and cache

Prepare a UTF-8 text file and select enough context for its tokens plus output:

```sh
"$LIE_BENCH" --model "$LIE_MODEL" --suite core \
  --prompt-file prompt.txt --context 32768 --chunk 2048 \
  --users 1 --tg 128 --warmups 0 --repetitions 3 \
  --kv-cache-ram-mb 0 --output results/core-fresh.jsonl
```

Use `--kv-cache-ram-mb 4096 --warmups 1` with a separate output file to measure
repeated prompt reuse. The file is raw text, without a chat template. The core
exports executed prefill and cache counters so hits remain distinguishable from
recomputation. KV disk options match those in the [server guide](USAGE.md#kv-cache-in-ram-and-on-disk).

## HTTP workloads

Start the server first. This suite uses the native C HTTP client:

```sh
"$LIE_BENCH" --suite http \
  --url http://127.0.0.1:8000/v1 --model qwen3.8-flash-next \
  --preset prefill --sizes 1500,8000,32768,131072 \
  --tg 128 --warmups 0 --repetitions 3 --server-kv-cache off \
  --server-label lie --output results/http-prefill.jsonl \
  --export-requests results/http-requests.json
```

Here `--server-kv-cache off` **records the server's declared configuration**; it
does not change the server. Start the server with `--kv-cache-ram-mb 0` and
without SSD options for that measurement. Other presets are `decode`,
`conversation` and `long-context`; use `--requests FILE` to replay a saved
corpus. The long-context generator can prepare larger inputs, but does not
extend the model's context limit. `--timeout` is the deadline in seconds for a
complete HTTP request, including response streaming.

For KV disk restart checks, use `--suite http-kv-disk --help`. Run the `write`
phase, restart the server against the same KV directory, then run `read` with
`--reference` pointing to the write phase's `.summary.json`. This suite requires
RAM retention off and disk retention on; it never starts or restarts the server.
The old `http-ssd` suite name remains an alias. These checks concern KV state,
not model-weight storage.

## Generate graphs

Add `--graphs results/charts` to a run, or export afterwards without loading
the model:

```sh
"$LIE_BENCH" --suite report results/single.jsonl \
  --output results/single-charts --label 'LIE'

"$LIE_BENCH" --suite report results/multi.jsonl \
  --output results/multi-charts --label 'LIE reactive' \
  --compare results/gufo-multi.jsonl --reference-label 'Gufo local control'
```

Each export contains `benchmark.svg`, `benchmark.png`, `summary.csv` and
`summary.json`. Throughput axes start at zero; prefill and generation have
separate scales. Error bars show the observed minimum and maximum, with the
median as the plotted value. Preserve raw JSONL and the build/model identities.
A graph-export failure returns a nonzero exit code while retaining the measurement file.

KV disk reports instead plot nearest-rank p50/p95/p99 latency distributions.
Their CSV includes sample counts, executed prefill and generation rates. Missing
measurements are omitted and labeled when an entire plotted series is unavailable.

SVG and PNG are generated directly in C; Python and Matplotlib are not needed.
Use a new output directory for each report: existing artifacts are not replaced.

## Coverage of Gufo's published campaign

| Published workload | LIE coverage |
| --- | --- |
| AR single user at eight prefix depths. | Simplified direct suite and local Gufo control measured through 128K. |
| AR multiple users. | Native batching measured through eight users. Exact HTTP per-request-rate summation is still missing. |
| MTP single and multiple users. | MTP is not integrated. |
| Cold-file loading to HTTP readiness. | Still missing; `loading` measures model construction with uncontrolled OS file-cache state. |
| Peak HIP memory. | Still missing; `memory` exports provider estimates, not allocation-exact peak usage. |

The reference is Gufo's [benchmark page](https://github.com/gufo-org/gufo/blob/f783fedb9bea2ec7de941f6da4e02f4a4596b29e/docs/models/qwen3.8-flash-next/BENCHMARKS.md)
and [measurement method](https://github.com/gufo-org/gufo/blob/f783fedb9bea2ec7de941f6da4e02f4a4596b29e/docs/models/qwen3.8-flash-next/QUALITY.md#benchmark-method).
Internal correctness tests and historical implementation checks are maintained
separately in the [development documentation](../development/README.md).
