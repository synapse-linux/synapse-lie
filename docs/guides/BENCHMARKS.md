<!-- SPDX-License-Identifier: MIT -->
# Running benchmarks

[Results and graphs by model/platform](../benchmarks/README.md) · [Build](BUILD.md)

`synapse-lie-bench` runs repeatable workloads and saves raw JSONL. Its direct
executor suites simplify the AR context-depth and multi-user workloads used by
Gufo. The `http-curve` suite implements its canonical cached-conversation depth
protocol; `http-multi` implements prepared-session HTTP cohorts. Execution,
reports and graphs are native C and require no Python. The results page
identifies the measurements already qualified on GPU.

## Choose the measurement

| Suite | Use it to measure | Timing scope |
| --- | --- | --- |
| `single` | Prefill and generation after an occupied prefix, through 128K by default. | New suffix prefill and decode, separately; excludes prefix construction. |
| `multi` | Decode throughput at 1, 2, 4, 6 and 8 simultaneous sequences. | All rows are prefilled before timed decoding; aggregate cohort decode rate. |
| `fresh` | The cost of processing a complete new prompt. | Full prompt prefill from an empty sequence, then decode. |
| `core` | The shared C engine, including admission and cache behavior. | Per-job TTFT, executed prefill, decode and output over cohort wall time. |
| `http` | Client-visible API latency and replayable conversation workloads. | HTTP request wall time and reported executor timings. |
| `http-curve` | Canonical Gufo conversation depth curve, through 128K by default. | Executed new-turn PP and TG, with HTTP wall time and TTFT recorded separately. |
| `http-multi` | Gufo-style prepared HTTP cohorts at C1/2/4/6/8, for AR or a separately configured MTP server. | Sum of individual server decode rates, common HTTP wall throughput, TTFT and preparation prefill. |
| `http-kv-disk` | KV checkpoint persistence across a server restart, including concurrent consumers. | HTTP latency, actual restored tokens and disk accounting. |

Prefill (PP) is prompt processing; generation (TG) is token decoding. Rates use
**tokens per second**. TTFT is time to first token. A full cache hit has no new
prefill tokens, so its executed PP rate is unavailable, not zero or infinity.
Decode rate and total output divided by request wall time are different metrics.
The core report rejects missing executed-phase time, inconsistent call counts
and phase times beyond the job's wall time before publishing graphs or a summary.

## Canonical Gufo conversation curve

Use an already running, authorized HTTP server. For the README server example:

```sh
mkdir -p results
build/release/synapse-lie-bench --suite http-curve \
  --url http://127.0.0.1:8000/v1 --model qwen3.8-flash-next \
  --depths 0,4096,8192,12288,16384,32768,65536,131072 \
  --pp 2048 --tg 128 --context-capacity 262144 \
  --warmups 1 --repetitions 3 --server-label LIE \
  --output results/lie-curve.jsonl --graphs results/lie-curve
```

The suite follows official Gufo `f783fedb`: calibrate template overhead with
`Hi` and tokens per word with the seeded 3,000-word probe, warm up, then prepare
each depth with an **8-token output budget**. Its actual assistant reply enters
the next request. The measured turn adds about 2,048 new tokens and requests
128 output tokens. Cached depth and new prefill must each lie within
`max(32, floor(target × 0.005))` tokens; a miss recalibrates and retries, at most
four times. The corrected ratio carries forward to deeper points. Early EOS in
the measured turn fails the curve instead of shortening the output workload.
All probes, warmups, preparations, retries and measured requests remain in JSONL.

The default task is `prose`; `--task repetition|copy|story|thinking` selects the
other pinned recipes. Thinking changes template options for both prefix and
measured turns. Greedy sampling and neutral penalties are explicit. Use a
separately configured MTP server with `--mode mtp`; this client does not enable
MTP or load a predictor itself. `X-Client-ID: model-bench` is shared across the
sequential requests, so run one curve at a time against an otherwise idle server.
RAM prefix caching must retain the tested state; a miss is visible in actual
cached/new-token counts and cannot be presented as a successful depth sample.

For a Gufo control, use the same model alias, context, workload and budgets,
a separate output filename, and `--endpoint-profile gufo --server-label Gufo`.
That profile adds Gufo's neutral top-k/min-p/repetition controls. Compare native
curve files offline:

```sh
build/release/synapse-lie-bench --suite report results/lie-curve.jsonl \
  --compare results/gufo-curve.jsonl --output results/curve-comparison \
  --label LIE --reference-label Gufo
```

The report regenerates the complete expected request sequence from retained
replies and token counts before calculating statistics. `summary.csv` and JSON
include arithmetic mean, sample standard deviation, median and min/max. Four
separate graph panels show PP, TG, HTTP wall time and TTFT with their own scales.
The comparison exposes differences in request hashes, completions and physical
counts. Different calibrated histories across quantizations remain visible;
matching the recipe alone does not establish numerical parity.

