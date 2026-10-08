<!-- SPDX-License-Identifier: MIT -->

# Native benchmark: DS4 walk

The default direct `synapse-lie-bench` mode follows the measurement loop in
[`antirez/ds4` `ds4_bench.c` at `0aaea5a`](https://github.com/antirez/ds4/blob/0aaea5a238fb41a35106a551e73c8409dfb751ac/ds4_bench.c).
It loads one model and tokenizes one raw-text corpus before timing. For each
walk it creates one logical sequence and advances the same token prefix by a
fixed step: 2048, 4096, 6144, 8192, and so on by default. The monotonic
prefill timer brackets only the newly appended tokens. Its numerator is the
frontier minus the previous frontier, so every default point reports 2048
prefill tokens. Greedy decode follows each frontier. Before the next step,
the benchmark restores the pre-decode frontier from a snapshot of at most
1 GiB, or replays the prefix if the snapshot is larger or unsupported. Neither
restoration path enters the prefill or decode timing window.

LIE's state API restores only into a pristine sequence. The benchmark therefore
replaces the underlying sequence handle outside the timer while preserving
the advancing logical prefix. DS4 restores its snapshot into the same session.
LIE's decode API may stop at EOS; DS4 explicitly excludes EOS when choosing a
greedy token. A run with fewer than the requested output tokens is flagged and
cannot enter the matched TG128 comparison. These backend differences remain
visible and should not be described as byte-for-byte DS4 execution.

The default is one walk with no warmup. `--warmups 1` runs an entire untimed
qualification walk before the measured walk; it does not reset the sequence
at every context point. For a fixed four-point check:

```sh
synapse-lie-bench --model MODEL.gguf --prompt-file promessi_sposi.txt \
  --output walk.jsonl --sizes 2048,4096,6144,8192 \
  --prefill-chunk 2048 --pp 2048 --tg 128 --warmups 0 --repetitions 1 \
  --context-capacity 133760 --restore snapshot-auto --graphs graphs
```

`--restore replay` forces the DS4 replay fallback for diagnostic checks. For
4K/8K steps, set both `--pp` and `--prefill-chunk` to 4096 or 8192 and use
contiguous exact sizes. The `fresh`, `single`, `multi`, `loading`, and `memory`
direct suites remain explicitly selectable as deprecated historical modes
pending review. Reports reject comparisons between their distinct timing
contracts. HTTP, core, and state suites retain their separate APIs.

The [CPU fixture](../experiments/ds4-walk-bench.patch) checks both snapshot
and replay paths, the exact append intervals, and that each actual prefill call
falls inside its reported monotonic bounds. It is synthetic and supplies no
model-performance evidence. The [source capsule](../config/ds4-walk-bench-source.json)
and [local GPU-linked binary provenance](../config/ds4-walk-bench-build.json)
record reproducible inputs and the unchanged numerical archives. The focused
four-point run is governed by [its frozen plan](../config/q2-ds4-walk-promessi-plan.json).
The previous [full-prefill table](Q2-PROMESSI-SHORT.md) starts from an empty
sequence at every point and measures all tokens; its rates answer a different
question and are kept as separate evidence.
