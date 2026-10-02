<!-- SPDX-License-Identifier: MIT -->
# SSD HTTP restart and reactive consumer checks

`synapse-lie-bench --suite http-ssd` exercises the shared C core through Chat
and Responses, in JSON and SSE. Python measures the external client; checkpoint
ownership, disk waits, cancellation and output credits stay in `lie_core`.
This increment changes no engine or numerical behavior.

Status, 2026-10-02: CPU fixtures and the original-weight R5 campaign pass.
R5 uses source `3b20903`: producer/restarted reader, 30 samples, three C2
cohorts, natural I/O cancellation and unread-client isolation. Actual prompt
sizes are 131123 and 8243 tokens. Checkpoints stay raw v1; this does not qualify
the later byte-plane/Zstandard codec. See [the complete R5 result](../../archive/CACHE-FEATURES-GPU.md).

## Client interface

Supply a JSON array of two to eight distinct cases, each containing exactly
`id`, `prompt` and `max_tokens` (1..4096). The first case is the disk wait probe;
the second is its longer-generating peer. Use distinct physical prefixes so
the producer does not reuse a previous case. Actual counts come from usage.

For an already admitted server on port 8000, configured with RAM off, SSD on,
two active slots, chunk2048 and an empty private store:

```sh
synapse-lie-bench --suite http-ssd \
  --url http://127.0.0.1:8000/v1 --management-url http://127.0.0.1:19880 \
  --model qwen3.8-flash-next --provider gufo-embedded-f783fedb \
  --cases cases.json --phase write --chunk 2048 --timeout 600 \
  --output write.jsonl
```

After the supervisor retires the server and starts the same executable and
configuration against the sealed store:

```sh
synapse-lie-bench --suite http-ssd \
  --url http://127.0.0.1:8000/v1 --management-url http://127.0.0.1:19880 \
  --model qwen3.8-flash-next --provider gufo-embedded-f783fedb \
  --cases cases.json --phase read --reference write.jsonl.summary.json \
  --chunk 2048 --timeout 600 --repetitions 3 \
  --overlap --slow-client --output read.jsonl --graphs read-charts
```

The client never starts/reconfigures a server or acquires hardware leases.
Outputs are exclusive new files/directories. JSONL retains failures; success
ends with `complete`, with all phase samples in `.summary.json`. Matplotlib is
optional for charts and never installed automatically. Synthetic charts say
NOT-INFERENCE. Individual requests have socket timeouts; the supervisor also
enforces a one-hour campaign deadline.

## Acceptance and metric scope

The producer completes one fresh Chat JSON request per case, waiting for each
durable write. A restarted reader matches provider/configuration, corpus,
prompt/output counts, finish and full text. It must reuse the largest eligible
chunk-aligned prefix, or the whole prompt when shorter than a chunk. Unaligned
tails execute real prefill. RAM is off so Responses' cached-token usage cannot
be mistaken for a RAM hit.

Each reader repetition executes four API variants per case, then a two-client
simultaneous cohort. No warmup is discarded. Chat validates physical PP plus
cached equals prompt, SSD reused tokens and actual executor rates. Full hits
have null PP throughput. Responses currently has usage but no `lie_timings`;
its PP/TG remain unavailable. Text equality supplements full-logit qualification.

Reports include HTTP wall, first nonempty SSE text latency, gaps between text
events and available executed PP/TG. Text events may combine model tokens:
these gaps are **not individual-token latency**. C2 output/common wall includes
submission, restoration, tail PP and generation. Executor batch intervals
overlap across rows and are not disjoint device time.

JSON/CSV and SVG/PNG expose nearest-rank p50/p95/p99, counts and observed bounds.
With three repetitions p95/p99 may equal the maximum; this gives no statistical
confidence about production tails. Startup hashing is outside request timing.
Inventory hashing warms OS file caches; no cold-SSD claim.

`--overlap` observes a generating peer, submits a disk request and requires an
SSD-pending state plus peer generation progress before I/O retires. It closes
the disk connection, requires cancellation while I/O is still pending, then
checks recovery. A missed natural window is INCONCLUSIVE, never a latency-based
inference of overlap or a successful run.

`--slow-client` holds an unread owned TCP connection with a small receive
window. It requires sustained exhausted credits and no additional decode
dispatch, peer completion while the client remains blocked, then cancellation
and idle retirement. Early EOS or completion before blocking is INCONCLUSIVE.
This probe currently requires plain HTTP.

## Leased supervisor and next device campaign

`tools/run-bench.py` adds these pairwise manifest arguments:

```text
--suite http-ssd --cases-file cases.json --context 262144 --chunk 2048
--users 2 --phase write --repetitions 3 --timeout-ms 600000
--prefix-cache-mib 0 --prefix-ssd-dir prefix-store
--prefix-ssd-quota-mib 8192 --prefix-ssd-staging-mib 4096
```

Read changes `--phase read` and optionally adds `--overlap 1 --slow-client 1`.
`benchmark_input` seals the case basename/bytes/SHA; `files` binds the server,
checker and helpers. `http_model_id` is explicit and `build_info` is the server's
masked probe. API defaults to 8000, management to 19880; both bind loopback and
are checked before model open.

The existing SSD create/reuse resource declaration requires explicit full
model/checkpoint hashing authorization. Read binds the successful original
sibling producer's result SHA, checkpoint inventory and HTTP-summary SHA. A
direct-core result cannot substitute for an HTTP producer. RAM/staging/disk,
model/binary/DSO, foreign-client and thermal admission remain enforced. The
server is the sole owned model process; clients run in a supervisor thread.
Telemetry records actual server threads/resources. Closure retires server and
checker before reporting success/releasing leases.

The next device campaign targets distinct prompts near 8K and 128K, TG128 and
a TG512 peer, greedy AR, thinking off, context262144/chunk2048/C2. Seal actual
corpus/counts before comparison. Natural overlap is a functional witness;
reactive speedup still needs a matched alternate-scheduling baseline. MTP,
vision, 256K SSD retention and 1M are outside this campaign.

Honor the owner's Strix Halo thermal observation policy: explicit CPU/GPU
observation mode, reported hardware bounds, NVMe85 C or lower, no hardware
settings changes. Preserve peaks/errors/exits. An independent observer saving
received samples locally is required for shutdown observation; remote telemetry
alone cannot establish an exact failure temperature.

## Local functional evidence

`test-ssd-http-server` links a test-only `pread` barrier. It proves peer progress
and cancellation during a held read; production binaries have no delay switch.
Two processes write/read one private store. Two reader repetitions give 20
samples and two C2 cohorts, followed by held-read cancellation, recovery and
slow-client isolation. Final counters: 23 completed, 2 cancelled, 0 failed;
zero active/queued/blocked/pending/staging and no replacement writes.

Four focused ASan/UBSan CTest suites pass: HTTP SSD, 16 core-bench checks, six
HTTP-client checks and two thermal-guard checks. The expanded reader additionally
passes through the supervisor's readiness/client path. Build/test exits are 0.
These are CPU contract checks, not model inference or GPU throughput. See the
[source-bound receipt](../../benchmarks/2026-10-02/ssd-http-cpu/receipt.json).
