<!-- SPDX-License-Identifier: MIT -->

# Full-prefill measurement correction

The 2026-10-07 exact-corpus curve does **not** satisfy the requested full-prefill
comparison. It times only the final chunk after an untimed prefix replay. Its
GPU calls and recorded counts are real, but the table cannot establish total
prefill performance or progress against the retained counting-prompt reference.
Its powers-of-two grid also omits requested intermediate points. Preserve the
raw records; withdraw their use as a target or optimization comparison.

The earlier HTTP chunk curves use unaligned physical counts, different input
and different output budgets. They also cannot establish the requested exact
counting-prompt comparison. Their higher rates do not prove either a kernel
improvement or a regression in the later run: the workload and timing interval
changed together. No measured attribution of that difference exists yet.

## Fixed contract for the requested replacement

- Native `synapse-lie-bench`, `fresh` suite, now the default. At prompt length
  N, start an empty sequence and time **all N tokens**, across every chunk.
  PP = N / elapsed completed-prefill time; no untimed prefix replay and no
  average of per-chunk token rates. Loading, tokenization, sequence allocation,
  logits hashing and generation are reported or handled outside the PP timer.
- Restore the original repeated `x ` counting prompt from
  `tests/q2_model.cpp::SizedPrompt`, including the model's complete chat template
  and disabled thinking. Construct exactly N physical tokens; reject a miss.
  The 2048-token input must hash to
  `75343e606f5b815fe01f69ddc6ce50a997e2de96d8a20304a82a7f24f1180b35`
  on the real backend. At the same N, the input is independent of chunk size.
  The closing counting instruction occurs at the end of each prompt; prompts
  of different lengths are not claimed to be prefixes of one token array.
- Chunk sizes 2048, 4096 and 8192; no partial calls. Default grids include
  every multiple of the selected chunk through 131072: 64, 32 and 16 points.
  Explicit smaller grids are diagnostic subsets, never a completed curve.
  Each point starts a fresh sequence; the model stays loaded between points.
  Inside a point the chunks extend the same sequence without resetting state.
  The 128K point with chunk2K therefore performs 64 consecutive prefill calls
  inside one start/end timestamp interval. This differs from the 64 independent
  prompt lengths in the complete 2K grid.
- Complete the matching UD model curve with chunk2048 as well. The earlier
  interpretation of the owner's "UD only for 2K" as a single 2048-token point
  did not cover that comparison. Scope is112 Q2 points plus64 UD points, using
  the same retained native executable and identical physical inputs at each N.
- Fix context allocation at 133760 for the curve, C1, greedy AR, MTP off,
  no prefix-cache restore. Keep IOMMU enabled and the retained numerical
  provider unchanged. Chunk size is the tested variable.
- TG requests 128 emitted tokens and times the native executor's completed
  decode calls. Incomplete output budgets remain visible and are not promoted
  as full TG128 results. The old `q2_model bench2k` emitted 128 outputs but timed
  127 forward calls; do not compare its TG directly to native TG128.
- Record executable/provider hashes, exact input IDs, allocated capacity,
  warmup count, every measured repetition and actual completed phase counts.
  The focused discrepancy check uses one warmup and three measured repetitions.
  The complete curves use the documented native default of one warmup and one
  measured repetition per point. Keep the diagnostic repetitions in their own
  files; do not mix them into this fresh full-curve campaign.
  Historical qualified binaries and reference values are preserved.

The `single` suite remains an explicitly selected incremental diagnostic.
Reports must reject a fresh sample with nonzero preceding depth, mismatched
timed token/call counts, or a comparison with a different measurement contract.
Reject `--depths` for fresh and `--sizes` for incremental rather than silently
ignoring them. Report axes use full prompt length for fresh.

```sh
synapse-lie-bench --suite fresh --model MODEL.gguf \
  --prompt-preset q2-counting --prefill-chunk 2048 \
  --context-capacity 133760 --tg 128 --warmups 1 --repetitions 1 \
  --output full-2k.jsonl --graphs full-2k-report
```

