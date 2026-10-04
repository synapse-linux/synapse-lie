<!-- SPDX-License-Identifier: MIT -->
# Bounded activation reuse during Q2 prefill preparation

Further inspection of the independently fetched official Gufo DeepSeek port
suggests checking which inputs remain live across producer/consumer phases.
The existing Qwen `PackQ2ScaledRowsKernel` reads each 640-column F32 row for
its maximum, then reads it again to write scaled F16 values. Its actual device
assembly contains both global-read loops; the compiler does not retain these
inputs across the barriers. This is a first-party follow-up, not copied DS4 code.

The separate [candidate generator](../tools/prepare-q2-scaled-row-reuse.py)
retains up to three values per thread, with the existing 256-thread block.
It preserves maximum reduction order, scale/inverse bits, F16 conversion,
barriers, output layout and the host's exact 640-column admission contract.
It starts from ordered Q2, without the new IQ2 scale-reuse patch. Exactly one
file changes; the other 1019 source files remain identical.
[Source inventory](../config/q2-scaled-row-reuse-source.json),
[patch](../experiments/q2-scaled-row-reuse.patch).

## Static device compilation only

Both variants compile with the same production gfx1151 flags. All 154 other
emitted function bodies remain identical. The changed kernel has:

| Metric | Reference | Candidate |
| --- | ---: | ---: |
| Static instruction lines | 157 | 168 |
| Allocated VGPR index bound | 11 | 13 |
| LDS bytes | 36 | 36 |
| Private scratch bytes | 0 | 0 |
| Global input reads per valid element, from control flow | 2 | 1 |

The unrolled candidate contains three static load sites before the reductions;
the original has two load sites in loops. Counting static sites alone would
therefore misdescribe the executed reads. Candidate conversion remains
`v_fma_mixlo_f16`, and both barriers remain. More registers and the changed
control flow can still offset the saved read. [Static receipt](../config/q2-scaled-row-reuse-static.json).

For 2048 tokens, ten experts and 640 columns, the removed second source pass
is 52,428,800 logical bytes per layer. This is an address-traffic bound, not
measured DRAM traffic or a promised throughput improvement. Prior retained
profiles put this preparation phase at 21.5–22.1 ms, about 1.46% of the GPU
prefill interval; they used the older counting workload and are not a new
canonical-prose attribution. Even removing that whole phase would not close
the complete Q2/UD gap.

## Remaining acceptance

No GPU/operator/model test has run for this candidate. It is excluded from
the admitted native four-arm IQ2-scale campaign. Before any model trial,
qualify whole buffers against the unchanged operator, including zero/sign,
subnormal, normal, extreme-finite and allocation-boundary rows; preserve any
nonfinite behavior required by the current operator contract. Measure a
complete preparation/down cycle over production-sized rotating buffers on
.157. Require numerical and lifecycle qualification independently of timing.
No default promotion, scheduling change or model performance claim follows
from this static preparation.
