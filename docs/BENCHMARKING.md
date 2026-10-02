# Benchmark direction and server prerequisites

The **`synapse-lie-bench` executable is C17**, like the server. A simplified
direct-executor AR implementation is now available; see
[CLI, graph exports and exact deviations](CONTEXT-COMPARISON.md).
Full-prefill and an explicit Python HTTP client mode are available, including
actual conversation replay. Cached-conversation/MTP execution below remains
incomplete; a benchmark client cannot supply absent server capabilities.
The [test closure matrix and 1M gate](TEST-COVERAGE-LONG-CONTEXT.md) distinguish
missing repetitions/protocols from missing engine features and describe the
extended-context client preset without claiming 1M LIE execution.
Python is permitted for intermediate development, supervision,
analysis and graph generation; it is not a replacement production server or
model executor. The existing `lie-executor-bench` is already C17, but implements
only the separate [fresh-session C1 baseline](C1-BASELINE.md), not the full suite
below. Previously qualified binaries and measurements are not renamed or rebuilt
in place.

Priority is server functionality and truthful measurement boundaries. The new
[per-request timings](HTTP.md#per-request-executor-timings) are implemented in C;
no kernel, adapter or executor ABI change is needed. They are a prerequisite for
HTTP benchmarking, distinct from client wall/first-output measurements.

## Antirez model requirement

Full fresh **prefill and decode** are explicitly required for the actual antirez
Q2/Q4 files. The [format-specific gate](ANTIREZ-BENCHMARKS.md) records their real
layouts and historical reader/binder/PP/TG investigation. The Q2 port is now
withdrawn; [the replacement plan](REPLAN.md) requires a working native Q2 reference
before another implementation. Current priority is native server tools with Unsloth,
not resuming the archived port.
The existing C17 executor harness measures both PP and TG, but cannot benchmark
an unsupported model; a separate HTTP lane must exercise the updated worker.
No UD-Q4_K_XL row, filename-only quantization label or historical DS4 result can
be used as an antirez LIE measurement. Blocked/not-run entries are not zero.

## Pinned reference methodology

Reference: Gufo's [Qwen3.8 Flash-Next BENCHMARKS.md](https://github.com/gufo-org/gufo/blob/fd1710b5fd090880722e0681a868df2006595c73/docs/models/qwen3.8-flash-next/BENCHMARKS.md),
[QUALITY.md](https://github.com/gufo-org/gufo/blob/fd1710b5fd090880722e0681a868df2006595c73/docs/models/qwen3.8-flash-next/QUALITY.md#benchmark-method)
and [bench.json](https://github.com/gufo-org/gufo/blob/fd1710b5fd090880722e0681a868df2006595c73/docs/models/qwen3.8-flash-next/artifacts/bench.json).
The documentation/tool revision is **`fd1710b5fd090880722e0681a868df2006595c73`**.
It does not replace the numerical provider pin `f783fedb`, nor identify all
historical binaries whose measurements the page combines. In particular the
page cites Gufo TG revision `f797b5b`, llama.cpp AR `b11069` and MTP `6fcaa16f`;
PP and other rows retain their earlier provenance.

Independent upstream downloads, HTTP status, hashes, timestamps, model identities,
methodology scripts and the upstream MIT license remain in local
`evidence/gufo-bench-method-r1/`. No upstream benchmark script was executed or
imported into the server. No sibling project code or artifacts were imported.

| Reference experiment | Meaning / required semantics | Current LIE gap |
|---|---|---|
| Single AR | HTTP, greedy, thinking off, approximately 2048 **new** prompt tokens and up to 128 output tokens after cached depths 0/4096/8192/12288/16384/32768/65536/131072; recipe context 133760 | Direct physical-prefix measurements through 128K exist; HTTP prefix caching remains absent; context now reaches 262144 with an 8 MiB request limit; exact reference corpus/calibration not reproduced |
| Single MTP | Same depth sweep; mixed and repetitive workloads; PP is the maximum per engine/depth across these workloads, including predictor catch-up | MTP not exposed |
| Multi AR/MTP | C1/2/4/6/8, context 4096 per user, all sessions prefilled before measured TG128; **sum of individual decode rates**, not cohort tokens divided by cohort wall time | Native AR batching is implemented for 1/2/4/6/8; the direct benchmark uses common-window aggregate throughput, not the reference HTTP/cache protocol or rate aggregation; MTP absent |
| Loading | Cold target/sidecar files to HTTP readiness, C1/MTP/context 262144 | No equivalent cold-load experiment; never drop global caches or alter another service implicitly |
| Memory | C1/AR/context 133121; d0 pp2048/tg128 and 16K prefix pp4096/tg128; peak **global HIP usage including idle memory** | Corresponding direct workloads report upstream size estimates and sampled system/device telemetry; allocation-exact global HIP peak remains absent |

The reference documents one warmed sample per point (recipe repetitions=1),
seed=1 and depth tolerance=0.005. Calibration depends on the ordered depth sweep;
paired controls must retain that order. Preserve actual physical prompt/cache/
output counts, EOS, all raw samples, warmups, repetition count, binary/config/
model/template identities and timing definitions. Changing the aggregation to
medians or measuring fresh 128K prefill is a different protocol and must be named
accordingly. Highest MTP PP does not authorize removing inconvenient samples.

## Implementation and acceptance boundaries

- Per-request `lie_timings` sums completed synchronous executor-call wall times.
  It excludes queue/credit stalls and HTTP delivery. A shared batch duration is
  attributed to each participating request, so these intervals overlap and must
  not be summed as GPU time. It is neither HTTP latency nor GPU-only time.
  No fake queue, TTFT, cache hit, MTP or memory metrics are added
  to make an external reader accept a response. A LIE-aware intermediate reader
  must recognize the schema rather than label it Gufo/llama.cpp timing.
- Prefix reuse requires correct physical-token/frontier identity, bounded state
  ownership, cancellation and invalidation. Chat history currently re-prefills
  from a fresh session. Do not label this cached-prefill measurement.
- Native concurrency, MTP and longer contexts require implementation and numerical/
  lifecycle/capacity qualification before their rows can be filled. The measured
  direct AR scope is in [REACTIVE-INFERENCE-RESULT.md](REACTIVE-INFERENCE-RESULT.md);
  HTTP near-256K capacity and Pi tools have their own [receipt](HTTP-256K-PI.md); MTP remains absent. Unsupported, not-run and failed remain
  distinct from measured zero.
- Separate graphs for fresh full prefill, cached-prefix incremental prefill,
  decode, concurrency, load and memory. Reference-published values and locally
  measured values must be visibly distinguished. The existing C1 dataset cannot
  be overlaid as matched HTTP depth data or used to claim a speedup.
- Q2/Q4 labels alone establish neither model identity nor end-to-end quantization
  support. Antirez Q2/Q4 remain unqualified; their matched references and gates are
  separate from the measured original UD-Q4_K_XL baseline.
- All GPU runs retain the [coordination lease](COORDINATION.md), exclusive evidence
  directories, private runtime settings and no implicit install/tuning/deployment.
  CPU fixtures, compilation and generated charts are not inference evidence.

Full-prompt and served measurements are recorded in [FULL-PREFILL-HTTP-RESULT.md](FULL-PREFILL-HTTP-RESULT.md). Their cold-context averages must not be substituted for the earlier incremental-prefix protocol.


## Direct shared core suite

`--suite core` exercises the same C engine as HTTP, including model/job lifecycle,
input preparation, reactive admission and output consumption. Unlike the older
executor diagnostic suites it does not create or schedule provider sequences.
Use exactly one of `--prompt-file` (raw UTF-8, no chat template) or `--tokens-file`
(a JSON array of nonnegative int32 physical IDs). Context defaults to 4096 and is
bounded at 262144; the prompt plus requested output must fit. `--users` is one
concurrency value from 1 through 8, not a host thread count. Generation is greedy
AR with fresh sessions and no cross-request cache, MTP or vision.

A safe fixture example in a GPU-masked `.157` CPU checkout:

```sh
# fixture-tokens.json contains [0,1,2,3]; output must not already exist.
build/debug/test-synthetic-lie-bench --suite core --model :fixture: \
  --tokens-file fixture-tokens.json --output core-fixture.jsonl \
  --context 4096 --chunk 2048 --users 4 --tg 128 \
  --warmups 1 --repetitions 3 --graphs core-fixture-charts
```

The HIP-linked `synapse-lie-bench` contains the same suite; real-model execution
needs a fresh coordinated GPU build/admission. The existing `run-bench.py`
allowlist has not yet been extended to bind core input files, so the new GPU
lane is pending. A direct command is not a substitute for the shared-machine
lease/manifest protocol. This increment's tests and plots are NOT-INFERENCE.

Each `synapse-lie.core-bench.v1` file contains identity, readiness time, complete
physical input IDs with little-endian SHA-256, per-job output IDs and timings,
per-cohort samples and an explicit complete/failed terminal. All repeated peers
must produce the same greedy output IDs. Report validation preserves EOS and
refuses missing/failed samples rather than averaging partial results.

| Measurement | Interval / aggregation |
|---|---|
| `load_to_ready_ns` | Core creation to client observation of READY; no cold-file guarantee |
| `first_token_ns` | Before that submit through client observation of the first confirmed token, nullable if none |
| `total_ns` | Before that submit through observable terminal; includes copy/preparation, queue, inference and consumption |
| `prefill_ns`, `decode_ns` | Completed executor-call wall durations per job; batch intervals overlap across jobs |
| `output_per_total_wall_tps` | All peer output tokens divided by common time from before first submit through last observable terminal; includes full prefill, not pure decode throughput |

Reports retain warmups and all raw measured values; charts show medians and
observed min/max. The prefill panel uses individual completed-call throughput;
aggregate output/total-wall and client first-token latency have their own panels.
Core comparisons require matching scope, input hash, context/chunk, users and
output limit; performance ratios additionally require equal full-budget output.
These checks do not establish model identity or independent numerical accuracy;
original-weight comparisons also require model/binary/DSO manifests and the
separate frontier/logit qualification. An executor result cannot be supplied as
a matched core result. Optional Matplotlib is used only for export, never installed
automatically. `--suite core --help` and `--build-info` open no model.
