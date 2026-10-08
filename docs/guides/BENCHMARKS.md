<!-- SPDX-License-Identifier: MIT -->
# Running benchmarks

[Results and graphs by model/platform](../benchmarks/README.md) · [Build](BUILD.md)

`synapse-lie-bench` runs repeatable workloads and saves raw JSONL. Its direct
executor suites simplify the AR context-depth and multi-user workloads used by
Gufo. The `http-curve` suite implements its canonical cached-conversation depth
protocol; `http-multi` implements prepared-session HTTP cohorts. Execution,
reports and graphs are native C and require no Python. The results page
identifies the measurements already qualified on GPU.

Commands use `build/strix-halo/`, produced by `make strix-halo`. Substitute
`build/strix-point/` after `make strix-point`. The separate Gufo comparison
executable uses `build/release/` from the [advanced build recipe](BUILD.md#advanced-cmake-build-and-comparison-control).

## Choose the measurement

| Suite | Use it to measure | Timing scope |
| --- | --- | --- |
| `single` | Prefill and generation after an occupied prefix, through 128K by default. | New suffix prefill and decode, separately; excludes prefix construction. |
| `multi` | Decode throughput at 1, 2, 4, 6 and 8 simultaneous sequences. | All rows are prefilled before timed decoding; aggregate cohort decode rate. |
| `fresh` | The cost of processing a complete new prompt. | Full prompt prefill from an empty sequence, then decode. |
| `ds4-walk` | Incremental prefill as one raw-text prefix grows. | Newly appended PP tokens and TG; checkpoint and restore/replay have separate durations. |
| `core` | The shared C engine, including admission and cache behavior. | Per-job TTFT, executed prefill, decode and output over cohort wall time. |
| `http` | Client-visible API latency and replayable conversation workloads. | HTTP request wall time and reported executor timings. |
| `http --preset long-context-recall` | Exact recovery of independent key/value bindings at start, middle and end, including continuation. | Actual prompt/output usage and per-turn exact-match results; separate from throughput workloads. |
| `http-curve` | Canonical Gufo conversation depth curve, through 128K by default. | Executed new-turn PP and TG, with HTTP wall time and TTFT recorded separately. |
| `http-multi` | Gufo-style prepared HTTP cohorts at C1/2/4/6/8, for AR or a separately configured MTP server. | Sum of individual server decode rates, common HTTP wall throughput, TTFT and preparation prefill. |
| `http-kv-disk` | KV checkpoint persistence across a server restart, including concurrent consumers. | HTTP latency, actual restored tokens and disk accounting. |

Prefill (PP) is prompt processing; generation (TG) is token decoding. Rates use
**tokens per second**. TTFT is time to first token. A full cache hit has no new
prefill tokens, so its executed PP rate is unavailable, not zero or infinity.
Decode rate and total output divided by request wall time are different metrics.
The core report rejects missing executed-phase time, inconsistent call counts
and phase times beyond the job's wall time before publishing graphs or a summary.

## Incremental raw-corpus walk

Use `ds4-walk` to measure a fixed number of new prefill tokens at increasing
physical context sizes. It tokenizes one UTF-8 text file without a chat template,
then advances through contiguous frontiers. For a short check:

```sh
build/strix-halo/synapse-lie-bench --suite ds4-walk \
  --model /path/to/first-model-shard.gguf --corpus /path/to/corpus.txt \
  --pp 2048 --sizes 2048,4096,6144,8192 --context 262144 \
  --prefill-chunk 2048 --tg 128 --warmups 0 --repetitions 3 \
  --restore auto --output results/walk.jsonl --graphs results/walk
```

Create `results/` first. Without `--sizes`, frontiers advance by `--pp` through
128K; the default is one walk with no warmup. Each frontier must be exactly
one `--pp` step beyond the previous one. The context must also leave room for
the requested output. `--context` admits up to 1,048,576 tokens with an explicit
`--rope-scaling native|yarn2|yarn4` profile; see [context profiles](CONTEXT.md).
For example, a 2K walk can reach 1,046,528 prompt tokens with a 1M capacity.
The corpus must tokenize to at least the last frontier and fit the 8 MiB input
bound. Configuration limits alone do not qualify model quality or memory fit.

The PP numerator is always the newly appended step, rather than the complete
prefix. Before TG, `--restore auto` captures prefix state within a 1 GiB budget;
unsupported or larger state uses replay. `--restore replay` forces replay.
Before advancing, the benchmark creates a pristine physical sequence, restores
or replays the prior prefix, and verifies its logits hash. Checkpoint creation
and restoration remain outside PP/TG timers. Transfer failures terminate the
run. JSONL retains their methods, bytes and monotonic intervals; JSON summarizes
phase durations and CSV adds new PP tokens, checkpoint seconds and restore seconds. The first frontier
has no restore measurement. PP and TG graphs use separate vertical scales.

This suite is C1 greedy AR. Reactive execution uses the shared C17 flow and
inference dispatch; the direct Gufo control uses its native API and replay.
The current control refuses scaled RoPE. A comparison requires matching
measurement contract, profile, physical prefixes, chunk, capacity and output
budget. Natural EOS remains visible; shortened output cannot enter a matched
TG comparison. `fresh` measures full prefill and answers a different question.
The current port passes
[original Q2 and UD-Q4 checks at 2K/4K/6K/8K](../benchmarks/models/qwen3.8-flash-next/strix-halo/README.md#current-q2-and-native-walk-qualification--october-8):
snapshot/replay and the original-sampler control retain identical logits hashes
and output IDs. Longer walks and matched performance remain separate gates.
The [earlier Q2 walk](../DS4-WALK-BENCH.md) retains its own binary identity.

## Reading prefill dispatch

Direct `single`, `multi`, `fresh` and `ds4-walk` suites accept `--prefill-chunk N` (1–32,768;
default 2,048). `--suite core` also accepts `--prefill-capacity N` to reserve a
larger provider capacity than its selected chunk. `--chunk` remains a CLI alias.
JSONL identities and summaries report both values; comparative reports require
matching chunk and capacity. Historical reports without capacity use their
recorded chunk as the reservation. These are configuration controls, not
measurements or proof that a larger chunk improves PP. HTTP suites use the
server's [shared-engine configuration](USAGE.md#context-and-concurrency).

Core sample JSONL includes `prefill_attention_dispatch`: confirmed and
unconfirmed attention selections over the cohort, split by matrix/scalar and
dense/sparse paths. `mask_pitch_refusals` helps investigate the fallback at high
configured context. `attention_rows` sums layer rows; it is not prompt usage.
Progress snapshots report cumulative counts. Maximum rows/mask words remain
lifetime maxima. Availability is explicit: null totals mean unsupported or
non-exact observation, while supported fully cached samples can have zero new
calls. This field does not alter PP/TG timing or prove a reactive improvement.
[The contract](../reference/METRICS.md#prefill-attention-dispatch) specifies
cancellation, epoch and overflow semantics. The matching r70 HIP build is
qualified. The [sparse-attention component gate](../development/validation/attention-fixture-point-2026-10-07.json)
checks generated inputs through 1M; actual original-weight dispatch and matched
observer cost remain open.

## Canonical Gufo conversation curve

Use an already running, authorized HTTP server. For the README server example:

```sh
mkdir -p results
build/strix-halo/synapse-lie-bench --suite http-curve \
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
build/strix-halo/synapse-lie-bench --suite report results/lie-curve.jsonl \
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
LIE_BENCH=build/strix-halo/synapse-lie-bench
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

For a paired direct provider control, run the same suite and workload options
with `build/release/synapse-lie-bench-gufo-reference`, using a different output
file. This executable binds the Gufo API to the verified sampling-OFF provider
build. It shares the upstream numerical engine and applicable provider ports;
it compares call paths and batching, not independent numerical engines or an
independently served official Gufo server. Use the HTTP commands above for that
server comparison and retain each server's source/build identity.

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
conversation follow-up. This simplified suite uses the native profile through
262,144 tokens. Explicit extended profiles are available in the shared-core
suite below; their physical GPU and quality gates remain separate.

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

The `core` suite accepts the same [initial steering controls](USAGE.md#directional-steering)
as the server. JSONL records requested scales and actual READY bank hashes and
host/device vector bytes. Matched reports require the same bank identity and
scales; they refuse inconsistent admission or a different steering configuration.
Older records without steering metadata mean unsteered inference. Vector-data
metadata and host fixtures are separate from numerical GPU qualification.

For a fixed-token decode measurement, add `--ignore-eos` to this **core** command.
Official Gufo's pinned native TG method continues past EOS to its stated output
budget. This flag gives LIE the same completion policy: an EOS token is sampled
and counted normally, even if its text is empty, and decoding continues until
`--tg` tokens. It does not mask EOS or draw a replacement. Both AR and MTP use
the shared core policy; vision and reactive probes refuse this flag.

Without the flag, EOS ends generation normally. The server keeps that behavior.
Raw JSONL and the summary record `eos_policy: stop|ignore`; paired reports require
the same policy and interpret older records without it as `stop`. A fixed-budget
run with short output or a stop finish fails, even if its numerical calls return
success. The historical [physical 1M run](../benchmarks/models/qwen3.8-flash-next/strix-point/README.md#physical-1m-context-and-fixed-generation)
completes 1,048,448 input tokens and all 128 output tokens with its frozen
runtime. It establishes that capacity/function result, not current-runtime
recall or matched performance. The previous EOS43 failure remains unchanged.

For a long regular core run, add `--progress-ms 1000` and redirect stderr to
`results/core-progress.jsonl`. The native client reports completed prefill tokens,
cache reuse, confirmed output and consumer-observed output for every job.
No Python or additional process is needed. Intervals range from 100 to 60,000 ms;
the default `0` keeps progress disabled. The final observation is retained on
success, failure or deadline; `final_snapshot:true` does not imply successful
inference or device retirement. Inspect the result file's terminal and job data.

Progress observations are separate from benchmark samples. The interval is
recorded in result identity and must match in a paired report, since logging
can affect client wall time. Older records without the field mean disabled.
The collected physical 1M run used its frozen r10 binary without this option.
Live counters apply to newly built clients; that result cannot be retrofitted.

The optional `.161` qualification supervisor accepts `progress_interval_ms`
for regular `modern-core` campaigns, including RAM/SSD variants. Missing or
zero means disabled. It verifies the declared interval against result identity,
requires live and final observations for each warmup/measured sample, and checks
every final job's retirement, consumed output, prefill/decode counters and times
against the completed benchmark record. Metadata alone cannot pass the run.
Malformed, oversized, synthetic or regressing observations refuse qualification.
Raw stderr is retained and hash-bound; partial/in-flight prefill observations
are reported separately. This optional private supervisor uses Python; the
benchmark and its progress output remain native C and need no supervisor.

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

To qualify live prefill configuration, use `--prefill-probe live` with a physical
prompt longer than the initial chunk and a larger explicit reservation:

```sh
"$LIE_BENCH" --suite core --model "$LIE_MODEL" \
  --tokens-file tokens-8192.json --context 16384 \
  --prefill-chunk 2048 --prefill-capacity 8192 \
  --users 2 --tg 32 --warmups 0 --repetitions 1 \
  --temperature 0 --ignore-eos --kv-cache-ram-mb 0 \
  --prefill-probe live --output results/prefill-live.jsonl
```

This saves a complete greedy baseline, observes an actual in-flight prefill
call, changes the selection for a queued peer and restores the engine selection.
It verifies both jobs' immutable choices, peer output equality, borrowed-output
stability and peer progress under withheld credit. It also cancels during a
separate prefill call and checks a fresh complete output after retirement.
Failure to observe the same numerical call across the change fails the probe;
the client introduces no provider barrier or additional inference thread.

`--prefill-probe ram` instead uses `--users 1 --kv-cache-ram-mb 4096`.
`--prefill-probe ssd` uses `--users 1 --kv-cache-ram-mb 0` and an explicit new
`--kv-disk-dir`, quota and staging budget. Each cache mode runs five complete
outputs: initial cold/hot, changed cold/hot, then the initial chunk hot again.
Full-prefix reuse and identical output IDs are required, including actual SSD
reuse without RAM fallback. Choose cache policy and budgets that can retain the
whole physical prompt; the probe fails instead of accepting a partial hit.
For either cache probe, also set `--kv-cache-min-tokens 1`,
`--kv-cache-cold-max-tokens 0`, `--kv-cache-boundary-trim-tokens 0`,
`--kv-cache-boundary-align-tokens 0`, `--kv-cache-continued-interval-tokens 0`
and `--kv-cache-capture-finish off`. These existing controls isolate one full
prompt checkpoint: intermediate boundaries otherwise split a large selected
chunk, and final snapshots can evict the saved input. DS4 framing, compression
and retention utility remain enabled. Normal engine/server defaults are unchanged.
MTP can be selected with an explicit predictor and is qualified separately.

All three modes require greedy fixed output, at least 32 output tokens, one
repetition and no warmup, progress, graphs, vision or steering plan. They emit
`prefill_probe` identity and complete functional witnesses. Native reports and
the optional historical report reader refuse these files as performance input.
The optional Point supervisor uses profile `modern-core-prefill-probe` and a
separate manifest `prefill_probe: live|ram|ssd`. The supervisor forwards and
verifies the six controlled cache settings above. Local synthetic and mocked
receipts qualify client contracts only; original-weight gates remain open.

To measure the dense sampler on original weights, use a fixed seed and keep
sampling parameters identical in both builds:

```sh
"$LIE_BENCH" --model "$LIE_MODEL" --suite core \
  --prompt-file prompt.txt --context 32768 --chunk 2048 \
  --users 1 --tg 128 --warmups 1 --repetitions 3 \
  --temperature 0.8 --top-p 0.9 --top-k 0 --min-p 0.05 --seed 123 \
  --frequency-penalty 0.2 --presence-penalty 0.1 \
  --kv-cache-ram-mb 0 --output results/core-sampled.jsonl
```

The default remains greedy. Nonzero temperature requires `--seed`; each request
uses that seed independently, including warmups and concurrent users. The raw
identity and report record all seven controls, and a matched comparison refuses
different sampling settings. `--top-k` accepts 0..2147483647 and `--min-p` accepts
0..1; zero disables the corresponding filter. Missing top-k/min-p fields in
historical results mean zero; results without generation settings retain their
historical greedy defaults. These controls use the shared-core sampling API.
To request the DS4 server sampling profile explicitly, select
`--temperature 1 --top-p 1 --top-k 0 --min-p 0.05 --seed 123`.
Original-weight AR/exact-MTP qualification of the newly exposed filters is pending.

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

## Scheduled steering

Use `--suite core --dir-steering-plan FILE.json` to compare repeatable changes
during prompt processing or generation. The model must also have an admitted
`--dir-steering-file`. For a physical input file containing exactly 1,500 token
IDs, this plan changes scales before evaluation, at position 1,024 and at the
completed prompt boundary:

```sh
cat > results/steering-plan.json <<'JSON'
[
  {"position":0,"ffn":1,"attention":0},
  {"position":1024,"ffn":-1,"attention":0},
  {"position":1500,"ffn":0,"attention":0.25}
]
JSON
build/strix-halo/synapse-lie-bench --suite core \
  --model "$LIE_MODEL" --tokens-file prompt-1500.json \
  --context 4096 --tg 128 --ignore-eos --users 2 --repetitions 3 \
  --dir-steering-file /path/to/directions.f32 \
  --dir-steering-plan results/steering-plan.json \
  --output results/lie-steering.jsonl --graphs results/lie-steering
```

The JSON array contains 1–64 steps with strictly increasing integer `position`
and both finite scales in [-100,100]. Positions count retained physical prompt
and generated positions. The inference owner splits prefill and caps each row's
AR/MTP burst to reach those boundaries exactly. Past tensors, logits and sampled
corrections remain intact; scales affect future forward work. A step outside the
prepared prompt/output budget is refused. An unreached step on early EOS fails
the sample and retains its final status.

Identity records the complete canonical binary32 scale plan. Each job records
actual application positions, status and final history/scope. Reports reject
crossed/unapplied changes and require matching plans, bank identities, sampling
and the other existing comparison settings. Ordinary runs have an empty plan;
historical reports without a plan retain that meaning. Cache reuse is limited
to a compatible token prefix before the first unapplied step; mixed histories
cannot replace uniform ones. The fixed plan disallows additional live changes
and `--reactive-probe`. Host fixtures verify scheduling and accounting; numerical
GPU quality, continuation and cost still need their own qualification.

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
`conversation`, `long-context` and `long-context-recall`; use `--requests FILE` to replay a saved
corpus. The long-context generator can prepare larger inputs, but does not
extend the model's context limit. `--timeout` is the deadline in seconds for a
complete HTTP request, including response streaming; its maximum is 86,400
seconds (24 hours) in all three HTTP clients. The `http` suite defaults to 630
seconds, or 14,400 seconds (4 hours) for either long-context preset. The `http-curve`
and `http-multi` defaults remain 3,600 and 630 seconds respectively.
The frozen physical 1M run took 7,478.56 seconds, longer than the former
7,200-second client limit. Set the server's own `--request-timeout-ms` and the
campaign supervisor deadline to cover the work too; client options do not
reconfigure either deadline. See the [extended-context guide](CONTEXT.md).

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

## Terminal agent tasks: Core-19

Core-19 is the 19-task full suite from the independently pinned
[Terminal Bench Mini](https://github.com/kyuz0/terminal-bench-mini/tree/07034484346dc724d0e2c47c821fd196add1d6fb).
It measures whether a terminal agent completes tasks, including debugging,
repository recovery and configuration. It is separate from prefill/decode
throughput measurements and from the 100-task OpenThoughts-TBLite dataset.

With LIE serving one model on port 8000, run the external harness from its own
directory:

```sh
python3 terminal_bench.py run --tier full \
  --endpoint http://127.0.0.1:8000/v1 --model qwen3.8-flash-next \
  --platform strix-halo --model-name Qwen3.8-Flash-Next \
  --engine synapse-lie --backend rocm --backend-version 7.2.4 \
  --quant UD-Q4_K_XL --inference-profile ar
```

Use the actual platform, backend version, quantization and serving profile.
The default evaluates one task at a time, with up to two attempts per task;
the second runs only after failure. Each attempt retains its three-hour agent
timeout. Only a final reward of exactly `1` counts as a pass. Preserve the
19-task denominator, attempt history, transcripts and infrastructure errors;
partial progress is not a final pass rate. A quantization comparison must use
the same server revision, context, sampling, cache and evaluation settings.

Harbor 0.20.0 with Terminus-2 2.0.0 parses terminal commands from the model's
assistant text. Trajectory `tool_calls` are synthesized after that parsing;
they do not establish native OpenAI HTTP function calls. Core-19 therefore
tests agentic command/observation loops, but native `tools`, `tool_choice`,
call/result correlation, parallel calls, SSE and Responses require separate
protocol tests or an agent that actually uses those contracts.

Python belongs to this optional external evaluation harness. LIE's server,
native `synapse-lie-bench`, reports and graphs remain independent of Python.

## Long-context recall and continuation

Use a separately qualified server with the declared capacity and RoPE profile.
For a 1M-capacity server with RAM prefix caching disabled:

```sh
"$LIE_BENCH" --suite http \
  --url http://127.0.0.1:8000/v1 --model qwen3.8-flash-next \
  --preset long-context-recall --sizes 8192,131072,1048064 \
  --context-capacity 1048576 --rope-scaling yarn4 \
  --tg 128 --turns 2 --warmups 0 --repetitions 1 --corpus-seed 77 \
  --server-kv-cache off --server-label lie \
  --output results/recall.jsonl --export-requests results/recall-requests.jsonl
```

Three independently seeded bindings replace distractor rows at the beginning,
middle and end. Two-turn mode first asks for the middle binding, then asks for
the other two from the original ledger. Their answers are absent from the first
assistant reply. `--turns 1` asks for all three together. This measures synthetic
associative recall, not natural-language quality or a vendor's quality corpus.
Positions are recorded as row indices and UTF-8 byte offsets, not token offsets.

Three small 8/16/32-record requests calibrate physical input counts. They have
one-token output budgets and are not scored. Nonlinear calibration refuses the
run; use an explicitly prepared `--requests` corpus for that tokenizer.
Every first-turn sample must match its predicted physical input count. Targets
round down to complete records; actual usage is retained for every turn.
Two-turn admission reserves both output budgets and 256 tokens for continuation;
the example's largest target leaves 512 tokens within the declared 1M capacity.
The server's request deadline must cover the actual work.

Exported cases retain the exact request, positions, follow-up and one
`expected[]` oracle per turn. Replay the same file on another endpoint with
`--requests results/recall-requests.jsonl --timeout 14400`. The evaluator requires
exact string values in a flat JSON object; member order and JSON escapes may
differ. Missing, extra or duplicate keys, prose, tool calls and wrong values fail.
Oracles remain client metadata and are not sent as request fields.
For a prepared single-turn case, the metadata has this form:

```json
{"expected":[{"kind":"json-object-exact","value":{"requested-key":"known-value"}}]}
```

Each sample records `quality`; the final `quality_summary` separates measured
and warmup counts. A wrong answer preserves all remaining samples and ends with
`quality_failed`, exit 1. HTTP or workload failure ends with `failed`, exit 1.
Timing reports refuse failed quality runs. Source/client fixtures are separate
from the [original-weight recall results](../benchmarks/models/qwen3.8-flash-next/strix-point/README.md#yarn4-short-recall-control-current-r70-runtime).
The current r70 YaRN4/seed77 ladder passes both cold turns through 786K;
near-1M, other seeds and remaining profiles are still open.

The [Strix Point recall protocol](../development/protocols/LONG-CONTEXT-RECALL-GPU-PROTOCOL.md)
defines the native/YaRN ladder through 1M, three corpus seeds, memory admission
and an optional one-case GPU coordinator. It preserves failed answers and
actual exits; it adds no Python dependency to this benchmark or its graphs.

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
Single-case graphs label concurrency as C1–C8. Multi-case graphs use the
one-based case index followed by concurrency; CSV/JSON retain the full case IDs.

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
| AR single user at eight prefix depths. | Canonical `http-curve` is implemented and CPU-qualified; its new GPU campaign remains separate. Direct LIE/Gufo GPU comparisons and fresh, cache-disabled [served HTTP AR](../benchmarks/2026-10-04/strix-point/http-depth/README.md) reach near 256K on Strix Point with two measured repetitions per engine. Separate physical 1M PP/TG128 and current YaRN4/seed77 recall through near 1M are qualified in the [model/platform results](../benchmarks/models/qwen3.8-flash-next/strix-point/README.md); other recall seeds/profiles and matched long-context performance remain open. |
| AR multiple users. | Native batching and the [served 4K HTTP campaign](../benchmarks/2026-10-04/strix-point/http-multi/README.md) both compare LIE and official Gufo through C8. The HTTP campaign includes fresh sessions=C and fixed eight-session capacity. Long-context multi-client HTTP is still open. |
| MTP single and multiple users. | Direct core and the [served 4K HTTP campaign](../benchmarks/2026-10-04/strix-point/http-multi/README.md) compare AR/MTP and LIE/Gufo through C8 on prose and repetition. The cold served [long-context campaign](../benchmarks/2026-10-04/strix-point/http-depth/README.md) matches MTP and AR through near 256K at C1, with prefill, draft acceptance, decode and wall time. Long-context multi-client HTTP is still open. |
| Cold-file loading to HTTP readiness. | Still missing; `loading` measures model construction with uncontrolled OS file-cache state. |
| Peak HIP memory. | Still missing; `memory` exports provider estimates, not allocation-exact peak usage. |

The reference is Gufo's [benchmark page](https://github.com/gufo-org/gufo/blob/f783fedb9bea2ec7de941f6da4e02f4a4596b29e/docs/models/qwen3.8-flash-next/BENCHMARKS.md)
and [measurement method](https://github.com/gufo-org/gufo/blob/f783fedb9bea2ec7de941f6da4e02f4a4596b29e/docs/models/qwen3.8-flash-next/QUALITY.md#benchmark-method).
Internal correctness tests and historical implementation checks are maintained
separately in the [development documentation](../development/README.md).
