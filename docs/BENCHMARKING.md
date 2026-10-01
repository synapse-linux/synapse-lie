# Benchmark direction and server prerequisites

The definitive **`synapse-lie-bench` is to be C17**, like the server. It is not
implemented yet. Python is permitted for intermediate development, supervision,
analysis and graph generation; it is not a replacement production server or
model executor. The existing `lie-executor-bench` is already C17, but implements
only the separate [fresh-session C1 baseline](C1-BASELINE.md), not the full suite
below. Previously qualified binaries and measurements are not renamed or rebuilt
in place.

Priority is server functionality and truthful measurement boundaries. The new
[per-request timings](HTTP.md#per-request-executor-timings) are implemented in C;
no kernel, adapter or executor ABI change is needed. They are a prerequisite for
HTTP benchmarking, not evidence that the whole benchmark can already run.

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
| Single AR | HTTP, greedy, thinking off, approximately 2048 **new** prompt tokens and up to 128 output tokens after cached depths 0/4096/8192/12288/16384/32768/65536/131072; recipe context 133760 | No prefix reuse; HTTP context limit 32768 and 1 MiB request limit; exact ordered corpus/calibration not reproduced |
| Single MTP | Same depth sweep; mixed and repetitive workloads; PP is the maximum per engine/depth across these workloads, including predictor catch-up | MTP not exposed |
| Multi AR/MTP | C1/2/4/6/8, context 4096 per user, all sessions prefilled before measured TG128; **sum of individual decode rates**, not cohort tokens divided by cohort wall time | At most two interleaved single-row sequences, no equivalent prefill/cache cohort protocol or native batching; MTP absent |
| Loading | Cold target/sidecar files to HTTP readiness, C1/MTP/context 262144 | No equivalent cold-load experiment; never drop global caches or alter another service implicitly |
| Memory | C1/AR/context 133121; d0 pp2048/tg128 and 16K prefix pp4096/tg128; peak **global HIP usage including idle memory** | No corresponding run or exact peak counter; sampled system GTT/RAM is a different metric |

The reference documents one warmed sample per point (recipe repetitions=1),
seed=1 and depth tolerance=0.005. Calibration depends on the ordered depth sweep;
paired controls must retain that order. Preserve actual physical prompt/cache/
output counts, EOS, all raw samples, warmups, repetition count, binary/config/
model/template identities and timing definitions. Changing the aggregation to
medians or measuring fresh 128K prefill is a different protocol and must be named
accordingly. Highest MTP PP does not authorize removing inconvenient samples.

## Implementation and acceptance boundaries

- Per-request `lie_timings` sums completed synchronous executor-call wall times.
  It excludes queue/credit stalls and other jobs' work; it is neither HTTP latency
  nor GPU-only time. No fake queue, TTFT, cache hit, MTP or memory metrics are added
  to make an external reader accept a response. A LIE-aware intermediate reader
  must recognize the schema rather than label it Gufo/llama.cpp timing.
- Prefix reuse requires correct physical-token/frontier identity, bounded state
  ownership, cancellation and invalidation. Chat history currently re-prefills
  from a fresh session. Do not label this cached-prefill measurement.
- Native concurrency, MTP and longer contexts require implementation and numerical/
  lifecycle/capacity qualification before their rows can be filled. Unsupported,
  not-run and failed are distinct from measured zero.
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
