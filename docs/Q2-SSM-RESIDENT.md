<!-- SPDX-License-Identifier: MIT -->
# SSM resident tile composition

The next new candidate combines a 128-row SSM tile, a compact XOR transpose
and phased operand lifetimes. It derives from retained Q2 **1587.893545 PP /
25.12414406 TG**, with unchanged fixed UD **1685.777092 PP / 24.34174251 TG**.
The preceding HC-up model was only nominally +0.115811%, with overlapping
ranges, and is not added to this provider. No new model performance is claimed.

## Mechanism

The parent fused Q8 SSM projection uses BM256/BN128/BK2/WM8/WN1, 48 KiB LDS
and 220 actual VGPR (241 in the descriptor). The private resident-fence draft
uses BM128/BN128/BK2/WM4/WN2, 32 KiB LDS and 158 actual VGPR (169 descriptor),
without private scratch. The XOR transpose preserves aligned float4 access
while fitting the two-stage operand storage. A compiler scheduling fence
keeps each K16 operand phase's lifetime short.

The 40 K stages, 80 block barriers, low/high K16 update order, original Q8
weight bytes and F16 operand rounding stay unchanged. Output-row blocks double
from 64 to 128 at M16384; duplicated activation reads and altered scheduling
are real costs to measure. Compiler annotations and occupancy API limits do
not establish measured active occupancy or performance.

This is a new composition of previously explored ingredients. Row128 alone
and the older compact-LDS BK1 variant have negative evidence and are not rerun.
The latter changed the K-stage schedule; this composition keeps BK2.
Both fenced and unfenced local compiler probes are preserved; only the fenced
variant belongs to this component plan. All 164 original device bodies and
resources remain exact in the compiler probe.

## Complete component

The new fixture calls the retained production launcher as its in-process
control and the private resident wrapper as candidate. Both include projection,
interior convolution and the unchanged boundary-convolution launch. Five
shapes cover N1024/1025/1057/2048/2049 with M16384/K2560, 10240 convolution
channels and four taps. The raw-live mask is preserved: interior raw QKV stays
poisoned, boundary and non-convolved channels must be finite and written.
Inputs, weights, history and device guards must remain unchanged.

Three independent weight matrices total 133,693,440 bytes, above 32 MiB MALL.
Each timed arm has three distinct output states. Two warmups and five measured
repeats alternate arms; every actual timed destination is checked before reuse.
The primary component timer is completed monotonic wall time. Raw HIP events
and validity remain separate; zero or nonfinite events cannot become a speed
claim. Allocations, uploads, resets, checks and downloads stay outside timers.

The fixture emits 72 complete buffer comparisons, including 42 from actual
timed destinations, and 144 independent sampled FP64 formula checks. The
formula reconstructs Q8-to-F16 operands, projection dots, history, convolution
and SiLU with the existing 0.002 relative-RMS/peak-scaled limits. Each check
contains 24 samples spanning boundaries. Finite disagreement retains all
timings and exit1; guard, unwritten, nonfinite or device failures stop with
exit2. Representative failed arrays and every comparison/hash are preserved.

Local host/device object compilation passes, with inherited provider enum
warnings and the fixture's inherited ignored hipFree-return warning. This is
not GPU qualification. Actual .157 host tests now pass39/39 Debug and39/39
ASan/UBSan, with all six command exits0 and seven artifacts collected. Frozen
plan6599fc47 binds287 fixture hashes; checkpoint and fresh coordination checks
precede the component-only GPU window. Collect and publish
closure before analysis. No model controls, Q4 or full context curve are rerun.

[Fixture binding](../config/q2-ssm-resident-fixture.json),
[compiler evidence](../config/q2-hc-up-short-chain-static.json),
[provenance](../third_party/gufo/LIE-Q2-SSM-RESIDENT.md).
