<!-- SPDX-License-Identifier: MIT -->
# Qwen3.8 Flash Next on AMD Strix Point

[Model platforms](../README.md) · [Benchmark index](../../../README.md)

Original Unsloth UD-Q4_K_XL weights, four verified shards, run on
`pop@192.168.5.161` with Radeon 890M (`gfx1150`). The current ROCm 10
campaign uses Pop!_OS kernel `7.1.5-76070105-generic`, a pinned Fedora 43
image through Docker-managed Distrobox. The initial AR baselines below use the
older Point runtime. The later [modern MTP section](#modern-c17-core-mtp-vs-ar-on-the-gpu)
uses the newly built C17 core on the same GPU. Each completed campaign used a fresh
private lease, retained the exact raw files and restored the authorized
`llama-router.service` afterwards.

| Direct benchmark | LIE prefill | LIE decode | Same-stack Gufo decode | Scope |
| --- | ---: | ---: | ---: | --- |
| Occupied prefix 0, C1 | 479.936 tok/s | 10.433 tok/s | — | PP2048/TG128, one measured sample |
| Occupied prefix 128K, C1 | 357.117 tok/s | 9.227 tok/s | — | PP2048/TG128, one measured sample |
| Parallel C1 | 479.881 tok/s | 10.440 tok/s | 10.417 tok/s | PP2048/TG128, median of three |
| Parallel C8 | 474.092 tok/s | 32.837 aggregate tok/s | 32.872 aggregate tok/s | PP2048/TG128, median of three |

The [eight-depth single-session report](../../../2026-10-02/strix-point/rocm10-distrobox-single/README.md)
contains every 0–128K value, prefill/decode graphs, telemetry, raw JSONL and
reproduction commands. The [three-arm multi-session report](../../../2026-10-02/strix-point/rocm10-distrobox-multi/README.md)
contains LIE reactive, direct Gufo and LIE serial results at C1/2/4/6/8,
including every prefill/decode median, min/max, GPU batch counter and graph.
LIE and Gufo within ROCm 10 produce identical physical prompts, output IDs
and full prefill/decode frontiers in the three-arm campaign. Earlier ROCm 7.2
frontiers differ at every point, so the cross-stack rates are observations
across changed kernel/runtime/container configurations, not a controlled
quality-equivalent comparison.

## Fresh full-prompt prefill through 128K

The paired `fresh-128k` runs each begin with an empty sequence, reserve 262,144
tokens, process the entire listed physical prompt and generate 128 tokens.
There are two measured samples per size and no warmup. All **10 LIE/Gufo pairs**
have identical physical input IDs, output IDs and full prefill/decode-logit
hashes. Rates below are independent medians; prefill wait includes the full
new prompt and does not use a retained KV prefix.

| Physical prompt | LIE PP | Gufo PP | LIE PP seconds | Gufo PP seconds | LIE TG | Gufo TG |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,500 | 462.491 | 460.139 | 3.243 | 3.260 | 10.559 | 10.556 |
| 8,000 | 456.756 | 454.846 | 17.515 | 17.588 | 10.405 | 10.394 |
| 8,192 | 455.188 | 453.611 | 17.997 | 18.060 | 10.410 | 10.402 |
| 32,768 | 429.730 | 429.114 | 76.252 | 76.362 | 10.342 | 10.337 |
| 131,072 | 401.949 | 402.066 | 326.091 | 325.996 | 10.061 | 10.062 |

![ROCm 10 Strix Point fresh-prompt prefill and decode](charts/rocm10-fresh128.svg)

The native C17 reporter produced the
[complete median/min/max and duration CSV](charts/rocm10-fresh128.csv),
[comparison JSON](charts/rocm10-fresh128-summary.json),
[zero-axis PNG](charts/rocm10-fresh128.png) and SVG above. Exact LIE/Gufo
differences are in the table and CSV; the zero-axis graph shows their shared
context trend. The [collection and thermal receipt](charts/rocm10-fresh128-collection.json)
and original
[LIE](data/rocm10-fresh128-lie.tar.gz) and
[Gufo](data/rocm10-fresh128-gufo.tar.gz) campaign bundles are included.
The bundles retain every measurement row, supervisor/child exit, model-stat
and service/lease record, telemetry and source runner. Fresh collection
verified 21/21 remote files by SHA-256 in each arm; the portable bundles omit
transient container home/cache files. Sampled maxima were CPU/GPU/NVMe
82.375/85/65.85 C for LIE and 83/86/71.85 C for Gufo, below the authorized
100 C ceiling and lower sensor limits. Reproduce the verified comparison and
plots offline with the C17 benchmark, from a repository root with a new run
directory:

```sh
cmake -S . -B build/point-report -G Ninja -DBUILD_TESTING=OFF
cmake --build build/point-report --target synapse-lie-bench -j2
sha256sum -c docs/benchmarks/models/qwen3.8-flash-next/strix-point/data/archives.sha256
mkdir -p run/point-rocm10-fresh128/lie run/point-rocm10-fresh128/gufo
tar -xzf docs/benchmarks/models/qwen3.8-flash-next/strix-point/data/rocm10-fresh128-lie.tar.gz \
  -C run/point-rocm10-fresh128/lie measurements.jsonl
tar -xzf docs/benchmarks/models/qwen3.8-flash-next/strix-point/data/rocm10-fresh128-gufo.tar.gz \
  -C run/point-rocm10-fresh128/gufo measurements.jsonl
build/point-report/synapse-lie-bench --suite report \
  run/point-rocm10-fresh128/lie/measurements.jsonl \
  --compare run/point-rocm10-fresh128/gufo/measurements.jsonl \
  --label 'LIE ROCm10' --reference-label 'Gufo ROCm10' \
  --output run/point-rocm10-fresh128/report
```

The native reporter validates complete physical IDs, sample counts, output
budgets, rates and pairwise numerical frontiers before writing CSV/JSON/SVG/PNG.
The frozen collection receipt additionally records service/lease closure and
the 21/21 remote-file hash checks made before publication; portable archives
omit transient container cache files.

## Fresh full-prompt prefill near 256K

The separate paired run starts with an empty sequence, processes **258,794**
physical input tokens with context capacity 262,144, then generates the full
128-token output. Each path has two measured samples and no warmup. Both
LIE/Gufo pairs have identical physical input IDs, output IDs and full
prefill/decode-logit hashes. These direct-executor results use the same older
ROCm 10 runtime as the 128K table above; MTP is not enabled.

| Engine | Prefill median (min–max) tok/s | Prefill median (min–max) s | Decode median (min–max) tok/s | Decode median (min–max) s |
| --- | ---: | ---: | ---: | ---: |
| LIE | 382.855 (382.503–383.206) | 675.960 (675.340–676.580) | 9.733 (9.732–9.734) | 13.151 (13.150–13.152) |
| Gufo | 380.717 (380.582–380.851) | 679.755 (679.515–679.995) | 9.715 (9.709–9.721) | 13.175 (13.167–13.183) |

![ROCm 10 Strix Point near-256K fresh-prompt prefill and decode](charts/rocm10-fresh256.svg)

The [complete native CSV](charts/rocm10-fresh256.csv),
[comparison JSON](charts/rocm10-fresh256-summary.json),
[PNG](charts/rocm10-fresh256.png),
[collection and thermal receipt](charts/rocm10-fresh256-collection.json), and
original [LIE](data/rocm10-fresh256-lie.tar.gz) and
[Gufo](data/rocm10-fresh256-gufo.tar.gz) bundles retain the exact measurements
and commands. All 21 remote files in each arm match the collected SHA-256
inventory. Both child/supervisor exits are zero, the four target shard stat
identities stay unchanged, and the named service and private lease are
restored/released. Sampled CPU/GPU/NVMe maxima were 83.125/86/70.85 C for
LIE and 82.375/86/70.85 C for Gufo. Reproduce the report offline with the
native C17 reporter:

```sh
sha256sum -c docs/benchmarks/models/qwen3.8-flash-next/strix-point/data/archives.sha256
mkdir -p run/point-rocm10-fresh256/lie run/point-rocm10-fresh256/gufo
tar -xzf docs/benchmarks/models/qwen3.8-flash-next/strix-point/data/rocm10-fresh256-lie.tar.gz \
  -C run/point-rocm10-fresh256/lie measurements.jsonl
tar -xzf docs/benchmarks/models/qwen3.8-flash-next/strix-point/data/rocm10-fresh256-gufo.tar.gz \
  -C run/point-rocm10-fresh256/gufo measurements.jsonl
build/point-report/synapse-lie-bench --suite report \
  run/point-rocm10-fresh256/lie/measurements.jsonl \
  --compare run/point-rocm10-fresh256/gufo/measurements.jsonl \
  --label 'LIE ROCm10' --reference-label 'Gufo ROCm10' \
  --output run/point-rocm10-fresh256/report
```

The pre-integration binary at source checkpoint `1877b03` has no newly added
prefill/decode phase clocks. The two samples per point show observed variation,
not a broad confidence interval or a new-runtime speed claim.

## Modern C17 core MTP vs AR on the GPU

The `rocm10-point-modern-r3` build uses LIE source `9b109998`, Gufo pin
`f783fedb` inside the explicit adapter, `gfx1150`, the same pinned Fedora 43
ROCm 10 image and original UD model as above, plus the copied Q8 MTP predictor.
The source/build and predictor identities are in the
[collection receipt](charts/rocm10-modern-mtp-collection.json). LZ4 has been
removed from the active checkpoint codec and build dependencies. The new ELF
requires `libzstd.so.1`, with no `liblz4` dependency; matching Zstandard 1.5.7
headers and their BSD license were sealed into the build capsule because the
runtime image contains the library but no development headers. Compression is
enabled in this build, though each measurement below disables retained RAM and
SSD KV caching and therefore does not measure checkpoint compression.

All four **matched original-weight GPU pairs** have the same physical prompt
IDs, complete output budgets and exact output token IDs across MTP and AR.
Greedy sampling, 2,048-token prefill chunks, one measured repetition and zero
warmups are identical within each pair. These are direct C-core measurements,
not HTTP or Pi-agent timings. Prefill and decode rates below use the executor
phase clocks; the final column uses all generated tokens divided by the
complete shared client wall, including prefill. For C2 the phase rates are
medians of two jobs, while wall throughput is the aggregate for both clients.

| Prompt / clients / output | Prefill AR → MTP, tok/s (s) | Decode AR → MTP, tok/s (s) | Complete wall AR → MTP, tok/s (s) | MTP accepted / drafted |
| --- | ---: | ---: | ---: | ---: |
| 1,500 / C1 / 32 | 461.752 (3.248) → 453.148 (3.310) | 10.517 (3.043) → 10.959 (2.920) | 5.072 (6.309) → 5.119 (6.252) | 12 / 31 |
| 8,192 / C1 / 128 | 459.693 (17.821) → 453.229 (18.075) | 10.388 (12.321) → 13.656 (9.373) | 4.241 (30.179) → 4.656 (27.492) | 70 / 115 |
| 131,072 / C1 / 128 | 401.798 (326.214) → 396.749 (330.365) | 10.042 (12.747) → 12.574 (10.180) | 0.377 (339.406) → 0.375 (341.095) | 56 / 85 |
| 8,192 / C2 / 128 each | 457.746 (17.896) → 451.039 (18.162) | 8.553 (14.965) → 9.714 (13.177) | 5.037 (50.827) → 5.164 (49.578) | 106 / 178 |

![Modern Strix Point MTP versus AR at 8K/C1: prefill, complete-wall throughput and decode](charts/rocm10-modern-mtp8192/benchmark.svg)

At 128K, MTP improves decode by 25.2% in the measured sample, but the much
longer prefill dominates total time: complete-wall throughput is 0.5% lower.
At 8K/C1, decode improves by 31.4% and complete-wall throughput by 9.8%; at
8K/C2, aggregate complete-wall throughput improves by 2.5%. Both C2 paths use
GPU decode batching: MTP records 75 batches/150 rows, AR 128 batches/256 rows.
One repetition per arm does not establish a stable speedup or a confidence
interval. The new AR output also matches the older direct-runtime baseline at
8K and 128K for all 128 output IDs, and at 1,500 for the first 32 IDs; that is
functional parity across runtimes, not a controlled timing comparison.

The native C17 reporter exports [1,500-token](charts/rocm10-modern-mtp1500/summary.csv),
[8K/C1](charts/rocm10-modern-mtp8192/summary.csv),
[128K/C1](charts/rocm10-modern-mtp131072/summary.csv) and
[8K/C2](charts/rocm10-modern-mtp8192-c2/summary.csv) complete CSVs, alongside
JSON summaries and SVG/PNG plots in each corresponding chart directory. The
[1,500-token](charts/rocm10-modern-mtp1500/benchmark.svg),
[128K/C1](charts/rocm10-modern-mtp131072/benchmark.svg) and
[8K/C2](charts/rocm10-modern-mtp8192-c2/benchmark.svg) plots use the same
zero-axis scales per metric. Each
summary validates input identity, full output budget and token parity before
computing the comparison. The
[raw campaign and build bundle](data/rocm10-modern-mtp-r3.tar.gz) preserves
all eight successful run receipts, the first failed AR supervisor attempt,
telemetry, model-stat checks, compile logs and the remote SHA-256 inventories;
transient Distrobox home/cache files are omitted from the portable archive.
Fresh local collection verified every remote file before packaging. The first
AR attempt had a completed inference child (exit 0) but supervisor exit 1
because KFD briefly retained its already-exited owned PID; the bounded
retirement correction passes dedicated CPU fixtures and the fresh AR rerun.
All eight qualified runs have child/supervisor exit 0, unchanged model and
predictor stat identities, restored service and released private lease. Final
postflight found only `llama-router.service` PID 96285 in KFD, no LIE container
and the private lease free. The highest observed CPU/GPU/NVMe readings across
these runs are 81.375/86/75.85 C, with CPU guarded at 98 C, NVMe at 85 C or
its lower hardware bound, and GPU observation only.

Reproduce an 8K comparison and its prefill/decode CSV and graphs offline from
the repository root, without model weights or GPU access:

```sh
sha256sum -c docs/benchmarks/models/qwen3.8-flash-next/strix-point/data/archives.sha256
mkdir -p run/point-modern-mtp-replay-r3
tar -xzf docs/benchmarks/models/qwen3.8-flash-next/strix-point/data/rocm10-modern-mtp-r3.tar.gz \
  -C run/point-modern-mtp-replay-r3
cmake -S . -B build/point-report -G Ninja -DBUILD_TESTING=OFF
cmake --build build/point-report --target synapse-lie-bench -j2
build/point-report/synapse-lie-bench --suite report \
  run/point-modern-mtp-replay-r3/evidence/point-modern-r3-mtp-p8192-c1-r1/measurements.jsonl \
  --compare run/point-modern-mtp-replay-r3/evidence/point-modern-r3-ar-p8192-c1-r1/measurements.jsonl \
  --label 'LIE MTP' --reference-label 'LIE AR' \
  --output run/point-modern-mtp-replay-r3/report-8192
```

### RAM and opt-in SSD KV reuse with MTP

Four additional original-weight `gfx1150` runs compare MTP and AR at an
8,192-token physical prompt and 32 generated tokens, separately with a 4 GiB
RAM cache and an explicitly enabled SSD cache (4 GiB quota, 512 MiB staging,
zero retained RAM budget). Each run has one cold warmup followed by one hot
measured request. The hot request restores all 8,192 tokens and performs zero
prefill calls. RAM records one RAM hit; SSD records one SSD hit, 8,192
SSD-cached tokens and zero SSD errors. All eight cold/hot requests have the
same physical input and 32 output token IDs. The predictor drafts 33 and
accepts 18 tokens per MTP request. Default SSD caching remains disabled.

| Hot cache / path | Reused tokens | Prefill | Decode tok/s | Complete-wall tok/s |
| --- | ---: | ---: | ---: | ---: |
| RAM / AR | 8,192 | 0 | 10.407 | 10.254 |
| RAM / MTP | 8,192 | 0 | 13.272 | 12.983 |
| SSD / AR | 8,192 | 0 | 10.380 | 8.306 |
| SSD / MTP | 8,192 | 0 | 13.222 | 9.939 |

These are functional cache gates with one measured request per arm, not a
statistical performance claim. The SSD read and checkpoint write remain in
complete-wall time; the archived SSD KV metadata reports 1,068,054,635 bytes
for AR and 1,128,102,871 bytes for MTP. The payload files remain on `.161` and
are excluded from the portable [raw evidence archive](data/rocm10-modern-mtp-cache-r3.tar.gz).
The [collection receipt](charts/rocm10-modern-mtp-cache-collection.json)
binds source, binary, remote SHA-256 checks (62/62 files), exact identities,
cache counters, temperatures and lease/service closure. The [RAM CSV](charts/rocm10-modern-mtp-ram8192/summary.csv)
and [SSD CSV](charts/rocm10-modern-mtp-ssd8192/summary.csv) contain full
prefill, decode, cache and wall values; the [RAM graph](charts/rocm10-modern-mtp-ram8192/benchmark.svg)
and [SSD graph](charts/rocm10-modern-mtp-ssd8192/benchmark.svg) have PNG and
JSON counterparts. Across these four runs, sampled CPU/GPU/NVMe peaks were
71.25/72/71.85 C. Every child and supervisor exited 0, model and predictor
stat identities remained unchanged, and the named service and private lease
were restored and released. Final postflight found only the restored router
PID 101236 in KFD, no LIE container and the private lease free.

Replay the two comparisons with the native C17 reporter:

```sh
sha256sum -c docs/benchmarks/models/qwen3.8-flash-next/strix-point/data/archives.sha256
mkdir -p run/point-modern-cache-replay-r3
tar -xzf docs/benchmarks/models/qwen3.8-flash-next/strix-point/data/rocm10-modern-mtp-cache-r3.tar.gz \
  -C run/point-modern-cache-replay-r3
for cache in ram ssd; do
  build/point-report/synapse-lie-bench --suite report \
    "run/point-modern-cache-replay-r3/evidence/point-modern-r3-mtp-${cache}-p8192-r1/measurements.jsonl" \
    --compare "run/point-modern-cache-replay-r3/evidence/point-modern-r3-ar-${cache}-p8192-r1/measurements.jsonl" \
    --label "LIE MTP ${cache^^}" --reference-label "LIE AR ${cache^^}" \
    --output "run/point-modern-cache-replay-r3/report-${cache}"
done
```

### Original-weight HTTP AR and MTP gates

Two additional `.161` windows start `synapse-lie-server` in the same supervised
ROCm 10 Distrobox, once with AR and once with the copied Q8 predictor explicitly
enabled. Both use the original UD shards, 16,384-token configured context,
fresh short requests, one private server on loopback and no retained RAM/SSD
KV cache. The server reports `synthetic=false`, `READY` and the pinned Gufo
provider in both runs; its MTP flag is false for AR and true for the predictor
run. This exercises the C HTTP/worker/flow path with real GPU inference.

| Check | AR | MTP |
| --- | --- | --- |
| `/v1/models` lists the configured model | pass | pass |
| Chat Completions JSON and SSE, same output | `4` | `4` |
| Responses JSON and SSE, same output | `4` | `4` |
| Server / Distrobox child / supervisor exit | 0 / 0 / 0 | 0 / 0 / 0 |

The [collection receipt](charts/rocm10-modern-http-collection.json) records
the binary and helper identities, API checks, backend mode, thermal peaks,
34/34 collected remote-file SHA-256 checks and lease/service closure. The
[portable raw archive](data/rocm10-modern-http-r3.tar.gz) contains every
request/response, server and supervisor log, telemetry and original manifest;
transient container home/cache files are omitted. Sampled CPU/GPU/NVMe peaks
were 63.375/54/66.85 C across the two windows. Final postflight found only
the restored router PID 103651 in KFD, no LIE container and the private lease
free. Recheck the archive from the repository root:

```sh
sha256sum -c docs/benchmarks/models/qwen3.8-flash-next/strix-point/data/archives.sha256
mkdir -p run/point-modern-http-replay-r3
tar -xzf docs/benchmarks/models/qwen3.8-flash-next/strix-point/data/rocm10-modern-http-r3.tar.gz \
  -C run/point-modern-http-replay-r3
for mode in ar mtp; do
  (cd "run/point-modern-http-replay-r3/point-modern-r3-${mode}-http-r1" && \
   sha256sum -c remote.sha256)
done
```

These short loopback requests establish functional serving for the tested
paths. External Pi-agent connectivity, tool-call generation, 128K/256K HTTP
requests and served performance still need separate Point qualification.

### SSD KV reuse across inference processes

Two more original-weight GPU windows test **process restart**, separately for
AR and MTP. In each window a cold `synapse-lie-bench --suite core` process
prefills the same 8,192 physical tokens, writes the opt-in SSD KV state and
exits. A distinct process then opens the same private SSD directory and
generates 32 tokens. RAM KV retention is zero; SSD quota and staging are 4 GiB
and 512 MiB. The hot process restores all 8,192 tokens from SSD, records one
SSD hit and zero SSD errors, and performs no prefill. Cold/hot physical input
and output IDs match within each arm; AR and MTP output IDs also match each
other. MTP accepts 18 drafted tokens in both processes.

| Path | Cold prefill tokens | Hot SSD-cached tokens | Hot prefill tokens | Hot decode tok/s | Hot complete-wall tok/s |
| --- | ---: | ---: | ---: | ---: | ---: |
| AR | 8,192 | 8,192 | 0 | 10.262 | 8.226 |
| MTP | 8,192 | 8,192 | 0 | 12.550 | 9.696 |

Each row is one hot request after one cold request; these rates do not
establish a stable performance difference. The [collection receipt](charts/rocm10-modern-ssd-restart-collection.json)
links all four process exit codes, exact identity comparisons, KV file stats,
temperature and 42/42 remote-file SHA-256 checks. The
[portable raw archive](data/rocm10-modern-ssd-restart-r3.tar.gz) contains both
processes' JSONL, logs and telemetry. It excludes the SSD payloads, whose
retained sizes are 1,068,054,635 bytes for AR and 1,128,102,871 bytes for
MTP. Sampled CPU/GPU/NVMe peaks are 70.75/71/72.85 C. Both windows restore
the authorized router and release the private lease; final postflight sees
only router PID 106168 in KFD and no LIE container.

```sh
sha256sum -c docs/benchmarks/models/qwen3.8-flash-next/strix-point/data/archives.sha256
mkdir -p run/point-modern-ssd-restart-r3
tar -xzf docs/benchmarks/models/qwen3.8-flash-next/strix-point/data/rocm10-modern-ssd-restart-r3.tar.gz \
  -C run/point-modern-ssd-restart-r3
for mode in ar mtp; do
  (cd "run/point-modern-ssd-restart-r3/point-modern-r3-${mode}-ssd-restart-r1" && \
   sha256sum -c remote.sha256)
done
```

This qualifies normal cross-process persistence on `.161`. Abrupt process
failure, host reboot and SSD eviction remain separate tests.

The [full Strix Point report](../../../../STRIX-POINT-RESULT.md) and
[direct benchmark report](../../../../STRIX-POINT-BENCHMARK-RESULT.md)
cover the earlier ROCm 7.2 fresh physical prompts through 258,794 tokens,
capacity, cache reuse, resources and failures. Modern ROCm 10 served HTTP
multi-client measurements remain pending.
Neither the direct C8 result nor the synthetic HTTP fixtures establish Pi
agent throughput. The old runtime has no newly added benchmark phase clocks;
new-runtime performance must be measured separately.
