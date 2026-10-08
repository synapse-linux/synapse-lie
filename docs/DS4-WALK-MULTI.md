<!-- SPDX-License-Identifier: MIT -->

# Serial prefill, reactive multi-flow decode

`--suite ds4-walk-multi` is an experimental extension of the qualified
[`ds4-walk`](DS4-WALK-BENCH.md) measurement. It uses the same exact tokenized
corpus and advancing frontier grid. At each frontier **one sequence** executes
the next prefill chunk. The prefill numerator is the number of newly appended
physical tokens, regardless of decode width.

After prefill, the benchmark captures a bounded prefix snapshot (at most
1 GiB) or selects untimed replay, closes the advancing sequence, and prepares
`--users N` identical decode sequences. Preparation and hash validation occur
outside both timed phases. The C reactive inference path dispatches the ready
sequences through the native decode batch. After decode, it restores the one
advancing sequence outside timing for the next frontier. `--execution` is
rejected for this suite: reactive scheduling is its fixed execution contract,
including at width one. Historical direct suites retain their legacy switch.

Run one width per process, for example:

```sh
synapse-lie-bench --suite ds4-walk-multi --model MODEL.gguf \
  --prompt-file promessi_sposi.txt --output c4.jsonl --users 4 \
  --sizes 2048,4096,6144,8192 --pp 2048 --prefill-chunk 2048 \
  --tg 128 --warmups 0 --context-capacity 133760 --graphs graphs-c4
```

Use separate output files for C1, C2, C4, C6 and C8. The raw JSONL records
`prefill_tokens_total`, `prefill_calls_total`, and `output_tokens` (all emitted
tokens across the decode cohort). Its phase durations use monotonic bounds.
`frontier_fork` records snapshot/replay mode, bytes, capture time, clone
preparation time and their sum; `frontier_restore` records the untimed reset.
Decoded tokens, logits hashes and the batch row counts are validated. A
single width's report shows prefill and aggregate decode throughput against
context. Different widths can be compared only when the physical corpus IDs,
frontiers, chunk, context capacity and TG limit match.

This is **not** a simultaneous prefill/decode serving throughput measurement:
fork preparation is deliberately excluded from both rates and reported
separately. It isolates whether reactive batching improves decode at a fixed
prefix. A production scheduler still needs its own end-to-end concurrency and
responsiveness tests. C1 in this new suite uses the reactive path, so it is a
separate control from historical serial `ds4-walk` C1.

The implementation is the tracked [patch](../experiments/ds4-walk-multi.patch)
over the byte-verified [DS4 walk source](../config/ds4-walk-bench-source.json),
with a [new capsule manifest](../config/ds4-walk-multi-source.json) and
[reproducer](../tools/prepare-ds4-walk-multi.py). The original qualified
capsule and its `.157` GPU evidence remain unchanged. Focused synthetic CTests
pass in Debug and ASan/UBSan for C1/C2/C4, snapshot and replay, exact timed
prefill calls, batch counters and reports. Synthetic fixtures provide no
original-weight performance result. A real `.157` GPU curve needs the
[coordinated lease protocol](COORDINATION.md), a new build and its own
numerical/performance evidence.

The [CPU test record](../config/ds4-walk-multi-cpu-tests.json) retains actual
exit codes, including the first development error and ten pre-existing legacy
direct-suite test failures. Those deprecated-suite tests omit the prompt
source now required by their CLI. The same ten failures reproduce with the
unchanged parent capsule; the focused walk tests pass.