This command selects all 64 exact chunk multiples. Use 4096 or 8192 to
select the other grids and distinct output paths. It documents the eventual
curve; the current focused diagnostic explicitly passes only 2048 or 8192
through `--sizes`, with three measured repetitions. All runtime work still
requires the shared-host coordination protocol.

## What the source references actually specify

| Reference | Input | X coordinate | Timed prefill |
| --- | --- | --- | --- |
| Retained LIE `q2_model bench2k` | Exact counting chat, 2048 physical IDs | Fixed 2048-token input, allocation 9216 | Entire 2048-token input from reset |
| Gufo single AR | Seeded synthetic-paragraph chat | Already cached prefix depth, including 12288 | New approximately 2048-token turn after that prefix |
| `antirez/ds4` bench | Raw prompt file; the owner's corpus is *I promessi sposi* | Final `ctx_tokens` frontier; additive step supported | Tokens added since the previous frontier |
| Requested replacement | Exact counting chat | Entire prompt length N | All N tokens from empty sequence |

The requested full-prefill curve is deliberately explicit about this last
distinction. It must not be described as identical to Gufo's cached-depth
curve or DS4's incremental interval. Exact-count requirements and the user's
native-bench choice take precedence over upstream approximate HTTP defaults.

Reviewed references: Gufo's locally pinned
`docs/models/qwen3.8-flash-next/{README,BENCHMARKS,QUALITY}.md`,
`docs/BENCHMARKS.md`, and `.agents/skills/benchmark-model/SKILL.md`;
[DS4 bench at 0aaea5a2](https://github.com/antirez/ds4/blob/0aaea5a238fb41a35106a551e73c8409dfb751ac/ds4_bench.c).
The local Gufo source remains independently fetched under
`.deps/gufo-q2-prefill-chunks`; no sibling workspace source is imported.

## Current validation status

The correction compiles in Debug, ASan/UBSan and the GPU-linked build. Static
ELF inspection verifies all 923 device functions byte-identical to the retained
native executable; numerical kernels are not rebuilt. All four focused CTests
pass on .157 at 2026-10-08 00:18:40 UTC: 38 CLI invocations in Debug and the
same 38 under ASan/UBSan/LSan. The synthetic tests independently trace call
start/end timestamps across the 112-point default grid and check every prefill
call lies inside the reported complete interval. They also exercise raw corpus
regressions, invalid grids and tampered reports. They provide no performance
or neural-inference evidence. Receipt:
`evidence/q2-counting-bench-preparation/ctest.json`.

The [focused GPU diagnostic](Q2-COUNTING-FULL-PREFILL.md) now completes all
five arms and 20 samples with full TG128. The 2048-token input is byte-identical
to the retained reference; shared 8192-token inputs match across chunk sizes.
The large 900-versus-1400 gap is not reproduced on this counting workload:
2K-chunk full PP8192 spans 1540.27–1544.15 token/s; 4K spans1495.90–1499.86;
8K spans1438.85–1439.70. No numerical kernel changes are involved. This does
not identify the cause of the raw-corpus result or qualify a complete context
curve. The [complete campaign](Q2-COUNTING-CURVE128.md) subsequently finishes
all112 Q2 points plus64 matching UD chunk2K points, with all352 samples
validated and all176 measured points completingTG128. Physical inputs and
counting continuations match at every shared length. Plan ca98934d uses the
same retained numerical executable and the documented full-curve default of
one warmup plus one measured repetition per point. Collection and strong
closure precede the new user-authorized IOMMU-off boot transition.

Preserve the 1587.893545 historical observation on its own
2048-token contract. Do not reinterpret it as a long-context measurement or
an interchangeable native TG reference. The old harness also paused 15 seconds
between repetitions; the new focused chunk comparison uses the same no-pause
policy for all arms and does not claim a strict historical performance delta.