Depths up to 1,048,576 can be declared when the remote server supports enough
capacity for **depth + new prefill + output**. This is a client protocol limit:
LIE now accepts explicit [YaRN context profiles](CONTEXT.md) through a total
capacity of 1,048,576. A depth of exactly 1,048,576 leaves no room for new prefill
or output and therefore cannot run at that capacity. Reserve those tokens when
choosing the largest depth. Selecting a larger client argument alone does not
change the server profile or establish GPU memory fit. Exact text/protocol equivalence has
CPU fixture coverage through 128K and a 1M client protocol boundary; new GPU
performance results require a separate coordinated run.

## Simplified executor depth and concurrent users

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

To check credit handling directly in the core, prepare a JSON array of physical
token IDs and run the optional functional probe:

```sh
"$LIE_BENCH" --suite core --model "$LIE_MODEL" \
  --tokens-file tokens.json --context 4096 --chunk 2048 \
  --users 2 --tg 128 --warmups 0 --repetitions 1 \
  --kv-cache-ram-mb 0 --reactive-probe \
  --output results/core-reactive.jsonl
```

The probe holds a borrowed output block without returning its credits, requires
the peer to finish, then cancels the held job and checks loan stability and
retirement. It needs two users, at least 16 output tokens, one repetition, no
warmup, and cache and vision disabled. MTP may be enabled with its predictor.
This produces functional evidence about backpressure and cancellation; use the
regular suites above for throughput measurements. A synthetic build checks the
consumer contract; original-weight inference requires a qualified GPU build.

To measure the dense sampler on original weights, use a fixed seed and keep
sampling parameters identical in both builds:

```sh
"$LIE_BENCH" --model "$LIE_MODEL" --suite core \
  --prompt-file prompt.txt --context 32768 --chunk 2048 \
  --users 1 --tg 128 --warmups 1 --repetitions 3 \
  --temperature 0.8 --top-p 0.9 --seed 123 \
  --frequency-penalty 0.2 --presence-penalty 0.1 \
  --kv-cache-ram-mb 0 --output results/core-sampled.jsonl
```

The default remains greedy. Nonzero temperature requires `--seed`; each request
uses that seed independently, including warmups and concurrent users. The raw
identity and report record all five controls, and a matched comparison refuses
different sampling settings. Older core results without those fields retain
their historical greedy defaults. These controls select the existing shared-core
sampling API; top-k and min-p are not exposed by that API.

MTP is integrated in the shared-core suite. Add an explicit compatible predictor
and draft budget to separate runs (one cohort size per invocation):

```sh
for LIE_USERS in 1 2 4 6 8; do
  "$LIE_BENCH" --model "$LIE_MODEL" --suite core \
    --model-mtp /path/to/mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf \
    --mtp-draft-tokens 3 --prompt-file prompt.txt \
    --context 32768 --chunk 2048 --users "$LIE_USERS" \
    --tg 128 --warmups 1 --repetitions 3 --kv-cache-ram-mb 0 \
    --output "results/core-mtp-c$LIE_USERS.jsonl" || break
done
```

The core suite records cohort wall time, individual job timings and actual
proposed/accepted tokens. It does not use Gufo's all-prefilled HTTP decode barrier
or its sum of individual request rates. The direct `single`/`multi`/`fresh`
suites currently support AR only; using `core` does not complete those MTP
comparison workloads.

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

For the [Point cold-context comparison](../benchmarks/2026-10-04/strix-point/http-depth/README.md),
run one target per **fresh** 262,144-context server and use
`--preset long-context --sizes TARGET --tg 128 --warmups 0 --repetitions 2
--context-capacity 262144 --rope-scaling native --corpus-seed 20261004
--server-kv-cache off --timeout 1800`. LIE needs `--kv-cache-ram-mb 0`
and no SSD options; official Gufo needs a JSON request-options file containing
`{"cache_prompt":false}`. The campaign runner pins the servers and model,
acquires the GPU lease and archives both original requests and results. The
offline verifier removes only that Gufo-specific cache-control field when
checking matched request bodies. Client declarations alone do not disable a
server cache or raise its context capacity.

## Prepared HTTP multi-user cohorts

Use a running server with prefix caching enabled and at least eight active
slots. On LIE, select `--max-active 8` and a sufficient `--kv-cache-ram-mb`
budget when starting it; do not use RAM zero or eviction that prevents reuse.
Use the same model alias and physical weights for the LIE and Gufo servers.
The client does not start, reconfigure or restart either server.

The repository includes the pinned Gufo prompt data. `prose.jsonl` is the
mixed-text AR/MTP workload; `repetition.jsonl` is the predictable MTP workload.
Both target approximately 2,048 input tokens at depth zero. Their UTF-8 prompt
hashes match the published artifacts; actual new-run token counts must still
be verified. License, source pin and hashes are in the
[corpus provenance](../../config/bench/gufo-qwen38/PROVENANCE.json).

```sh
"$LIE_BENCH" --suite http-multi \
  --url http://127.0.0.1:8000/v1 --model qwen3.8-flash-next \
  --requests config/bench/gufo-qwen38/prose.jsonl \
  --users 1,2,4,6,8 --tg 128 --context-capacity 4096 \
  --warmups 1 --repetitions 3 --server-label LIE \
  --output results/http-multi-prose.jsonl

# After collecting the same workload from the authorized Gufo server:
"$LIE_BENCH" --suite report results/http-multi-prose.jsonl \
  --output results/http-multi-prose-charts --label LIE \
  --compare results/gufo-http-multi-prose.jsonl --reference-label Gufo
```

