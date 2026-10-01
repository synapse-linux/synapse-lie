# Simplified Gufo-style benchmark and comparison

The user selected the official [benchmarks](https://github.com/gufo-org/gufo/blob/main/docs/models/qwen3.8-flash-next/BENCHMARKS.md)
and [method](https://github.com/gufo-org/gufo/blob/main/docs/models/qwen3.8-flash-next/QUALITY.md#benchmark-method)
on 2026-10-01. These main-branch documents are reference descriptions; LIE keeps
its independently fetched runtime pin f783fedb unchanged. Current main includes
later quality updates, not code automatically incorporated into LIE.

Measured results and comparison graphs: [BENCHMARK-RESULTS.md](BENCHMARK-RESULTS.md).

## Reusable executable

`synapse-lie-bench` is C17 and uses the LIE executor ABI. It reports JSONL with
physical inputs/hashes, reused/new token counts, completed intervals, actual EOS,
output IDs, full-frontier hashes, loading/size estimates and every warm-up/sample.
`--help` and `--build-info` open no model. An opt-in HIP runtime build provides
the production binary; the separately named CPU fixture is NOT-INFERENCE.

Defaults: AR, greedy, thinking/MTP/vision off, pp2048/tg128, one warm-up and one
measured sample per point. Increase `--repetitions` to retain variation.

```sh
synapse-lie-bench --model FIRST-SHARD --output single.jsonl --suite single
synapse-lie-bench --model FIRST-SHARD --output multi.jsonl --suite multi
synapse-lie-bench --model FIRST-SHARD --output memory.jsonl --suite memory
synapse-lie-bench --model FIRST-SHARD --output loading.jsonl --suite loading
```

On shared .157 these invocations are children of `tools/run-bench.py`, using a
fresh operator-authorized manifest and all four leases; do not run them outside
the coordinated ownership protocol. This is not a persistent lease or deployment.

- `single`: depths 0/4096/8192/12288/16384/32768/65536/131072, capacity 133760.
  A fresh session processes exactly the requested physical prefix outside PP;
  the timed interval processes about 2048 **new** tokens at that depth. Physical
  total is calibrated within 32 tokens; actual counts always replace nominal
  counts in rates. This measures occupied 128K, not just allocated capacity.
- `multi`: users 1/2/4/6/8, capacity 4096, the same homogeneous prose prompt as
  single d0. All sessions finish prefill before TG starts. LIE serially interleaves
  one-token completed calls; common-window throughput sums confirmed tokens.
  This is direct executor concurrency, not the HTTP worker admission capacity.
- `memory`: capacity 133121, d0/pp2048 and d16384/pp4096, tg128. Reported model/
  session byte fields are upstream size estimates, **not measured peak HIP**.
  The lease supervisor separately retains sampled system/device counters.
- `loading`: AR model load at capacity 262144, under the existing OS cache.
  This is neither cold-file load nor HTTP readiness nor MTP-sidecar loading.

`--depths`, `--users`, `--pp`, `--tg`, `--warmups`, `--repetitions` select smaller
or repeated workloads. Output creation is exclusive; a preexisting file is never
replaced. EOS is honored and short outputs remain evidence with full-budget=false.
They are not nominal tg128 measurements. Interrupts retire only owned sequences.

## Graphs and exports

```sh
synapse-lie-bench --model FIRST-SHARD --output single.jsonl --graphs charts
python3 synapse-lie-bench-report.py single.jsonl --output charts \
  --compare gufo-single.jsonl --reference-label Gufo
```

`--graphs` launches the adjacent Python helper after model retirement; `--compare`
adds a second JSONL result. Existing results can be replotted without opening a
model/GPU. Matplotlib is optional for benchmarking, required for SVG/PNG export;
no automatic installation. CSV/JSON summaries retain medians, min/max and every
measured value. CLI exit 3 indicates graph export failed while benchmark JSONL
is preserved; malformed arguments exit 2, inference/accounting failure exit 1.

Comparison refuses unmatched capacities, physical input hashes, suite/output
budgets and fixture/inference mixtures. Ratios are eligible only with matching
output IDs and full budgets; PP/TG frontier hash equality is recorded separately.
Warm-ups are excluded, no outlier removal, incomplete failures are not averaged.
Loading/estimates are labeled separately from throughput and sampled memory.

## Simplifications and unavailable sections

This retains a live **physical prefix in the same session**, not Gufo HTTPs
multi-turn 8-token preparation and RAM/disk snapshot restoration. The independently
written deterministic project-note paragraphs/prose instruction are shared across
arms, not Gufo exact historical prompt bytes. Accordingly published Gufo/llama.cpp
numbers are historical reference, not a matched numerical gain comparison.
No LIE cache/snapshot implementation is claimed by the benchmark.

The benchmark-only `synapse-lie-bench-gufo-reference` links unchanged LIE-owned
upstream archives and invokes direct `Sync`/`DecodeStep`/`DecodeBatch`. It isolates
adapter/interleaving versus native batch behavior, **not independent numerical
engines or the full Gufo HTTP server**. Identical-input peers, finite frontiers
and exact within-point warm-up repeatability must hold. Cross-arm physical/output
IDs and frontier hashes are checked in the report. No tolerance changes on failure.

MTP, mixed/repetitive MTP maxima, cold cache eviction and allocation-exact peak
tracking are unavailable in LIE and explicitly not replicated. This tool is not
QUALITY.md independent FP64/operator or broad model-quality qualification.
LIE HTTP still has a 32K capacity limit and no prefix cache; direct 128K success
must not be presented as HTTP 128K/cache support.

## Admitted measurement protocol

Original UD-Q4_K_XL, context/chunk/output/mode exactly as above; single LIE and
single direct Gufo use identical depth lists, then multi LIE and multi Gufo use
identical users/prompts. Each arm owns a fresh four-lock nonblocking admission,
model stat/DSO/binary preflight, private HOME/cache, observed GPU-client watch,
start/end registration, 3600-second deadline, and owned cleanup. No weight hash,
conversion, package installation, tuning, foreign termination or DS4 artifacts.

An earlier fresh-full-prefill 8K-to-128K draft and its CPU fixture checks were
superseded before any GPU launch when the user selected the actual Gufo method.
Failures/CPU receipts remain in evidence/context-*; they do not qualify this new
suffix-prefill protocol. Fresh debug and sanitizer validation precedes GPU runs.
