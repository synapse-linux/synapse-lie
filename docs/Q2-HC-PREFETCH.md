<!-- SPDX-License-Identifier: MIT -->
# Original-F16 HC down prefetch

This independent decode experiment is prepared; **GPU correctness and speed
remain unmeasured**. It derives from the measured packed checkpoint, without
the separately prepared HC up/mix fusion. Latest measured C1 pp2048/tg128
remains Q2 1250.45 PP/22.97 TG versus fresh UD 1685.15/24.32. Parity is unmet.

## Profile and arithmetic contract

The packed profile attributes 69.603 ms to 1455 scalar HC down calls across
15 decode steps. The original F16 matrix has 320 rows and 10240 columns.
Four waves cooperate per row; each thread processes twenty groups of four
elements. Baseline assembly loads one group, waits for it, then accumulates.

The candidate retains the original F16 weights, F32 activations and accumulator,
128-thread launch, row ownership, four-wave reduction and 16-byte LDS partials.
It stages the next group in registers while computing the current group.
The fixed geometry removes the lane-varying loop mask. Dispatch remains limited
to `SmallGemm` with F16, one token, 320 output rows and 10240 input columns;
all other shapes and prefill follow the measured baseline.

The baseline compiler reassociates the source dot product into component order
3, 1, 2, 0 on one F32 accumulator. Explicit round-to-nearest FMAs preserve that
observed sequence in the candidate. Algebra alone is insufficient evidence:
the planned operator and complete-model byte comparisons must confirm it.
No weights, KV data, allocation policy, C17 core or reactive scheduling change.

## Generated-code evidence

The first version compiled but LLVM sank the next loads below the current FMAs,
removing the intended overlap. Its patch and assembly remain in `evidence/`.
A machine scheduling boundary now keeps the next activation/weight loads ahead
of the four current FMAs and scalar loop backedge. The loop still waits for the
previous loads on entry; this overlaps a bounded amount of work, not all latency.

| Version | VGPR | SGPR | Private bytes | LDS bytes |
| --- | ---: | ---: | ---: | ---: |
| Measured packed baseline | 13 | 12 | 0 | 16 |
| Initial prefetch, eliminated by compiler | 12 | 12 | 0 | 16 |
| Scheduled prefetch | 20 | 12 | 0 | 16 |

[Static receipts](../config/q2-hc-prefetch-static.json) describe compiler
resources, not runtime throughput. Device assembly and host-only fixture syntax
pass. All 1019 source files reconstruct exactly through both generator and
zero-fuzz patch application. The baseline also matches every source file in the
actual measured packed capsule; official formatting passes 486 C++ files.
[Source identity](../config/q2-hc-prefetch-source.json) records hashes and the
inventory encoding. Only one upstream translation unit changes.

The `.157` CPU capsule passes 9/9 Debug and 9/9 ASan/UBSan suites, including
six remote-guard methods covering thirteen refusal cases. All six commands exit
zero and seven artifacts are collected and hash verified. Runner/command
retirement is verified. GPU visibility is disabled and no model is accessed;
these are [host checks](../config/q2-hc-prefetch-host.json), not kernel results.

## Prepared GPU measurements

Reuse the existing eleven synthetic HC cases: ordinary, tiny and alternating
inputs for the changed scalar shape; token widths 2/3/8/9; ragged row/K controls;
HC up and router controls. Independent FP64 dot-product limits remain 0.00002
for relative RMS and error over peak. Check output guards, finite values and
all eleven complete saved F32 frontiers against a fresh packed arm.

The same fixture then rotates sixteen `hipMalloc` weight matrices, 100 MiB in
total, beyond the 32 MiB cache. One warm rotation precedes five HIP-event samples
of 128 launches. A component gain must survive unprofiled full-model timing:
one warmup plus three fresh C1 pp2048/tg128 sessions, 15 seconds idle outside
timing, full MMQ builds, exact comparison of all 21 saved buffers. Use a fresh
UD control in the same window before making a new parity claim.

Numerical mismatches and actual failure exits remain evidence. The user's
performance-first authorization permits bounded timing after memory/launch
checks; it does not convert discrepancies into false positives or permit
promotion. Earlier qualified-Q2 drift remains a separate unresolved issue.

Core retains the enclosing `.157` window. After its verified return, acquire
all four fresh leases per arm under the existing 98 C inclusive Q2 guard:

```sh
python3 tools/q2-remote.py hc-bench q2-hc-prefetch-reference-r1 --source-variant packed
python3 tools/q2-remote.py hc-bench q2-hc-prefetch-candidate-r1 --source-variant hc-prefetch
python3 tools/q2-remote.py q2-bench2k q2-hc-prefetch-model-base-r1 --source-variant packed --rebuild-mmq
python3 tools/q2-remote.py q2-bench2k q2-hc-prefetch-model-r1 --source-variant hc-prefetch --rebuild-mmq
```

No GPU job, build or automatic waiter is queued. See the
[protocol](../config/q2-hc-prefetch-protocol.json) and [coordination ledger](COORDINATION.md).