For the Gufo run, use the first command with its URL, `--server-label Gufo`
and a new output filename. For MTP, explicitly start a compatible MTP-enabled
server, then collect separate files with both supplied corpora. The client
keeps greedy sampling and thinking disabled; it does not enable MTP itself.
`--context-capacity` records the declared server setting and checks that the
observed prompt plus output fits it; it does not expand the provider ceiling.

Each participant has a distinct `X-Client-ID`, preserved across preparation
and measurement. Every preparation must finish one output token before any
measured request begins. The measured request must reuse the prompt, replay
at most four tail tokens and complete all 128 output tokens. One native C
event loop drives the cohort. Missing phase timings, early EOS, incomplete
streams, changed payloads or failed participants fail the run; partial JSONL
remains available and is excluded from reports.

`sum_request_decode_tps` is the sum of each participant's output divided by
its server decode time, matching Gufo's rate definition. It is distinct from
`aggregate_output_tps`, which divides all output by the common complete HTTP
interval and includes client/server overhead. Preparation wall time and the
mean executed per-request PP rate are recorded separately. A preparation
cohort made entirely of cache hits has no executed PP rate. Graphs put PP,
the two decode metrics and TTFT in four panels with separate scales.

The default has one excluded warmup cohort and three measured cohorts for
statistics. `--warmups 0 --repetitions 1` selects a single prepared cohort,
closer to Gufo's published point count. Preparation still occurs. The native
fixture tests qualify client behavior; paired original-weight GPU campaign
results for this new suite remain pending.

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
median as the plotted value for direct/core/ordinary HTTP and prepared cohorts.
Canonical `http-curve` plots arithmetic means, as Gufo does, and also exports
sample standard deviation. Preserve raw JSONL and the build/model identities.
Direct-suite CSV/JSON also include prefill/decode seconds with median, minimum
and maximum. These durations are summarized independently of throughput.
New raw direct samples carry monotonic phase bounds and a wall-clock sample
start for correlation with thermal/device telemetry. Prefix construction ends
before the prefill bound; frontier inspection and flow setup precede decode.
Elapsed time always uses the monotonic clock. The exporter rejects incomplete,
reversed or duration-inconsistent phase bounds and still reads older evidence
without those fields. Graphs alone do not supply clock/power telemetry.
A graph-export failure returns a nonzero exit code while retaining the measurement file.

KV disk reports instead plot nearest-rank p50/p95/p99 latency distributions.
Their CSV includes sample counts, executed prefill and generation rates. Missing
measurements are omitted and labeled when an entire plotted series is unavailable.

SVG and PNG are generated directly in C; Python and Matplotlib are not needed.
Use a new output directory for each report: existing artifacts are not replaced.

## Coverage of Gufo's published campaign

| Published workload | LIE coverage |
| --- | --- |
| AR single user at eight prefix depths. | Canonical `http-curve` is implemented and CPU-qualified; its new GPU campaign remains separate. Direct LIE/Gufo GPU comparisons and fresh, cache-disabled [served HTTP AR](../benchmarks/2026-10-04/strix-point/http-depth/README.md) reach near 256K on Strix Point with two measured repetitions per engine. Explicit YaRN profiles permit total capacity through 1,048,576; original-weight 1M memory, quality and performance qualification remains open. |
| AR multiple users. | Native batching and the [served 4K HTTP campaign](../benchmarks/2026-10-04/strix-point/http-multi/README.md) both compare LIE and official Gufo through C8. The HTTP campaign includes fresh sessions=C and fixed eight-session capacity. Long-context multi-client HTTP is still open. |
| MTP single and multiple users. | Direct core and the [served 4K HTTP campaign](../benchmarks/2026-10-04/strix-point/http-multi/README.md) compare AR/MTP and LIE/Gufo through C8 on prose and repetition. The cold served [long-context campaign](../benchmarks/2026-10-04/strix-point/http-depth/README.md) matches MTP and AR through near 256K at C1, with prefill, draft acceptance, decode and wall time. Long-context multi-client HTTP is still open. |
| Cold-file loading to HTTP readiness. | Still missing; `loading` measures model construction with uncontrolled OS file-cache state. |
| Peak HIP memory. | Still missing; `memory` exports provider estimates, not allocation-exact peak usage. |

The reference is Gufo's [benchmark page](https://github.com/gufo-org/gufo/blob/f783fedb9bea2ec7de941f6da4e02f4a4596b29e/docs/models/qwen3.8-flash-next/BENCHMARKS.md)
and [measurement method](https://github.com/gufo-org/gufo/blob/f783fedb9bea2ec7de941f6da4e02f4a4596b29e/docs/models/qwen3.8-flash-next/QUALITY.md#benchmark-method).
Internal correctness tests and historical implementation checks are maintained
separately in the [development documentation](../development/README.md).
