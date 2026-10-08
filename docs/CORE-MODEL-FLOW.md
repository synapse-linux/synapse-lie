<!-- SPDX-License-Identifier: MIT -->

# Model-owned serial prefill and reactive decode

This page preserves the historical Q2 capsule, its distinct CLI and measured
binary. Its preparation helpers and retained archives are outside the normal
LIE build. Use the [current benchmark guide](guides/BENCHMARKS.md) for current
commands. These results do not qualify the new provider composition.

The legacy direct `--suite multi` creates a sequence for each user and loops
through their prefill calls inside the benchmark. It then invokes the reactive
decode dispatcher. That measures the direct executor with benchmark-controlled
prefill ordering. The default `ds4-walk` is a separate C1 advancing-prefix
test. The withdrawn `ds4-walk-multi` prototype cloned one prefix outside the
timers; it did not represent several real requests and must not be used as a
multi-user performance result.

For real concurrent requests, use `--suite core`. The benchmark only submits
N jobs. LIE's C17 model owner executes one prefill call at a time in
`src/worker.c`; the HIP adapter calls the model's `Session::Sync` for each
sequence. When jobs are ready, the C reactive inference dispatcher sends them
to the model's native `DecodeBatch`. This is the same inference core used by
HTTP, independent of the HTTP transport. Prefill and decode do not overlap on
the device owner thread.

The core result records each job's executed prompt tokens and duration, plus
model-owner counters and two physical throughput rates:

- `prefill_executor_tps` = sum of physically executed prefill tokens divided
  by the model owner's sum of completed prefill-call durations. It excludes
  queue, cache and client time. With cache disabled, an N-user cohort processes
  N complete prompts serially.
- `decode_executor_tps` = all confirmed output tokens divided by the model
  owner's sum of native decode-dispatch durations. Each batch is timed once;
  overlapping per-job decode durations are never added.

`output_per_total_wall_tps` separately includes admission, serial prefill,
decode, rendering and client consumption. The report checks model-owner call
counts against the sum of job prefill calls, validates both rates, and plots
model prefill and native decode when those counters are present. The old core
record format stays readable and retains its old graph labels.

For the requested `.157` Q2 diagnostic, export exact physical 2K/4K/6K/8K
token prefixes from the completed Promessi walk with
[`prepare-core-model-flow-inputs.py`](../tools/prepare-core-model-flow-inputs.py).
Run one core process per context and width C1/C2/C4/C6/C8, with context
capacity 133760, chunk 2048, TG128, greedy AR, cache off and no warmup. For
example:

```sh
synapse-lie-bench --suite core --model MODEL.gguf \
  --tokens-file tokens-8192.json --output c4-8192.jsonl \
  --context 133760 --chunk 2048 --users 4 --tg 128 \
  --warmups 0 --repetitions 1 --kv-cache-ram-mb 0 \
  --kv-cache-policy legacy --graphs graphs-c4-8192
```

The [completed 20-point matrix](Q2-CORE-MULTI-2K8K.md) records the executor
and whole-cohort rates. It also exposes a C1 versus C2+ continuation
divergence; batch output parity needs separate numerical qualification.

This is a full-prompt multi-request workload and has a different prefill
numerator from the 2K incremental `ds4-walk` C1 curve. Its C1 arm is an
internal baseline for the multi-user matrix. The source is the tracked
[patch](../experiments/core-model-flow.patch) over the byte-verified
[DS4-walk parent](../config/ds4-walk-bench-source.json), with a separate
[manifest](../config/core-model-flow-source.json). The parent capsule and
qualified GPU evidence are unchanged. CPU fixture tests C1/C2/C4/C8 check
non-overlapping model prefill calls, native batch counts, raw physical tokens,
timing, rejected corrupt counters and graphs in Debug and ASan/UBSan. They do
not measure original-weight performance.
