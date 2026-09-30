# C1 prefill/decode baseline protocol

This measures the selected LIE execution ABI with **embedded Gufo**, not an
independent owned numerical engine, HTTP throughput or a reactive speedup.
The original-weight HTTP/SSE smoke has passed. Pristine numerical comparison,
broad quality and real concurrency/cancellation qualification remain separate.
The user explicitly requested prefill/decode measurements on 2026-09-30.

## Fixed workload, defined before execution

- Original read-only Qwen3.8 Flash Next UD-Q4_K_XL shards, revision
  `38bb39ee97821de2c9009abb7e93950eec396e66`; no alternative quant or conversion.
- Gufo pin `f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, independently fetched;
  unchanged Qwen-only numerical archives from `gufo-qwen-host-r2`.
- Single model, single owner, one fresh AR session per sample, context **9216**
  for every workload, chunk **2048**, greedy, no MTP/vision/prefix reuse.
- Prompt targets 512/2048/8192 **physical** tokens. A deterministic binary search
  selects the largest repeated reference-text count not exceeding each target.
  The pinned actual chat renderer/tokenizer supplies framing and thinking-off
  semantics. Counts will generally be slightly below targets: report actual
  counts and retain complete input token vectors, never label them exact 512/2K/8K.
- Reference text is synthetic English padding. The user instruction requests
  integers 1 through 10000, one per line, to exercise up to **128 generated tokens**.
  It is not a quality workload. Text preparation/tokenization is outside timing.
- **EOS is honored** with the production `lie_sequence_decode` path. Early EOS
  is retained with its actual emitted count; no padding, ignore-EOS ABI change,
  forced-token substitute or rerun to obtain a faster/more convenient sample.
- One warmup per workload, all excluded from summaries. Then three measured
  rounds, order ascending / descending / ascending. All nine measurements retained.
  No outlier deletion, profiling, clock/power/governor changes or autotuning by LIE.

## Completed-work boundaries

`tools/executor-bench.c` is C17 and invokes the same link-selected execution ABI.
The main thread is the only device owner. No HTTP, worker/flow scheduling or text
rendering occurs in the measured loops. The linked adapter and numerical sources
remain unchanged. The harness is not selectable as a synthetic production provider.

**PP:** CLOCK_MONOTONIC interval around all cumulative-prefix prefill calls, after
fresh session creation, ending at successful completion of the final chunk.
The numerator is the entire actual fresh prompt, not a cached-prefix delta.

**TG:** one CLOCK_MONOTONIC interval around up to 128 synchronous decode calls.
Each emitted token must advance the completed frontier by exactly one. Sampling,
required GPU/host synchronization and transfers, C ABI calls and minimal loop/
frontier bookkeeping are included. This is end-to-end executor decode, **not
GPU-only kernel time**. An EOS detection call, if any, is included in that interval
but not counted as an emitted token. The first emitted token is evaluated to the
next usable frontier before the synchronous call returns; no free first token.

Model loading, session creation/destruction, prompt preparation, full-logit
copy/check/hash, output formatting, evidence writes and process shutdown are
outside both intervals. There are no additional per-kernel/device-wide barriers.
Pinned Gufo Forward already synchronizes before returning its host logits.

## Sanity gates and evidence

- Full finite vocabulary logits at completed PP and final TG frontiers.
- Exact in-memory comparison of those float arrays, output IDs, EOS outcome and
  final position against each workload's warmup. No tolerance relaxation on failure.
- Per-sample complete output IDs, timings/counts, and SHA256 of little-endian
  float32 frontier arrays. Input token vectors are retained. This is repeatability
  of one backend, **not independent numerical equivalence or model quality**.
- Mutating backend failure aborts; no retry/fallback. Partial rows and failures
  remain evidence, not a partially averaged successful result.
- Summaries report medians, min/max and every sample for each actual prompt size.
  Hardware/software identities, build flags, original stat identities, DSOs,
  process exit and whole-device/system observations accompany the result.
- One-second telemetry is not exact LIE allocation/peak accounting. Strix Halo
  GTT and RAM share physical memory. Desktop/permission-denied observations are
  retained; cooperative locks and empty KFD do not prove universal exclusivity.

## Admission and local tests

`tools/bench-model.py` requires a fresh run manifest/operator window. It acquires
all four existing leases nonblockingly in the documented order, verifies original
model stats and staged artifacts/DSOs, isolates HOME/cache/temp, records existing
power settings without modifying them, and watches for new observable GPU clients.
It retains leases through owned-child retirement and writes actual start/end
register entries. Model weights are read only by the admitted model load, never
rehash-converted or copied. A failed/occupied run directory cannot be reused.

SIGINT/SIGTERM in the C harness only latches stop; cleanup follows the synchronous
owned operation's completion. A supervisor deadline can terminate/ultimately kill
only its own child, marking failure. A successful baseline leaves no daemon.

The separate `test-synthetic-bench` checks counts, warmup/order, EOS, finite-logit
refusal, deterministic mismatch, mutating failure, invalid frontier and exclusive
output. Python summary tests refuse incomplete/inconsistent/nonfinite measurements.
These CPU fixtures are explicitly NOT-INFERENCE; their timings are not GPU evidence.
The benchmark witness hashing uses the already installed OpenSSL Crypto library;
CPU benchmark tests need its development headers too. No dependency is installed.

## Observed result — 2026-09-30 20:50–20:52 UTC

Run `t0-c1-perf-r2`, Strix Halo `.157`, original UD-Q4_K_XL. Medians and ranges
below exclude the three warmups; all nine measured samples are retained.
Every sample emitted exactly 128 tokens (no early EOS). Context/chunk were fixed
at 9216/2048; sessions were fresh, not restored prefixes.

| Actual prompt tokens | PP median tok/s | PP min–max | TG median tok/s | TG min–max |
|---:|---:|---:|---:|---:|
| 502 | 988.68 | 983.70–996.65 | 26.851 | 26.844–26.852 |
| 2042 | 1642.65 | 1642.03–1648.98 | 26.049 | 26.037–26.054 |
| 8191 | 1607.13 | 1596.16–1613.55 | 25.965 | 25.796–25.965 |

Median completed PP durations were 0.507749 / 1.243112 / 5.096658 seconds;
TG128 durations were 4.766985 / 4.913743 / 4.929760 seconds. These are direct
executor intervals, not server TTFT or total wall time including model load.
Full vocabulary frontiers were finite and byte-identical to warmup at PP/TG
boundaries; output IDs and positions also matched. This remains a **single-backend
repeatability check**, not a pristine reference or general quality test.

The benchmark child and helper exited 0. All original model stat identities and
staged artifact hashes were unchanged; KFD was empty after retirement, with no
foreign GPU client observed. The run retained all four leases through cleanup.
107 one-second samples describe whole-device/system memory, not exact allocation
peaks. Existing CPU governor was `powersave`, EPP `balance_performance`, GPU DPM
`auto`; none was changed. `pp_power_profile_mode` was unavailable (ENOENT), recorded
as null/error rather than guessed. These are the existing machine conditions,
not a tuned maximum-throughput configuration.

The first attempt, `t0-c1-perf-r1`, acquired the leases and passed DSO checks but
failed **before model launch** on that missing optional sysfs attribute, exit 1.
It is preserved. A CPU regression reproduced the error before adding explicit
unavailable telemetry; `t0-perf-power-red-r1/green-r1` and `t0-perf-cpu-r3` record
the fix. Neither workload, timing boundary nor numerical/admission oracle changed.
There was no discarded GPU timing run.

Sources: benchmark commit `cbb06fc`, supervisor correction `7f85ef8`.
Build `t0-perf-linked-r1` uses Debug first-party C/adapter code and the existing
RelWithDebInfo HIP archives; its receipt records all compiler/link commands.
Benchmark binary SHA256:
`594ef2f21281c456618ecbcd3cb877861eb65ac5b2b33327f8ba2756cd5220a2`.
Authoritative raw samples, physical/output IDs, frontier hashes, manifest,
DSOs/settings, process exits and telemetry are in
`evidence/t0-c1-perf-r2/remote-results/`; the locally recomputed `assessment.json`
matches the supervisor summary. Raw measurement SHA256 is in `result.json`.

This establishes the first **completed-work C1 baseline through the LIE ABI**.
It does not establish a reactive gain, native batching, an owned numerical engine,
HTTP throughput, a matched comparison with DS4/published Gufo, or long-context
performance. The independent comparator and real cancellation/backpressure gates
remain open.
