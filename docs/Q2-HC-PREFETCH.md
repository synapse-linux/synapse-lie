<!-- SPDX-License-Identifier: MIT -->
# Original-F16 HC down prefetch

These independent HC down decode experiments are measured on `.157` and
**rejected for performance**. They derive from the measured packed checkpoint,
without HC up/mix fusion. The one-group prefetch changes the 100 MiB rotating
microbenchmark median from 47.390 to 47.601 µs per launch; the two-group
version reaches 51.153 µs. Both retain byte-exact synthetic output, but neither
improves HC down. No full-model gain is claimed. Q2/UD parity remains unmet.

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
observed sequence in the candidate. Algebra alone was insufficient evidence;
the complete synthetic buffers were compared after the GPU runs.
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
| Scheduled one-group prefetch | 20 | 12 | 0 | 16 |
| Two-group prefetch | 30 | 12 | 0 | 16 |

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

## GPU measurements and disposition

The eleven synthetic HC cases cover ordinary, tiny and alternating inputs for
the changed scalar shape; token widths 2/3/8/9; ragged row/K controls; HC up
and router controls. Independent FP64 dot-product limits remain 0.00002 for
relative RMS and error over peak. Both candidates pass all eleven cases; all
complete F32 frontiers match the fresh packed arm byte for byte.

The fixture rotates sixteen `hipMalloc` weight matrices, 100 MiB in total,
beyond the 32 MiB cache. One warm rotation precedes five HIP-event samples of
128 launches. The one-group candidate is 0.44% slower by median; the two-group
candidate is 7.35% slower. The collected
[one-group report](../config/q2-hc-prefetch-micro.json) and
[two-group report](../config/q2-hc-prefetch2-micro.json) include every sample,
FP64 check, exit, artifact hash and thermal observation. Neither negative
component result was promoted to a full-model benchmark.

The two-group source and compiler assembly remain as negative evidence. Its
CPU capsule passes 10/10 Debug and 10/10 ASan/UBSan with six zero-exit commands;
the GPU arm also exits zero. Earlier qualified-Q2 drift remains a separate
unresolved issue. The runs used fresh four-lease admission in the Q2 window
under the existing 98 C inclusive guard:

```sh
python3 tools/q2-remote.py hc-bench q2-hc-prefetch-reference-r1 --source-variant packed
python3 tools/q2-remote.py hc-bench q2-hc-prefetch-candidate-r1 --source-variant hc-prefetch
python3 tools/q2-remote.py hc-bench q2-hc-prefetch2-candidate-r1 --source-variant hc-prefetch2
```

See the [protocol](../config/q2-hc-prefetch-protocol.json),
[coordination ledger](COORDINATION.md) and separate
[scalar HC up vector experiment](Q2-HC-UP-VECTOR.md).
